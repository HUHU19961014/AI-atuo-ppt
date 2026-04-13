# API Reference

This project primarily exposes a CLI interface, with selected Python modules intended for integration and automation.

## Public Runtime Modules

- `sie_autoppt.cli`
  - CLI entrypoint and command routing.
- `sie_autoppt.v2`
  - V2 semantic generation and rendering workflow.
- `sie_autoppt.clarifier`
  - Requirement clarification session and parsing utilities.
- `sie_autoppt.clarify_web`
  - Local web server wrapper for clarifier interactions.
- `sie_autoppt.exceptions`
  - Unified exception classes for configuration, runtime, and CLI behaviors.

## Suggested Stable Entry Points

- `sie_autoppt.cli.main()`
- `sie_autoppt.v2.make_v2_ppt(...)`
- `sie_autoppt.v2.generate_outline_with_ai(...)`
- `sie_autoppt.v2.generate_semantic_deck_with_ai(...)`
- `sie_autoppt.v2.generate_ppt(...)`
- `sie_autoppt.clarifier.clarify_user_input(...)`

## Notes

- Internal modules under `sie_autoppt.legacy` and many helper modules are not guaranteed to stay stable.
- Prefer CLI contracts (`docs/CLI_REFERENCE.md`) for external automation unless you need in-process integration.
