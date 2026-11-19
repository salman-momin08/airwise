-- Initialize required PostgreSQL extensions for AirWise AI
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "citext";
CREATE EXTENSION IF NOT EXISTS "postgis";
-- Note: pgvector is enabled when using a pgvector-enabled PostgreSQL image or managed RDS/Cloud SQL instance
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'vector') THEN
        CREATE EXTENSION IF NOT EXISTS "vector";
    END IF;
END
$$;
