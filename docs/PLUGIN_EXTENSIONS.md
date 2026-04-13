# Plugin Extensions

This project supports runtime plugin registration through environment variables.

## Enable Plugins

Set `SIE_AUTOPPT_PLUGIN_MODULES` to a comma-separated module list:

```powershell
$env:SIE_AUTOPPT_PLUGIN_MODULES="my_company.ppt_plugins,my_company.model_plugins"
```

Each plugin module can expose:

- `register_layout_renderers(register_fn)`
- `register_model_adapters(register_fn)`

## Layout Renderer Plugin

`register_layout_renderers` receives a callback:

- `register_fn(layout_name: str, renderer: callable) -> None`

If a slide layout name matches your plugin renderer, `v2/layout_router.py` will route to your renderer.

## Model Adapter Plugin

`register_model_adapters` receives a callback:

- `register_fn(name: str, factory: callable) -> None`

The factory signature:

- `factory(model: str | None) -> client`

Where `client` must support:

- `create_structured_json(developer_prompt, user_prompt, schema_name, schema)`

Then select adapter:

```powershell
$env:SIE_AUTOPPT_MODEL_ADAPTER="my_adapter"
```

Optional dedicated visual-review adapter:

```powershell
$env:SIE_AUTOPPT_VISION_MODEL_ADAPTER="my_adapter"
```
