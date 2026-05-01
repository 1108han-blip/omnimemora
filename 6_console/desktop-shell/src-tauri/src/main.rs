use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::env;
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::thread;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

const APP_VERSION: &str = "1.0.0-beta.2";
const SUPPORT_EMAIL: &str = "support@doloclaw.com";
const RUNTIME_PORT: u16 = 8765;
const ADAPTER_PORT: u16 = 18011;
const UI_PORT: u16 = 5173;
const INTERNAL_TOKEN: &str = "omnimemora-desktop-beta-local";

#[derive(Serialize, Deserialize, Clone)]
struct ManagedProcess {
    name: String,
    pid: u32,
    port: u16,
    command: String,
    started_at: u64,
}

#[derive(Serialize, Deserialize, Default, Clone)]
struct PersistedDesktopState {
    processes: Vec<ManagedProcess>,
}

#[derive(Serialize, Clone)]
struct ServiceStatus {
    name: &'static str,
    port: u16,
    state: String,
    url: String,
    detail: String,
    managed_by_desktop: bool,
    pid: Option<u32>,
}

#[derive(Serialize, Clone)]
struct UpdateLayerStatus {
    layer: &'static str,
    current_version: String,
    available_version: Option<String>,
    status: String,
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

fn home_dir() -> PathBuf {
    env::var("HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("."))
}

fn app_root() -> PathBuf {
    env::var("OMNIMEMORA_APP_ROOT")
        .map(PathBuf::from)
        .unwrap_or_else(|_| home_dir().join(".omnimemora").join("app"))
}

fn current_dir() -> PathBuf {
    app_root().join("current")
}

fn previous_dir() -> PathBuf {
    app_root().join("previous")
}

fn downloads_dir() -> PathBuf {
    app_root().join("downloads")
}

fn rollback_dir() -> PathBuf {
    app_root().join("rollback")
}

fn logs_dir() -> PathBuf {
    home_dir().join(".omnimemora").join("logs")
}

fn state_path() -> PathBuf {
    current_dir().join("desktop_state.json")
}

fn repo_root() -> PathBuf {
    env::var("OMNIMEMORA_REPO_ROOT")
        .map(PathBuf::from)
        .unwrap_or_else(|_| {
            PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .parent()
                .and_then(Path::parent)
                .and_then(Path::parent)
                .map(Path::to_path_buf)
                .unwrap_or_else(|| PathBuf::from("."))
        })
}

fn unix_now() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}

fn ensure_dirs() -> Result<(), String> {
    for dir in [
        current_dir(),
        previous_dir(),
        downloads_dir(),
        rollback_dir(),
        logs_dir(),
    ] {
        fs::create_dir_all(&dir).map_err(|err| format!("无法创建目录 {}: {err}", dir.display()))?;
    }
    Ok(())
}

fn read_state() -> PersistedDesktopState {
    let path = state_path();
    let Ok(raw) = fs::read_to_string(path) else {
        return PersistedDesktopState::default();
    };
    serde_json::from_str(&raw).unwrap_or_default()
}

fn write_state(state: &PersistedDesktopState) -> Result<(), String> {
    ensure_dirs()?;
    let raw =
        serde_json::to_string_pretty(state).map_err(|err| format!("无法序列化桌面状态: {err}"))?;
    fs::write(state_path(), raw).map_err(|err| format!("无法写入桌面状态: {err}"))
}

fn managed_process<'a>(state: &'a PersistedDesktopState, name: &str) -> Option<&'a ManagedProcess> {
    state.processes.iter().find(|proc| proc.name == name)
}

fn process_alive(pid: u32) -> bool {
    Command::new("kill")
        .arg("-0")
        .arg(pid.to_string())
        .status()
        .map(|status| status.success())
        .unwrap_or(false)
}

fn kill_process(pid: u32) -> bool {
    Command::new("kill")
        .arg(pid.to_string())
        .status()
        .map(|status| status.success())
        .unwrap_or(false)
}

fn prune_dead_processes(mut state: PersistedDesktopState) -> PersistedDesktopState {
    state.processes.retain(|proc| process_alive(proc.pid));
    let _ = write_state(&state);
    state
}

