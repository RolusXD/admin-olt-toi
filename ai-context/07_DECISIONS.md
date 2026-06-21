# Decision Log

Each entry resume las decisiones arquitectónicas que afectan la continuidad del proyecto multi-IA.

## 2026-06-20 — Autenticación basada en variables de entorno
- **Motivo:** Eliminar credenciales por defecto y forzar configuración segura en cada entorno.
- **Impacto:** Login depende de `ADMIN_USERNAME` + `ADMIN_PASSWORD_HASH`. Se documentó proceso de creación del administrador inicial y se removieron datos demo.

## 2026-06-20 — Snapshot completo para importación inicial
- **Motivo:** Garantizar que la importación ZTE se ejecute sobre un `show running-config` íntegro con checksum válido.
- **Impacto:** El flujo de importación almacena snapshots capturados, verifica prompt final estable y reutiliza el mismo archivo en preview/confirm.

## 2026-06-20 — Escaneo de secretos con Gitleaks en CI
- **Motivo:** Evitar filtraciones accidentales antes del rollout a producción y coordinar trabajo multi-IA.
- **Impacto:** Workflow `security-scans` bloquea merges con hallazgos y README incluye pasos locales; TODO registra integración pendiente en pre-commit.