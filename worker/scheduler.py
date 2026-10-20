"""Nightly price refresh for compounds people have looked up recently.

    python -m worker.scheduler          # runs forever, refreshes at 02:00 local time
    python -m worker.scheduler --once   # refresh now and exit
"""

from __future__ import annotations

import argparse
import logging

from core import repository
from core.db import init_db
from core.pricing import scrape_compound
from scrapers.registry import enabled_scrapers

log = logging.getLogger("worker")


def refresh_recent(days: int = 30) -> None:
    keys = repository.recent_run_inchikeys(days)
    log.info("Refreshing prices for %d compounds", len(keys))
    scrapers = enabled_scrapers()
    for ik in keys:
        compound = repository.get_compound(ik)
        if not compound:
            continue
        offers, warnings = scrape_compound(compound, scrapers)
        log.info("%s: %d offers, %d warnings", compound.label, len(offers), len(warnings))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--once", action="store_true")
    p.add_argument("--hour", type=int, default=2)
    args = p.parse_args()
    init_db()
    if args.once:
        refresh_recent()
        return
    from apscheduler.schedulers.blocking import BlockingScheduler

    sched = BlockingScheduler()
    sched.add_job(refresh_recent, "cron", hour=args.hour, minute=0)
    log.info("Scheduler started; refresh daily at %02d:00", args.hour)
    sched.start()


if __name__ == "__main__":
    main()
