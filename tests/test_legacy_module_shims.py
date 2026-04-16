from tools.sie_autoppt import body_renderers, generator, pipeline, reference_styles, slide_ops


def test_generator_module_exposes_native_entrypoints():
    assert generator.build_output_path.__module__.startswith("tools.sie_autoppt.")
    assert generator.generate_ppt.__module__.startswith("tools.sie_autoppt.")
    assert generator.generate_ppt_artifacts_from_deck_spec.__module__.startswith("tools.sie_autoppt.")
    assert generator.validate_slide_pool_configuration.__module__.startswith("tools.sie_autoppt.")
    assert ".legacy." not in generator.build_output_path.__module__
    assert ".legacy." not in generator.generate_ppt.__module__
    assert ".legacy." not in generator.generate_ppt_artifacts_from_deck_spec.__module__
    assert ".legacy." not in generator.validate_slide_pool_configuration.__module__


def test_pipeline_module_exposes_native_entrypoints():
    assert pipeline.build_deck_plan.__module__ == "tools.sie_autoppt.pipeline"
    assert pipeline.plan_deck_from_html.__module__ == "tools.sie_autoppt.pipeline"
    assert pipeline.plan_deck_from_json.__module__ == "tools.sie_autoppt.pipeline"


def test_slide_ops_module_exposes_native_entrypoints():
    assert slide_ops.clone_slide_after.__module__ == "tools.sie_autoppt.presentation_ops"
    assert slide_ops.remove_slide.__module__ == "tools.sie_autoppt.presentation_ops"
    assert slide_ops.ensure_last_slide.__module__ == "tools.sie_autoppt.presentation_ops"
    assert slide_ops.import_slides_from_presentation.__module__ == "tools.sie_autoppt.openxml_slide_ops"
    assert slide_ops.copy_slide_xml_assets.__module__ == "tools.sie_autoppt.openxml_slide_ops"
    assert slide_ops.set_slide_metadata_names.__module__ == "tools.sie_autoppt.openxml_slide_ops"


def test_reference_styles_module_exposes_native_entrypoints():
    assert reference_styles.build_reference_import_plan.__module__ == "tools.sie_autoppt.reference_styles"
    assert reference_styles.populate_reference_body_pages.__module__ == "tools.sie_autoppt.reference_styles"
    assert reference_styles.locate_reference_slide_no.__module__ == "tools.sie_autoppt.reference_styles"


def test_body_renderers_module_exposes_native_entrypoints():
    assert body_renderers.fill_body_slide.__module__ == "tools.sie_autoppt.body_renderers"
    assert body_renderers.fill_directory_slide.__module__ == "tools.sie_autoppt.body_renderers"
    assert body_renderers.apply_theme_title.__module__ == "tools.sie_autoppt.body_renderers"
    assert body_renderers.resolve_render_pattern.__module__ == "tools.sie_autoppt.body_renderers"
