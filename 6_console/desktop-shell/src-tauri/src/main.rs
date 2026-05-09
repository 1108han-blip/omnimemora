use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::env;
use std::fs::{self, File, OpenOptions};
use std::io::{ErrorKind, Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::thread;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tauri::menu::{Menu, MenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Manager, RunEvent, WebviewUrl, WebviewWindowBuilder, WindowEvent};
use tauri_plugin_updater::UpdaterExt;

const APP_VERSION: &str = "1.0.0-beta.12";
const SUPPORT_EMAIL: &str = "support@doloclaw.com";
const RUNTIME_PORT: u16 = 8765;
const ADAPTER_PORT: u16 = 18011;
const UI_PORT: u16 = 5173;
const INTERNAL_TOKEN: &str = "omnimemora-desktop-beta-local";
const LATEST_MANIFEST_URL: &str = "https://doloclaw.com/releases/latest.json";
const CLOUD_POLICY_CANDIDATE_URL: &str =
    "https://doloclaw.com/api/control/recommendation/candidates/latest";
const TRAY_SHOW_ID: &str = "show";
const TRAY_QUIT_ID: &str = "quit";

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

#[derive(Serialize, Clone)]
struct AgentStatus {
    id: &'static str,
    name: &'static str,
    state: String,
    installed: bool,
    running: bool,
    attached: bool,
    supported: bool,
    experimental: bool,
    detail: String,
    config_path: String,
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

fn service_current_dir() -> PathBuf {
    home_dir()
        .join(".omnimemora")
        .join("service")
        .join("current")
}

fn component_dir() -> PathBuf {
    let app_current = current_dir();
    if app_current.join("manifest.json").exists()
        || app_current.join("tools/_run_adapter.py").exists()
        || app_current.join("bin/omnimemora").exists()
    {
        app_current
    } else {
        service_current_dir()
    }
}

fn current_agent_modes_path() -> PathBuf {
    component_dir().join("5_connectors/adapter/config/agent_modes.json")
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

fn downloaded_manifest_path() -> PathBuf {
    downloads_dir().join("latest.json")
}

fn downloaded_candidate_path() -> PathBuf {
    downloads_dir().join("cloud_policy_candidate.json")
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
    let mut bytes = Vec::new();
    let mut buffer = [0_u8; 4096];
    loop {
        match stream.read(&mut buffer) {
            Ok(0) => break,
            Ok(n) => bytes.extend_from_slice(&buffer[..n]),
            Err(err)
                if matches!(
                    err.kind(),
                    ErrorKind::WouldBlock | ErrorKind::TimedOut | ErrorKind::Interrupted
                ) && !bytes.is_empty() =>
            {
                break;
            }
            Err(err) => return Err(format!("端口 {port} 响应读取失败: {err}")),
        }
    }
    let response = String::from_utf8_lossy(&bytes);
    if !response.starts_with("HTTP/1.1 200") && !response.starts_with("HTTP/1.0 200") {
        return Err(format!("端口 {port} HTTP 非 200"));
    }
    if let Some(expected) = expect_json_status {
        let compact = response.split_whitespace().collect::<String>();
        if !response.contains(expected) && !compact.contains(expected) {
            return Err(format!("端口 {port} 响应不是预期服务"));
        }
    }
    Ok("本地服务健康。".to_string())
}

fn curl_probe(port: u16, path: &str, expect_json_status: Option<&str>) -> Result<String, String> {
    let output = Command::new("curl")
        .args([
            "-fsS",
            "--connect-timeout",
            "1",
            "--max-time",
            "2",
            &format!("http://127.0.0.1:{port}{path}"),
        ])
        .output()
        .map_err(|err| format!("端口 {port} curl 探测失败: {err}"))?;
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("端口 {port} curl 非 200: {}", stderr.trim()));
    }
    if let Some(expected) = expect_json_status {
        let body = String::from_utf8_lossy(&output.stdout);
        let compact = body.split_whitespace().collect::<String>();
        if !body.contains(expected) && !compact.contains(expected) {
            return Err(format!("端口 {port} curl 响应不是预期服务"));
        }
    }
    Ok("本地服务健康。".to_string())
}

fn port_owner_pid(port: u16) -> Option<u32> {
    let output = Command::new("lsof")
        .args(["-nP", "-iTCP", &format!(":{port}"), "-sTCP:LISTEN", "-t"])
        .output()
        .ok()?;
    if !output.status.success() {
        return None;
    }
    String::from_utf8_lossy(&output.stdout)
        .lines()
        .find_map(|line| line.trim().parse::<u32>().ok())
}

fn process_command(pid: u32) -> Option<String> {
    let output = Command::new("ps")
        .args(["-p", &pid.to_string(), "-o", "command="])
        .output()
        .ok()?;
    if !output.status.success() {
        return None;
    }
    let command = String::from_utf8_lossy(&output.stdout).trim().to_string();
    if command.is_empty() {
        None
    } else {
        Some(command)
    }
}

fn known_omnimemora_service(name: &str, command: &str) -> bool {
    match name {
        "runtime" => command.contains("omnimemora-runtime") && command.contains("serve"),
        "adapter" => command.contains("_run_adapter.py"),
        "ui" => command.contains("http.server") && command.contains("5173"),
        _ => false,
    }
}

fn service_probe(
    name: &'static str,
    port: u16,
    path: &'static str,
    expected: Option<&'static str>,
    state: &PersistedDesktopState,
) -> ServiceStatus {
    let managed = managed_process(state, name).filter(|proc| process_alive(proc.pid));
    let port_pid = port_owner_pid(port);
    let port_command = port_pid.and_then(process_command);
    let known_product_process = port_command
        .as_deref()
        .map(|command| known_omnimemora_service(name, command))
        .unwrap_or(false);
    let managed_by_desktop = managed.is_some();
    let pid = managed.map(|proc| proc.pid).or(port_pid);
    match http_probe(port, path, expected).or_else(|_| curl_probe(port, path, expected)) {
        Ok(detail) => ServiceStatus {
            name,
            port,
            state: "healthy".to_string(),
            url: format!("http://127.0.0.1:{port}{path}"),
            detail: if managed_by_desktop {
                format!("{detail} 由桌面 App 管理。")
            } else if known_product_process {
                format!("{detail} 由 OmniMemora 产品进程提供。")
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
                    if known_product_process {
                        "unreachable".to_string()
                    } else {
                        "blocked".to_string()
                    }
                } else {
                    "unreachable".to_string()
                },
                url: format!("http://127.0.0.1:{port}{path}"),
                detail: if tcp_open {
                    if known_product_process {
                        "OmniMemora 产品进程已占用入口，但健康检查未通过；可以点击 Restart 修复连接。"
                            .to_string()
                    } else {
                        "本地服务入口被其他进程占用；桌面 App 不会强行关闭未知进程。".to_string()
                    }
                } else {
                    let _ = http_err;
                    "服务暂不可用；可以点击 Start 由桌面 App 启动。".to_string()
                },
                managed_by_desktop,
                pid,
            }
        }
    }
}

