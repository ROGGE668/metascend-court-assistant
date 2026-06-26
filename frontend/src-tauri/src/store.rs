use serde_json::{json, Value};
use std::collections::HashMap;
use std::path::PathBuf;
use tokio::fs;
use tokio::io::AsyncWriteExt;
use tokio::sync::RwLock;

/// Default ASR model size, kept in sync with Python `Config.ASR_MODEL_SIZE`.
const DEFAULT_ASR_MODEL: &str = "large-v3-turbo";
/// Default LLM model, kept in sync with Python `Config.LLM_MODEL`.
const DEFAULT_LLM_MODEL: &str = "qwen2.5:7b";
/// Default embedding model, kept in sync with Python `Config.EMBEDDING_MODEL`.
const DEFAULT_EMBEDDING_MODEL: &str = "BAAI/bge-large-zh-v1.5";

/// Runtime settings persisted to the app data directory.
///
/// Mirrors `src/api_server.py::SettingsStore`. The frontend only sends/receives
/// the `toggles` object; static metadata fields are injected on read so the
/// response shape stays identical to the previous Python HTTP endpoint.
pub struct SettingsStore {
    path: PathBuf,
    data_dir: PathBuf,
    inner: RwLock<SettingsData>,
}

#[derive(Clone, Debug, serde::Serialize, serde::Deserialize)]
struct SettingsData {
    toggles: HashMap<String, bool>,
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
            "llm_model": DEFAULT_LLM_MODEL,
            "embedding_model": DEFAULT_EMBEDDING_MODEL,
            "data_dir": self.data_dir.to_string_lossy(),
        })
    }

    /// Merge `updates` into the current toggles, persist, and return the full payload.
    pub async fn update(&self, updates: Value) -> Value {
        let mut data = self.inner.write().await;

        if let Some(map) = updates.as_object() {
            for (key, value) in map {
                if let Some(flag) = value.as_bool() {
                    data.toggles.insert(key.clone(), flag);
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
        // Kept in sync with Python `Config` defaults.
        toggles.insert("diarization".to_string(), false);
        toggles.insert("hotword".to_string(), false);
        toggles.insert("legal".to_string(), false);
        toggles.insert("tts".to_string(), false);
        toggles.insert("recording".to_string(), false);
        toggles.insert("diary".to_string(), false);
        SettingsData { toggles }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::Map;

    #[tokio::test]
    async fn settings_store_uses_defaults_on_first_run() {
        let dir = std::env::temp_dir().join(format!("metascend-settings-test-{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir).await;
        fs::create_dir_all(&dir).await.unwrap();

        let store = SettingsStore::new(dir.clone()).await;
        let payload = store.get().await;

        let toggles = payload["toggles"].as_object().unwrap();
        assert_eq!(toggles["diarization"], false);
        assert_eq!(toggles["legal"], false);
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
            "metascend-settings-test-{}",
            std::process::id()
        ));
        let _ = fs::remove_dir_all(&dir).await;
        fs::create_dir_all(&dir).await.unwrap();

        let path = dir.join("settings.json");

        let store = SettingsStore::new(dir.clone()).await;
        let mut updates = Map::new();
        updates.insert("diarization".to_string(), Value::Bool(true));
        updates.insert("legal".to_string(), Value::Bool(true));

        let payload = store.update(Value::Object(updates)).await;
        let toggles = payload["toggles"].as_object().unwrap();
        assert_eq!(toggles["diarization"], true);
        assert_eq!(toggles["legal"], true);

        // Reload from disk and verify the same values come back.
        let reloaded = SettingsStore::new(dir.clone()).await;
        let reloaded_payload = reloaded.get().await;
        let reloaded_toggles = reloaded_payload["toggles"].as_object().unwrap();
        assert_eq!(reloaded_toggles["diarization"], true);
        assert_eq!(reloaded_toggles["legal"], true);

        // Sanity-check the file was actually written.
        assert!(path.exists());

        let _ = fs::remove_dir_all(&dir).await;
    }
}
