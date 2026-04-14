"""
Usage 上报器 - 异步上报，best effort
"""
import asyncio
import loguru
from datetime import datetime
from typing import Optional
from .models import UsageReport
from .client import CloudClient
from ..config import config


_report_queue: Optional[asyncio.Queue] = None
_report_worker_task: Optional[asyncio.Task] = None


def _ensure_worker():
    """
    懒初始化上报 worker
    """
    global _report_queue, _report_worker_task

    if _report_queue is not None:
        return

    _report_queue = asyncio.Queue()

    async def _worker():
        while True:
            try:
                usage = await _report_queue.get()
                try:
                    if config.cloud.enabled and config.cloud.usage_report_enabled:
                        client = CloudClient(
                            base_url=config.cloud.base_url,
                            timeout_ms=5000.0
                        )
                        success = client.report_usage(usage)
                        if success:
                            loguru.logger.debug(f"[USAGE_REPORTED] request_id={usage.request_id}")
                        else:
                            loguru.logger.debug(f"[USAGE_REPORT_SKIPPED] request_id={usage.request_id}")
                except Exception as e:
                    loguru.logger.warning(f"[USAGE_REPORT_FAILED] request_id={usage.request_id}, error={e}")
                finally:
                    _report_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    _report_worker_task = asyncio.create_task(_worker())


def report_usage_async(
    request_id: str,
    tenant: Optional[str] = None,
    saved_tokens: int = 0,
    savings_ratio: float = 0.0,
    request_count: int = 1
):
    """
    异步上报 usage（best effort，不阻塞主流程）
    """
    if not config.cloud.enabled or not config.cloud.usage_report_enabled:
        return

    try:
        _ensure_worker()

        usage = UsageReport(
            request_id=request_id,
            tenant=tenant,
            saved_tokens=saved_tokens,
            savings_ratio=savings_ratio,
            request_count=request_count,
            timestamp=datetime.utcnow().isoformat() + "Z"
        )

        if _report_queue is not None:
            _report_queue.put_nowait(usage)
    except Exception as e:
        loguru.logger.warning(f"[USAGE_QUEUE_FAILED] request_id={request_id}, error={e}")