fn release_manifest_from_disk() -> Option<Value> {
    let candidates = [
        downloaded_manifest_path(),
        current_dir().join("manifest.json"),
        repo_root().join("4_core/local-runtime/release/1.0.0-beta.12/latest.json"),
        repo_root().join("4_core/local-runtime/release/1.0.0-beta.12/1.0.0-beta.12.json"),
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

fn installed_component_version() -> Option<String> {
    fs::read_to_string(current_dir().join("manifest.json"))
        .ok()
        .and_then(|raw| serde_json::from_str::<Value>(&raw).ok())
        .and_then(|value| {
            value
                .get("version")
                .and_then(Value::as_str)
                .map(ToString::to_string)
        })
}

fn version_number_parts(version: &str) -> Vec<u64> {
    let mut parts = Vec::new();
    let mut current = String::new();
    for ch in version.chars() {
        if ch.is_ascii_digit() {
            current.push(ch);
        } else if !current.is_empty() {
            if let Ok(value) = current.parse::<u64>() {
                parts.push(value);
            }
            current.clear();
        }
    }
    if !current.is_empty() {
        if let Ok(value) = current.parse::<u64>() {
            parts.push(value);
        }
    }
    parts
}

fn version_is_newer(available: &str, current: &str) -> bool {
    let available_parts = version_number_parts(available);
    let current_parts = version_number_parts(current);
    for idx in 0..available_parts.len().max(current_parts.len()) {
        let available_part = *available_parts.get(idx).unwrap_or(&0);
        let current_part = *current_parts.get(idx).unwrap_or(&0);
        if available_part > current_part {
            return true;
        }
        if available_part < current_part {
            return false;
        }
    }
    false
}

#[cfg(test)]
mod tests {
    use super::version_is_newer;

    #[test]
    fn version_comparison_handles_beta_patch_order() {
        assert!(version_is_newer("1.0.0-beta.12", "1.0.0-beta.10"));
        assert!(!version_is_newer("1.0.0-beta.10", "1.0.0-beta.12"));
        assert!(!version_is_newer("1.0.0-beta.12", "1.0.0-beta.12"));
    }
}

fn candidate_policy_status() -> (String, Option<String>, String) {
    let Ok(raw) = fs::read_to_string(downloaded_candidate_path()) else {
        return (
            "not_checked".to_string(),
            None,
            "云端策略保持 candidate-only；不会自动覆盖本地 active policy。".to_string(),
        );
    };
    let Ok(value) = serde_json::from_str::<Value>(&raw) else {
        return (
            "blocked".to_string(),
            None,
            "云端策略候选响应不是有效 JSON；不会启用。".to_string(),
        );
    };
    let version = value
        .get("policy_version")
        .or_else(|| value.get("version"))
        .and_then(Value::as_str)
        .map(ToString::to_string);
    let status = value
        .get("status")
        .and_then(Value::as_str)
        .unwrap_or("candidate");
    (
        if version.is_some() {
            "available".to_string()
        } else {
            "not_checked".to_string()
        },
        version,
        format!("云端策略候选状态：{status}。只显示候选，不自动启用。"),
    )
}

fn update_statuses() -> Vec<UpdateLayerStatus> {
    let manifest = release_manifest_from_disk();
    let available = manifest
        .as_ref()
        .and_then(|value| value.get("version"))
        .and_then(Value::as_str)
        .map(ToString::to_string);
    let installed = installed_component_version();
    let current_components = installed.clone().unwrap_or_else(|| APP_VERSION.to_string());
    let local_status = match &available {
        Some(_) if installed.is_none() => "available",
        Some(version) if version_is_newer(version, &current_components) => "available",
        Some(_) => "current",
        None => "not_checked",
    };
    let desktop_status = match &available {
        Some(version) if version_is_newer(version, APP_VERSION) => "available",
        Some(_) => "current",
        None => "not_checked",
    };
    let (cloud_status, cloud_version, cloud_detail) = candidate_policy_status();
    vec![
        UpdateLayerStatus {
            layer: "desktop_shell",
            current_version: APP_VERSION.to_string(),
            available_version: available.clone(),
            status: desktop_status.to_string(),
            detail: "桌面壳使用 Tauri updater 检查、签名校验、下载并安装桌面 App 更新。"
                .to_string(),
        },
        UpdateLayerStatus {
            layer: "local_components",
            current_version: current_components,
            available_version: available,
            status: local_status.to_string(),
            detail: "本地组件更新走 release manifest、SHA256 校验和回滚流程。".to_string(),
        },
        UpdateLayerStatus {
            layer: "cloud_policy",
            current_version: "local-active".to_string(),
            available_version: cloud_version,
            status: cloud_status,
            detail: cloud_detail,
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

fn runtime_binary() -> Option<PathBuf> {
    let root = repo_root();
    let component = component_dir();
    let service_current = service_current_dir();
    first_existing(&[
        env::var("OMNIMEMORA_RUNTIME_BIN")
            .map(PathBuf::from)
            .unwrap_or_default(),
        component.join("bin/omnimemora"),
        component.join("omnimemora"),
        service_current.join("tools/omnimemora-runtime"),
        service_current.join("bin/omnimemora"),
        root.join("4_core/local-runtime/release/1.0.0-beta.12/omnimemora-darwin-arm64/omnimemora"),
        root.join(
            "4_core/local-runtime/release/1.0.0-beta.12/omnimemora-darwin-arm64/bin/omnimemora",
        ),
        root.join("tools/omnimemora-runtime"),
    ])
}

fn python_can_import(python: &str, modules: &[&str]) -> bool {
    let script = if modules.is_empty() {
        "import sys".to_string()
    } else {
        format!(
            "import importlib.util, sys\nmods = {:?}\nsys.exit(0 if all(importlib.util.find_spec(m) for m in mods) else 1)",
            modules
        )
    };
    Command::new(python)
        .arg("-c")
        .arg(script)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|status| status.success())
        .unwrap_or(false)
}

fn python_bin_with_modules(modules: &[&str]) -> Option<String> {
    let mut candidates = Vec::new();
    if let Ok(configured) = env::var("PYTHON_BIN") {
        candidates.push(configured);
    }
    candidates.extend(
        [
            "/usr/bin/python3",
            "/opt/homebrew/bin/python3",
            "/usr/local/bin/python3",
            "python3",
            "python",
        ]
        .iter()
        .map(|item| item.to_string()),
    );

    let mut deduped = Vec::new();
    for candidate in candidates {
        if !candidate.trim().is_empty() && !deduped.contains(&candidate) {
            deduped.push(candidate);
        }
    }
    deduped
        .into_iter()
        .find(|candidate| python_can_import(candidate, modules))
}

fn python_bin() -> Option<String> {
    python_bin_with_modules(&[])
}

fn adapter_python_bin() -> Option<String> {
    python_bin_with_modules(&["uvicorn", "fastapi"])
}

fn launch_agent_path(label: &str) -> PathBuf {
    home_dir()
        .join("Library")
        .join("LaunchAgents")
        .join(format!("{label}.plist"))
}

fn launchd_domain() -> Option<String> {
    run_capture(
        {
            let mut cmd = Command::new("id");
            cmd.arg("-u");
            cmd
        },
        "读取用户 uid",
    )
    .ok()
    .map(|uid| format!("gui/{}", uid.trim()))
}

fn bootstrap_or_kickstart_launch_agent(label: &str) -> bool {
    let Some(domain) = launchd_domain() else {
        return false;
    };
    let plist = launch_agent_path(label);
    if !plist.exists() {
        return false;
    }
    let target = format!("{domain}/{label}");
    let loaded = Command::new("launchctl")
        .arg("print")
        .arg(&target)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|status| status.success())
        .unwrap_or(false);
    if !loaded {
        let _ = Command::new("launchctl")
            .arg("bootstrap")
            .arg(&domain)
            .arg(&plist)
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();
    }
    Command::new("launchctl")
        .arg("kickstart")
        .arg("-k")
        .arg(&target)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|status| status.success())
        .unwrap_or(false)
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
    if bootstrap_or_kickstart_launch_agent("com.omnimemora.runtime")
        && wait_for_service(RUNTIME_PORT, "/health", Some("\"status\":"))
    {
        return Ok(None);
    }
    let binary = runtime_binary()
        .ok_or_else(|| "找不到 runtime binary。请先生成或安装 runtime 组件。".to_string())?;
    let agent_modes = current_agent_modes_path();
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
    if bootstrap_or_kickstart_launch_agent("com.omnimemora.adapter")
        && wait_for_service(ADAPTER_PORT, "/health", Some("\"status\":\"healthy\""))
    {
        return Ok(None);
    }
    let python = adapter_python_bin()
        .ok_or_else(|| "找不到带 uvicorn/fastapi 的 Python，无法启动 adapter。".to_string())?;
    let root = repo_root();
    let component = component_dir();
    let service_current = service_current_dir();
    let launcher = first_existing(&[
        component.join("tools/_run_adapter.py"),
        service_current.join("tools/_run_adapter.py"),
        root.join("tools/_run_adapter.py"),
    ])
    .ok_or_else(|| "找不到 adapter launcher。".to_string())?;
    let adapter_root = launcher
        .parent()
        .and_then(Path::parent)
        .map(Path::to_path_buf)
        .unwrap_or_else(|| root.clone());
    let agent_modes = current_agent_modes_path();
    let mut cmd = Command::new(&python);
    cmd.arg(&launcher)
        .current_dir(&adapter_root)
        .env("PORT", ADAPTER_PORT.to_string())
        .env(
            "MEMORY_BACKEND_URL",
            format!("http://127.0.0.1:{RUNTIME_PORT}"),
        )
        .env("OMNIMEMORA_INTERNAL_API_TOKEN", INTERNAL_TOKEN)
        .env("OMNIMEMORA_AGENT_MODES_PATH", agent_modes)
        .env("PYTHONPATH", adapter_root);
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
    if bootstrap_or_kickstart_launch_agent("com.omnimemora.dashboard")
        && wait_for_service(UI_PORT, "/", None)
    {
        return Ok(None);
    }
    let python =
        python_bin().ok_or_else(|| "找不到 python3，无法启动本地 GUI 静态服务。".to_string())?;
    let root = repo_root();
    let component = component_dir();
    let service_current = service_current_dir();
    let dist = first_existing(&[
        component.join("ui/dist"),
        service_current.join("ui/dist"),
        service_current.join("6_console/demo-dashboard/dist"),
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

fn platform_id() -> &'static str {
    match (env::consts::OS, env::consts::ARCH) {
        ("macos", "aarch64") => "darwin-arm64",
        ("macos", "x86_64") => "darwin-amd64",
        ("windows", "x86_64") => "windows-amd64",
        _ => "unsupported",
    }
}

fn run_capture(mut command: Command, label: &str) -> Result<String, String> {
    let output = command
        .output()
        .map_err(|err| format!("{label} 执行失败: {err}"))?;
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("{label} 返回失败: {}", stderr.trim()));
    }
    Ok(String::from_utf8_lossy(&output.stdout).to_string())
}

fn curl_to_string(url: &str) -> Result<String, String> {
    let mut command = Command::new("curl");
    command.args(["-fsSL", "--connect-timeout", "8", "--max-time", "30", url]);
    run_capture(command, "下载 manifest")
}

fn curl_to_file(url: &str, dest: &Path) -> Result<(), String> {
    ensure_dirs()?;
    let mut command = Command::new("curl");
    command
        .args(["-fL", "--connect-timeout", "8", "--max-time", "300", "-o"])
        .arg(dest)
        .arg(url);
    run_capture(command, "下载更新包").map(|_| ())
}

fn sha256_file(path: &Path) -> Result<String, String> {
    let mut command = Command::new("shasum");
    command.args(["-a", "256"]).arg(path);
    let output = run_capture(command, "SHA256 校验")?;
    output
        .split_whitespace()
        .next()
        .map(ToString::to_string)
        .ok_or_else(|| "SHA256 输出为空。".to_string())
}

fn parse_json(raw: &str, context: &str) -> Result<Value, String> {
    serde_json::from_str(raw).map_err(|err| format!("{context} 不是有效 JSON: {err}"))
}

fn fetch_latest_manifest() -> Result<Value, String> {
    ensure_dirs()?;
    let raw = curl_to_string(LATEST_MANIFEST_URL)?;
    let value = parse_json(&raw, "线上 release manifest")?;
    fs::write(downloaded_manifest_path(), raw)
        .map_err(|err| format!("无法保存 release manifest: {err}"))?;
    Ok(value)
}

fn fetch_cloud_policy_candidate() -> Result<(), String> {
    ensure_dirs()?;
    let raw = curl_to_string(CLOUD_POLICY_CANDIDATE_URL)?;
    let _ = parse_json(&raw, "云端策略候选")?;
    fs::write(downloaded_candidate_path(), raw)
        .map_err(|err| format!("无法保存云端策略候选: {err}"))
}

fn platform_manifest<'a>(manifest: &'a Value, platform: &str) -> Result<&'a Value, String> {
    manifest
        .get("platforms")
        .and_then(|value| value.get(platform))
        .ok_or_else(|| format!("release manifest 不包含当前平台 {platform}。"))
}

