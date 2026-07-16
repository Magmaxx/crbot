import asyncio
import logging
from typing import Callable, Awaitable, Optional


logger = logging.getLogger("watchdog")


class Watchdog:
    """
    Basit watchdog:
    - worker coroutine'i çalıştırır
    - hata olursa bekleyip restart eder
    """

    def __init__(
        self,
        worker_factory: Callable[[], Awaitable[None]],
        restart_delay_sec: float = 3.0,
        name: str = "worker",
    ):
        self.worker_factory = worker_factory
        self.restart_delay_sec = restart_delay_sec
        self.name = name
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def _runner(self):
        while self._running:
            try:
                logger.info(f"[{self.name}] starting")
                await self.worker_factory()
                logger.warning(f"[{self.name}] exited normally, restarting in {self.restart_delay_sec}s")
            except asyncio.CancelledError:
                logger.info(f"[{self.name}] cancelled")
                raise
            except Exception as e:
                logger.exception(f"[{self.name}] crashed: {e}")

            if self._running:
                await asyncio.sleep(self.restart_delay_sec)

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._runner())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
