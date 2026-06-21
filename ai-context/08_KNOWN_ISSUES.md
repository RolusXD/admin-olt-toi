# Known Issues

| Problema | Estado | Prioridad | Responsable |
| --- | --- | --- | --- |
| Integración de hooks pre-commit para Gitleaks | Pendiente | Alta | Equipo DevSecOps / AI |
| Placeholders JWT/crypto/DB permanecen en `.env.example` | En curso | Alta | Lider backend |
| Sin política de retención para logs de comandos y snapshots | Abierto | Media | Operaciones |
| | Parser ZTE degradaba zonas válidas a `SIN_ZONA` cuando había separadores atípicos | Mitigado (2026-06-20) | Media | AI |
| | Falta cobertura end-to-end del wizard de importación | Abierto | Media | QA |
| | | Tests locales para importación inicial requerían `psycopg` al inicializar el engine PostgreSQL global; se ajustó `backend/app/core/database.py` para respetar `DATABASE_URL` y permitir `sqlite+pysqlite:///:memory:` en tests. | Mitigado (2026-06-20) | Baja | Equipo Backend |