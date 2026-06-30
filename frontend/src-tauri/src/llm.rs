//! Rust-native LLM inference using candle-transformers (Qwen3 quantized GGUF).

use candle_core::{quantized::gguf_file, Device, Tensor};
use candle_transformers::generation::{LogitsProcessor, Sampling};
use candle_transformers::models::quantized_qwen3::ModelWeights;
use std::fs::File;
use std::io::BufReader;
use std::path::PathBuf;
use tokenizers::Tokenizer;

const DEFAULT_RUST_LLM_MODEL: &str = "Qwen/Qwen3-0.6B-GGUF";
const DEFAULT_GGUF_FILE: &str = "qwen3-0.6b-q4_k_m.gguf";
const MAX_NEW_TOKENS: usize = 512;
const TEMPERATURE: f64 = 0.7;
const TOP_P: f64 = 0.9;

#[derive(Clone, Debug)]
pub struct ConversationTurn {
    pub role: String,
    pub content: String,
}

pub struct LlmEngine {
    model: std::sync::Mutex<ModelWeights>,
    tokenizer: Tokenizer,
    device: Device,
    history: std::sync::Mutex<Vec<ConversationTurn>>,
}

impl LlmEngine {
    pub fn load(model_id_or_path: &str, cache_dir: PathBuf) -> Result<Self, String> {
        let device = Device::Cpu;
        let (gguf_path, tokenizer_path) = Self::ensure_files(model_id_or_path, &cache_dir)?;
        let mut reader = BufReader::new(
            File::open(&gguf_path).map_err(|e| format!("open GGUF failed: {}", e))?,
        );
        let content = gguf_file::Content::read(&mut reader)
            .map_err(|e| format!("read GGUF failed: {}", e))?;
        let model = ModelWeights::from_gguf(content, &mut reader, &device)
            .map_err(|e| format!("load Qwen3 GGUF failed: {}", e))?;
        let tokenizer = if tokenizer_path.exists() {
            Tokenizer::from_file(&tokenizer_path).map_err(|e| e.to_string())?
        } else {
            return Err("tokenizer.json not found near GGUF file".into());
        };
        Ok(Self {
            model: std::sync::Mutex::new(model),
            tokenizer,
            device,
            history: std::sync::Mutex::new(Vec::new()),
        })
    }

    fn ensure_files(model_id_or_path: &str, cache_dir: &PathBuf) -> Result<(PathBuf, PathBuf), String> {
        let local = PathBuf::from(model_id_or_path);
        if local.exists() && local.extension().and_then(|s| s.to_str()) == Some("gguf") {
            let tok = local.parent().unwrap_or(&local).join("tokenizer.json");
            return Ok((local, tok));
        }
        if local.is_dir() {
            let gguf = Self::find_gguf_in_dir(&local)?;
            let tok = local.join("tokenizer.json");
            return Ok((gguf, tok));
        }
        match try_hf_hub_gguf(model_id_or_path, cache_dir) {
            Ok(paths) => return Ok(paths),
            Err(e) => eprintln!("HF hub download failed ({}), trying ModelScope...", e),
        }
        try_modelscope_gguf(model_id_or_path, cache_dir)
    }

    fn find_gguf_in_dir(dir: &PathBuf) -> Result<PathBuf, String> {
        let mut ggufs: Vec<PathBuf> = std::fs::read_dir(dir)
            .map_err(|e| e.to_string())?
            .filter_map(|e| e.ok().map(|e| e.path()))
            .filter(|p| p.extension().and_then(|s| s.to_str()) == Some("gguf"))
            .collect();
        if ggufs.is_empty() {
            return Err(format!("no .gguf in {}", dir.display()));
        }
        ggufs.sort();
        Ok(ggufs[0].clone())
    }

    pub fn chat(&self, user_prompt: &str) -> Result<String, String> {
        self.chat_with_history(user_prompt)
    }

