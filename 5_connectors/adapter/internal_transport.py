"""
internal_transport.py — Internal Transport Layer
==============================================
Per ADR-0006: 内部直连传递规范。

所有本机内部 HTTP 调用必须：
1. 绕过环境代理（trust_env=False）
2. 自动选择可达的 loopback 地址（运行时探测）
3. 失败时自动 fallback 到其他候选地址

关键原则：
- 直连是硬规则，具体地址由运行时解析决定
- 不硬编码单一地址（127.0.0.1 / localhost / ::1 均可）
- 不依赖用户配置 NO_PROXY
"""
import asyncio
import httpx
import logging
import os
import time
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# =============================================================================
# ADR-0006 §2.2: 内部目标识别
# =============================================================================

# 本地产品端口列表（host + port 一起判断才认为是内部）
_INTERNAL_PORTS = {8765, 18011, 5173, 1933}

# localhost / loopback host patterns
_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "::ffff:127.0.0.1"}


def _is_loopback_host(host: str) -> bool:
    """Check if host is any form of loopback (IPv4 CIDR 127.0.0.0/8, IPv4 single, IPv6)."""
    h = host.lower().strip()
    if h in {"localhost", "::1", "::ffff:127.0.0.1"}:
        return True
    if h.startswith("127."):
        return True  # 127.0.0.0/8
    return False


def is_internal_target(host: str, port: int | None = None) -> bool:
    """
    ADR-0006 §2.2: 判断目标是否为内部本机目标。

    判断标准（必须 host + port 一起判断）：
    - host 是 localhost / 127.0.0.0/8 / ::1
    - host 命中已知本地服务 host
    - port 命中本地产品端口列表 且 host 明确指向本机

    Args:
        host: 目标主机名或 IP
        port: 目标端口（可选）

    Returns:
        True if target is internal (should bypass proxy)
    """
    if not host:
        return False

    host_lower = host.lower().strip()

    # Direct loopback (including 127.0.0.0/8 CIDR range)
    if _is_loopback_host(host_lower):
        return True

    # Check if host is a known local service name (flexible matching)
    # e.g. "omnimemora-runtime" -> treat as internal if port matches
    _local_service_hosts = {
        "omnimemora-runtime",
        "runtime",
        "memory-backend",
        "openviking",
        "host.docker.internal",
    }
    if host_lower in _local_service_hosts:
        return port is None or port in _INTERNAL_PORTS

    # If port is a known internal port and host looks like it could be local
    if port in _INTERNAL_PORTS:
        return True

    return False


