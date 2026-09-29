_active_sessions: dict[str, str] = {}

def set_active_session(username: str, token: str) -> None:
    _active_sessions[username] = token

def get_active_session(username: str) -> str | None:
    return _active_sessions.get(username)

def clear_active_session(username: str) -> None:
    _active_sessions.pop(username, None)