//! AI 命令层 —— 庭审控制、状态、校准、转写与聊天。
//!
//! Phase 3：接入真实自动转写流水线（VAD + ASR + 说话人分离）。

use serde_json::{json, Value};
use tauri::State;

use crate::AppState;

#[tauri::command]
pub async fn local_backend_status() -> Result<String, String> {
    Ok("ok".to_string())
}

/// 启动庭审实时辅助：启动自动转写流水线。
#[tauri::command]
pub async fn start_courtroom(
    app: tauri::AppHandle,
    state: State<'_, crate::AppState>,
) -> Result<Value, String> {
    state
        .pipeline
        .start(Some(app))
        .await
        .map_err(|e| e.to_string())?;
    let status = state.pipeline.status().await;
    Ok(json!({
        "courtroom_running": status.running,
        "message": "庭审实时辅助已启动，自动转写流水线运行中",
        "pipeline": status,
    }))
}

/// 停止庭审实时辅助。
#[tauri::command]
pub async fn stop_courtroom(
    app: tauri::AppHandle,
    state: State<'_, crate::AppState>,
) -> Result<Value, String> {
    state
        .pipeline
        .stop(Some(app))
        .await
        .map_err(|e| e.to_string())?;
    Ok(json!({
        "courtroom_running": false,
        "message": "庭审实时辅助已停止"
    }))
}

/// 获取系统状态。
#[tauri::command]
pub async fn get_status(state: State<'_, crate::AppState>) -> Result<Value, String> {
    let pipeline_status = state.pipeline.status().await;
    let recording = state.mic.snapshot().await;
    Ok(json!({
        "message": if pipeline_status.running {
            "庭审实时辅助运行中，自动转写流水线运行中"
        } else {
            "Rust 后端已就绪"
        },
        "status": if pipeline_status.running { "running" } else { "ready" },
        "service_status": {
            "语音识别 ASR": if pipeline_status.asr_ready { "已加载" } else { "未加载" },
            "说话人分离": if pipeline_status.calibrated_speakers.is_empty() {
                "未校准".to_string()
            } else {
                format!("已校准 {} 人", pipeline_status.calibrated_speakers.len())
            },
            "法律策略引擎": "本地规则",
            "语音合成 TTS": "未启用"
        },
        "latency": "",
        "courtroom_running": pipeline_status.running,
        "active_case": null,
        "recording": recording,
        "pipeline": pipeline_status,
    }))
}

/// 获取实时转写记录。
#[tauri::command]
pub async fn get_transcript(state: State<'_, crate::AppState>) -> Result<Value, String> {
    let entries = state.pipeline.get_recent_transcripts(50).await;
    let transcripts: Vec<Value> = entries
        .iter()
        .map(|e| {
            json!({
                "id": e.id,
                "text": e.text,
                "speaker": e.speaker,
                "speaker_confidence": e.speaker_confidence,
                "timestamp": e.timestamp,
                "start_ms": e.start_ms,
                "end_ms": e.end_ms,
            })
        })
        .collect();
    Ok(json!({
        "transcript": transcripts,
        "count": entries.len(),
    }))
}

/// 获取法律建议（基于策略引擎）。
#[tauri::command]
pub async fn get_suggestion(state: State<'_, crate::AppState>) -> Result<Value, String> {
    let entries = state.pipeline.get_recent_transcripts(5).await;
    let last_text = entries
        .last()
        .map(|e| e.text.as_str())
        .unwrap_or("");

    if last_text.is_empty() {
        return Ok(json!({
            "text": "等待庭审发言...",
            "laws": [],
            "suggestion": "等待庭审发言...",
            "references": [],
            "disclaimer": "本系统输出仅供参考，不构成法律意见。"
        }));
    }

    let engine = state.strategy_engine.read().await;
    let suggestion = engine.get_suggestion(last_text, None);

    Ok(json!({
        "text": suggestion["text"],
        "laws": suggestion["laws"],
        "suggestion": suggestion["text"],
        "countermeasure": suggestion["countermeasure"],
        "case_type": suggestion["case_type"],
        "stage": suggestion["stage"],
        "references": [],
        "disclaimer": suggestion["disclaimer"]
    }))
}

/// 声纹校准：录制指定角色的语音样本并存储声纹嵌入。
#[tauri::command]
pub async fn calibrate_role(
    role: String,
    state: State<'_, crate::AppState>,
) -> Result<Value, String> {
    // 先确保麦克风启动
    state.mic.start().await?;

    // 等待 5 秒录制
    tokio::time::sleep(std::time::Duration::from_secs(5)).await;

    // 取录制的音频
    let (samples, sample_rate, _channels) = state.mic.take_segment().await;
    state.mic.stop().await?;

    if samples.is_empty() {
        return Err("未录制到音频，请检查麦克风权限".into());
    }

    let sr = sample_rate.unwrap_or(16000);

    // 提取声纹嵌入并存储
    let profile = state
        .pipeline
        .diarization()
        .calibrate(&role, &samples, sr)
        .await
        .map_err(|e| e.to_string())?;

    Ok(json!({
        "ok": true,
        "role": role,
        "message": format!("声纹校准完成：{}", role),
        "profile": profile,
    }))
}

/// 获取法律聊天历史。
#[tauri::command]
pub async fn chat_messages(state: State<'_, crate::AppState>) -> Result<Value, String> {
    let messages = state.chat_store.load_messages().await.map_err(|e| e.to_string())?;
    Ok(json!(messages))
}

/// 搜索文档。
#[tauri::command]
pub async fn search_documents(query: String, state: State<'_, AppState>) -> Result<Value, String> {
    let docs = state.knowledge_store.list_documents().await?;
    let q = query.to_lowercase();
    let results: Vec<Value> = docs
        .into_iter()
        .filter(|d| {
            d.name.to_lowercase().contains(&q) || d.category.to_lowercase().contains(&q)
        })
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

/// 获取流水线详细状态。
#[tauri::command]
pub async fn get_pipeline_status(state: State<'_, crate::AppState>) -> Result<Value, String> {
    let status = state.pipeline.status().await;
    Ok(json!(status))
}

/// 清空转写记录。
#[tauri::command]
pub async fn clear_transcripts(state: State<'_, crate::AppState>) -> Result<Value, String> {
    state.pipeline.clear_transcripts().await;
    Ok(json!({"ok": true, "message": "转写记录已清空"}))
}

/// 生成策略报告。
#[tauri::command]
pub async fn generate_strategy_report(
    case_type: Option<String>,
    state: State<'_, crate::AppState>,
) -> Result<Value, String> {
    // 获取转写历史
    let transcripts = state.pipeline.get_transcripts().await;
    let transcript_texts: Vec<String> = transcripts.iter().map(|t| t.text.clone()).collect();

    // 获取聊天历史作为补充
    let chat_messages = state.chat_store.load_messages().await.map_err(|e| e.to_string())?;
    let chat_texts: Vec<String> = chat_messages
        .iter()
        .filter(|m| m.sender == "User")
        .map(|m| m.text.clone())
        .collect();

    // 合并转写和聊天记录
    let mut all_texts = transcript_texts;
    all_texts.extend(chat_texts);

    if all_texts.is_empty() {
        return Ok(json!({
            "ok": false,
            "message": "暂无转写或聊天记录，无法生成报告。"
        }));
    }

    let engine = state.strategy_engine.read().await;
    let report = engine.generate_report(&all_texts, case_type.as_deref());

    Ok(json!({
        "ok": true,
        "report": report
    }))
}