fn manifest_version(manifest: &Value) -> Result<String, String> {
    manifest
        .get("version")
        .and_then(Value::as_str)
        .map(ToString::to_string)
        .ok_or_else(|| "release manifest 缺少 version。".to_string())
}

fn manifest_package(manifest: &Value, platform: &str) -> Result<(String, String, String), String> {
    let entry = platform_manifest(manifest, platform)?;
    let package = entry
        .get("package")
        .and_then(Value::as_str)
        .ok_or_else(|| format!("{platform} manifest 缺少 package。"))?;
    let sha = entry
        .get("sha256")
        .and_then(Value::as_str)
        .ok_or_else(|| format!("{platform} manifest 缺少 sha256。"))?;
    let url = entry
        .get("download_url")
        .and_then(Value::as_str)
        .ok_or_else(|| format!("{platform} manifest 缺少 download_url。"))?;
    Ok((package.to_string(), sha.to_string(), url.to_string()))
}

fn unpack_zip(zip_path: &Path, dest: &Path) -> Result<(), String> {
    if dest.exists() {
        fs::remove_dir_all(dest)
            .map_err(|err| format!("无法清理 staging 目录 {}: {err}", dest.display()))?;
    }
    fs::create_dir_all(dest)
        .map_err(|err| format!("无法创建 staging 目录 {}: {err}", dest.display()))?;
    let mut command = Command::new("unzip");
    command.args(["-q"]).arg(zip_path).arg("-d").arg(dest);
    run_capture(command, "解包更新包").map(|_| ())
}

