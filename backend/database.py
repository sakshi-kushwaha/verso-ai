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
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id INTEGER PRIMARY KEY REFERENCES users(id),
            learning_style TEXT DEFAULT 'reading'
        );

        CREATE TABLE IF NOT EXISTS uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            filename TEXT NOT NULL,
            status TEXT DEFAULT 'processing',
            doc_type TEXT,
            total_pages INTEGER DEFAULT 0,
            qa_ready INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS reels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            upload_id INTEGER REFERENCES uploads(id),
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
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
    conn.commit()
    conn.close()
