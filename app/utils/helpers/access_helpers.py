from app import db
from sqlalchemy import text

def user_right(accesslevel: str, menu_id: str) -> str:
    
    if not accesslevel or not menu_id:
        return ''

    row = db.session.execute(
        text("""
            SELECT userright FROM APP_CAMMNACC WITH(NOLOCK)
            WHERE ACCESSCAM = :accesslevel AND menu_id = :menu_id
        """),
        {"accesslevel": str(accesslevel), "menu_id": str(menu_id)},
    ).first()

    return row.userright if row and row.userright is not None else ''