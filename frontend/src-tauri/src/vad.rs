//! Voice Activity Detection (VAD) — 能量阈值 + 静音计时。
//!
//! 将音频帧分为 speech / silence，用于驱动自动转写流水线。
//! 不引入外部 VAD crate，使用帧 RMS 能量与自适应阈值。

use serde::{Deserialize, Serialize};

/// 一帧的检测结果。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VadFrame {
    pub is_speech: bool,
    pub rms: f32,
}

/// VAD 状态机配置。
#[derive(Debug, Clone)]
pub struct VadConfig {
    /// 每帧采样数（16 kHz × 30 ms = 480）。
    pub frame_size: usize,
    /// 判定为语音的 RMS 阈值。
    pub energy_threshold: f32,
    /// 语音段开始后，连续多少帧静音才算结束。
    pub silence_frames_to_end: usize,
    /// 语音段最少持续帧数，低于此丢弃（防误触发）。
    pub min_speech_frames: usize,
}

impl Default for VadConfig {
    fn default() -> Self {
        Self {
            frame_size: 480,
            energy_threshold: 0.015,
            silence_frames_to_end: 20,
            min_speech_frames: 5,
        }
    }
}

/// 语音段：起止帧索引与对应采样。
#[derive(Debug, Clone)]
pub struct SpeechSegment {
    pub start_frame: usize,
    pub end_frame: usize,
    pub samples: Vec<f32>,
}

/// VAD 引擎，持续接收采样并输出语音段。
pub struct VadEngine {
    config: VadConfig,
    /// 滚动帧缓冲。
    buffer: Vec<f32>,
    /// 当前是否在语音段内。
    in_speech: bool,
    /// 当前语音段开始的帧号。
    speech_start: usize,
    /// 当前语音段内连续静音帧计数。
    silence_count: usize,
    /// 当前语音段内的帧计数。
    speech_frame_count: usize,
    /// 已处理的总帧数。
    total_frames: usize,
    /// 当前语音段的采样积累。
    speech_samples: Vec<f32>,
    /// 已完成的语音段队列。
    segments: Vec<SpeechSegment>,
    /// 历史能量用于自适应阈值。
    energy_history: Vec<f32>,
}

impl VadEngine {
    pub fn new(config: VadConfig) -> Self {
        Self {
            config,
            buffer: Vec::new(),
            in_speech: false,
            speech_start: 0,
            silence_count: 0,
            speech_frame_count: 0,
            total_frames: 0,
            speech_samples: Vec::new(),
            segments: Vec::new(),
            energy_history: Vec::new(),
        }
    }

    /// 推送新采样（单声道 f32），返回本次触发完成的语音段。
    pub fn feed_samples(&mut self, samples: &[f32]) -> Vec<SpeechSegment> {
        self.buffer.extend_from_slice(samples);
        let frame_size = self.config.frame_size;

        while self.buffer.len() >= frame_size {
            let frame: Vec<f32> = self.buffer[..frame_size].to_vec();
            self.buffer.drain(..frame_size);

            let rms = compute_rms(&frame);
            self.energy_history.push(rms);
            if self.energy_history.len() > 200 {
                self.energy_history.remove(0);
            }

            let threshold = self.adaptive_threshold();
            let is_speech = rms > threshold;

            if is_speech {
                if !self.in_speech {
                    self.in_speech = true;
                    self.speech_start = self.total_frames;
                    self.speech_frame_count = 0;
                    self.speech_samples.clear();
                }
                self.silence_count = 0;
                self.speech_frame_count += 1;
                self.speech_samples.extend_from_slice(&frame);
            } else if self.in_speech {
                self.silence_count += 1;
                self.speech_samples.extend_from_slice(&frame);

                if self.silence_count >= self.config.silence_frames_to_end {
                    if self.speech_frame_count >= self.config.min_speech_frames {
                        let seg = SpeechSegment {
                            start_frame: self.speech_start,
                            end_frame: self.total_frames,
                            samples: std::mem::take(&mut self.speech_samples),
                        };
                        self.segments.push(seg);
                    }
                    self.in_speech = false;
                    self.silence_count = 0;
                    self.speech_frame_count = 0;
                }
            }

            self.total_frames += 1;
        }

        std::mem::take(&mut self.segments)
    }

    /// 当前是否有语音活动。
    pub fn is_speech_active(&self) -> bool {
        self.in_speech
    }

    /// 取出当前正在积累的语音段（不结束），用于实时预览。
    pub fn current_speech_samples(&self) -> &[f32] {
        &self.speech_samples
    }

    /// 重置状态。
    pub fn reset(&mut self) {
        self.buffer.clear();
        self.in_speech = false;
        self.speech_start = 0;
        self.silence_count = 0;
        self.speech_frame_count = 0;
        self.total_frames = 0;
        self.speech_samples.clear();
        self.segments.clear();
        self.energy_history.clear();
    }

    fn adaptive_threshold(&self) -> f32 {
        if self.energy_history.len() < 10 {
            return self.config.energy_threshold;
        }
        let mean: f32 =
            self.energy_history.iter().sum::<f32>() / self.energy_history.len() as f32;
        // 阈值 = max(配置阈值, 历史均值 × 2.0)
        f32::max(self.config.energy_threshold, mean * 2.0)
    }
}

fn compute_rms(samples: &[f32]) -> f32 {
    if samples.is_empty() {
        return 0.0;
    }
    let sum: f32 = samples.iter().map(|x| x * x).sum();
    (sum / samples.len() as f32).sqrt()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn vad_detects_speech_in_loud_segment() {
        let config = VadConfig {
            frame_size: 100,
            energy_threshold: 0.005,
            silence_frames_to_end: 3,
            min_speech_frames: 2,
        };
        let mut vad = VadEngine::new(config);

        // 10 frames of near-silence to establish baseline
        for _ in 0..10 {
            let silence = vec![0.001f32; 100];
            vad.feed_samples(&silence);
        }
        assert!(!vad.is_speech_active());

        // 8 frames of loud audio (enough to exceed adaptive threshold)
        for _ in 0..8 {
            let loud = vec![0.5f32; 100];
            vad.feed_samples(&loud);
        }
        assert!(vad.is_speech_active());

        // 4 frames of silence → should trigger end
        let silence = vec![0.001f32; 100];
        let mut all_segs = Vec::new();
        for _ in 0..4 {
            let segs = vad.feed_samples(&silence);
            all_segs.extend(segs);
        }
        assert!(!all_segs.is_empty());
        assert!(all_segs[0].samples.len() > 0);
    }

    #[test]
    fn vad_ignores_short_bursts() {
        let config = VadConfig {
            frame_size: 100,
            energy_threshold: 0.01,
            silence_frames_to_end: 2,
            min_speech_frames: 5, // require 5 frames minimum
        };
        let mut vad = VadEngine::new(config);

        let loud = vec![0.5f32; 100];
        vad.feed_samples(&loud);
        vad.feed_samples(&loud);

        let silence = vec![0.001f32; 100];
        let segs = vad.feed_samples(&silence);
        let segs2 = vad.feed_samples(&silence);
        // 2 speech frames < min_speech_frames=5, so segment is discarded
        assert!(segs.is_empty() && segs2.is_empty());
    }
}
