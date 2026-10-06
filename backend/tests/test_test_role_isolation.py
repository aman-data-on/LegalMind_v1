"""The test role cannot read live data (kickoff item 8, 2026-10-01).

Opt-in, because it connects to the LIVE database's name — read-only, and expecting to
be refused. Set LEGALMIND_LIVE_DATABASE_NAME (e.g. `legalmind_v1_dev`) to run it. It
proves the isolation `/root/.legalmind-test.env` is meant to give: the role the suite
runs as owns only its own database and is refused on every live table it tries.
"""
import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

from legalmind import config

LIVE = os.environ.get("LEGALMIND_LIVE_DATABASE_NAME")

pytestmark = pytest.mark.skipif(not LIVE, reason="set LEGALMIND_LIVE_DATABASE_NAME to run")


@pytest.mark.parametrize("table", ["public.users", "public.contracts",
                                   "public.document_evidence", "assist.messages",
                                   "assist.chunks"])
def test_the_test_role_is_refused_on_live_tables(table):
    url = config.test_database_url().rsplit("/", 1)[0] + f"/{LIVE}"
    with create_engine(url).connect() as conn, pytest.raises(ProgrammingError) as refused:
        conn.execute(text(f"SELECT 1 FROM {table} LIMIT 1"))
    assert "permission denied" in str(refused.value)
