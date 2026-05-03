# Pipeline scheduling

The puriy pipeline (CU-11) runs on a hybrid schedule:

- **Per-trip event trigger** — when a recording session ends with a
  line assigned, the API process fires
  `services.pipeline_trigger.run_clean_traces_for_line` via FastAPI
  `BackgroundTasks`. This runs only the `clean_traces` step, scoped to
  the one line the user just contributed to. Gives users a tight
  feedback loop without waiting for the next cron tick. Every run is
  recorded in `PipelineRun` with `trigger="event:recording_end"`.
- **Periodic batch jobs** — heavier per-line aggregations
  (`reconstruct_routes`, `resolve_*`, `rebuild_graph`,
  `infer_schedules`, housekeeping) run from the host's `cron` against
  the `pipeline` one-shot service in
  `infra/deploy/docker-compose.yml`. Recorded with `trigger="cron"`.

## Install on the deploy host

1. Adjust `PUR_DEPLOY` in [crontab.example](crontab.example) to your
   deploy path (defaults to `/opt/puriy/infra/deploy`).
2. Make sure `/var/log/puriy-pipeline.log` is writable by the user
   running cron.
3. Install the crontab:
   ```bash
   crontab -u <deploy-user> infra/deploy/cron/crontab.example
   ```
4. Verify:
   ```bash
   crontab -u <deploy-user> -l
   ```

## Manual one-off run

```bash
cd infra/deploy
docker compose --profile jobs run --rm pipeline run --all
```

## Cadence overview

| What | When | Why |
|---|---|---|
| `clean_traces` (per line) | event-driven on session end | Tight feedback loop for the contributing user |
| `deduplicate_lines + reconstruct_routes + resolve_edge_votes + resolve_routes + resolve_line_votes + rebuild_graph` | every 6 h | Fresh enough to surface new ramales / promotions; not so frequent it churns route versions |
| `infer_schedules` | daily 03:15 | Trip-timestamp aggregation; no need for finer cadence |
| `cleanup` | daily 04:00 | Bounded stale-row growth |
| `/detours/cleanup` + `/recordings/cleanup/stale` | daily 04:30 | Server-side cleanup endpoints |

## Run history

Every cron tick produces a `PipelineRun` row visible via:

```bash
docker compose --profile jobs run --rm pipeline history --limit 20
```

For finer-grained debugging, query `PipelineRun` and
`PipelineStepResult` directly via the database.

## Future work — orchestrator migration

For larger deployments, this cron-based scheduler can be migrated to
[Prefect](https://www.prefect.io/) without changing the pipeline
itself: the `run_pipeline` runner already records every run as a
`PipelineRun` row with a `trigger` field, so a Prefect-based orchestrator
would just substitute `trigger="prefect"` and gain UI / retries / event
triggers on top of the same execution + telemetry contract.
