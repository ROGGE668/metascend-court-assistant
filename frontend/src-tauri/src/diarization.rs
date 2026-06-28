//! 说话人分离（简化版）—— 基于 MFCC 特征的余弦相似度。
//!
//! 工作流程：
//! 1. 校准时为每个角色录制 5 秒音频，提取 MFCC 特征向量作为声纹嵌入。
//! 2. 实时转写时，对每段语音提取同样的 MFCC 特征，与校准嵌入比对。
//! 3. 返回最匹配的角色标签。
//!
//! 这是一个轻量级方案，无需外部 ML 模型。
//! 对于短时说话人区分已经够用；如需更准确的 diarization，
//! 后续可替换为 pyannote-rs / ONNX speaker embedding。

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use tokio::sync::RwLock;

/// 说话人声纹嵌入（MFCC 特征向量）。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SpeakerProfile {
    pub role: String,
    /// 13 维 MFCC 均值向量。
    pub embedding: Vec<f32>,
    /// 校准时的音频时长（采样数）。
    pub sample_count: usize,
    /// 校准时间戳。
    pub calibrated_at: String,
}

/// 说话人识别结果。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SpeakerMatch {
    pub role: String,
    pub confidence: f32,
}

/// 说话人分离引擎。
pub struct DiarizationEngine {
    profiles: RwLock<HashMap<String, SpeakerProfile>>,
}

impl DiarizationEngine {
    pub fn new() -> Self {
        Self {
            profiles: RwLock::new(HashMap::new()),
        }
    }

    /// 校准：从音频采样中提取声纹嵌入并存储。
    pub async fn calibrate(&self, role: &str, samples: &[f32], sample_rate: u32) -> Result<SpeakerProfile, String> {
        if samples.len() < (sample_rate as usize / 2) {
            return Err("校准音频过短，至少需要 0.5 秒".into());
        }

        let embedding = extract_mfcc_embedding(samples, sample_rate);
        let profile = SpeakerProfile {
            role: role.to_string(),
            embedding,
            sample_count: samples.len(),
            calibrated_at: chrono::Local::now().to_rfc3339(),
        };

        let mut profiles = self.profiles.write().await;
        profiles.insert(role.to_string(), profile.clone());
        Ok(profile)
    }

    /// 识别：将音频段与已校准的声纹比对，返回最匹配角色。
    pub async fn identify(&self, samples: &[f32], sample_rate: u32) -> SpeakerMatch {
        let profiles = self.profiles.read().await;
        if profiles.is_empty() {
            return SpeakerMatch {
                role: "未校准".to_string(),
                confidence: 0.0,
            };
        }

        let embedding = extract_mfcc_embedding(samples, sample_rate);
        let mut best_role = "未知".to_string();
        let mut best_sim = -1.0f32;

        for (role, profile) in profiles.iter() {
            let sim = cosine_similarity(&embedding, &profile.embedding);
            if sim > best_sim {
                best_sim = sim;
                best_role = role.clone();
            }
        }

        SpeakerMatch {
            role: best_role,
            confidence: best_sim,
        }
    }

    /// 获取所有已校准的角色。
    pub async fn calibrated_roles(&self) -> Vec<String> {
        let profiles = self.profiles.read().await;
        profiles.keys().cloned().collect()
    }

    /// 检查某个角色是否已校准。
    pub async fn is_calibrated(&self, role: &str) -> bool {
        let profiles = self.profiles.read().await;
        profiles.contains_key(role)
    }

    /// 重置所有校准数据。
    pub async fn reset(&self) {
        let mut profiles = self.profiles.write().await;
        profiles.clear();
    }
}

