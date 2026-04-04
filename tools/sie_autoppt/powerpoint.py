from dataclasses import dataclass

try:
    import win32com.client as win32_client  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover
    win32_client = None


@dataclass(frozen=True)
class PowerPointRuntime:
    available: bool
    reason: str = ""


def get_powerpoint_runtime() -> PowerPointRuntime:
    if win32_client is None:
        return PowerPointRuntime(
            available=False,
            reason="win32com is unavailable; PowerPoint COM enhancement is disabled.",
        )
    return PowerPointRuntime(available=True)


def has_powerpoint_com() -> bool:
    return get_powerpoint_runtime().available


def open_powerpoint_application():
    runtime = get_powerpoint_runtime()
    if not runtime.available or win32_client is None:
        raise RuntimeError(runtime.reason or "PowerPoint COM is unavailable.")
    app = win32_client.Dispatch("PowerPoint.Application")
    app.Visible = 1
    return app
