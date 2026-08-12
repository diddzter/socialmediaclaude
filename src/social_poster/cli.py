from __future__ import annotations

import argparse
import logging
import sys

from .config import Settings
from .pipeline import run


def main() -> int:
    parser = argparse.ArgumentParser(description="Post new Drive videos to TikTok/Instagram with AI captions + music.")
    parser.add_argument("--dry-run", action="store_true", help="Render but don't publish; overrides DRY_RUN env var.")
    parser.add_argument("--max-videos", type=int, default=None, help="Override MAX_VIDEOS_PER_RUN.")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    settings = Settings()
    if args.dry_run:
        settings.dry_run = True
    if args.max_videos is not None:
        settings.max_videos_per_run = args.max_videos

    summary = run(settings)
    logging.info("Run summary: %s", summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
