"""풀 한 항목 변경과 예상하지 못한 배포본 보호."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "pool_trial", Path(__file__).parents[1] / "pool_trial.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
patch_pool = module.patch_pool


def test_pool_trial_changes_only_capacity():
    source = '"pool_size": 3,\n"max_overflow": 2,\n"pool_timeout": 3,\n'
    changed = patch_pool(source)
    assert '"pool_size": 5,' in changed
    assert '"max_overflow": 5,' in changed
    assert '"pool_timeout": 3,' in changed
    with pytest.raises(ValueError, match="unexpected_pool_source"):
        patch_pool(changed)
