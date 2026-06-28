//! 自动庭审转写流水线。
//!
//! 数据流：麦克风 → VAD → ASR → 说话人分离 → 前端事件
//!
//! 设计原则：
//! - 后台轮询麦克风缓冲区，通过 VAD 检测语音段。
//! - 检测到语音段后自动触发 ASR 转写。
//! - 转写结果附带说话人标签（如已校准）。
//! - 通过 Tauri Event 实时推送到前端。

use crate::asr::AsrEngine;
use crate::audio::MicRecorder;
use crate::diarization::DiarizationEngine;
use crate::vad::{VadConfig, VadEngine};
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::sync::Arc;
use tauri::{AppHandle, Emitter};
use tokio::sync::RwLock;
use tokio::time::{sleep, Duration};

/// 一条转写记录。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TranscriptEntry {
    pub id: u64,
    pub text: String,
    pub speaker: String,
    pub speaker_confidence: f32,
    pub timestamp: String,
    pub start_ms: u64,
    pub end_ms: u64,
}

/// 流水线状态。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PipelineStatus {
    pub running: bool,
    pub vad_active: bool,
    pub transcript_count: usize,
    pub calibrated_speakers: Vec<String>,
    pub asr_ready: bool,
    pub uptime_ms: u64,
}

/// 自动庭审转写流水线。
pub struct CourtroomPipeline {
    mic: Arc<MicRecorder>,
    asr: Arc<AsrEngine>,
    diarization: Arc<DiarizationEngine>,
    transcripts: RwLock<Vec<TranscriptEntry>>,
    running: RwLock<bool>,
    counter: std::sync::atomic::AtomicU64,
    started_at: RwLock<Option<std::time::Instant>>,
}

impl CourtroomPipeline {
    pub fn new(
        mic: Arc<MicRecorder>,
        asr: Arc<AsrEngine>,
        diarization: Arc<DiarizationEngine>,
    ) -> Arc<Self> {
        Arc::new(Self {
            mic,
            asr,
            diarization,
            transcripts: RwLock::new(Vec::new()),
            running: RwLock::new(false),
            counter: std::sync::atomic::AtomicU64::new(1),
            started_at: RwLock::new(None),
        })
    }

    /// 启动自动流水线。
    pub async fn start(self: &Arc<Self>, app: Option<AppHandle>) -> Result<(), String> {
        {
            let mut running = self.running.write().await;
            if *running {
                return Err("流水线已在运行".into());
            }
            *running = true;
        }

        {
            let mut started = self.started_at.write().await;
            *started = Some(std::time::Instant::now());
        }

        // 启动麦克风
        self.mic.start().await?;

        // 通知前端
        if let Some(ref handle) = app {
            let _ = handle.emit("pipeline:started", json!({"ok": true}));
        }

        // 启动后台处理循环
        let pipeline = Arc::clone(self);
        let app_clone = app.clone();
        tokio::spawn(async move {
            pipeline.processing_loop(app_clone).await;
        });

        Ok(())
    }

    /// 停止流水线。
    pub async fn stop(self: &Arc<Self>, app: Option<AppHandle>) -> Result<(), String> {
        {
            let mut running = self.running.write().await;
            if !*running {
                return Err("流水线未在运行".into());
            }
            *running = false;
        }

        self.mic.flush_writer().await;
        self.mic.stop().await?;

        if let Some(ref handle) = app {
            let _ = handle.emit("pipeline:stopped", json!({"ok": true}));
        }

        Ok(())
    }

