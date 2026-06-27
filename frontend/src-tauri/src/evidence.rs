use chrono::DateTime;
use serde_json::{json, Value};
use std::path::PathBuf;
use tokio::fs;

/// Local evidence file store, mirroring `src.evidence.store.EvidenceStore`.
///
/// File import, list, and delete are handled natively in Rust. OCR text
/// extraction and PDF parsing are intentionally left to the Python sidecar
/// (via future `/evidence/{name}/preview` endpoints) until a reliable Rust
/// alternative is validated, so the response shape preserves the original
/// `ocr_status`/`text_preview` fields with safe defaults.
pub struct EvidenceStore {
    base_dir: PathBuf,
}

impl EvidenceStore {
    pub async fn new(data_dir: PathBuf) -> Self {
        let base_dir = data_dir.join("evidence");
        fs::create_dir_all(&base_dir)
            .await
            .expect("failed to create evidence directory");
        Self { base_dir }
    }

    /// Return metadata for every stored evidence file.
    pub async fn list(&self) -> Result<Vec<Value>, String> {
        let mut items = Vec::new();
        let mut dir = fs::read_dir(&self.base_dir)
            .await
            .map_err(|e| format!("failed to read evidence directory: {}", e))?;

        while let Some(entry) = dir.next_entry().await.map_err(|e| e.to_string())? {
            let path = entry.path();
            let metadata = match fs::metadata(&path).await {
                Ok(m) if m.is_file() => m,
                _ => continue,
            };
            items.push(self.item_from_path(&path, &metadata).await?);
        }

        items.sort_by(|a, b| {
            let a_name = a["name"].as_str().unwrap_or("");
            let b_name = b["name"].as_str().unwrap_or("");
            a_name.cmp(b_name)
        });

        Ok(items)
    }

    /// Copy an external file into the evidence store, appending a numeric
    /// suffix if the name already exists.
    pub async fn import_file(&self, source_path: String) -> Result<Value, String> {
        let src = PathBuf::from(source_path);
        let metadata = fs::metadata(&src)
            .await
            .map_err(|e| format!("file not found: {}", e))?;
        if !metadata.is_file() {
            return Err("not a file".to_string());
        }

        let mut dest = self.base_dir.join(src.file_name().ok_or("invalid source path")?);

        // Resolve name collisions by appending _1, _2, ... before the extension.
        if dest.exists() {
            let stem = src.file_stem().unwrap_or_default().to_string_lossy();
            let ext = src.extension().unwrap_or_default().to_string_lossy();
            let mut counter = 1;
            loop {
                let candidate = if ext.is_empty() {
                    self.base_dir.join(format!("{}_{}", stem, counter))
                } else {
                    self.base_dir.join(format!("{}_{}.{}", stem, counter, ext))
                };
                if !candidate.exists() {
                    dest = candidate;
                    break;
                }
                counter += 1;
            }
        }

        fs::copy(&src, &dest)
            .await
            .map_err(|e| format!("failed to copy evidence file: {}", e))?;

        let metadata = fs::metadata(&dest).await.map_err(|e| e.to_string())?;
        self.item_from_path(&dest, &metadata).await
    }

    /// Delete an evidence file by name, with path-traversal protection.
    pub async fn delete(&self, name: String) -> Result<(), String> {
        let path = self.resolve_path(&name)?;
        if !path.exists() {
            return Err(format!("evidence not found: {}", name));
        }
        fs::remove_file(&path)
            .await
            .map_err(|e| format!("failed to delete evidence file: {}", e))?;
        Ok(())
    }

    async fn item_from_path(&self, path: &PathBuf, metadata: &std::fs::Metadata) -> Result<Value, String> {
        let name = path
            .file_name()
            .map(|n| n.to_string_lossy().to_string())
            .unwrap_or_default();
        let suffix = path
            .extension()
            .map(|e| e.to_string_lossy().to_string())
            .unwrap_or_default();
        let modified_at = metadata
            .modified()
            .map_err(|e| e.to_string())?
            .duration_since(std::time::UNIX_EPOCH)
            .map_err(|e| e.to_string())?
            .as_millis() as i64;
        let modified_at_utc = DateTime::from_timestamp_millis(modified_at)
            .ok_or("invalid modified time")?
            .to_rfc3339();

        let ocr_path = path.with_extension("ocr.txt");
        let (ocr_status, text_preview) = match fs::read_to_string(&ocr_path).await {
            Ok(text) => ("ready", text.chars().take(200).collect::<String>()),
            Err(_) => ("unavailable", String::new()),
        };

        Ok(json!({
            "name": name,
            "size": metadata.len(),
            "suffix": suffix,
            "modified_at": modified_at_utc,
            "ocr_status": ocr_status,
            "text_preview": text_preview,
        }))
    }

    /// Return the stored filesystem path for an evidence file by name.
    pub fn file_path(&self, name: &str) -> PathBuf {
        self.base_dir.join(name)
    }

    fn resolve_path(&self, name: &str) -> Result<PathBuf, String> {
        let candidate = self.base_dir.join(name);
        let resolved = candidate.canonicalize().map_err(|e| e.to_string())?;
        let base_canonical = self.base_dir.canonicalize().map_err(|e| e.to_string())?;
        if !resolved.starts_with(&base_canonical) {
            return Err("invalid evidence name".to_string());
        }
        Ok(resolved)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn evidence_store_imports_lists_and_deletes() {
        let dir = std::env::temp_dir().join(format!("metascend-evidence-test-{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir).await;
        fs::create_dir_all(&dir).await.unwrap();

        let store = EvidenceStore::new(dir.clone()).await;
        let list = store.list().await.unwrap();
        assert!(list.is_empty());

        // Create two source files with the same base name to exercise collision handling.
        let src_dir = dir.join("src");
        fs::create_dir_all(&src_dir).await.unwrap();
        let src1 = src_dir.join("contract.txt");
        fs::write(&src1, "contract one").await.unwrap();
        let src2 = src_dir.join("contract.txt");
        fs::write(&src2, "contract two").await.unwrap();

        let imported1 = store
            .import_file(src1.to_string_lossy().to_string())
            .await
            .unwrap();
        assert_eq!(imported1["name"], "contract.txt");
        assert_eq!(imported1["suffix"], "txt");

        let imported2 = store
            .import_file(src2.to_string_lossy().to_string())
            .await
            .unwrap();
        assert_eq!(imported2["name"], "contract_1.txt");

        let list = store.list().await.unwrap();
        assert_eq!(list.len(), 2);

        store.delete("contract.txt".to_string()).await.unwrap();
        let list = store.list().await.unwrap();
        assert_eq!(list.len(), 1);
        assert_eq!(list[0]["name"], "contract_1.txt");

        let _ = fs::remove_dir_all(&dir).await;
    }
}