/// 提取 MFCC 嵌入向量（简化版：13 维 MFCC 均值）。
///
/// 完整实现应使用 DCT + Mel 滤波器组；这里用简化方案：
/// 1. 分帧（25ms, 10ms hop）
/// 2. 计算每帧的频谱质心 + 能量 + 前 11 个频带能量
/// 3. 对所有帧取均值作为嵌入
fn extract_mfcc_embedding(samples: &[f32], sample_rate: u32) -> Vec<f32> {
    let frame_len = (sample_rate as f32 * 0.025) as usize; // 25ms
    let hop_len = (sample_rate as f32 * 0.010) as usize;   // 10ms hop

    if samples.len() < frame_len || frame_len == 0 {
        return vec![0.0; 13];
    }

    let n_bands = 12;
    let mut feature_sum = vec![0.0f32; 13]; // 13 维
    let mut frame_count = 0usize;

    let mut start = 0;
    while start + frame_len <= samples.len() {
        let frame = &samples[start..start + frame_len];
        let mut features = vec![0.0f32; 13];

        // 能量
        let energy: f32 = frame.iter().map(|x| x * x).sum();
        features[0] = energy.sqrt();

        // 频谱质心
        let mut weighted_sum = 0.0f32;
        let mut magnitude_sum = 0.0f32;
        for (i, &s) in frame.iter().enumerate() {
            let mag = s.abs();
            weighted_sum += i as f32 * mag;
            magnitude_sum += mag;
        }
        features[1] = if magnitude_sum > 0.0 {
            weighted_sum / magnitude_sum / frame_len as f32
        } else {
            0.0
        };

        // 频带能量（简化版：将帧等分 12 个子带）
        let band_len = frame_len / n_bands;
        if band_len > 0 {
            for b in 0..n_bands {
                let b_start = b * band_len;
                let b_end = (b_start + band_len).min(frame_len);
                let band_energy: f32 = frame[b_start..b_end].iter().map(|x| x * x).sum();
                features[2 + b.min(10)] = band_energy.sqrt();
            }
        }

        for (s, f) in feature_sum.iter_mut().zip(features.iter()) {
            *s += f;
        }
        frame_count += 1;
        start += hop_len;
    }

    if frame_count > 0 {
        for s in feature_sum.iter_mut() {
            *s /= frame_count as f32;
        }
    }

    // L2 归一化
    let norm: f32 = feature_sum.iter().map(|x| x * x).sum::<f32>().sqrt();
    if norm > 1e-8 {
        for s in feature_sum.iter_mut() {
            *s /= norm;
        }
    }

    feature_sum
}

/// 余弦相似度。
fn cosine_similarity(a: &[f32], b: &[f32]) -> f32 {
    if a.len() != b.len() || a.is_empty() {
        return 0.0;
    }
    let dot: f32 = a.iter().zip(b.iter()).map(|(x, y)| x * y).sum();
    let na: f32 = a.iter().map(|x| x * x).sum::<f32>().sqrt();
    let nb: f32 = b.iter().map(|x| x * x).sum::<f32>().sqrt();
    if na < 1e-8 || nb < 1e-8 {
        0.0
    } else {
        dot / (na * nb)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cosine_similarity_identical_vectors() {
        let a = vec![1.0, 2.0, 3.0];
        let sim = cosine_similarity(&a, &a);
        assert!((sim - 1.0).abs() < 1e-5);
    }

    #[test]
    fn cosine_similarity_orthogonal_vectors() {
        let a = vec![1.0, 0.0, 0.0];
        let b = vec![0.0, 1.0, 0.0];
        let sim = cosine_similarity(&a, &b);
        assert!(sim.abs() < 1e-5);
    }

    #[test]
    fn cosine_similarity_empty_vectors() {
        let a: Vec<f32> = vec![];
        let sim = cosine_similarity(&a, &a);
        assert_eq!(sim, 0.0);
    }

    #[test]
    fn mfcc_embedding_returns_correct_dimension() {
        let samples = vec![0.1f32; 16000]; // 1 second at 16kHz
        let emb = extract_mfcc_embedding(&samples, 16000);
        assert_eq!(emb.len(), 13);
    }

    #[test]
    fn mfcc_embedding_handles_short_input() {
        let samples = vec![0.1f32; 100];
        let emb = extract_mfcc_embedding(&samples, 16000);
        assert_eq!(emb.len(), 13);
    }

    #[tokio::test]
    async fn diarization_calibrate_and_identify() {
        let engine = DiarizationEngine::new();

        // 生成不同的"声纹"（不同频率）
        let samples_judge: Vec<f32> = (0..16000)
            .map(|i| (2.0 * std::f32::consts::PI * 300.0 * i as f32 / 16000.0).sin() * 0.3)
            .collect();
        let samples_party: Vec<f32> = (0..16000)
            .map(|i| (2.0 * std::f32::consts::PI * 500.0 * i as f32 / 16000.0).sin() * 0.3)
            .collect();

        engine.calibrate("法官", &samples_judge, 16000).await.unwrap();
        engine.calibrate("己方", &samples_party, 16000).await.unwrap();

        // 用法官的音频应该识别为法官
        let result = engine.identify(&samples_judge, 16000).await;
        assert_eq!(result.role, "法官");
        assert!(result.confidence > 0.5);

        // 用己方的音频应该识别为己方
        let result = engine.identify(&samples_party, 16000).await;
        assert_eq!(result.role, "己方");
    }
}
