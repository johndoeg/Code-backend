from __future__ import annotations
from sqlalchemy import text
from app import db

def compute_akseskhusus(employee_id: str) -> bool:
    if not employee_id:
        return False
    row = db.session.execute(text("""
        SELECT TOP 1 1 AS PARAMETER
        FROM APP_CAMTABACC xx
            INNER JOIN APP_USRMST ss ON ss.ACCESSCAM = xx.ACCESSCAM
        WHERE ss.EMPLOYEE_ID = :employee_id
    """), {"employee_id": employee_id}).fetchone()
    return row is not None

def compute_editable_flag(appl_no: str, status: str) -> bool:
    if status not in ("RO", "Edit"):
        return True
    row = db.session.execute(text("""
        SELECT TOP 1 1 FROM CLFCONT WITH (NOLOCK)
        WHERE UPD_STAT = 'Y' AND EXECUTION <> '' AND FLGDEL = '0' AND APPL_NO = :appl_no
    """), {"appl_no": appl_no}).fetchone()
    return row is None