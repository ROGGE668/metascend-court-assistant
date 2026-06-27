use std::path::PathBuf;
use std::sync::Arc;
use std::time::Instant;

use chrono::Local;
use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use cpal::{SampleFormat, StreamConfig};
use serde_json::{json, Value};
use tokio::sync::RwLock;

pub struct MicRecorder {
    inner: Arc<MicInner>,
}

struct MicInner {
    state: RwLock<MicState>,
}

struct MicState {
    recording: bool,
    device_name: Option<String>,
    sample_rate: Option<u32>,
    channels: Option<u16>,
    started_at: Option<Instant>,
    segment: Vec<f32>,
    errors: Vec<String>,
    output_dir: Option<PathBuf>,
    current_wav: Option<PathBuf>,
    current_writer: Option<hound::WavWriter<std::io::BufWriter<std::fs::File>>>,
}

impl MicRecorder {
    pub fn new() -> Self {
        Self {
            inner: Arc::new(MicInner {
                state: RwLock::new(MicState {
                    recording: false,
                    device_name: None,
                    sample_rate: None,
                    channels: None,
                    started_at: None,
                    segment: Vec::new(),
                    errors: Vec::new(),
                    output_dir: None,
                    current_wav: None,
                    current_writer: None,
                }),
            }),
        }
    }

    pub fn with_output_dir(self, dir: PathBuf) -> Self {
        {
            let mut state = self.inner.state.blocking_write();
            std::fs::create_dir_all(&dir).ok();
            state.output_dir = Some(dir);
        }
        self
    }

    pub async fn start(&self) -> Result<Value, String> {
        {
            let mut state = self.inner.state.write().await;
            if state.recording {
                return Err("麦克风已经在录音".into());
            }
            state.segment.clear();
            state.errors.clear();
            state.current_writer = None;
            state.current_wav = None;
        }

        let host = cpal::default_host();
        let device = host
            .default_input_device()
            .ok_or("未找到可用麦克风，请检查系统隐私权限")?;
        let supported = device
            .default_input_config()
            .map_err(|e| format!("读取麦克风配置失败：{}", e))?;
        let sample_rate: u32 = supported.sample_rate();
        let channels: u16 = supported.channels();
        let config = StreamConfig {
            channels,
            sample_rate,
            buffer_size: cpal::BufferSize::Default,
        };
        let device_name = Some(format!("{}", device));
        let stream = match supported.sample_format() {
            SampleFormat::F32 => {
                let data_state = self.inner.clone();
                let err_state = self.inner.clone();
                device
                .build_input_stream(
                    config.clone(),
                    move |data: &[f32], _: &cpal::InputCallbackInfo| {
                        let inner = data_state.clone();
                        let mut guard = inner.state.blocking_write();
                        guard.segment.extend_from_slice(data);
                        if guard.segment.len() > sample_rate as usize * 120 {
                            let keep = sample_rate as usize * 60;
                            let start = guard.segment.len() - keep;
                            guard.segment = guard.segment[start..].to_vec();
                        }
                        if let Some(writer) = guard.current_writer.as_mut() {
                            for &sample in data {
                                let sample = (sample.clamp(-1.0, 1.0) * 32767.0) as i16;
                                let _ = writer.write_sample(sample);
                            }
                        }
                    },
                    move |err| {
                        let inner = err_state.clone();
                        let mut guard = inner.state.blocking_write();
                        guard.errors.push(format!("麦克风回调异常：{}", err));
                    },
                    None,
                )
                .map_err(|e| format!("启动麦克风失败：{}", e))?
            }
            SampleFormat::I16 => {
                let data_state = self.inner.clone();
                let err_state = self.inner.clone();
                device
                    .build_input_stream::<i16, _, _>(
                        config.clone(),
                        move |data: &[i16], _: &cpal::InputCallbackInfo| {
                            let inner = data_state.clone();
                            let mut guard = inner.state.blocking_write();
                            for &sample in data {
                                let normalized = sample as f32 / 32768.0;
                                guard.segment.push(normalized);
                                if let Some(writer) = guard.current_writer.as_mut() {
                                    let _ = writer.write_sample(sample as i16);
                                }
                            }
                            if guard.segment.len() > sample_rate as usize * 120 {
                                let keep = sample_rate as usize * 60;
                                let start = guard.segment.len() - keep;
                                guard.segment = guard.segment[start..].to_vec();
                            }
                        },
                        move |err| {
                            let inner = err_state.clone();
                            let mut guard = inner.state.blocking_write();
                            guard.errors.push(format!("麦克风回调异常：{}", err));
                        },
                        None,
                    )
                    .map_err(|e| format!("启动麦克风失败：{}", e))?
            }
            SampleFormat::U16 => {
                let data_state = self.inner.clone();
                let err_state = self.inner.clone();
                device
                    .build_input_stream::<u16, _, _>(
                        config.clone(),
                        move |data: &[u16], _: &cpal::InputCallbackInfo| {
                            let inner = data_state.clone();
                            let mut guard = inner.state.blocking_write();
                            for &sample in data {
                                let normalized = (sample as f32 - 32768.0) / 32768.0;
                                guard.segment.push(normalized);
                                if let Some(writer) = guard.current_writer.as_mut() {
                                    let _ = writer.write_sample(sample as i16);
                                }
                            }
                            if guard.segment.len() > sample_rate as usize * 120 {
                                let keep = sample_rate as usize * 60;
                                let start = guard.segment.len() - keep;
                                guard.segment = guard.segment[start..].to_vec();
                            }
                        },
                        move |err| {
                            let inner = err_state.clone();
                            let mut guard = inner.state.blocking_write();
                            guard.errors.push(format!("麦克风回调异常：{}", err));
                        },
                        None,
                    )
                    .map_err(|e| format!("启动麦克风失败：{}", e))?
            }
            other => return Err(format!("不支持的麦克风采样格式：{:?}", other)),
        };

        stream
            .play()
            .map_err(|e| format!("无法开始录音：{}", e))?;

        {
            let mut state = self.inner.state.write().await;
            state.recording = true;
            state.device_name = device_name;
            state.sample_rate = Some(sample_rate);
            state.channels = Some(channels);
            state.started_at = Some(Instant::now());
            if let Some(dir) = state.output_dir.clone() {
                let file_name = format!("庭审录音-{}.wav", Local::now().format("%Y%m%d-%H%M%S"));
                let wav_path = dir.join(file_name);
                let spec = hound::WavSpec {
                    channels,
                    sample_rate,
                    bits_per_sample: 16,
                    sample_format: hound::SampleFormat::Int,
                };
                match hound::WavWriter::create(&wav_path, spec) {
                    Ok(writer) => {
                        state.current_wav = Some(wav_path);
                        state.current_writer = Some(writer);
                    }
                    Err(e) => {
                        state.errors.push(format!("创建录音文件失败：{}", e));
                    }
                }
            }
        }

        let writer_ref = self.inner.clone();
        std::thread::spawn(move || {
            let _stream = stream;
            loop {
                std::thread::sleep(std::time::Duration::from_millis(200));
                let guard = writer_ref.state.blocking_read();
                if !guard.recording {
                    break;
                }
            }
        });

        let snapshot = self.snapshot().await;
        Ok(json!({
            "ok": true,
            "message": "麦克风已开始录音",
            "recording": snapshot
        }))
    }

