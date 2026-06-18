-- 002_vector_search.sql — Add match_reviews RPC function for pgvector similarity search with metadata filtering

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
