# Visual Review Container

When LibreOffice or PowerPoint COM is unavailable on the host, visual review can export slide previews through Docker.

## Build Image

```bash
docker compose -f docker/compose.visual-review.yml build
```

## Enable Docker Fallback

Set:

- `SIE_AUTOPPT_VISUAL_REVIEW_DOCKER_ENABLED=1`
- Optional: `SIE_AUTOPPT_VISUAL_REVIEW_DOCKER_IMAGE=libreoffice-docker:latest`

Then run existing `review` / `iterate` commands as usual.  
If `soffice` is missing locally, the runtime will call `docker run ... soffice --headless --convert-to png`.

## CI Notes

- Add Docker service availability in CI runners.
- Build the image once per workflow (or pre-publish and pull).
- Keep preview export timeout aligned with `DEFAULT_PREVIEW_EXPORT_TIMEOUT_SEC` in `tools/sie_autoppt/v2/visual_review.py`.
