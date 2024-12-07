CREATE TABLE IF NOT EXISTS nd2_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    user TEXT NOT NULL,
    size_bytes BIGINT NOT NULL,
    creation_date DATETIME,
    last_access DATETIME,
    last_modified DATETIME,
    analyzed_at DATETIME DEFAULT CURRENT_TIMESTAMP
)