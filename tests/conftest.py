import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session", autouse=True)
def demo_db(tmp_path_factory):
    """Fresh SQLite database with the demo data, no network scraping."""
    db = tmp_path_factory.mktemp("db") / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db}"
    os.environ["ENABLE_LIVE_SCRAPING"] = "false"
    os.environ["ANTHROPIC_API_KEY"] = ""

    from core.config import get_settings
    from core.db import _session_factory, get_engine

    get_settings.cache_clear()
    get_engine.cache_clear()
    _session_factory.cache_clear()

    from core.db import init_db
    from scripts.seed_demo import load_demo, register_vendors

    init_db()
    register_vendors()
    load_demo()
    yield
