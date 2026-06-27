mod ai_stub;
mod cases;
mod evidence;
mod knowledge;
mod store;

use serde_json::{json, Value};
use std::sync::Arc;
use tauri::{Manager, State};

use cases::CaseStore;
use evidence::EvidenceStore;
use knowledge::KnowledgeStore;
use store::SettingsStore;

pub struct AppState {
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
        "engine": "Rust local filesystem",
        "embedding_model": "未启用"
    }))
}

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

fn project_root() -> std::path::PathBuf {
    if let Ok(manifest_dir) = std::env::var("CARGO_MANIFEST_DIR") {
        let path = std::path::PathBuf::from(manifest_dir);
        if let Some(root) = path.parent().and_then(|p| p.parent()) {
            return root.to_path_buf();
        }
    }
    std::env::current_dir().unwrap_or_default()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            let app_data_dir = app.path().app_data_dir()?;
            let data_dir = app_data_dir.clone();

            let settings_store = Arc::new(tauri::async_runtime::block_on(SettingsStore::new(data_dir.clone())));
            let case_store = Arc::new(tauri::async_runtime::block_on(CaseStore::new(data_dir.clone())));
            let evidence_store = Arc::new(tauri::async_runtime::block_on(EvidenceStore::new(data_dir.clone())));

            let knowledge_base_dir = if cfg!(debug_assertions) {
                project_root().join("data").join("knowledge_base")
            } else {
                data_dir.join("knowledge_base")
            };
            let knowledge_store = Arc::new(tauri::async_runtime::block_on(KnowledgeStore::new(knowledge_base_dir)));

            app.manage(AppState {
                settings_store,
                case_store,
                evidence_store,
                knowledge_store,
                data_dir,
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            open_url,
            ai_stub::local_backend_status,
            ai_stub::start_courtroom,
            ai_stub::stop_courtroom,
            ai_stub::get_status,
            ai_stub::get_transcript,
            ai_stub::get_suggestion,
            ai_stub::calibrate_role,
            list_cases,
            create_case,
            get_case,
            list_evidence,
            import_evidence,
            delete_evidence,
            list_documents,
            ai_stub::search_documents,
            import_knowledge_document,
            get_knowledge_document,
            ai_stub::chat_ask,
            ai_stub::chat_messages,
            get_settings,
            save_settings
        ])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|_app_handle, _event| {});
}
