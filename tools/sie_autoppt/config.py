import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSETS_DIR = PROJECT_ROOT / "assets"
TEMPLATES_DIR = ASSETS_DIR / "templates"
INPUT_DIR = PROJECT_ROOT / "input"
PROJECTS_DIR = PROJECT_ROOT / "projects"
PATTERN_FILE = PROJECT_ROOT / "skills" / "sie-autoppt" / "references" / "business-slide-patterns.json"


def _default_output_dir() -> Path:
    configured = os.environ.get("SIE_AUTOPPT_OUTPUT_DIR")
    if configured:
        return Path(configured).expanduser()
    desktop = Path.home() / "Desktop"
    if desktop.exists():
        return desktop
    return PROJECTS_DIR / "generated"


DEFAULT_TEMPLATE = TEMPLATES_DIR / "sie_template.pptx"
DEFAULT_HTML = INPUT_DIR / "uat_plan_sample.html"
DEFAULT_REFERENCE_BODY = INPUT_DIR / "reference_body_style.pptx"
DEFAULT_OUTPUT_DIR = _default_output_dir()
DEFAULT_OUTPUT_PREFIX = "SIE_AutoPPT"
DEFAULT_MIN_TEMPLATE_SLIDES = 5
MAX_BODY_CHAPTERS = 3

# Theme
FONT_NAME = "Microsoft YaHei"
COLOR_ACTIVE = (173, 5, 61)
COLOR_INACTIVE = (184, 196, 201)

# Template role indices (0-based)
IDX_WELCOME = 0
IDX_THEME = 1
IDX_DIRECTORY = 2
IDX_BODY_TEMPLATE = 3
