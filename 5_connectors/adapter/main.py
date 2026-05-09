"""
Memory Adapter v2.2 - memory backend 中间层
功能：标准化 → 过滤 → 路由 → 转换

改进点 v2.2（相比 v2.1）：
1. 错误内容不再过滤，转换为 failure_experience 类型并加分
2. 失败经验自动进入 L2（经验记忆）
3. 支持检测失败内容并标记

处理流程：
标准化 → 过滤 → 去重 → 限流 → 路由 → 转换 → memory backend
"""
import asyncio
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Any, Dict, Set
from datetime import datetime
from urllib.parse import quote
from uuid import uuid4
import httpx
import loguru
import sys
import os
import re
import socket
from pathlib import PurePosixPath
from collections import deque

from .config import config
from .trace_context import REQUEST_HEADER, TRACE_HEADER, build_trace_event, ensure_request_context
from .trace_events import append_trace_event
# Cloud access is consumed via infrastructure boundary in Batch 3D.
from .infrastructure import load_policy, load_flags, report_usage_async
from .quota_observer import (
    classify_quota_observation,
    is_quota_related_path,
    upstream_url_for_observation,
)
from .startup_probe import run_startup_probe
from .mcp_surface import configure_mcp_surface
from .diagnostics_surface import configure_diagnostics_surface
from .usage_surface import configure_usage_surface
from .scope_surface import configure_scope_surface
from .billing_surface import configure_billing_surface
from .cloud_surface import configure_cloud_surface

# 兼容数字开头包：逐个子模块动态导入（避免语法错误）
import importlib
_4_filter   = importlib.import_module("4_core.logic.filter")
_4_norm     = importlib.import_module("4_core.logic.normalizer")
_4_router   = importlib.import_module("4_core.logic.router")
_4_dedup    = importlib.import_module("4_core.logic.dedup")
_4_v2       = importlib.import_module("4_core.logic.v2_compute")
_4_engine   = importlib.import_module("4_core.logic.engine")
_4_rules    = importlib.import_module("4_core.logic.rules")
_5_adapter  = importlib.import_module("5_connectors.adapter")
_5_meter    = importlib.import_module("5_connectors.adapter.infrastructure.meter_store")
_5_tc       = importlib.import_module("5_connectors.adapter.task_classifier")
_5_trace    = importlib.import_module("5_connectors.adapter.infrastructure.trace_store")
_5_agent_id = importlib.import_module("5_connectors.adapter.agent_identity")
_5_ctrl     = importlib.import_module("5_connectors.adapter.control_mode")
_5_route_state = importlib.import_module("5_connectors.adapter.agent_routing_state")
_5_agnet_m  = importlib.import_module("5_connectors.adapter.agent_metrics")
_5_agnet_m.get_agent_metrics_store(
    events_path=config.agent_events_path,
    flush_interval_seconds=config.agent_events_flush_interval_seconds,
    max_file_size_mb=config.agent_events_max_file_size_mb,
    retention_days=config.agent_events_retention_days,
)

_5_route_state.reload_agent_modes()

_adapter_started_at = datetime.utcnow().isoformat() + "Z"
_adapter_hostname = socket.gethostname()

should_store              = _4_filter.should_store
detect_failure_content    = _4_filter.detect_failure_content
normalize                = _4_norm.normalize
to_viking_format         = _4_norm.to_viking_format
parse_viking_response     = _4_norm.parse_viking_response
calculate_expire_at       = _4_norm.calculate_expire_at
route_memory_type_and_level = _4_router.route_memory_type_and_level
check_duplicate          = _4_dedup.check_duplicate
add_to_dedup             = _4_dedup.add_to_dedup
get_dedup_cache          = _4_dedup.get_dedup_cache
check_quota_enforcement  = _4_v2.check_quota_enforcement
TokenSavingsMeter         = _4_v2.TokenSavingsMeter
CallChain                = _4_v2.CallChain
OptimizationInput         = _4_engine.OptimizationInput
optimize_context         = _4_engine.optimize_context
FilterRules              = _4_rules.FilterRules
RoutingRules             = _4_rules.RoutingRules
store_meter              = _5_meter.store_meter
get_meter                = _5_meter.get_meter
get_tenant_usage         = _5_meter.get_tenant_usage
get_trend_data           = _5_meter.get_trend_data
get_tenant_current_usage = _5_meter.get_tenant_current_usage
classify_task            = _5_tc.classify_task
from .access import get_tenant_registry_entry, resolve_query_access
from .backends.factory import create_backend, get_memory_backend, set_memory_backend
from .backends.base import MemoryBackend, MemorySearchRequest, MemoryWriteRequest

# Lazy backend initialization
_initialized_backend: Optional[MemoryBackend] = None


def _get_backend() -> MemoryBackend:
    """Get or create the memory backend instance (lazy initialization)"""
    global _initialized_backend
    if _initialized_backend is None:
        _initialized_backend = create_backend(config.memory_backend)
    return _initialized_backend

# 日志配置
loguru.logger.remove()
loguru.logger.add(
    sys.stderr,
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"
)

run_startup_probe()


class SupportAPIError(Exception):
    """统一的售后可追踪错误。"""

    def __init__(self, status_code: int, payload: Dict[str, Any]):
        self.status_code = status_code
        self.payload = payload
        super().__init__(payload.get("message") or payload.get("detail") or "support_api_error")


_default_cors_origins = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
]
_configured_cors_origins = [
    origin.strip()
    for origin in os.getenv("OMNIMEMORA_ALLOWED_CONTROL_ORIGINS", "").split(",")
    if origin.strip()
]

app = FastAPI(
    title="Memory Adapter v2.2",
    description="memory backend 中间层：标准化 → 过滤 → 去重 → 限流 → 路由 → 转换",
    version="2.2.0"
)

# CORS 中间件：18011 is a local product ingress; do not expose control actions
# to arbitrary browser origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_configured_cors_origins or _default_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 18011 assembly convergence (Batch 3B):
# group router registration by responsibility while preserving existing routes.
import importlib


def _register_product_data_path(app: FastAPI) -> None:
    """Register product data path surfaces (ingress + product protocol)."""
    _llm_proxy_mod = importlib.import_module("5_connectors.adapter.llm_proxy")
    _mcp_surface_mod = importlib.import_module("5_connectors.adapter.mcp_surface")
    app.include_router(_llm_proxy_mod.router, prefix="")
    app.include_router(_mcp_surface_mod.router, prefix="")


def _register_control_plane(app: FastAPI) -> None:
    """Register control-plane surfaces."""
    _agent_control_api_mod = importlib.import_module("5_connectors.adapter.agent_control_api")
    app.include_router(_agent_control_api_mod.router, prefix="")


def _register_read_model_and_diagnostics(app: FastAPI) -> None:
    """Register read-model / diagnostics surfaces."""
    _status_api_mod = importlib.import_module("5_connectors.adapter.status_api")
    _data_lifecycle_api_mod = importlib.import_module("5_connectors.adapter.data_lifecycle_api")
    _diagnostics_surface_mod = importlib.import_module("5_connectors.adapter.diagnostics_surface")
    _usage_surface_mod = importlib.import_module("5_connectors.adapter.usage_surface")
    _scope_surface_mod = importlib.import_module("5_connectors.adapter.scope_surface")
    _billing_surface_mod = importlib.import_module("5_connectors.adapter.billing_surface")
    _cloud_surface_mod = importlib.import_module("5_connectors.adapter.cloud_surface")
    app.include_router(_status_api_mod.router, prefix="")
    app.include_router(_data_lifecycle_api_mod.router, prefix="")
    app.include_router(_diagnostics_surface_mod.router, prefix="")
    app.include_router(_usage_surface_mod.router, prefix="")
    app.include_router(_scope_surface_mod.router, prefix="")
    app.include_router(_billing_surface_mod.router, prefix="")
    app.include_router(_cloud_surface_mod.router, prefix="")


_register_product_data_path(app)
_register_control_plane(app)
_register_read_model_and_diagnostics(app)

_dlp_scheduler = None


_ULTRA_FAST_INTERNAL_GET_PATHS = frozenset(
    {
        "/health",
        "/metrics/summary",
        "/metrics/summary_24h",
        "/metrics/core_capabilities",
        "/metrics/core_capabilities/trend",
        "/metrics/recent_requests",
        "/usage/token-savings",
        "/usage/token-savings/trend",
        "/data-lifecycle/status",
        "/data-lifecycle/meter-storage/status",
        "/data-lifecycle/meter-storage/parity",
    }
)


def _skip_default_trace_write(request: Request) -> bool:
    if request.method.upper() != "GET":
        return False
    request_path = str(getattr(getattr(request, "url", None), "path", "") or "")
    return request_path in _ULTRA_FAST_INTERNAL_GET_PATHS


@app.on_event("startup")
async def _startup_data_lifecycle_scheduler() -> None:
    global _dlp_scheduler
    scheduler_mod = __import__("5_connectors.adapter.data_lifecycle.scheduler", fromlist=["dummy"])
    _dlp_scheduler = scheduler_mod.DataLifecycleScheduler()
    _dlp_scheduler.start()


@app.on_event("shutdown")
async def _shutdown_data_lifecycle_scheduler() -> None:
    global _dlp_scheduler
    if _dlp_scheduler is None:
        return
    await _dlp_scheduler.stop()
    _dlp_scheduler = None

@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    context = ensure_request_context(request)
    skip_trace_write = _skip_default_trace_write(request)
    if config.trace_events_enabled and not skip_trace_write:
        append_trace_event(
            build_trace_event(
                trace_id=context["trace_id"],
                request_id=context["request_id"],
                stage="entry",
                path=context["path"],
                status="received",
                agent_id=request.headers.get("x-omnimemora-agent") or "unknown",
                details={
                    "method": request.method,
                    "path_mode": config.path_mode,
                    "primary_ratio": config.primary_ratio,
                },
            )
        )
    response = await call_next(request)
    response.headers["X-Request-ID"] = context["request_id"]
    response.headers[REQUEST_HEADER] = context["request_id"]
    response.headers[TRACE_HEADER] = context["trace_id"]
    request_path = str(getattr(getattr(request, "url", None), "path", "") or "")
    if is_quota_related_path(request_path):
        content_length = response.headers.get("content-length", "")
        action = classify_quota_observation(request, request_path, response.status_code, content_length)
        upstream_url = upstream_url_for_observation(request, request_path)
        loguru.logger.info(
            "[QUOTA_PATH_OBS] "
            f"request_id={context['request_id']} "
            f"method={request.method} "
            f"path={request_path} "
            f"status_code={response.status_code} "
            f"upstream_url={upstream_url} "
            f"action={action}"
        )
    if config.trace_events_enabled and not skip_trace_write:
        append_trace_event(
            build_trace_event(
                trace_id=context["trace_id"],
                request_id=context["request_id"],
                stage="entry",
                path=context["path"],
                status="ok" if response.status_code < 400 else "error",
                agent_id=request.headers.get("x-omnimemora-agent") or "unknown",
                error_type=None if response.status_code < 400 else f"http_{response.status_code}",
                details={"status_code": response.status_code},
            )
        )
    return response



# ==================== MCP Protocol Endpoints (for OpenClaw integration) ====================

import asyncio
import json as _json

_explicit_adapter_url = os.getenv("OMNIMEMORA_ADAPTER_URL", "").strip().rstrip("/")
if _explicit_adapter_url:
    _adapter_http_base = _explicit_adapter_url
else:
    # Important: uvicorn port can be overridden by PORT at process start,
    # while config.adapter_port may still keep its static default.
    _resolved_port = os.getenv("PORT", "18011").strip() or "18011"
    _resolved_host = os.getenv("OMNIMEMORA_ADAPTER_HOST", "127.0.0.1").strip() or "127.0.0.1"
    if _resolved_host in ("0.0.0.0", "::"):
        _resolved_host = "127.0.0.1"
    _adapter_http_base = f"http://{_resolved_host}:{_resolved_port}"


