# Backup And Recovery

## Backup Targets

- `output/` generated artifacts
- `projects/generated/` intermediate deck JSON files
- `.env` (stored in secure secrets manager, never commit)
- `CHANGELOG.md` and release tags (source-of-truth for deployed versions)

## Backup Cadence

- Nightly automated backup for generated artifacts.
- Pre-release manual backup snapshot.

## Automated Backup Workflow

Use `.github/workflows/nightly-backup.yml`:

- Bundles selected folders into archive.
- Uploads artifact to GitHub Actions artifacts for retention.

## Manual Backup

```powershell
Compress-Archive -Path .\output,.\projects\generated -DestinationPath .\output\backup-manual.zip -Force
```

## Recovery Steps

1. Download latest successful backup artifact.
2. Restore files into workspace:
   - `output/`
   - `projects/generated/`
3. Restore `.env` from secure secret store.
4. Run smoke validation:
   - `python .\main.py --help`
   - `python -m pytest tests/test_cli.py -q`

## Recovery Validation Criteria

- CLI starts without config errors.
- Deck JSON can render through `v2-render`.
- Recent regression tests pass.
