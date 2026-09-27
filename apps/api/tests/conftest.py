import pytest

from src.data.repositories import clear_caches
from src.capacityos.historical import clear_cache as clear_hist
from src.owners.run_store import runs
from src.scenario_store import store


@pytest.fixture(autouse=True)
def _fresh_state():
    clear_caches()
    store.clear()
    runs.clear()
    clear_hist()
    yield
    clear_caches()
    store.clear()
    runs.clear()
    clear_hist()
