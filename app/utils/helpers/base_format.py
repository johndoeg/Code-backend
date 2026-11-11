import os
import re
import io
import calendar

from datetime import date, datetime
from typing import Optional

from app import db
from sqlalchemy import text
from flask import session, send_file

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

from app.utils.helpers.settings_helpers import company_name

def _username():
    return session.get("username", "")

def _branch():
    return session.get("branchcode", "")

def _emp_id():
    return session.get("emp_id", "")

def _access_level():
    return session.get("accesslevel", "")

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

def exec_rows(sql: str, params: list) -> list[dict]:
    raw_conn = db.session.connection().connection
    cursor = raw_conn.cursor()
    try:
        cursor.execute(sql, params)
        if cursor.description is None:
            return []
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        cursor.close()

def exec_multi_resultset(sql: str, params: list) -> list[dict]:
    raw_conn = db.session.connection().connection
    cursor = raw_conn.cursor()
    all_rows: list[dict] = []
    try:
        cursor.execute(sql, params)
        while True:
            if cursor.description is not None:
                columns = [col[0] for col in cursor.description]
                all_rows += [dict(zip(columns, row)) for row in cursor.fetchall()]
            if not cursor.nextset():
                break
        return all_rows
    finally:
        cursor.close()

def parse_iso_date(raw: str) -> Optional[date]:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None

def sp_date(d) -> str:
    if d is None or d == '':
        return ''
    if hasattr(d, 'isoformat'):
        return d.isoformat()[:10]
    return str(d)

def env_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        val = int(str(raw).strip())
    except (TypeError, ValueError):
        return default
    return val if val >= minimum else default

def num(val) -> float:
    if val is None:
        return 0.0
    return float(val)

def safe_div(a, b):
    return (a / b) if b else 0

def fmt_ddmmyyyy(d) -> str:
    return fmt_date(d, "%d-%m-%Y")

def fmt_long(d) -> str:
    return fmt_date(d, "%d %B %Y")

def today_ddmmyyyy() -> str:
    return datetime.now().strftime("%d-%m-%Y")

def period_label(start_date, end_date) -> str:
    if start_date and end_date:
        return f"Period : {fmt_ddmmyyyy(start_date)} to {fmt_ddmmyyyy(end_date)}"
    return ""

def period_label_long(start_date, end_date) -> str:
    if start_date and end_date:
        return f"{fmt_long(start_date)} - {fmt_long(end_date)}"
    return ""

def range_plain(start_date, end_date) -> str:
    if start_date and end_date:
        return f"{fmt_ddmmyyyy(start_date)} to {fmt_ddmmyyyy(end_date)}"
    return ""

def branch_name(branch_cd: str) -> str:
    if not branch_cd:
        return ""
    rows = exec_rows("SELECT BRANCH_NAME FROM UMFBRANCH WITH (NOLOCK) WHERE BRANCH_CD = ?", [branch_cd])
    return (rows[0]["BRANCH_NAME"] or "").strip() if rows else ""

def fetch_branch_list(exclude_ho: bool = True) -> list[dict]:
    if exclude_ho:
        rows = exec_rows(
            "SELECT BRANCH_CD, BRANCH_NAME FROM UMFBRANCH WITH (NOLOCK) WHERE BRANCH_CD <> '100' ORDER BY BRANCH_CD",
            [],
        )
    else:
        rows = exec_rows(
            "SELECT BRANCH_CD, BRANCH_NAME FROM UMFBRANCH WITH (NOLOCK) ORDER BY BRANCH_CD", []
        )
    return [{"branch_cd": r.get("BRANCH_CD"), "branch_name": r.get("BRANCH_NAME")} for r in rows]

def fetch_branch_options() -> dict:
    return {
        "branches": fetch_branch_list(exclude_ho=False),
        "default_branch_cd": _branch() or "",
    }

def fetch_subordinate_ids(emp_id: str) -> list[str]:
    rows = exec_rows(
        "SELECT EMPLOYEE_ID FROM APP_USRMST WITH (NOLOCK) WHERE EMPLOYEE_ID = ? OR SUPERIOR = ?",
        [emp_id, emp_id],
    )
    return [r["EMPLOYEE_ID"] for r in rows] or [emp_id]

def fetch_revisions(appl_nos: list[str]) -> dict[str, str]:
    if not appl_nos:
        return {}
    placeholders = ",".join("?" for _ in appl_nos)
    rows = exec_rows(
        f"SELECT NEWAPPL_NO, REVISI FROM MCMORevisi WITH (NOLOCK) WHERE NEWAPPL_NO IN ({placeholders})",
        appl_nos,
    )
    return {r["NEWAPPL_NO"]: f"R{r['REVISI']}" for r in rows}

STATUS_LABELS = {
    "A": "Approved",
    "F": "Approved & Send to Admin",
    "R": "Reject",
    "N": "Send for Approval",
}

