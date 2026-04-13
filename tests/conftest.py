from __future__ import annotations

import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

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

_TEMP_ROOT = PROJECT_ROOT / ".tmp_test_runtime"
_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
_TEMP_ROOT_STR = str(_TEMP_ROOT)

# Ensure process-level temp env always points to writable workspace path.
tempfile.tempdir = _TEMP_ROOT_STR
os.environ["TEMP"] = _TEMP_ROOT_STR
os.environ["TMP"] = _TEMP_ROOT_STR
os.environ["TMPDIR"] = _TEMP_ROOT_STR


def _safe_mkdtemp(suffix: str | None = None, prefix: str | None = None, dir: str | None = None):
    base_dir = Path(dir) if dir else _TEMP_ROOT
    base_dir.mkdir(parents=True, exist_ok=True)
    final_prefix = prefix or "tmp_"
    final_suffix = suffix or ""
    for _ in range(1000):
        candidate = base_dir / f"{final_prefix}{uuid4().hex}{final_suffix}"
        try:
            candidate.mkdir(parents=False, exist_ok=False)
            return str(candidate)
        except FileExistsError:
            continue
    raise RuntimeError("Unable to create temporary directory after multiple attempts.")


@dataclass
class _SafeTemporaryDirectory:
    suffix: str | None = None
    prefix: str | None = None
    dir: str | None = None
    name: str | None = None

    def __enter__(self) -> str:
        self.name = _safe_mkdtemp(self.suffix, self.prefix, self.dir)
        return self.name

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.cleanup()
        return False

    def cleanup(self) -> None:
        if self.name:
            shutil.rmtree(self.name, ignore_errors=True)


# Apply globally so unittest-style tests are covered too.
tempfile.mkdtemp = _safe_mkdtemp
tempfile.TemporaryDirectory = _SafeTemporaryDirectory


@pytest.fixture(autouse=True)
def isolate_ai_environment(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest):
    if "test_real_ai_smoke.py" in request.node.nodeid:
        return
    for name in _ISOLATED_ENV_VARS:
        monkeypatch.delenv(name, raising=False)

