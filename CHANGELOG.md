# Changelog

All notable changes to this project are documented in this file.

The format is based on Keep a Changelog and this project follows Semantic Versioning.

## [Unreleased]

### Added
- Added root `.env.example` with OpenAI/Anthropic and runtime configuration keys.
- Added root `CHANGELOG.md` for release tracking.
- Added optional LLM heartbeat progress output via `SIE_AUTOPPT_STREAM_PROGRESS`.

### Changed
- Clarifier web input validation now uses unified `ClarifierRequestError` instead of raw `ValueError`.
- Clarifier web endpoint now normalizes invalid session payload errors into user-facing 400 responses.
- Updated `.gitignore` to exclude local env files and `.ruff_cache`.
- Enforced CI coverage gate threshold (`coverage report --fail-under=70`).
- Split `cli.py` by extracting V2/health command handling into `tools/sie_autoppt/cli_v2_commands.py`.
