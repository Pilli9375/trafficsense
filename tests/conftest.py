import pytest

from trafficsense.config import load_config, repo_root


@pytest.fixture(scope="session")
def cfg():
    return load_config("configs/default.yaml")


@pytest.fixture(scope="session")
def synthetic_4x4(cfg):
    sc = cfg["scenarios"]["synthetic_4x4"]
    paths = {k: repo_root() / v for k, v in sc.items()}
    missing = [str(p) for p in paths.values() if not p.is_file()]
    if missing:
        pytest.fail(f"Missing scenario files {missing}; run scripts/fetch_collmlight_data.sh")
    return paths