COMMITTEE_ROLE_CODES = ("CRH", "ODH", "CRDH", "DR", "PD")

def fetch_cam_basic_info(appl_no: str) -> dict:
    rows = exec_rows(
        """
        SELECT LTRIM(RTRIM(a.CMO)) AS CMO, b.LESSEE_NM, b.apless, c.USERNAME
        FROM CAFCONT a WITH (NOLOCK)
            LEFT JOIN CAFLESS b WITH (NOLOCK) ON a.APLESS = b.APLESS
            LEFT JOIN APP_USRMST c WITH (NOLOCK) ON a.CMO = c.EMPLOYEE_ID
        WHERE a.APPL_NO = ?
        """,
        [appl_no],
    )
    return rows[0] if rows else {}

def fetch_revision_suffix(appl_no: str) -> str:
    rows = exec_rows("SELECT REVISI FROM MCMOREVISI WITH (NOLOCK) WHERE NEWAPPL_NO = ?", [appl_no])
    return f"R{rows[0]['REVISI']}" if rows else ""

def fetch_approval_history(appl_no: str, require_comment: bool, role_codes=COMMITTEE_ROLE_CODES) -> list[dict]:
    comment_filter = "AND a.comment IS NOT NULL AND a.comment <> ''" if require_comment else ""
    role_placeholders = ",".join("?" for _ in role_codes)
    sql = f"""
        SELECT * FROM (
            SELECT a.[No], a.APPR_ID, a.APPR_DATE, a.COMMENT, SUBSTRING(a.APPR_STS, 1, 1) AS APPR_STS
            FROM MCMOCAMOUTSSTATUS a WITH (NOLOCK)
            WHERE a.APPL_NO = ? AND (a.APPR_STS IN ('N', 'A', 'F', 'R') OR a.APPR_STS LIKE '%R')

            UNION

            SELECT a.[No], a.APPR_ID, a.APPR_DATE, a.COMMENT, SUBSTRING(a.APPR_STS, 1, 1) AS APPR_STS
            FROM MCMOCAMStatus a WITH (NOLOCK)
            WHERE a.APPL_NO = ? AND (a.APPR_STS IN ('N', 'A', 'F', 'R') OR a.APPR_STS LIKE '%R')
        ) a
        WHERE a.APPR_ID IN (SELECT username FROM app_usrmst WHERE ACCESSCAM IN ({role_placeholders}))
            {comment_filter}
        ORDER BY a.[No]
    """
    rows = exec_rows(sql, [appl_no, appl_no, *role_codes])
    history = []
    for r in rows:
        appr_date = r.get("APPR_DATE")
        history.append({
            "date": appr_date.strftime("%d-%m-%Y %H:%M:%S") if appr_date else "",
            "approved_by": r.get("APPR_ID"),
            "status": STATUS_LABELS.get(r.get("APPR_STS"), ""),
            "comment": r.get("COMMENT") or "",
        })
    return history

def fetch_related_cams(appl_no: str, apless: Optional[str], role_codes=COMMITTEE_ROLE_CODES) -> list[dict]:
    related_rows = exec_multi_resultset("EXEC USP_ListCamCommittee ?, ?", [appl_no, apless])
    related = []
    for r in related_rows:
        related_appl_no = r.get("appl_no")
        if not related_appl_no:
            continue
        if not fetch_approval_history(related_appl_no, require_comment=True, role_codes=role_codes):
            continue
        history = fetch_approval_history(related_appl_no, require_comment=False, role_codes=role_codes)
        info = fetch_cam_basic_info(related_appl_no)
        suffix = fetch_revision_suffix(related_appl_no)
        related.append({
            "appl_no_display": f"{related_appl_no}{suffix}",
            "customer_name": info.get("LESSEE_NM"),
            "cmo_name": info.get("USERNAME"),
            "history": history,
        })
    return related

def build_comments_payload(appl_no: str, role_codes=COMMITTEE_ROLE_CODES) -> dict:
    """Payload for the 'Credit Committee Comments' modal."""
    info = fetch_cam_basic_info(appl_no)
    suffix = fetch_revision_suffix(appl_no)
    return {
        "main": {
            "appl_no_display": f"{appl_no}{suffix}",
            "customer_name": info.get("LESSEE_NM"),
            "cmo_name": info.get("USERNAME"),
            "history": fetch_approval_history(appl_no, require_comment=False, role_codes=role_codes),
        },
        "related": fetch_related_cams(appl_no, info.get("apless"), role_codes=role_codes),
    }

XLSX_MIMETYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

THIN_SIDE = Side(style='thin', color='FF000000')
ALL_BORDERS = Border(top=THIN_SIDE, bottom=THIN_SIDE, left=THIN_SIDE, right=THIN_SIDE)

