"""Non-destructive Data Lifecycle maintenance scheduler."""

from __future__ import annotations

import asyncio
from typing import Optional

from .maintenance_manager import MaintenanceManager
from .policy import DataLifecyclePolicy, load_policy


class DataLifecycleScheduler:
    def __init__(
        self,
        *,
        manager: Optional[MaintenanceManager] = None,
        policy: Optional[DataLifecyclePolicy] = None,
    ) -> None:
        self._policy = policy or load_policy()
        self._manager = manager or MaintenanceManager(policy=self._policy)
        self._task: Optional[asyncio.Task] = None
        self._stopping: Optional[asyncio.Event] = None
        self._singleflight: Optional[asyncio.Lock] = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> bool:
        if not self._policy.maintenance_enabled:
            return False
        if self.running:
            return True
        self._stopping = asyncio.Event()
        self._singleflight = asyncio.Lock()
        self._task = asyncio.create_task(self._runner())
        return True

    async def stop(self) -> None:
        if self._stopping is not None:
            self._stopping.set()
        task = self._task
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None

    async def _sleep_or_stop(self, seconds: float) -> bool:
        if self._stopping is None:
            return True
        if seconds <= 0:
            return self._stopping.is_set()
        try:
            await asyncio.wait_for(self._stopping.wait(), timeout=seconds)
            return True
        except asyncio.TimeoutError:
            return self._stopping.is_set()

    async def _run_cycle(self, trigger: str) -> None:
        if self._singleflight is None:
            return
        if self._singleflight.locked():
            return
        async with self._singleflight:
            await asyncio.to_thread(self._manager.run_once, trigger)

    async def _runner(self) -> None:
        if self._stopping is None:
            return
        stopped = await self._sleep_or_stop(self._policy.maintenance_startup_delay_seconds)
        if stopped:
            return
        await self._run_cycle("startup_warm")
        while not self._stopping.is_set():
            stopped = await self._sleep_or_stop(self._policy.maintenance_interval_seconds)
            if stopped:
                break
            await self._run_cycle("interval_refresh")
