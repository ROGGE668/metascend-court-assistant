use std::mem;
use std::path::PathBuf;
use std::sync::atomic::{AtomicU32, Ordering};
use std::sync::Arc;
use std::time::Duration;
use tokio::fs::OpenOptions;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader, BufWriter};
use tokio::process::{ChildStderr, ChildStdout, Command};
use tokio::sync::{Mutex, RwLock};
use tokio::task::JoinHandle;
use tokio::time::{sleep, Instant};

fn _assert_types() {
    fn assert_send<T: Send>() {}
    fn assert_sync<T: Sync>() {}
    assert_send::<tokio::process::ChildStdout>();
    assert_send::<tokio::process::ChildStderr>();
    assert_send::<SidecarState>();
    assert_sync::<SidecarState>();
    assert_send::<tokio::sync::Mutex<SidecarState>>();
    assert_sync::<tokio::sync::Mutex<SidecarState>>();
    assert_send::<SidecarManager>();
    assert_sync::<SidecarManager>();
    assert_send::<Arc<SidecarManager>>();
}

pub struct SidecarManager {
    backend_url: RwLock<String>,
    state: Mutex<SidecarState>,
    restart_count: AtomicU32,
    base_port: u16,
    log_path: PathBuf,
}

struct SidecarState {
    child_pid: Option<u32>,
    health_handle: Option<JoinHandle<()>>,
    log_handles: Vec<JoinHandle<()>>,
}

impl SidecarManager {
    pub fn new(base_port: u16, log_path: PathBuf) -> Arc<Self> {
        Arc::new(Self {
            backend_url: RwLock::new(format!("http://127.0.0.1:{}", base_port)),
            state: Mutex::new(SidecarState {
                child_pid: None,
                health_handle: None,
                log_handles: Vec::new(),
            }),
            restart_count: AtomicU32::new(0),
            base_port,
            log_path,
        })
    }

    pub fn backend_url(self: Arc<Self>) -> impl std::future::Future<Output = String> + Send {
        async move { self.backend_url.read().await.clone() }
    }

    pub fn start(manager: Arc<Self>) -> impl std::future::Future<Output = Result<(), String>> + Send {
        async move {
            {
                let state = manager.state.lock().await;
                if state.child_pid.is_some() {
                    return Ok(());
                }
            }

            let port = Self::resolve_port(manager.base_port).await?;
            {
                let mut url = manager.backend_url.write().await;
                *url = format!("http://127.0.0.1:{}", port);
            }

            let (pid, stdout, stderr) = Self::spawn_python(port)?;

            let log_path_stdout = manager.log_path.clone();
            let log_path_stderr = manager.log_path.clone();

            let stdout_handle = tokio::spawn(async move {
                forward_stream(stdout, log_path_stdout, "stdout").await;
            });
            let stderr_handle = tokio::spawn(async move {
                forward_stream(stderr, log_path_stderr, "stderr").await;
            });

            {
                let mut state = manager.state.lock().await;
                state.child_pid = Some(pid);
                state.log_handles.push(stdout_handle);
                state.log_handles.push(stderr_handle);
            }

            Self::wait_for_ready(manager.clone().backend_url().await).await?;

            let manager_clone = manager.clone();
            let health_handle = tokio::spawn(async move {
                health_check_loop(manager_clone).await;
            });
            manager.state.lock().await.health_handle = Some(health_handle);

            manager.restart_count.store(0, Ordering::SeqCst);
            Ok(())
        }
    }

    pub fn stop(self: Arc<Self>) -> impl std::future::Future<Output = Result<(), String>> + Send {
        async move {
            let url = self.clone().backend_url().await;
            let mut state = self.state.lock().await;

            if let Some(handle) = state.health_handle.take() {
                handle.abort();
            }
            for handle in state.log_handles.drain(..) {
                handle.abort();
            }

            let _ = reqwest::Client::new()
                .post(format!("{}/courtroom/stop", url))
                .timeout(Duration::from_secs(3))
                .send()
                .await;

            if let Some(pid) = state.child_pid.take() {
                let pid = pid as i32;
                let _ = send_signal(pid, nix::sys::signal::Signal::SIGTERM);
                let deadline = Instant::now() + Duration::from_secs(5);
                while Instant::now() < deadline {
                    if !is_process_alive(pid) {
                        break;
                    }
                    sleep(Duration::from_millis(100)).await;
                }
                if is_process_alive(pid) {
                    let _ = send_signal(pid, nix::sys::signal::Signal::SIGKILL);
                }
            }

            Ok(())
        }
    }

