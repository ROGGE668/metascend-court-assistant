//! Rust-native LLM inference using candle-transformers (Qwen2.5).

use candle_core::{Device, DType, Tensor};
use candle_nn::VarBuilder;
use candle_transformers::generation::{LogitsProcessor, Sampling};
use candle_transformers::models::qwen2::{Config as QwenConfig, ModelForCausalLM};
use std::path::PathBuf;
use tokenizers::Tokenizer;

const DEFAULT_RUST_LLM_MODEL: &str = "Qwen/Qwen2.5-0.5B-Instruct";
const MAX_NEW_TOKENS: usize = 256;
const TEMPERATURE: f64 = 0.7;
const TOP_P: f64 = 0.9;

pub struct LlmEngine {
    model: std::sync::Mutex<ModelForCausalLM>,
    tokenizer: Tokenizer,
    device: Device,
}

impl LlmEngine {
    /// Load from a local dir or download from Hugging Face.
    pub fn load(model_id_or_path: &str, cache_dir: PathBuf) -> Result<Self, String> {
        // Metal acceleration is disabled by default because candle-transformers
        // lacks a Metal implementation for RMSNorm used by Qwen2, which causes
        // "Metal error no metal implementation for rms-norm" at inference time.
        // Users can opt-in to Metal/CUDA via METASCEND_LLM_DEVICE=metal|cuda.
        let device = match std::env::var("METASCEND_LLM_DEVICE").unwrap_or_default().to_lowercase().as_str() {
            "metal" => Device::new_metal(0).unwrap_or(Device::Cpu),
            "cuda" => Device::new_cuda(0).unwrap_or(Device::Cpu),
            _ => Device::Cpu,
        };
        let dtype = if device.is_metal() {
            DType::F16
        } else {
            DType::F32
        };

        let (config_path, tokenizer_path, model_paths) =
            Self::ensure_files(model_id_or_path, &cache_dir)?;

        let config: QwenConfig = serde_json::from_str(
            &std::fs::read_to_string(&config_path).map_err(|e| e.to_string())?,
        )
        .map_err(|e| e.to_string())?;
        let tokenizer = Tokenizer::from_file(&tokenizer_path).map_err(|e| e.to_string())?;
        let vb = unsafe {
            VarBuilder::from_mmaped_safetensors(&model_paths, dtype, &device)
                .map_err(|e| e.to_string())?
        };
        let model = ModelForCausalLM::new(&config, vb).map_err(|e| e.to_string())?;
        Ok(Self {
            model: std::sync::Mutex::new(model),
            tokenizer,
            device,
        })
    }

    fn ensure_files(
        model_id_or_path: &str,
        cache_dir: &PathBuf,
    ) -> Result<(PathBuf, PathBuf, Vec<PathBuf>), String> {
        let local = PathBuf::from(model_id_or_path);
        if local.is_dir()
            && local.join("config.json").exists()
            && local.join("tokenizer.json").exists()
        {
            let model_file = local.join("model.safetensors");
            if !model_file.exists() {
                let mut shards: Vec<PathBuf> = std::fs::read_dir(&local)
                    .map_err(|e| e.to_string())?
                    .filter_map(|e| e.ok().map(|e| e.path()))
                    .filter(|p| {
                        let name = p.file_name().and_then(|n| n.to_str()).unwrap_or("");
                        name.starts_with("model-") && name.ends_with(".safetensors")
                    })
                    .collect();
                if shards.is_empty() {
                    return Err(format!(
                        "no model.safetensors found in {}",
                        local.display()
                    ));
                }
                shards.sort();
                return Ok((local.join("config.json"), local.join("tokenizer.json"), shards));
            }
            return Ok((local.join("config.json"), local.join("tokenizer.json"), vec![model_file]));
        }

        // Try HuggingFace / configured mirror first, then ModelScope fallback.
        match try_hf_hub(model_id_or_path, cache_dir) {
            Ok(paths) => return Ok(paths),
            Err(e) => eprintln!("HF hub download failed ({}), trying ModelScope fallback...", e),
        }
        try_modelscope(model_id_or_path, cache_dir)
    }

