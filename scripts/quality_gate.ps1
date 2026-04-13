Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "[1/6] Ruff (CLI targeted F checks)"
python -m ruff check tools/sie_autoppt/cli.py tools/sie_autoppt/clarify_web.py tools/sie_autoppt/exceptions.py tools/sie_autoppt/cli_parser.py --select F

Write-Host "[2/6] Ruff (V2/planning/qa targeted F checks)"
python -m ruff check tools/sie_autoppt/v2 tools/sie_autoppt/planning tools/sie_autoppt/qa --select F

Write-Host "[3/6] Ruff (targeted tests F checks)"
python -m ruff check tests/test_cli.py tests/test_clarify_web.py tests/test_v2_services.py tests/test_v2_quality_checks.py --select F

Write-Host "[4/6] Mypy (release target files)"
python -m mypy tools/sie_autoppt/llm_openai.py tools/sie_autoppt/cli_v2_commands.py tools/sie_autoppt/language_policy.py

Write-Host "[5/6] Legacy boundary guard"
python tools/check_legacy_boundary.py

Write-Host "[6/6] Release subset tests + coverage gate"
python -m pytest tests/test_cli.py tests/test_v2_cli.py tests/test_runtime_resilience.py tests/test_project_hygiene.py tests/test_clarify_web.py tests/test_clarifier.py tests/test_v2_services.py tests/test_v2_quality_checks.py tests/test_plugins.py tests/test_language_policy.py -q
python -m coverage run --source=tools.sie_autoppt.cli,tools.sie_autoppt.cli_v2_commands,tools.sie_autoppt.exceptions -m pytest tests/test_cli.py tests/test_v2_cli.py tests/test_clarifier.py tests/test_clarify_web.py -q
python -m coverage report -m --fail-under=80

Write-Host "quality gate passed"
