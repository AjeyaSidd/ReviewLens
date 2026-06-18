# Getting Started Guide

Welcome to the **App Review Intelligence** project! This guide is designed to help you get the system up and running on your local machine.

---

## 1. Prerequisites

Ensure you have the following installed:
* **Python 3.11+**
* **Node.js 18+** & **npm**
* **Supabase** account (Free tier is perfect)
* **Google AI Studio** account (for Gemini API keys)

---

## 2. Environment Setup

1. Clone the repository to your local machine.
2. In the project root, copy the `.env.example` file to `.env`:
   ```bash
   cp .env.example .env
   ```
3. Open `.env` and fill in the required keys:
   * **`SUPABASE_URL`**: Your Supabase project URL (e.g., `https://your-project.supabase.co`).
   * **`SUPABASE_SERVICE_ROLE_KEY`**: Your Supabase `service_role` secret key. *(Note: Do NOT use the `anon` key, as the backend needs admin access to bypass RLS and write records).*
   * **`GEMINI_API_KEY`**: Your Gemini API key for chat/sentiment from Google AI Studio.
   * **`GEMINI_EMBEDDING_API_KEY`**: Your Gemini API key for generating vector embeddings.
   * **`ADMIN_API_KEY`**: A secure random string used to authenticate admin actions.
   * **`MAX_REVIEWS_PER_APP`**: Set to `500` for local development (production default is `2000`).

---

## 3. Database Setup (Supabase)

Initialize your Supabase schema and functions using the SQL files in `supabase/migrations/`:

1. Go to your **Supabase Dashboard** > **SQL Editor** > **New Query**.
2. Copy the contents of [`supabase/migrations/001_init.sql`](file:///c:/Users/Ajeya%20Siddhartha/Projects/app-review-intelligence/supabase/migrations/001_init.sql), paste it into the editor, and click **Run**. This sets up the `catalog_apps`, `reviews`, and `daily_rollups` tables with their respective indexes and generated columns.
3. Open another **New Query** window.
4. Copy the contents of [`supabase/migrations/002_vector_search.sql`](file:///c:/Users/Ajeya%20Siddhartha/Projects/app-review-intelligence/supabase/migrations/002_vector_search.sql), paste it, and click **Run**. This registers the custom pgvector similarity matching function `match_reviews`.

---

## 4. Local Development Installation

We use a `Makefile` to simplify dependencies management. Run the following command in your terminal from the project root:

```bash
make install
```
*(This will automatically run `pip install -r requirements.txt` inside the `backend` folder and `npm install` inside the `frontend` folder).*

---

## 5. Running the Application

To run the application locally, you will start the Backend API server and the Frontend Next.js app in separate terminal windows:

### A. Run Backend API
```bash
make run-api
```
* **API Address:** [http://localhost:8000](http://localhost:8000)
* **Swagger Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs) (Use the `X-Admin-Key` header with your `ADMIN_API_KEY` to authenticate admin routes).

### B. Run Frontend Dev Server
```bash
make run-web
```
* **Web App Address:** [http://localhost:3000](http://localhost:3000)

---

## 6. Project Ingestion & Verification

Once both servers are running:
1. Navigate to the Backend Swagger docs at [http://localhost:8000/docs](http://localhost:8000/docs).
2. Authorize using your `ADMIN_API_KEY`.
3. Use the `POST /admin/apps` endpoint to add a new tracking app (e.g. Google Drive: `"play_package": "com.google.android.apps.docs"`, `"ios_app_id": "310633997"`).
4. Run the initial data scraping pipeline by sending a `POST` request to `/admin/sync-all`.
5. Open your local web dashboard at [http://localhost:3000](http://localhost:3000) to see your app card, trend graphs, and talk to your AI Copilot!

---

## 7. Running Tests

Verify your local installation is fully functional by running:

```bash
make test
```

---

## 8. Performance & Load Testing

The project includes a load testing utility to measure the server's response times under concurrent request loads.

* **File Location:** [`backend/scripts/concurrency_test.py`](file:///c:/Users/Ajeya%20Siddhartha/Projects/app-review-intelligence/backend/scripts/concurrency_test.py)
* **Configuration:** Open the script and modify the configuration variables at the top:
  * `RENDER_URL`: Set to `"http://localhost:8000"` for local testing or your deployed service domain (e.g. `"https://app-review-intelligence.onrender.com"`).
  * `ENDPOINT`: The endpoint path to load test (defaults to `"/catalog"`).
  * `NUM_REQUESTS`: Number of concurrent requests to fire (defaults to `80`).

### Running the Load Test:

Ensure you are inside the backend virtual environment, then execute the script:
```bash
.venv\Scripts\python.exe backend/scripts/concurrency_test.py
```
*(The script will fire all requests concurrently using `httpx.AsyncClient` and print the individual execution times, followed by the maximum and average duration).*

