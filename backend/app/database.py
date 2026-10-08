import sqlite3
from pathlib import Path
from datetime import datetime


# Database will be created at:
# backend/reality.db

DB_PATH = Path(__file__).resolve().parent.parent / "reality.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS player (
            id TEXT PRIMARY KEY,
            total_xp INTEGER NOT NULL DEFAULT 0,
            cases_solved INTEGER NOT NULL DEFAULT 0,
            cases_attempted INTEGER NOT NULL DEFAULT 0
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS completed_cases (
            case_id TEXT PRIMARY KEY,
            xp_earned INTEGER NOT NULL,
            solved_at TEXT NOT NULL
        )
        """
    )

    conn.execute(
        """
        INSERT OR IGNORE INTO player
        (id, total_xp, cases_solved, cases_attempted)
        VALUES ('local-player', 0, 0, 0)
        """
    )

    conn.commit()
    conn.close()


def get_player():
    conn = get_connection()

    row = conn.execute(
        """
        SELECT id, total_xp, cases_solved, cases_attempted
        FROM player
        WHERE id = 'local-player'
        """
    ).fetchone()

    conn.close()

    return dict(row)


def record_attempt():
    conn = get_connection()

    conn.execute(
        """
        UPDATE player
        SET cases_attempted = cases_attempted + 1
        WHERE id = 'local-player'
        """
    )

    conn.commit()
    conn.close()


def award_xp(case_id: str, xp: int):
    conn = get_connection()

    # Prevent the same case from awarding XP twice.
    existing = conn.execute(
        """
        SELECT case_id
        FROM completed_cases
        WHERE case_id = ?
        """,
        (case_id,),
    ).fetchone()

    if existing:
        player = conn.execute(
            """
            SELECT id, total_xp, cases_solved, cases_attempted
            FROM player
            WHERE id = 'local-player'
            """
        ).fetchone()

        conn.close()

        return {
            "awarded": False,
            "xp_earned": 0,
            "total_xp": player["total_xp"],
            "cases_solved": player["cases_solved"],
            "cases_attempted": player["cases_attempted"],
        }

    now = datetime.utcnow().isoformat()

    conn.execute(
        """
        INSERT INTO completed_cases
        (case_id, xp_earned, solved_at)
        VALUES (?, ?, ?)
        """,
        (case_id, xp, now),
    )

    conn.execute(
        """
        UPDATE player
        SET
            total_xp = total_xp + ?,
            cases_solved = cases_solved + 1
        WHERE id = 'local-player'
        """,
        (xp,),
    )

    conn.commit()

    player = conn.execute(
        """
        SELECT id, total_xp, cases_solved, cases_attempted
        FROM player
        WHERE id = 'local-player'
        """
    ).fetchone()

    conn.close()

    return {
        "awarded": True,
        "xp_earned": xp,
        "total_xp": player["total_xp"],
        "cases_solved": player["cases_solved"],
        "cases_attempted": player["cases_attempted"],
    }