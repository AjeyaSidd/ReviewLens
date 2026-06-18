# Development History

This document chronicles the design plans, completed milestones, and historical implementations of **App Review Intelligence**.

---

## Completed Phases

### Phase 1: Foundation Setup
* Established database models in Supabase.
* Created FastAPI server skeleton and Docker deployment configuration.
* Implemented Google Play & App Store scrapers with automated pruning (capped at 500 reviews per app locally, 2000 in production).
* Integrated Gemini-powered bulk sentiment analysis (processing text reviews in chunks of 30).

### Phase 2: Vector Search & Semantic Storage
* Integrated Gemini `gemini-embedding-001` to generate 1536-dimensional vectors.
* Enabled `pgvector` extension and built the primary database RPC function `match_reviews` to execute native cosine-similarity math inside PostgreSQL.
* Added HNSW indexes for fast approximate nearest-neighbor query resolutions.

### Phase 3: Historical Rollups
* Built automated aggregation scripts targeting daily review statistics (`avg_rating`, `avg_sentiment`, star-distribution breakdowns).
* Created the `/apps/{id}/trends` endpoint to fetch rollup series for charting.

### Phase 4: Hybrid RAG Pipeline
* Integrated Gemini `gemini-2.0-flash` chat agent.
* Developed natural-language filter extraction (identifying relative date spans, rating ceilings, and version targets using regex rules).
* Built a parallel RAG pipeline fetching both daily trends metrics and raw vector search reviews to formulate responses complete with structured inline citations.

### Phase 5: Frontend Interface
* Built Next.js client interface featuring a main landing page and catalog grid.
* Added dynamic Recharts graphs to plot sentiment/ratings curves.
* Created interactive Suggestions chips, permitting PMs to populate the chat box with templates.
* Built a scrollable **Recent Reviews Panel** featuring a table of the latest 50 reviews with colored sentiment pills.
* Integrated detailed review modals popping up upon row clicks.

---

## Retrospective Design Decisions

### 1. Pruning Strategy
Initially, reviews were scraped without store boundaries, occasionally causing one platform to exhaust the entire limit. We implemented a balanced split-scraping strategy:
* If both stores are synced, each store is capped at 50% of the maximum reviews (e.g. 250 Play Store and 250 App Store reviews).
* If only one store is connected, it occupies up to the full limit.
* Pruning is run at the end of every sync, selecting the newest records and deleting older reviews to respect Supabase free-tier storage capacities (500MB).

### 2. Generated Numeric Version Casting
To support range checks (e.g., *"crashes since version 20.90"*), version numbers had to be cast to double precision. We added a PostgreSQL generated column:
```sql
ALTER TABLE reviews ADD COLUMN app_version_numeric double precision GENERATED ALWAYS AS (
  (substring(app_version from '^[vV]?([0-9]+(?:\.[0-9]+)?)'))::double precision
) STORED;
```
This parses the leading major/minor version (e.g., `v20.96.12` → `20.96`) dynamically upon inserts, bypassing manual float conversion during scrapers normalization.