    pub async fn stop(&self) -> Result<Value, String> {
        let mut state = self.inner.state.write().await;
        if !state.recording {
            return Err("当前未在录音".into());
        }
        state.recording = false;
        state.started_at = None;
        Ok(json!({"ok": true, "message": "麦克风已停止"}))
    }

    pub async fn append_samples(&self, samples: &[f32]) {
        let mut state = self.inner.state.write().await;
        if let Some(writer) = state.current_writer.as_mut() {
            for &sample in samples {
                let sample = (sample.clamp(-1.0, 1.0) * 32767.0) as i16;
                let _ = writer.write_sample(sample);
            }
        }
    }

    pub async fn snapshot(&self) -> Value {
        let state = self.inner.state.read().await;
        let duration_ms = state
            .started_at
            .map(|t| t.elapsed().as_millis() as u64)
            .unwrap_or(0);
        let rms = compute_rms(&state.segment);
        let recent_rms = compute_recent_rms(&state.segment, 3200);
        json!({
            "recording": state.recording,
            "device_name": state.device_name,
            "sample_rate": state.sample_rate,
            "channels": state.channels,
            "duration_ms": duration_ms,
            "buffer_samples": state.segment.len(),
            "rms": rms,
            "recent_rms": recent_rms,
            "latest_error": state.errors.last(),
            "recording_path": state.current_wav.as_ref().map(|p| p.to_string_lossy().to_string()),
        })
    }

    pub async fn take_segment(&self) -> (Vec<f32>, Option<u32>, Option<u16>) {
        let mut state = self.inner.state.write().await;
        let samples = std::mem::take(&mut state.segment);
        (samples, state.sample_rate, state.channels)
    }

    pub async fn last_recording_path(&self) -> Option<PathBuf> {
        let state = self.inner.state.read().await;
        state.current_wav.clone()
    }
}

fn compute_rms(samples: &[f32]) -> f32 {
    if samples.is_empty() {
        return 0.0;
    }
    let mut sum = 0.0f32;
    for &x in samples {
        sum += x * x;
    }
    (sum / samples.len() as f32).sqrt()
}

fn compute_recent_rms(samples: &[f32], window: usize) -> f32 {
    if samples.is_empty() {
        return 0.0;
    }
    let start = samples.len().saturating_sub(window);
    compute_rms(&samples[start..])
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn compute_rms_handles_empty_input() {
        assert!((compute_rms(&[]) - 0.0).abs() < 1e-6);
    }

    #[test]
    fn compute_recent_rms_handles_short_buffer() {
        let samples = vec![0.5, -0.5, 0.25];
        let rms = compute_recent_rms(&samples, 3200);
        assert!(rms > 0.0);
    }
}