fn http_probe(port: u16, path: &str, expect_json_status: Option<&str>) -> Result<String, String> {
    let addr = SocketAddr::from(([127, 0, 0, 1], port));
    let mut stream = TcpStream::connect_timeout(&addr, Duration::from_millis(350))
        .map_err(|err| format!("端口 {port} 不可连接: {err}"))?;
    stream
        .set_read_timeout(Some(Duration::from_millis(900)))
        .ok();
    let req = format!("GET {path} HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n");
    stream
        .write_all(req.as_bytes())
        .map_err(|err| format!("端口 {port} 请求失败: {err}"))?;
    let mut response = String::new();
    stream
        .read_to_string(&mut response)
        .map_err(|err| format!("端口 {port} 响应读取失败: {err}"))?;
    if !response.starts_with("HTTP/1.1 200") && !response.starts_with("HTTP/1.0 200") {
        return Err(format!("端口 {port} HTTP 非 200"));
    }
    if let Some(expected) = expect_json_status {
        if !response.contains(expected) {
            return Err(format!("端口 {port} 响应不是预期服务"));
        }
    }
    Ok(format!("端口 {port} 健康。"))
}

fn service_probe(
    name: &'static str,
    port: u16,
    path: &'static str,
    expected: Option<&'static str>,
    state: &PersistedDesktopState,
) -> ServiceStatus {
    let managed = managed_process(state, name).filter(|proc| process_alive(proc.pid));
    let managed_by_desktop = managed.is_some();
    let pid = managed.map(|proc| proc.pid);
    match http_probe(port, path, expected) {
        Ok(detail) => ServiceStatus {
            name,
            port,
            state: "healthy".to_string(),
            url: format!("http://127.0.0.1:{port}{path}"),
            detail: if managed_by_desktop {
                format!("{detail} 由桌面 App 管理。")
            } else {
                format!("{detail} 当前进程不是桌面 App 启动的。")
            },
            managed_by_desktop,
            pid,
        },
        Err(http_err) => {
            let tcp_open = TcpStream::connect_timeout(
                &SocketAddr::from(([127, 0, 0, 1], port)),
                Duration::from_millis(200),
            )
            .is_ok();
            ServiceStatus {
                name,
                port,
                state: if tcp_open {
                    "blocked".to_string()
                } else {
                    "unreachable".to_string()
                },
                url: format!("http://127.0.0.1:{port}{path}"),
                detail: if tcp_open {
                    format!("端口 {port} 被占用，但不是预期的 OmniMemora 服务：{http_err}")
                } else {
                    http_err
                },
                managed_by_desktop,
                pid,
            }
        }
    }
}

fn release_manifest_from_disk() -> Option<Value> {
    let candidates = [
        current_dir().join("manifest.json"),
        repo_root().join("4_core/local-runtime/release/1.0.0-beta.2/latest.json"),
        repo_root().join("4_core/local-runtime/release/1.0.0-beta.2/1.0.0-beta.2.json"),
    ];
    for path in candidates {
        if let Ok(raw) = fs::read_to_string(path) {
            if let Ok(value) = serde_json::from_str::<Value>(&raw) {
                return Some(value);
            }
        }
    }
    None
}

fn update_statuses() -> Vec<UpdateLayerStatus> {
    let manifest = release_manifest_from_disk();
    let available = manifest
        .as_ref()
        .and_then(|value| value.get("version"))
        .and_then(Value::as_str)
        .map(ToString::to_string);
    let local_status = match &available {
        Some(version) if version != APP_VERSION => "available",
        Some(_) => "current",
        None => "not_checked",
    };
    vec![
        UpdateLayerStatus {
            layer: "desktop_shell",
            current_version: APP_VERSION.to_string(),
            available_version: available.clone(),
            status: "current".to_string(),
            detail: "桌面壳本体在本 beta 中通过新版安装器更新，不做静默自更新。".to_string(),
        },
        UpdateLayerStatus {
            layer: "local_components",
            current_version: APP_VERSION.to_string(),
            available_version: available,
            status: local_status.to_string(),
            detail: "本地组件更新走 release manifest、SHA256 校验和回滚流程。".to_string(),
        },
        UpdateLayerStatus {
            layer: "cloud_policy",
            current_version: "local-active".to_string(),
            available_version: None,
            status: "not_checked".to_string(),
            detail: "云端策略保持 candidate-only；不会自动覆盖本地 active policy。".to_string(),
        },
    ]
}

fn desktop_status() -> DesktopStatus {
    let state = prune_dead_processes(read_state());
    DesktopStatus {
        app_version: APP_VERSION,
        data_dir: current_dir().display().to_string(),
        services: vec![
            service_probe(
                "runtime",
                RUNTIME_PORT,
                "/health",
                Some("\"status\":"),
                &state,
            ),
            service_probe(
                "adapter",
                ADAPTER_PORT,
                "/health",
                Some("\"status\":\"healthy\""),
                &state,
            ),
            service_probe("ui", UI_PORT, "/", None, &state),
        ],
        updates: update_statuses(),
        feedback_email: SUPPORT_EMAIL,
    }
}

