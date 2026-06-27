use serde_json::{json, Value};
use tauri::State;

use crate::AppState;

#[tauri::command]
pub async fn local_backend_status() -> Result<String, String> {
    Ok("ok".to_string())
}

#[tauri::command]
pub async fn start_courtroom(state: State<'_, crate::AppState>) -> Result<Value, String> {
    let recording = state.mic.start().await?;
    Ok(json!({
        "courtroom_running": true,
        "message": "庭审实时辅助已启动，本地麦克风录音已开启",
        "recording": recording
    }))
}

#[tauri::command]
pub async fn stop_courtroom(state: State<'_, crate::AppState>) -> Result<Value, String> {
    let _ = state.mic.stop().await;
    Ok(json!({"courtroom_running": false, "message": "庭审实时辅助已暂停"}))
}

#[tauri::command]
pub async fn get_status(state: State<'_, crate::AppState>) -> Result<Value, String> {
    let recording = state.mic.snapshot().await;
    let recording_flag = recording.get("recording").and_then(|v| v.as_bool()).unwrap_or(false);
    Ok(json!({
        "message": if recording_flag { "庭审实时辅助运行中，麦克风录音已开启" } else { "Rust 后端已就绪，庭审实时辅助可正常运行" },
        "status": if recording_flag { "running" } else { "ready" },
        "service_status": {
            "语音识别 ASR": if recording_flag { "录音中" } else { "本地 Rust 录音" },
            "说话人分离": "未启用",
            "法律策略引擎": "本地规则",
            "语音合成 TTS": "未启用"
        },
        "latency": "",
        "courtroom_running": recording_flag,
        "active_case": null,
        "recording": recording
    }))
}

#[tauri::command]
pub async fn get_transcript() -> Result<Value, String> {
    Ok(json!({"transcript": "当前由 Rust 本地录音后端提供转写内容，AI 推理尚未接入。"}))
}

#[tauri::command]
pub async fn get_suggestion() -> Result<Value, String> {
    Ok(json!({
        "suggestion": "当前为本地 Rust 规则提示，AI 推理尚未接入。",
        "references": [],
        "disclaimer": "本系统输出仅供参考，不构成法律意见。"
    }))
}

#[tauri::command]
pub async fn calibrate_role(role: String, state: State<'_, crate::AppState>) -> Result<Value, String> {
    state.mic.start().await?;
    tokio::time::sleep(std::time::Duration::from_secs(5)).await;
    state.mic.stop().await?;
    Ok(json!({
        "ok": true,
        "role": role,
        "message": format!("声纹校准已录制完成：{}", role)
    }))
}


#[tauri::command]
pub async fn chat_messages() -> Result<Value, String> {
    Ok(json!([]))
}

#[tauri::command]
pub async fn search_documents(query: String, state: State<'_, AppState>) -> Result<Value, String> {
    let docs = state.knowledge_store.list_documents().await?;
    let q = query.to_lowercase();
    let results: Vec<Value> = docs
        .into_iter()
        .filter(|d| d.name.to_lowercase().contains(&q) || d.category.to_lowercase().contains(&q))
        .map(|d| {
            json!({
                "id": d.id,
                "name": d.name,
                "category": d.category,
                "score": 1.0,
                "snippet": ""
            })
        })
        .collect();
    Ok(json!({"query": query, "results": results}))
}
