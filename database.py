import aiosqlite
import os
from datetime import datetime
from config import DB_PATH


async def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return await aiosqlite.connect(DB_PATH)


async def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS music_requests (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id   TEXT    NOT NULL,
                youtube_url  TEXT    NOT NULL,
                title        TEXT    DEFAULT '정보 없음',
                duration     INTEGER DEFAULT 0,
                thumbnail    TEXT    DEFAULT '',
                status       TEXT    DEFAULT 'pending',
                play_count   INTEGER DEFAULT 0,
                rating_sum   INTEGER DEFAULT 0,
                rating_count INTEGER DEFAULT 0,
                created_at   TEXT    NOT NULL,
                approved_at  TEXT
            )
        """)

        columns_to_add = [
            ("play_count", "INTEGER DEFAULT 0"),
            ("rating_sum", "INTEGER DEFAULT 0"),
            ("rating_count", "INTEGER DEFAULT 0")
        ]
        
        for col_name, col_type in columns_to_add:
            try:
                await db.execute(f"ALTER TABLE music_requests ADD COLUMN {col_name} {col_type}")
            except aiosqlite.OperationalError:
                pass

        await db.execute("""
            CREATE TABLE IF NOT EXISTS broadcast_schedule (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT    NOT NULL,
                start_time  TEXT    NOT NULL,
                end_time    TEXT    NOT NULL,
                created_at  TEXT    NOT NULL,
                UNIQUE(date)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS broadcast_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT    NOT NULL,
                start_time  TEXT,
                end_time    TEXT,
                status      TEXT    DEFAULT 'scheduled',
                playlist    TEXT    DEFAULT '[]',
                created_at  TEXT    NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS blocked_students (
                student_id  TEXT PRIMARY KEY,
                reason      TEXT,
                created_at  TEXT NOT NULL
            )
        """)

        await db.commit()
    print("[DB] 데이터베이스 초기화 완료")


async def create_music_request(student_id: str, youtube_url: str,
                                title: str, duration: int, thumbnail: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO music_requests
               (student_id, youtube_url, title, duration, thumbnail, status, created_at)
               VALUES (?, ?, ?, ?, ?, 'pending', ?)""",
            (student_id, youtube_url, title, duration, thumbnail,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        await db.commit()
        return cursor.lastrowid


async def get_all_requests(status_filter: str = None) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if status_filter:
            cursor = await db.execute(
                "SELECT * FROM music_requests WHERE status = ? ORDER BY created_at DESC",
                (status_filter,)
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM music_requests ORDER BY created_at DESC"
            )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_request_by_id(request_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM music_requests WHERE id = ?", (request_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_approved_requests() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM music_requests
               WHERE status = 'approved'
               ORDER BY approved_at ASC"""
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def update_request_status(request_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        approved_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if status == "approved" else None
        await db.execute(
            "UPDATE music_requests SET status = ?, approved_at = ? WHERE id = ?",
            (status, approved_at, request_id)
        )
        await db.commit()


async def delete_request(request_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM music_requests WHERE id = ?", (request_id,))
        await db.commit()


async def upsert_schedule(date: str, start_time: str, end_time: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO broadcast_schedule (date, start_time, end_time, created_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(date) DO UPDATE SET
                   start_time = excluded.start_time,
                   end_time   = excluded.end_time""",
            (date, start_time, end_time, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        await db.commit()
    return {"date": date, "start_time": start_time, "end_time": end_time}


async def get_schedule(date: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM broadcast_schedule WHERE date = ?", (date,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_all_schedules() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM broadcast_schedule ORDER BY date DESC LIMIT 30"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def create_broadcast_log(date: str, start_time: str, end_time: str, playlist_json: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO broadcast_log (date, start_time, end_time, status, playlist, created_at)
               VALUES (?, ?, ?, 'running', ?, ?)""",
            (date, start_time, end_time, playlist_json,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        await db.commit()
        return cursor.lastrowid


async def update_broadcast_log(log_id: int, status: str, end_time: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        if end_time:
            await db.execute(
                "UPDATE broadcast_log SET status = ?, end_time = ? WHERE id = ?",
                (status, end_time, log_id)
            )
        else:
            await db.execute(
                "UPDATE broadcast_log SET status = ? WHERE id = ?",
                (status, log_id)
            )
        await db.commit()


async def get_broadcast_logs() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM broadcast_log ORDER BY created_at DESC LIMIT 20"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def increment_play_count(request_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE music_requests SET play_count = play_count + 1 WHERE id = ?",
            (request_id,)
        )
        await db.commit()


async def update_song_rating(request_id: int, rating: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE music_requests 
               SET rating_sum = rating_sum + ?, 
                   rating_count = rating_count + 1,
                   five_star_count = five_star_count + (CASE WHEN ? = 5 THEN 1 ELSE 0 END),
                   low_rating_count = low_rating_count + (CASE WHEN ? IN (1, 2) THEN 1 ELSE 0 END)
               WHERE id = ?""",
            (rating, rating, rating, request_id)
        )
        await db.commit()


async def perform_weekly_cleanup(count: int):
    
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        
        cursor = await db.execute(
            """SELECT id, title, play_count, low_rating_count,
               (CASE WHEN rating_count > 0 THEN CAST(rating_sum AS FLOAT) / rating_count ELSE 0 END) as avg_rating
               FROM music_requests 
               WHERE low_rating_count >= 5 
               ORDER BY avg_rating ASC, play_count ASC 
               LIMIT ?""",
            (count,)
        )
        targets = await cursor.fetchall()
        
        if targets:
            target_ids = [t["id"] for t in targets]
            print(f"[Cleanup] 삭제 대상 곡: {[t['title'] for t in targets]}")
            await db.execute(
                f"DELETE FROM music_requests WHERE id IN ({','.join(['?']*len(target_ids))})",
                target_ids
            )
            await db.commit()
            return len(target_ids)
        return 0


async def get_played_history() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT *, 
               CASE WHEN rating_count > 0 THEN CAST(rating_sum AS FLOAT) / rating_count ELSE 0 END as avg_rating
               FROM music_requests 
               WHERE play_count > 0 
               ORDER BY id DESC"""
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def block_student(student_id: str, reason: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO blocked_students (student_id, reason, created_at) VALUES (?, ?, ?)",
            (student_id, reason, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        await db.commit()


async def unblock_student(student_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM blocked_students WHERE student_id = ?", (student_id,))
        await db.commit()


async def is_student_blocked(student_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT 1 FROM blocked_students WHERE student_id = ?", (student_id,))
        row = await cursor.fetchone()
        return row is not None


async def get_blocked_students() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM blocked_students ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
