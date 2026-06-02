# Bootstrap files (copy to project root)

Plan mode could not write non-markdown files. **Switch to Agent mode** and ask to "apply PROJECT_BOOTSTRAP" to create these automatically, or copy manually.

---

## `.gitignore` (project root)

```gitignore
# Secrets
.env
.env.local
.env.*.local
backend/.env
frontend/.env.local

# Python
__pycache__/
*.py[cod]
.venv/
venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/
*.egg-info/

# Node / Next.js
node_modules/
.next/
out/
dist/

# Logs
backend/logs/
*.log

# OS / IDE
.DS_Store
Thumbs.db
.idea/
.vscode/
```

---

## `.env.example` (project root)

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=
GEMINI_API_KEY=
ADMIN_API_KEY=change-me-to-a-long-random-string
MAX_ACTIVE_APPS=15
MAX_REVIEWS_PER_APP=2000
GEMINI_SENTIMENT_BATCH_SIZE=30
GEMINI_SENTIMENT_MODEL=gemini-2.0-flash
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
GEMINI_EMBEDDING_DIMENSIONS=1536
CORS_ORIGINS=http://localhost:3000,https://your-app.vercel.app
LOG_DIR=backend/logs
LOG_LEVEL=INFO
```

Copy to `.env` and fill in values. **Never commit `.env`.**

---

## `Makefile` (project root)

See Agent mode apply or full content in repo after Phase 1 bootstrap command.

Targets: `help`, `install`, `install-backend`, `install-frontend`, `build`, `test`, `test-backend`, `test-frontend`, `lint`, `run-api`, `run-web`, `docker-build`, `clean`.

---

## `.cursor/rules/app-review-intelligence.mdc`

Cursor rule with `alwaysApply: true` pointing to `docs/ARCHITECTURE.md` and `docs/AI_ASSISTANT_RULES.md`. Apply via Agent mode.
