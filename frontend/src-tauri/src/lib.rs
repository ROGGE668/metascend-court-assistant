mod sidecar;

use reqwest;
use serde_json::{json, Value};
use tauri::State;
use tauri::Manager;
use sidecar::SidecarManager;
use std::sync::Arc;

pub struct AppState {
  pub sidecar: Arc<SidecarManager>,
}

#[tauri::command]
fn open_url(url: String) -> Result<(), String> {
  open::that(url).map_err(|e| e.to_string())
}

async fn api_get(state: State<'_, AppState>, path: &str) -> Result<Value, String> {
  let url = format!("{}{}", state.sidecar.clone().backend_url().await, path);
  reqwest::get(&url)
    .await
    .map_err(|e| e.to_string())?
    .json()
    .await
    .map_err(|e| e.to_string())
}

async fn api_post(state: State<'_, AppState>, path: &str, body: Value) -> Result<Value, String> {
  let url = format!("{}{}", state.sidecar.clone().backend_url().await, path);
  reqwest::Client::new()
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
  api_get(state, "/cases").await
}

#[tauri::command]
async fn create_case(title: String, case_type: String, state: State<'_, AppState>) -> Result<Value, String> {
  api_post(state, "/cases", json!({"title": title, "case_type": case_type})).await
}

#[tauri::command]
async fn get_case(case_id: String, state: State<'_, AppState>) -> Result<Value, String> {
  api_get(state, &format!("/cases/{}", case_id)).await
}

#[tauri::command]
async fn list_evidence(state: State<'_, AppState>) -> Result<Value, String> {
  api_get(state, "/evidence").await
}

#[tauri::command]
async fn import_evidence(source_path: String, state: State<'_, AppState>) -> Result<Value, String> {
  api_post(state, "/evidence/import", json!({"source_path": source_path})).await
}

#[tauri::command]
async fn delete_evidence(name: String, state: State<'_, AppState>) -> Result<Value, String> {
  let url = format!("{}/evidence/{}", state.sidecar.clone().backend_url().await, name);
  reqwest::Client::new()
    .delete(&url)
    .send()
    .await
    .map_err(|e| e.to_string())?
    .json()
    .await
    .map_err(|e| e.to_string())
}

// ------------------------------------------------------------------ //
// Knowledge base
// ------------------------------------------------------------------ //
#[tauri::command]
async fn list_documents(state: State<'_, AppState>) -> Result<Value, String> {
  api_get(state, "/knowledge").await
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
  api_get(state, "/settings").await
}

#[tauri::command]
async fn save_settings(toggles: Value, state: State<'_, AppState>) -> Result<Value, String> {
  api_post(state, "/settings", json!({"toggles": toggles})).await
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
      let log_dir = app_data_dir.join("logs");
      std::fs::create_dir_all(&log_dir)?;
      let log_path = log_dir.join("backend.log");

      let sidecar = SidecarManager::new(8727, log_path);
      let sidecar_clone = sidecar.clone();
      tauri::async_runtime::spawn(async move {
        if let Err(e) = SidecarManager::start(sidecar_clone).await {
          eprintln!("Backend readiness check failed: {}", e);
        }
      });

      app.manage(AppState { sidecar });
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
