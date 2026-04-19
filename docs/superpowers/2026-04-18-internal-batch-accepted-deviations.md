# Internal Batch Accepted Deviations (P0/P1)

Reference plan: `docs/superpowers/plans/2026-04-17-internal-batch-pptmaster-p0-p1-plan.md`

## Accepted deviation

- `InputEnvelope` stays as top-level:
  - `run_id`
  - `created_at`
  - `mode`
  - `inputs`

## Decision

- This top-level `InputEnvelope` format is accepted for the P0/P1 closure.
- Do not roll back to a nested `run` object in this round.
- Follow-up work (if needed) must be tracked as a new explicit compatibility task.
