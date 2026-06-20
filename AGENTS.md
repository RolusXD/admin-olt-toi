# AI Operating Rules

These instructions apply to every AI coding tool working in this repository.

## Mandatory Context Gate

Before changing code, database schemas, infrastructure or tests, read these files in order:

1. `ai-context/00_PROJECT_CONTEXT.md`
2. `ai-context/01_PROJECT_HISTORY.md`
3. `ai-context/03_IMPORTACION_OLT.md`
4. `ai-context/04_DEVELOPMENT_RULES.md`
5. `ai-context/05_TODO.md`

Do not begin implementation until this context gate is complete. Read `ai-context/02_ARCHITECTURE.md` when the task affects module boundaries, data ownership or deployment.

## Required Handoff Updates

After every material change:

- Update `ai-context/05_TODO.md` with remaining or completed follow-up work.
- Append the milestone and verification result to `ai-context/06_CHANGELOG_AI.md`.
- Update `ai-context/00_PROJECT_CONTEXT.md` when runtime, migrations, safety state, production identity or project capabilities changed.

## Non-Negotiable Safety

- Never connect to an OLT unless the user explicitly authorizes it for the current task.
- Stored credentials do not imply authorization.
- Never run provisioning or configuration commands as part of tests or inspection.
- Preserve OLT ownership boundaries and existing manual data.
- Never commit secrets, real Telnet exports, production configuration snapshots or sensitive command logs.

