from flask import Blueprint, jsonify, request, current_app
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text
from datetime import date, timedelta
import calendar

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.utils.helpers.base_format import (
    WRAP_TOP_LEFT,
    _username,
    title_font,
    today_ddmmyyyy,
    workbook_response,
)
from app.utils.helpers.settings_helpers import company_name as get_company_name

monthly_summary_cam_approved_bp = Blueprint("monthly_summary_cam_approved", __name__, url_prefix="/CAM/Others")

def _date_range(bulan: int, tahun: int) -> tuple[str, str]:
    today    = date.today()
    from_dt  = date(tahun, bulan, 1)
    
    if bulan == today.month and tahun == today.year:
        to_dt = today - timedelta(days=1)
    else:
        to_dt = date(tahun, bulan, calendar.monthrange(tahun, bulan)[1])
    return from_dt.strftime("%Y-%m-%d"), to_dt.strftime("%Y-%m-%d")

def _get_font_color(emp_id: str, to_dt: str, resigned: bool) -> str:
    if resigned:
        return "red"
    try:
        row = db.session.execute(
            text("EXEC USP_COUNT_CAR_CONDITION :emp_id, :to_dt"),
            {"emp_id": emp_id, "to_dt": to_dt},
        ).mappings().first()
        return row["warna"] if row and row["warna"] else "black"
    except Exception:
        return "black"

def _get_cam_counts(emp_id: str, to_dt: str, dates: list) -> list[int]:
    try:
        rows = db.session.execute(
            text("EXEC USP_COUNT_CAM :emp_id, :to_dt"),
            {"emp_id": emp_id, "to_dt": to_dt},
        ).mappings().all()
        day_map = {r["tgl"].day: int(r["hasil"] or 0) for r in rows if r["tgl"]}
    except Exception:
        day_map = {}
    return [day_map.get(d["day_num"], 0) for d in dates]

def _build_employee(emp_id: str, fullname: str, no: int, is_cmh: bool,
                    resigned: bool, to_dt: str, working_days: int,
                    dates: list) -> dict:
    name_color = _get_font_color(emp_id, to_dt, resigned)
    counts     = _get_cam_counts(emp_id, to_dt, dates)
    total      = sum(counts)
    avg        = round(total / working_days, 2) if working_days else 0
    return {
        "no": no, "employee_id": emp_id, "fullname": fullname or "",
        "is_cmh": is_cmh, "name_color": name_color, "resigned": resigned,
        "daily_counts": counts, "total": total, "avg_per_day": avg,
    }

