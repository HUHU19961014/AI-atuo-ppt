# Release Process

## Scope

This process covers versioned release preparation, quality validation, tagging, and rollback readiness.

## Pre-Release Checklist

1. Confirm `CHANGELOG.md` has an `[Unreleased]` summary for included changes.
2. Run local quality gates:
   - `python -m ruff check tools/sie_autoppt/cli.py tools/sie_autoppt/clarify_web.py tools/sie_autoppt/exceptions.py tools/sie_autoppt/cli_parser.py --select F`
   - `python -m pytest tests/test_cli.py tests/test_clarify_web.py tests/test_clarifier.py -q`
3. Validate critical generation path:
   - `python .\main.py make --topic "Release smoke test" --min-slides 3 --max-slides 4 --progress`
4. Confirm docs were updated when behavior changed:
   - `docs/CLI_REFERENCE.md`
   - `docs/TROUBLESHOOTING.md`
   - `docs/COMPATIBILITY_MATRIX.md`

## Versioning

1. Bump version in `pyproject.toml`.
2. Add release section to `CHANGELOG.md` with date.
3. Commit as: `chore(release): vX.Y.Z`.

## Release Validation

1. Trigger GitHub workflow `release-readiness.yml`.
2. Ensure all checks pass.
3. Tag:
   - `git tag vX.Y.Z`
   - `git push origin vX.Y.Z`

## Rollback

1. Identify last stable tag.
2. Re-deploy last stable package/artifact.
3. Open incident summary and append root cause + corrective actions to runbook.
