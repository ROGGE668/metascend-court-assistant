use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use tokio::fs;

/// Document metadata returned by the knowledge base list API.
///
/// Mirrors the shape produced by Python `LocalLegalKnowledgeBase.list_documents()`.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct KnowledgeDoc {
    pub id: String,
    pub name: String,
    pub category: String,
    pub status: String,
    pub chunks: i64,
    pub date: String,
}

/// Rust-side metadata manager for the legal knowledge base.
///
/// Vector search remains in the Python sidecar; this store only lists document
/// metadata from `data/knowledge_base/` files and mirrors Python's built-in
/// fallback documents when no user files exist.
pub struct KnowledgeStore {
    base_dir: PathBuf,
    built_in: Vec<KnowledgeDoc>,
}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
#[serde(rename_all = "snake_case")]
struct RawDoc {
    law: Option<String>,
    content: Option<String>,
    case_type: Option<String>,
    #[serde(rename = "type")]
    doc_type: Option<String>,
    text: Option<String>,
    metadata: Option<HashMap<String, String>>,
}

impl KnowledgeStore {
    /// Create a store for the given knowledge base directory.
    pub async fn new(base_dir: PathBuf) -> Self {
        fs::create_dir_all(&base_dir)
            .await
            .expect("failed to create knowledge base directory");
        Self {
            base_dir,
            built_in: built_in_documents(),
        }
    }

    /// Return document metadata for every loaded knowledge base entry.
    pub async fn list_documents(&self) -> Result<Vec<KnowledgeDoc>, String> {
        let mut docs = self.load_from_disk().await?;
        if docs.is_empty() {
            docs = self.built_in.clone();
        }
        Ok(docs)
    }

    async fn load_from_disk(&self) -> Result<Vec<KnowledgeDoc>, String> {
        let mut docs = Vec::new();
        let mut dir = fs::read_dir(&self.base_dir)
            .await
            .map_err(|e| format!("failed to read knowledge base directory: {}", e))?;

        while let Some(entry) = dir.next_entry().await.map_err(|e| e.to_string())? {
            let path = entry.path();
            if !path.is_file() {
                continue;
            }
            let suffix = path
                .extension()
                .and_then(|s| s.to_str())
                .unwrap_or("")
                .to_lowercase();
            match suffix.as_str() {
                "json" => self.load_json(&path, &mut docs).await?,
                "yaml" | "yml" => self.load_yaml(&path, &mut docs).await?,
                "pdf" | "png" | "jpg" | "jpeg" | "tif" | "tiff" | "bmp" | "gif" | "webp" => {
                    self.load_media(&path, &mut docs).await?
                }
                _ => continue,
            }
        }

        // Assign sequential doc_ids, matching Python's `doc_{i}` convention.
        for (i, doc) in docs.iter_mut().enumerate() {
            doc.id = format!("doc_{}", i);
        }

        Ok(docs)
    }

    async fn load_json(&self, path: &PathBuf, docs: &mut Vec<KnowledgeDoc>) -> Result<(), String> {
        let text = fs::read_to_string(path).await.map_err(|e| e.to_string())?;
        let raw_docs: Vec<RawDoc> = serde_json::from_str(&text).map_err(|e| e.to_string())?;
        for raw in raw_docs {
            docs.push(raw.into());
        }
        Ok(())
    }

    async fn load_yaml(&self, path: &PathBuf, docs: &mut Vec<KnowledgeDoc>) -> Result<(), String> {
        let text = fs::read_to_string(path).await.map_err(|e| e.to_string())?;
        let raw_docs: Vec<RawDoc> = serde_yaml::from_str(&text).map_err(|e| e.to_string())?;
        for raw in raw_docs {
            docs.push(raw.into());
        }
        Ok(())
    }

    async fn load_media(&self, path: &PathBuf, docs: &mut Vec<KnowledgeDoc>) -> Result<(), String> {
        let name = path
            .file_stem()
            .map(|s| s.to_string_lossy().to_string())
            .unwrap_or_else(|| format!("文档 {}", docs.len() + 1));
        docs.push(KnowledgeDoc {
            id: String::new(),
            name,
            category: "其他".to_string(),
            status: "已加载".to_string(),
            chunks: 1,
            date: "-".to_string(),
        });
        Ok(())
    }
}

