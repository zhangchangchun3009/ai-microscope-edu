"""浮标坐标读写：损坏文件则回默认并仍能夹紧。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SOFTWARE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SOFTWARE))

from app.fab_store import load_fab, save_fab  # noqa: E402
from app.shell_state import FabPos, default_fab_pos  # noqa: E402


def test_roundtrip(tmp_path: Path) -> None:
    """保存后的浮标坐标应可原样读取。"""
    path = tmp_path / "fab.json"
    save_fab(path, FabPos(40, 80))
    loaded = load_fab(path, width=1080, height=1920)
    assert loaded.x == 40
    assert loaded.y == 80
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["v"] == 2


def test_legacy_unversioned_fab_uses_right_center(tmp_path: Path) -> None:
    """首版左上角存档没有版本号，应改用右侧居中，避免旧默认位置粘住。"""
    path = tmp_path / "fab.json"
    path.write_text(json.dumps({"x": 8, "y": 8}), encoding="utf-8")
    expected = default_fab_pos(1920, 1080)
    loaded = load_fab(path, width=1920, height=1080)
    assert loaded.x == pytest.approx(expected.x)
    assert loaded.y == pytest.approx(expected.y)


def test_missing_and_corrupt_use_right_center(tmp_path: Path) -> None:
    """文件缺失或损坏时应使用右侧垂直居中默认坐标。"""
    expected = default_fab_pos(1080, 1920)
    missing = load_fab(tmp_path / "nope.json", width=1080, height=1920)
    assert missing.x == pytest.approx(expected.x)
    assert missing.y == pytest.approx(expected.y)
    (tmp_path / "bad.json").write_text("{")
    bad = load_fab(tmp_path / "bad.json", width=1080, height=1920)
    assert bad.x == pytest.approx(expected.x)


def test_non_finite_coordinate_uses_right_center(tmp_path: Path) -> None:
    """JSON 非有限坐标无效，应回退到右侧居中默认值。"""
    path = tmp_path / "fab.json"
    path.write_text(
        json.dumps({"x": float("nan"), "y": 1}, allow_nan=True),
        encoding="utf-8",
    )
    expected = default_fab_pos(1080, 1920)
    loaded = load_fab(path, width=1080, height=1920)
    assert loaded.x == pytest.approx(expected.x)
    assert loaded.y == pytest.approx(expected.y)