fn command_result(ok: bool, message: impl Into<String>) -> DesktopCommandResult {
    DesktopCommandResult {
        ok,
        message: message.into(),
        status: desktop_status(),
    }
}

fn first_existing(paths: &[PathBuf]) -> Option<PathBuf> {
    paths.iter().find(|path| path.exists()).cloned()
}

fn python_bin() -> Option<String> {
    env::var("PYTHON_BIN").ok().or_else(|| {
        Command::new("which")
            .arg("python3")
            .output()
            .ok()
            .and_then(|output| {
                if output.status.success() {
                    Some(String::from_utf8_lossy(&output.stdout).trim().to_string())
                } else {
                    None
                }
            })
    })
}

fn log_file(name: &str, stream: &str) -> Result<File, String> {
    ensure_dirs()?;
    OpenOptions::new()
        .create(true)
        .append(true)
        .open(logs_dir().join(format!("desktop-{name}-{stream}.log")))
        .map_err(|err| format!("无法打开日志文件: {err}"))
}

fn spawn_service(
    name: &str,
    mut command: Command,
    port: u16,
    command_label: String,
) -> Result<ManagedProcess, String> {
    command.stdout(Stdio::from(log_file(name, "stdout")?));
    command.stderr(Stdio::from(log_file(name, "stderr")?));
    let child = command
        .spawn()
        .map_err(|err| format!("无法启动 {name}: {err}"))?;
    Ok(ManagedProcess {
        name: name.to_string(),
        pid: child.id(),
        port,
        command: command_label,
        started_at: unix_now(),
    })
}

fn start_runtime() -> Result<Option<ManagedProcess>, String> {
    if http_probe(RUNTIME_PORT, "/health", Some("\"status\":")).is_ok() {
        return Ok(None);
    }
    let root = repo_root();
    let binary = first_existing(&[
        env::var("OMNIMEMORA_RUNTIME_BIN")
            .map(PathBuf::from)
            .unwrap_or_default(),
        current_dir().join("bin/omnimemora"),
        current_dir().join("omnimemora"),
        root.join("4_core/local-runtime/release/1.0.0-beta.2/omnimemora-darwin-arm64/omnimemora"),
        root.join("tools/omnimemora-runtime"),
    ])
    .ok_or_else(|| "找不到 runtime binary。请先生成或安装 runtime 组件。".to_string())?;
    let agent_modes = root.join("5_connectors/adapter/config/agent_modes.json");
    let mut cmd = Command::new(&binary);
    cmd.arg("serve")
        .env("OMNIMEMORA_RUNTIME_PORT", RUNTIME_PORT.to_string())
        .env("OMNIMEMORA_ADAPTER_PORT", ADAPTER_PORT.to_string())
        .env("OMNIMEMORA_AGENT_MODES_PATH", agent_modes);
    spawn_service(
        "runtime",
        cmd,
        RUNTIME_PORT,
        format!("{} serve", binary.display()),
    )
    .map(Some)
}

fn start_adapter() -> Result<Option<ManagedProcess>, String> {
    if http_probe(ADAPTER_PORT, "/health", Some("\"status\":\"healthy\"")).is_ok() {
        return Ok(None);
    }
    let python = python_bin().ok_or_else(|| "找不到 python3，无法启动 adapter。".to_string())?;
    let root = repo_root();
    let launcher = first_existing(&[
        current_dir().join("tools/_run_adapter.py"),
        root.join("tools/_run_adapter.py"),
    ])
    .ok_or_else(|| "找不到 adapter launcher。".to_string())?;
    let agent_modes = root.join("5_connectors/adapter/config/agent_modes.json");
    let mut cmd = Command::new(&python);
    cmd.arg(&launcher)
        .current_dir(&root)
        .env("PORT", ADAPTER_PORT.to_string())
        .env(
            "MEMORY_BACKEND_URL",
            format!("http://127.0.0.1:{RUNTIME_PORT}"),
        )
        .env("OMNIMEMORA_INTERNAL_API_TOKEN", INTERNAL_TOKEN)
        .env("OMNIMEMORA_AGENT_MODES_PATH", agent_modes);
    spawn_service(
        "adapter",
        cmd,
        ADAPTER_PORT,
        format!("{python} {}", launcher.display()),
    )
    .map(Some)
}

