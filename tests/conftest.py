from __future__ import annotations

import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
project_root_str = str(PROJECT_ROOT)
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)


_ISOLATED_ENV_VARS = (
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_ORG_ID",
    "OPENAI_PROJECT_ID",
    "SIE_AUTOPPT_ALLOW_EMPTY_API_KEY",
    "SIE_AUTOPPT_LLM_API_STYLE",
    "SIE_AUTOPPT_RUN_REAL_AI_TESTS",
    "SIE_AUTOPPT_REAL_AI_TOPIC",
    "SIE_AUTOPPT_REAL_AI_GENERATION_MODE",
    "SIE_AUTOPPT_REAL_AI_WITH_RENDER",
)


@pytest.fixture(autouse=True)
def isolate_ai_environment(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest):
    if "test_real_ai_smoke.py" in request.node.nodeid:
        return
    for name in _ISOLATED_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