    pub fn chat_with_history(&self, user_prompt: &str) -> Result<String, String> {
        let system = "You are a professional legal assistant. Answer concisely and accurately based on Chinese law. Reply in the same language as the user.";
        let mut history = self.history.lock().map_err(|e| e.to_string())?;
        let mut fp = format!("<|im_start|>system\n{}\n</think>\n", system);
        for t in history.iter() {
            fp.push_str(&format!("<|im_start|>{}\n{}\n</think>\n", t.role, t.content));
        }
        fp.push_str(&format!("<|im_start|>user\n{}\n</think>\n<|im_start|>assistant\n", user_prompt));
        let encoding = self.tokenizer.encode(fp, true).map_err(|e| e.to_string())?;
        let mut tokens: Vec<u32> = encoding.get_ids().to_vec();
        let eos: Vec<u32> = ["</think>", "</think>"].iter().filter_map(|t| self.tokenizer.token_to_id(t)).collect();
        let mut model = self.model.lock().map_err(|e| e.to_string())?;
        model.clear_kv_cache();
        let input = Tensor::new(tokens.as_slice(), &self.device).map_err(|e| e.to_string())?.unsqueeze(0).map_err(|e| e.to_string())?;
        let logits = model.forward(&input, 0).map_err(|e| e.to_string())?;
        let logits = logits.squeeze(0).map_err(|e| e.to_string())?.squeeze(0).map_err(|e| e.to_string())?;
        let sampling = Sampling::TopP { p: TOP_P, temperature: TEMPERATURE };
        let mut lp = LogitsProcessor::from_sampling(299792458, sampling);
        let next = lp.sample(&logits).map_err(|e| e.to_string())?;
        tokens.push(next);
        let mut gen = vec![next];
        if !eos.contains(&next) {
            for _ in 0..MAX_NEW_TOKENS {
                let i = Tensor::new(&[tokens[tokens.len() - 1]], &self.device).map_err(|e| e.to_string())?.unsqueeze(0).map_err(|e| e.to_string())?;
                let l = model.forward(&i, tokens.len() - 1).map_err(|e| e.to_string())?;
                let l = l.squeeze(0).map_err(|e| e.to_string())?.squeeze(0).map_err(|e| e.to_string())?;
                let n = lp.sample(&l).map_err(|e| e.to_string())?;
                tokens.push(n);
                if eos.contains(&n) { break; }
                gen.push(n);
            }
        }
        drop(model);
        let reply = self.tokenizer.decode(&gen, true).map_err(|e| e.to_string())?;
        let reply = reply.trim().to_string();
        history.push(ConversationTurn { role: "user".to_string(), content: user_prompt.to_string() });
        history.push(ConversationTurn { role: "assistant".to_string(), content: reply.clone() });
        if history.len() > 20 { history.drain(..4); }
        Ok(reply)
    }

    pub fn clear_history(&self) {
        if let Ok(mut h) = self.history.lock() { h.clear(); }
    }

    pub fn history_length(&self) -> usize {
        self.history.lock().map(|h| h.len()).unwrap_or(0)
    }
}

fn huggingface_endpoint() -> String {
    if let Ok(endpoint) = std::env::var("HF_ENDPOINT") {
        if !endpoint.is_empty() {
            return endpoint.trim_end_matches("/").to_string();
        }
    }
    "https://hf-mirror.com".to_string()
}

fn try_hf_hub_gguf(model_id: &str, cache_dir: &PathBuf) -> Result<(PathBuf, PathBuf), String> {
    let api = hf_hub::api::sync::ApiBuilder::new()
        .with_cache_dir(cache_dir.clone())
        .with_endpoint(huggingface_endpoint())
        .build()
        .map_err(|e| e.to_string())?;
    let repo = api.model(model_id.to_string());
    let gguf_path = repo.get(DEFAULT_GGUF_FILE).map_err(|e| format!("download GGUF failed: {}", e))?;
    let tokenizer_path = repo.get("tokenizer.json").map_err(|e| format!("download tokenizer failed: {}", e))?;
    Ok((gguf_path, tokenizer_path))
}

fn try_modelscope_gguf(model_id: &str, cache_dir: &PathBuf) -> Result<(PathBuf, PathBuf), String> {
    let parts: Vec<&str> = model_id.split('/').collect();
    if parts.len() != 2 {
        return Err(format!("model_id '{}' is not namespace/model_name", model_id));
    }
    let namespace = parts[0].to_lowercase();
    let model_name = parts[1];
    let model_dir = cache_dir.join("modelscope").join(format!("{}_{}", namespace, model_name));
    std::fs::create_dir_all(&model_dir).map_err(|e| e.to_string())?;
    let gguf_path = model_dir.join(DEFAULT_GGUF_FILE);
    let tokenizer_path = model_dir.join("tokenizer.json");
    for (file, path) in [(DEFAULT_GGUF_FILE, &gguf_path), ("tokenizer.json", &tokenizer_path)] {
        if !path.exists() {
            let url = format!("https://www.modelscope.cn/models/{}/{}/resolve/master/{}", namespace, model_name, file);
            eprintln!("Downloading {} from ModelScope: {}", file, url);
            download_file(&url, path).map_err(|e| format!("download {} failed: {}", file, e))?;
        }
    }
    Ok((gguf_path, tokenizer_path))
}

fn download_file(url: &str, path: &PathBuf) -> Result<(), String> {
    if let Err(e) = download_file_reqwest(url, path) {
        eprintln!("reqwest failed ({}), retrying with curl...", e);
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
        .args(["-fsSL", "--connect-timeout", "30", "--max-time", "600", "-A", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36", "-o", &path.to_string_lossy(), url])
        .status()
        .map_err(|e| format!("spawn curl failed: {}", e))?;
    if !status.success() {
        return Err(format!("curl exited with {}", status));
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
    #[ignore = "downloads Qwen3 GGUF from HuggingFace/ModelScope"]
    fn qwen3_chat_smoke() {
        let cache = std::env::temp_dir().join("metascend-llm-smoke-cache");
        let engine = LlmEngine::load(default_model(), cache).expect("load failed");
        let reply = engine.chat("Hello, who are you?").expect("chat failed");
        println!("reply: {}", reply);
        assert!(!reply.is_empty());
    }
}
