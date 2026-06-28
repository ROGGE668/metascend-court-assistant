//! 法律策略引擎。
//!
//! 从 `data/templates/strategies.yaml` 加载案件类型对应的质证/辩论/通用策略。
//! 根据发言关键词和案件类型动态匹配最佳策略。

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::path::PathBuf;
use tokio::fs;

/// 策略模板（质证/辩论/通用）。
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct StrategyTemplate {
    #[serde(default)]
    pub 质证: String,
    #[serde(default)]
    pub 辩论: String,
    #[serde(default)]
    pub 通用: String,
}

/// 法律策略引擎。
pub struct StrategyEngine {
    strategies: HashMap<String, StrategyTemplate>,
    /// 当前活跃案件类型（可由前端设置）。
    active_case_type: Option<String>,
}

impl StrategyEngine {
    pub async fn new(template_path: PathBuf) -> Self {
        let strategies = Self::load_strategies(&template_path).await;
        Self {
            strategies,
            active_case_type: None,
        }
    }

    /// 加载策略 YAML。
    async fn load_strategies(path: &PathBuf) -> HashMap<String, StrategyTemplate> {
        match fs::read_to_string(path).await {
            Ok(text) => serde_yaml::from_str(&text).unwrap_or_default(),
            Err(_) => HashMap::new(),
        }
    }

    /// 重新加载策略（支持热更新）。
    pub async fn reload(&mut self, template_path: PathBuf) {
        self.strategies = Self::load_strategies(&template_path).await;
    }

    /// 设置当前案件类型。
    pub fn set_active_case_type(&mut self, case_type: Option<String>) {
        self.active_case_type = case_type;
    }

    /// 根据发言内容和案件类型获取策略建议。
    pub fn get_suggestion(&self, text: &str, case_type: Option<&str>) -> Value {
        let ct = case_type
            .or(self.active_case_type.as_deref())
            .unwrap_or("通用");

        // 关键词检测庭审阶段
        let stage = self.detect_stage(text);

        // 查找匹配的策略模板
        let (template, matched_type) = self.find_template(ct, text);

        let (hint, countermeasure) = match template {
            Some(tpl) => {
                let hint = match stage.as_str() {
                    "质证" => tpl.质证.clone(),
                    "辩论" => tpl.辩论.clone(),
                    _ => tpl.通用.clone(),
                };
                let countermeasure = format!(
                    "当前阶段：{} · 案件类型：{}\n建议：{}",
                    stage, ct, hint
                );
                (hint, countermeasure)
            }
            None => {
                let default_hint = self.default_suggestion(text);
                (default_hint.clone(), default_hint)
            }
        };

        json!({
            "text": hint,
            "countermeasure": countermeasure,
            "laws": self.get_relevant_laws(ct, &stage),
            "case_type": matched_type,
            "stage": stage,
            "disclaimer": "本系统输出仅供参考，不构成法律意见。"
        })
    }

    /// 检测发言属于哪个庭审阶段。
    fn detect_stage(&self, text: &str) -> String {
        if text.contains("质证") || text.contains("证据") || text.contains("真实性") || text.contains("异议") {
            "质证".to_string()
        } else if text.contains("辩论") || text.contains("主张") || text.contains("应当") || text.contains("责任") {
            "辩论".to_string()
        } else {
            "通用".to_string()
        }
    }

    /// 查找匹配的策略模板（精确匹配案件类型，或模糊匹配关键词）。
    /// 返回 (模板引用, 匹配到的案件类型)。
    fn find_template(&self, case_type: &str, text: &str) -> (Option<&StrategyTemplate>, String) {
        // 精确匹配（跳过通用类型）
        if case_type != "通用" {
            if let Some(tpl) = self.strategies.get(case_type) {
                return (Some(tpl), case_type.to_string());
            }
        }

        // 模糊匹配：从发言中提取案件类型关键词
        let keywords = [
            ("借贷", vec!["借款", "贷款", "利息", "还款", "本金"]),
            ("离婚", vec!["离婚", "抚养", "财产分割", "婚姻"]),
            ("劳动", vec!["劳动", "工资", "加班", "社保", "解除"]),
            ("合同", vec!["合同", "违约", "履行", "赔偿", "签订"]),
        ];

        for (ctype, kws) in &keywords {
            if kws.iter().any(|kw| text.contains(*kw)) {
                return (self.strategies.get(*ctype), ctype.to_string());
            }
        }

        (None, "通用".to_string())
    }

