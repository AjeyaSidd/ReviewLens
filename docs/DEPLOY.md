# App Review Intelligence — Production Deployment Guide

This guide walks you through setting up and launching the **App Review Intelligence** application in a live production environment. The stack is split into:
1. **Supabase** (Database, vector storage, and pgvector RPC searches)
2. **FastAPI Backend** (Dockerized container deployed on Render, Koyeb, or Railway)
3. **Next.js Frontend** (Static & Server-rendered React frontend deployed on Vercel)
4. **Daily Sync Automation** (Web Cron calling `/admin/sync-all` to keep reviews fresh)

---

## 1. Database Setup (Supabase)

Supabase provides a free-tier PostgreSQL database equipped with `pgvector` for vector searches.

### Step 1: Create a Supabase Project
1. Log in to [Supabase](https://supabase.com).
2. Click **New Project** and select your organization.
3. Choose a project name, secure database password, and region (e.g., *Asia South (Mumbai)* or nearest).
4. Wait for the database to finish provisioning (usually takes 1-2 minutes).

### Step 2: Run SQL Schema Migrations
You need to apply the schemas and custom database functions.
1. In the Supabase Dashboard, go to **SQL Editor** (the terminal icon on the left sidebar).
2. Click **New Query**.
3. Open [001_init.sql](file:///c:/Users/Ajeya%20Siddhartha/Projects/app-review-intelligence/supabase/migrations/001_init.sql) from your repository, copy its entire contents, paste it into the editor, and click **Run**. This creates:
   * `catalog_apps` table (tracking active store apps)
   * `reviews` table (with custom indexes and `vector` column)
   * `daily_rollups` table (precalculated trends cache)
4. Create another **New Query**.
5. Open [002_vector_search.sql](file:///c:/Users/Ajeya%20Siddhartha/Projects/app-review-intelligence/supabase/migrations/002_vector_search.sql) from your repository, copy its entire contents, paste it, and click **Run**. This establishes:
   * The custom database RPC function `match_reviews` executing fast cosine-similarity math natively over PostgreSQL.

---

## 2. Obtain Credentials & API Keys

Before deploying, collect the following environment variables:

1. **Supabase URL & Keys**:
   * Go to **Project Settings** (gear icon) > **API**.
   * Copy the **Project URL** (`SUPABASE_URL`).
   * Copy the **`service_role` secret** (`SUPABASE_SERVICE_ROLE_KEY`). 
     > [!IMPORTANT]
     > Use the `service_role` key instead of the `anon` key. The backend needs full read/write privileges to insert reviews, manage sentiment scores, and perform low-level vector searches. Keep this key strictly confidential.
2. **Gemini API Keys**:
   * Visit [Google AI Studio](https://aistudio.google.com/).
   * Click **Get API Key** and generate your standard API key for chat/LLM responses (`GEMINI_API_KEY`).
   * Generate/create another distinct API key for embedding calculations (`GEMINI_EMBEDDING_API_KEY`).
3. **Admin API Key**:
   * Generate a secure random string (e.g., using `openssl rand -hex 32` or a password manager) to act as your `X-Admin-Key` for administrative tasks.

---

## 3. Environment Variables Configuration

Create a production environment template. Copy `.env.example` to `.env` locally for live testing, or input these variables directly in your hosting platform dashboard:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
GEMINI_API_KEY=AIzaSy...
GEMINI_EMBEDDING_API_KEY=AIzaSy...
ADMIN_API_KEY=your-secure-admin-secret-key
MAX_ACTIVE_APPS=15
MAX_REVIEWS_PER_APP=2000
GEMINI_SENTIMENT_BATCH_SIZE=30
GEMINI_SENTIMENT_MODEL=gemini-2.0-flash
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
GEMINI_EMBEDDING_DIMENSIONS=1536
CORS_ORIGINS=http://localhost:3000,https://app-review-intelligence.vercel.app
LOG_DIR=backend/logs
LOG_LEVEL=INFO
```

---

## 4. Backend Container Deployment (Render / Koyeb)

The FastAPI server comes pre-configured with a custom [Dockerfile](file:///c:/Users/Ajeya%20Siddhartha/Projects/app-review-intelligence/backend/Dockerfile) optimized for secure, lightweight Python 3.13 operations.

### Option A: Render Deployment
1. Log in to [Render](https://render.com).
2. Click **New +** > **Web Service**.
3. Connect your GitHub repository.
4. Configure the service:
   * **Name**: `app-review-intelligence-backend`
   * **Root Directory**: `backend`
   * **Language**: `Docker`
   * **Branch**: `main`
   * **Plan**: `Free` (or preferred tier)
5. Under **Advanced**, add the environment variables defined in Section 3.
6. Click **Deploy Web Service**. Render will build the Docker container and expose a public URL (e.g., `https://app-review-intelligence-backend.onrender.com`).

### Option B: Koyeb Deployment
1. Log in to [Koyeb](https://www.koyeb.com).
2. Click **Create Service**.
3. Select **GitHub** and choose your repository.
4. Set configurations:
   * **Builder**: `Docker`
   * **Docker directory**: `backend`
   * **Port**: `8000`
5. Inject the environment variables under **Environment Variables**.
6. Deploy. Koyeb compiles the image and deploys it with automatic SSL.

---

## 5. Frontend Deployment (Vercel)

Vercel is the natural choice for deploying modern Next.js App Router projects.

### Step 1: Connect Repo to Vercel
1. Log in to [Vercel](https://vercel.com).
2. Click **Add New** > **Project**.
3. Import your GitHub repository.

### Step 2: Configure Build Settings
1. Set the **Root Directory** of the project to `frontend`.
2. Under **Framework Preset**, select **Next.js**.
3. Set the following environment variable:
   * Name: `NEXT_PUBLIC_API_URL`
   * Value: `https://your-backend-url.onrender.com` (Your live FastAPI public URL without a trailing slash)
4. Click **Deploy**. Vercel will build the frontend assets, bundle Recharts elements, compile Tailwind styles, and publish your live app details dashboard.

---

## 6. Daily Review Sync & Automation

To keep historical rating trends and user sentiments fresh, you must trigger a sync periodically. The backend exposes a `/admin/sync-all` route that scrapes, normalizes, sentiments, embeds, and rolls up reviews for all active apps.

### Setting up a Web Cron
Use a free scheduler service like [Cron-job.org](https://cron-job.org/) to trigger the sync automatically.
1. Create a free account on **Cron-job.org**.
2. Click **Create Cronjob**.
3. Set configurations:
   * **Title**: `App Review Daily Sync`
   * **Address**: `https://your-backend-url.onrender.com/admin/sync-all`
   * **Schedule**: Daily at 01:00 AM (or preferred interval).
   * **Request Method**: `POST`
4. Under **Request Headers**, add:
   * **Header Key**: `X-Admin-Key`
   * **Header Value**: `your-secure-admin-secret-key` (Must match the `ADMIN_API_KEY` defined in the backend settings)
5. Save the cron job. It will run in the background, automatically pulling store updates, trimming counts to 2,000, and regenerating vector embeddings.

---

## 7. Live End-to-End Verification

Verify the system operates successfully in production:

### Step 1: Add a Tracked App
Send a `POST` request to `/admin/apps` using curl or your Swagger docs (`https://your-backend-url.onrender.com/docs`) to track your first application:

```bash
curl -X POST "https://your-backend-url.onrender.com/admin/apps" \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: your-secure-admin-secret-key" \
  -d '{
    "display_name": "Google Drive",
    "country": "in",
    "play_package": "com.google.android.apps.docs",
    "ios_app_id": "310633997"
  }'
```

### Step 2: Run Initial Ingestion Sync
Trigger the synchronization worker for the newly registered app:

```bash
curl -X POST "https://your-backend-url.onrender.com/admin/sync-all" \
  -H "X-Admin-Key: your-secure-admin-secret-key"
```
*Observe backend logs to verify that the store scrapers normalise reviews, Gemini successfully processes sentiments in chunks of 30, embedding vectors are populated, and daily rollups are generated.*

### Step 3: Test Frontend Catalog & Hybrid RAG
1. Load your Vercel deployment in a browser.
2. Verify that **Google Drive** appears inside the catalog grid with its review count and store badges.
3. Click the card to open the **Dashboard**.
4. Check that **Recharts Rating & Sentiment Trend curves** plot data points correctly.
5. In the right **AI Copilot Chat Console**, type a semantic inquiry (e.g. *"What are the most common complaints regarding the search interface?"*).
6. Verify the AI synthesizes an answer and lists **Clickable Citation Cards** at the bottom. Clicking a citation should open the **Review Modal** showing full review text.
