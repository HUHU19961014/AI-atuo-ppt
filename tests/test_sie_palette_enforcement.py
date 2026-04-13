import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RENDERERS_DIR = ROOT / "tools" / "sie_autoppt" / "v2" / "renderers"
FIXED_THEME_PATH = ROOT / "tools" / "sie_autoppt" / "v2" / "themes" / "sie_consulting_fixed.json"
HEX_COLOR = re.compile(r"#[0-9A-Fa-f]{6}")
FORBIDDEN_FONTS = re.compile(r"\b(?:Arial|Inter|Roboto)\b", re.IGNORECASE)


class SiePaletteEnforcementTests(unittest.TestCase):
    def test_renderers_have_no_hardcoded_hex_colors(self):
        offenders: list[str] = []
        for file_path in sorted(RENDERERS_DIR.glob("*.py")):
            content = file_path.read_text(encoding="utf-8")
            if HEX_COLOR.search(content):
                offenders.append(str(file_path))
        self.assertEqual(offenders, [])

    def test_renderers_have_no_non_yahei_font_literals(self):
        offenders: list[str] = []
        for file_path in sorted(RENDERERS_DIR.glob("*.py")):
            content = file_path.read_text(encoding="utf-8")
            if FORBIDDEN_FONTS.search(content):
                offenders.append(str(file_path))
        self.assertEqual(offenders, [])

    def test_fixed_theme_uses_yahei_font_family(self):
        payload = json.loads(FIXED_THEME_PATH.read_text(encoding="utf-8"))
        fonts = payload.get("fonts", {})
        for key in ("title", "body", "fallback"):
            value = str(fonts.get(key, "")).strip()
            self.assertIn("微软雅黑", value, msg=f"{key} must use 微软雅黑 family")