def _build_payload(bulan: int, tahun: int) -> dict:
    from_dt, to_dt = _date_range(bulan, tahun)

    if to_dt < from_dt:
        return {
            "asof": date(tahun, bulan, 1).strftime("%B %Y"),
            "working_days": 0, "to_date": to_dt,
            "dates": [], "branches": [],
            "grand_day_totals": [], "grand_total": 0,
            "grand_avg": 0, "grand_cmo_count": 0,
            "company_name": get_company_name(), "printed_by": _username(),
        }

    wd_row = db.session.execute(
        text("EXEC USP_DateRange :f, :t, '2'"), {"f": from_dt, "t": to_dt}
    ).mappings().first()
    working_days = max(int(wd_row["harikerja"] or 1), 1)

    date_rows = db.session.execute(
        text("EXEC USP_DateRange :f, :t, '1'"), {"f": from_dt, "t": to_dt}
    ).mappings().all()
    dates = [
        {"day_num": r["dt"].day, "day_str": r["dt"].strftime("%d"),
         "is_holiday": bool(r["holiday"])}
        for r in date_rows
    ]
    num_days = len(dates)

    branch_rows = db.session.execute(
        text("SELECT BRANCH_CD, BRANCH_NAME FROM UMFBRANCH WITH(NOLOCK) "
             "WHERE BRANCH_CD NOT IN ('000','100') ORDER BY BRANCH_CD")
    ).mappings().all()

    grand_day_totals = [0] * num_days
    grand_total = grand_cmo_count = 0
    branches_out = []

    for br in branch_rows:
        bcd, bname = br["BRANCH_CD"], br["BRANCH_NAME"]
        day_totals  = [0] * num_days
        branch_total = cmo_count = 0
        employees = []
        no = 1

        top_rows = db.session.execute(text("""
            SELECT '1' AS cmh, EMPLOYEE_ID, FULLNAME,
                   CASE WHEN DATEDIFF(m, RESIGN_DATE, :to_dt) = 0 THEN 'red' ELSE '' END AS warna
            FROM APP_USRMST WITH(NOLOCK)
            WHERE ACCESSCAM = 'CMH' AND BRANCHCODE = :bcd
                AND (RECSTATUS = 'A' OR DATEDIFF(m, RESIGN_DATE, :to_dt) <= 0)
                
            UNION
            
            SELECT '0' AS cmh, EMPLOYEE_ID, FULLNAME,
                   CASE WHEN DATEDIFF(m, RESIGN_DATE, :to_dt) = 0 THEN 'red' ELSE '' END AS warna
            FROM APP_USRMST WITH(NOLOCK)
            WHERE ACCESSCAM = 'CMO' AND (SUPERIOR IS NULL OR SUPERIOR = '') AND BRANCHCODE = :bcd
                AND (RECSTATUS = 'A' OR DATEDIFF(m, RESIGN_DATE, :to_dt) <= 0)
        """), {"to_dt": to_dt, "bcd": bcd}).mappings().all()

        sub_all = db.session.execute(text("""
            SELECT EMPLOYEE_ID, FULLNAME, SUPERIOR,
                   CASE WHEN DATEDIFF(m, RESIGN_DATE, :to_dt) = 0 THEN 'red' ELSE '' END AS warna
            FROM APP_USRMST WITH(NOLOCK)
            WHERE ACCESSCAM = 'CMO' AND BRANCHCODE = :bcd
                AND SUPERIOR IS NOT NULL AND SUPERIOR <> ''
                AND (RECSTATUS = 'A' OR DATEDIFF(m, RESIGN_DATE, :to_dt) <= 0)
        """), {"to_dt": to_dt, "bcd": bcd}).mappings().all()

        subs_by_superior: dict[str, list] = {}
        for row in sub_all:
            subs_by_superior.setdefault(row["SUPERIOR"], []).append(row)

        for top in top_rows:
            emp_id   = top["EMPLOYEE_ID"]
            is_cmh   = top["cmh"] == "1"
            resigned = top["warna"] == "red"

            if not is_cmh:
                cmo_count       += 1
                grand_cmo_count += 1

            emp = _build_employee(emp_id, top["FULLNAME"], no, is_cmh,
                                  resigned, to_dt, working_days, dates)
            employees.append(emp)
            for i, c in enumerate(emp["daily_counts"]):
                day_totals[i] += c
            branch_total += emp["total"]
            no += 1

            for sub in subs_by_superior.get(emp_id, []):
                sid       = sub["EMPLOYEE_ID"]
                s_resigned = sub["warna"] == "red"
                cmo_count       += 1
                grand_cmo_count += 1

                s_emp = _build_employee(sid, sub["FULLNAME"], no, False,
                                        s_resigned, to_dt, working_days, dates)
                employees.append(s_emp)
                for i, c in enumerate(s_emp["daily_counts"]):
                    day_totals[i] += c
                branch_total += s_emp["total"]
                no += 1

        if not employees:
            continue

        branch_avg = round(branch_total / working_days, 2) if working_days else 0
        for i, t in enumerate(day_totals):
            grand_day_totals[i] += t
        grand_total += branch_total

        branches_out.append({
            "branch_cd": bcd, "branch_name": bname,
            "cmo_count": cmo_count, "employees": employees,
            "day_totals": day_totals, "branch_total": branch_total,
            "branch_avg": branch_avg,
        })

    grand_avg = round(grand_total / working_days, 2) if working_days else 0

    return {
        "asof":             date(tahun, bulan, 1).strftime("%B %Y"),
        "working_days":     working_days,
        "to_date":          to_dt,
        "dates":            dates,
        "branches":         branches_out,
        "grand_day_totals": grand_day_totals,
        "grand_total":      grand_total,
        "grand_avg":        grand_avg,
        "grand_cmo_count":  grand_cmo_count,
        "company_name":     get_company_name(),
        "printed_by":       _username(),
    }

