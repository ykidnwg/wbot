"""Database-backed scheduling and publishing worker process."""

import asyncio
import logging
import signal

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.publishing import run_worker_cycle

logger = logging.getLogger(__name__)


async def worker_loop(stop: asyncio.Event) -> None:
    settings = get_settings()
    logger.info("Publishing worker started")
    while not stop.is_set():
        try:
            async with SessionLocal() as db:
                result = await run_worker_cycle(db)
                await db.commit()
                if result.dispatched or result.attempted or result.recovered:
                    logger.info(
                        "worker cycle recovered=%s dispatched=%s attempted=%s "
                        "succeeded=%s failed=%s",
                        result.recovered,
                        result.dispatched,
                        result.attempted,
                        result.succeeded,
                        result.failed,
                    )
        except Exception:
            logger.exception("Publishing worker cycle failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.worker_poll_seconds)
        except TimeoutError:
            continue
    logger.info("Publishing worker stopped")


async def run_forever() -> None:
    stop = asyncio.Event()

    def request_stop(*_: object) -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, request_stop)
        except NotImplementedError:
            signal.signal(sig, request_stop)

    await worker_loop(stop)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_forever())


if __name__ == "__main__":
    main()
