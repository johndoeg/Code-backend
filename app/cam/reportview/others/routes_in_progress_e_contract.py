from flask import Blueprint, jsonify, request, current_app, session
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.utils.helpers.base_format import (
    WRAP_TOP_LEFT,
    _branch,
    _username,
    branch_name,
    env_int,
    title_font,
    today_ddmmyyyy,
    workbook_response,
)
from app.utils.helpers.settings_helpers import company_name as get_company_name

in_progress_e_contract_bp = Blueprint("in_progress_e_contract", __name__, url_prefix="/CAM/Others")

HO_BRANCH_CD = "100"
CONSOLIDATE_CD = "000"
PAGE_SIZE_DEFAULT = env_int("PAGE_SIZE_DEFAULT", 25)
MAX_PAGE_SIZE = 200

_THIN   = Side(style="thin", color="000000")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
_LEFT   = Alignment(horizontal="left",   vertical="center")
_F_HDR  = Font(name="Tahoma", size=10, bold=True)
_F_DATA = Font(name="Tahoma", size=10)
_FILL_HDR = PatternFill("solid", fgColor="D9E1F2")

_HEADERS = ["No.", "CAM No.", "Contract No.", "Customer Name",
            "Brand / Type", "CMO", "Status", "Last Update"]
_COL_WIDTHS = [6, 18, 18, 30, 26, 20, 20, 20]

_SELECT = """
    SELECT ApplNo, LeaseNo, LesseeNm, BrandName, TypeName,
           CMOName, CurrentStatus, LastUpdate
    FROM V_EContractStatus
"""

def _session_user() -> tuple[str, str, str]:
    emp_id      = (session.get("emp_id") or "").strip()
    accesslevel = (session.get("accesslevel") or "").strip()
    return emp_id, accesslevel, (_branch() or "").strip()

def _effective_branch(branch_cd: str, requested: str) -> tuple[str, bool]:
    is_ho = branch_cd == HO_BRANCH_CD
    if not is_ho:
        return branch_cd, False
    return (requested or CONSOLIDATE_CD), True

def _where(branch: str, lessee_nm: str, search_no: str) -> tuple[str, dict]:
    clauses: list[str] = []
    params: dict = {}

    if branch and branch != CONSOLIDATE_CD:
        clauses.append("BranchCode = :branch")
        params["branch"] = branch

    if lessee_nm:
        clauses.append("LesseeNm LIKE :lessee_nm")
        params["lessee_nm"] = f"%{lessee_nm}%"

    if search_no:
        clauses.append("(ApplNo = :search_no OR LeaseNo = :search_no)")
        params["search_no"] = search_no

    emp_id, accesslevel, _ = _session_user()
    if accesslevel == "CMO":
        clauses.append("CMOID = :emp_id")
        params["emp_id"] = emp_id
    elif accesslevel == "CMH":
        clauses.append("(CMOID = :emp_id OR CMHID = :emp_id)")
        params["emp_id"] = emp_id

    sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return sql, params

def _brand_type(brand: str, type_nm: str) -> str:
    if not brand and not type_nm:
        return "-"
    return f"{brand} / {type_nm}"

def _serialize(rows) -> list[dict]:
    out = []
    for r in rows:
        last = r["LastUpdate"]
        out.append({
            "appl_no":        r["ApplNo"]        or "",
            "lease_no":       r["LeaseNo"]       or "",
            "lessee_nm":      r["LesseeNm"]      or "",
            "brand_type":     _brand_type(r["BrandName"] or "", r["TypeName"] or ""),
            "cmo_name":       r["CMOName"]       or "",
            "current_status": r["CurrentStatus"] or "",
            "last_update":    last.strftime("%d-%m-%Y %H:%M:%S") if last else "",
        })
    return out

def _fetch(branch: str, lessee_nm: str, search_no: str,
           page: int, limit: int, want_all: bool) -> tuple[list[dict], int]:
    where_sql, params = _where(branch, lessee_nm, search_no)

    if want_all:
        sql = f"{_SELECT}{where_sql} ORDER BY LastUpdate DESC"
        rows = db.session.execute(text(sql), params).mappings().all()
        return _serialize(rows), len(rows)

    sql = f"""
        SELECT COUNT(*) OVER() AS total_rows, *
        FROM (
            {_SELECT}{where_sql}
        ) t
        ORDER BY LastUpdate DESC
        OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
    """
    params = {**params, "offset": (page - 1) * limit, "limit": limit}
    rows = db.session.execute(text(sql), params).mappings().all()
    total = int(rows[0]["total_rows"]) if rows else 0
    return _serialize(rows), total