HEADER_FONT = Font(bold=True)
ITALIC_FONT = Font(italic=True)
RED_BOLD_FONT = Font(color='FFFF0000', bold=True)
CENTER = Alignment(horizontal='center', vertical='center')
RIGHT = Alignment(horizontal='right')
WRAP_TOP_LEFT = Alignment(wrap_text=True, horizontal='left', vertical='top')

def title_font(size: int = 16) -> Font:
    return Font(bold=True, size=size)

TITLE_FONT_TAHOMA = Font(name='Tahoma', size=12, bold=True)
DATA_FONT = Font(name='Tahoma', size=7)

STYLE_1 = {'font': DATA_FONT, 'border': ALL_BORDERS}
STYLE_2 = {'font': DATA_FONT, 'border': ALL_BORDERS, 'alignment': Alignment(horizontal='right')}
STYLE_3 = {'font': DATA_FONT, 'border': ALL_BORDERS, 'alignment': Alignment(horizontal='left')}

STYLES_BY_KEY = {'style1': STYLE_1, 'style2': STYLE_2, 'style3': STYLE_3}

def apply_style(cell, style: dict):
    cell.font = style['font']
    cell.border = style['border']
    if 'alignment' in style:
        cell.alignment = style['alignment']

def apply_style_range(ws, cell_range: str, font=None, alignment=None):
    for row in ws[cell_range]:
        for cell in row:
            if font is not None:
                cell.font = font
            if alignment is not None:
                cell.alignment = alignment

def set_cell(cell, value):
    if isinstance(value, str):
        value = ILLEGAL_CHARACTERS_RE.sub('', value)
        cell.value = value
        if value.startswith('='):
            cell.data_type = 's'
        return
    cell.value = value

def write_report_header(ws, title: str, branch_line: str, period_line: str,
                        stamp_cell: str, title_size: int = 16, row_height: int = 30,
                        date_fmt: str = '%d-%m-%Y'):

    ws['A1'] = company_name()

    ws[stamp_cell] = f"Date : {datetime.now().strftime(date_fmt)}\nPrint By : {_username()}"
    ws[stamp_cell].alignment = WRAP_TOP_LEFT
    ws.row_dimensions[1].height = row_height

    ws.merge_cells('A2:D2')
    ws['A2'] = title
    ws['A2'].font = title_font(title_size)
    ws['A2'].alignment = CENTER

    ws.merge_cells('A3:D3')
    ws['A3'] = branch_line

    ws.merge_cells('A4:D4')
    ws['A4'] = period_line

def build_report_workbook(
    sheet_title: str,
    report_title: str,
    columns: list,
    rows: list[dict],
    search_by: str,
    date_from: Optional[date],
    date_to: Optional[date],
    username: str,
) -> Workbook:
    
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title

    last_col = columns[-1][0]
    second_last_col = columns[-2][0]

    ws.merge_cells(f'A1:{second_last_col}1')
    ws.merge_cells(f'A2:{second_last_col}2')
    ws['A2'] = company_name()
    ws['A2'].alignment = Alignment(horizontal='left')

    ws[f'{last_col}1'] = f"Date : {datetime.now().strftime('%d %b %Y')}"
    ws[f'{last_col}1'].alignment = Alignment(horizontal='left')
    ws[f'{last_col}2'] = f"Print By : {username or ''}"
    ws[f'{last_col}2'].alignment = Alignment(horizontal='left')

    filter_label = 'CAM Create Date ' if search_by == '1' else 'Disbursement Date '

    ws.merge_cells(f'A3:{last_col}3')
    ws['A3'] = report_title
    apply_style_range(ws, f'A3:{last_col}3', font=TITLE_FONT_TAHOMA, alignment=CENTER)

    ws.merge_cells(f'A4:{last_col}4')
    ws['A4'] = f"{filter_label}{fmt_ddmmyyyy(date_from)} - {fmt_ddmmyyyy(date_to)}"
    ws['A4'].alignment = Alignment(horizontal='center')

    header_row = 5
    for col, _field, label, _style_key in columns:
        cell = ws[f'{col}{header_row}']
        cell.value = f' {label} '
        cell.border = ALL_BORDERS

    for col, _field, label, _style_key in columns:
        ws.column_dimensions[col].width = len(f' {label} ')
    ws.column_dimensions['A'].width = 5

    for i, row in enumerate(rows, start=1):
        excel_row = header_row + i
        for col, field, _label, style_key in columns:
            cell = ws[f'{col}{excel_row}']
            set_cell(cell, i if field is None else row.get(field))
            apply_style(cell, STYLES_BY_KEY[style_key])

    return wb

def workbook_response(wb: Workbook, download_name: str):
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return send_file(
        buffer,
        mimetype=XLSX_MIMETYPE,
        as_attachment=True,
        download_name=download_name,
    )