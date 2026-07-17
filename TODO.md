# TODO

## Backlog Execution (Post v0.2.0)

- [x] Implement CI pipeline (GitHub Actions) for pytest + preflight
- [x] Harden `.gitignore` for runtime artifacts (`logs/`, `*.log`, `__pycache__/`, etc.)
- [x] Add Streamlit dashboard smoke test automation
- [x] Update `RUNBOOK.md` with incident-response playbook (severity, triage, kill-switch, rollback)
- [x] Prepare v0.2.1 draft notes in `CHANGELOG.md` and `RELEASE_NOTES.md`
- [x] Run validation commands (`pytest -q`, `preflight_check.ps1`) and record status

## Validation Record (Post v0.2.0 Backlog)

- [x] `powershell -ExecutionPolicy Bypass -File .\scripts\preflight_check.ps1`
  - Result: `PREFLIGHT_STATUS=OK`
  - Notes: `BINANCE_API_KEY` / `BINANCE_API_SECRET` WARN (paper/test setup için kabul edilebilir)
- [x] `.\.venv\Scripts\python -m pytest -q`
  - Result: PASS (`............. [100%]`)
