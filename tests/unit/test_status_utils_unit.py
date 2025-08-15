from __future__ import annotations


def test_success_and_error_status_roundtrip():
    from status import error_status, success_status

    s = success_status("ok", data={"x": 1}, details={"a": 2})
    assert s.is_success is True
    assert s.message == "ok"
    assert isinstance(s.details, dict) and s.details.get("a") == 2
    assert isinstance(s.data, dict) and s.data.get("x") == 1

    e = error_status("bad", details={"code": 500})
    assert e.is_success is False
    assert e.message == "bad"
    assert e.details.get("code") == 500


def test_unwrap_status_nested():
    from status import success_status
    from utils.status_utils import unwrap_status

    inner = success_status("inner", data={"v": 42}, details={"k": "v"})
    outer = success_status("outer", data=inner, details={"outer": True})

    data, details = unwrap_status(outer)
    assert isinstance(details, dict)
    # unwrap_status preserves outer details
    assert details.get("outer") is True
    # and returns inner data as the value
    assert isinstance(data, dict) and data.get("v") == 42


def test_unwrap_status_honors_max_depth():
    from status import success_status
    from utils.status_utils import unwrap_status

    level3 = success_status("l3", data=3, details={})
    level2 = success_status("l2", data=level3, details={})
    level1 = success_status("l1", data=level2, details={})

    data, _ = unwrap_status(level1, max_depth=1)
    # With max_depth=1, data should be the level2 status, not the raw 3
    assert hasattr(data, "is_success")
