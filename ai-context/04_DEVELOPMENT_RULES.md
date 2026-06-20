# Development Rules

## Mandatory Context Gate

Before any code, schema, infrastructure or test change, read in order:

1. `ai-context/00_PROJECT_CONTEXT.md`
2. `ai-context/01_PROJECT_HISTORY.md`
3. `ai-context/03_IMPORTACION_OLT.md`
4. `ai-context/04_DEVELOPMENT_RULES.md`
5. `ai-context/05_TODO.md`

This gate applies to Codex and every API-based coding tool. Read `02_ARCHITECTURE.md` as well when module boundaries, data ownership or deployment are affected.

## Safety

- Do not connect to a real OLT unless explicitly authorized for the current task.
- Do not infer permission from stored credentials.
- Import and monitoring commands must use `read_only=true`.
- Log every real CLI command in `DriverCommandLog`.
- Stop command sequences on the first CLI error.
- Never add `write` or `save` to automatic workflows.

## Engineering

- Keep drivers, parsers, services and API routes separate.
- Preserve existing manual data during imports.
- Scope every operational query and upsert by OLT.
- Add Alembic migrations for schema changes.
- Do not edit generated `.next` output.
- Keep unrelated user changes intact.

## Verification

- Canonical fixture: `tests/fixtures/zte_c300_running_config.txt`.
- Run tests with a local SQLite URL when the host lacks Psycopg:

```powershell
$env:DATABASE_URL='sqlite+pysqlite:///:memory:'
pytest -q
```

- Build frontend with `npm run build` from `frontend`.
- Rebuild deployment with `./scripts/rebuild-containers.ps1`.
- Verify HTTP endpoints without triggering client-side actions that call Telnet.

## Documentation

After every material change:

- Update `05_TODO.md` with remaining or completed follow-up work.
- Append the milestone and verification result to `06_CHANGELOG_AI.md`.
- Update `00_PROJECT_CONTEXT.md` when project state, runtime, migrations, safety posture or capabilities changed.
