"""
配置模块 v2.2
"""
import json
import os
from pydantic import BaseModel
from typing import List, Dict, Any, Optional


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _prefer_minimax_upstream() -> bool:
    """
    Decide whether Anthropic-compatible upstream should default to MiniMax.

    Important:
    - Agent-facing `ANTHROPIC_BASE_URL` may point at OmniMemora itself (`/llm`)
    - Gateway upstream must not inherit that value, or it can recurse/bypass incorrectly
    """
    return bool(os.getenv("MINIMAX_API_KEY", "").strip())


def _default_anthropic_upstream_base_url() -> str:
    explicit = os.getenv("OMNIMEMORA_ANTHROPIC_BASE_URL", "").strip()
    if explicit:
        return explicit
    if _prefer_minimax_upstream():
        return "https://api.minimaxi.com/anthropic"
    return "https://api.anthropic.com"


def _default_anthropic_api_key() -> str:
    explicit = os.getenv("OMNIMEMORA_ANTHROPIC_API_KEY", "").strip()
    if explicit:
        return explicit
    minimax = os.getenv("MINIMAX_API_KEY", "").strip()
    if minimax:
        return minimax
    bridge = os.getenv("ANTHROPIC_AUTH_TOKEN", "").strip()
    if bridge:
        return bridge
    return os.getenv("ANTHROPIC_API_KEY", "")


def _default_anthropic_model() -> str:
    explicit = os.getenv("OMNIMEMORA_ANTHROPIC_MODEL", "").strip()
    if explicit:
        return explicit
    if _prefer_minimax_upstream():
        return "MiniMax-M2.7"
    return "claude-sonnet-4-20250514"


def _default_openai_model() -> str:
    explicit = os.getenv("OMNIMEMORA_OPENAI_MODEL", "").strip()
    if explicit:
        return explicit
    return "gemma4:26b"


def _default_openai_model_map() -> dict[str, str]:
    explicit = os.getenv("OMNIMEMORA_OPENAI_MODEL_MAP", "").strip()
    if not explicit:
        return {
            "gemma4:26b": "gemma4:26b",
        }
    try:
        parsed = json.loads(explicit)
    except Exception:
        return {
            "gemma4:26b": "gemma4:26b",
        }
    if not isinstance(parsed, dict):
        return {
            "gemma4:26b": "gemma4:26b",
        }
    normalized: dict[str, str] = {}
    for raw_key, raw_value in parsed.items():
        key = str(raw_key).strip()
        value = str(raw_value).strip()
        if key and value:
            normalized[key] = value
    return normalized or {
        "gemma4:26b": "gemma4:26b",
    }


def _default_anthropic_timeout_seconds() -> float:
    return float(os.getenv("OMNIMEMORA_ANTHROPIC_TIMEOUT_SECONDS", "120"))


def _default_openai_timeout_seconds() -> float:
    return float(os.getenv("OMNIMEMORA_OPENAI_TIMEOUT_SECONDS", "240"))


class MemoryBackendConfig(BaseModel):
    """Memory Backend 配置"""
    backend_type: str = os.getenv("MEMORY_BACKEND_TYPE", "omnimemora_runtime")
    base_url: str = os.getenv("MEMORY_BACKEND_URL", "http://127.0.0.1:8765")
    api_key: Optional[str] = os.getenv("MEMORY_BACKEND_API_KEY", None)
    timeout_seconds: float = float(os.getenv("MEMORY_BACKEND_TIMEOUT_SECONDS", "30"))
    connect_timeout_seconds: float = float(os.getenv("MEMORY_BACKEND_CONNECT_TIMEOUT_SECONDS", "5"))


class InternalTransportConfig(BaseModel):
    """ADR-0006: 内部直连传输配置"""
    enabled: bool = True
    probe_on_startup: bool = True
    cache_ttl_seconds: int = 300
    connect_timeout_seconds: float = 1.5
    read_timeout_seconds: float = 5.0
    loopback_candidates: list[str] = [
        "127.0.0.1",
        "localhost",
        "::1",
    ]


class MemoryLevelConfig(BaseModel):
    """记忆等级配置"""
    min_score: int  # 最低分数阈值
    description: str
    ttl_days: int = -1  # -1 表示永久


def _default_data_dir() -> str:
    return os.path.expanduser("~/.omnimemora/data")


def _default_access_registry_path() -> str:
    return os.getenv(
        "OMNIMEMORA_ACCESS_REGISTRY_PATH",
        os.path.join(_default_data_dir(), "tenant_access_registry.json"),
    )


