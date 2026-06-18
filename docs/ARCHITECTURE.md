# System Architecture

This document serves as the canonical system architecture guide for **App Review Intelligence**.

---

## 1. Product Overview

App Review Intelligence is a web based review analysis platform designed for product teams. 
It aggregates reviews from the Google Play Store and Apple App Store, performs sentiment analysis and vector embedding calculation 
using Google Gemini, and allows the PM to query trends or ask natural-language questions with citations.

---

## 2. Tech Stack

| Layer | Technology |
|--------|------------|
| **Frontend** | Next.js (App Router), React, Tailwind CSS, Recharts |
| **Backend** | Python 3.11+, FastAPI, Uvicorn |
| **Database** | PostgreSQL + **pgvector** (Supabase) |
| **Embeddings** | Google Gemini `gemini-embedding-001` (1536 dimensions) |
| **Chat LLM** | Google Gemini `gemini-2.0-flash` (via Google GenAI SDK) |
| **Scrapers** | `google-play-scraper`, `app-store-scraper` |

---

## 3. Data Model (Supabase Schema)

### 3.1 `catalog_apps`
Stores the registry of mobile apps tracked by the application (maximum 15 active apps).
* `id` (UUID, PK)
* `display_name` (TEXT)
* `country` (CHAR(2), default `'in'`)
* `play_package` (TEXT, Nullable)
* `ios_app_id` (TEXT, Nullable)
* `is_active` (BOOLEAN, default `true`)
* `scrape_status` (TEXT, default `'pending'`)
* `last_synced_at` (TIMESTAMPTZ)
* `review_count` (INT, default `0`)
* `app_icon_url` (TEXT, Nullable)
* `created_at` (TIMESTAMPTZ, default `now()`)

### 3.2 `reviews`
Contains normalized app reviews scraped from the App Store and Play Store.
* `id` (UUID, PK)
* `catalog_app_id` (UUID, FK referencing `catalog_apps.id` ON DELETE CASCADE)
* `platform` (TEXT, `play_store` or `app_store`)
* `platform_review_id` (TEXT)
* `rating` (SMALLINT, 1-5)
* `title` (TEXT, default `''`)
* `body` (TEXT, default `''`)
* `review_date` (DATE)
* `language` (TEXT)
* `app_version` (TEXT)
* `sentiment_label` (TEXT, `positive`, `neutral`, `negative`)
* `sentiment_score` (FLOAT, range -1.0 to 1.0)
* `embedding` (vector(1536))
* `scraped_at` (TIMESTAMPTZ, default `now()`)
* `app_version_numeric` (DOUBLE PRECISION, generated column casting `app_version` to float for version-range queries)

**Unique Constraint:** `(catalog_app_id, platform, platform_review_id)`

### 3.3 `daily_rollups`
Pre-aggregated daily statistics per catalog app used to power rapid trend chart drawing.
* `catalog_app_id` (UUID, FK referencing `catalog_apps.id` ON DELETE CASCADE)
* `date` (DATE)
* `review_count` (INT, default `0`)
* `avg_rating` (FLOAT)
* `avg_sentiment` (FLOAT)
* `star_1` through `star_5` (INT, default `0`)

**Primary Key:** `(catalog_app_id, date)`

---

## 4. Vector Search & Metadata Filtering

Similarity search is handled natively in PostgreSQL via the `match_reviews` RPC function. It calculates the 
cosine similarity (`1 - (embedding <=> query_embedding)`) and supports granular filtering over app version, rating, and review date:

```sql
CREATE OR REPLACE FUNCTION match_reviews (
  query_embedding vector(1536),
  match_threshold float,
  match_count int,
  filter_app_id uuid,
  filter_from_date date DEFAULT NULL::date,
  filter_to_date date DEFAULT NULL::date,
  filter_min_version double precision DEFAULT NULL::double precision,
  filter_max_version double precision DEFAULT NULL::double precision,
  filter_min_rating integer DEFAULT NULL::integer,
  filter_max_rating integer DEFAULT NULL::integer
)
RETURNS TABLE (
  id uuid,
  catalog_app_id uuid,
  platform text,
  platform_review_id text,
  rating smallint,
  title text,
  body text,
  review_date date,
  sentiment_label text,
  sentiment_score float,
  similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    reviews.id,
    reviews.catalog_app_id,
    reviews.platform,
    reviews.platform_review_id,
    reviews.rating,
    reviews.title,
    reviews.body,
    reviews.review_date,
    reviews.sentiment_label,
    reviews.sentiment_score,
    1 - (reviews.embedding <=> query_embedding) AS similarity
  FROM reviews
  WHERE reviews.catalog_app_id = filter_app_id
    AND reviews.embedding IS NOT NULL
    AND 1 - (reviews.embedding <=> query_embedding) > match_threshold
    AND (filter_from_date IS NULL OR reviews.review_date >= filter_from_date)
    AND (filter_to_date IS NULL OR reviews.review_date <= filter_to_date)
    AND (filter_min_version IS NULL OR reviews.app_version_numeric >= filter_min_version)
    AND (filter_max_version IS NULL OR reviews.app_version_numeric <= filter_max_version)
    AND (filter_min_rating IS NULL OR reviews.rating >= filter_min_rating)
    AND (filter_max_rating IS NULL OR reviews.rating <= filter_max_rating)
  ORDER BY reviews.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
```

---

## 5. RAG Pipeline (Hybrid Retrieval)

The RAG engine supports quantitative, diagnostic, and exploratory PM inquiries:

1. **Metadata Filter Extraction:** Uses fast, zero-latency regex matching on the input query to extract filters for dates, ratings, and app versions.
2. **Concurrent Context Retrieval:** Executes parallel asynchronous database fetches to gather complete context:
   * **SQL Path:** Fetches aggregated daily metrics from `daily_rollups` (last 30 days).
   * **Semantic Path:** Invokes the `match_reviews` RPC function using the query's vector embedding combined with any extracted filters.
3. **Response Synthesis (LLM-driven Integration):** Passes both the daily rollup data and the semantic reviews directly to Gemini (`gemini-2.0-flash`). The model acts as the dynamic router/synthesizer, using its system instructions to return a structured JSON response containing:
   * `answer`: A natural-language response styled in Markdown.
   * `metrics`: Dynamic metrics matching the user's inquiry (empty if qualitative).
   * `citations`: Array of reference review cards with snippets.
