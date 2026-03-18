from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config import get_settings
from core.logging import get_logger, setup_logging
from core.mongodb import close_mongo_client, ping_mongo
from services.weakness_batch_service import WeaknessBatchService


async def _main(batch_size: int) -> None:
    settings = get_settings()
    setup_logging(environment=settings.ENVIRONMENT, log_dir=settings.log_directory)
    logger = get_logger(__name__)

    if not await ping_mongo():
        raise RuntimeError("MongoDB 연결에 실패했습니다.")

    service = WeaknessBatchService()
    result = await service.run_once(batch_size=batch_size)
    logger.info("weakness batch result | %s", result)

    await close_mongo_client()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run weakness profile batch job")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Number of turn analyses to process per run",
    )
    args = parser.parse_args()
    asyncio.run(_main(batch_size=args.batch_size))


if __name__ == "__main__":
    main()
