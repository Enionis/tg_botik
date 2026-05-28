import os
from dataclasses import dataclass, field
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    bot_token: str = field(default_factory=lambda: os.getenv("BOT_TOKEN", ""))
    channel_id: int = field(default_factory=lambda: int(os.getenv("CHANNEL_ID", "0")))
    channel_url: str = field(
        default_factory=lambda: os.getenv("CHANNEL_URL", "https://t.me/mavk_DM")
    )
    admin_group_id: int = field(
        default_factory=lambda: int(os.getenv("ADMIN_GROUP_ID", "0"))
    )
    bot_proxy_url: str = field(default_factory=lambda: os.getenv("BOT_PROXY_URL", ""))
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", ""))
    db_host: str = field(default_factory=lambda: os.getenv("DB_HOST", "localhost"))
    db_port: int = field(default_factory=lambda: int(os.getenv("DB_PORT", "5432")))
    db_name: str = field(default_factory=lambda: os.getenv("DB_NAME", "botik"))
    db_user: str = field(default_factory=lambda: os.getenv("DB_USER", "botik"))
    db_password: str = field(default_factory=lambda: os.getenv("DB_PASSWORD", ""))
    db_pool_min_size: int = field(
        default_factory=lambda: int(os.getenv("DB_POOL_MIN_SIZE", "2"))
    )
    db_pool_max_size: int = field(
        default_factory=lambda: int(os.getenv("DB_POOL_MAX_SIZE", "10"))
    )
    initial_admin_ids: tuple[int, ...] = field(
        default_factory=lambda: tuple(
            int(x.strip())
            for x in os.getenv("INITIAL_ADMIN_IDS", "").split(",")
            if x.strip().isdigit()
        )
    )

    max_match_time_minutes: int = 60
    max_players: int = 20
    screenshot_timeout_hours: int = 24

    valid_maps: frozenset[str] = frozenset(
        {
            "Arena",
            "Breeze",
            "Bridge",
            "Calypso",
            "Dune",
            "Favelas",
            "Hanari",
            "Lakeside",
            "Pipeline",
            "Polygon",
            "Pool",
            "Province",
            "Ritual Arena",
            "Rust",
            "Sanctum",
            "Sand Yards",
            "Sandstone",
            "Temple Yard",
            "Training Outside",
            "Village",
            "Zone 7",
        }
    )

    def postgres_dsn(self) -> str:
        if self.database_url:
            return self.database_url
        if not self.db_password:
            raise ValueError(
                "Задайте DATABASE_URL или DB_PASSWORD для подключения к PostgreSQL."
            )
        password = quote_plus(self.db_password)
        return (
            f"postgresql://{self.db_user}:{password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings()
