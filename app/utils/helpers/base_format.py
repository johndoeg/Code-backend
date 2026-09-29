import re
import calendar

from datetime import date, datetime
from app import db
from sqlalchemy import text
from flask import session

def _username():
    return session.get("username", "")

def _branch():
    return session.get("branchcode", "")

def _emp_id():
    return session.get("emp_id", "")

def _to_bit(value):
    
    if value is None:
        return None
    v = str(value).strip().lower()
    if v == "":
        return None
    if v in ("true", "1", "yes", "y"):
        return 1
    if v in ("false", "0", "no", "n"):
        return 0
    return None

def _strip_non_digit(value: str) -> str:
    return re.sub(r"\D", "", value or "")

def fmt_date(d, fmt: str = "%d %b %Y") -> str:
    if d is None:
        return ""
    if isinstance(d, datetime):
        return d.strftime(fmt)
    if isinstance(d, date):
        return d.strftime(fmt)
    return str(d)

def parse_date(raw: str) -> str:
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m", "%d %b %Y", "%d %B %Y", "%B %Y", "%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date format: {raw!r}")

def as_of_date(ratio: str, imp_date_str: str) -> str:
    d = datetime.strptime(parse_date(imp_date_str), "%Y-%m-%d")
    if ratio == "5":
        return f"{d.year}-12-31"
    last_day = calendar.monthrange(d.year, d.month)[1]
    return f"{d.year}-{d.month:02d}-{last_day:02d}"

def can_edit(implement_date) -> bool:
    if implement_date is None:
        return False
    if isinstance(implement_date, datetime):
        d = implement_date.date()
    elif isinstance(implement_date, date):
        d = implement_date
    else:
        return False
    return d >= date.today()

def format_threshold(ratio: str, remark_val: str, val_from: str, val_to: str) -> str:
    r = str(ratio)
    m = str(remark_val)
    f = val_from or ""
    t = val_to   or ""
    if r in ("1", "5"):
        suffix = ""
    elif r == "2":
        suffix = "x"
    else:
        suffix = "%"
    if m == "3":
        return f"{f}{suffix} s/d {t}{suffix}"
    return f"{f}{suffix}"

def get_combo(cat_value: str) -> list:
    rows = db.session.execute(
        text("SELECT VALUE, DESC_VALUE FROM MSTCOMBO WITH(NOLOCK) WHERE CAT_VALUE = :cat ORDER BY VALUE"),
        {"cat": cat_value}
    ).fetchall()
    return [{"value": r.VALUE, "desc_value": r.DESC_VALUE} for r in rows]