fn start_ui() -> Result<Option<ManagedProcess>, String> {
    if http_probe(UI_PORT, "/", None).is_ok() {
        return Ok(None);
    }
    let python =
        python_bin().ok_or_else(|| "找不到 python3，无法启动本地 GUI 静态服务。".to_string())?;
    let root = repo_root();
    let dist = first_existing(&[
        current_dir().join("ui/dist"),
        root.join("6_console/demo-dashboard/dist"),
    ])
    .ok_or_else(|| "找不到 GUI dist。请先构建 6_console/demo-dashboard。".to_string())?;
    let mut cmd = Command::new(&python);
    cmd.args([
        "-m",
        "http.server",
        &UI_PORT.to_string(),
        "--bind",
        "127.0.0.1",
        "--directory",
    ])
    .arg(&dist);
    spawn_service(
        "ui",
        cmd,
        UI_PORT,
        format!(
            "{python} -m http.server {UI_PORT} --directory {}",
            dist.display()
        ),
    )
    .map(Some)
}

fn wait_for_service(port: u16, path: &str, expected: Option<&str>) -> bool {
    for _ in 0..30 {
        if http_probe(port, path, expected).is_ok() {
            return true;
        }
        thread::sleep(Duration::from_millis(250));
    }
    false
}

fn start_all_services() -> Result<String, String> {
    ensure_dirs()?;
    let mut state = prune_dead_processes(read_state());
    let mut started: Vec<ManagedProcess> = Vec::new();

    if let Some(proc) = start_runtime()? {
        started.push(proc);
    }
    if !wait_for_service(RUNTIME_PORT, "/health", Some("\"status\":")) {
        return Err("runtime 启动后健康检查未通过。".to_string());
    }

    if let Some(proc) = start_adapter()? {
        started.push(proc);
    }
    if !wait_for_service(ADAPTER_PORT, "/health", Some("\"status\":\"healthy\"")) {
        return Err("adapter 启动后健康检查未通过。".to_string());
    }

    if let Some(proc) = start_ui()? {
        started.push(proc);
    }
    if !wait_for_service(UI_PORT, "/", None) {
        return Err("GUI 启动后健康检查未通过。".to_string());
    }

    for proc in started.iter() {
        state
            .processes
            .retain(|existing| existing.name != proc.name);
        state.processes.push(proc.clone());
    }
    write_state(&state)?;
    if started.is_empty() {
        Ok("所有服务已经健康；桌面 App 未接管外部进程。".to_string())
    } else {
        Ok(format!("已启动 {} 个桌面管理服务。", started.len()))
    }
}

fn stop_all_services() -> Result<String, String> {
    let mut state = prune_dead_processes(read_state());
    let count = state.processes.len();
    for proc in state.processes.iter() {
        let _ = kill_process(proc.pid);
    }
    state.processes.clear();
    write_state(&state)?;
    Ok(format!(
        "已请求停止 {count} 个桌面管理服务；未知外部进程未被停止。"
    ))
}

#[tauri::command]
fn get_desktop_status() -> DesktopStatus {
    desktop_status()
}

#[tauri::command]
fn start_services() -> DesktopCommandResult {
    match start_all_services() {
        Ok(message) => command_result(true, message),
        Err(err) => command_result(false, err),
    }
}

#[tauri::command]
fn stop_services() -> DesktopCommandResult {
    match stop_all_services() {
        Ok(message) => command_result(true, message),
        Err(err) => command_result(false, err),
    }
}

#[tauri::command]
fn restart_services() -> DesktopCommandResult {
    if let Err(err) = stop_all_services() {
        return command_result(false, err);
    }
    thread::sleep(Duration::from_millis(500));
    match start_all_services() {
        Ok(message) => command_result(true, format!("重启完成：{message}")),
        Err(err) => command_result(false, err),
    }
}

#[tauri::command]
fn check_for_updates() -> DesktopCommandResult {
    command_result(
        true,
        "已检查本地 release manifest。线上 manifest 拉取将在下一阶段接入。",
    )
}

#[tauri::command]
fn install_update() -> DesktopCommandResult {
    command_result(
        false,
        "组件安装更新将在 manifest 下载、SHA256 校验和回滚流程完成后启用。",
    )
}

#[tauri::command]
fn rollback() -> DesktopCommandResult {
    command_result(
        false,
        "当前没有已安装的组件更新可回滚；rollback 将在组件更新阶段启用。",
    )
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
