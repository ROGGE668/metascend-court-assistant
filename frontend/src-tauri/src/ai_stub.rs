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
        "message": "庭审实时辅助暂未实现（等待 Rust AI 后端 Phase B-D）"
    }))
}

#[tauri::command]
pub async fn stop_courtroom() -> Result<Value, String> {
    Ok(json!({"courtroom_running": false}))
}

#[tauri::command]
pub async fn get_status() -> Result<Value, String> {
    Ok(json!({
        "message": "Rust 后端已就绪，AI 功能暂未启用",
        "status": "ready",
        "service_status": {
            "语音识别 ASR": "未启用",
            "说话人分离": "未启用",
            "法律策略引擎": "未启用",
            "语音合成 TTS": "未启用"
        },
        "latency": "",
        "courtroom_running": false,
        "active_case": null
    }))
}

#[tauri::command]
pub async fn get_transcript() -> Result<Value, String> {
    Ok(json!({"transcript": []}))
}

#[tauri::command]
pub async fn get_suggestion() -> Result<Value, String> {
    Ok(json!({
        "suggestion": "法律策略建议功能暂未启用。",
        "references": [],
        "disclaimer": "本系统输出仅供参考，不构成法律意见。"
    }))
}

#[tauri::command]
pub async fn calibrate_role(role: String) -> Result<Value, String> {
    Ok(json!({
        "ok": false,
        "role": role,
        "message": "声纹校准暂未实现（等待 Rust AI 后端 Phase C）"
    }))
}

#[tauri::command]
pub async fn chat_ask(message: String) -> Result<Value, String> {
    Ok(json!({
        "sender": "AI",
        "text": format!("\"{}\" 的法律分析功能暂未启用。", message),
        "ref": "本系统输出仅供参考，不构成法律意见。"
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
