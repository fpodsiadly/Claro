CREATE TABLE laws (
    law_id TEXT PRIMARY KEY,
    law_name TEXT NOT NULL
);

CREATE TABLE articles (
    id SERIAL PRIMARY KEY,
    law_id TEXT REFERENCES laws(law_id),
    article_number TEXT NOT NULL
);

CREATE TABLE article_versions (
    id SERIAL PRIMARY KEY,
    article_id INTEGER REFERENCES articles(id),
    content TEXT,
    version_start_date DATE, -- od kiedy ta wersja obowiązuje
    version_end_date DATE,   -- NULL = nadal aktualna
    inserted_at TIMESTAMP DEFAULT NOW()
);

-- Create a GIN index for full-text search on the 'content' column in the 'article_versions' table
CREATE INDEX idx_article_versions_content_search ON article_versions
USING GIN (to_tsvector('simple', content));