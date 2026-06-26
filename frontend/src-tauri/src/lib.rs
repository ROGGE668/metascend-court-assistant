mod sidecar;
mod store;
mod cases;
mod evidence;
mod knowledge;

use reqwest;
use std::time::Duration;
use serde_json::{json, Value};
use tauri::State;
use tauri::Manager;
use tauri::Emitter;
use sidecar::SidecarManager;
use store::SettingsStore;
use cases::CaseStore;
use evidence::EvidenceStore;
use knowledge::KnowledgeStore;
use std::sync::Arc;

pub struct AppState {
  pub sidecar: Arc<SidecarManager>,
  pub settings_store: Arc<SettingsStore>,
  pub case_store: Arc<CaseStore>,
  pub evidence_store: Arc<EvidenceStore>,
  pub knowledge_store: Arc<KnowledgeStore>,
  pub data_dir: std::path::PathBuf,
}

#[tauri::command]
fn open_url(url: String) -> Result<(), String> {
  open::that(url).map_err(|e| e.to_string())
}

async fn api_get(state: State<'_, AppState>, path: &str) -> Result<Value, String> {
  let url = format!("{}{}", state.sidecar.clone().backend_url().await, path);
  let client = reqwest::Client::builder()
    .no_proxy()
    .timeout(Duration::from_secs(30))
    .build()
    .map_err(|e| e.to_string())?;
  client
    .get(&url)
    .send()
    .await
    .map_err(|e| e.to_string())?
    .json()
    .await
    .map_err(|e| e.to_string())
}

async fn api_post(state: State<'_, AppState>, path: &str, body: Value) -> Result<Value, String> {
  let url = format!("{}{}", state.sidecar.clone().backend_url().await, path);
  let client = reqwest::Client::builder()
    .no_proxy()
    .timeout(Duration::from_secs(30))
    .build()
    .map_err(|e| e.to_string())?;
  client
    .post(&url)
    .json(&body)
    .send()
    .await
    .map_err(|e| e.to_string())?
    .json()
    .await
    .map_err(|e| e.to_string())
}

#[tauri::command]
async fn local_backend_status(state: State<'_, AppState>) -> Result<String, String> {
  match api_get(state, "/health").await {
    Ok(v) => Ok(v["status"].as_str().unwrap_or("ok").to_string()),
    Err(e) => Err(format!("error: {}", e)),
  }
}

// ------------------------------------------------------------------ //
// Realtime courtroom
// ------------------------------------------------------------------ //
#[tauri::command]
async fn start_courtroom(state: State<'_, AppState>) -> Result<Value, String> {
  api_post(state, "/courtroom/start", json!({})).await
}

#[tauri::command]
async fn stop_courtroom(state: State<'_, AppState>) -> Result<Value, String> {
  api_post(state, "/courtroom/stop", json!({})).await
}

#[tauri::command]
async fn get_status(state: State<'_, AppState>) -> Result<Value, String> {
  api_get(state, "/status").await
}

#[tauri::command]
async fn get_transcript(state: State<'_, AppState>) -> Result<Value, String> {
  api_get(state, "/transcript").await
}

#[tauri::command]
async fn get_suggestion(state: State<'_, AppState>) -> Result<Value, String> {
  api_get(state, "/suggestion").await
}

#[tauri::command]
async fn calibrate_role(role: String, state: State<'_, AppState>) -> Result<Value, String> {
  api_post(state, "/calibrate", json!({"role": role})).await
}

// ------------------------------------------------------------------ //
// Cases & evidence
// ------------------------------------------------------------------ //
#[tauri::command]
async fn list_cases(state: State<'_, AppState>) -> Result<Value, String> {
  Ok(Value::Array(state.case_store.list_cases().await?))
}

#[tauri::command]
async fn create_case(title: String, case_type: String, state: State<'_, AppState>) -> Result<Value, String> {
  state.case_store.create_case(title, case_type).await
}

#[tauri::command]
async fn get_case(case_id: String, state: State<'_, AppState>) -> Result<Value, String> {
  match state.case_store.get_case(case_id).await? {
    Some(value) => Ok(value),
    None => Err("case not found".to_string()),
  }
}

#[tauri::command]
async fn list_evidence(state: State<'_, AppState>) -> Result<Value, String> {
  Ok(Value::Array(state.evidence_store.list().await?))
}

#[tauri::command]
async fn import_evidence(source_path: String, state: State<'_, AppState>) -> Result<Value, String> {
  state.evidence_store.import_file(source_path).await
}

#[tauri::command]
async fn delete_evidence(name: String, state: State<'_, AppState>) -> Result<Value, String> {
  state.evidence_store.delete(name).await?;
  Ok(json!({"success": true}))
}