def parse_host_from_url(url: str) -> tuple[str, int | None]:
    """Extract (host, port) from a URL string."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        port = parsed.port
        return host, port
    except Exception:
        return "", None


# =============================================================================
# ADR-0006 §3.2-3.3: 内部地址解析器
# =============================================================================

# ADR-0006 §3.3: 解析结果缓存
_internal_endpoint_cache: dict[str, tuple[str, float]] = {}  # service_name -> (resolved_url, timestamp)


def _get_loopback_candidates() -> list[str]:
    """
    返回候选 loopback 地址列表（按探测优先级）。
    ADR-0006 §6: loopback_candidates 配置顺序即为探测顺序。
    """
    return ["127.0.0.1", "localhost", "::1"]


async def _probe_address(host: str, port: int, timeout: float = 1.0) -> bool:
    """
    用轻量 HTTP GET 探测地址是否可达。
    仅探测 /health 或根路径，超时即认为不可达。

    Note: IPv6 hosts (::1) need brackets in URL: http://[::1]:8765
    """
    schemes = ["http"]
    paths = ["/health", "/"]

    # Format host for URL: IPv6 needs brackets
    if ":" in host and not host.startswith("["):
        host_for_url = f"[{host}]"
    else:
        host_for_url = host

    for scheme in schemes:
        url = f"{scheme}://{host_for_url}:{port}"
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout, connect=timeout),
                trust_env=False,
            ) as client:
                for path in paths:
                    try:
                        r = await client.get(f"{url}{path}", timeout=timeout)
                        if r.status_code < 500:
                            return True
                    except Exception:
                        break  # try next path
        except Exception:
            pass
    return False


def _rebuild_url(base_url: str, new_host: str) -> str:
    """Replace host in URL, preserve scheme, port, path. Handles IPv6 brackets."""
    try:
        parsed = urlparse(base_url)
        # IPv6 hosts need brackets in URL
        if ":" in new_host and not new_host.startswith("["):
            new_host_brackets = f"[{new_host}]"
        else:
            new_host_brackets = new_host
        if parsed.port:
            new_netloc = f"{new_host_brackets}:{parsed.port}"
        else:
            new_netloc = new_host_brackets
        return f"{parsed.scheme}://{new_netloc}{parsed.path}"
    except Exception:
        return base_url


async def resolve_internal_base_url(
    service_name: str,
    configured_url: str,
    loopback_candidates: Optional[list[str]] = None,
    connect_timeout: float = 1.5,
) -> tuple[str, str]:
    """
    ADR-0006 §3.2: 解析内部服务 base URL 为可达的 loopback 地址。

    策略：
    1. 从 configured_url 提取 host/port
    2. 若 host 已是 loopback 且可达，直接用
    3. 若不可达或需要探测，按 loopback_candidates 顺序探测
    4. 缓存结果（TTL 300s）

    Args:
        service_name: 服务名（如 "runtime", "adapter"）
        configured_url: 用户配置的 URL（可能含 localhost）
        loopback_candidates: 候选 loopback 地址列表
        connect_timeout: 探测超时（秒）

    Returns:
        (resolved_url, reason): 解析后的 URL 和原因描述
    """
    global _internal_endpoint_cache

    candidates = loopback_candidates or _get_loopback_candidates()
    parsed = urlparse(configured_url)
    configured_host = parsed.hostname or ""
    configured_port = parsed.port or 80
    configured_scheme = parsed.scheme or "http"

    # TTL: 300 seconds
    cache_ttl = 300.0
    now = time.time()

    # Check cache first
    if service_name in _internal_endpoint_cache:
        cached_url, cached_ts = _internal_endpoint_cache[service_name]
        if now - cached_ts < cache_ttl:
            return cached_url, "cached"

    # Step 1: If configured host is already a loopback, try it first
    if configured_host.lower() in _LOOPBACK_HOSTS:
        reachable = await _probe_address(configured_host, configured_port, connect_timeout)
        if reachable:
            result_url = f"{configured_scheme}://{configured_host}:{configured_port}"
            _internal_endpoint_cache[service_name] = (result_url, now)
            logger.info(
                f"[internal_transport] resolved {service_name}: "
                f"configured={configured_url} resolved={result_url} reason=configured_loopback_reachable"
            )
            return result_url, "configured_loopback_reachable"

    # Step 2: Try each loopback candidate
    for candidate in candidates:
        if candidate.lower() == configured_host.lower():
            continue  # already tried above

        reachable = await _probe_address(candidate, configured_port, connect_timeout)
        if reachable:
            result_url = f"{configured_scheme}://{candidate}:{configured_port}"
            _internal_endpoint_cache[service_name] = (result_url, now)
            logger.info(
                f"[internal_transport] resolved {service_name}: "
                f"configured={configured_url} resolved={result_url} reason=fallback candidate={candidate}"
            )
            return result_url, f"fallback_{candidate}"

    # Step 3: All candidates failed — return configured_url as last resort
    # (let it fail at call time rather than blocking startup)
    logger.warning(
        f"[internal_transport] resolve {service_name}: all candidates unreachable, "
        f"falling back to configured={configured_url}"
    )
    return configured_url, "all_candidates_failed"


def resolve_internal_base_url_sync(
    service_name: str,
    configured_url: str,
    loopback_candidates: Optional[list[str]] = None,
) -> tuple[str, str]:
    """
    Synchronous wrapper for resolve_internal_base_url.
    Uses asyncio.run() — only use in startup/initialization context.
    """
    return asyncio.run(
        resolve_internal_base_url(service_name, configured_url, loopback_candidates)
    )


def invalidate_cache(service_name: Optional[str] = None) -> None:
    """Invalidate cache for a specific service or all services."""
    global _internal_endpoint_cache
    if service_name:
        _internal_endpoint_cache.pop(service_name, None)
    else:
        _internal_endpoint_cache.clear()


# =============================================================================
# ADR-0006 §2.3: HTTP Client 工厂
# =============================================================================

_default_internal_client: Optional[httpx.AsyncClient] = None
_default_external_client: Optional[httpx.AsyncClient] = None


def create_internal_http_client(
    timeout: float = 30.0,
    connect_timeout: float = 1.5,
    headers: Optional[dict] = None,
) -> httpx.AsyncClient:
    """
    ADR-0006 §2.3: 创建内部直连 HTTP client。

    要求：
    - trust_env=False（不继承系统代理）
    - 合理 timeout
    - 可加统一 headers

    Returns:
        httpx.AsyncClient configured for internal traffic (bypasses proxy)
    """
    return httpx.AsyncClient(
        timeout=httpx.Timeout(timeout, connect=connect_timeout),
        trust_env=False,  # ADR-0006: bypass proxy for internal
        headers=headers or {},
    )


def create_external_http_client(
    timeout: float = 30.0,
    connect_timeout: float = 5.0,
    headers: Optional[dict] = None,
) -> httpx.AsyncClient:
    """
    ADR-0006 §2.3: 创建外部 HTTP client。

    要求：
    - trust_env=True（尊重用户代理环境）

    Returns:
        httpx.AsyncClient configured for external traffic (honors system proxy)
    """
    return httpx.AsyncClient(
        timeout=httpx.Timeout(timeout, connect=connect_timeout),
        trust_env=True,  # respect system proxy for external
        headers=headers or {},
    )


def get_default_internal_client() -> httpx.AsyncClient:
    """Get or create a shared internal client (singleton)."""
    global _default_internal_client
    if _default_internal_client is None or _default_internal_client.is_closed:
        _default_internal_client = create_internal_http_client()
    return _default_internal_client


def get_default_external_client() -> httpx.AsyncClient:
    """Get or create a shared external client (singleton)."""
    global _default_external_client
    if _default_external_client is None or _default_external_client.is_closed:
        _default_external_client = create_external_http_client()
    return _default_external_client


async def close_default_clients() -> None:
    """Close shared clients on shutdown."""
    global _default_internal_client, _default_external_client
    if _default_internal_client and not _default_internal_client.is_closed:
        await _default_internal_client.aclose()
        _default_internal_client = None
    if _default_external_client and not _default_external_client.is_closed:
        await _default_external_client.aclose()
        _default_external_client = None


# =============================================================================
# ADR-0006 §6: 启动时预探测
# =============================================================================

async def probe_internal_endpoint(
    service_name: str,
    configured_url: str,
    loopback_candidates: Optional[list[str]] = None,
    connect_timeout: float = 1.5,
) -> dict:
    """
    ADR-0006 §6: 启动时探测内部服务，打印日志。

    Returns:
        dict with keys: service, configured, resolved, reason
    """
    resolved_url, reason = await resolve_internal_base_url(
        service_name, configured_url, loopback_candidates, connect_timeout
    )
    result = {
        "service": service_name,
        "configured": configured_url,
        "resolved": resolved_url,
        "reason": reason,
    }
    logger.info(f"[internal_transport] probe {service_name}: {result}")
    return result


# =============================================================================
# ADR-0006 §7: 运行时 fallback
# =============================================================================

async def request_with_fallback(
    method: str,
    url: str,
    loopback_candidates: Optional[list[str]] = None,
    timeout: float = 30.0,
    connect_timeout: float = 1.5,
    **kwargs,
) -> httpx.Response:
    """
    ADR-0006 §7: 发起 HTTP 请求，失败时自动尝试其他 loopback 候选。

    Args:
        method: HTTP method
        url: 初始 URL（含可能不可达的 host）
        loopback_candidates: 备用 loopback 候选
        timeout: 请求超时
        connect_timeout: 连接超时
        **kwargs: 其他 httpx.request() 参数

    Returns:
        httpx.Response from the first reachable address

    Raises:
        httpx.HTTPError if all candidates fail
    """
    candidates = loopback_candidates or _get_loopback_candidates()
    parsed = urlparse(url)
    original_host = parsed.hostname or ""
    port = parsed.port or 80
    scheme = parsed.scheme or "http"
    path = parsed.path or "/"

    tried: set[str] = set()

    def _url_for(host: str, port: int, scheme: str, path: str) -> str:
        """Build URL with proper IPv6 bracket handling."""
        if ":" in host and not host.startswith("["):
            return f"{scheme}://[{host}]:{port}{path}"
        return f"{scheme}://{host}:{port}{path}"

    # Try original host first
    for host in [original_host] + candidates:
        if host.lower() in tried:
            continue
        if host.lower() == original_host.lower():
            tried.add(host.lower())
            try:
                client = httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=connect_timeout), trust_env=False)
                resp = await client.request(method, url, **kwargs)
                await client.aclose()
                return resp
            except Exception:
                pass
        else:
            tried.add(host.lower())
            candidate_url = _url_for(host, port, scheme, path)
            try:
                client = httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=connect_timeout), trust_env=False)
                resp = await client.request(method, candidate_url, **kwargs)
                await client.aclose()
                logger.info(
                    f"[internal_transport] fallback: original={original_host} tried={host} "
                    f"success_url={candidate_url}"
                )
                return resp
            except Exception:
                pass

    # All failed
    raise httpx.HTTPError(f"All loopback candidates failed for {original_host}:{port}")
