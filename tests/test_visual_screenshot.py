import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.sie_autoppt.visual_screenshot import (
    capture_html_screenshot,
    html_file_to_url,
    resolve_browser_path,
)


class VisualScreenshotTests(unittest.TestCase):
    def test_html_file_to_url_handles_windows_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            html_path = Path(temp_dir) / "a b.html"
            html_path.write_text("<html></html>", encoding="utf-8")
            url = html_file_to_url(html_path)
            self.assertTrue(url.startswith("file:///"))
            self.assertIn("a%20b.html", url)

    def test_resolve_browser_path_raises_actionable_error(self):
        with patch("pathlib.Path.exists", return_value=False):
            with self.assertRaisesRegex(FileNotFoundError, "Please pass --browser"):
                resolve_browser_path("C:/not-exist/browser.exe")

    def test_capture_html_screenshot_invokes_headless_command(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            html_path = Path(temp_dir) / "preview.html"
            png_path = Path(temp_dir) / "preview.png"
            html_path.write_text("<html></html>", encoding="utf-8")
            browser_path = Path(temp_dir) / "msedge.exe"
            browser_path.write_bytes(b"fake")
            captured = {}

            def fake_run(command, capture_output=True, check=False, **kwargs):
                captured["command"] = command
                captured["kwargs"] = kwargs
                png_path.write_bytes(b"png")
                return type("Result", (), {"returncode": 0, "stderr": b"", "stdout": b""})()

            with patch("tools.sie_autoppt.visual_screenshot.subprocess.run", side_effect=fake_run):
                output = capture_html_screenshot(
                    html_path=html_path,
                    screenshot_path=png_path,
                    width=1280,
                    height=720,
                    browser_path=str(browser_path),
                )

            self.assertEqual(output, png_path.resolve())
            command = captured["command"]
            self.assertIn("--headless", command)
            self.assertIn("--hide-scrollbars", command)
            self.assertIn("--window-size=1280,720", command)
            self.assertTrue(any(str(item).startswith("--screenshot=") for item in command))
            self.assertIn("timeout", captured["kwargs"])


if __name__ == "__main__":
    unittest.main()
