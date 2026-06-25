use reqwest::blocking::get;
use serde_json::json;
use tauri::{Manager, State};

#[derive(Default)]
pub struct AppState {
  pub backend_url: String,
}

#[tauri::command]
fn open_url(url: String) -> Result<(), String> {
  open::that(url).map_err(|e| e.to_string())
}

#[tauri::command]
fn fetch_json(url: String) -> Result<serde_json::Value, String> {
  get(&url).map_err(|e| e.to_string())?.json().map_err(|e| e.to_string())
}

#[tauri::command]
fn local_backend_status(state: State<'_, AppState>) -> String {
  format!("backend={}", state.backend_url)
}

#[tauri::command]
fn start_listening(state: State<'_, AppState>) -> Result<String, String> {
  let payload = json!({"status":"listening","backend": state.backend_url});
  Ok(payload.to_string())
}

#[tauri::command]
fn stop_listening() -> Result<String, String> {
  Ok(json!({"status":"idle"}).to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  tauri::Builder::default()
    .plugin(tauri_plugin_shell::init())
    .manage(AppState::default())
    .invoke_handler(tauri::generate_handler![open_url, fetch_json, local_backend_status, start_listening, stop_listening])
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}