    pub fn restart(manager: Arc<Self>) -> impl std::future::Future<Output = Result<(), String>> + Send {
        async move {
            manager.clone().stop().await?;
            sleep(Duration::from_millis(500)).await;
            Self::start(manager).await
        }
    }

    async fn resolve_port(base: u16) -> Result<u16, String> {
        for port in base..=base + 20 {
            if is_port_free(port).await {
                return Ok(port);
            }

            let url = format!("http://127.0.0.1:{}/health", port);
            if let Ok(resp) = reqwest::get(&url).await {
                if resp.status().is_success() {
                    if let Ok(body) = resp.json::<serde_json::Value>().await {
                        if body.get("disclaimer").is_some() {
                            eprintln!("Port {} occupied by existing Metascend backend, terminating...", port);
                            if let Err(e) = kill_process_on_port(port) {
                                eprintln!("Warning: failed to kill existing backend on port {}: {}", port, e);
                                continue;
                            }
                            sleep(Duration::from_millis(500)).await;
                            if is_port_free(port).await {
                                return Ok(port);
                            }
                        }
                    }
                }
            }
        }
        Err("No free port found in range 8727-8747".into())
    }

    fn spawn_python(port: u16) -> Result<(u32, ChildStdout, ChildStderr), String> {
        let root = project_root();
        let mut child = Command::new("uv")
            .args(["run", "python", "-m", "src.api_server"])
            .current_dir(&root)
            .env("METASCEND_PORT", port.to_string())
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::piped())
            .kill_on_drop(false)
            .spawn()
            .map_err(|e| format!("Failed to spawn backend: {}", e))?;

        let pid = child.id().ok_or("Failed to get child PID")?;
        let stdout = child.stdout.take().ok_or("Failed to take stdout")?;
        let stderr = child.stderr.take().ok_or("Failed to take stderr")?;

        mem::forget(child);
        Ok((pid, stdout, stderr))
    }

    async fn wait_for_ready(url: String) -> Result<(), String> {
        for _ in 0..40 {
            if let Ok(resp) = reqwest::get(format!("{}/health", url)).await {
                if resp.status().is_success() {
                    return Ok(());
                }
            }
            sleep(Duration::from_millis(250)).await;
        }
        Err("Python backend did not become ready".into())
    }
}

async fn health_check_loop(manager: Arc<SidecarManager>) {
    let mut failures = 0;
    loop {
        sleep(Duration::from_secs(5)).await;

        let url = manager.clone().backend_url().await;
        let healthy = match reqwest::get(format!("{}/health", url)).await {
            Ok(resp) => resp.status().is_success(),
            Err(_) => false,
        };

        if !healthy {
            failures += 1;
            eprintln!("Backend health check failed ({}/3)", failures);
            if failures >= 3 {
                let count = manager.restart_count.fetch_add(1, Ordering::SeqCst);
                if count >= 5 {
                    eprintln!("Backend restart limit exceeded; giving up.");
                    break;
                }
                eprintln!("Backend health check failed 3 times, restarting (attempt {})...", count + 1);
                if let Err(e) = SidecarManager::restart(manager.clone()).await {
                    eprintln!("Failed to restart backend: {}", e);
                }
                failures = 0;
            }
        } else {
            failures = 0;
        }
    }
}