_THIN    = Side(style="thin", color="000000")
_BORDER  = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_CENTER  = Alignment(horizontal="center", vertical="center")
_LEFT    = Alignment(horizontal="left",   vertical="center")
_SPAN    = Alignment(horizontal="centerContinuous", vertical="center")
_F_BOLD  = Font(name="Tahoma", size=9, bold=True)
_F_DATA  = Font(name="Tahoma", size=9)
_FILL_HDR     = PatternFill("solid", fgColor="F2F2F2")
_FILL_BRANCH  = PatternFill("solid", fgColor="DBEAFE")
_FILL_HOLIDAY = PatternFill("solid", fgColor="FFCCCC")
_FILL_CMH     = PatternFill("solid", fgColor="89CFF0")
_FILL_TOTAL   = PatternFill("solid", fgColor="F3F4F6")
_FILL_GRAND   = PatternFill("solid", fgColor="E5E7EB")
_AVG_FMT = "#,##0.00"

def _cell(ws, row, col, value=None, font=None, align=None, fill=None, fmt=None, border=True):
    c = ws.cell(row=row, column=col, value=value)
    c.font = font or _F_DATA
    c.alignment = align or _CENTER
    if border: c.border = _BORDER
    if fill:   c.fill = fill
    if fmt:    c.number_format = fmt
    return c

