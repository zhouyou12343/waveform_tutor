# Maintenance guide

- Read the real backend/frontend code and trace fixtures before describing behavior. Separate recorded evidence, user configuration, and inference; never invent test outcomes, benchmarks, provider compatibility, or remote CI status.
- Keep changes scoped. Preserve integer-tick semantics, X/Z values, same-timestamp record order, explicit truncation, and parser/resource bounds. RTL references are name-only, not semantic bindings.
- Never execute uploaded/user-provided RTL. The example generator is only for the three fixed, trusted repository examples; a temporary directory is not a hostile-code sandbox.
- Never commit or expose API keys, environment secrets, private traces, or sensitive source in code, logs, chat, fixtures, or screenshots. AI keys may be submitted in the local settings form, but must never be returned by configuration endpoints or persisted in browser storage. Backend-only storage is the Git-ignored .waveform-tutor/ai-config.json or process environment; .env is not automatically loaded.
- Preserve explicit AI consent and separate RTL consent. Structural validation and reference allowlists do not make free-text explanations factual or formally verified.
- Run relevant checks from the repository root: `.venv/bin/python -m pytest -q`, `.venv/bin/ruff check backend scripts`, `.venv/bin/ruff format --check backend scripts`, and `npm --prefix frontend run build`, `typecheck`, `test` (each as a separate npm run command).
- For `npm --prefix frontend run test:e2e`, install Chromium with `frontend/node_modules/.bin/playwright install chromium` and create the root `.venv`. Playwright manages both FastAPI and Vite; keep AI environment variables unset for offline integration assertions. Report failures and skipped checks honestly.
- When changing examples, run `.venv/bin/python scripts/generate_examples.py` with external Icarus installed; review assertions, lesson files, traces, and documented checkpoints together.
- Keep README.md as the English entry point, README.zh-CN.md aligned, and `docs/api.md` / `docs/limitations.md` accurate. Do not present roadmap items as implemented features.
