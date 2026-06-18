# AI Assistant Rules

This document outlines the coding standards, testing rules, and execution standards for AI coding assistants working on **App Review Intelligence**.

---

## 1. Mandatory Coding Guidelines

### 1.1 Documentation and Code Integrity
* Keep code well-documented with docstrings and comments. Do not delete pre-existing docstrings or comments.
* Always write code files to the appropriate workspace location (`backend/`, `frontend/`, `supabase/`, etc.). Do not save files to system temporary paths unless explicitly requested.

### 1.2 Test-Driven Development
* Every core feature or endpoint must be covered by automated tests.
* Backend tests are located in `backend/tests/` using **pytest**.
* Run `make test` to ensure the test suite is green before declaring a task complete.

### 1.3 Logging
* Log all significant execution paths, jobs, and errors to both stdout and a log file.
* Backend logs are stored in `backend/logs/` (ensure this directory is in your `.gitignore`).

### 1.4 Environment Secrets
* **Never** commit secrets or `.env` files to GitHub.
* Ensure all secrets are loaded using Pydantic Settings/dotenv from `.env` in the project root.
* Maintain `.env.example` with blank placeholders.

---

## 2. Technical Safeguards

* **App Registry Capping:** Enforce `MAX_ACTIVE_APPS=15` limits during app additions.
* **Review Pruning:** Always prune reviews per catalog app to `MAX_REVIEWS_PER_APP` (default is 2000 in production, 500 in local testing) after each store sync, keeping only the newest records.
* **Sentiment Analysis:** Only perform sentiment analysis on reviews that contain text. Skips rating-only reviews, keeping their sentiment as `NULL`.

---

## 3. Standard Commands (Makefile)

We utilize the root `Makefile` to orchestrate actions:

| Command | Action |
|---------|--------|
| `make install` | Installs Python backend packages and frontend Node modules |
| `make run-api` | Starts the Uvicorn FastAPI backend server (Port 8000) |
| `make run-web` | Starts the Next.js frontend dev server (Port 3000) |
| `make test` | Executes backend pytests and frontend tests |
| `make lint` | Run code quality checks (Ruff on backend, ESLint on frontend) |
| `make clean` | Purges node caches, pycache directories, and temp files |