    /// Generate a reply for a user prompt.
    pub fn chat(&self, user_prompt: &str) -> Result<String, String> {
        let system = "你是一位专业的法律助手，回答简洁、准确，只基于中国现行法律常识。";
        let prompt = format!(
            "<|im_start|>system\n{}\n<|im_end|>\n<|im_start|>user\n{}\n<|im_end|>\n<|im_start|>assistant\n",
            system, user_prompt
        );
        let encoding = self.tokenizer.encode(prompt, true).map_err(|e| e.to_string())?;
        let mut tokens: Vec<u32> = encoding.get_ids().to_vec();

        let eos_tokens: Vec<u32> = ["<|im_end|>", "<|endoftext|>"]
            .iter()
            .filter_map(|t| self.tokenizer.token_to_id(t))
            .collect();

        let mut model = self.model.lock().map_err(|e| e.to_string())?;
        model.clear_kv_cache();

        let input = Tensor::new(tokens.as_slice(), &self.device)
            .map_err(|e| e.to_string())?
            .unsqueeze(0)
            .map_err(|e| e.to_string())?;
        let logits = model.forward(&input, 0).map_err(|e| e.to_string())?;
        let logits = logits
            .squeeze(0)
            .map_err(|e| e.to_string())?
            .squeeze(0)
            .map_err(|e| e.to_string())?;
        let sampling = Sampling::TopP {
            p: TOP_P,
            temperature: TEMPERATURE,
        };
        let mut logits_processor = LogitsProcessor::from_sampling(299792458, sampling);
        let next_token = logits_processor.sample(&logits).map_err(|e| e.to_string())?;
        tokens.push(next_token);

        let mut generated = vec![next_token];
        if !eos_tokens.contains(&next_token) {
            for _ in 0..MAX_NEW_TOKENS {
                let input = Tensor::new(&[tokens[tokens.len() - 1]], &self.device)
                    .map_err(|e| e.to_string())?
                    .unsqueeze(0)
                    .map_err(|e| e.to_string())?;
                let logits = model.forward(&input, tokens.len() - 1).map_err(|e| e.to_string())?;
                let logits = logits
                    .squeeze(0)
                    .map_err(|e| e.to_string())?
                    .squeeze(0)
                    .map_err(|e| e.to_string())?;
                let next_token = logits_processor.sample(&logits).map_err(|e| e.to_string())?;
                tokens.push(next_token);
                if eos_tokens.contains(&next_token) {
                    break;
                }
                generated.push(next_token);
            }
        }
        drop(model);
        let text = self
            .tokenizer
            .decode(&generated, true)
            .map_err(|e| e.to_string())?;
        Ok(text.trim().to_string())
    }
}

    fn huggingface_endpoint() -> String {
        if let Ok(endpoint) = std::env::var("HF_ENDPOINT") {
            if !endpoint.is_empty() {
                return endpoint.trim_end_matches("/").to_string();
            }
        }
        // Default to a mirror because the upstream huggingface.co endpoint is
        // not reachable in this environment. Users outside China can override
        // with the HF_ENDPOINT environment variable.
        "https://hf-mirror.com".to_string()
    }



fn try_hf_hub(
    model_id: &str,
    cache_dir: &PathBuf,
) -> Result<(PathBuf, PathBuf, Vec<PathBuf>), String> {
    let api = hf_hub::api::sync::ApiBuilder::new()
        .with_cache_dir(cache_dir.clone())
        .with_endpoint(huggingface_endpoint())
        .build()
        .map_err(|e| e.to_string())?;
    let repo = api.model(model_id.to_string());
    let config_path = repo.get("config.json").map_err(|e| e.to_string())?;
    let tokenizer_path = repo.get("tokenizer.json").map_err(|e| e.to_string())?;
    let model_path = repo.get("model.safetensors").map_err(|e| e.to_string())?;
    Ok((config_path, tokenizer_path, vec![model_path]))
}

