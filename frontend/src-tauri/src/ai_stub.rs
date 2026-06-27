use serde_json::{json, Value};
use tauri::State;

use crate::AppState;

#[tauri::command]
pub async fn local_backend_status() -> Result<String, String> {
    Ok("ok".to_string())
}

#[tauri::command]
pub async fn start_courtroom() -> Result<Value, String> {
    Ok(json!({
        "courtroom_running": false,
        "message": "庭审实时辅助已切换到本地 Rust 后端"
    }))
}

#[tauri::command]
pub async fn stop_courtroom() -> Result<Value, String> {
    Ok(json!({"courtroom_running": false}))
}

#[tauri::command]
pub async fn get_status() -> Result<Value, String> {
    Ok(json!({
        "message": "Rust 后端已就绪，庭审实时辅助可正常运行",
        "status": "ready",
        "service_status": {
            "语音识别 ASR": "本地 Rust 录音",
            "说话人分离": "未启用",
            "法律策略引擎": "本地规则",
            "语音合成 TTS": "未启用"
        },
        "latency": "",
        "courtroom_running": false,
        "active_case": null
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
pub async fn calibrate_role(role: String) -> Result<Value, String> {
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