@app.exception_handler(SupportAPIError)
async def support_api_error_handler(request: Request, exc: SupportAPIError):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.payload,
        headers={"X-Request-ID": get_request_id(request) or ""},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    payload = build_support_payload(
        request,
        "ADAPTER_REQUEST_VALIDATION_FAILED",
        "Request validation failed",
        operation="request_validation",
        detail=str(exc),
        retryable=False,
    )
    return JSONResponse(
        status_code=422,
        content=payload,
        headers={"X-Request-ID": get_request_id(request) or ""},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    payload = build_support_payload(
        request,
        "ADAPTER_INTERNAL_ERROR",
        "Unhandled adapter error",
        operation="unhandled_exception",
        detail=f"{type(exc).__name__}: {exc}",
        retryable=False,
    )
    log_error("Unhandled adapter exception", payload["detail"])
    return JSONResponse(
        status_code=500,
        content=payload,
        headers={"X-Request-ID": get_request_id(request) or ""},
    )


# ==================== 限流器 ====================

class RateLimiter:
    """滑动窗口限流器"""

    def __init__(self, max_per_minute: int = 100):
        self.max_per_minute = max_per_minute
        self.requests = deque()

    def is_allowed(self) -> bool:
        """检查是否允许写入"""
        now = datetime.now().timestamp()
        one_minute_ago = now - 60

        # 清理超过 1 分钟的请求
        while self.requests and self.requests[0] < one_minute_ago:
            self.requests.popleft()

        # 检查是否超过限制
        if len(self.requests) >= self.max_per_minute:
            return False

        # 记录本次请求
        self.requests.append(now)
        return True

    def get_current_count(self) -> int:
        """获取当前分钟内的请求数"""
        now = datetime.now().timestamp()
        one_minute_ago = now - 60

        # 清理超过 1 分钟的请求
        while self.requests and self.requests[0] < one_minute_ago:
            self.requests.popleft()

        return len(self.requests)


# 全局限流器
_rate_limiter = RateLimiter(max_per_minute=config.rate_limit_per_minute)

configure_usage_surface(
    config_obj=config,
    get_tenant_usage_fn=get_tenant_usage,
    get_trend_data_fn=get_trend_data,
    get_meter_fn=get_meter,
)

configure_scope_surface(
    config_obj=config,
    scope_registry_path=os.path.expanduser("~/.omnimemora/config/scope_registry.json"),
)

configure_billing_surface(
    config_obj=config,
    get_tenant_usage_fn=get_tenant_usage,
    get_tenant_current_usage_fn=get_tenant_current_usage,
)

configure_cloud_surface(config_obj=config)


# ==================== 请求/响应模型 ====================

class MemoryRequest(BaseModel):
    """记忆写入请求"""
    agent: str = "unknown"
    type: str = "general"
    content: str
    tags: List[str] = []
    memory_type: Optional[str] = None  # 可显式指定
    timestamp: Optional[int] = None


class MemoryResponse(BaseModel):
    """记忆写入响应"""
    status: str  # "stored", "skipped", "duplicate", "rate_limited", "error"
    reason: Optional[str] = None
    memory_id: Optional[str] = None
    memory_type: Optional[str] = None
    memory_level: Optional[str] = None
    memory_expire_at: Optional[int] = None
    score: Optional[int] = None
    is_failure: Optional[bool] = None  # 新增：是否失败经验
    uri: Optional[str] = None  # 兼容 OpenClaw 插件期望字段
    request_id: Optional[str] = None
    error_code: Optional[str] = None
    support: Optional[Dict[str, Any]] = None


class RetrieveRequest(BaseModel):
    """记忆查询请求"""
    query: Optional[str] = None
    uri: Optional[str] = None
    agent: Optional[str] = None  # Agent 隔离
    memory_type: Optional[str] = None  # 记忆类型过滤
    memory_level: Optional[str] = None  # 记忆等级过滤
    include_expired: bool = False  # 是否包含过期记忆
    limit: int = 10
    scoreThreshold: Optional[float] = None


class DeleteRequest(BaseModel):
    """按 URI 删除记忆"""
    uri: str


class SnapshotRequest(BaseModel):
    """生成 MEMORY.md 启动快照"""
    agent: str = "supervisor"
    limit: int = 200


class MemoryQueryRequest(BaseModel):
    """V2: Unified memory query request with optimization."""
    tenant: str
    user: str
    agent: str = "supervisor"
    query: str
    context: Optional[Dict[str, Any]] = None
    options: Optional[Dict[str, Any]] = None
    # Decision Log identity binding
    agent_id: str = "unknown"
    workspace_id: str = "unknown"
    scope: str = "workspace"


class MemoryQueryResponse(BaseModel):
    """V2: Unified memory query response with token savings."""
    request_id: str
    selected_memories: List[Dict[str, Any]]
    packed_context: str
    memory_tokens_injected: int
    tokens_saved_estimate: int
    savings_ratio: float
    explanation: Dict[str, Any]
    meter_artifact: Dict[str, Any]
    # Policy v1: Task classification & context bypass observability
    task_type: str = "continuation"
    context_bypass: bool = False
    matched_keywords: List[str] = []
    # Policy v1: Active policy version for wrapper feedback
    policy_version: str = ""


# ==================== 工具函数 ====================

SUPPORT_SCHEMA_VERSION = "ov-support/v1"
SUPPORT_ERROR_CATALOG: Dict[str, Dict[str, Any]] = {
    "ADAPTER_BAD_REQUEST": {
        "category": "input",
        "severity": "low",
        "retryable": False,
        "suggested_action": "修正请求参数后重试。",
    },
    "ADAPTER_REQUEST_VALIDATION_FAILED": {
        "category": "input",
        "severity": "low",
        "retryable": False,
        "suggested_action": "按接口要求补齐必填字段并修正字段类型。",
    },
    "ADAPTER_SEARCH_FAILED": {
        "category": "dependency",
        "severity": "medium",
        "retryable": True,
        "suggested_action": "检查 memory backend 搜索状态、索引窗口与 Adapter health。",
    },
    "ADAPTER_READ_FAILED": {
        "category": "dependency",
        "severity": "medium",
        "retryable": True,
        "suggested_action": "检查下游读取接口与目标 URI 是否仍存在。",
    },
    "ADAPTER_DELETE_FAILED": {
        "category": "dependency",
        "severity": "medium",
        "retryable": True,
        "suggested_action": "检查下游删除接口、URI 正确性与命名空间状态。",
    },
    "ADAPTER_SNAPSHOT_FAILED": {
        "category": "dependency",
        "severity": "medium",
        "retryable": True,
        "suggested_action": "检查 memory backend 文件系统可用性与命名空间遍历状态。",
    },
    "ADAPTER_NAMESPACE_PREPARE_FAILED": {
        "category": "runtime",
        "severity": "high",
        "retryable": True,
        "suggested_action": "检查命名空间根路径配置与 memory backend 文件系统写权限。",
    },
    "ADAPTER_MEMORY_BACKEND_UPLOAD_FAILED": {
        "category": "dependency",
        "severity": "high",
        "retryable": True,
        "suggested_action": "检查 memory backend 上传接口与临时存储状态。",
    },
    "ADAPTER_MEMORY_BACKEND_COMMIT_FAILED": {
        "category": "dependency",
        "severity": "high",
        "retryable": True,
        "suggested_action": "检查 memory backend 提交链路、commit timeout 与上游负载。",
    },
    "ADAPTER_MEMORY_BACKEND_UNAVAILABLE": {
        "category": "dependency",
        "severity": "high",
        "retryable": True,
        "suggested_action": "确认 memory backend 服务在线且网络可达。",
    },
    "ADAPTER_MEMORY_BACKEND_TIMEOUT": {
        "category": "dependency",
        "severity": "high",
        "retryable": True,
        "suggested_action": "提升相关 timeout 或排查 memory backend 提交/索引时延。",
    },
    "ADAPTER_INTERNAL_ERROR": {
        "category": "runtime",
        "severity": "high",
        "retryable": False,
        "suggested_action": "记录 request_id 并结合 Adapter 日志做进一步排障。",
    },
    "ADAPTER_QUOTA_EXCEEDED": {
        "category": "quota",
        "severity": "high",
        "retryable": False,
        "suggested_action": "升级订阅计划或等待下个计费周期重置配额。",
    },
}

configure_diagnostics_surface(
    config_obj=config,
    get_backend_fn=_get_backend,
    get_dedup_cache_fn=get_dedup_cache,
    rate_limiter=_rate_limiter,
    adapter_hostname=_adapter_hostname,
    adapter_started_at=_adapter_started_at,
    agent_metrics_module=_5_agnet_m,
    agent_identity_module=_5_agent_id,
    get_meter_fn=get_meter,
    support_schema_version=SUPPORT_SCHEMA_VERSION,
    support_error_catalog=SUPPORT_ERROR_CATALOG,
)


def get_request_id(request: Optional[Request]) -> Optional[str]:
    if request is None:
        return None
    return getattr(getattr(request, "state", None), "request_id", None)


def build_support_payload(
    request: Optional[Request],
    code: str,
    message: str,
    *,
    operation: str,
    detail: Optional[str] = None,
    upstream_status: Optional[int] = None,
    retryable: Optional[bool] = None,
    suggested_action: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    catalog = SUPPORT_ERROR_CATALOG.get(code, SUPPORT_ERROR_CATALOG["ADAPTER_INTERNAL_ERROR"])
    effective_retryable = catalog["retryable"] if retryable is None else retryable
    effective_suggested_action = suggested_action or catalog["suggested_action"]
    payload: Dict[str, Any] = {
        "schema_version": SUPPORT_SCHEMA_VERSION,
        "status": "error",
        "message": message,
        "detail": detail or message,
        "error_code": code,
        "request_id": get_request_id(request),
        "support": {
            "category": catalog["category"],
            "severity": catalog["severity"],
            "retryable": effective_retryable,
            "operation": operation,
            "suggested_action": effective_suggested_action,
        },
    }
    if upstream_status is not None:
        payload["support"]["upstream_status"] = upstream_status
    if extra:
        payload["support"]["context"] = extra
    return payload


def build_memory_error_response(
    request: Optional[Request],
    code: str,
    reason: str,
    *,
    operation: str,
    detail: Optional[str] = None,
    suggested_action: Optional[str] = None,
    upstream_status: Optional[int] = None,
) -> MemoryResponse:
    support_payload = build_support_payload(
        request,
        code,
        detail or reason,
        operation=operation,
        detail=detail or reason,
        upstream_status=upstream_status,
        suggested_action=suggested_action,
    )
    return MemoryResponse(
        status="error",
        reason=reason,
        request_id=get_request_id(request),
        error_code=code,
        support=support_payload["support"],
    )


def raise_support_api_error(
    request: Optional[Request],
    status_code: int,
    code: str,
    message: str,
    *,
    operation: str,
    detail: Optional[str] = None,
    upstream_status: Optional[int] = None,
    retryable: Optional[bool] = None,
    suggested_action: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    payload = build_support_payload(
        request,
        code,
        message,
        operation=operation,
        detail=detail,
        upstream_status=upstream_status,
        retryable=retryable,
        suggested_action=suggested_action,
        extra=extra,
    )
    raise SupportAPIError(status_code=status_code, payload=payload)

def log_stored(Agent: str, memory_type: str, memory_level: str, score: int, is_failure: bool = False):
    """记录存储成功"""
    failure_tag = " [FAILURE_EXPERIENCE]" if is_failure else ""
    loguru.logger.info(f"[STORED]{failure_tag} agent={Agent}, type={memory_type}, level={memory_level}, score={score}")


def log_filtered(reason: str, content_preview: str = ""):
    """记录过滤原因"""
    preview = content_preview[:50] + "..." if len(content_preview) > 50 else content_preview
    loguru.logger.warning(f"[FILTERED] reason={reason}, preview={preview}")


def log_error(error: str, detail: str = ""):
    """记录错误"""
    loguru.logger.error(f"[ERROR] {error}: {detail}")


def build_timeout(total_seconds: float) -> httpx.Timeout:
    """统一构建下游请求 timeout，避免散落的硬编码常量。"""
    total = max(total_seconds, config.memory_backend_connect_timeout_seconds)
    return httpx.Timeout(
        timeout=total,
        connect=min(config.memory_backend_connect_timeout_seconds, total),
        read=total,
        write=total,
        pool=min(config.memory_backend_connect_timeout_seconds, total),
    )


def log_slow_request(operation: str, elapsed_ms: float, timeout_seconds: float):
    """记录慢请求，帮助后续收敛 timeout 与索引延迟。"""
    if elapsed_ms >= config.slow_request_threshold_ms:
        loguru.logger.warning(
            f"[SLOW_REQUEST] op={operation}, elapsed_ms={elapsed_ms:.0f}, timeout_s={timeout_seconds}"
        )


def emit_decision_log(
    query: str,
    task_type: str,
    context_bypass: bool,
    packed_context: str,
    memory_tokens_injected: int,
    baseline_tokens_estimate: int,
    actual_tokens_estimate: int,
    saved_tokens_estimate: float,
    savings_ratio: float,
    matched_keywords: List[str],
    selected_memory_count: int,
    request_id: str,
    agent: str,
    tenant: str,
    agent_id: str = "unknown",
    workspace_id: str = "unknown",
    scope: str = "workspace",
):
    """
    Memora Decision Log / Context Decision Event
    --------------------------------------------
    记录 OmniMemora 服务端的判断与计量结果。

    定位：
    - 这是"服务端决策日志"，不是完整的"真实使用日志"
    - 表示 OmniMemora adapter 做了什么判断、节省了多少
    - 完整的 Real Usage Log（含用户主观评价）由 wrapper 层（memrun/ccm/ocm）补充

    输出到 stdout，每条独立一行，无前缀后缀。
    """
    import json

    log_entry = {
        # --- 核心判断 ---
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "query": query[:200] if query else "",
        "task_type": task_type,
        "context_bypass": context_bypass,

        # --- 服务端计量 ---
        "context_stats": {
            "packed_context_length": len(packed_context),
            "memory_tokens_injected": memory_tokens_injected,
            "baseline_tokens_estimate": baseline_tokens_estimate,
            "actual_tokens_estimate": actual_tokens_estimate,
            "saved_tokens_estimate": int(saved_tokens_estimate),
            "savings_ratio": round(savings_ratio, 3),
        },

        # --- 主观字段：adapter 层留空，由 wrapper 补 ---
        "execution_feedback": None,    # ← wrapper 层填充
        "subjective_score": None,       # ← wrapper 层填充（用户反馈）

        # --- 服务端元信息（身份绑定：来自 API 入参）---
        "_meta": {
            "request_id": request_id,
            "agent": agent,
            "tenant": tenant,
            "agent_id": agent_id,
            "workspace_id": workspace_id,
            "scope": scope,
            "matched_keywords": matched_keywords,
        },
    }

    # 直接打印 JSON，不加任何前缀/后缀
    print(json.dumps(log_entry, ensure_ascii=False))


async def viking_request(
    method: str,
    path: str,
    *,
    operation: str,
    timeout_seconds: float,
    retryable: bool = True,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    **kwargs,
) -> httpx.Response:
    """统一封装对 memory backend 的下游调用，提供分层超时与有限重试。"""
    attempts = 1 + max(0, config.memory_backend_retry_attempts if retryable else 0)
    backoff = max(0.0, config.memory_backend_retry_backoff_seconds)
    last_exc: Optional[Exception] = None
    request_headers = build_headers_with_tenant(tenant_id, user_id) if tenant_id and user_id else build_headers()

    for attempt in range(1, attempts + 1):
        started = datetime.now().timestamp()
        try:
            async with httpx.AsyncClient(timeout=build_timeout(timeout_seconds)) as client:
                response = await client.request(
                    method,
                    f"{config.memory_backend_url}{path}",
                    headers=request_headers,
                    **kwargs,
                )
            elapsed_ms = (datetime.now().timestamp() - started) * 1000
            log_slow_request(operation, elapsed_ms, timeout_seconds)

            if retryable and response.status_code in {502, 503, 504} and attempt < attempts:
                loguru.logger.warning(
                    f"[RETRYABLE_STATUS] op={operation}, attempt={attempt}/{attempts}, status={response.status_code}"
                )
                await asyncio.sleep(backoff * attempt)
                continue
            return response
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
            last_exc = exc
            loguru.logger.warning(
                f"[RETRYABLE_ERROR] op={operation}, attempt={attempt}/{attempts}, error={type(exc).__name__}: {exc}"
            )
            if attempt < attempts:
                await asyncio.sleep(backoff * attempt)
                continue
            raise

    if last_exc:
        raise last_exc
    raise RuntimeError(f"unreachable_viking_request_state:{operation}")


def build_headers() -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if config.memory_backend_api_key:
        headers["X-API-Key"] = config.memory_backend_api_key
    return headers


def build_headers_with_tenant(tenant_id: str, user_id: str) -> Dict[str, str]:
    headers = build_headers()
    headers["X-OmniMemora-Tenant"] = tenant_id
    headers["X-OmniMemora-User"] = user_id
    return headers


def resolve_tenant_identity(request: Request) -> tuple[Optional[str], Optional[str]]:
    state = getattr(request, "state", None)
    override_tenant = getattr(state, "v2_tenant_override", None) if state else None
    override_user = getattr(state, "v2_user_override", None) if state else None
    if override_tenant and override_user:
        return override_tenant, override_user

    header_tenant = request.headers.get("X-OmniMemora-Tenant")
    header_user = request.headers.get("X-OmniMemora-User")
    if header_tenant and header_user:
        return header_tenant, header_user

    return None, None


def normalize_viking_uri(uri: str) -> str:
    normalized = (uri or "").strip()
    if normalized == "viking://":
        return normalized
    return normalized.rstrip("/")


def split_viking_uri(uri: str) -> List[str]:
    normalized = normalize_viking_uri(uri)
    if not normalized.startswith("viking://"):
        return []
    suffix = normalized[len("viking://") :]
    return [segment for segment in suffix.split("/") if segment]


def join_viking_uri(segments: List[str]) -> str:
    if not segments:
        return "viking://"
    return "viking://" + "/".join(segments)


def sanitize_path_segment(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in (value or "").strip())
    safe = safe.strip("-_")
    return safe or "unknown"


def build_memory_root_prefix() -> str:
    return normalize_viking_uri(config.viking_memory_namespace_root)


def build_agent_memory_prefix(agent: str) -> str:
    agent_segment = sanitize_path_segment(agent)
    return f"{build_memory_root_prefix()}/{agent_segment}"


def build_memory_type_prefix(agent: str, memory_type: str) -> str:
    prefix = build_agent_memory_prefix(agent)
    type_segment = sanitize_path_segment(memory_type or "general")
    return f"{prefix}/{type_segment}"


def build_memory_resource_uri(agent: str, memory_type: str) -> str:
    prefix = build_memory_type_prefix(agent, memory_type)
    return f"{prefix}/mem-{uuid4().hex}.md"


def map_memory_level(level: Any) -> Optional[int]:
    """统一将 L1/L2/L3 或数字层级映射为插件可用的 1/2/3。"""
    if level is None:
        return None
    if isinstance(level, int):
        return level
    if isinstance(level, float):
        return int(level)
    if isinstance(level, str):
        normalized = level.strip().upper()
        if normalized.startswith("L") and normalized[1:].isdigit():
            return int(normalized[1:])
        if normalized.isdigit():
            return int(normalized)
    return None


def get_nested(data: Dict[str, Any], *paths: str) -> Any:
    for path in paths:
        value: Any = data
        ok = True
        for part in path.split("."):
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                ok = False
                break
        if ok:
            return value
    return None


def extract_response_error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        return (response.text or "").strip()

    if isinstance(payload, dict):
        candidates = [
            payload.get("detail"),
            payload.get("error"),
            payload.get("message"),
            get_nested(payload, "result.error"),
            get_nested(payload, "result.message"),
        ]
        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()

    return (response.text or "").strip()


def is_missing_namespace_error(status_code: int, detail: str) -> bool:
    normalized = (detail or "").lower()
    if status_code == 404:
        return True
    patterns = (
        "no such directory",
        "no such file or directory",
        "not found",
    )
    return any(pattern in normalized for pattern in patterns)


def extract_memory_items(payload: Any) -> List[Dict[str, Any]]:
    """兼容多种 Viking 返回结构，提取记忆列表。"""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []

    collected: List[Dict[str, Any]] = []
    candidates = [
        payload.get("memories"),
        get_nested(payload, "result.memories"),
        payload.get("resources"),
        get_nested(payload, "result.resources"),
        payload.get("items"),
        get_nested(payload, "result.items"),
        payload.get("results"),
        get_nested(payload, "result.results"),
    ]
    for candidate in candidates:
        if isinstance(candidate, list):
            collected.extend(item for item in candidate if isinstance(item, dict))
    return collected


def to_plugin_memory(item: Dict[str, Any]) -> Dict[str, Any]:
    """把底层返回统一成 OpenClaw 插件当前消费的数据形状。"""
    metadata = item.get("metadata", {}) if isinstance(item.get("metadata"), dict) else {}
    uri = (
        item.get("uri")
        or item.get("id")
        or metadata.get("uri")
        or metadata.get("memory_id")
        or ""
    )
    category = (
        item.get("category")
        or metadata.get("type")
        or metadata.get("memory_type")
        or item.get("context_type")
        or "memory"
    )
    raw_abstract = (
        item.get("abstract")
        or item.get("summary")
        or item.get("content")
        or item.get("text")
        or ""
    )
    raw_content = item.get("content") or item.get("text") or raw_abstract
    abstract = extract_memory_body(raw_abstract) or raw_abstract
    content = extract_memory_body(raw_content) or raw_content
    score = item.get("score")
    if score is None:
        score = item.get("similarity")
    level = (
        map_memory_level(item.get("level"))
        or map_memory_level(item.get("memory_level"))
        or map_memory_level(metadata.get("memory_level"))
        or (2 if item.get("is_leaf") else 1)
    )

    return {
        "uri": uri,
        "content": content,
        "abstract": abstract,
        "score": score,
        "category": category,
        "level": level,
        "metadata": metadata,
    }


def content_matches_query(content: str, query: str) -> bool:
    normalized_content = normalize_fact_text(content).lower()
    normalized_query = normalize_fact_text(query).lower()
    return bool(normalized_query) and normalized_query in normalized_content


async def list_directory_entries(
    uri: str,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    encoded_uri = quote(uri, safe="")
    try:
        response = await viking_request(
            "GET",
            f"/api/v1/fs/ls?uri={encoded_uri}",
            operation="list_directory_entries",
            timeout_seconds=config.memory_backend_snapshot_timeout_seconds,
            retryable=True,
            tenant_id=tenant_id,
            user_id=user_id,
        )
    except Exception as exc:
        loguru.logger.warning(f"[LIST_DIRECTORY_ERROR] uri={uri}, error={type(exc).__name__}: {exc}")
        return []

    if not response.is_success:
        detail = extract_response_error_detail(response)
        if is_missing_namespace_error(response.status_code, detail):
            loguru.logger.info(f"[NAMESPACE_MISSING] uri={uri}, op=list_directory_entries")
            return []
        loguru.logger.warning(
            f"[LIST_DIRECTORY_FAILED] uri={uri}, status={response.status_code}, detail={compact_fact_text(detail, 120)}"
        )
        return []

    payload = response.json()
    result = get_nested(payload, "result")
    if not isinstance(result, list):
        return []
    return [item for item in result if isinstance(item, dict)]


async def namespace_exists(
    uri: str,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> bool:
    normalized = normalize_viking_uri(uri)
    segments = split_viking_uri(normalized)
    if not segments:
        return False
    if normalized == "viking://resources":
        return True

    current_parent = "viking://resources"
    for index in range(2, len(segments) + 1):
        current_uri = join_viking_uri(segments[:index])
        entries = await list_directory_entries(current_parent, tenant_id=tenant_id, user_id=user_id)
        if not any(
            normalize_viking_uri(str(item.get("uri", ""))) == current_uri
            for item in entries
        ):
            return False
        current_parent = current_uri
    return True


async def mkdir_uri(uri: str, tenant_id: Optional[str] = None, user_id: Optional[str] = None) -> bool:
    try:
        response = await viking_request(
            "POST",
            "/api/v1/fs/mkdir",
            operation="mkdir_uri",
            timeout_seconds=config.memory_backend_resolve_timeout_seconds,
            retryable=False,
            tenant_id=tenant_id,
            user_id=user_id,
            json={"uri": uri},
        )
    except Exception as exc:
        loguru.logger.warning(f"[MKDIR_ERROR] uri={uri}, error={type(exc).__name__}: {exc}")
        return False

    if response.is_success:
        loguru.logger.info(f"[NAMESPACE_CREATED] uri={uri}")
        return True

    detail = extract_response_error_detail(response)
    if "exist" in detail.lower():
        return True

    loguru.logger.warning(
        f"[MKDIR_FAILED] uri={uri}, status={response.status_code}, detail={compact_fact_text(detail, 120)}"
    )
    return False


async def ensure_namespace_tree(
    uri: str,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> bool:
    normalized = normalize_viking_uri(uri)
    segments = split_viking_uri(normalized)
    if len(segments) < 2:
        return False

    current_parent = "viking://resources"
    for index in range(2, len(segments) + 1):
        current_uri = join_viking_uri(segments[:index])
        entries = await list_directory_entries(current_parent, tenant_id=tenant_id, user_id=user_id)
        if any(
            normalize_viking_uri(str(item.get("uri", ""))) == current_uri
            for item in entries
        ):
            current_parent = current_uri
            continue
        if not await mkdir_uri(current_uri, tenant_id=tenant_id, user_id=user_id):
            return False
        current_parent = current_uri
    return True


async def fallback_scan_memories(
    agent: str,
    query: str,
    limit: int,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """当上游搜索结果不稳定时，扫描最近资源做内容匹配降级。"""
    root_uri = build_agent_memory_prefix(agent or "unknown")
    if not await namespace_exists(root_uri, tenant_id=tenant_id, user_id=user_id):
        return []
    leaf_uris = await collect_memory_leaf_uris(
        root_uri,
        tenant_id=tenant_id,
        user_id=user_id,
        max_files=max(limit, config.search_fallback_scan_limit),
    )
    matches: List[Dict[str, Any]] = []

    for uri in leaf_uris:
        content = await read_clean_resource_content(uri, tenant_id=tenant_id, user_id=user_id)
        if not content or not content_matches_query(content, query):
            continue
        matches.append(
            {
                "uri": uri,
                "content": content,
                "abstract": compact_fact_text(content, max_len=240),
                "score": 1.0,
                "category": "resource",
                "level": 2 if PurePosixPath(uri).name.startswith("upload_") else 1,
                "metadata": {"fallback": "content_scan", "agent": agent, "tenant_id": tenant_id},
            }
        )
        if len(matches) >= limit:
            break

    if matches:
        loguru.logger.warning(
            f"[SEARCH_FALLBACK] agent={agent}, query={compact_fact_text(query, 80)}, matches={len(matches)}"
        )
    return matches


async def resolve_leaf_uri(
    root_uri: str,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> str:
    """尝试从资源根目录解析真正可读的叶子文件 URI。"""
    try:
        if root_uri.startswith(build_memory_root_prefix()) and not await namespace_exists(
            root_uri,
            tenant_id=tenant_id,
            user_id=user_id,
        ):
            return root_uri
        encoded_uri = quote(root_uri, safe="")
        response = await viking_request(
            "GET",
            f"/api/v1/fs/tree?uri={encoded_uri}",
            operation="resolve_leaf_uri",
            timeout_seconds=config.memory_backend_resolve_timeout_seconds,
            retryable=True,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        if not response.is_success:
            return root_uri
        payload = response.json()
        result = get_nested(payload, "result")
        if not isinstance(result, list):
            return root_uri
        leaf_candidates = [
            item.get("uri")
            for item in result
            if isinstance(item, dict) and not item.get("isDir") and item.get("uri")
        ]
        if leaf_candidates:
            return leaf_candidates[0]
    except Exception:
        pass
    return root_uri


def extract_memory_body(content: Optional[str]) -> Optional[str]:
    """从资源包装文档中提取纯记忆正文。"""
    if not isinstance(content, str):
        return None

    text = content.strip()
    if not text:
        return None

    if text.startswith("# Memory"):
        lines = text.splitlines()
        if lines and lines[0].strip() == "# Memory":
            text = "\n".join(lines[1:]).lstrip()

        for delimiter in ("\n\n---\n", "\n---\n"):
            if delimiter in text:
                text = text.split(delimiter, 1)[0].rstrip()
                break

    return text.strip() or None


def is_derived_resource_uri(uri: str) -> bool:
    """过滤 memory backend 自动生成的摘要/概览资源，避免污染召回。"""
    if not isinstance(uri, str) or not uri:
        return False

    name = PurePosixPath(uri).name
    return name.startswith(".") or name in {".overview.md", ".abstract.md"}


def normalize_fact_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def compact_fact_text(text: str, max_len: int = 180) -> str:
    normalized = normalize_fact_text(text)
    if len(normalized) <= max_len:
        return normalized
    return normalized[: max_len - 3].rstrip() + "..."


def classify_snapshot_fact(text: str) -> str:
    lowered = text.lower()
    if any(pattern in text for pattern in ("是用户", "用户是", "称呼", "叫做")) or "user is" in lowered:
        return "identity"
    if any(pattern in text for pattern in ("项目", "project", "创业", "赚钱系统", "自动化赚钱")):
        return "projects"
    if any(pattern in text for pattern in ("偏好", "期望", "希望", "协作", "风格", "启发", "务实", "高质量")):
        return "preferences"
    if any(pattern in text for pattern in ("决定", "约束", "规则", "必须", "不要", "应当", "以后")):
        return "decisions"
    return "facts"


def should_include_snapshot_fact(text: str) -> bool:
    lowered = text.lower()
    noisy_patterns = [
        "sender (untrusted metadata)",
        "a new session was started",
        "memory adapter should return only",
        "clean readback test",
        "formatting optimization test",
        "codex????",
        "request timeout after",
        "memory/read",
    ]
    if any(pattern in lowered for pattern in noisy_patterns):
        return False

    if "测试" in text and not any(keyword in text for keyword in ("用户", "项目", "偏好", "期望", "协作")):
        return False

    return True


def dedupe_facts(facts: List[str], limit: int) -> List[str]:
    seen = set()
    result: List[str] = []
    for fact in facts:
        normalized = normalize_fact_text(fact).lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(compact_fact_text(fact))
        if len(result) >= limit:
            break
    return result


def render_snapshot_markdown(agent: str, grouped_facts: Dict[str, List[str]], source_count: int) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def render_section(title: str, items: List[str], empty_text: str) -> List[str]:
        lines = [f"### {title}"]
        if items:
            lines.extend(f"- {item}" for item in items)
        else:
            lines.append(f"- {empty_text}")
        lines.append("")
        return lines

    lines: List[str] = [
        "## 启动必读摘要（自动生成）",
        f"- agent: {agent}",
        f"- generated_at: {generated_at}",
        f"- source_memories: {source_count}",
        "",
    ]
    lines.extend(render_section("用户身份与关系", grouped_facts["identity"], "暂无稳定身份事实"))
    lines.extend(render_section("当前项目", grouped_facts["projects"], "暂无高置信项目事实"))
    lines.extend(render_section("协作偏好", grouped_facts["preferences"], "暂无稳定协作偏好"))
    lines.extend(render_section("最近重要决策", grouped_facts["decisions"], "暂无高优先级决策"))
    lines.extend(render_section("其他关键事实", grouped_facts["facts"], "暂无补充关键事实"))
    return "\n".join(lines).strip() + "\n"


async def read_clean_resource_content(
    uri: str,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Optional[str]:
    """按 URI 读取资源正文，并去掉包装元数据。"""
    if not uri:
        return None

    encoded_uri = quote(uri, safe="")
    response = await viking_request(
        "GET",
        f"/api/v1/content/read?uri={encoded_uri}",
        operation="read_clean_resource_content",
        timeout_seconds=config.memory_backend_read_timeout_seconds,
        retryable=True,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    if not response.is_success:
        detail = extract_response_error_detail(response)
        if is_missing_namespace_error(response.status_code, detail):
            loguru.logger.info(f"[READ_MISSING] uri={uri}")
            return None
        loguru.logger.warning(
            f"[READ_FAILED] uri={uri}, status={response.status_code}, detail={compact_fact_text(detail, 120)}"
        )
        return None

    result = response.json()
    if not isinstance(result, dict):
        return None

    return extract_memory_body(result.get("result"))


async def collect_memory_leaf_uris(
    root_uri: str,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    max_files: int = 200,
) -> List[str]:
    collected: List[str] = []
    seen_dirs = set()
    stack = [root_uri]

    while stack and len(collected) < max_files:
        current = stack.pop()
        if current in seen_dirs:
            continue
        seen_dirs.add(current)

        for item in await list_directory_entries(current, tenant_id=tenant_id, user_id=user_id):
            uri = item.get("uri")
            if not isinstance(uri, str) or not uri:
                continue
            name = PurePosixPath(uri).name
            if item.get("isDir"):
                if not name.startswith("."):
                    stack.append(uri)
                continue
            if is_derived_resource_uri(uri):
                continue
            if name.startswith("upload_") and uri not in collected:
                collected.append(uri)
                if len(collected) >= max_files:
                    break

    return collected


def filter_expired_memories(memories: list, current_time: int = None) -> list:
    """
    过滤过期记忆
    在 read 接口调用
    """
    if current_time is None:
        current_time = int(datetime.now().timestamp())

    filtered = []
    for memory in memories:
        metadata = memory.get("metadata", {})
        expire_at = metadata.get("expire_at", -1)

        # -1 表示永久不过期
        if expire_at == -1:
            filtered.append(memory)
        # 0 表示已过期
        elif expire_at == 0:
            continue
        # 检查是否过期
        elif expire_at > current_time:
            filtered.append(memory)
        # 已过期
        else:
            loguru.logger.debug(f"[EXPIRED] memory_id={memory.get('id', 'unknown')}")

    return filtered


@app.post("/memory/write", response_model=MemoryResponse)
async def write_memory(request: MemoryRequest, http_request: Request):
    """
    主接口：写入记忆

    处理流程：
    1. 标准化 - 统一数据格式
    2. 过滤 - 判断是否需要存储
    3. 去重 - 检查内容是否重复
    4. 限流 - 检查写入频率
    5. 路由 - 决定记忆类型和等级（含失败经验检测）
    6. 转换 - 转换为 memory backend 格式（含 expire_at）
    7. 转发 - 发送到 memory backend
    """
    loguru.logger.info(f"[WRITE] Received from agent={request.agent}, type={request.type}, len={len(request.content)}")

    # ========== 1. 标准化 ==========
    data = normalize(request.dict())

    # ========== 2. 过滤 ==========
    should_store_result, reason = should_store(request.content, request.type)
    if not should_store_result:
        log_filtered(reason, request.content)
        return MemoryResponse(
            status="skipped",
            reason=reason,
            request_id=get_request_id(http_request),
        )

    # ========== 3. 去重 ==========
    if config.enable_deduplication:
        is_dup, content_id = check_duplicate(request.content)
        if is_dup:
            loguru.logger.info(f"[DUPLICATE] content_id={content_id[:8]}...")
            return MemoryResponse(
                status="duplicate",
                reason="content_already_exists",
                memory_id=content_id,
                request_id=get_request_id(http_request),
            )
    else:
        content_id = ""

    # ========== 4. 限流 ==========
    if config.enable_rate_limit:
        if not _rate_limiter.is_allowed():
            current = _rate_limiter.get_current_count()
            loguru.logger.warning(f"[RATE_LIMITED] current={current}, limit={config.rate_limit_per_minute}")
            return MemoryResponse(
                status="rate_limited",
                reason=f"rate_limit_exceeded: {current}/{config.rate_limit_per_minute}",
                request_id=get_request_id(http_request),
            )

    # ========== 5. 路由（含失败经验检测） ==========
    # 检测失败内容
    is_failure, failure_type = detect_failure_content(request.content)

    # 如果是失败内容，更新 type
    if is_failure:
        data["type"] = failure_type
        loguru.logger.info(f"[FAILURE_DETECTED] content contains error/failure, type={failure_type}")

    memory_type, memory_level, score = route_memory_type_and_level(request.content, data)
    loguru.logger.info(f"[ROUTE] type={memory_type}, level={memory_level}, score={score}")

    # 计算过期时间
    expire_at = calculate_expire_at(memory_level, request.timestamp)

    # ========== 6. 转换 ==========
    viking_payload = to_viking_format(
        data,
        memory_type=memory_type,
        memory_level=memory_level,
        score=score,
        content_id=content_id
    )
    resource_markdown = (
        f"# Memory\n\n"
        f"{request.content.strip()}\n\n"
        f"---\n"
        f"- agent: {request.agent}\n"
        f"- type: {data.get('type', request.type)}\n"
        f"- memory_type: {memory_type}\n"
        f"- memory_level: {memory_level}\n"
        f"- score: {score}\n"
        f"- expire_at: {expire_at}\n"
        f"- content_id: {content_id}\n"
        f"- adapter_version: 2.2.0\n"
    )

    # ========== 7. 转发 via backend interface ==========
    try:
        # Namespace prep via backend interface
        if not await _get_backend().prepare_namespace("agent", request.agent or "default"):
            return build_memory_error_response(
                http_request,
                "ADAPTER_NAMESPACE_PREPARE_FAILED",
                "viking_namespace_prepare_failed",
                operation="write_memory",
                detail="Failed to prepare the target agent namespace before commit.",
            )

        # Use backend interface for write (handles temp_upload + commit internally)
        write_request = MemoryWriteRequest(
            content=resource_markdown,
            scope="agent",
            scope_ref=request.agent or "default",
            metadata={
                "memory_type": memory_type,
                "memory_level": memory_level,
                "score": score,
                "expire_at": expire_at,
                "content_id": content_id,
                "agent": request.agent,
                "type": data.get("type", request.type),
            },
            overwrite=False,
        )
        record = await _get_backend().write(write_request)

        if config.enable_deduplication:
            add_to_dedup(request.content)

        # Backend returns memory_id
        stored_uri = record.memory_id or "unknown"

        log_stored(request.agent, memory_type, memory_level, score, is_failure)

        return MemoryResponse(
            status="stored",
            memory_id=stored_uri,
            uri=stored_uri,
            memory_type=memory_type,
            memory_level=memory_level,
            memory_expire_at=expire_at,
            score=score,
            is_failure=is_failure,
            request_id=get_request_id(http_request),
        )

    except httpx.ConnectError as e:
        log_error("Memory backend unavailable", str(e))
        return build_memory_error_response(
            http_request,
            "ADAPTER_MEMORY_BACKEND_UNAVAILABLE",
            "memory_backend_unavailable",
            operation="write_memory",
            detail=str(e),
        )
    except httpx.TimeoutException as e:
        log_error("Memory backend timeout", f"{type(e).__name__}: {e}")
        return build_memory_error_response(
            http_request,
            "ADAPTER_MEMORY_BACKEND_TIMEOUT",
            "memory_backend_timeout",
            operation="write_memory",
            detail=f"{type(e).__name__}: {e}",
        )
    except Exception as e:
        import traceback
        log_error("Unexpected error", f"{str(e)}\nStack trace:\n{traceback.format_exc()}")
        return build_memory_error_response(
            http_request,
            "ADAPTER_INTERNAL_ERROR",
            f"internal_error:{str(e)}",
            operation="write_memory",
            detail=str(e),
            suggested_action="记录 request_id 并检查 Adapter 运行日志中的对应堆栈。",
        )


configure_mcp_surface(
    adapter_http_base=_adapter_http_base,
    config_obj=config,
    agent_identity_module=_5_agent_id,
    memory_request_model=MemoryRequest,
    write_memory_fn=write_memory,
)


@app.post("/memory/search")
async def search_memory(request: RetrieveRequest, http_request: Request):
    """
    搜索记忆，返回与 OpenClaw 插件兼容的 memories[] 结构。
    """
    if not request.query:
        raise_support_api_error(
            http_request,
            400,
            "ADAPTER_BAD_REQUEST",
            "query is required",
            operation="search_memory",
            detail="query is required",
            retryable=False,
        )

    tenant_id, user_id = resolve_tenant_identity(http_request)

    # Use backend interface for search
    search_result = await _get_backend().search(
        MemorySearchRequest(
            query=request.query,
            limit=request.limit,
            scope="agent",
            scope_ref=request.agent or "default",
            score_threshold=request.scoreThreshold or 0.0,
        )
    )

    # Convert MemorySearchResult to plugin memory format
    # Backend returns MemoryRecord items; convert to dict format for to_plugin_memory
    raw_items = []
    for record in search_result.memories:
        raw_items.append({
            "uri": record.memory_id,
            "content": record.content,
            "metadata": record.metadata or {},
            "score": record.score,
            "created_at": record.created_at if isinstance(record.created_at, str) else (record.created_at.isoformat() if record.created_at else None),
        })

    memories = [
        to_plugin_memory(item)
        for item in raw_items
        if not is_derived_resource_uri(
            item.get("uri")
            or item.get("id")
            or (item.get("metadata", {}) if isinstance(item.get("metadata"), dict) else {}).get("uri")
            or ""
        )
    ]

    if request.agent:
        memories = [
            item for item in memories
            if not item.get("metadata") or item["metadata"].get("agent") in (None, request.agent)
        ]
    if request.memory_type:
        memories = [
            item for item in memories
            if item.get("category") == request.memory_type
            or item.get("metadata", {}).get("memory_type") == request.memory_type
        ]
    if request.memory_level:
        requested_level = map_memory_level(request.memory_level)
        if requested_level is not None:
            memories = [item for item in memories if item.get("level") == requested_level]

    if not request.include_expired:
        current_time = int(datetime.now().timestamp())
        memories = [
            item for item in memories
            if (
                item.get("metadata", {}).get("expire_at", -1) == -1
                or item.get("metadata", {}).get("expire_at", -1) > current_time
            )
        ]

    # Note: Backend.search() returns full content - no need for additional content loading
    # Fallback search is handled by backend.fallback_search() if needed

    return {
        "memories": memories[: request.limit],
        "total": len(memories),
    }


@app.post("/memory/read")
async def read_memory(request: RetrieveRequest, http_request: Request):
    """
    读取记忆内容。

    优先按 uri 读取单条内容；如果没有 uri，则回退到 query 检索行为。
    """
    try:
        tenant_id, user_id = resolve_tenant_identity(http_request)

        # Case 1: uri-based read via backend.read()
        if request.uri:
            try:
                record = await _get_backend().read(request.uri)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 405:
                    raise_support_api_error(
                        http_request,
                        501,
                        "UNSUPPORTED_OPERATION",
                        "read not supported by current backend",
                        operation="read_memory",
                        detail="omnimemora_runtime backend does not support read",
                        retryable=False,
                    )
                raise
            if record is not None:
                return {"content": record.content}
            raise_support_api_error(
                http_request,
                404,
                "ADAPTER_NOT_FOUND",
                "memory not found",
                operation="read_memory",
                detail=f"uri={request.uri}",
                retryable=False,
            )

        # Case 2: query-based search via backend.search()
        if not request.query:
            raise_support_api_error(
                http_request,
                400,
                "ADAPTER_BAD_REQUEST",
                "uri or query is required",
                operation="read_memory",
                detail="uri or query is required",
                retryable=False,
            )

        search_result = await _get_backend().search(
            MemorySearchRequest(
                query=request.query,
                limit=request.limit,
                scope="agent",
                scope_ref=request.agent or "default",
                score_threshold=0.0,
            )
        )

        # Convert MemorySearchResult to dict format for backward compatibility
        raw_items = []
        for record in search_result.memories:
            raw_items.append({
                "uri": record.memory_id,
                "content": record.content,
                "metadata": record.metadata or {},
                "score": record.score,
                "created_at": record.created_at if isinstance(record.created_at, str) else (record.created_at.isoformat() if record.created_at else None),
            })

        memories = [
            to_plugin_memory(item)
            for item in raw_items
            if not is_derived_resource_uri(
                item.get("uri")
                or item.get("id")
                or (item.get("metadata", {}) if isinstance(item.get("metadata"), dict) else {}).get("uri")
                or ""
            )
        ]

        if request.agent:
            memories = [
                item for item in memories
                if not item.get("metadata") or item["metadata"].get("agent") in (None, request.agent)
            ]
        if request.memory_type:
            memories = [
                item for item in memories
                if item.get("category") == request.memory_type
                or item.get("metadata", {}).get("memory_type") == request.memory_type
            ]
        if request.memory_level:
            requested_level = map_memory_level(request.memory_level)
            if requested_level is not None:
                memories = [item for item in memories if item.get("level") == requested_level]

        if not request.include_expired:
            current_time = int(datetime.now().timestamp())
            memories = [
                item for item in memories
                if (
                    item.get("metadata", {}).get("expire_at", -1) == -1
                    or item.get("metadata", {}).get("expire_at", -1) > current_time
                )
            ]

        return {"memories": memories[: request.limit], "total": len(memories)}

    except HTTPException:
        raise
    except SupportAPIError:
        raise
    except Exception as e:
        log_error("Error reading memory", str(e))
        raise_support_api_error(
            http_request,
            500,
            "ADAPTER_READ_FAILED",
            "Read request failed",
            operation="read_memory",
            detail=str(e),
            retryable=True,
        )


@app.post("/memory/delete")
async def delete_memory(request: DeleteRequest, http_request: Request):
    """按 URI 删除记忆。"""
    try:
        # Use backend interface; protocol-specific encoding stays behind the backend boundary.
        success = await _get_backend().delete(request.uri)
        if success:
            return {"success": True, "uri": request.uri, "request_id": get_request_id(http_request)}
        # Backend returns False = not found
        return {
            "success": False,
            "uri": request.uri,
            "status": 404,
            "reason": "not_found",
            "request_id": get_request_id(http_request),
            "error_code": "ADAPTER_DELETE_FAILED",
            "support": build_support_payload(
                http_request,
                "ADAPTER_DELETE_FAILED",
                "Delete target was not found",
                operation="delete_memory",
                detail="not_found",
                upstream_status=404,
                retryable=False,
            )["support"],
        }
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 405:
            raise_support_api_error(
                http_request,
                501,
                "UNSUPPORTED_OPERATION",
                "delete not supported by current backend",
                operation="delete_memory",
                detail="omnimemora_runtime backend does not support delete",
                retryable=False,
            )
        if e.response.status_code == 404:
            return {
                "success": False,
                "uri": request.uri,
                "status": 404,
                "reason": "not_found",
                "request_id": get_request_id(http_request),
                "error_code": "ADAPTER_DELETE_FAILED",
                "support": build_support_payload(
                    http_request,
                    "ADAPTER_DELETE_FAILED",
                    "Delete target was not found",
                    operation="delete_memory",
                    detail="not_found",
                    upstream_status=404,
                    retryable=False,
                )["support"],
            }
        raise
    except HTTPException:
        raise
    except SupportAPIError:
        raise
    except Exception as e:
        log_error("Error deleting memory", str(e))
        raise_support_api_error(
            http_request,
            500,
            "ADAPTER_DELETE_FAILED",
            "Delete request failed",
            operation="delete_memory",
            detail=str(e),
            retryable=True,
        )


@app.post("/memory/snapshot")
async def build_memory_snapshot(request: SnapshotRequest, http_request: Request):
    """
    从 memory backend 主库生成 MEMORY.md 自动摘要区。

    NOTE: This endpoint only works with the legacy compatibility backend.
    For other backends, use the backend's native snapshot capability.
    """
    try:
        tenant_id, user_id = resolve_tenant_identity(http_request)
        root_uri = build_agent_memory_prefix(request.agent)
        if not await namespace_exists(root_uri, tenant_id=tenant_id, user_id=user_id):
            markdown = render_snapshot_markdown(
                request.agent,
                {
                    "identity": [],
                    "projects": [],
                    "preferences": [],
                    "decisions": [],
                    "facts": [],
                },
                0,
            )
            return {
                "agent": request.agent,
                "generatedAt": datetime.now().isoformat(),
                "sourceCount": 0,
                "markdown": markdown,
                "sections": {"identity": 0, "projects": 0, "preferences": 0, "decisions": 0, "facts": 0},
                "request_id": get_request_id(http_request),
            }
        leaf_uris = await collect_memory_leaf_uris(
            root_uri,
            tenant_id=tenant_id,
            user_id=user_id,
            max_files=max(20, request.limit),
        )

        grouped: Dict[str, List[str]] = {
            "identity": [],
            "projects": [],
            "preferences": [],
            "decisions": [],
            "facts": [],
        }

        for uri in leaf_uris:
            content = await read_clean_resource_content(uri, tenant_id=tenant_id, user_id=user_id)
            if not content:
                continue
            if not should_include_snapshot_fact(content):
                continue
            group = classify_snapshot_fact(content)
            grouped[group].append(content)

        deduped = {
            "identity": dedupe_facts(grouped["identity"], 6),
            "projects": dedupe_facts(grouped["projects"], 8),
            "preferences": dedupe_facts(grouped["preferences"], 8),
            "decisions": dedupe_facts(grouped["decisions"], 8),
            "facts": dedupe_facts(grouped["facts"], 10),
        }

        markdown = render_snapshot_markdown(request.agent, deduped, len(leaf_uris))

        return {
            "agent": request.agent,
            "generatedAt": datetime.now().isoformat(),
            "sourceCount": len(leaf_uris),
            "markdown": markdown,
            "sections": {key: len(value) for key, value in deduped.items()},
            "request_id": get_request_id(http_request),
        }
    except HTTPException:
        raise
    except SupportAPIError:
        raise
    except Exception as e:
        log_error("Error building memory snapshot", str(e))
        raise_support_api_error(
            http_request,
            500,
            "ADAPTER_SNAPSHOT_FAILED",
            "Snapshot generation failed",
            operation="build_memory_snapshot",
            detail=str(e),
            retryable=True,
        )


@app.get("/memory/types")
async def get_memory_types():
    """获取记忆类型和等级配置"""
    return {
        "memory_types": ["long_term", "short_term"],
        "memory_levels": {
            "L0": "垃圾/不存",
            "L1": "短期缓存 (7天)",
            "L2": "经验记忆 (30天)",
            "L3": "核心知识 (永久)"
        },
        "score_rules": config.route_score_rules,
        "long_term_threshold": config.long_term_threshold,
        "exclude_types": config.exclude_types,
        "ttl_config": {
            "L1": "7 days",
            "L2": "30 days",
            "L3": "permanent"
        },
        "failure_detection": {
            "enabled": True,
            "keywords": ["错误", "error", "失败", "fail", "异常", "exception"]
        }
    }


@app.get("/memory/dedup/stats")
async def get_dedup_stats():
    """获取去重缓存状态"""
    return get_dedup_cache().get_stats()


@app.get("/memory/rate_limit/stats")
async def get_rate_limit_stats():
    """获取限流状态"""
    return {
        "enabled": config.enable_rate_limit,
        "max_per_minute": config.rate_limit_per_minute,
        "current": _rate_limiter.get_current_count()
    }


# ==================== V2 Platform Endpoints ====================

@app.post("/memory/query", response_model=MemoryQueryResponse)
async def query_memory_v2(request: MemoryQueryRequest, http_request: Request):
    """
    V2: Unified memory query via engine.optimize_context().
    Adapter only handles: access, data fetch, input assembly, store meter, response.
    """
    access = resolve_query_access(
        http_request,
        requested_tenant=request.tenant,
        requested_user=request.user,
        registry_path=config.omnimemora_access_registry_path,
        require_key=config.omnimemora_require_api_key_for_v2,
        registry_sync=config.registry_sync.model_dump() if config.registry_sync else None,
    )
    http_request.state.omnimemora_access = access.to_dict()

    request_id = f"req-{uuid4().hex[:8]}"
    loguru.logger.info(
        f"[QUERY_V2] request_id={request_id}, tenant={access.tenant_id}, auth_mode={access.auth_mode}, query={request.query[:50]}..."
    )

    # ---- Agent Observability: identity + control mode ----
    req_ctx = request.context or {}
    raw_agent_id = request.agent_id if request.agent_id and request.agent_id != "unknown" else (request.agent or "unknown")
    identity = _5_agent_id.AgentIdentity(
        canonical_agent_id=_5_agent_id.resolve_canonical_agent_id(raw_agent_id),
        raw_agent_id=raw_agent_id,
        session_id=req_ctx.get("session_id") or req_ctx.get("conversation_id") or req_ctx.get("thread_id"),
        workspace_id=request.workspace_id,
        user_id=access.user_id,
        integration_type="wrapper",
        source="body",
    )
    per_agent_dict, default_mode = _5_route_state.get_agent_modes_cache()
    control_mode = _5_ctrl.load_control_mode(
        identity.canonical_agent_id, identity.integration_type, per_agent_dict, default_mode
    )
    _5_agnet_m.record_agent_request(identity, control_mode.mode)

    # --- Cloud Integration: Load policy & flags ---
    policy = load_policy()
    flags = load_flags()
    loguru.logger.info(
        f"[CLOUD_INTEGRATION] request_id={request_id}, policy_version={policy.version}, "
        f"optimization_enabled={flags.optimization_enabled}"
    )

    # If optimization is disabled, still go through unified path but skip optimization
    if not flags.optimization_enabled:
        loguru.logger.info(
            f"[OPTIMIZATION_DISABLED] request_id={request_id}, skipping optimize_context() but preserving metrics/trace"
        )
        # Still load candidates for metrics, but bypass optimization
        # (Continue with unified path - just skip the optimize_context call later)
        pass

    # Parse options
    options = request.options or {}
    max_local_cards = options.get("max_local_cards", 4)
    packing_enabled = options.get("enable_packing", True)

    # Get client identifier
    client = (request.context or {}).get("client")
    if not client:
        client = "omnimemora-api" if access.key_present else "openclaw"

    # --- Assemble rules from config (adapter reads world) ---
    filter_rules = FilterRules(
        min_content_length=config.min_content_length,
        exclude_types=config.exclude_types,
        route_score_rules=config.route_score_rules,
        long_term_threshold=config.long_term_threshold,
    )
    routing_rules = RoutingRules(
        route_score_rules=config.route_score_rules,
        long_term_threshold=config.long_term_threshold,
    )

    # --- Get quota context from meter_store ---
    registry_entry = get_tenant_registry_entry(
        config.omnimemora_access_registry_path,
        access.tenant_id,
    ) if access.auth_mode == "omnimemora_key" else None
    current_usage = get_tenant_current_usage(access.tenant_id)
    raw_quota = registry_entry.get("monthly_quota_tokens") if registry_entry else None
    monthly_quota = int(raw_quota) if raw_quota not in (None, "") else None

    # --- Fetch candidate memories from backend ---
    retrieve_req = RetrieveRequest(
        query=request.query,
        agent=request.agent,
        limit=max_local_cards * 2,
        scoreThreshold=0.01
    )
    http_request.state.v2_tenant_override = access.tenant_id
    http_request.state.v2_user_override = access.user_id
    try:
        search_result = await search_memory(retrieve_req, http_request)
    finally:
        http_request.state.v2_tenant_override = None
        http_request.state.v2_user_override = None

    candidate_memories = search_result.get("memories", [])

    # --- Task classification (observability only) ---
    classification = classify_task(request.query)
    task_type = classification.task_type
    matched_keywords = classification.matched_keywords
    context_bypass = False
    bypassed_context_tokens = 0

    if not flags.optimization_enabled:
        # Feature flag: optimization disabled, but still go through unified path
        loguru.logger.info(
            f"[OPTIMIZATION_PASSTHROUGH] request_id={request_id}, optimization_enabled=false, preserving metrics/trace"
        )
        # Create passthrough result (no optimization, but preserve all metadata/trace)
        from datetime import datetime as dt
        passthrough_meter = TokenSavingsMeter(
            request_id=request_id,
            tenant=access.tenant_id,
            user=access.user_id,
            agent=request.agent,
            client=client,
            timestamp=dt.utcnow().isoformat() + "Z",
            query_shape="mixed",
            query_chars=len(request.query),
            query=request.query[:100],
            baseline_chars=0,
            actual_chars=0,
            saved_chars=0,
            baseline_tokens_estimate=0,
            actual_tokens_estimate=0,
            saved_tokens_estimate=0,
            savings_ratio=0.0,
            packed_memory_count=0,
            local_cards_used=0,
            remote_candidates_considered=len(candidate_memories),
            remote_candidates_skipped=0,
            remote_used_count=0,
            skipped_remote_reason="optimization_disabled",
            coverage_satisfied=True,
            packing_enabled=False,
            abstract_preferred=False,
            dedup_applied=False,
            task_type=task_type,
            context_bypass=False,
            bypassed_context_tokens=0,
        )
        class PassthroughResult:
            def __init__(self, meter, candidates):
                self.selected_memories = candidates  # Pass through all candidates
                self.packed_context = ""  # No packing when optimization is disabled
                self.token_savings = meter
                self.quota_result = check_quota_enforcement(current_usage, monthly_quota)
                self.meter_artifact = meter.to_dict()
                self.candidate_count = len(candidates)
                self.selected_count = len(candidates)
                # For trace compatibility
                self.call_chain = None
        result = PassthroughResult(passthrough_meter, candidate_memories)
    else:
        # All task types share the same context-optimization path.
        input_data = OptimizationInput(
            query=request.query,
            candidate_memories=candidate_memories,
            filter_rules=filter_rules,
            routing_rules=routing_rules,
            agent=request.agent,
            client=client,
            current_usage=current_usage,
            monthly_quota=monthly_quota,
            packing_enabled=packing_enabled,
            max_local_cards=max_local_cards,
            candidate_limit=16,
            task_type=task_type,
            context_bypass=False,
            bypassed_context_tokens=0,
        )
        result = optimize_context(input_data)

    # --- Quota enforcement (SaaS-key path) ---
    if access.auth_mode == "omnimemora_key" and result.quota_result.quota_exceeded:
        loguru.logger.warning(
            f"[QUOTA_EXCEEDED] tenant={access.tenant_id}, "
            f"current_usage={result.quota_result.current_usage}, "
            f"monthly_quota={result.quota_result.monthly_quota}"
        )
        raise_support_api_error(
            http_request,
            429,
            "ADAPTER_QUOTA_EXCEEDED",
            f"Monthly token quota exceeded ({result.quota_result.current_usage}/{result.quota_result.monthly_quota})",
            operation="memory_query_quota_check",
            detail=(
                f"Tenant {access.tenant_id} has exceeded monthly token quota. "
                f"Current usage: {result.quota_result.current_usage} tokens. "
                f"Monthly quota: {result.quota_result.monthly_quota} tokens. "
                f"Upgrade plan or wait for billing cycle reset."
            ),
            retryable=False,
            extra={
                "tenant_id": access.tenant_id,
                "current_usage": result.quota_result.current_usage,
                "monthly_quota": result.quota_result.monthly_quota,
                "quota_status": result.quota_result.quota_status,
            },
        )

    # --- Persist meter artifact (adapter responsibility) ---
    result.meter_artifact["request_id"] = request_id
    result.meter_artifact["tenant"] = access.tenant_id  # Use real tenant from access, not hardcoded "engine"
    result.meter_artifact["matched_keywords"] = matched_keywords  # Policy v1 observability
    store_meter(result.meter_artifact)

    # ---- Agent Observability: record result ----
    optimization_applied = bool(flags.optimization_enabled and not context_bypass)
    bypass_detected = context_bypass or (result.packed_context == "" and len(candidate_memories) > 0)
    raw_tokens = result.token_savings.baseline_tokens_estimate
    compressed_tokens = result.token_savings.actual_tokens_estimate
    quality_delta_pct = (
        0.5 * ((raw_tokens - compressed_tokens) / raw_tokens if raw_tokens > 0 else 0)
        + 0.3 * (result.selected_count / result.candidate_count if result.candidate_count > 0 else 0)
        + 0.2 * (1.0 - len(result.selected_memories) / result.candidate_count if result.candidate_count > 0 else 0)
    ) * 100
    _5_agnet_m.record_agent_result(
        identity=identity,
        mode=control_mode.mode,
        optimized=optimization_applied,
        bypassed=bypass_detected,
        meter_artifact=result.meter_artifact,
        quality_delta_pct=quality_delta_pct,
    )

    # --- Cloud Integration: Report usage async ---
    report_usage_async(
        request_id=request_id,
        route="/memory/query",
        version="2.2.0",
        saved_tokens=result.token_savings.saved_tokens_estimate,
        savings_ratio=result.token_savings.savings_ratio,
        optimization_enabled=bool(flags.optimization_enabled and not context_bypass),
        error_code=None,
    )

    # --- Store call chain trace ---
    if hasattr(result, "call_chain") and result.call_chain:
        result.call_chain.trace_id = request_id
        _5_trace.store_trace(request_id, result.call_chain)

    # --- Format response ---
    selected_memories = [
        {
            "id": mem.get("uri", f"mem-{i:03d}"),
            "type": mem.get("category", "memory"),
            "score": mem.get("score", 0.5),
            "content": mem.get("content", mem.get("abstract", "")),
            "source": "local"
        }
        for i, mem in enumerate(result.selected_memories)
    ]

    explanation = {
        "local_cards_used": result.selected_count,
        "remote_candidates_skipped": 16,
        "skip_remote_reason": "local-first coverage satisfied",
        "packing_enabled": packing_enabled,
        "abstract_preferred": False,
        "auth_mode": access.auth_mode,
        "tenant_status": access.status,
        "candidate_count": result.candidate_count,
    }

    # --- Decision Log (auto-generated) ---
    emit_decision_log(
        query=request.query,
        task_type=task_type,
        context_bypass=context_bypass,
        packed_context=result.packed_context,
        memory_tokens_injected=result.token_savings.actual_tokens_estimate,
        baseline_tokens_estimate=result.token_savings.baseline_tokens_estimate,
        actual_tokens_estimate=result.token_savings.actual_tokens_estimate,
        saved_tokens_estimate=result.token_savings.saved_tokens_estimate,
        savings_ratio=result.token_savings.savings_ratio,
        matched_keywords=matched_keywords,
        selected_memory_count=len(result.selected_memories),
        request_id=request_id,
        agent=request.agent,
        tenant=access.tenant_id,
        agent_id=request.agent_id,
        workspace_id=request.workspace_id,
        scope=request.scope,
    )

    return MemoryQueryResponse(
        request_id=request_id,
        selected_memories=selected_memories,
        packed_context=result.packed_context,
        memory_tokens_injected=result.token_savings.actual_tokens_estimate,
        tokens_saved_estimate=result.token_savings.saved_tokens_estimate,
        savings_ratio=result.token_savings.savings_ratio,
        explanation=explanation,
        meter_artifact={"$ref": f"/requests/{request_id}/meter"},
        # Policy v1 observability
        task_type=task_type,
        context_bypass=context_bypass,
        matched_keywords=matched_keywords,
        policy_version=policy.version,
    )


# ==================== Demo UI Dashboard Endpoints ====================

@app.post("/mcp/query")
async def mcp_query(request: Request):
    """
    Internal MCP query endpoint — called by _mcp_call_tool when OpenClaw MCP
    client calls memory.context / memory.recall.
    Bypasses resolve_query_access (openclaw tenant is hardcoded).
    Directly calls engine.optimize_context() with openclaw defaults.
    """
    body = await request.json()
    request.state._body_cache = body
    query = (body.get("query") or body.get("keyword", ""))[:200]
    limit = int(body.get("limit", 8)) or 8
    tenant = body.get("tenant", "openclaw")
    user = body.get("user", "openclaw-user")
    agent = body.get("agent", "openclaw-agent")

    if not query:
        return JSONResponse(
            status_code=400,
            content={"error": "query or keyword required"},
        )

    request_id = f"mcp-{uuid4().hex[:8]}"

    # Set tenant context for search
    request.state.v2_tenant_override = tenant
    request.state.v2_user_override = user

    try:
        # ---- Agent Observability: identity + control mode ----
        raw_agent_id = (
            body.get("agent_id")
            or body.get("agent")
            or request.headers.get("x-agent-id")
            or "unknown"
        )
        session_id = (
            body.get("session_id")
            or body.get("conversation_id")
            or body.get("thread_id")
            or request.headers.get("x-session-id")
        )
        workspace_id = body.get("workspace_id") or request.headers.get("x-workspace-id")
        integration_type = body.get("integration_type") or request.headers.get("x-integration-type") or "unknown"
        if integration_type not in ("tool_caller", "pre_llm_connector", "wrapper"):
            integration_type = "unknown"
        identity = _5_agent_id.AgentIdentity(
            canonical_agent_id=_5_agent_id.resolve_canonical_agent_id(raw_agent_id),
            raw_agent_id=raw_agent_id,
            session_id=session_id,
            workspace_id=workspace_id,
            user_id=body.get("user_id") or request.headers.get("x-user-id"),
            integration_type=integration_type,
            source="body",
        )
        # ADR-0005 v1.2: use cached per-agent modes with canonical key lookup
        per_agent_dict, default_mode = _5_route_state.get_agent_modes_cache()
        control_mode = _5_ctrl.load_control_mode(
            identity.canonical_agent_id, identity.integration_type, per_agent_dict, default_mode
        )
        _5_agnet_m.record_agent_request(identity, control_mode.mode)

        optimization_attempted = False
        optimization_applied = False
        bypass_detected = False

        # Assemble rules
        filter_rules = FilterRules(
            min_content_length=config.min_content_length,
            exclude_types=config.exclude_types,
            route_score_rules=config.route_score_rules,
            long_term_threshold=config.long_term_threshold,
        )
        routing_rules = RoutingRules(
            route_score_rules=config.route_score_rules,
            long_term_threshold=config.long_term_threshold,
        )

        # Get quota context
        registry_entry = get_tenant_registry_entry(
            config.omnimemora_access_registry_path, tenant
        ) if tenant == "openclaw" else None
        current_usage = get_tenant_current_usage(tenant)
        raw_quota = registry_entry.get("monthly_quota_tokens") if registry_entry else None
        monthly_quota = int(raw_quota) if raw_quota not in (None, "") else None

        # Fetch candidates
        retrieve_req = RetrieveRequest(
            query=query,
            agent=agent,
            limit=limit * 2,
            scoreThreshold=0.01,
        )
        search_result = await search_memory(retrieve_req, request)
        candidate_memories = search_result.get("memories", [])

        # Task classification is retained for observability only.
        classification = classify_task(query)
        task_type = classification.task_type
        matched_keywords = classification.matched_keywords
        context_bypass = False
        bypassed_context_tokens = 0

        input_data = OptimizationInput(
            query=query,
            candidate_memories=candidate_memories,
            filter_rules=filter_rules,
            routing_rules=routing_rules,
            agent=agent,
            client="openclaw-mcp",
            current_usage=current_usage,
            monthly_quota=monthly_quota,
            packing_enabled=True,
            max_local_cards=limit,
            candidate_limit=16,
            task_type=task_type,
            context_bypass=False,
            bypassed_context_tokens=0,
            # Multi-source final compile gate (Phase 4)
            native_compiled_context=body.get("native_compiled_context"),
            current_session_context=body.get("current_session_context"),
            raw_candidates=body.get("raw_candidates"),
        )
        result = optimize_context(input_data)

        # Persist meter artifact
        result.meter_artifact["request_id"] = request_id
        result.meter_artifact["tenant"] = tenant
        result.meter_artifact["matched_keywords"] = matched_keywords
        store_meter(result.meter_artifact)

        # ---- Agent Observability: record result ----
        optimization_applied = not context_bypass
        bypass_detected = context_bypass or (result.packed_context == "" and len(candidate_memories) > 0)
        raw_tokens = result.token_savings.baseline_tokens_estimate
        compressed_tokens = result.token_savings.actual_tokens_estimate
        quality_delta_pct = (
            0.5 * ((raw_tokens - compressed_tokens) / raw_tokens if raw_tokens > 0 else 0)
            + 0.3 * (result.selected_count / result.candidate_count if result.candidate_count > 0 else 0)
            + 0.2 * (1.0 - len(result.selected_memories) / result.candidate_count if result.candidate_count > 0 else 0)
        ) * 100
        _5_agnet_m.record_agent_result(
            identity=identity,
            mode=control_mode.mode,
            optimized=optimization_applied,
            bypassed=bypass_detected,
            meter_artifact=result.meter_artifact,
            quality_delta_pct=quality_delta_pct,
        )

        # Store call chain trace
        if hasattr(result, "call_chain") and result.call_chain:
            result.call_chain.trace_id = request_id
            _5_trace.store_trace(request_id, result.call_chain)

        # Decision log
        emit_decision_log(
            query=query,
            task_type=task_type,
            context_bypass=context_bypass,
            packed_context=result.packed_context,
            memory_tokens_injected=result.token_savings.actual_tokens_estimate,
            baseline_tokens_estimate=result.token_savings.baseline_tokens_estimate,
            actual_tokens_estimate=result.token_savings.actual_tokens_estimate,
            saved_tokens_estimate=result.token_savings.saved_tokens_estimate,
            savings_ratio=result.token_savings.savings_ratio,
            matched_keywords=matched_keywords,
            selected_memory_count=len(result.selected_memories),
            request_id=request_id,
            agent=agent,
            tenant=tenant,
        )

        return {
            "request_id": request_id,
            "packed_context": result.packed_context,
            "selected_memories": result.selected_memories,
            "usage": {
                "saved_tokens_estimate": result.token_savings.saved_tokens_estimate,
                "savings_ratio": result.token_savings.savings_ratio,
                "actual_tokens_estimate": result.token_savings.actual_tokens_estimate,
                "baseline_tokens_estimate": result.token_savings.baseline_tokens_estimate,
            },
            "task_type": task_type,
            "context_bypass": context_bypass,
            "matched_keywords": matched_keywords,
        }

    finally:
        request.state.v2_tenant_override = None
        request.state.v2_user_override = None


# ==================== Trial Provisioning (Protected Admin) ====================

from .access import hash_api_key, atomic_write_registry, load_registry


class TrialProvisionRequest(BaseModel):
    """Request body for trial provisioning endpoint."""
    contact_email: Optional[str] = None
    display_name: Optional[str] = None
    source: Optional[str] = None


class TrialProvisionResponse(BaseModel):
    """Response body for successful trial provisioning."""
    tenant_id: str
    api_key: str          # plaintext — shown only once here
    plan: str
    status: str
    monthly_quota_tokens: int
    trial_expires_at: Optional[int] = None
    created_at: str


@app.post("/api/admin/trials/provision", response_model=TrialProvisionResponse)
async def provision_trial(request: TrialProvisionRequest, http_request: Request):
    """
    Minimal protected trial provisioning endpoint.

    Protected by: OMNIMEMORA_ADMIN_API_TOKEN sent as X-OmniMemora-Admin-Token header.

    Responsibilities:
    - Validate admin token
    - Generate tenant_id and a one-time plaintext API key
    - Write api_key_hash (never plaintext) to tenant_access_registry.json
    - Default plan=starter, status=active, quota from config
    - Return plaintext API key once (never stored or retrievable after)
    """
    # ---- Admin token check ----
    admin_token = http_request.headers.get("X-OmniMemora-Admin-Token", "")
    if not admin_token:
        raise HTTPException(status_code=401, detail="Missing X-OmniMemora-Admin-Token header.")
    if admin_token != config.omnimemora_admin_api_token:
        raise HTTPException(status_code=403, detail="Invalid admin token.")

    # ---- Generate identifiers ----
    tenant_id = f"trial-{uuid4().hex[:12]}"
    raw_api_key = f"omni-{uuid4().hex}-{uuid4().hex[:8]}"
    api_key_hash = hash_api_key(raw_api_key)
    token_id = f"tk-{uuid4().hex[:12]}"

    # ---- Build tenant entry (hash only, never plaintext) ----
    now_ts = int(datetime.now().timestamp())
    trial_seconds = config.omnimemora_trial_days * 86400
    trial_expires_at = now_ts + trial_seconds if config.omnimemora_trial_days > 0 else None

    now_iso = datetime.now().isoformat()
    new_entry: Dict[str, Any] = {
        "tenant_id": tenant_id,
        "api_key_hash": api_key_hash,
        "token_id": token_id,
        "plan": "starter",
        "status": "active",
        "monthly_quota_tokens": config.omnimemora_trial_quota_tokens,
        "default_user": "trial-user",
        "trial_expires_at": trial_expires_at,
        "created_at": now_iso,
        "source": request.source or "trial-provisioning",
    }
    if request.contact_email:
        new_entry["contact_email"] = request.contact_email
    if request.display_name:
        new_entry["display_name"] = request.display_name

    # ---- Atomic write to registry ----
    registry = load_registry(config.omnimemora_access_registry_path)
    registry.append(new_entry)
    atomic_write_registry(config.omnimemora_access_registry_path, registry)

    loguru.logger.info(
        f"[TRIAL_PROVISIONED] tenant={tenant_id}, plan=starter, quota={config.omnimemora_trial_quota_tokens}, "
        f"expires_at={trial_expires_at}, source={request.source or 'direct'}"
    )

    return TrialProvisionResponse(
        tenant_id=tenant_id,
        api_key=raw_api_key,
        plan="starter",
        status="active",
        monthly_quota_tokens=config.omnimemora_trial_quota_tokens,
        trial_expires_at=trial_expires_at,
        created_at=now_iso,
    )


# ==================== Internal Service Endpoints ====================

class InternalTrialQueryRequest(BaseModel):
    """Request body for internal trial query proxy."""
    tenant: str
    user: str
    agent: str = "omnimemora-trial"
    query: str
    limit: int = 10
    context: Optional[Dict[str, Any]] = None
    options: Optional[Dict[str, Any]] = None
    # Decision Log identity binding
    agent_id: str = "unknown"
    workspace_id: str = "unknown"
    scope: str = "workspace"


class InternalTrialQueryResponse(BaseModel):
    """Response shape returned to Cloudflare trial/query proxy."""
    selected_memories: List[Dict[str, Any]]
    packed_context: str
    memory_tokens_injected: int
    tokens_saved_estimate: int
    savings_ratio: float
    explanation: Dict[str, Any]
    meter_artifact: Optional[Dict[str, Any]] = None
    # Policy v1 observability
    task_type: str = "continuation"
    context_bypass: bool = False
    matched_keywords: List[str] = []


@app.post("/internal/trial-query", response_model=InternalTrialQueryResponse)
async def internal_trial_query(request: InternalTrialQueryRequest, http_request: Request):
    """
    Internal trial query endpoint — called ONLY by cloud control-plane edge handlers
    (query.ts) after it has already validated the API key against D1.

    Trust is established via X-Internal-Token header matching
    OMNIMEMORA_INTERNAL_API_TOKEN env var.

    This endpoint bypasses the normal OmniMemora API key auth flow and
    uses the tenant context passed directly from the validated Cloudflare layer.
    """
    import os as _os

    # ---- Verify internal service token ----
    internal_token = http_request.headers.get("X-Internal-Token", "")
    expected_token = _os.getenv("OMNIMEMORA_INTERNAL_API_TOKEN", "")
    if not expected_token:
        loguru.logger.warning("[INTERNAL] OMNIMEMORA_INTERNAL_API_TOKEN not set — rejecting internal call")
        raise HTTPException(status_code=500, detail="Internal API token not configured on adapter.")
    if not internal_token or internal_token != expected_token:
        loguru.logger.warning(f"[INTERNAL] Invalid internal token from {http_request.client}")
        raise HTTPException(status_code=403, detail="Invalid internal service token.")

    # ---- Also verify tenant came from X-OmniMemora-Tenant header ----
    validated_tenant = http_request.headers.get("X-OmniMemora-Tenant", "")
    if not validated_tenant:
        raise HTTPException(status_code=400, detail="Missing X-OmniMemora-Tenant header.")
    if validated_tenant != request.tenant:
        raise HTTPException(status_code=400, detail="Tenant mismatch between header and body.")

    loguru.logger.info(
        f"[INTERNAL_TRIAL_QUERY] tenant={request.tenant}, user={request.user}, "
        f"agent={request.agent}, query={request.query[:50]}..."
    )

    # ---- Agent Observability: identity + control mode ----
    req_ctx = request.context or {}
    raw_agent_id = request.agent_id if request.agent_id and request.agent_id != "unknown" else (request.agent or "unknown")
    identity = _5_agent_id.AgentIdentity(
        canonical_agent_id=_5_agent_id.resolve_canonical_agent_id(raw_agent_id),
        raw_agent_id=raw_agent_id,
        session_id=req_ctx.get("session_id") or req_ctx.get("conversation_id") or req_ctx.get("thread_id"),
        workspace_id=request.workspace_id,
        user_id=request.user,
        integration_type="wrapper",
        source="body",
    )
    per_agent_dict, default_mode = _5_route_state.get_agent_modes_cache()
    control_mode = _5_ctrl.load_control_mode(
        identity.canonical_agent_id, identity.integration_type, per_agent_dict, default_mode
    )
    _5_agnet_m.record_agent_request(identity, control_mode.mode)

    # ---- Set tenant context for search ----
    http_request.state.v2_tenant_override = request.tenant
    http_request.state.v2_user_override = request.user

    try:
        # ---- Parse options ----
        options = request.options or {}
        max_local_cards = options.get("max_local_cards", 4)
        packing_enabled = options.get("enable_packing", True)
        client = (request.context or {}).get("client", "omnimemora-trial")

        # ---- Assemble rules from config ----
        filter_rules = FilterRules(
            min_content_length=config.min_content_length,
            exclude_types=config.exclude_types,
            route_score_rules=config.route_score_rules,
            long_term_threshold=config.long_term_threshold,
        )
        routing_rules = RoutingRules(
            route_score_rules=config.route_score_rules,
            long_term_threshold=config.long_term_threshold,
        )

        # ---- Get quota context ----
        registry_entry = get_tenant_registry_entry(
            config.omnimemora_access_registry_path,
            request.tenant,
        )
        trial_usage = get_tenant_current_usage(request.tenant)
        trial_quota = int(registry_entry.get("monthly_quota_tokens")) if registry_entry and registry_entry.get("monthly_quota_tokens") not in (None, "") else None

        # ---- Fetch candidate memories ----
        retrieve_req = RetrieveRequest(
            query=request.query,
            agent=request.agent,
            limit=max_local_cards * 2,
            scoreThreshold=0.01,
        )
        search_result = await search_memory(retrieve_req, http_request)
        candidate_memories = search_result.get("memories", [])

        # ---- Task classification (observability only) ----
        classification = classify_task(request.query)
        task_type = classification.task_type
        matched_keywords = classification.matched_keywords
        context_bypass = False
        bypassed_context_tokens = 0

        request_id = f"trial-{uuid4().hex[:8]}"

        input_data = OptimizationInput(
            query=request.query,
            candidate_memories=candidate_memories,
            filter_rules=filter_rules,
            routing_rules=routing_rules,
            agent=request.agent,
            client=client,
            current_usage=trial_usage,
            monthly_quota=trial_quota,
            packing_enabled=packing_enabled,
            max_local_cards=max_local_cards,
            candidate_limit=16,
            task_type=task_type,
            context_bypass=False,
            bypassed_context_tokens=0,
        )
        result = optimize_context(input_data)

        # ---- Quota enforcement ----
        if result.quota_result.quota_exceeded:
            raise_support_api_error(
                http_request,
                429,
                "ADAPTER_QUOTA_EXCEEDED",
                f"Monthly token quota exceeded ({result.quota_result.current_usage}/{result.quota_result.monthly_quota})",
                operation="internal_trial_query_quota",
                detail=(
                    f"Tenant {request.tenant} has exceeded monthly token quota. "
                    f"Current usage: {result.quota_result.current_usage} tokens. "
                    f"Monthly quota: {result.quota_result.monthly_quota} tokens."
                ),
                retryable=False,
                extra={
                    "tenant_id": request.tenant,
                    "current_usage": result.quota_result.current_usage,
                    "monthly_quota": result.quota_result.monthly_quota,
                    "quota_status": result.quota_result.quota_status,
                },
            )

        # ---- Persist meter artifact ----
        result.meter_artifact["request_id"] = request_id
        result.meter_artifact["matched_keywords"] = matched_keywords  # Policy v1 observability
        store_meter(result.meter_artifact)

        # ---- Agent Observability: record result ----
        optimization_applied = not context_bypass
        bypass_detected = context_bypass or (result.packed_context == "" and len(candidate_memories) > 0)
        raw_tokens = result.token_savings.baseline_tokens_estimate
        compressed_tokens = result.token_savings.actual_tokens_estimate
        quality_delta_pct = (
            0.5 * ((raw_tokens - compressed_tokens) / raw_tokens if raw_tokens > 0 else 0)
            + 0.3 * (result.selected_count / result.candidate_count if result.candidate_count > 0 else 0)
            + 0.2 * (1.0 - len(result.selected_memories) / result.candidate_count if result.candidate_count > 0 else 0)
        ) * 100
        _5_agnet_m.record_agent_result(
            identity=identity,
            mode=control_mode.mode,
            optimized=optimization_applied,
            bypassed=bypass_detected,
            meter_artifact=result.meter_artifact,
            quality_delta_pct=quality_delta_pct,
        )

        # ---- Format response ----
        selected_memories = [
            {
                "id": mem.get("uri", f"mem-{i:03d}"),
                "type": mem.get("category", "memory"),
                "score": mem.get("score", 0.5),
                "content": mem.get("content", mem.get("abstract", "")),
                "source": "local",
            }
            for i, mem in enumerate(result.selected_memories)
        ]

        explanation = {
            "local_cards_used": result.selected_count,
            "remote_candidates_skipped": 16,
            "skip_remote_reason": "local-first coverage satisfied",
            "packing_enabled": packing_enabled,
            "abstract_preferred": False,
            "auth_mode": "internal_trial",
            "tenant_status": "active",
        }

        # --- Decision Log (auto-generated) ---
        emit_decision_log(
            query=request.query,
            task_type=task_type,
            context_bypass=context_bypass,
            packed_context=result.packed_context,
            memory_tokens_injected=result.token_savings.actual_tokens_estimate,
            baseline_tokens_estimate=result.token_savings.baseline_tokens_estimate,
            actual_tokens_estimate=result.token_savings.actual_tokens_estimate,
            saved_tokens_estimate=result.token_savings.saved_tokens_estimate,
            savings_ratio=result.token_savings.savings_ratio,
            matched_keywords=matched_keywords,
            selected_memory_count=len(result.selected_memories),
            request_id=request_id,
            agent=request.agent,
            tenant=request.tenant,
            agent_id=request.agent_id,
            workspace_id=request.workspace_id,
            scope=request.scope,
        )

        return InternalTrialQueryResponse(
            selected_memories=selected_memories,
            packed_context=result.packed_context,
            memory_tokens_injected=result.token_savings.actual_tokens_estimate,
            tokens_saved_estimate=result.token_savings.saved_tokens_estimate,
            savings_ratio=result.token_savings.savings_ratio,
            explanation=explanation,
            meter_artifact=result.meter_artifact,
            task_type=task_type,
            context_bypass=context_bypass,
            matched_keywords=matched_keywords,
        )

    finally:
        http_request.state.v2_tenant_override = None
        http_request.state.v2_user_override = None


# ==================== 启动 ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=config.adapter_host,
        port=config.adapter_port,
        log_level="info",
        access_log=False,
    )
