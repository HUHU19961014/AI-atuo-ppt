from __future__ import annotations

import subprocess
from pathlib import Path
from urllib.parse import quote

DEFAULT_SCREENSHOT_TIMEOUT_SEC = 120


def resolve_browser_path(explicit_path: str = "") -> Path:
    candidates = [Path(explicit_path)] if explicit_path else []
    candidates.extend(
        [
            Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
            Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
            Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
            Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        ]
    )
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate
    raise FileNotFoundError("Could not find Edge/Chrome. Please pass --browser with a valid path.")


def html_file_to_url(html_path: Path) -> str:
    resolved = html_path.resolve().as_posix()
    return f"file:///{quote(resolved, safe=':/()_-.,')}"


def capture_html_screenshot(
    html_path: Path,
    screenshot_path: Path,
    *,
    width: int = 1280,
    height: int = 720,
    browser_path: str = "",
) -> Path:
    browser = resolve_browser_path(browser_path)
    resolved_html = html_path.resolve()
    resolved_screenshot = screenshot_path.resolve()
    resolved_screenshot.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(browser),
        "--headless",
        f"--screenshot={resolved_screenshot}",
        f"--window-size={width},{height}",
        "--hide-scrollbars",
        "--disable-gpu",
        html_file_to_url(resolved_html),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            check=False,
            timeout=DEFAULT_SCREENSHOT_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Failed to capture HTML screenshot: timed out after {DEFAULT_SCREENSHOT_TIMEOUT_SEC}s.") from exc
    if result.returncode != 0 or not resolved_screenshot.exists():
        raw_output = result.stderr or result.stdout or b""
        detail = raw_output.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Failed to capture HTML screenshot. {detail or 'No output from browser.'}")
    return resolved_screenshot
