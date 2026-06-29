use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::Duration;

use tauri::{Manager, RunEvent};

struct SidecarHandle(Mutex<Option<Child>>);

const SIDECAR_HEALTH_URL: &str = "http://127.0.0.1:8765/healthz";
const SIDECAR_PORT: &str = "8765";

/// Kill any process holding the sidecar port.
///
/// Without this, a sidecar orphaned by a previous SIGKILL of the Tauri parent
/// would keep serving old code on 8765, the new sidecar would silently fail
/// to bind, and the UI would talk to stale routes.
fn free_sidecar_port() {
    if let Ok(output) = Command::new("lsof").args(["-ti", &format!(":{SIDECAR_PORT}")]).output() {
        for pid in String::from_utf8_lossy(&output.stdout)
            .split_whitespace()
            .filter(|s| !s.is_empty())
        {
            eprintln!("sidecar: killing stale process {pid} on port {SIDECAR_PORT}");
            let _ = Command::new("kill").arg("-9").arg(pid).status();
        }
        // Give the kernel a beat to release the bind.
        std::thread::sleep(Duration::from_millis(200));
    }
}

fn spawn_sidecar() -> std::io::Result<Child> {
    free_sidecar_port();

    let cwd = std::env::current_dir()?;
    let project_root = if cwd.ends_with("src-tauri") {
        cwd.parent().unwrap().to_path_buf()
    } else {
        cwd
    };

    Command::new("uv")
        .args(["run", "python", "-m", "sidecar.main"])
        .current_dir(&project_root)
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .spawn()
}

async fn wait_for_sidecar(timeout: Duration) -> bool {
    let client = reqwest::Client::builder()
        .timeout(Duration::from_millis(500))
        .build()
        .unwrap();
    let deadline = std::time::Instant::now() + timeout;
    while std::time::Instant::now() < deadline {
        if client.get(SIDECAR_HEALTH_URL).send().await.is_ok() {
            return true;
        }
        tokio::time::sleep(Duration::from_millis(250)).await;
    }
    false
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let child = spawn_sidecar().ok();

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(SidecarHandle(Mutex::new(child)))
        .setup(|app| {
            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                let ready = wait_for_sidecar(Duration::from_secs(30)).await;
                if !ready {
                    eprintln!("sidecar did not become ready within 30s, UI will still load");
                }
                if let Some(window) = handle.get_webview_window("main") {
                    let _ = window.show();
                }
            });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            if let RunEvent::ExitRequested { .. } = event {
                if let Some(state) = app_handle.try_state::<SidecarHandle>() {
                    if let Ok(mut guard) = state.0.lock() {
                        if let Some(mut child) = guard.take() {
                            let _ = child.kill();
                            let _ = child.wait();
                        }
                    }
                }
            }
        });
}
