# Phase 4 Implementation Plan — Chat API (Hybrid RAG)

## Goal

Implement the core conversational API endpoint `POST /apps/{app_id}/chat` that allows Product Managers to ask natural-language questions about review trends or user experiences. The endpoint dynamically uses **Intent Detection** to choose between SQL trend analysis (structured rollups) and vector similarity search (experiential review text) to generate accurate summaries citing specific reviews.

---

## Technical Specifications

### 1. Intent Detection Design
Inside the chat endpoint, we use a fast intent classifier via `gemini-2.0-flash`. The model determines whether the question is:
* **`METRIC_TRENDS`**: Questions asking for numerical aggregates, counts, ratings over time (e.g., *"What is my average rating over the last week?"*).
* **`SEMANTIC_FEEDBACK`**: Questions asking about user experiences, complaints, features, crashes (e.g., *"Why are users complaining about logins?"*).

If `METRIC_TRENDS` is selected, the backend queries the daily rollups table. If `SEMANTIC_FEEDBACK` is selected, the backend performs a cosine-similarity search using pgvector on `reviews.embedding`.

### 2. Context Aggregation & RAG Prompt
* **Semantic Context**: Retrieve the top 5 most similar reviews based on cosine distance.
* **Prompt**: Feed the retrieved reviews or daily rollups to `gemini-2.0-flash` with a system instruction to synthesize a structured JSON response containing:
  * `answer`: A natural-language response.
  * `citations`: A list of referenced review IDs and text snippets.
  * `metrics`: Contextual aggregates (if applicable).

---

## Proposed Changes

### Backend — Chat Service

#### [NEW] [backend/app/services/chat.py](file:///c:/Users/Ajeya%20Siddhartha/Projects/app-review-intelligence/backend/app/services/chat.py)
Creates the chat & RAG processing service:
* Exposes `detect_query_intent(query: str) -> str`:
  * Asks Gemini to classify the user's message as `METRIC_TRENDS` or `SEMANTIC_FEEDBACK`.
* Exposes `retrieve_semantic_context(app_id: str, query_vector: list[float], limit: int = 5) -> list[dict]`:
  * Performs pgvector cosine similarity search on the `reviews` table matching `catalog_app_id` to retrieve matching review title, body, and IDs.
* Exposes `run_hybrid_rag(app_id: str, query: str) -> dict`:
  * Resolves intent.
  * Generates embedding vector for the query if intent is semantic.
  * Retrieves relevant context (SQL rollups or reviews).
  * Prompts `gemini-2.0-flash` to synthesize the structured answer with exact citations.
  * Returns the formatted JSON response matching the Chat response shape.

### Backend — API Routes

#### [MODIFY] [backend/app/routers/public.py](file:///c:/Users/Ajeya%20Siddhartha/Projects/app-review-intelligence/backend/app/routers/public.py)
* Exposes new public `POST /apps/{app_id}/chat` endpoint:
  * Verifies the app exists and is active.
  * Accepts request body `{ "message": "..." }`.
  * Invokes the hybrid RAG service and returns the structured answer.

### Backend — Test Suite

#### [NEW] [backend/tests/test_chat.py](file:///c:/Users/Ajeya%20Siddhartha/Projects/app-review-intelligence/backend/tests/test_chat.py)
* Tests intent classification mocks.
* Tests pgvector similarity queries and SQL rollups retrievals.
* Tests end-to-end RAG output structure, ensuring `answer` and `citations` are returned cleanly.

---

## Verification Plan

### Automated Tests
Run the entire backend test suite including the new chat unit tests:
```bash
.venv\Scripts\python.exe -m pytest backend/tests/ -v
```
All tests run offline using mocked databases. No network calls or real credentials are required.