async fn forward_stream<R>(reader: R, log_path: PathBuf, stream_name: &'static str)
where
    R: tokio::io::AsyncRead + Unpin + Send,
{
    let file = match OpenOptions::new()
        .create(true)
        .append(true)
        .open(&log_path)
        .await
    {
        Ok(f) => f,
        Err(e) => {
            eprintln!("Failed to open log file {:?}: {}", log_path, e);
            return;
        }
    };

    let mut writer = BufWriter::new(file);
    let mut lines = BufReader::new(reader).lines();

    while let Ok(Some(line)) = lines.next_line().await {
        let entry = format!("[{}] {}\n", stream_name, line);
        let _ = writer.write_all(entry.as_bytes()).await;
        let _ = writer.flush().await;
    }
}

async fn is_port_free(port: u16) -> bool {
    tokio::net::TcpListener::bind(format!("127.0.0.1:{}", port)).await.is_ok()
}

fn kill_process_on_port(port: u16) -> Result<(), String> {
    let output = std::process::Command::new("lsof")
        .args(["-ti", &format!("tcp:{}", port)])
        .output()
        .map_err(|e| e.to_string())?;

    let pid_str = String::from_utf8_lossy(&output.stdout);
    for pid in pid_str.lines() {
        if let Ok(pid) = pid.parse::<i32>() {
            let _ = send_signal(pid, nix::sys::signal::Signal::SIGTERM);
        }
    }
    Ok(())
}

fn is_process_alive(pid: i32) -> bool {
    #[cfg(unix)]
    {
        use nix::sys::signal;
        use nix::unistd::Pid;
        signal::kill(Pid::from_raw(pid), None).is_ok()
    }
    #[cfg(not(unix))]
    {
        let _ = pid;
        false
    }
}

fn send_signal(pid: i32, signal: nix::sys::signal::Signal) -> Result<(), String> {
    #[cfg(unix)]
    {
        use nix::sys::signal;
        use nix::unistd::Pid;
        signal::kill(Pid::from_raw(pid), signal).map_err(|e| e.to_string())
    }
    #[cfg(not(unix))]
    {
        let _ = (pid, signal);
        Err("Signals not supported on this platform".into())
    }
}

fn project_root() -> PathBuf {
    // Development builds launched via cargo: CARGO_MANIFEST_DIR is
    // frontend/src-tauri, so the project root is two levels up.
    if let Ok(manifest_dir) = std::env::var("CARGO_MANIFEST_DIR") {
        let path = PathBuf::from(manifest_dir);
        if let Some(root) = path.parent().and_then(|p| p.parent()) {
            return root.to_path_buf();
        }
    }

    // Release .app: search upward from the executable for project markers
    // (pyproject.toml or src/api_server.py). This lets the bundled app find
    // the Python project as long as the .app is placed inside the repo.
    if let Ok(exe) = std::env::current_exe() {
        let mut dir = exe.parent();
        while let Some(d) = dir {
            if d.join("pyproject.toml").exists() || d.join("src").join("api_server.py").exists() {
                return d.to_path_buf();
            }
            dir = d.parent();
        }
    }

    std::env::current_dir().unwrap_or_default()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Duration;
    use tokio::time::timeout;

    #[test]
    fn project_root_returns_valid_path() {
        let root = project_root();
        assert!(
            root.join("pyproject.toml").exists() || root.join("src").join("api_server.py").exists(),
            "project_root should point to the repository root: {:?}",
            root
        );
    }

    #[tokio::test]
    #[ignore = "spawns Python and loads models; run manually with cargo test -- --ignored"]
    async fn sidecar_manager_starts_python_backend() {
        let port = 8730;
        let log_dir = std::env::temp_dir().join(format!("metascend-test-logs-{}", port));
        let _ = std::fs::remove_dir_all(&log_dir);
        std::fs::create_dir_all(&log_dir).unwrap();
        let log_path = log_dir.join("backend.log");

        let manager = SidecarManager::new(port, log_path);
        SidecarManager::start(manager.clone()).await.expect("start failed");

        let url = manager.clone().backend_url().await;
        let health = timeout(Duration::from_secs(60), async {
            loop {
                if let Ok(resp) = reqwest::get(format!("{}/health", url)).await {
                    if resp.status().is_success() {
                        break;
                    }
                }
                sleep(Duration::from_millis(250)).await;
            }
        })
        .await;
        assert!(health.is_ok(), "backend did not become healthy within 60s");

        manager.stop().await.expect("stop failed");
    }
}