fn unpacked_component_root(staging: &Path) -> Result<PathBuf, String> {
    let mut roots = Vec::new();
    for entry in fs::read_dir(staging).map_err(|err| format!("无法读取 staging 目录: {err}"))?
    {
        let entry = entry.map_err(|err| format!("无法读取 staging 条目: {err}"))?;
        if entry.file_type().map(|kind| kind.is_dir()).unwrap_or(false) {
            roots.push(entry.path());
        }
    }
    if roots.len() != 1 {
        return Err("更新包结构不正确：staging 中应只有一个组件目录。".to_string());
    }
    Ok(roots.remove(0))
}

fn component_health_ok() -> bool {
    wait_for_service(RUNTIME_PORT, "/health", Some("\"status\":"))
        && wait_for_service(ADAPTER_PORT, "/health", Some("\"status\":\"healthy\""))
        && wait_for_service(UI_PORT, "/", None)
}

fn restore_previous_components() -> Result<(), String> {
    if !previous_dir().exists() {
        return Err("没有 previous 组件可回滚。".to_string());
    }
    let rollback_snapshot = rollback_dir().join(format!("failed-current-{}", unix_now()));
    if current_dir().exists() {
        if rollback_snapshot.exists() {
            fs::remove_dir_all(&rollback_snapshot)
                .map_err(|err| format!("无法清理旧 rollback snapshot: {err}"))?;
        }
        fs::rename(current_dir(), &rollback_snapshot)
            .map_err(|err| format!("无法保存失败版本到 rollback: {err}"))?;
    }
    fs::rename(previous_dir(), current_dir()).map_err(|err| format!("无法恢复 previous: {err}"))?;
    Ok(())
}

