use std::path::PathBuf;

use serde_json::{json, Value};
use tokio::sync::RwLock;
use whisper_rs::{FullParams, SamplingStrategy, WhisperContext, WhisperContextParameters, WhisperState};

pub struct AsrEngine {
    inner: RwLock<AsrInner>,
}

struct AsrInner {
    model_path: Option<PathBuf>,
    ctx: Option<WhisperContext>,
    state: Option<WhisperState>,
    ready: bool,
}

impl AsrEngine {
    pub fn new() -> Self {
        Self {
            inner: RwLock::new(AsrInner {
                model_path: None,
                ctx: None,
                state: None,
                ready: false,
            }),
        }
    }

    pub async fn snapshot(&self) -> Value {
        let inner = self.inner.read().await;
        json!({
            "ready": inner.ready,
            "model_path": inner.model_path.as_ref().map(|p| p.to_string_lossy().to_string()),
        })
    }

    pub async fn ensure_ready(&self, model_path: PathBuf) -> Result<(), String> {
        {
            let inner = self.inner.read().await;
            if inner.ready && inner.model_path.as_ref() == Some(&model_path) {
                return Ok(());
            }
        }

        if !model_path.exists() {
            return Err(format!("Whisper 模型文件不存在：{}", model_path.display()));
        }

        let ctx = WhisperContext::new_with_params(
            model_path.to_str().ok_or("模型路径包含非法字符")?,
            WhisperContextParameters::default(),
        )
        .map_err(|e| format!("加载 Whisper 模型失败：{}", e))?;
        let state = ctx
            .create_state()
            .map_err(|e| format!("创建 Whisper 状态失败：{}", e))?;

        let mut inner = self.inner.write().await;
        inner.ctx = Some(ctx);
        inner.state = Some(state);
        inner.model_path = Some(model_path);
        inner.ready = true;
        Ok(())
    }

    pub async fn transcribe(&self, audio: &[f32], sample_rate: u32, language: Option<&str>) -> Result<Value, String> {
        if audio.is_empty() {
            return Ok(json!({
                "ok": true,
                "text": "",
                "segments": []
            }));
        }

        let resampled = if sample_rate != 16000 {
            resample_linear(audio, sample_rate, 16000)
        } else {
            audio.to_vec()
        };

        let mut inner = self.inner.write().await;
        if !inner.ready {
            return Err("Whisper 尚未加载，请先确保模型已就绪".into());
        }
        let state = inner
            .state
            .as_mut()
            .ok_or("Whisper 状态未初始化")?;

        let mut params = FullParams::new(SamplingStrategy::Greedy { best_of: 1 });
        params.set_n_threads(std::cmp::max(1, num_cpus() as i32));
        params.set_language(language);
        params.set_print_special(false);
        params.set_print_progress(false);
        params.set_print_realtime(false);
        params.set_print_timestamps(false);
        params.set_single_segment(false);

        state
            .full(params, &resampled)
            .map_err(|e| format!("Whisper 转写失败：{}", e))?;

        let n_segments = state.full_n_segments();
        let mut segments = Vec::new();
        let mut full_text = String::new();
        for i in 0..n_segments {
            let Some(segment) = state.get_segment(i) else {
                continue;
            };
            let text = segment
                .to_str_lossy()
                .map_err(|e| format!("读取转写文本失败：{}", e))?
                .into_owned();
            let trimmed = text.trim().to_string();
            if trimmed.is_empty() {
                continue;
            }
            segments.push(json!({
                "index": i,
                "start_cs": segment.start_timestamp(),
                "end_cs": segment.end_timestamp(),
                "text": text
            }));
            if !full_text.is_empty() {
                full_text.push('\n');
            }
            full_text.push_str(&trimmed);
        }

        Ok(json!({
            "ok": true,
            "text": full_text,
            "segments": segments,
            "segment_count": segments.len(),
        }))
    }
}

fn resample_linear(samples: &[f32], from_rate: u32, to_rate: u32) -> Vec<f32> {
    if samples.is_empty() || from_rate == 0 || to_rate == 0 {
        return samples.to_vec();
    }
    let ratio = from_rate as f64 / to_rate as f64;
    let new_len = ((samples.len() as f64) / ratio).ceil() as usize;
    let mut out = Vec::with_capacity(new_len);
    for i in 0..new_len {
        let pos = i as f64 * ratio;
        let idx = pos as usize;
        let frac = pos - idx as f64;
        let s0 = samples.get(idx).copied().unwrap_or(0.0);
        let s1 = samples.get(idx + 1).copied().unwrap_or(s0);
        out.push((s0 as f64 * (1.0 - frac) + s1 as f64 * frac) as f32);
    }
    out
}

fn num_cpus() -> usize {
    std::thread::available_parallelism()
        .map(|n| n.get())
        .unwrap_or(1)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn resample_linear_handles_empty_input() {
        let out = resample_linear(&[], 48000, 16000);
        assert!(out.is_empty());
    }

    #[test]
    fn resample_linear_preserves_length_ratio() {
        let samples: Vec<f32> = (0..48000).map(|i| ((i % 100) as f32) / 100.0).collect();
        let out = resample_linear(&samples, 48000, 16000);
        assert!((out.len() as i64 - 16000).unsigned_abs() <= 1);
    }
}