// ------------------------------------------------------------------ //
// Knowledge base
// ------------------------------------------------------------------ //
#[tauri::command]
async fn list_documents(state: State<'_, AppState>) -> Result<Value, String> {
  let docs = state.knowledge_store.list_documents().await?;
  Ok(json!({
    "documents": docs,
    "total": docs.len(),
    "engine": "ChromaDB",
    "embedding_model": "BAAI/bge-large-zh-v1.5"
  }))
}

#[tauri::command]
async fn search_documents(query: String, category: Option<String>, state: State<'_, AppState>) -> Result<Value, String> {
  api_post(state, "/knowledge/search", json!({"query": query, "category": category})).await
}

// ------------------------------------------------------------------ //
// Chat
// ------------------------------------------------------------------ //
#[tauri::command]
async fn chat_ask(message: String, state: State<'_, AppState>) -> Result<Value, String> {
  api_post(state, "/chat/ask", json!({"message": message})).await
}

#[tauri::command]
async fn chat_messages(state: State<'_, AppState>) -> Result<Value, String> {
  api_get(state, "/chat/messages").await
}

// ------------------------------------------------------------------ //
// Settings
// ------------------------------------------------------------------ //
#[tauri::command]
async fn get_settings(state: State<'_, AppState>) -> Result<Value, String> {
  Ok(state.settings_store.get().await)
}

#[tauri::command]
async fn save_settings(toggles: Value, state: State<'_, AppState>) -> Result<Value, String> {
  Ok(state.settings_store.update(toggles).await)
}

// ------------------------------------------------------------------ //
// Knowledge base import / detail
// ------------------------------------------------------------------ //
#[tauri::command]
async fn import_knowledge_document(source_path: String, category: String, state: State<'_, AppState>) -> Result<Value, String> {
  let doc = state.knowledge_store.import_file(source_path, category).await?;
  Ok(json!({
    "id": doc.id,
    "name": doc.name,
    "category": doc.category,
    "status": doc.status,
    "chunks": doc.chunks,
    "date": doc.date,
    "path": doc.path,
  }))
}

#[tauri::command]
async fn get_knowledge_document(path: String, state: State<'_, AppState>) -> Result<Value, String> {
  state.knowledge_store.get_document_content(path).await
}

// ------------------------------------------------------------------ //
// Backend lifecycle
// ------------------------------------------------------------------ //
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  tauri::Builder::default()
    .plugin(tauri_plugin_shell::init())
    .plugin(tauri_plugin_dialog::init())
    .setup(|app| {
      let app_data_dir = app.path().app_data_dir()?;
      let data_dir = app_data_dir.clone();
      let log_dir = app_data_dir.join("logs");
      std::fs::create_dir_all(&log_dir)?;
      let log_path = log_dir.join("backend.log");

      let settings_store = Arc::new(tauri::async_runtime::block_on(SettingsStore::new(data_dir.clone())));
      let case_store = Arc::new(tauri::async_runtime::block_on(CaseStore::new(data_dir.clone())));
      let evidence_store = Arc::new(tauri::async_runtime::block_on(EvidenceStore::new(data_dir.clone())));
      let knowledge_base_dir = sidecar::project_root().join("data").join("knowledge_base");
      let knowledge_store = Arc::new(tauri::async_runtime::block_on(KnowledgeStore::new(knowledge_base_dir)));

      let sidecar = SidecarManager::new(8727, log_path);
      let sidecar_clone = sidecar.clone();
      let app_handle = app.handle().clone();
      tauri::async_runtime::spawn(async move {
        if let Err(e) = SidecarManager::start(sidecar_clone).await {
          eprintln!("Backend readiness check failed: {}", e);
          let _ = app_handle.emit("backend:error", e);
        } else {
          let _ = app_handle.emit("backend:ready", ());
        }
      });

      app.manage(AppState { sidecar, settings_store, case_store, evidence_store, knowledge_store, data_dir });
      Ok(())
    })
    .invoke_handler(tauri::generate_handler![
      open_url,
      local_backend_status,
      start_courtroom,
      stop_courtroom,
      get_status,
      get_transcript,
      get_suggestion,
      calibrate_role,
      list_cases,
      create_case,
      get_case,
      list_evidence,
      import_evidence,
      delete_evidence,
      list_documents,
      search_documents,
      import_knowledge_document,
      get_knowledge_document,
      chat_ask,
      chat_messages,
      get_settings,
      save_settings
    ])
    .build(tauri::generate_context!())
    .expect("error while building tauri application")
    .run(|app_handle: &tauri::AppHandle, event| {
      if let tauri::RunEvent::ExitRequested { api, .. } = event {
        let app_handle = app_handle.clone();
        tauri::async_runtime::spawn(async move {
          if let Some(state) = app_handle.try_state::<AppState>() {
            let _ = state.sidecar.clone().stop().await;
          }
          app_handle.exit(0);
        });
        api.prevent_exit();
      }
    });
}