def _default_usage_state_path() -> str:
    return os.getenv(
        "OMNIMEMORA_USAGE_STATE_PATH",
        os.path.join(_default_data_dir(), "usage_state.json"),
    )


class RegistrySyncConfig(BaseModel):
    """Optional remote registry sync configuration."""
    enabled: bool = False
    url: str = ""
    token: str = ""
    timeout_seconds: float = 10.0


class CloudIntegrationConfig(BaseModel):
    """云接入层配置"""
    enabled: bool = _env_bool(
        "OMNIMEMORA_CLOUD_POLICY_UPDATES_ENABLED",
        _env_bool("CLOUD_ENABLED", False),
    )
    base_url: str = os.getenv("CLOUD_BASE_URL", "https://your-cloud-domain")
    policy_timeout_ms: float = float(os.getenv("CLOUD_POLICY_TIMEOUT_MS", "500"))
    flags_timeout_ms: float = float(os.getenv("CLOUD_FLAGS_TIMEOUT_MS", "300"))
    # Consent rule:
    # - pure local mode: cloud disabled, no usage reporting
    # - cloud policy updates enabled: minimal telemetry is enabled by default
    #   unless the operator explicitly overrides it back off
    usage_report_enabled: bool = _env_bool(
        "CLOUD_USAGE_REPORT_ENABLED",
        _env_bool(
            "OMNIMEMORA_CLOUD_POLICY_UPDATES_ENABLED",
            _env_bool("CLOUD_ENABLED", False),
        ),
    )
    # Candidate source contract (Cloud Reset Batch 1):
    # - Cloudflare: candidate pointer fetch entry
    # - Railway: candidate snapshot/state fetch
    # - Local active remains authoritative
    candidate_source_enabled: bool = _env_bool(
        "OMNIMEMORA_CLOUD_CANDIDATE_SOURCE_ENABLED",
        False,
    )
    control_plane_base_url: str = os.getenv(
        "OMNIMEMORA_CLOUD_CONTROL_PLANE_BASE_URL",
        "https://doloclaw.com",
    )
    control_plane_candidate_path: str = os.getenv(
        "OMNIMEMORA_CLOUD_CANDIDATE_POINTER_PATH",
        "/api/control/recommendation/candidates/latest",
    )
    control_plane_token: str = os.getenv("OMNIMEMORA_CLOUD_CONTROL_TOKEN", "")
    railway_state_base_url: str = os.getenv("OMNIMEMORA_RAILWAY_STATE_BASE_URL", "")
    railway_snapshot_path_template: str = os.getenv(
        "OMNIMEMORA_RAILWAY_SNAPSHOT_PATH_TEMPLATE",
        "/internal/recommendation/snapshots/{snapshot_id}",
    )
    candidate_timeout_ms: float = float(
        os.getenv("OMNIMEMORA_CLOUD_CANDIDATE_TIMEOUT_MS", "800")
    )


