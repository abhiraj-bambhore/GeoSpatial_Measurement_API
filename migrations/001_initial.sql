-- Geospatial Measurement API: Supabase Schema
-- Run this SQL in Supabase SQL Editor to create the required tables.

-- Files table: stores metadata about uploaded geospatial files
CREATE TABLE IF NOT EXISTS files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    feature_count INTEGER DEFAULT 0,
    crs TEXT,
    status TEXT NOT NULL DEFAULT 'PENDING',
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Measurements table: stores per-feature measurement results
CREATE TABLE IF NOT EXISTS measurements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    feature_index INTEGER NOT NULL,
    geometry_type TEXT NOT NULL,
    geometry_wkt TEXT,
    properties JSONB DEFAULT '{}',
    measurement_type TEXT,
    measurement_value DOUBLE PRECISION,
    measurement_unit TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_measurements_file_id ON measurements(file_id);

-- Row Level Security: permissive policies for API access
ALTER TABLE files ENABLE ROW LEVEL SECURITY;
ALTER TABLE measurements ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow full access on files" ON files
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Allow full access on measurements" ON measurements
    FOR ALL USING (true) WITH CHECK (true);
