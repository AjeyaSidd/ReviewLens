# Phase 3 Implementation Plan — Aggregations & Trends

## Goal

Calculate daily aggregated review counts, average ratings, average sentiment scores, and star-count breakdowns (1 to 5 stars) per date for each catalog app. Save them into the `daily_rollups` table in Supabase and serve them via a new public `GET /apps/{app_id}/trends` endpoint to power historical aggregation charts.

---

## Technical Specifications

### 1. Database Rollup Schema (`daily_rollups`)
Pre-aggregating daily metrics ensures that PMs can explore historical charts instantly without needing to scan thousands of reviews. The fields mapped on `daily_rollups` are:
* `catalog_app_id` (UUID PK/FK)
* `date` (DATE PK)
* `review_count` (INT)
* `avg_rating` (FLOAT)
* `avg_sentiment` (FLOAT) — average of reviews having non-null sentiment scores
* `star_1` ... `star_5` (INT) — counts of reviews for each star score

### 2. Idempotency & Batching
Since reviews are capped at a maximum of **2,000 rows per app**, computing aggregations in Python in memory is extremely fast (under 10 milliseconds), robust, and highly testable offline. The service will fetch all active reviews for an app, aggregate them by date, and execute a bulk `upsert` on `daily_rollups`.

---

## Proposed Changes

### Backend — Aggregations Service

#### `backend/app/services/rollups.py`
Creates the aggregations service:
* Exposes `recompute_daily_rollups(app_id: str) -> int`:
  * Fetches all reviews for `app_id` (selecting `rating`, `review_date`, `sentiment_score`).
  * Groups them by `review_date`.
  * For each date, calculates the total review count, mathematical average rating, mathematical average sentiment (ignoring rating-only reviews with `NULL` sentiment), and star breakdowns.
  * Formats daily rollup rows and executes a bulk `.upsert()` into the `daily_rollups` table in Supabase (preventing duplicates using composite PK `(catalog_app_id, date)`).
  * Returns the number of unique dates processed.

### Backend — Sync pipeline Integration

#### `backend/app/services/sync_app.py`
* Imports `recompute_daily_rollups` from `app.services.rollups`.
* Updates **Step 8** to execute:
  ```python
  # Step 8: Rollup
  rollups_count = recompute_daily_rollups(app_id)
  ```

### Backend — API Routes

#### `backend/app/routers/public.py`
* Exposes new public `GET /apps/{app_id}/trends` endpoint:
  * Accepts optional query parameters `from_date: Optional[date] = None` and `to_date: Optional[date] = None`.
  * Queries `daily_rollups` table matching `app_id`.
  * Appends filters for date ranges if provided (`gte` / `lte`).
  * Orders rollups ascending by date (`order("date")`) and returns the historical dataset.

### Backend — Test Suite

#### `backend/tests/test_rollups.py`
Unit tests to mathematically verify the rollups and the API endpoint:
* `test_recompute_rollups_mathematical_accuracy`:
  * Mocks Supabase return values with a mixture of reviews across different dates, star ratings, and null/non-null sentiments.
  * Verifies rollup aggregates are computed accurately.
  * Asserts the bulk upsert receives correct daily values.
* `test_trends_api_filtering_and_ordering`:
  * Hitting `GET /apps/{app_id}/trends` via `TestClient`.
  * Verifies standard query params (`from_date` and `to_date`) filter the queries and the output is sorted chronologically.

---

## Verification Plan

### Automated Tests
Run the entire backend test suite including the new daily rollups unit tests:
```bash
.venv\Scripts\python.exe -m pytest backend/tests/ -v
```
All tests run offline using mocked databases. No network calls or real credentials are required.
