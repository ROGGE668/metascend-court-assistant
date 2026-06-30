//! LLM 客户端 —— 通过 MLX Python sidecar 进行推理。
//!
//! Rust 层管理 MLX sidecar 的生命周期（启动、健康检查、重启），
//! 通过本地 HTTP API 调用 `/chat` 端点获取模型回复。
//! 模型：Qwen3.5-9B-MLX-4bit，框架：Apple MLX。

use std::path::PathBuf;
use std::sync::Arc;
use tokio::sync::Mutex;

const DEFAULT_MLX_MODEL: &str = "mlx-community/Qwen3.5-9B-MLX-4bit";
const CHAT_TIMEOUT_SECS: u64 = 120;

/// 聊天消息。
#[derive(Clone, Debug)]
#[allow(dead_code)]
pub struct ConversationTurn {
    pub role: String,
    pub content: String,
}

/// LLM 引擎客户端，通过 HTTP 调用 MLX sidecar。
pub struct LlmEngine {
    backend_url: String,
    client: reqwest::Client,
    history: Arc<Mutex<Vec<ConversationTurn>>>,
}

impl LlmEngine {
    /// 连接到已运行的 MLX sidecar。
    pub fn load(_model_id_or_path: &str, _cache_dir: PathBuf) -> Result<Self, String> {
        // model_id_or_path 在 sidecar 模式下是模型 ID，URL 由调用方传入
        // 但为了兼容现有签名，我们用默认端口
        let url = std::env::var("MLX_BACKEND_URL")
            .unwrap_or_else(|_| "http://127.0.0.1:8727".to_string());

        let client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(CHAT_TIMEOUT_SECS))
            .build()
            .map_err(|e| format!("create HTTP client failed: {}", e))?;

        Ok(Self {
            backend_url: url,
            client,
            history: Arc::new(Mutex::new(Vec::new())),
        })
    }

    /// 使用指定 URL 创建引擎（用于 sidecar 管理场景）。
    pub fn with_url(url: String) -> Result<Self, String> {
        let client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(CHAT_TIMEOUT_SECS))
            .build()
            .map_err(|e| format!("create HTTP client failed: {}", e))?;

        Ok(Self {
            backend_url: url,
            client,
            history: Arc::new(Mutex::new(Vec::new())),
        })
    }

    /// 单轮对话（无历史）。
    pub fn chat(&self, user_prompt: &str) -> Result<String, String> {
        // 同步包装：在当前线程上创建临时 tokio runtime
        let rt = tokio::runtime::Runtime::new().map_err(|e| e.to_string())?;
        rt.block_on(self.chat_async(user_prompt))
    }

    /// 带历史的多轮对话。
    pub fn chat_with_history(&self, user_prompt: &str) -> Result<String, String> {
        let rt = tokio::runtime::Runtime::new().map_err(|e| e.to_string())?;
        rt.block_on(self.chat_async(user_prompt))
    }

    /// 异步对话。
    async fn chat_async(&self, user_prompt: &str) -> Result<String, String> {
        let payload = serde_json::json!({
            "message": user_prompt,
            "max_tokens": 512,
            "temperature": 0.7,
        });

        let resp = self
            .client
            .post(format!("{}/chat", self.backend_url))
            .json(&payload)
            .send()
            .await
            .map_err(|e| format!("MLX sidecar request failed: {}", e))?;

        if !resp.status().is_success() {
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            return Err(format!("MLX sidecar error ({}): {}", status, body));
        }

        let data: serde_json::Value = resp
            .json()
            .await
            .map_err(|e| format!("parse MLX response failed: {}", e))?;

        let reply = data["reply"]
            .as_str()
            .ok_or("MLX response missing 'reply' field")?
            .to_string();

        // 更新本地历史缓存
        let mut history = self.history.lock().await;
        history.push(ConversationTurn {
            role: "user".to_string(),
            content: user_prompt.to_string(),
        });
        history.push(ConversationTurn {
            role: "assistant".to_string(),
            content: reply.clone(),
        });
        if history.len() > 40 {
            history.drain(..2);
        }

        Ok(reply)
    }

    /// 清空对话历史。
    pub fn clear_history(&self) {
        let client = self.client.clone();
        let url = self.backend_url.clone();
        let history = self.history.clone();
        // 异步清除 sidecar 端历史，同步清除本地缓存
        let _ = std::thread::spawn(move || {
            let rt = tokio::runtime::Runtime::new().unwrap();
            let _ = rt.block_on(async {
                let _ = client.post(format!("{}/reset", url)).send().await;
            });
            rt.block_on(async {
                history.lock().await.clear();
            });
        })
        .join();
    }

    /// 当前历史长度。
    pub fn history_length(&self) -> usize {
        // 非 async 场景用 try_lock
        self.history.try_lock().map(|h| h.len()).unwrap_or(0)
    }

    /// 检查 MLX sidecar 是否就绪。
    pub async fn check_health(&self) -> Result<serde_json::Value, String> {
        let resp = self
            .client
            .get(format!("{}/health", self.backend_url))
            .send()
            .await
            .map_err(|e| format!("health check failed: {}", e))?;

        let data: serde_json::Value = resp
            .json()
            .await
            .map_err(|e| format!("parse health response failed: {}", e))?;

        Ok(data)
    }
}

/// 默认模型 ID。
pub fn default_model() -> &'static str {
    DEFAULT_MLX_MODEL
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_model_is_mlx() {
        assert_eq!(default_model(), "mlx-community/Qwen3.5-9B-MLX-4bit");
    }

    #[test]
    #[ignore = "requires running MLX sidecar"]
    fn chat_with_running_sidecar() {
        let engine = LlmEngine::load(default_model(), std::env::temp_dir()).expect("load failed");
        let reply = engine.chat("你好，你是谁？").expect("chat failed");
        println!("reply: {}", reply);
        assert!(!reply.is_empty());
    }
}