fn config_path_for_agent(agent: &str) -> PathBuf {
    match agent {
        "codex" => home_dir().join(".codex/config.toml"),
        "claude" => {
            let settings = home_dir().join(".claude/settings.json");
            if settings.exists() {
                settings
            } else {
                home_dir().join(".claude.json")
            }
        }
        "openclaw" => home_dir().join(".openclaw/openclaw.json"),
        _ => home_dir(),
    }
}

fn agent_process_running(patterns: &[&str]) -> bool {
    let output = Command::new("ps")
        .args(["-axo", "command="])
        .output()
        .ok()
        .map(|output| String::from_utf8_lossy(&output.stdout).to_lowercase())
        .unwrap_or_default();
    patterns
        .iter()
        .any(|pattern| output.contains(&pattern.to_lowercase()))
}

fn config_contains(path: &Path, needles: &[&str]) -> bool {
    let Ok(raw) = fs::read_to_string(path) else {
        return false;
    };
    needles.iter().any(|needle| raw.contains(needle))
}

fn agent_attached(agent: &str, path: &Path) -> bool {
    match agent {
        "codex" => config_contains(
            path,
            &[
                r#"model_provider = "omnimemora""#,
                "[model_providers.omnimemora]",
                "[mcp_servers.omnimemora]",
            ],
        ),
        "claude" => config_contains(path, &["omnimemora", "http://127.0.0.1:18011"]),
        "openclaw" => config_contains(
            path,
            &[
                ".omnimemora.attach.marker",
                "omnimemora",
                "http://127.0.0.1:18011",
            ],
        ),
        _ => false,
    }
}

