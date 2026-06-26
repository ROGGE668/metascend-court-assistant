use chrono::{Datelike, Utc};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::path::PathBuf;
use tokio::fs;
use tokio::io::AsyncWriteExt;

/// Local case archive store, mirroring `src.case_archive.store.CaseArchive`.
///
/// Each case is stored as `data_dir/cases/{case_id}.json`. Entity lists are
/// kept as typed structs so files written by the Python backend remain readable
/// and files written by Rust remain compatible with Python.
pub struct CaseStore {
    base_dir: PathBuf,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub struct CaseParty {
    pub code: String,
    pub role: String,
    pub name: String,
    #[serde(default)]
    pub description: String,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub struct CaseMaterial {
    pub code: String,
    pub title: String,
    pub content: String,
    #[serde(default)]
    pub file_path: Option<String>,
    #[serde(default)]
    pub created_at: String,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub struct CaseEvidence {
    pub code: String,
    pub title: String,
    pub description: String,
    #[serde(default = "document_type")]
    pub evidence_type: String,
    #[serde(default)]
    pub source_party_code: Option<String>,
    #[serde(default)]
    pub file_path: Option<String>,
    #[serde(default)]
    pub tags: Vec<String>,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub struct CaseAppeal {
    pub code: String,
    pub title: String,
    pub content: String,
    #[serde(default = "complaint_type")]
    pub appeal_type: String,
    #[serde(default)]
    pub created_at: String,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub struct CaseRelatedCase {
    pub code: String,
    pub title: String,
    pub source: String,
    pub summary: String,
    #[serde(default)]
    pub reference_laws: Vec<String>,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub struct CaseLegalClause {
    pub code: String,
    pub title: String,
    pub content: String,
    #[serde(default)]
    pub law_source: String,
    #[serde(default)]
    pub tags: Vec<String>,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub struct CaseFact {
    pub code: String,
    pub content: String,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub struct CaseArgument {
    pub code: String,
    pub content: String,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub struct CaseFile {
    pub case_id: String,
    #[serde(default = "other_case_type")]
    pub case_type: String,
    pub title: String,
    pub created_at: String,
    pub updated_at: String,
    #[serde(default)]
    pub parties: Vec<CaseParty>,
    #[serde(default)]
    pub facts: Vec<CaseFact>,
    #[serde(default)]
    pub materials: Vec<CaseMaterial>,
    #[serde(default)]
    pub evidence: Vec<CaseEvidence>,
    #[serde(default)]
    pub appeals: Vec<CaseAppeal>,
    #[serde(default)]
    pub related_cases: Vec<CaseRelatedCase>,
    #[serde(default)]
    pub legal_clauses: Vec<CaseLegalClause>,
    #[serde(default)]
    pub strategy_notes: Vec<CaseArgument>,
}

fn document_type() -> String {
    "document".to_string()
}

fn complaint_type() -> String {
    "complaint".to_string()
}

fn other_case_type() -> String {
    "other".to_string()
}

impl CaseStore {
    pub async fn new(data_dir: PathBuf) -> Self {
        let base_dir = data_dir.join("cases");
        fs::create_dir_all(&base_dir)
            .await
            .expect("failed to create cases directory");
        Self { base_dir }
    }

    /// Return a lightweight summary for every stored case, sorted newest-first.
    pub async fn list_cases(&self) -> Result<Vec<Value>, String> {
        let mut entries = Vec::new();
        let mut dir = fs::read_dir(&self.base_dir)
            .await
            .map_err(|e| format!("failed to read cases directory: {}", e))?;

        while let Some(entry) = dir.next_entry().await.map_err(|e| e.to_string())? {
            let path = entry.path();
            if path.extension().and_then(|s| s.to_str()) != Some("json") {
                continue;
            }

            let text = fs::read_to_string(&path).await.map_err(|e| e.to_string())?;
            let data: Value = serde_json::from_str(&text).map_err(|e| e.to_string())?;
            entries.push(json!({
                "case_id": data.get("case_id").and_then(|v| v.as_str()).unwrap_or(""),
                "case_type": data.get("case_type").and_then(|v| v.as_str()).unwrap_or("other"),
                "title": data.get("title").and_then(|v| v.as_str()).unwrap_or(""),
                "updated_at": data.get("updated_at").and_then(|v| v.as_str()).unwrap_or(""),
            }));
        }

        entries.sort_by(|a, b| {
            let a_updated = a["updated_at"].as_str().unwrap_or("");
            let b_updated = b["updated_at"].as_str().unwrap_or("");
            b_updated.cmp(a_updated)
        });

        Ok(entries)
    }

    /// Create a new case file and return its full JSON representation.
    pub async fn create_case(&self, title: String, case_type: String) -> Result<Value, String> {
        let now = Utc::now().to_rfc3339();
        let case_id = generate_case_id();
        let case = CaseFile {
            case_id: case_id.clone(),
            case_type: case_type.clone(),
            title: title.clone(),
            created_at: now.clone(),
            updated_at: now,
            ..Default::default()
        };
        self.save(&case).await?;
        Ok(json!(case))
    }

    /// Load a case by id, returning `None` if it does not exist.
    pub async fn get_case(&self, case_id: String) -> Result<Option<Value>, String> {
        let path = self.path(&case_id);
        if !path.exists() {
            return Ok(None);
        }
        let text = fs::read_to_string(&path).await.map_err(|e| e.to_string())?;
        let case: CaseFile = serde_json::from_str(&text).map_err(|e| e.to_string())?;
        Ok(Some(json!(case)))
    }

    async fn save(&self, case: &CaseFile) -> Result<(), String> {
        let path = self.path(&case.case_id);
        let json = serde_json::to_string_pretty(case).map_err(|e| e.to_string())?;
        let mut file = fs::File::create(&path)
            .await
            .map_err(|e| format!("failed to create case file: {}", e))?;
        file.write_all(json.as_bytes())
            .await
            .map_err(|e| format!("failed to write case file: {}", e))?;
        file.flush()
            .await
            .map_err(|e| format!("failed to flush case file: {}", e))?;
        Ok(())
    }

    fn path(&self, case_id: &str) -> PathBuf {
        let safe = PathBuf::from(case_id)
            .file_name()
            .map(|n| n.to_string_lossy().to_string())
            .unwrap_or_default();
        self.base_dir.join(format!("{}.json", safe))
    }
}

fn generate_case_id() -> String {
    let now = Utc::now();
    let year = now.year();
    let seq = (now.timestamp() % 10000) as u16;
    format!("CASE-{}-{:04}", year, seq)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn case_store_lists_and_creates_cases() {
        let dir = std::env::temp_dir().join(format!("metascend-cases-test-{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir).await;
        fs::create_dir_all(&dir).await.unwrap();

        let store = CaseStore::new(dir.clone()).await;
        let list = store.list_cases().await.unwrap();
        assert!(list.is_empty());

        let created = store
            .create_case("Test Case".to_string(), "loan".to_string())
            .await
            .unwrap();
        assert_eq!(created["title"], "Test Case");
        assert_eq!(created["case_type"], "loan");
        assert!(created["case_id"].as_str().unwrap().starts_with("CASE-"));

        let list = store.list_cases().await.unwrap();
        assert_eq!(list.len(), 1);
        assert_eq!(list[0]["title"], "Test Case");

        let case_id = created["case_id"].as_str().unwrap().to_string();
        let loaded = store.get_case(case_id).await.unwrap();
        assert!(loaded.is_some());
        assert_eq!(loaded.unwrap()["title"], "Test Case");

        let _ = fs::remove_dir_all(&dir).await;
    }
}
