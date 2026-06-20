# AI Handoff - TOI OLT Manager

## Project Summary

TOI OLT Manager is a FastAPI and Next.js application for multi-OLT inventory, ZTE C300 read-only monitoring, snapshot-based initial import, ONU discovery and controlled provisioning workflows.

## Resume With Codex

1. Open the repository root in Codex.
2. Ask Codex to read `AGENTS.md` and the mandatory files listed below before changing code.
3. State the exact scope and whether real OLT access is authorized. No authorization is assumed.
4. Ask for tests and frontend build verification appropriate to the change.
5. Require the AI context and changelog to be updated before handoff.

## Resume With an API Tool

Include `AGENTS.md` and the mandatory context files in the API request before the task specification. Give the tool repository access only, keep secrets in environment variables, and explicitly disable network or OLT access unless the current operation requires and authorizes it. Require a final response with changed files, tests, build result and unresolved risks.

## Read First

1. `ai-context/00_PROJECT_CONTEXT.md`
2. `ai-context/01_PROJECT_HISTORY.md`
3. `ai-context/03_IMPORTACION_OLT.md`
4. `ai-context/04_DEVELOPMENT_RULES.md`
5. `ai-context/05_TODO.md`

Also read `ai-context/02_ARCHITECTURE.md` for architectural work and `ai-context/06_CHANGELOG_AI.md` for recent implementation history.

## Rules Never To Omit

- Do not access a real OLT without explicit authorization for that task.
- Import and monitoring are read-only and every real command is audited.
- Never infer permission from saved credentials.
- Never commit `.env`, API keys, OLT credentials, real running-config exports or sensitive logs.
- Keep drivers, parsers, services and API routes separated.
- Scope imported and operational records by `olt_id`; do not mix OLT inventories.
- Preserve manual records and unrelated user changes.
- Update TODO, changelog and project context after material work.

## Last Known State

- Alembic head: `0033_complete_snapshots`.
- The V1 demo login is removed. Authentication requires local `ADMIN_USERNAME` and `ADMIN_PASSWORD_HASH` values and returns HTTP 503 while unconfigured.
- Generate an initial administrator with `python -m app.scripts.create_initial_admin --username <name>` inside the backend environment.
- Initial ZTE import persists and validates a complete checksummed running-config snapshot before parsing.
- Preview does not create definitive inventory; confirmation reuses the same validated snapshot.
- Local test suite: 98 passing tests on 2026-06-20.
- Frontend production build and rebuilt containers returned successfully on 2026-06-20; the backend image was rebuilt successfully after the authentication change.
- No real OLT access was performed for the snapshot refactor or this handoff preparation.

## Recommended Next Task

Add automated secret scanning to CI and replace the remaining local-development JWT, crypto and database placeholders with deployment-managed secrets before production rollout.
