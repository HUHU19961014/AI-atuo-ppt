from tools.sie_autoppt import generator, pipeline, slide_ops
from tools.sie_autoppt.legacy import generator as legacy_generator
from tools.sie_autoppt.legacy import pipeline as legacy_pipeline
from tools.sie_autoppt.legacy import reference_styles as legacy_reference_styles
from tools.sie_autoppt.legacy import body_renderers as legacy_body_renderers
from tools.sie_autoppt.legacy import presentation_ops
from tools.sie_autoppt.legacy import openxml_slide_ops
from tools.sie_autoppt import body_renderers, reference_styles


def test_generator_module_reexports_legacy_entrypoints():
    assert generator.build_output_path is legacy_generator.build_output_path
    assert generator.generate_ppt is legacy_generator.generate_ppt
    assert generator.generate_ppt_artifacts_from_deck_spec is legacy_generator.generate_ppt_artifacts_from_deck_spec
    assert generator.validate_slide_pool_configuration is legacy_generator.validate_slide_pool_configuration


def test_pipeline_module_reexports_legacy_entrypoints():
    assert pipeline.build_deck_plan is legacy_pipeline.build_deck_plan
    assert pipeline.plan_deck_from_html is legacy_pipeline.plan_deck_from_html
    assert pipeline.plan_deck_from_json is legacy_pipeline.plan_deck_from_json


def test_slide_ops_module_reexports_legacy_entrypoints():
    assert slide_ops.clone_slide_after is presentation_ops.clone_slide_after
    assert slide_ops.remove_slide is presentation_ops.remove_slide
    assert slide_ops.ensure_last_slide is presentation_ops.ensure_last_slide
    assert slide_ops.import_slides_from_presentation is openxml_slide_ops.import_slides_from_presentation
    assert slide_ops.copy_slide_xml_assets is openxml_slide_ops.copy_slide_xml_assets
    assert slide_ops.set_slide_metadata_names is openxml_slide_ops.set_slide_metadata_names


def test_reference_styles_module_reexports_legacy_entrypoints():
    assert reference_styles.build_reference_import_plan is legacy_reference_styles.build_reference_import_plan
    assert reference_styles.populate_reference_body_pages is legacy_reference_styles.populate_reference_body_pages
    assert reference_styles.locate_reference_slide_no is legacy_reference_styles.locate_reference_slide_no


def test_body_renderers_module_reexports_legacy_entrypoints():
    assert body_renderers.fill_body_slide is legacy_body_renderers.fill_body_slide
    assert body_renderers.fill_directory_slide is legacy_body_renderers.fill_directory_slide
    assert body_renderers.apply_theme_title is legacy_body_renderers.apply_theme_title
    assert body_renderers.resolve_render_pattern is legacy_body_renderers.resolve_render_pattern
