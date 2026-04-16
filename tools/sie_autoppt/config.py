import os
from pathlib import Path
from urllib.parse import urlparse

from .sample_registry import INPUT_SAMPLES_DIR

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSETS_DIR = PROJECT_ROOT / "assets"
TEMPLATES_DIR = ASSETS_DIR / "templates"
INPUT_DIR = INPUT_SAMPLES_DIR
PROJECTS_DIR = PROJECT_ROOT / "projects"
PATTERN_FILE = PROJECT_ROOT / "skills" / "sie-autoppt" / "references" / "business-slide-patterns.json"


def _default_output_dir() -> Path:
    configured = os.environ.get("SIE_AUTOPPT_OUTPUT_DIR")
    if configured:
        return Path(configured).expanduser()
    return PROJECT_ROOT / "output"


DEFAULT_TEMPLATE = TEMPLATES_DIR / "sie_template.pptx"
DEFAULT_TEMPLATE_MANIFEST = TEMPLATES_DIR / "sie_template.manifest.json"
DEFAULT_HTML = INPUT_DIR / "uat_plan_sample.html"
DEFAULT_REFERENCE_BODY = INPUT_DIR / "reference_body_style.pptx"
DEFAULT_OUTPUT_DIR = _default_output_dir()
DEFAULT_OUTPUT_PREFIX = "Enterprise-AI-PPT"
DEFAULT_MIN_TEMPLATE_SLIDES = 5
# 0 means "auto": explicit <slide> HTML keeps detected pages, legacy HTML infers 3-5 pages from content density.
DEFAULT_HTML_BODY_CHAPTERS = 0
MAX_BODY_CHAPTERS = 20
DEFAULT_AI_MODEL = os.environ.get("SIE_AUTOPPT_LLM_MODEL", "gpt-4o-mini")
DEFAULT_AI_TIMEOUT_SEC = float(os.environ.get("SIE_AUTOPPT_LLM_TIMEOUT_SEC", "90"))
DEFAULT_AI_REASONING_EFFORT = os.environ.get("SIE_AUTOPPT_LLM_REASONING_EFFORT", "low")
DEFAULT_AI_TEXT_VERBOSITY = os.environ.get("SIE_AUTOPPT_LLM_VERBOSITY", "low")
DEFAULT_AI_SOURCE_CHAR_LIMIT = 12000
DEFAULT_AI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")


def infer_llm_api_style(base_url: str, configured_style: str | None = None) -> str:
    candidate = (configured_style or os.environ.get("SIE_AUTOPPT_LLM_API_STYLE", "")).strip().lower().replace("-", "_")
    if candidate:
        if candidate not in {"responses", "chat_completions", "auto"}:
            raise ValueError(f"Unsupported SIE_AUTOPPT_LLM_API_STYLE: {candidate}")
        return candidate

    netloc = urlparse(base_url).netloc.lower()
    if "api.openai.com" in netloc or "openrouter.ai" in netloc:
        return "responses"
    return "auto"


DEFAULT_AI_API_STYLE = infer_llm_api_style(DEFAULT_AI_BASE_URL)
DEFAULT_PATTERN_LOW_CONFIDENCE_SCORE = int(os.environ.get("SIE_AUTOPPT_PATTERN_LOW_CONFIDENCE_SCORE", "4"))
DEFAULT_PATTERN_MARGIN_THRESHOLD = int(os.environ.get("SIE_AUTOPPT_PATTERN_MARGIN_THRESHOLD", "1"))
ENABLE_AI_PATTERN_ASSIST = os.environ.get("SIE_AUTOPPT_ENABLE_AI_PATTERN_ASSIST", "").strip().lower() not in {"0", "false", "no"}
DEFAULT_PATTERN_ASSIST_MODEL = os.environ.get("SIE_AUTOPPT_PATTERN_ASSIST_MODEL", DEFAULT_AI_MODEL)

# Theme
FONT_NAME = "Microsoft YaHei"
COLOR_ACTIVE = (173, 5, 61)
COLOR_INACTIVE = (184, 196, 201)
