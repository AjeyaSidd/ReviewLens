# Implementation Plan — Recent Reviews Table & Chat Suggestions

This plan details the addition of a **Recent Reviews Table** and **Conversational Suggestions** to the Product Manager's application dashboard (`/apps/[id]`). It also describes the handling of multi-part queries in the backend RAG pipeline.

---

## Technical Specifications & UI Review

### 1. Design & Layout Adjustments (Splits Layout)
Currently, `/apps/[id]/page.tsx` uses a 2-column split (Left Panel: Recharts Trend curves [60% width]; Right Panel: AI Chat Console [40% width]).
We will reorganize the page into a clean, modern layout:
* **Top Banner**: App Profile & Sync Stats (Already existing).
* **Upper Section (60% width Left, 40% width Right)**:
  * **Left (Trends Panel)**: Date Filters + Recharts Rating & Sentiment Trend graphs.
  * **Right (Recent Reviews Panel - NEW)**: A scrollable glassmorphic panel containing a beautiful table of the latest 50 reviews.
* **Lower Section (100% width)**:
  * **AI Chat Console**: Spanned across the bottom 60% of the screen.
  * **Suggestions (NEW)**: Clickable suggestion chips right above the chat input to get started.

---

## Answers to User Questions & Design Updates

### Question 1: How many reviews can comfortably be shown in the table, and what columns are nice to have?
* **Volume**:
  * We will fetch and render the **latest 50 reviews** by default.
  * Rendering 2,000 reviews at once would severely degrade browser rendering speeds. Slicing at 50 is perfect for immediate scanability and keeps page load sub-second. We will also add a subtle scrollbar with standard CSS `overflow-y-auto` inside a fixed-height card panel (`h-[480px]`).
* **Nice-to-Have Columns**:
  1. **Platform**: SVG store badges representing Google Play Store (emerald pill) and Apple App Store (sky pill).
  2. **Rating**: A horizontal row of 1 to 5 glowing star icons (yellow/gold), allowing PMs to visually scan ratings instantly.
  3. **Sentiment**: A color-coded pill tag:
     * `POSITIVE` (emerald text on emerald background with low opacity)
     * `NEUTRAL` (grey text on grey background)
     * `NEGATIVE` (rose/red text on red background)
  4. **Date**: Cleanly formatted string (e.g. `28 May 2026`).
  5. **Review**: Truncated review text (first 100 characters) with an ellipsis (`...`). Clicking on the row will trigger the existing detailed `ReviewModal` overlay, showing full text, rating, and metadata.

### Question 2: Suggestion Pills Interaction (Non-Autosubmit)
* **Corrected Interaction**:
  * **Clicking any suggestion pill will only populate the prompt in the message bar but NOT submit it**.
  * This allows the PM to read the prompt, customize it, append specific context, or edit it before clicking the "Send" button. Only the user should trigger the final submission.

### Question 3: Handling Multi-Part Queries (SQL Table + Vector RAG)
If a user submits a query containing two distinct parts (e.g., *"What was our average rating last week and what specific bugs did users complain about?"*), the backend RAG pipeline will resolve it elegantly:
* **Intent Classification Upgrade**:
  * We will expand `detect_query_intent(query: str)` to recognize a third intent: **`HYBRID`**.
  * **`METRIC_TRENDS`**: Asking exclusively about numerical rollups.
  * **`SEMANTIC_FEEDBACK`**: Asking exclusively about feedback text/experiences.
  * **`HYBRID`**: Asking for *both* aggregate metrics and qualitative complaints/experiences.
* **Dual Context Retrieval**:
  * If a `HYBRID` intent is detected, the backend will retrieve **both** types of context:
    1. The last 30 days of pre-aggregated logs from `daily_rollups`.
    2. The top 5 relevant reviews from the pgvector `match_reviews` RPC.
