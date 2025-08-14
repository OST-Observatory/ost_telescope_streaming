class _Cfg:
    def __init__(self, enabled: bool) -> None:
        self._enabled = enabled

    def get_camera_config(self):
        return {"cooling": {"enable_cooling": self._enabled}}


def test_cooling_service_disabled_initialize():
    from services.cooling.service import CoolingService

    cs = CoolingService(config=_Cfg(False))
    st = cs.initialize(camera=object())
    assert st.is_success


def test_cooling_service_initialize_error(monkeypatch):
    from services.cooling.service import CoolingService

    def _raise(*args, **kwargs):  # pragma: no cover - simple stub
        raise RuntimeError("boom")

    monkeypatch.setitem(
        __import__("sys").modules,
        "services.cooling.backend",
        type("M", (), {"create_cooling_manager": _raise}),
    )
    cs = CoolingService(config=_Cfg(True))
    st = cs.initialize(camera=object())
    assert st.is_error


def test_cooling_service_properties_false_when_no_manager():
    from services.cooling.service import CoolingService

    cs = CoolingService(config=_Cfg(True))
    assert cs.is_cooling is False
    assert cs.is_warming_up is False
