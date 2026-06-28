//! 聊天历史持久化。
//!
//! 消息存储在 `data_dir/chat/history.json`，支持加载、追加、清空。

use chrono::Local;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::path::PathBuf;
use tokio::fs;
use tokio::io::AsyncWriteExt;

/// 单条聊天消息。
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ChatMessage {
    pub sender: String,
    pub text: String,
    #[serde(default)]
    pub ref_text: String,
    pub time: String,
}

/// 聊天历史存储。
pub struct ChatStore {
    file_path: PathBuf,
}

impl ChatStore {
    pub async fn new(data_dir: PathBuf) -> Self {
        let dir = data_dir.join("chat");
        fs::create_dir_all(&dir)
            .await
            .expect("failed to create chat directory");
        Self {
            file_path: dir.join("history.json"),
        }
    }

    /// 加载所有历史消息。
    pub async fn load_messages(&self) -> Result<Vec<ChatMessage>, String> {
        if !self.file_path.exists() {
            return Ok(Vec::new());
        }
        let text = fs::read_to_string(&self.file_path)
            .await
            .map_err(|e| e.to_string())?;
        let messages: Vec<ChatMessage> =
            serde_json::from_str(&text).map_err(|e| e.to_string())?;
        Ok(messages)
    }

    /// 追加一条消息并持久化。
    pub async fn append_message(&self, sender: &str, text: &str, ref_text: &str) -> Result<ChatMessage, String> {
        let mut messages = self.load_messages().await?;
        let message = ChatMessage {
            sender: sender.to_string(),
            text: text.to_string(),
            ref_text: ref_text.to_string(),
            time: Local::now().format("%Y-%m-%d %H:%M:%S").to_string(),
        };
        messages.push(message.clone());
        self.save_messages(&messages).await?;
        Ok(message)
    }

    /// 清空历史。
    pub async fn clear(&self) -> Result<(), String> {
        self.save_messages(&[]).await
    }

    /// 获取最近 N 条消息。
    pub async fn recent_messages(&self, n: usize) -> Result<Vec<ChatMessage>, String> {
        let messages = self.load_messages().await?;
        let len = messages.len();
        if len <= n {
            Ok(messages)
        } else {
            Ok(messages[len - n..].to_vec())
        }
    }

    async fn save_messages(&self, messages: &[ChatMessage]) -> Result<(), String> {
        let json = serde_json::to_string_pretty(messages).map_err(|e| e.to_string())?;
        let mut file = fs::File::create(&self.file_path)
            .await
            .map_err(|e| format!("failed to create chat file: {}", e))?;
        file.write_all(json.as_bytes())
            .await
            .map_err(|e| format!("failed to write chat file: {}", e))?;
        file.flush()
            .await
            .map_err(|e| format!("failed to flush chat file: {}", e))?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn chat_store_append_and_load() {
        let dir = std::env::temp_dir().join(format!("metascend-chat-test-{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir).await;
        fs::create_dir_all(&dir).await.unwrap();

        let store = ChatStore::new(dir.clone()).await;

        // 空历史
        let msgs = store.load_messages().await.unwrap();
        assert!(msgs.is_empty());

        // 追加消息
        store.append_message("User", "你好", "").await.unwrap();
        store.append_message("AI", "你好！有什么可以帮你？", "免责声明").await.unwrap();

        let msgs = store.load_messages().await.unwrap();
        assert_eq!(msgs.len(), 2);
        assert_eq!(msgs[0].sender, "User");
        assert_eq!(msgs[1].sender, "AI");

        // 最近 N 条
        let recent = store.recent_messages(1).await.unwrap();
        assert_eq!(recent.len(), 1);
        assert_eq!(recent[0].text, "你好！有什么可以帮你？");

        // 清空
        store.clear().await.unwrap();
        let msgs = store.load_messages().await.unwrap();
        assert!(msgs.is_empty());

        let _ = fs::remove_dir_all(&dir).await;
    }
}