    /// 获取相关法律条文。
    fn get_relevant_laws(&self, case_type: &str, stage: &str) -> Vec<String> {
        match (case_type, stage) {
            ("借贷", "质证") => vec!["《民法典》第667条（借款合同）".to_string(), "《最高人民法院关于审理民间借贷案件适用法律若干问题的规定》".to_string()],
            ("借贷", "辩论") => vec!["《民法典》第680条（利率限制）".to_string()],
            ("离婚", _) => vec!["《民法典》第1079条（离婚条件）".to_string(), "《民法典》第1087条（财产分割）".to_string()],
            ("劳动", _) => vec!["《劳动合同法》第38条（解除权）".to_string(), "《劳动法》第44条（加班费）".to_string()],
            ("合同", "质证") => vec!["《民法典》第490条（合同形式）".to_string()],
            ("合同", "辩论") => vec!["《民法典》第577条（违约责任）".to_string()],
            _ => vec![],
        }
    }

    /// 无匹配时的默认建议。
    fn default_suggestion(&self, text: &str) -> String {
        if text.contains("异议") {
            "对方提出异议，建议关注异议的具体内容和法律依据。".to_string()
        } else if text.contains("证据") {
            "涉及证据问题，建议核实证据的真实性、合法性和关联性。".to_string()
        } else if text.contains("赔偿") || text.contains("损失") {
            "涉及赔偿/损失问题，建议明确计算依据和因果关系。".to_string()
        } else {
            "正在分析发言内容...".to_string()
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    #[tokio::test]
    async fn strategy_engine_loads_templates() {
        let manifest_dir = std::env::var("CARGO_MANIFEST_DIR").unwrap_or_default();
        let root = PathBuf::from(manifest_dir)
            .parent()
            .and_then(|p| p.parent())
            .map(|p| p.to_path_buf())
            .unwrap_or_default();
        let template_path = root.join("data").join("templates").join("strategies.yaml");

        let engine = StrategyEngine::new(template_path).await;

        // 借贷质证
        let suggestion = engine.get_suggestion("对证据的真实性提出异议", Some("借贷"));
        assert!(suggestion["text"].as_str().unwrap().contains("异议"));
        assert_eq!(suggestion["case_type"].as_str().unwrap(), "借贷");
        assert_eq!(suggestion["stage"].as_str().unwrap(), "质证");

        // 劳动辩论
        let suggestion = engine.get_suggestion("主张用人单位应当支付加班费", Some("劳动"));
        assert_eq!(suggestion["case_type"].as_str().unwrap(), "劳动");
        assert_eq!(suggestion["stage"].as_str().unwrap(), "辩论");
    }

    #[tokio::test]
    async fn strategy_engine_fuzzy_match() {
        let manifest_dir = std::env::var("CARGO_MANIFEST_DIR").unwrap_or_default();
        let root = PathBuf::from(manifest_dir)
            .parent()
            .and_then(|p| p.parent())
            .map(|p| p.to_path_buf())
            .unwrap_or_default();
        let template_path = root.join("data").join("templates").join("strategies.yaml");

        let engine = StrategyEngine::new(template_path).await;

        // 从关键词自动匹配借贷（文本包含"借款"）
        let suggestion = engine.get_suggestion("对方要求偿还借款本金", None);
        let ct = suggestion["case_type"].as_str().unwrap();
        assert_eq!(ct, "借贷", "expected '借贷' but got '{}', strategies keys: {:?}", ct, engine.strategies.keys().collect::<Vec<_>>());
    }

    #[tokio::test]
    async fn strategy_engine_default_fallback() {
        let engine = StrategyEngine {
            strategies: HashMap::new(),
            active_case_type: None,
        };
        let suggestion = engine.get_suggestion("对方提出异议", None);
        assert!(suggestion["text"].as_str().unwrap().contains("异议"));
    }
}

/// 策略报告结构。
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct StrategyReport {
    pub summary: String,
    pub case_type: String,
    pub key_points: Vec<String>,
    pub suggestions: Vec<String>,
    pub relevant_laws: Vec<String>,
    pub risk_analysis: String,
    pub generated_at: String,
}

impl StrategyEngine {
    /// 生成完整策略报告，基于转写历史和聊天记录。
    pub fn generate_report(
        &self,
        transcripts: &[String],
        case_type: Option<&str>,
    ) -> StrategyReport {
        let ct = case_type.unwrap_or("通用");
        let mut key_points = Vec::new();
        let mut suggestions = Vec::new();
        let mut all_laws = Vec::new();

        // 分析每条转写内容
        for text in transcripts {
            let suggestion = self.get_suggestion(text, Some(ct));
            
            // 提取关键点
            if let Some(stage) = suggestion["stage"].as_str() {
                key_points.push(format!("[{}] {}", stage, text));
            }
            
            // 提取建议
            if let Some(countermeasure) = suggestion["countermeasure"].as_str() {
                if !countermeasure.is_empty() && !suggestions.contains(&countermeasure.to_string()) {
                    suggestions.push(countermeasure.to_string());
                }
            }
            
            // 提取法律条文
            if let Some(laws) = suggestion["laws"].as_array() {
                for law in laws {
                    if let Some(law_str) = law.as_str() {
                        if !all_laws.contains(&law_str.to_string()) {
                            all_laws.push(law_str.to_string());
                        }
                    }
                }
            }
        }

        // 风险分析
        let risk_analysis = self.analyze_risks(transcripts, ct);

        // 生成摘要
        let summary = format!(
            "案件类型：{}\n转写记录数：{}\n识别到的关键点：{}\n建议数：{}",
            ct,
            transcripts.len(),
            key_points.len(),
            suggestions.len()
        );

        StrategyReport {
            summary,
            case_type: ct.to_string(),
            key_points,
            suggestions,
            relevant_laws: all_laws,
            risk_analysis,
            generated_at: chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string(),
        }
    }

    /// 风险分析。
    fn analyze_risks(&self, transcripts: &[String], case_type: &str) -> String {
        let mut risks = Vec::new();

        // 检查是否遗漏关键证据
        let has_evidence = transcripts.iter().any(|t| t.contains("证据"));
        if !has_evidence {
            risks.push("未提及证据问题，建议补充证据说明。".to_string());
        }

        // 检查是否回应了对方主张
        let has_response = transcripts.iter().any(|t| t.contains("回应") || t.contains("反驳"));
        if !has_response {
            risks.push("未明确回应对方主张，建议准备反驳要点。".to_string());
        }

        // 根据案件类型检查特定风险
        match case_type {
            "借贷" => {
                let has_amount = transcripts.iter().any(|t| t.contains("金额") || t.contains("利息"));
                if !has_amount {
                    risks.push("借贷案件未明确金额和利息，建议核实具体数字。".to_string());
                }
            }
            "离婚" => {
                let has_property = transcripts.iter().any(|t| t.contains("财产") || t.contains("抚养"));
                if !has_property {
                    risks.push("离婚案件未涉及财产分割或抚养权，建议补充相关陈述。".to_string());
                }
            }
            _ => {}
        }

        if risks.is_empty() {
            "未发现明显风险。".to_string()
        } else {
            risks.join("\n")
        }
    }
}