fn agent_status(
    id: &'static str,
    name: &'static str,
    running_patterns: &[&str],
    supported: bool,
    experimental: bool,
) -> AgentStatus {
    let config_path = config_path_for_agent(id);
    let installed = config_path.exists();
    let running = agent_process_running(running_patterns);
    let attached = installed && agent_attached(id, &config_path);
    let state = if attached {
        "connected"
    } else if installed || running {
        "ready"
    } else {
        "not_found"
    };
    let detail = if attached {
        "已连接到 OmniMemora；重启对应工具后配置生效。"
    } else if installed || running {
        "已发现本机工具，可以从这里连接。"
    } else if experimental {
        "未发现配置文件；Codex 当前保持实验入口，不默认启用。"
    } else {
        "未发现本机配置；仍可手动创建连接配置。"
    };
    AgentStatus {
        id,
        name,
        state: state.to_string(),
        installed,
        running,
        attached,
        supported,
        experimental,
        detail: detail.to_string(),
        config_path: config_path.display().to_string(),
    }
}

fn detect_agents() -> Vec<AgentStatus> {
    vec![
        agent_status("claude", "Claude Code", &["claude"], true, false),
        agent_status("openclaw", "OpenClaw", &["openclaw"], true, false),
        agent_status("codex", "Codex", &["codex"], true, true),
    ]
}

fn run_agent_cli(agent: &str, action: &str) -> Result<String, String> {
    match agent {
        "codex" | "claude" | "openclaw" => {}
        _ => return Err("未知 AI tool。".to_string()),
    }
    let binary = runtime_binary()
        .ok_or_else(|| "找不到 OmniMemora runtime binary，无法写入 agent 连接配置。".to_string())?;
    let mut cmd = Command::new(&binary);
    cmd.arg(action)
        .arg(agent)
        .current_dir(repo_root())
        .env("OMNIMEMORA_ADAPTER_PORT", ADAPTER_PORT.to_string());
    run_capture(cmd, "AI tool connection")
}

