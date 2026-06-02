-- 002_vector_search.sql — Add match_reviews RPC function for pgvector similarity search

CREATE OR REPLACE FUNCTION match_reviews (
  query_embedding vector(1536),
  match_threshold float,
  match_count int,
  filter_app_id uuid
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
  ORDER BY reviews.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
