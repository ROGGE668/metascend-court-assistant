mod cases;
mod diarization;
mod evidence;
mod knowledge;
mod llm;
mod pipeline;
mod store;
mod ai_stub;
mod asr;
mod audio;
mod vad;

use serde_json::Value;
use std::sync::Arc;
use tauri::{Manager, State};

use cases::CaseStore;
use diarization::DiarizationEngine;
use evidence::EvidenceStore;
use knowledge::KnowledgeStore;
use pipeline::CourtroomPipeline;
use store::SettingsStore;

pub struct AppState {
    pub settings_store: Arc<SettingsStore>,
    pub case_store: Arc<CaseStore>,
    pub evidence_store: Arc<EvidenceStore>,
    pub knowledge_store: Arc<KnowledgeStore>,
    pub llm: Arc<std::sync::Mutex<Option<llm::LlmEngine>>>,
    pub mic: Arc<audio::MicRecorder>,
    pub asr: Arc<asr::AsrEngine>,
    pub pipeline: Arc<CourtroomPipeline>,
    pub data_dir: std::path::PathBuf,
}

#[tauri::command]
fn open_url(url: String) -> Result<(), String> {
    open::that(url).map_err(|e| e.to_string())
}

#[tauri::command]
async fn list_cases(state: State<'_, AppState>) -> Result<Value, String> {
    Ok(Value::Array(state.case_store.list_cases().await?))
}

#[tauri::command]
async fn create_case(
    title: String,
    case_type: String,
    state: State<'_, AppState>,
) -> Result<Value, String> {
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
    Ok(serde_json::json!({"success": true}))
}

#[tauri::command]
async fn ocr_evidence(name: String, state: State<'_, AppState>) -> Result<Value, String> {
    let path = state.evidence_store.file_path(&name);
    if !path.exists() {
        return Err("evidence not found".to_string());
    }
    Ok(serde_json::json!({
        "name": name,
        "path": path.to_string_lossy(),
        "text": "",
        "note": "当前 Rust 后端仅返回占位结果，OCR 尚未接入。"
    }))
}

#[tauri::command]
async fn list_documents(state: State<'_, AppState>) -> Result<Value, String> {
    let docs = state.knowledge_store.list_documents().await?;
    Ok(serde_json::json!({
        "documents": docs,
        "total": docs.len(),
        "engine": "Rust local filesystem",
        "embedding_model": "未启用"
    }))
}

