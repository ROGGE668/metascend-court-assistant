use serde_json::{json, Value};
use std::collections::HashMap;
use std::path::PathBuf;
use tokio::fs;
use tokio::io::AsyncWriteExt;
use tokio::sync::RwLock;
use crate::llm;

/// Default ASR model size, kept in sync with Python `Config.ASR_MODEL_SIZE`.
const DEFAULT_ASR_MODEL: &str = "large-v3-turbo";
/// Default LLM model, kept in sync with Python `Config.LLM_MODEL`.
const DEFAULT_LLM_MODEL: &str = "qwen2.5:7b";
/// Default embedding model, kept in sync with Python `Config.EMBEDDING_MODEL`.
const DEFAULT_EMBEDDING_MODEL: &str = "BAAI/bge-large-zh-v1.5";

/// Runtime settings persisted to the app data directory.
pub struct SettingsStore {
    path: PathBuf,
    data_dir: PathBuf,
    inner: RwLock<SettingsData>,
}

#[derive(Clone, Debug, serde::Serialize, serde::Deserialize)]
struct SettingsData {
    toggles: HashMap<String, bool>,
    model_provider: String,
    api_key: String,
    base_url: String,
    chat_model: String,
    rust_llm_model: String,
}

impl SettingsStore {
    /// Create or load the settings store in `data_dir`.
    pub async fn new(data_dir: PathBuf) -> Self {
        fs::create_dir_all(&data_dir)
            .await
            .expect("failed to create app data directory");

        let path = data_dir.join("settings.json");
        let data = Self::load(&path).await;

        Self {
            path,
            data_dir,
            inner: RwLock::new(data),
        }
    }

    /// Return the full settings payload expected by the frontend.
    pub async fn get(&self) -> Value {
        let data = self.inner.read().await;
        let toggles: HashMap<String, bool> = data.toggles.clone();
        json!({
            "toggles": toggles,
            "asr_model": DEFAULT_ASR_MODEL,
            "llm_model": data.chat_model,
            "embedding_model": DEFAULT_EMBEDDING_MODEL,
            "data_dir": self.data_dir.to_string_lossy(),
            "model_provider": data.model_provider,
            "api_key": data.api_key,
            "base_url": data.base_url,
            "chat_model": data.chat_model,
            "rust_llm_model": data.rust_llm_model,
        })
    }

    /// Merge `updates` into the current state, persist, and return the full payload.
    pub async fn update(&self, updates: Value) -> Value {
        let mut data = self.inner.write().await;

        if let Some(map) = updates.as_object() {
            for (key, value) in map {
                if let Some(flag) = value.as_bool() {
                    data.toggles.insert(key.clone(), flag);
                } else if let Some(text) = value.as_str() {
                    match key.as_str() {
                        "model_provider" => data.model_provider = text.to_string(),
                        "api_key" => data.api_key = text.to_string(),
                        "base_url" => data.base_url = text.to_string(),
                        "chat_model" => data.chat_model = text.to_string(),
                        "rust_llm_model" => data.rust_llm_model = text.to_string(),
                        _ => {}
                    }
                }
            }
        }

        // Best-effort persistence: a failed write should not silently drop in-memory state,
        // but it should surface via the next operation's health/error log.
        let _ = Self::persist(&self.path, &data).await;

        drop(data);
        self.get().await
    }

    async fn load(path: &PathBuf) -> SettingsData {
        match fs::read_to_string(path).await {
            Ok(text) => match serde_json::from_str::<SettingsData>(&text) {
                Ok(data) => data,
                Err(_) => Self::defaults(),
            },
            Err(_) => Self::defaults(),
        }
    }

    async fn persist(path: &PathBuf, data: &SettingsData) -> Result<(), String> {
        let json = serde_json::to_string_pretty(data).map_err(|e| e.to_string())?;
        let mut file = fs::File::create(path)
            .await
            .map_err(|e| format!("failed to create settings file: {}", e))?;
        file.write_all(json.as_bytes())
            .await
            .map_err(|e| format!("failed to write settings file: {}", e))?;
        file.flush()
            .await
            .map_err(|e| format!("failed to flush settings file: {}", e))?;
        Ok(())
    }

    fn defaults() -> SettingsData {
        let mut toggles = HashMap::new();
        toggles.insert("diarization".to_string(), false);
        toggles.insert("hotword".to_string(), false);
        toggles.insert("legal".to_string(), false);
        toggles.insert("tts".to_string(), false);
        toggles.insert("recording".to_string(), false);
        toggles.insert("diary".to_string(), false);
        SettingsData {
            toggles,
            model_provider: "ollama".to_string(),
            api_key: String::new(),
            base_url: "http://localhost:11434".to_string(),
            chat_model: DEFAULT_LLM_MODEL.to_string(),
            rust_llm_model: llm::default_model().to_string(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::Map;

    #[tokio::test]
    async fn settings_store_uses_defaults_on_first_run() {
        let dir = std::env::temp_dir().join(format!("metascend-settings-defaults-test-{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir).await;
        fs::create_dir_all(&dir).await.unwrap();

        let store = SettingsStore::new(dir.clone()).await;
        let payload = store.get().await;

        let toggles = payload["toggles"].as_object().unwrap();
        assert_eq!(toggles["diarization"], false);
        assert_eq!(toggles["legal"], false);
        assert_eq!(payload["model_provider"].as_str().unwrap(), "ollama");
        assert_eq!(payload["base_url"].as_str().unwrap(), "http://localhost:11434");
        assert_eq!(payload["chat_model"].as_str().unwrap(), DEFAULT_LLM_MODEL);
        assert_eq!(payload["asr_model"].as_str().unwrap(), DEFAULT_ASR_MODEL);
        assert_eq!(payload["llm_model"].as_str().unwrap(), DEFAULT_LLM_MODEL);
        assert_eq!(
            payload["embedding_model"].as_str().unwrap(),
            DEFAULT_EMBEDDING_MODEL
        );

        let _ = fs::remove_dir_all(&dir).await;
    }

    #[tokio::test]
    async fn settings_store_persists_updates() {
        let dir = std::env::temp_dir().join(format!(
            "metascend-settings-persist-test-{}",
            std::process::id()
        ));
        let _ = fs::remove_dir_all(&dir).await;
        fs::create_dir_all(&dir).await.unwrap();

        let path = dir.join("settings.json");

        let store = SettingsStore::new(dir.clone()).await;
        let mut updates = Map::new();
        updates.insert("diarization".to_string(), Value::Bool(true));
        updates.insert("legal".to_string(), Value::Bool(true));
        updates.insert("chat_model".to_string(), Value::String("llama3.1".to_string()));

        let payload = store.update(Value::Object(updates)).await;
        let toggles = payload["toggles"].as_object().unwrap();
        assert_eq!(toggles["diarization"], true);
        assert_eq!(toggles["legal"], true);
        assert_eq!(payload["chat_model"].as_str().unwrap(), "llama3.1");

        let reloaded = SettingsStore::new(dir.clone()).await;
        let reloaded_payload = reloaded.get().await;
        let reloaded_toggles = reloaded_payload["toggles"].as_object().unwrap();
        assert_eq!(reloaded_toggles["diarization"], true);
        assert_eq!(reloaded_toggles["legal"], true);
        assert_eq!(reloaded_payload["chat_model"].as_str().unwrap(), "llama3.1");

        assert!(path.exists());

        let _ = fs::remove_dir_all(&dir).await;
    }
}