fn start_all_services() -> Result<String, String> {
    ensure_dirs()?;
    let mut state = prune_dead_processes(read_state());
    let mut started: Vec<ManagedProcess> = Vec::new();
    let mut failures: Vec<String> = Vec::new();

    match start_runtime() {
        Ok(Some(proc)) => started.push(proc),
        Ok(None) => {}
        Err(err) => failures.push(format!("8765 runtime: {err}")),
    }
    if !wait_for_service(RUNTIME_PORT, "/health", Some("\"status\":")) {
        failures.push("8765 runtime 健康检查未通过".to_string());
    }

    match start_adapter() {
        Ok(Some(proc)) => started.push(proc),
        Ok(None) => {}
        Err(err) => failures.push(format!("18011 adapter: {err}")),
    }
    if !wait_for_service(ADAPTER_PORT, "/health", Some("\"status\":\"healthy\"")) {
        failures.push("18011 adapter 健康检查未通过".to_string());
    }

    match start_ui() {
        Ok(Some(proc)) => started.push(proc),
        Ok(None) => {}
        Err(err) => failures.push(format!("5173 GUI: {err}")),
    }
    if !wait_for_service(UI_PORT, "/", None) {
        failures.push("5173 GUI 健康检查未通过".to_string());
    }

    for proc in started.iter() {
        state
            .processes
            .retain(|existing| existing.name != proc.name);
        state.processes.push(proc.clone());
    }
    write_state(&state)?;
    if !failures.is_empty() {
        return Err(format!("启动未完全成功：{}", failures.join("； ")));
    }
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

    // Also stop launchctl-managed OmniMemora services so Stop has visible effect
    // even when services were started outside the desktop shell process table.
    let uid = run_capture(
        {
            let mut cmd = Command::new("id");
            cmd.arg("-u");
            cmd
        },
        "读取用户 uid",
    )
    .unwrap_or_default()
    .trim()
    .to_string();
    let launchd_labels = [
        format!("gui/{uid}/com.omnimemora.runtime"),
        format!("gui/{uid}/com.omnimemora.adapter"),
        format!("gui/{uid}/com.omnimemora.dashboard"),
    ];
    let mut launchd_stopped = 0usize;
    let mut launchd_booted_out = 0usize;
    let mut launchd_killed_by_pid = 0usize;
    for label in launchd_labels {
        let mut bootout_cmd = Command::new("launchctl");
        bootout_cmd.arg("bootout").arg(&label);
        if bootout_cmd
            .output()
            .map(|o| o.status.success())
            .unwrap_or(false)
        {
            launchd_booted_out += 1;
            launchd_stopped += 1;
            continue;
        }

        let mut stop_cmd = Command::new("launchctl");
        stop_cmd.arg("stop").arg(&label);
        if stop_cmd
            .output()
            .map(|o| o.status.success())
            .unwrap_or(false)
        {
            launchd_stopped += 1;
            continue;
        }

        // Last-resort fallback: read launchctl pid and kill it directly.
        let mut print_cmd = Command::new("launchctl");
        print_cmd.arg("print").arg(&label);
        if let Ok(output) = print_cmd.output() {
            if output.status.success() {
                let text = String::from_utf8_lossy(&output.stdout);
                for line in text.lines() {
                    let trimmed = line.trim();
                    if let Some(pid_str) = trimmed.strip_prefix("pid = ") {
                        if let Ok(pid) = pid_str.trim().parse::<u32>() {
                            if kill_process(pid) {
                                launchd_killed_by_pid += 1;
                                launchd_stopped += 1;
                            }
                        }
                        break;
                    }
                }
            }
        }
    }

    for (name, port) in [
        ("runtime", RUNTIME_PORT),
        ("adapter", ADAPTER_PORT),
        ("ui", UI_PORT),
    ] {
        let Some(pid) = port_owner_pid(port) else {
            continue;
        };
        let Some(command) = process_command(pid) else {
            continue;
        };
        if known_omnimemora_service(name, &command) && kill_process(pid) {
            launchd_killed_by_pid += 1;
            launchd_stopped += 1;
        }
    }

    Ok(format!(
        "已请求停止 {count} 个桌面管理进程；launchctl 停止 {launchd_stopped} 个（bootout={launchd_booted_out}, kill={launchd_killed_by_pid}）。"
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
    match fetch_latest_manifest() {
        Ok(manifest) => {
            let version = manifest
                .get("version")
                .and_then(Value::as_str)
                .unwrap_or("unknown");
            let desktop_message = if version_is_newer(version, APP_VERSION) {
                "桌面 App 有新版可用；可使用产品内 updater 下载、签名校验并安装。"
            } else {
                "桌面 App 已是当前版本。"
            };
            let candidate_message = match fetch_cloud_policy_candidate() {
                Ok(_) => "云端策略候选也已检查；仍保持 candidate-only。",
                Err(_) => "云端策略候选暂不可用；本地 active policy 未改变。",
            };
            command_result(
                true,
                format!(
                    "已检查线上 release manifest：{version}。{desktop_message}{candidate_message}"
                ),
            )
        }
        Err(err) => command_result(false, format!("检查更新失败：{err}")),
    }
}

#[tauri::command]
async fn install_desktop_update(app: AppHandle) -> DesktopCommandResult {
    let result = async {
        let platform = platform_id();
        if platform == "unsupported" {
            return Err("当前平台暂未支持桌面 App 自动更新。".to_string());
        }
        let updater = app
            .updater()
            .map_err(|err| format!("桌面 App updater 初始化失败：{err}"))?;
        let Some(update) = updater
            .check()
            .await
            .map_err(|err| format!("桌面 App updater 检查失败：{err}"))?
        else {
            return Ok(format!("桌面 App 已是最新版本：{APP_VERSION}。"));
        };
        let version = update.version.clone();
        update
            .download_and_install(|_, _| {}, || {})
            .await
            .map_err(|err| format!("桌面 App updater 安装失败：{err}"))?;
        eprintln!("OmniMemora desktop update {version} installed; restarting app.");
        app.restart();
        #[allow(unreachable_code)]
        {
            Ok(format!(
                "桌面 App {version} 已通过 Tauri updater 签名校验并安装。应用将重启以进入新版本；用户 memory 与本地产品数据不会被删除。"
            ))
        }
    }
    .await;

    match result {
        Ok(message) => command_result(true, message),
        Err(err) => command_result(false, err),
    }
}

#[tauri::command]
fn install_update() -> DesktopCommandResult {
    let result = (|| -> Result<String, String> {
        let platform = platform_id();
        if platform == "unsupported" {
            return Err("当前平台暂未支持自动组件更新。".to_string());
        }
        let manifest = fetch_latest_manifest().or_else(|_| {
            release_manifest_from_disk()
                .ok_or_else(|| "无法获取线上或本地 release manifest。".to_string())
        })?;
        let version = manifest_version(&manifest)?;
        let installed = installed_component_version();
        if installed
            .as_deref()
            .map(|current| !version_is_newer(&version, current))
            .unwrap_or(false)
        {
            return Ok(format!("本地组件已是最新版本：{version}。"));
        }
        let (package, expected_sha, download_url) = manifest_package(&manifest, platform)?;
        let zip_path = downloads_dir().join(&package);
        curl_to_file(&download_url, &zip_path)?;
        let actual_sha = sha256_file(&zip_path)?;
        if actual_sha != expected_sha {
            return Err(format!(
                "SHA256 不匹配，已阻止安装。expected={expected_sha} actual={actual_sha}"
            ));
        }

        let staging = downloads_dir().join(format!("staging-{version}-{platform}"));
        unpack_zip(&zip_path, &staging)?;
        let unpacked_root = unpacked_component_root(&staging)?;
        if !unpacked_root.join("manifest.json").exists()
            || !unpacked_root.join("tools/_run_adapter.py").exists()
        {
            return Err("更新包缺少 manifest 或 adapter launcher。".to_string());
        }

        stop_all_services()?;
        if previous_dir().exists() {
            fs::remove_dir_all(previous_dir())
                .map_err(|err| format!("无法清理 previous 目录: {err}"))?;
        }
        if current_dir().exists() {
            fs::rename(current_dir(), previous_dir())
                .map_err(|err| format!("无法切换 current 到 previous: {err}"))?;
        }
        fs::rename(&unpacked_root, current_dir())
            .map_err(|err| format!("无法安装新组件到 current: {err}"))?;
        let _ = fs::remove_dir_all(&staging);

        match start_all_services() {
            Ok(_) if component_health_ok() => Ok(format!("本地组件已更新到 {version}。")),
            Ok(_) => {
                stop_all_services().ok();
                restore_previous_components().ok();
                start_all_services().ok();
                Err("更新后健康检查未通过，已尝试自动回滚。".to_string())
            }
            Err(err) => {
                restore_previous_components().ok();
                start_all_services().ok();
                Err(format!("更新后服务启动失败，已尝试自动回滚：{err}"))
            }
        }
    })();

    match result {
        Ok(message) => command_result(true, message),
        Err(err) => command_result(false, err),
    }
}

#[tauri::command]
fn rollback() -> DesktopCommandResult {
    let result = (|| -> Result<String, String> {
        stop_all_services()?;
        restore_previous_components()?;
        match start_all_services() {
            Ok(_) if component_health_ok() => {
                Ok("已回滚本地组件；桌面壳和用户 memory 数据未回滚。".to_string())
            }
            Ok(_) => Err("回滚后健康检查未通过，请检查本地组件包。".to_string()),
            Err(err) => Err(format!("回滚后服务启动失败：{err}")),
        }
    })();
    match result {
        Ok(message) => command_result(true, message),
        Err(err) => command_result(false, err),
    }
}

#[tauri::command]
fn scan_agents() -> Vec<AgentStatus> {
    detect_agents()
}

#[tauri::command]
fn attach_agent(agent: String) -> DesktopCommandResult {
    match run_agent_cli(&agent, "attach") {
        Ok(_) => command_result(
            true,
            format!("已写入 {agent} 连接配置；请重启对应工具后使用。"),
        ),
        Err(err) => command_result(false, format!("连接 {agent} 失败：{err}")),
    }
}

#[tauri::command]
fn detach_agent(agent: String) -> DesktopCommandResult {
    match run_agent_cli(&agent, "detach") {
        Ok(_) => command_result(true, format!("已移除 {agent} 连接配置。")),
        Err(err) => command_result(false, format!("断开 {agent} 失败：{err}")),
    }
}

fn show_main_window(app_handle: &AppHandle) {
    if let Some(window) = app_handle.get_webview_window("main") {
        if let Err(err) = window.show() {
            eprintln!("failed to show OmniMemora desktop window: {err}");
        }
        if let Err(err) = window.set_focus() {
            eprintln!("failed to focus OmniMemora desktop window: {err}");
        }
    }
}

fn ensure_main_window(app: &mut tauri::App) -> Result<(), Box<dyn std::error::Error>> {
    if app.get_webview_window("main").is_none() {
        WebviewWindowBuilder::new(app, "main", WebviewUrl::App("index.html".into()))
            .title("OmniMemora Desktop")
            .inner_size(1120.0, 760.0)
            .min_inner_size(860.0, 620.0)
            .resizable(true)
            .center()
            .build()?;
    }
    Ok(())
}

fn setup_desktop_shell(app: &mut tauri::App) -> Result<(), Box<dyn std::error::Error>> {
    ensure_main_window(app)?;
    if let (Some(window), Some(icon)) = (
        app.get_webview_window("main"),
        app.default_window_icon().cloned(),
    ) {
        window.set_icon(icon.clone())?;
    }
    show_main_window(app.handle());
    let show = MenuItem::with_id(app, TRAY_SHOW_ID, "Show OmniMemora", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, TRAY_QUIT_ID, "Quit OmniMemora", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&show, &quit])?;
    let mut tray = TrayIconBuilder::with_id("main")
        .menu(&menu)
        .tooltip("OmniMemora")
        .show_menu_on_left_click(true)
        .on_menu_event(|app_handle, event| match event.id().as_ref() {
            TRAY_SHOW_ID => show_main_window(app_handle),
            TRAY_QUIT_ID => app_handle.exit(0),
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                show_main_window(tray.app_handle());
            }
        });
    if let Some(icon) = app.default_window_icon().cloned() {
        tray = tray.icon(icon);
    }
    tray.build(app)?;
    Ok(())
}

fn main() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_updater::Builder::new().build())
        .setup(setup_desktop_shell)
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                if let Err(err) = window.hide() {
                    eprintln!("failed to hide OmniMemora desktop window: {err}");
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            get_desktop_status,
            start_services,
            stop_services,
            restart_services,
            check_for_updates,
            install_desktop_update,
            install_update,
            rollback,
            scan_agents,
            attach_agent,
            detach_agent
        ])
        .build(tauri::generate_context!())
        .expect("error while building OmniMemora desktop shell");

    app.run(|app_handle, event| {
        #[cfg(target_os = "macos")]
        if let RunEvent::Reopen { .. } = event {
            show_main_window(app_handle);
        }
    });
}
