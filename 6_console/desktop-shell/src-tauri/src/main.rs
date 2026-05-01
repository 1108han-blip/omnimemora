use serde::Serialize;
use std::env;
use std::net::{SocketAddr, TcpStream};
use std::path::PathBuf;
use std::time::Duration;

const APP_VERSION: &str = "1.0.0-beta.2";
const SUPPORT_EMAIL: &str = "support@doloclaw.com";

#[derive(Serialize, Clone)]
struct ServiceStatus {
    name: &'static str,
    port: u16,
    state: &'static str,
    url: String,
    detail: String,
}

#[derive(Serialize, Clone)]
struct UpdateLayerStatus {
    layer: &'static str,
    current_version: &'static str,
    available_version: Option<String>,
    status: &'static str,
    detail: String,
}

#[derive(Serialize, Clone)]
struct DesktopStatus {
    app_version: &'static str,
    data_dir: String,
    services: Vec<ServiceStatus>,
    updates: Vec<UpdateLayerStatus>,
    feedback_email: &'static str,
}

#[derive(Serialize)]
struct DesktopCommandResult {
    ok: bool,
    message: String,
    status: DesktopStatus,
}

fn omnimemora_data_dir() -> String {
    env::var("OMNIMEMORA_APP_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|_| {
            let home = env::var("HOME").unwrap_or_else(|_| ".".to_string());
            PathBuf::from(home).join(".omnimemora").join("app").join("current")
        })
        .display()
        .to_string()
}

fn tcp_state(port: u16) -> (&'static str, String) {
    let addr = SocketAddr::from(([127, 0, 0, 1], port));
    match TcpStream::connect_timeout(&addr, Duration::from_millis(250)) {
        Ok(_) => ("healthy", format!("Port {port} is accepting local connections.")),
        Err(err) => ("unreachable", format!("Port {port} is not reachable: {err}")),
    }
}

fn service(name: &'static str, port: u16, path: &'static str) -> ServiceStatus {
    let (state, detail) = tcp_state(port);
    ServiceStatus {
        name,
        port,
        state,
        url: format!("http://127.0.0.1:{port}{path}"),
        detail,
    }
}

fn desktop_status() -> DesktopStatus {
    DesktopStatus {
        app_version: APP_VERSION,
        data_dir: omnimemora_data_dir(),
        services: vec![
            service("runtime", 8765, "/health"),
            service("adapter", 18011, "/health"),
            service("ui", 5173, "/"),
        ],
        updates: vec![
            UpdateLayerStatus {
                layer: "desktop_shell",
                current_version: APP_VERSION,
                available_version: None,
                status: "not_checked",
                detail: "Desktop shell updates are installer-based in this beta.".to_string(),
            },
            UpdateLayerStatus {
                layer: "local_components",
                current_version: APP_VERSION,
                available_version: None,
                status: "not_checked",
                detail: "Local component updates will use the release manifest and SHA256 verification.".to_string(),
            },
            UpdateLayerStatus {
                layer: "cloud_policy",
                current_version: "local-active",
                available_version: None,
                status: "not_checked",
                detail: "Cloud policy candidates are visible but never auto-promoted.".to_string(),
            },
        ],
        feedback_email: SUPPORT_EMAIL,
    }
}

fn foundation_only(command: &str) -> DesktopCommandResult {
    DesktopCommandResult {
        ok: false,
        message: format!("{command} is defined in the desktop shell contract; service mutation is scheduled for the next batch."),
        status: desktop_status(),
    }
}

#[tauri::command]
fn get_desktop_status() -> DesktopStatus {
    desktop_status()
}

#[tauri::command]
fn start_services() -> DesktopCommandResult {
    foundation_only("start_services")
}

#[tauri::command]
fn stop_services() -> DesktopCommandResult {
    foundation_only("stop_services")
}

#[tauri::command]
fn restart_services() -> DesktopCommandResult {
    foundation_only("restart_services")
}

#[tauri::command]
fn check_for_updates() -> DesktopCommandResult {
    foundation_only("check_for_updates")
}

#[tauri::command]
fn install_update() -> DesktopCommandResult {
    foundation_only("install_update")
}

#[tauri::command]
fn rollback() -> DesktopCommandResult {
    foundation_only("rollback")
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            get_desktop_status,
            start_services,
            stop_services,
            restart_services,
            check_for_updates,
            install_update,
            rollback
        ])
        .run(tauri::generate_context!())
        .expect("error while running OmniMemora desktop shell");
}
