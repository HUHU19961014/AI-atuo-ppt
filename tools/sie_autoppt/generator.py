from .legacy.generator import (
    build_output_path,
    generate_ppt,
    generate_ppt_artifacts_from_deck_plan,
    generate_ppt_artifacts_from_deck_spec,
    generate_ppt_artifacts_from_html,
    validate_slide_pool_configuration,
)


__all__ = [
    "build_output_path",
    "generate_ppt",
    "generate_ppt_artifacts_from_deck_plan",
    "generate_ppt_artifacts_from_deck_spec",
    "generate_ppt_artifacts_from_html",
    "validate_slide_pool_configuration",
]
