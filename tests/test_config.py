import pytest

from trafficsense.config import load_config, repo_root, resolve_path


def test_repo_root_has_pyproject():
    assert (repo_root() / "pyproject.toml").is_file()


def test_default_config_paths_resolve_under_repo():
    cfg = load_config("configs/default.yaml")
    root = repo_root()
    for key in cfg["paths"]:
        assert resolve_path(cfg, key).is_relative_to(root)


def test_missing_path_key_raises():
    with pytest.raises(KeyError):
        resolve_path({"paths": {}}, "nope")


def test_absolute_path_rejected():
    with pytest.raises(ValueError):
        resolve_path({"paths": {"x": "/etc"}}, "x")


def test_missing_config_file_raises():
    with pytest.raises(FileNotFoundError):
        load_config("configs/does_not_exist.yaml")