#[tauri::command]
async fn import_knowledge_document(
    source_path: String,
    category: String,
    state: State<'_, AppState>,
) -> Result<Value, String> {
    let doc = state
        .knowledge_store
        .import_file(source_path, category)
        .await?;
    Ok(serde_json::json!({
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

#[tauri::command]
async fn start_recording(state: State<'_, AppState>) -> Result<Value, String> {
    state.mic.start().await
}

#[tauri::command]
async fn stop_recording(state: State<'_, AppState>) -> Result<Value, String> {
    state.mic.stop().await
}

#[tauri::command]
async fn get_recording(state: State<'_, AppState>) -> Result<Value, String> {
    Ok(state.mic.snapshot().await)
}

#[tauri::command]
async fn get_recording_files(state: State<'_, AppState>) -> Result<Value, String> {
    let dir = state.data_dir.join("recordings");
    let mut files = Vec::new();
    if dir.exists() {
        for entry in std::fs::read_dir(&dir).map_err(|e| e.to_string())? {
            let entry = entry.map_err(|e| e.to_string())?;
            let path = entry.path();
            if path.extension().and_then(|s| s.to_str()) == Some("wav") {
                let metadata = std::fs::metadata(&path).map_err(|e| e.to_string())?;
                files.push(serde_json::json!({
                    "name": path.file_name().map(|s| s.to_string_lossy().to_string()),
                    "path": path.to_string_lossy(),
                    "size": metadata.len(),
                }));
            }
        }
    }
    files.sort_by(|a, b| b["name"].as_str().cmp(&a["name"].as_str()));
    Ok(serde_json::json!({"dir": dir.to_string_lossy(), "files": files}))
}

#[tauri::command]
async fn load_asr_model(model_path: String, state: State<'_, AppState>) -> Result<Value, String> {
    state
        .asr
        .ensure_ready(std::path::PathBuf::from(model_path))
        .await?;
    Ok(state.asr.snapshot().await)
}

#[tauri::command]
async fn get_asr_status(state: State<'_, AppState>) -> Result<Value, String> {
    Ok(state.asr.snapshot().await)
}

#[tauri::command]
async fn transcribe_recording(
    language: Option<String>,
    state: State<'_, AppState>,
) -> Result<Value, String> {
    let (samples, sample_rate, _channels) = state.mic.take_segment().await;
    if samples.is_empty() {
        return Err("当前录音缓冲为空，请先开始庭审并录入语音".into());
    }
    let sample_rate = sample_rate.unwrap_or(16000);
    let result = state
        .asr
        .transcribe(&samples, sample_rate, language.as_deref())
        .await?;
    Ok(result)
}

#[tauri::command]
async fn chat_ask(message: String, state: State<'_, AppState>) -> Result<Value, String> {
    let settings = state.settings_store.get().await;
    let model_id = settings["rust_llm_model"]
        .as_str()
        .map(|s| s.to_string())
        .unwrap_or_else(|| llm::default_model().to_string());
    let cache_dir = state.data_dir.join("llm_cache");
    let llm = state.llm.clone();
    let reply = tokio::task::spawn_blocking(move || -> Result<String, String> {
        let mut guard = llm.lock().map_err(|e| e.to_string())?;
        if guard.is_none() {
            let engine = llm::LlmEngine::load(&model_id, cache_dir)?;
            *guard = Some(engine);
        }
        guard.as_ref().unwrap().chat(&message)
    })
    .await
    .map_err(|e| format!("LLM 任务异常：{}", e))?
    .map_err(|e| format!("LLM 加载或推理失败：{}", e))?;
    Ok(serde_json::json!({
        "sender": "AI",
        "text": reply,
        "ref": "本系统输出仅供参考，不构成法律意见。",
    }))
}

#[tauri::command]
async fn get_settings(state: State<'_, AppState>) -> Result<Value, String> {
    Ok(state.settings_store.get().await)
}

#[tauri::command]
async fn save_settings(payload: Value, state: State<'_, AppState>) -> Result<Value, String> {
    Ok(state.settings_store.update(payload).await)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            let app_data_dir = app.path().app_data_dir()?;
            let data_dir = app_data_dir.clone();

            let settings_store = Arc::new(tauri::async_runtime::block_on(
                SettingsStore::new(data_dir.clone()),
            ));
            let case_store = Arc::new(tauri::async_runtime::block_on(
                CaseStore::new(data_dir.clone()),
            ));
            let evidence_store = Arc::new(tauri::async_runtime::block_on(
                EvidenceStore::new(data_dir.clone()),
            ));

            let knowledge_base_dir = if cfg!(debug_assertions) {
                let manifest_dir = std::env::var("CARGO_MANIFEST_DIR").unwrap_or_default();
                let root = std::path::PathBuf::from(manifest_dir)
                    .parent()
                    .and_then(|p| p.parent())
                    .map(|p| p.to_path_buf())
                    .unwrap_or_default();
                root.join("data").join("knowledge_base")
            } else {
                data_dir.join("knowledge_base")
            };
            let knowledge_store = Arc::new(tauri::async_runtime::block_on(
                KnowledgeStore::new(knowledge_base_dir),
            ));
            let llm = Arc::new(std::sync::Mutex::new(None));
            let mic = Arc::new(
                audio::MicRecorder::new().with_output_dir(data_dir.join("recordings")),
            );
            let asr = Arc::new(asr::AsrEngine::new());
            let diarization = Arc::new(DiarizationEngine::new());
            let pipeline = CourtroomPipeline::new(mic.clone(), asr.clone(), diarization);

            app.manage(AppState {
                settings_store,
                case_store,
                evidence_store,
                knowledge_store,
                llm,
                mic,
                asr,
                pipeline,
                data_dir,
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            open_url,
            load_asr_model,
            get_asr_status,
            transcribe_recording,
            start_recording,
            stop_recording,
            get_recording,
            get_recording_files,
            ai_stub::local_backend_status,
            ai_stub::start_courtroom,
            ai_stub::stop_courtroom,
            ai_stub::get_status,
            ai_stub::get_transcript,
            ai_stub::get_suggestion,
            ai_stub::calibrate_role,
            ai_stub::get_pipeline_status,
            ai_stub::clear_transcripts,
            list_cases,
            create_case,
            get_case,
            list_evidence,
            import_evidence,
            delete_evidence,
            ocr_evidence,
            list_documents,
            import_knowledge_document,
            get_knowledge_document,
            ai_stub::search_documents,
            chat_ask,
            ai_stub::chat_messages,
            get_settings,
            save_settings
        ])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            if let tauri::RunEvent::ExitRequested { api, .. } = event {
                let app_handle = app_handle.clone();
                tauri::async_runtime::spawn(async move {
                    app_handle.exit(0);
                });
                api.prevent_exit();
            }
        });
}
