# Phase 2 Implementation Plan — Embeddings & Vector Storage

## Goal

Convert review texts into 1536-dimensional vector embeddings using Google Gemini `gemini-embedding-001` and store them in the `reviews.embedding` column in Supabase for semantic search.

---

## Technical Specifications

### 1. Gemini Embedding Model
We use the official Google Gemini SDK (`google-genai`) and target the `gemini-embedding-001` model, producing 1536-dimensional floating-point vectors.

### 2. Idempotent Ingestion
To avoid unnecessary API costs, the ingestion pipeline only embeds reviews that:
1. Have actual text content (body is not empty).
2. Do not already have an embedding stored in the database (`embedding IS NULL`).
This ensures that subsequent refreshes or scrapings are extremely fast and only consume tokens for newly scraped reviews!

### 3. Safe Python Truncation Guardrail
To prevent any API errors or crashes from exceptionally long reviews (e.g. spam), a pre-emptive safety truncation guardrail is implemented:
* Slices the text to keep only the first **8,000 characters** (roughly 1,600–2,000 tokens) before sending to Gemini.
* Sliced format: `f"{title}. {body}".strip().strip(" .")[:8000]`.
* This guarantees that the API call never fails due to length limits (the `gemini-embedding-001` model supports up to 2048 tokens).

---

## Proposed Changes

### Backend — Embeddings Service

#### `backend/app/services/embeddings.py`
Creates the embeddings service:
* Imports `genai` from `google`.
* Exposes `generate_embeddings_batch(texts: list[str], max_retries: int = 3) -> list[list[float]]`:
  * Connects to the official `genai.Client` using the API key.
  * Splits texts into batches of up to 100 elements.
  * Calls `client.models.embed_content(model="gemini-embedding-001", contents=batch)`.
  * Extracts the float array `values` from the response.
  * Incorporates exponential backoff and retry logic for `429` (Rate Limit) and `5xx` (Server Error).
* Exposes `run_embeddings(app_id: str) -> int`:
  * Fetches reviews for `app_id` where `body` is not empty/null, and `embedding` is `NULL`.
  * Prepares text for each as `f"{title}. {body}".strip().strip(" .")`.
  * Generates embeddings in batches.
  * Updates each review's `embedding` vector in Supabase (pgvector accepts a standard list of floats).
  * Returns the count of reviews embedded.

### Backend — Sync Integration

#### `backend/app/services/sync_app.py`
* Imports `run_embeddings` from `app.services.embeddings`.
* Updates **Step 7** to execute:
  ```python
  # Step 7: Embedding
  run_embeddings(app_id)
  ```

### Backend — Test Suite

#### `backend/tests/test_embeddings.py`
Unit tests to verify vector shapes, cleanups, batching, and error handling:
* `test_generate_embeddings_batch_success`:
  * Mocks `genai.Client` and verifies that the correct embed model is requested, returning dummy 1536-dimensional vectors.
* `test_generate_embeddings_multiple_batches`:
  * Verifies that sending 150 texts splits them into two API batches (e.g. batch size of 100).
* `test_run_embeddings_e2e_success`:
  * Mocks Supabase responses to return reviews that need embeddings.
  * Asserts that embeddings are generated and updated correctly in the database.
* `test_run_embeddings_empty_or_no_text`:
  * Confirms that empty/rating-only reviews are completely skipped (no API calls).

---

## Verification Plan

### Automated Tests
Run the entire backend test suite including the new vector embedding unit tests:
```bash
.venv\Scripts\python.exe -m pytest backend/tests/ -v
```
All tests run offline using mocked API and database modules. No network calls or real Gemini credentials are required.