* **Unified Synthesis**:
  * We will prompt Gemini using a unified `RAG_SYSTEM_PROMPT_HYBRID` which instructs the model to synthesize a response that populates **both** aspects:
    * `answer`: A natural-language response answering both the trends and user stories.
    * `metrics`: Mathematical calculations (average ratings, volume) from the daily rollups.
    * `citations`: Reference review arrays (IDs, snippets) from the pgvector similarity results.

---

## Proposed Changes

### 1. Backend Layer (FastAPI)

#### [NEW ROUTE] [backend/app/routers/public.py](file:///c:/Users/Ajeya%20Siddhartha/Projects/app-review-intelligence/backend/app/routers/public.py)
* Add a public route `GET /apps/{app_id}/reviews` to retrieve recent reviews:
  * Accepts optional query parameters `limit: int = 50` and `offset: int = 0`.
  * Selects `id, platform, rating, title, body, sentiment, review_date` from the `reviews` table, sorted by `review_date DESC` and restricted by limits.

#### [MODIFY] [backend/app/services/chat.py](file:///c:/Users/Ajeya%20Siddhartha/Projects/app-review-intelligence/backend/app/services/chat.py)
* Add `HYBRID` intent classification to `INTENT_SYSTEM_PROMPT`.
* Define `RAG_SYSTEM_PROMPT_HYBRID` to instruct Gemini to process both daily rollups and pgvector reviews, producing both `metrics` and `citations`.
* Modify `run_hybrid_rag` to detect `HYBRID` intent, fetch both context sets, and apply the hybrid system instruction.

### 2. Frontend Layer (Next.js)

#### [MODIFY] [frontend/app/apps/[id]/page.tsx](file:///c:/Users/Ajeya%20Siddhartha/Projects/app-review-intelligence/frontend/app/apps/%5Bid%5D/page.tsx)
* Re-organize page layout into a cohesive 2-tier dashboard:
  * **Top**: App Details Banner.
  * **Mid Section (60/40 Split)**:
    * Left (60%): Date filters and Trend curves.
    * Right (40%): The new scrollable **Recent Reviews Table** panel.
  * **Bottom Section (100% width)**:
    * Centered **AI Chat Console** with expanded width.
* Fetch recent reviews via `GET /apps/{id}/reviews?limit=50` inside `fetchAppAndTrends`.

#### [MODIFY] [frontend/components/ChatPanel.tsx](file:///c:/Users/Ajeya%20Siddhartha/Projects/app-review-intelligence/frontend/components/ChatPanel.tsx)
* Add interactive suggestions pills directly above the input prompt form.
* Clicking a pill populates the prompt in the text input state without submitting.

### 3. Tests Layer

#### [MODIFY] [backend/tests/test_chat.py](file:///c:/Users/Ajeya%20Siddhartha/Projects/app-review-intelligence/backend/tests/test_chat.py)
* Add unit tests to verify:
  * `HYBRID` intent classification.
  * Retrieval of both rollup records and pgvector reviews under `HYBRID` intent.
  * RAG output formatting containing both `metrics` and `citations`.

#### [NEW TESTS] [backend/tests/test_reviews.py](file:///c:/Users/Ajeya%20Siddhartha/Projects/app-review-intelligence/backend/tests/test_reviews.py)
* Add unit tests to verify that `GET /apps/{app_id}/reviews` returns 200, handles limits, and sorts descending.

---

## Verification Plan

### Automated Tests
Run unit tests to ensure all routers and service components operate cleanly under mocks:
```bash
.venv\Scripts\python.exe -m pytest backend/tests/ -v
```

### Manual Verification
1. Open the local dashboard `/apps/[id]`.
2. Verify the **Recent Reviews Table** loads perfectly with dynamic ratings, sentiment tags, and scrollable panels.
3. Click a row and confirm that the detailed **ReviewModal** opens displaying full metadata.
4. Click a **Chat Prompt Suggestion pill** and verify that it injects the prompt in the text bar without submitting.
5. Ask a hybrid question (e.g. *"What is our average rating this week, and what features do iOS users want?"*) and verify that the chat returns both **metrics summaries** and **citations list cards**.