    /// 后台处理循环：从麦克风缓冲区取音频 → VAD → ASR → 事件推送。
    async fn processing_loop(self: Arc<Self>, app: Option<AppHandle>) {
        let mut vad = VadEngine::new(VadConfig::default());
        let poll_interval = Duration::from_millis(200);

        loop {
            {
                let running = self.running.read().await;
                if !*running {
                    break;
                }
            }

            // 从麦克风取最新采样
            let (samples, sample_rate, _channels) = self.mic.take_segment().await;
            let sr = sample_rate.unwrap_or(16000);

            if !samples.is_empty() {
                // VAD 检测
                let segments = vad.feed_samples(&samples);

                for seg in segments {
                    if seg.samples.is_empty() {
                        continue;
                    }

                    // ASR 转写
                    let asr_result = self.asr.transcribe(&seg.samples, sr, Some("zh")).await;
                    let text = match asr_result {
                        Ok(val) => {
                            val.get("text")
                                .and_then(|v| v.as_str())
                                .unwrap_or("")
                                .to_string()
                        }
                        Err(e) => {
                            eprintln!("ASR 转写失败: {}", e);
                            continue;
                        }
                    };

                    if text.trim().is_empty() {
                        continue;
                    }

                    // 说话人识别
                    let speaker_match = self.diarization.identify(&seg.samples, sr).await;

                    let id = self
                        .counter
                        .fetch_add(1, std::sync::atomic::Ordering::SeqCst);
                    let now_ms = self
                        .started_at
                        .read()
                        .await
                        .map(|t| t.elapsed().as_millis() as u64)
                        .unwrap_or(0);

                    let entry = TranscriptEntry {
                        id,
                        text: text.clone(),
                        speaker: speaker_match.role.clone(),
                        speaker_confidence: speaker_match.confidence,
                        timestamp: chrono::Local::now().format("%H:%M:%S").to_string(),
                        start_ms: now_ms,
                        end_ms: now_ms + (seg.samples.len() as u64 * 1000 / sr as u64),
                    };

                    // 存储
                    {
                        let mut transcripts = self.transcripts.write().await;
                        transcripts.push(entry.clone());
                        // 保留最近 1000 条
                        if transcripts.len() > 1000 {
                            transcripts.remove(0);
                        }
                    }

                    // 推送事件到前端
                    if let Some(ref handle) = app {
                        let _ = handle.emit(
                            "transcript:new",
                            json!({
                                "id": entry.id,
                                "text": entry.text,
                                "speaker": entry.speaker,
                                "speaker_confidence": entry.speaker_confidence,
                                "timestamp": entry.timestamp,
                                "start_ms": entry.start_ms,
                                "end_ms": entry.end_ms,
                            }),
                        );
                    }
                }
            }

            sleep(poll_interval).await;
        }
    }

    /// 获取所有转写记录。
    pub async fn get_transcripts(&self) -> Vec<TranscriptEntry> {
        let transcripts = self.transcripts.read().await;
        transcripts.clone()
    }

    /// 获取最新 N 条转写记录。
    pub async fn get_recent_transcripts(&self, n: usize) -> Vec<TranscriptEntry> {
        let transcripts = self.transcripts.read().await;
        let len = transcripts.len();
        if len <= n {
            transcripts.clone()
        } else {
            transcripts[len - n..].to_vec()
        }
    }

    /// 流水线状态快照。
    pub async fn status(&self) -> PipelineStatus {
        let running = *self.running.read().await;
        let transcripts = self.transcripts.read().await;
        let calibrated = self.diarization.calibrated_roles().await;
        let asr_snapshot = self.asr.snapshot().await;
        let asr_ready = asr_snapshot
            .get("ready")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        let uptime_ms = self
            .started_at
            .read()
            .await
            .map(|t| t.elapsed().as_millis() as u64)
            .unwrap_or(0);

        PipelineStatus {
            running,
            vad_active: running, // VAD is active when pipeline is running
            transcript_count: transcripts.len(),
            calibrated_speakers: calibrated,
            asr_ready,
            uptime_ms,
        }
    }

    /// 清空转写记录。
    pub async fn clear_transcripts(&self) {
        let mut transcripts = self.transcripts.write().await;
        transcripts.clear();
    }

    /// 获取 DiarizationEngine 引用（用于校准）。
    pub fn diarization(&self) -> &DiarizationEngine {
        &self.diarization
    }

    /// 获取 MicRecorder 引用。
    pub fn mic(&self) -> &MicRecorder {
        &self.mic
    }
}