/// Fallback downloader for HuggingFace models hosted on ModelScope.
/// This is needed because the upstream huggingface.co endpoint is often
/// unreachable in China, while ModelScope (modelscope.cn) is local and fast.
fn try_modelscope(
    model_id: &str,
    cache_dir: &PathBuf,
) -> Result<(PathBuf, PathBuf, Vec<PathBuf>), String> {
    let parts: Vec<&str> = model_id.split('/').collect();
    if parts.len() != 2 {
        return Err(format!("model_id '{}' is not namespace/model_name", model_id));
    }
    let namespace = parts[0].to_lowercase();
    let model_name = parts[1];

    let model_dir = cache_dir
        .join("modelscope")
        .join(format!("{}_{}", namespace, model_name));
    std::fs::create_dir_all(&model_dir).map_err(|e| e.to_string())?;

    let files = ["config.json", "tokenizer.json", "model.safetensors"];
    let mut paths = Vec::with_capacity(files.len());
    for file in &files {
        let path = model_dir.join(file);
        if !path.exists() {
            let url = format!(
                "https://www.modelscope.cn/models/{}/{}/resolve/master/{}",
                namespace, model_name, file
            );
            eprintln!("Downloading {} from ModelScope: {}", file, url);
            download_file(&url, &path).map_err(|e| {
                format!("failed to download {} from ModelScope: {}", file, e)
            })?;
        }
        paths.push(path);
    }

    Ok((paths[0].clone(), paths[1].clone(), vec![paths[2].clone()]))
}

fn download_file(url: &str, path: &PathBuf) -> Result<(), String> {
    // Try reqwest first; if it is blocked (common for some Chinese mirrors),
    // fall back to curl which is available on macOS and handles redirects/cookies
    // more permissively.
    if let Err(e) = download_file_reqwest(url, path) {
        eprintln!("reqwest download failed ({}), retrying with curl...", e);
        return download_file_curl(url, path);
    }
    Ok(())
}

fn download_file_reqwest(url: &str, path: &PathBuf) -> Result<(), String> {
    let client = reqwest::blocking::Client::builder()
        .timeout(std::time::Duration::from_secs(600))
        .user_agent("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
        .build()
        .map_err(|e| e.to_string())?;
    let mut resp = client.get(url).send().map_err(|e| e.to_string())?;
    if !resp.status().is_success() {
        return Err(format!("HTTP {}", resp.status()));
    }
    let mut file = std::fs::File::create(path).map_err(|e| e.to_string())?;
    resp.copy_to(&mut file).map_err(|e| e.to_string())?;
    Ok(())
}

fn download_file_curl(url: &str, path: &PathBuf) -> Result<(), String> {
    let status = std::process::Command::new("curl")
        .args([
            "-fsSL",
            "--connect-timeout",
            "30",
            "--max-time",
            "600",
            "-A",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "-o",
            &path.to_string_lossy(),
            url,
        ])
        .status()
        .map_err(|e| format!("failed to spawn curl: {}", e))?;
    if !status.success() {
        return Err(format!("curl exited with status {}", status));
    }
    Ok(())
}
pub fn default_model() -> &'static str {
    DEFAULT_RUST_LLM_MODEL
}
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    #[ignore = "downloads Qwen2.5 from HuggingFace/ModelScope"]
    fn qwen_chat_smoke() {
        // Use a fixed cache path so repeated manual runs do not re-download the model.
        let cache = std::env::temp_dir().join("metascend-llm-smoke-cache");
        if std::env::var("RUST_LLM_SMOKE_REFRESH").is_ok() {
            let _ = std::fs::remove_dir_all(&cache);
        }
        let engine = LlmEngine::load(default_model(), cache.clone()).expect("load failed");
        let reply = engine.chat("你好，请用一句话介绍自己。").expect("chat failed");
        println!("reply: {}", reply);
        assert!(!reply.is_empty());
    }
}