class Config(BaseModel):
    omnimemora_access_registry_path: str = _default_access_registry_path()
    omnimemora_usage_state_path: str = _default_usage_state_path()
    omnimemora_require_api_key_for_v2: bool = os.getenv(
        "OMNIMEMORA_REQUIRE_API_KEY_FOR_V2",
        "false",
    ).lower() == "true"
    registry_sync: RegistrySyncConfig = RegistrySyncConfig(
        enabled=os.getenv("OMNIMEMORA_REGISTRY_SYNC_ENABLED", "").lower() == "true",
        url=os.getenv("OMNIMEMORA_REGISTRY_SYNC_URL", ""),
        token=os.getenv("OMNIMEMORA_REGISTRY_SYNC_TOKEN", ""),
        timeout_seconds=float(os.getenv("OMNIMEMORA_REGISTRY_SYNC_TIMEOUT", "10.0")),
    )

    # Trial provisioning config
    omnimemora_admin_api_token: str = os.getenv("OMNIMEMORA_ADMIN_API_TOKEN", "")
    omnimemora_trial_days: int = int(os.getenv("OMNIMEMORA_TRIAL_DAYS", "14"))
    omnimemora_trial_quota_tokens: int = int(os.getenv("OMNIMEMORA_TRIAL_QUOTA_TOKENS", "500000"))

    # Memory plane endpoint config (active naming)
    memory_backend_url: str = os.getenv("MEMORY_BACKEND_URL", "http://127.0.0.1:8765")
    memory_backend_api_key: str = os.getenv("MEMORY_BACKEND_API_KEY", "")
    viking_memory_namespace_root: str = os.getenv(
        "OMNIMEMORA_MEMORY_NAMESPACE_ROOT",
        "viking://resources/memory-adapter",
    )

    # Memory Backend 配置
    memory_backend: MemoryBackendConfig = MemoryBackendConfig()

    # Adapter 配置
    adapter_host: str = "0.0.0.0"
    adapter_port: int = int(os.getenv("PORT", "18011"))

    # ========== 超时治理配置 ==========
    viking_connect_timeout_seconds: float = float(os.getenv("VIKING_CONNECT_TIMEOUT_SECONDS", "5"))
    viking_health_timeout_seconds: float = float(os.getenv("VIKING_HEALTH_TIMEOUT_SECONDS", "5"))
    viking_search_timeout_seconds: float = float(os.getenv("VIKING_SEARCH_TIMEOUT_SECONDS", "20"))
    viking_read_timeout_seconds: float = float(os.getenv("VIKING_READ_TIMEOUT_SECONDS", "20"))
    viking_delete_timeout_seconds: float = float(os.getenv("VIKING_DELETE_TIMEOUT_SECONDS", "20"))
    viking_snapshot_timeout_seconds: float = float(os.getenv("VIKING_SNAPSHOT_TIMEOUT_SECONDS", "60"))
    viking_upload_timeout_seconds: float = float(os.getenv("VIKING_UPLOAD_TIMEOUT_SECONDS", "20"))
    viking_commit_timeout_seconds: float = float(os.getenv("VIKING_COMMIT_TIMEOUT_SECONDS", "45"))
    viking_resolve_timeout_seconds: float = float(os.getenv("VIKING_RESOLVE_TIMEOUT_SECONDS", "15"))
    viking_retry_attempts: int = int(os.getenv("VIKING_RETRY_ATTEMPTS", "1"))
    viking_retry_backoff_seconds: float = float(os.getenv("VIKING_RETRY_BACKOFF_SECONDS", "0.75"))
    slow_request_threshold_ms: int = int(os.getenv("SLOW_REQUEST_THRESHOLD_MS", "5000"))
    search_fallback_scan_limit: int = int(os.getenv("SEARCH_FALLBACK_SCAN_LIMIT", "40"))

    # ========== 过滤器配置 ==========
    min_content_length: int = 20
    exclude_keywords: List[str] = []  # v2.2: 移除 error 过滤，改为加分
    exclude_types: List[str] = ["chat", "thinking", "debug", "log"]  # type 过滤

    # ========== 路由器配置 (评分制) ==========
    # 长期记忆评分规则
    route_score_rules: Dict[str, int] = {
        "length_gt_100": 1,       # 内容 > 100 字符
        "length_gt_500": 1,       # 内容 > 500 字符
        "success_keyword": 2,     # 含"成功"/"完成"
        "strategy_keyword": 2,    # 含"策略"/"规划"
        "important_keyword": 2,   # 含"重要"/"关键"
        "knowledge_keyword": 2,   # 含"知识"/"规则"
        "failure_experience": 2,  # 失败经验（新增：不再过滤，改为加分）
        "type_strategy": 2,      # metadata.type = strategy
        "type_result": 1,         # metadata.type = result
        "type_failure": 2,       # metadata.type = failure_experience
    }
    long_term_threshold: int = 2  # 分数 >= 2 进入长期记忆

    # ========== 记忆等级配置 ==========
    memory_levels: Dict[str, MemoryLevelConfig] = {
        "L0": MemoryLevelConfig(min_score=0, description="垃圾/不存", ttl_days=0),
        "L1": MemoryLevelConfig(min_score=1, description="短期缓存", ttl_days=7),
        "L2": MemoryLevelConfig(min_score=3, description="经验记忆", ttl_days=30),
        "L3": MemoryLevelConfig(min_score=5, description="核心知识", ttl_days=-1),
    }

    # ========== 去重配置 ==========
    enable_deduplication: bool = True

    # ========== 限流配置 ==========
    enable_rate_limit: bool = True
    rate_limit_per_minute: int = 100  # 每分钟最大写入数

    # ========== 云接入配置 ==========
    cloud: CloudIntegrationConfig = CloudIntegrationConfig()

    # ========== Agent Observability 配置 ==========
    agent_events_path: str = os.getenv(
        "OMNIMEMORA_AGENT_EVENTS_PATH",
        os.path.join(os.path.expanduser("~/.omnimemora/adapter"), "agent_events.jsonl"),
    )
    agent_events_flush_interval_seconds: float = float(os.getenv("OMNIMEMORA_AGENT_EVENTS_FLUSH", "5"))
    agent_events_max_file_size_mb: int = int(os.getenv("OMNIMEMORA_AGENT_EVENTS_MAX_MB", "50"))
    agent_events_retention_days: int = int(os.getenv("OMNIMEMORA_AGENT_EVENTS_RETENTION_DAYS", "30"))
    trace_anthropic_payload: bool = os.getenv(
        "OMNIMEMORA_TRACE_ANTHROPIC_PAYLOAD",
        "false",
    ).lower() == "true"
    trace_redact: bool = os.getenv(
        "OMNIMEMORA_TRACE_REDACT",
        "true",
    ).lower() == "true"
    anthropic_payload_trace_path: str = os.getenv(
        "OMNIMEMORA_ANTHROPIC_PAYLOAD_TRACE_PATH",
        os.path.join(os.path.expanduser("~/.omnimemora/adapter"), "anthropic_payload_trace.jsonl"),
    )
    trace_events_enabled: bool = os.getenv(
        "OMNIMEMORA_TRACE_EVENTS_ENABLED",
        "true",
    ).lower() == "true"
    trace_events_path: str = os.getenv(
        "OMNIMEMORA_TRACE_EVENTS_PATH",
        os.path.join(os.path.expanduser("~/.omnimemora/adapter"), "trace_events.jsonl"),
    )
    path_mode: str = os.getenv("OMNIMEMORA_PATH_MODE", "baseline").strip().lower() or "baseline"
    primary_ratio: float = float(os.getenv("OMNIMEMORA_PRIMARY_RATIO", "0.0"))

    # Per-agent control modes (loaded from agent_modes.json at startup)
    agent_control: dict = {}  # {agent_id: mode} — filled by main.py from agent_modes.json

    # ========== ADR-0006: 内部直连传输配置 ==========
    internal_transport: InternalTransportConfig = InternalTransportConfig()

    # ========== MCP Auto Bootstrap (产品级默认行为) ==========
    mcp_auto_bootstrap_enabled: bool = os.getenv(
        "OMNIMEMORA_MCP_AUTO_BOOTSTRAP_ENABLED",
        "true",
    ).lower() == "true"
    mcp_auto_bootstrap_query: str = os.getenv(
        "OMNIMEMORA_MCP_AUTO_BOOTSTRAP_QUERY",
        "session bootstrap context handshake",
    )

    # ========== LLM Proxy 配置（Phase 1 — 请求路径接管）============
    # 每个 provider 代表一个 LLM 上游，Agent 的请求经过 OmniMemora 时會轉發到這裡
    llm_proxy_enabled: bool = os.getenv("OMNIMEMORA_LLM_PROXY_ENABLED", "true").lower() == "true"

    # 默认 Anthropic 上游（Claude Code 等使用 Anthropic API 的 Agent）
    anthropic_base_url: str = _default_anthropic_upstream_base_url()
    anthropic_api_key: str = _default_anthropic_api_key()
    anthropic_default_model: str = _default_anthropic_model()

    # 默认 OpenAI/Ollama 上游（OpenClaw 等使用 OpenAI 格式的 Agent）
    openai_base_url: str = os.getenv(
        "OMNIMEMORA_OPENAI_BASE_URL",
        "http://127.0.0.1:11434/v1",  # 默认 Ollama 本地
    )
    openai_api_key: str = os.getenv("OMNIMEMORA_OPENAI_API_KEY", "ollama")
    openai_default_model: str = _default_openai_model()

    # Phase 2: UPSTREAMS 配置（显式结构化配置）
    # 用法：upstreams["anthropic"]["base_url"] 等
    upstreams: dict = {
        "anthropic": {
            "provider": "anthropic",
            "base_url": _default_anthropic_upstream_base_url(),
            "api_key_env": "OMNIMEMORA_ANTHROPIC_API_KEY",
            "api_key": _default_anthropic_api_key(),
            "model_map": {
                "claude-sonnet-4-20250514": _default_anthropic_model(),
                "claude-sonnet-4-6": _default_anthropic_model(),
                "claude-opus-4-5": _default_anthropic_model(),
                "MiniMax-M2.7": "MiniMax-M2.7",
            },
            "supports_stream": True,
            "timeout_seconds": _default_anthropic_timeout_seconds(),
        },
        "openai": {
            "provider": "openai_compatible",
            "base_url": os.getenv("OMNIMEMORA_OPENAI_BASE_URL", "http://127.0.0.1:11434/v1"),
            "api_key_env": "OMNIMEMORA_OPENAI_API_KEY",
            "api_key": os.getenv("OMNIMEMORA_OPENAI_API_KEY", "ollama"),
            "default_model": _default_openai_model(),
            "model_map": _default_openai_model_map(),
            "supports_stream": True,
            "timeout_seconds": _default_openai_timeout_seconds(),
        },
    }


config = Config()
