import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "verso.db")


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()

    # Migration: if old user_preferences schema is missing display_name, drop and recreate
    try:
        cols = [row[1] for row in conn.execute("PRAGMA table_info(user_preferences)").fetchall()]
        if cols and "display_name" not in cols:
            conn.execute("DROP TABLE user_preferences")
            conn.commit()
    except Exception:
        pass

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id INTEGER PRIMARY KEY REFERENCES users(id),
            display_name TEXT NOT NULL DEFAULT '',
            learning_style TEXT DEFAULT 'reading' CHECK(learning_style IN ('visual','auditory','reading','mixed')),
            content_depth TEXT DEFAULT 'balanced' CHECK(content_depth IN ('brief','balanced','detailed')),
            use_case TEXT DEFAULT 'learning' CHECK(use_case IN ('exam','work','learning','research')),
            flashcard_difficulty TEXT DEFAULT 'medium' CHECK(flashcard_difficulty IN ('easy','medium','hard')),
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            filename TEXT NOT NULL,
            status TEXT DEFAULT 'processing',
            doc_type TEXT,
            total_pages INTEGER DEFAULT 0,
            progress INTEGER DEFAULT 0,
            stage TEXT DEFAULT 'uploading',
            qa_ready INTEGER DEFAULT 0,
            error_message TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS reels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            upload_id INTEGER REFERENCES uploads(id),
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
            narration TEXT,
            category TEXT,
            keywords TEXT,
            page_ref INTEGER,
            audio_path TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS flashcards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            upload_id INTEGER REFERENCES uploads(id),
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS bookmarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            reel_id INTEGER REFERENCES reels(id),
            flashcard_id INTEGER REFERENCES flashcards(id),
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS progress (
            user_id INTEGER REFERENCES users(id),
            upload_id INTEGER REFERENCES uploads(id),
            viewed_reel_ids TEXT DEFAULT '[]',
            last_viewed_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (user_id, upload_id)
        );

        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            upload_id INTEGER REFERENCES uploads(id),
            user_message TEXT NOT NULL,
            ai_response TEXT NOT NULL,
            sources TEXT DEFAULT '[]',
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)

    # Migration: add progress/stage/error_message columns to uploads if missing
    upload_cols = [row[1] for row in conn.execute("PRAGMA table_info(uploads)").fetchall()]
    if "progress" not in upload_cols:
        conn.execute("ALTER TABLE uploads ADD COLUMN progress INTEGER DEFAULT 0")
    if "stage" not in upload_cols:
        conn.execute("ALTER TABLE uploads ADD COLUMN stage TEXT DEFAULT 'uploading'")
    if "error_message" not in upload_cols:
        conn.execute("ALTER TABLE uploads ADD COLUMN error_message TEXT")

    # Migration: add narration column to reels if missing
    reel_cols = [row[1] for row in conn.execute("PRAGMA table_info(reels)").fetchall()]
    if "narration" not in reel_cols:
        conn.execute("ALTER TABLE reels ADD COLUMN narration TEXT")

    # Seed a default user (placeholder until auth is implemented)
    conn.execute(
        "INSERT OR IGNORE INTO users (id, name, password_hash) VALUES (1, 'default', 'placeholder')"
    )

    # Backfill: assign orphan uploads to the default seed user
    conn.execute("UPDATE uploads SET user_id = 1 WHERE user_id IS NULL")

    conn.commit()
    conn.close()
