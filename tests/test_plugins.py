import os
import sys
import types
import unittest
from unittest.mock import patch

from tools.sie_autoppt import plugins
from tools.sie_autoppt.v2 import layout_router


class PluginRegistryTests(unittest.TestCase):
    def tearDown(self):
        plugins.reset_plugin_registry_for_tests()

    def test_load_plugin_modules_registers_layout_and_model_hooks(self):
        module_name = "tests.fake_plugin_registry"
        fake_module = types.ModuleType(module_name)

        def _register_layout(register):
            register("plugin_layout", lambda *args, **kwargs: {"kind": "layout"})

        def _register_adapter(register):
            register("plugin_adapter", lambda model=None: {"adapter": "plugin", "model": model})

        fake_module.register_layout_renderers = _register_layout
        fake_module.register_model_adapters = _register_adapter

        with patch.dict(sys.modules, {module_name: fake_module}):
            with patch.dict(os.environ, {"SIE_AUTOPPT_PLUGIN_MODULES": module_name}):
                loaded = plugins.load_plugin_modules()
                self.assertIn(module_name, loaded)

                renderers = plugins.plugin_layout_renderers()
                self.assertIn("plugin_layout", renderers)

                adapter_factory = plugins.resolve_model_adapter("plugin_adapter")
                self.assertIsNotNone(adapter_factory)
                self.assertEqual(adapter_factory("gpt-test")["model"], "gpt-test")

    def test_layout_router_uses_plugin_renderers(self):
        fake_renderer = lambda *args, **kwargs: "plugin-render-ok"
        with patch("tools.sie_autoppt.v2.layout_router.plugin_layout_renderers", return_value={"plugin_layout": fake_renderer}):
            slide = type("Slide", (), {"layout": "plugin_layout"})()
            rendered = layout_router.render_slide(None, slide, None, None, 1, 1)
        self.assertEqual(rendered, "plugin-render-ok")