def _build_workbook(rows: list[dict], branch_label: str) -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "InProgressEContract"

    n_cols = len(_HEADERS)
    last = get_column_letter(n_cols)

    ws["A1"].value = get_company_name()
    ws["A1"].font = _F_DATA
    ws["A1"].alignment = _LEFT

    ws[f"{last}1"].value = f"Date : {today_ddmmyyyy()}\nPrint By : {_username()}"
    ws[f"{last}1"].font = _F_DATA
    ws[f"{last}1"].alignment = WRAP_TOP_LEFT
    ws.row_dimensions[1].height = 30

    ws.merge_cells(f"A2:{last}2")
    ws["A2"].value = "List In Progress E-Contract"
    ws["A2"].font = title_font(16)
    ws["A2"].alignment = _CENTER
    ws.row_dimensions[2].height = 24

    ws.merge_cells(f"A3:{last}3")
    ws["A3"].value = f"Branch : {branch_label}"
    ws["A3"].font = _F_DATA
    ws["A3"].alignment = _LEFT

    for col, header in enumerate(_HEADERS, 1):
        c = ws.cell(row=5, column=col, value=header)
        c.font = _F_HDR
        c.alignment = _CENTER
        c.border = _BORDER
        c.fill = _FILL_HDR

    for idx, r in enumerate(rows):
        row_no = idx + 6
        values = [idx + 1, r["appl_no"], r["lease_no"], r["lessee_nm"],
                  r["brand_type"], r["cmo_name"], r["current_status"], r["last_update"]]
        for col, value in enumerate(values, 1):
            c = ws.cell(row=row_no, column=col, value=value)
            c.font = _F_DATA
            c.border = _BORDER
            c.alignment = _LEFT if col == 4 else _CENTER

    for col, width in enumerate(_COL_WIDTHS, 1):
        ws.column_dimensions[get_column_letter(col)].width = width

    ws.freeze_panes = "A6"
    return wb

@in_progress_e_contract_bp.route("/InProgressEContract/branches")
@login_required
def get_branches():
    try:
        _, _, branch_cd = _session_user()
        rows = db.session.execute(text(
            "SELECT BRANCH_CD, BRANCH_NAME FROM UMFBRANCH WITH(NOLOCK) "
            "WHERE BRANCH_CD <> :ho ORDER BY BRANCH_CD"
        ), {"ho": HO_BRANCH_CD}).mappings().all()

        effective, is_ho = _effective_branch(branch_cd, "")
        return jsonify({
            "branches": [{"branch_cd": r["BRANCH_CD"],
                          "branch_name": r["BRANCH_NAME"] or ""} for r in rows],
            "is_ho": is_ho,
            "branch_cd": effective,
        })
    except Exception:
        current_app.logger.exception("In Progress E-Contract branches error")
        return jsonify({"error": "Failed to load branches"}), 500

@in_progress_e_contract_bp.route("/InProgressEContract/data")
@login_required
def get_data():
    _, _, branch_cd = _session_user()
    branch, _is_ho = _effective_branch(branch_cd, request.args.get("branch", "").strip())

    lessee_nm = request.args.get("lessee_nm", "").strip()
    search_no = request.args.get("search_no", "").strip()
    want_all  = request.args.get("all", "").strip().lower() in ("1", "true", "yes")

    page  = max(request.args.get("page", 1, type=int) or 1, 1)
    limit = request.args.get("limit", PAGE_SIZE_DEFAULT, type=int) or PAGE_SIZE_DEFAULT
    limit = min(max(limit, 1), MAX_PAGE_SIZE)

    try:
        rows, total = _fetch(branch, lessee_nm, search_no, page, limit, want_all)
        return jsonify({
            "rows":         rows,
            "total":        total,
            "page":         1 if want_all else page,
            "limit":        len(rows) if want_all else limit,
            "branch_name":  branch_name(branch),
            "company_name": get_company_name(),
            "printed_by":   _username(),
        })
    except Exception:
        current_app.logger.exception("In Progress E-Contract data error")
        return jsonify({"error": "Failed to load data"}), 500

@in_progress_e_contract_bp.route("/InProgressEContract/excel")
@login_required
def export_excel():
    _, _, branch_cd = _session_user()
    branch, _is_ho = _effective_branch(branch_cd, request.args.get("branch", "").strip())

    lessee_nm = request.args.get("lessee_nm", "").strip()
    search_no = request.args.get("search_no", "").strip()

    try:
        rows, _ = _fetch(branch, lessee_nm, search_no, 1, MAX_PAGE_SIZE, True)
        wb = _build_workbook(rows, branch_name(branch))
        return workbook_response(wb, "ListInProgressEContract.xlsx")
    except Exception:
        current_app.logger.exception("In Progress E-Contract Excel error")
        return jsonify({"error": "Failed to generate Excel"}), 500