def _build_workbook(payload: dict) -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "CMOProductivity"

    dates    = payload["dates"]
    num_days = len(dates)
    n_cols   = num_days + 4
    last     = get_column_letter(n_cols)
    col_tot  = num_days + 3
    col_avg  = num_days + 4

    _cell(ws, 1, 1, payload["company_name"], align=_LEFT, border=False)
    _cell(ws, 1, n_cols, f"Date : {today_ddmmyyyy()}\nPrint By : {payload['printed_by']}",
          align=WRAP_TOP_LEFT, border=False)
    ws.row_dimensions[1].height = 30

    ws.merge_cells(f"A2:{last}2")
    _cell(ws, 2, 1, "CMO PRODUCTIVITY", font=title_font(16), align=_CENTER, border=False)
    ws.row_dimensions[2].height = 24

    ws.merge_cells(f"A3:{last}3")
    _cell(ws, 3, 1, f"Approval Date : {payload['asof']}", font=_F_BOLD, align=_CENTER, border=False)

    ws.merge_cells(f"A4:{last}4")
    _cell(ws, 4, 1, f"({payload['working_days']} Working Days)", align=_CENTER, border=False)

    if not num_days:
        return wb

    r = 6
    for branch in payload["branches"]:
        for col in range(1, n_cols + 1):
            _cell(ws, r, col, None, font=_F_BOLD, align=_SPAN, fill=_FILL_BRANCH)
        _cell(ws, r, 1, "No.",     font=_F_BOLD, align=_CENTER, fill=_FILL_HDR)
        _cell(ws, r, 2, "Name",    font=_F_BOLD, align=_CENTER, fill=_FILL_HDR)
        ws.cell(row=r, column=3).value = branch["branch_name"]
        _cell(ws, r, col_tot, "Total",   font=_F_BOLD, align=_CENTER, fill=_FILL_HDR)
        _cell(ws, r, col_avg, "Avg/Day", font=_F_BOLD, align=_CENTER, fill=_FILL_HDR)
        r += 1

        _cell(ws, r, 1, None, fill=_FILL_HDR)
        _cell(ws, r, 2, None, fill=_FILL_HDR)
        for i, d in enumerate(dates):
            _cell(ws, r, 3 + i, int(d["day_num"]), font=_F_BOLD,
                  fill=_FILL_HOLIDAY if d["is_holiday"] else _FILL_HDR)
        _cell(ws, r, col_tot, None, fill=_FILL_HDR)
        _cell(ws, r, col_avg, None, fill=_FILL_HDR)
        r += 1

        for emp in branch["employees"]:
            row_fill = _FILL_CMH if emp["is_cmh"] else None
            name_font = Font(name="Tahoma", size=9, bold=emp["is_cmh"],
                             color="FF0000" if emp["name_color"] == "red" else "000000")
            _cell(ws, r, 1, emp["no"], fill=row_fill)
            _cell(ws, r, 2, emp["fullname"], font=name_font, align=_LEFT, fill=row_fill)
            for i, count in enumerate(emp["daily_counts"]):
                _cell(ws, r, 3 + i, count or None,
                      fill=_FILL_HOLIDAY if dates[i]["is_holiday"] else row_fill)
            _cell(ws, r, col_tot, emp["total"], font=_F_BOLD, fill=row_fill)
            _cell(ws, r, col_avg, emp["avg_per_day"], fill=row_fill, fmt=_AVG_FMT)
            r += 1

        _cell(ws, r, 1, branch["cmo_count"], font=_F_BOLD, fill=_FILL_TOTAL)
        _cell(ws, r, 2, "Total", font=_F_BOLD, align=_LEFT, fill=_FILL_TOTAL)
        for i, t in enumerate(branch["day_totals"]):
            _cell(ws, r, 3 + i, t or None, font=_F_BOLD,
                  fill=_FILL_HOLIDAY if dates[i]["is_holiday"] else _FILL_TOTAL)
        _cell(ws, r, col_tot, branch["branch_total"], font=_F_BOLD, fill=_FILL_TOTAL)
        _cell(ws, r, col_avg, branch["branch_avg"], font=_F_BOLD, fill=_FILL_TOTAL, fmt=_AVG_FMT)
        r += 2

    _cell(ws, r, 1, payload["grand_cmo_count"], font=_F_BOLD, fill=_FILL_GRAND)
    _cell(ws, r, 2, "Grand Total", font=_F_BOLD, align=_LEFT, fill=_FILL_GRAND)
    for i, t in enumerate(payload["grand_day_totals"]):
        _cell(ws, r, 3 + i, t or None, font=_F_BOLD,
              fill=_FILL_HOLIDAY if dates[i]["is_holiday"] else _FILL_GRAND)
    _cell(ws, r, col_tot, payload["grand_total"], font=_F_BOLD, fill=_FILL_GRAND)
    _cell(ws, r, col_avg, payload["grand_avg"], font=_F_BOLD, fill=_FILL_GRAND, fmt=_AVG_FMT)

    ws.column_dimensions["A"].width = 5
    ws.column_dimensions["B"].width = 26
    for i in range(num_days):
        ws.column_dimensions[get_column_letter(3 + i)].width = 4.5
    ws.column_dimensions[get_column_letter(col_tot)].width = 8
    ws.column_dimensions[get_column_letter(col_avg)].width = 9
    ws.freeze_panes = "C6"

    return wb

@monthly_summary_cam_approved_bp.route("/MonthlySummaryCAMApproved/data")
@login_required
def get_data():

    try:
        bulan = int(request.args.get("bulan", date.today().month))
        tahun = int(request.args.get("tahun", date.today().year))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid params"}), 400

    try:
        return jsonify(_build_payload(bulan, tahun))
    except ValueError:
        return jsonify({"error": "Invalid params"}), 400
    except Exception:
        current_app.logger.exception("CMO Productivity error")
        return jsonify({"error": "Failed to load data"}), 500

@monthly_summary_cam_approved_bp.route("/MonthlySummaryCAMApproved/excel")
@login_required
def export_excel():

    try:
        bulan = int(request.args.get("bulan", date.today().month))
        tahun = int(request.args.get("tahun", date.today().year))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid params"}), 400

    try:
        payload = _build_payload(bulan, tahun)
    except ValueError:
        return jsonify({"error": "Invalid params"}), 400
    except Exception:
        current_app.logger.exception("CMO Productivity data error")
        return jsonify({"error": "Failed to load data"}), 500

    try:
        return workbook_response(_build_workbook(payload), "SummaryCAMbyCMO.xlsx")
    except Exception:
        current_app.logger.exception("CMO Productivity Excel export error")
        return jsonify({"error": "Failed to generate Excel"}), 500