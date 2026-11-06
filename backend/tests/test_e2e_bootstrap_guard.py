"""`--recreate` drops only a database named for the harness (incident 2026-11-06)."""
import pytest

from tools.e2e_bootstrap import recreate_database

URL = "postgresql+psycopg2://u:p@127.0.0.1:1/"


@pytest.mark.parametrize("name", ["legalmind_clm_e2e", "legalmind_clm_demo", "legalmind", "harness_x"])
def test_a_database_not_named_for_the_harness_is_never_dropped(name: str) -> None:
    with pytest.raises(SystemExit, match="refusing to recreate"):
        recreate_database(URL + name)