impl From<RawDoc> for KnowledgeDoc {
    fn from(raw: RawDoc) -> Self {
        let name = raw
            .law
            .clone()
            .or_else(|| raw.content.as_ref().map(|c| c.chars().take(30).collect()))
            .or_else(|| raw.metadata.as_ref().and_then(|m| m.get("source").cloned()))
            .unwrap_or_else(|| "未命名文档".to_string());
        let category = raw
            .case_type
            .clone()
            .or_else(|| raw.metadata.as_ref().and_then(|m| m.get("case_type").cloned()))
            .unwrap_or_else(|| "其他".to_string());
        KnowledgeDoc {
            id: String::new(),
            name,
            category,
            status: "已加载".to_string(),
            chunks: 1,
            date: "-".to_string(),
        }
    }
}

fn built_in_documents() -> Vec<KnowledgeDoc> {
    vec![
        KnowledgeDoc {
            id: "doc_0".to_string(),
            name: "《民法典》第679条".to_string(),
            category: "借贷".to_string(),
            status: "已加载".to_string(),
            chunks: 1,
            date: "-".to_string(),
        },
        KnowledgeDoc {
            id: "doc_1".to_string(),
            name: "《民法典》第680条".to_string(),
            category: "借贷".to_string(),
            status: "已加载".to_string(),
            chunks: 1,
            date: "-".to_string(),
        },
        KnowledgeDoc {
            id: "doc_2".to_string(),
            name: "《民间借贷司法解释》第25条".to_string(),
            category: "借贷".to_string(),
            status: "已加载".to_string(),
            chunks: 1,
            date: "-".to_string(),
        },
        KnowledgeDoc {
            id: "doc_3".to_string(),
            name: "《民法典》第1079条".to_string(),
            category: "离婚".to_string(),
            status: "已加载".to_string(),
            chunks: 1,
            date: "-".to_string(),
        },
        KnowledgeDoc {
            id: "doc_4".to_string(),
            name: "《民法典》第1087条".to_string(),
            category: "离婚".to_string(),
            status: "已加载".to_string(),
            chunks: 1,
            date: "-".to_string(),
        },
        KnowledgeDoc {
            id: "doc_5".to_string(),
            name: "《劳动合同法》第30条".to_string(),
            category: "劳动".to_string(),
            status: "已加载".to_string(),
            chunks: 1,
            date: "-".to_string(),
        },
        KnowledgeDoc {
            id: "doc_6".to_string(),
            name: "《劳动合同法》第31条".to_string(),
            category: "劳动".to_string(),
            status: "已加载".to_string(),
            chunks: 1,
            date: "-".to_string(),
        },
        KnowledgeDoc {
            id: "doc_7".to_string(),
            name: "《民法典》第577条".to_string(),
            category: "合同".to_string(),
            status: "已加载".to_string(),
            chunks: 1,
            date: "-".to_string(),
        },
    ]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn knowledge_store_falls_back_to_built_ins() {
        let dir = std::env::temp_dir().join(format!(
            "metascend-knowledge-defaults-test-{}",
            std::process::id()
        ));
        let _ = fs::remove_dir_all(&dir).await;
        fs::create_dir_all(&dir).await.unwrap();

        let store = KnowledgeStore::new(dir.clone()).await;
        let docs = store.list_documents().await.unwrap();
        assert_eq!(docs.len(), 8);
        assert_eq!(docs[0].name, "《民法典》第679条");

        let _ = fs::remove_dir_all(&dir).await;
    }

    #[tokio::test]
    async fn knowledge_store_loads_json_files() {
        let dir = std::env::temp_dir().join(format!(
            "metascend-knowledge-json-test-{}",
            std::process::id()
        ));
        let _ = fs::remove_dir_all(&dir).await;
        fs::create_dir_all(&dir).await.unwrap();

        fs::write(
            dir.join("custom.json"),
            r#"[{"law": "《测试法》第1条", "content": "测试内容", "case_type": "测试"}]"#,
        )
        .await
        .unwrap();

        let store = KnowledgeStore::new(dir.clone()).await;
        let docs = store.list_documents().await.unwrap();
        assert_eq!(docs.len(), 1);
        assert_eq!(docs[0].name, "《测试法》第1条");
        assert_eq!(docs[0].category, "测试");

        let _ = fs::remove_dir_all(&dir).await;
    }

    #[tokio::test]
    async fn knowledge_store_lists_media_files() {
        let dir = std::env::temp_dir().join(format!(
            "metascend-knowledge-media-test-{}",
            std::process::id()
        ));
        let _ = fs::remove_dir_all(&dir).await;
        fs::create_dir_all(&dir).await.unwrap();
        fs::write(dir.join("scan.pdf"), "fake pdf").await.unwrap();

        let store = KnowledgeStore::new(dir.clone()).await;
        let docs = store.list_documents().await.unwrap();
        assert_eq!(docs.len(), 1);
        assert_eq!(docs[0].name, "scan");

        let _ = fs::remove_dir_all(&dir).await;
    }
}
