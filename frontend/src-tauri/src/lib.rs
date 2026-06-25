use reqwest;
use serde_json::{json, Value};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use tauri::Manager;
use std::sync::Mutex;
use tauri::State;

pub struct AppState {
  pub backend_url: String,
  pub backend_child: Mutex<Option<Child>>,
}

impl Default for AppState {
  fn default() -> Self {
    Self {
      backend_url: String::from("http://127.0.0.1:8727"),
      backend_child: Mutex::new(None),
    }
  }
}

fn project_root() -> PathBuf {
  PathBuf::from(env!("CARGO_MANIFEST_DIR"))
    .parent()
    .and_then(|p| p.parent())
    .map(|p| p.to_path_buf())
    .unwrap_or_else(|| std::env::current_dir().unwrap_or_default())
}

#[tauri::command]
fn open_url(url: String) -> Result<(), String> {
  open::that(url).map_err(|e| e.to_string())
}

async fn api_get(state: State<'_, AppState>, path: &str) -> Result<Value, String> {
  let url = format!("{}{}", state.backend_url, path);
  reqwest::get(&url)
    .await
    .map_err(|e| e.to_string())?
    .json()
    .await
    .map_err(|e| e.to_string())
}

async fn api_post(state: State<'_, AppState>, path: &str, body: Value) -> Result<Value, String> {
  let url = format!("{}{}", state.backend_url, path);
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
  let url = format!("{}/evidence/{}", state.backend_url, name);
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
fn wait_for_backend(url: &str) -> Result<(), String> {
  for _ in 0..40 {
    if let Ok(resp) = reqwest::blocking::get(format!("{}/health", url)) {
      if resp.status().is_success() {
        return Ok(());
      }
    }
    std::thread::sleep(std::time::Duration::from_millis(250));
  }
  Err("Python backend did not become ready".into())
}

fn spawn_backend() -> Result<Child, String> {
  let root = project_root();
  Command::new("uv")
    .args(["run", "metascend-api"])
    .current_dir(&root)
    .stdout(Stdio::piped())
    .stderr(Stdio::piped())
    .spawn()
    .map_err(|e| format!("Failed to spawn backend: {}", e))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  tauri::Builder::default()
    .plugin(tauri_plugin_shell::init())
    .plugin(tauri_plugin_dialog::init())
    .manage(AppState::default())
    .setup(|app| {
      let state = app.state::<AppState>();
      let child = spawn_backend()?;
      *state.backend_child.lock().unwrap() = Some(child);
      let url = state.backend_url.clone();
      std::thread::spawn(move || {
        if let Err(e) = wait_for_backend(&url) {
          eprintln!("Backend readiness check failed: {}", e);
        }
      });
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
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}
