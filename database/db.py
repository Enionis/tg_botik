import asyncpg
from datetime import datetime, timedelta, timezone
from typing import Any

from config import settings


def _row_to_dict(row: asyncpg.Record | None) -> dict[str, Any] | None:
    return dict(row) if row else None


class Database:
    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(
            dsn=settings.postgres_dsn(),
            min_size=settings.db_pool_min_size,
            max_size=settings.db_pool_max_size,
            command_timeout=60,
        )
        await self._create_tables()
        await self._seed_initial_admins()

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("Database pool is not initialized.")
        return self._pool

    async def _create_tables(self) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id BIGINT PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    game_id TEXT,
                    nickname TEXT,
                    registered_at TIMESTAMPTZ,
                    is_registered BOOLEAN DEFAULT FALSE
                );

                CREATE TABLE IF NOT EXISTS roles (
                    telegram_id BIGINT PRIMARY KEY REFERENCES users(telegram_id),
                    role TEXT NOT NULL CHECK (role IN ('admin')),
                    display_name TEXT
                );

                CREATE TABLE IF NOT EXISTS hosters (
                    telegram_id BIGINT PRIMARY KEY,
                    nickname TEXT NOT NULL,
                    game_id TEXT NOT NULL,
                    username TEXT,
                    added_at TIMESTAMPTZ NOT NULL
                );

                CREATE TABLE IF NOT EXISTS matches (
                    id SERIAL PRIMARY KEY,
                    hoster_id BIGINT NOT NULL REFERENCES users(telegram_id),
                    lobby_url TEXT NOT NULL,
                    map_name TEXT NOT NULL,
                    time_minutes INTEGER NOT NULL,
                    player_limit INTEGER NOT NULL,
                    channel_message_id BIGINT,
                    status TEXT DEFAULT 'active',
                    registered BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL,
                    registered_at TIMESTAMPTZ,
                    screenshot_file_id TEXT,
                    screenshot_rejected BOOLEAN DEFAULT FALSE,
                    end_notified BOOLEAN DEFAULT FALSE,
                    screenshot_deadline TIMESTAMPTZ
                );

                CREATE TABLE IF NOT EXISTS match_stats (
                    id SERIAL PRIMARY KEY,
                    match_id INTEGER NOT NULL REFERENCES matches(id),
                    user_id BIGINT REFERENCES users(telegram_id),
                    nickname TEXT NOT NULL,
                    kills INTEGER NOT NULL,
                    deaths INTEGER NOT NULL,
                    assists INTEGER NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_users_username ON users (LOWER(username));
                CREATE INDEX IF NOT EXISTS idx_users_nickname ON users (LOWER(nickname));
                CREATE INDEX IF NOT EXISTS idx_hosters_username ON hosters (LOWER(username));
                CREATE INDEX IF NOT EXISTS idx_matches_hoster ON matches (hoster_id);
                CREATE INDEX IF NOT EXISTS idx_matches_registered_at ON matches (registered_at);
                """
            )
            await conn.execute(
                """
                ALTER TABLE matches
                ADD COLUMN IF NOT EXISTS end_notified BOOLEAN DEFAULT FALSE
                """
            )
            await conn.execute("DELETE FROM roles WHERE role <> 'admin'")
            await conn.execute("ALTER TABLE roles DROP CONSTRAINT IF EXISTS roles_role_check")
            await conn.execute(
                """
                ALTER TABLE roles
                ADD CONSTRAINT roles_role_check CHECK (role IN ('admin'))
                """
            )

    async def _seed_initial_admins(self) -> None:
        async with self.pool.acquire() as conn:
            for admin_id in settings.initial_admin_ids:
                await conn.execute(
                    """
                    INSERT INTO users (telegram_id, first_name, is_registered)
                    VALUES ($1, 'Initial Admin', FALSE)
                    ON CONFLICT (telegram_id) DO NOTHING
                    """,
                    admin_id,
                )
                await conn.execute(
                    """
                    INSERT INTO roles (telegram_id, role, display_name)
                    VALUES ($1, 'admin', 'Initial Admin')
                    ON CONFLICT (telegram_id) DO NOTHING
                    """,
                    admin_id,
                )

    # --- Users ---

    async def get_user(self, telegram_id: int) -> dict[str, Any] | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE telegram_id = $1", telegram_id
            )
            return _row_to_dict(row)

    async def upsert_user_basic(
        self,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
    ) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO users (telegram_id, username, first_name, last_name)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (telegram_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name
                """,
                telegram_id,
                username,
                first_name,
                last_name,
            )

    async def set_user_game_id(self, telegram_id: int, game_id: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET game_id = $1 WHERE telegram_id = $2",
                game_id,
                telegram_id,
            )

    async def complete_registration(self, telegram_id: int, nickname: str) -> None:
        now = datetime.now(timezone.utc)
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE users
                SET nickname = $1, registered_at = $2, is_registered = TRUE
                WHERE telegram_id = $3
                """,
                nickname,
                now,
                telegram_id,
            )

    async def count_users(self) -> int:
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT COUNT(*) FROM users WHERE is_registered = TRUE"
            )

    async def find_user_by_nickname(self, nickname: str) -> dict[str, Any] | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE LOWER(nickname) = LOWER($1)",
                nickname.strip(),
            )
            return _row_to_dict(row)

    # --- Roles ---

    async def get_role(self, telegram_id: int) -> str | None:
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT role FROM roles WHERE telegram_id = $1", telegram_id
            )

    async def is_admin(self, telegram_id: int) -> bool:
        return await self.get_role(telegram_id) == "admin"

    async def add_role(
        self, telegram_id: int, role: str, display_name: str | None = None
    ) -> bool:
        user = await self.get_user(telegram_id)
        if not user:
            return False
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO roles (telegram_id, role, display_name)
                VALUES ($1, $2, $3)
                ON CONFLICT (telegram_id) DO UPDATE SET
                    role = EXCLUDED.role,
                    display_name = EXCLUDED.display_name
                """,
                telegram_id,
                role,
                display_name,
            )
        return True

    async def remove_role(self, telegram_id: int) -> bool:
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM roles WHERE telegram_id = $1", telegram_id
            )
        return result.endswith("1")

    async def get_roles_by_type(self, role: str) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT u.telegram_id, u.username, u.first_name, u.last_name, r.display_name
                FROM roles r
                JOIN users u ON u.telegram_id = r.telegram_id
                WHERE r.role = $1
                ORDER BY u.first_name
                """,
                role,
            )
            return [dict(r) for r in rows]

    async def find_user_by_username(self, username: str) -> dict[str, Any] | None:
        username = username.lstrip("@").lower()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE LOWER(username) = LOWER($1)", username
            )
            return _row_to_dict(row)

    # --- Hosters ---

    async def is_hoster(self, telegram_id: int, username: str | None = None) -> bool:
        async with self.pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT 1 FROM hosters WHERE telegram_id = $1", telegram_id
            )
            if exists:
                return True
            if username:
                return bool(
                    await conn.fetchval(
                        "SELECT 1 FROM hosters WHERE LOWER(username) = LOWER($1)",
                        username.lstrip("@"),
                    )
                )
        return False

    async def link_hoster_by_username(
        self, telegram_id: int, username: str | None
    ) -> None:
        if not username:
            return
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE hosters SET telegram_id = $1
                WHERE LOWER(username) = LOWER($2) AND telegram_id < 0
                """,
                telegram_id,
                username.lstrip("@"),
            )

    async def can_create_match(
        self, telegram_id: int, username: str | None = None
    ) -> bool:
        return (
            await self.is_hoster(telegram_id, username)
            or await self.is_admin(telegram_id)
        )

    async def get_all_hosters(self) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM hosters ORDER BY nickname")
            return [dict(r) for r in rows]

    async def count_hosters(self) -> int:
        async with self.pool.acquire() as conn:
            return await conn.fetchval("SELECT COUNT(*) FROM hosters")

    async def add_hoster(
        self,
        telegram_id: int | None,
        nickname: str,
        game_id: str,
        username: str | None,
    ) -> None:
        now = datetime.now(timezone.utc)
        clean_username = username.lstrip("@") if username else None
        if not telegram_id and clean_username:
            telegram_id = -(abs(hash(clean_username.lower())) % (10**12) or 1)
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO hosters (telegram_id, nickname, game_id, username, added_at)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (telegram_id) DO UPDATE SET
                    nickname = EXCLUDED.nickname,
                    game_id = EXCLUDED.game_id,
                    username = EXCLUDED.username,
                    added_at = EXCLUDED.added_at
                """,
                telegram_id or 0,
                nickname,
                game_id,
                clean_username,
                now,
            )

    async def remove_hoster_by_username(self, username: str) -> dict[str, Any] | None:
        username = username.lstrip("@")
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM hosters WHERE LOWER(username) = LOWER($1)", username
            )
            if not row:
                return None
            hoster = dict(row)
            await conn.execute(
                "DELETE FROM hosters WHERE telegram_id = $1", hoster["telegram_id"]
            )
            return hoster

    # --- Matches ---

    async def create_match(
        self,
        hoster_id: int,
        lobby_url: str,
        map_name: str,
        time_minutes: int,
        player_limit: int,
    ) -> int:
        now = datetime.now(timezone.utc)
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                """
                INSERT INTO matches (
                    hoster_id, lobby_url, map_name, time_minutes, player_limit, created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                hoster_id,
                lobby_url,
                map_name,
                time_minutes,
                player_limit,
                now,
            )

    async def set_match_channel_message(self, match_id: int, message_id: int) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE matches SET channel_message_id = $1 WHERE id = $2",
                message_id,
                match_id,
            )

    async def get_match(self, match_id: int) -> dict[str, Any] | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM matches WHERE id = $1", match_id)
            return _row_to_dict(row)

    async def get_pending_screenshot_match(
        self, hoster_id: int
    ) -> dict[str, Any] | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM matches
                WHERE hoster_id = $1 AND registered = FALSE AND status = 'active'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                hoster_id,
            )
            return _row_to_dict(row)

    async def set_match_screenshot(self, match_id: int, file_id: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE matches
                SET screenshot_file_id = $1, screenshot_deadline = NULL
                WHERE id = $2
                """,
                file_id,
                match_id,
            )

    async def reject_screenshot(self, match_id: int) -> None:
        deadline = datetime.now(timezone.utc) + timedelta(
            hours=settings.screenshot_timeout_hours
        )
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE matches
                SET screenshot_rejected = TRUE, screenshot_deadline = $1
                WHERE id = $2
                """,
                deadline,
                match_id,
            )

    async def resubmit_screenshot(self, match_id: int, file_id: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE matches
                SET screenshot_file_id = $1,
                    screenshot_rejected = FALSE,
                    screenshot_deadline = NULL
                WHERE id = $2
                """,
                file_id,
                match_id,
            )

    async def register_match(
        self, match_id: int, stats: list[dict[str, Any]]
    ) -> None:
        now = datetime.now(timezone.utc)
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                for stat in stats:
                    await conn.execute(
                        """
                        INSERT INTO match_stats (
                            match_id, user_id, nickname, kills, deaths, assists
                        )
                        VALUES ($1, $2, $3, $4, $5, $6)
                        """,
                        match_id,
                        stat.get("user_id"),
                        stat["nickname"],
                        stat["kills"],
                        stat["deaths"],
                        stat["assists"],
                    )
                await conn.execute(
                    """
                    UPDATE matches
                    SET registered = TRUE, status = 'completed', registered_at = $1
                    WHERE id = $2
                    """,
                    now,
                    match_id,
                )

    async def count_matches_total(self) -> int:
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT COUNT(*) FROM matches WHERE registered = TRUE"
            )

    async def count_matches_month(self) -> int:
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                """
                SELECT COUNT(*) FROM matches
                WHERE registered = TRUE
                  AND registered_at >= NOW() - INTERVAL '30 days'
                """
            )

    async def get_matches_to_notify_finished(self) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM matches
                WHERE registered = FALSE
                  AND status = 'active'
                  AND end_notified = FALSE
                  AND screenshot_file_id IS NULL
                  AND created_at + (time_minutes * INTERVAL '1 minute') <= NOW()
                """
            )
            return [dict(r) for r in rows]

    async def mark_match_end_notified(self, match_id: int) -> None:
        deadline = datetime.now(timezone.utc) + timedelta(
            hours=settings.screenshot_timeout_hours
        )
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE matches
                SET end_notified = TRUE, screenshot_deadline = $1
                WHERE id = $2
                """,
                deadline,
                match_id,
            )

    async def get_expired_screenshot_matches(self) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM matches
                WHERE screenshot_deadline IS NOT NULL
                  AND screenshot_deadline <= NOW()
                  AND registered = FALSE
                  AND status != 'expired'
                  AND (
                    screenshot_rejected = TRUE
                    OR (end_notified = TRUE AND screenshot_file_id IS NULL)
                  )
                """
            )
            return [dict(r) for r in rows]

    async def mark_match_expired(self, match_id: int) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE matches SET status = 'expired' WHERE id = $1", match_id
            )


_db_instance: Database | None = None


async def get_db() -> Database:
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
        await _db_instance.connect()
    return _db_instance
