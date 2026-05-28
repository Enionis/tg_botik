import re

from config import settings


LOBBY_URL_PATTERN = re.compile(
    r"https?://link\.standoff2\.com/[^\s]+",
    re.IGNORECASE,
)


def validate_lobby_url(text: str) -> str | None:
    match = LOBBY_URL_PATTERN.search(text.strip())
    if match:
        return match.group(0)
    return None


def parse_match_info(text: str) -> tuple[str, int, int] | None:
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 3:
        return None
    map_name, time_str, players_str = parts
    if not map_name:
        return None
    try:
        time_minutes = int(time_str)
        player_limit = int(players_str)
    except ValueError:
        return None
    return map_name, time_minutes, player_limit


def validate_match_info(map_name: str, time_minutes: int, player_limit: int) -> str | None:
    valid_map = None
    for m in settings.valid_maps:
        if m.lower() == map_name.lower():
            valid_map = m
            break
    if not valid_map:
        return f"Карта «{map_name}» не найдена в базе данных."
    if time_minutes <= 0 or time_minutes > settings.max_match_time_minutes:
        return f"Время должно быть от 1 до {settings.max_match_time_minutes} минут."
    if player_limit <= 0 or player_limit > settings.max_players:
        return f"Лимит игроков должен быть от 1 до {settings.max_players}."
    return None


def parse_hoster_info(text: str) -> tuple[str, str, str] | None:
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 3:
        return None
    nickname, game_id, username = parts
    if not nickname or not game_id or not username:
        return None
    if not username.startswith("@"):
        username = f"@{username}"
    return nickname, game_id, username


def parse_role_input(text: str) -> tuple[str, str] | None:
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 2:
        return None
    username, role = parts
    if not username.startswith("@"):
        username = f"@{username}"
    role_lower = role.lower()
    if role_lower in ("администратор", "admin", "administrator"):
        return username, "admin"
    return None


def parse_player_stats(text: str) -> list[dict] | None:
    lines = [ln.strip() for ln in text.strip().split("\n") if ln.strip()]
    if not lines:
        return None
    result = []
    for line in lines:
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 4:
            return None
        nickname, kills, deaths, assists = parts
        try:
            result.append(
                {
                    "nickname": nickname,
                    "kills": int(kills),
                    "deaths": int(deaths),
                    "assists": int(assists),
                }
            )
        except ValueError:
            return None
    return result


def format_display_name(user: dict) -> str:
    first = user.get("first_name") or ""
    last = user.get("last_name") or ""
    name = f"{first} {last}".strip()
    return name or "Без имени"
