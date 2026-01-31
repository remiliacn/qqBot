import asyncio
from pathlib import Path

from loguru import logger


async def delete_file_after(file_path: str, delay_seconds: float) -> None:
    await asyncio.sleep(delay_seconds)
    path = Path(file_path)
    if not path.exists():
        return

    try:
        path.unlink()
    except OSError:
        logger.exception("Failed to delete file: {}", file_path)
