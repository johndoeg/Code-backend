from flask import Blueprint, jsonify, request, current_app
from app import db
from app.auth.decorators import login_required

from sqlalchemy import text
import calendar

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from app.utils.helpers.base_format import (
    WRAP_TOP_LEFT,
    _username,
    title_font,
    today_ddmmyyyy,
    workbook_response,
)
from app.utils.helpers.settings_helpers import company_name as get_company_name

f6pd_bp = Blueprint("f6pd", __name__, url_prefix="/CAM/Others")

_THIN   = Side(style="thin", color="000000")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_CENTER = Alignment(horizontal="center", vertical="bottom")
_LEFT   = Alignment(horizontal="left",   vertical="bottom")

_FONT_TITLE    = Font(name="Tahoma", size=12, bold=True)
_FONT_SUBTITLE = Font(name="Tahoma", size=8,  bold=True)
_FONT_DATA     = Font(name="Tahoma", size=7)
_FONT_CMH      = Font(name="Tahoma", size=7, bold=True)

_NUM_FMT = '#,##0'
_PCT_FMT = '0.00"%"'
_SPAN    = Alignment(horizontal="centerContinuous", vertical="bottom")

def _apply(cell, font=None, alignment=None, border=None, fill=None, number_format=None):
    if font:          cell.font          = font
    if alignment:     cell.alignment     = alignment
    if border:        cell.border        = border
    if fill:          cell.fill          = fill
    if number_format: cell.number_format = number_format

def _subtitle(ws, ref: str, value):
    cell = ws[ref]
    cell.value = value
    _apply(cell, font=_FONT_SUBTITLE, alignment=_CENTER, border=_BORDER)

def _span(ws, row: int, col_from: int, col_to: int, value):
    for col in range(col_from, col_to + 1):
        _apply(ws.cell(row=row, column=col), font=_FONT_SUBTITLE,
               alignment=_SPAN, border=_BORDER)
    ws.cell(row=row, column=col_from).value = value

def _sheet_header(ws, n_cols: int, title: str) -> None:
    last = get_column_letter(n_cols)
    ws["A1"].value = get_company_name()
    _apply(ws["A1"], font=_FONT_DATA, alignment=_LEFT)
    ws[f"{last}1"].value = f"Date : {today_ddmmyyyy()}\nPrint By : {_username()}"
    _apply(ws[f"{last}1"], font=_FONT_DATA, alignment=WRAP_TOP_LEFT)
    ws.row_dimensions[1].height = 30

    ws.merge_cells(f"A2:{last}2")
    ws["A2"].value = title
    _apply(ws["A2"], font=title_font(16),
           alignment=Alignment(horizontal="center", vertical="center"))
    ws.row_dimensions[2].height = 24

def _period(bulan: str, tahun: str) -> tuple[str, str]:
    bulan, tahun = str(bulan).strip(), str(tahun).strip()
    if not (1 <= int(bulan) <= 12):
        raise ValueError("bulan out of range")
    last = calendar.monthrange(int(tahun), int(bulan))[1]
    p1   = f"{tahun}-{bulan.zfill(2)}-{last:02d}"
    fmt  = f"{last:02d}-{bulan.zfill(2)}-{tahun}"
    return p1, fmt

def _pct(num: float, denom: float) -> float:
    return 0.0 if denom == 0 else round(num / denom * 100, 2)

def _exec_f6pd(emp_id: str, period1: str, mode: str) -> dict | None:
    try:
        row = db.session.execute(
            text("EXEC USP_F6PD_REPORT :eid, :p, :m"),
            {"eid": emp_id, "p": period1, "m": mode},
        ).mappings().first()
        return dict(row) if row else None
    except Exception:
        return None

def _build_summary_row(r: dict) -> dict:
    u1 = int(r.get("unit1") or 0)
    u2 = int(r.get("unit2") or 0)
    o1 = float(r.get("op1")  or 0)
    o2 = float(r.get("op2")  or 0)
    tu = u1 + u2
    to = o1 + o2
    return dict(unit1=u1, unit2=u2, tot_unit=tu, pd_unit=_pct(u2, tu),
                op1=o1,   op2=o2,   tot_op=to,   pd_op=_pct(o2, to))

def _fetch_all(bulan: str, tahun: str) -> dict:
    period1, formatted_date = _period(bulan, tahun)

    cmh_rows = db.session.execute(text("""
        SELECT DISTINCT ISNULL(a.SUPERIOR, '') AS employee_id,
               ISNULL(b.FULLNAME, 'No CMH') AS fullname
        FROM app_usrmst a WITH(NOLOCK)
            LEFT JOIN APP_USRMST b WITH(NOLOCK) ON a.SUPERIOR = b.EMPLOYEE_ID
        WHERE a.ACCESSCAM = 'CMO' AND a.RECSTATUS = 'A'
        ORDER BY fullname
    """)).mappings().all()

    cmo_all = db.session.execute(text("""
        SELECT EMPLOYEE_ID, FULLNAME, ISNULL(SUPERIOR, '') AS SUPERIOR
        FROM app_usrmst WITH(NOLOCK)
        WHERE ACCESSCAM = 'CMO' AND RECSTATUS = 'A'
        ORDER BY FULLNAME
    """)).mappings().all()

    cmo_by_superior: dict[str, list] = {}
    for row in cmo_all:
        cmo_by_superior.setdefault(row["SUPERIOR"], []).append(row)

    summary_cmo = []
    for cmh in cmh_rows:
        cmh_id, cmh_name = cmh["employee_id"] or "", cmh["fullname"]

        r = _exec_f6pd(cmh_id, period1, "CMH")
        if r:
            row = _build_summary_row(r)
            summary_cmo.append({"fullname": cmh_name, "is_cmh": True, **row})

        for cmo in cmo_by_superior.get(cmh_id, []):
            r = _exec_f6pd(cmo["EMPLOYEE_ID"], period1, "CMO")
            if r:
                row = _build_summary_row(r)
                summary_cmo.append({"fullname": cmo["FULLNAME"] or "", "is_cmh": False, **row})

    bulan_rows = db.session.execute(
        text("EXEC USP_F6PD_REPORT '', :p, 'BULAN'"), {"p": period1}
    ).mappings().all()
    summary_monthly = []
    for b in bulan_rows:
        row = _build_summary_row(b)
        summary_monthly.append({"bulan": b.get("bulan") or "", **row})

    raw_rows = db.session.execute(
        text("EXEC USP_F6PD_REPORT '', :p, 'RAW'"), {"p": period1}
    ).mappings().all()
    raw_data = [{
        "lease_no":   r.get("lease_no")   or "",
        "lessee_nm":  r.get("LESSEE_NM")  or "",
        "od":         int(r.get("od")     or 0),
        "outs_princ": float(r.get("outs_princ") or 0),
        "cmo":        r.get("CMO")        or "",
    } for r in raw_rows]

    return dict(formatted_date=formatted_date, period1=period1,
                summary_cmo=summary_cmo, summary_monthly=summary_monthly,
                raw_data=raw_data)

def _build_excel(d: dict) -> Workbook:
    wb = Workbook()

    ws1 = wb.active
    ws1.title = "Summary"

    _sheet_header(ws1, 9, f"F6PD REPORT AS OF {d['formatted_date']}")

    _subtitle(ws1, "A4", "CMO")
    _subtitle(ws1, "A5", None)
    _span(ws1, 4, 2, 5, "By Unit")
    _span(ws1, 4, 6, 9, "By Amount")
    for ref, val in [("B5","<= 30 DAYS"),("C5","> 30 DAYS"),("D5","GRAND TOTAL"),("E5","F6PD"),
                     ("F5","<= 30 DAYS"),("G5","> 30 DAYS"),("H5","GRAND TOTAL"),("I5","F6PD")]:
        _subtitle(ws1, ref, val)

    col_widths = {"A":25,"B":15,"C":15,"D":15,"E":15,"F":15,"G":15,"H":15,"I":15}
    for col, w in col_widths.items():
        ws1.column_dimensions[col].width = w

    row_i = 6
    for emp in d["summary_cmo"]:
        font = _FONT_CMH if emp["is_cmh"] else _FONT_DATA
        ws1[f"A{row_i}"].value = emp["fullname"]
        _apply(ws1[f"A{row_i}"], font=font, border=_BORDER)
        for col, key in [("B","unit1"),("C","unit2"),("D","tot_unit"),("E","pd_unit")]:
            c = ws1[f"{col}{row_i}"]
            c.value = emp[key]
            _apply(c, font=font, border=_BORDER, alignment=_CENTER,
                   number_format=_PCT_FMT if key == "pd_unit" else None)
        for col, key in [("F","op1"),("G","op2"),("H","tot_op")]:
            c = ws1[f"{col}{row_i}"]
            c.value = emp[key];  _apply(c, font=font, border=_BORDER,
                                        alignment=_CENTER, number_format=_NUM_FMT)
        c = ws1[f"I{row_i}"]
        c.value = emp["pd_op"]
        _apply(c, font=font, border=_BORDER, alignment=_CENTER, number_format=_PCT_FMT)
        row_i += 1

    j, k = row_i + 1, row_i + 2
    _subtitle(ws1, f"A{j}", "MONTH-YEAR")
    _subtitle(ws1, f"A{k}", None)
    _span(ws1, j, 2, 5, "By Unit")
    _span(ws1, j, 6, 9, "By Amount")
    for ref, val in [(f"B{k}","<= 30 DAYS"),(f"C{k}","> 30 DAYS"),(f"D{k}","GRAND TOTAL"),(f"E{k}","F6PD"),
                     (f"F{k}","<= 30 DAYS"),(f"G{k}","> 30 DAYS"),(f"H{k}","GRAND TOTAL"),(f"I{k}","F6PD")]:
        _subtitle(ws1, ref, val)

    row_l = k + 1
    for m in d["summary_monthly"]:
        ws1[f"A{row_l}"].value = m["bulan"]
        _apply(ws1[f"A{row_l}"], font=_FONT_DATA, border=_BORDER)
        for col, key in [("B","unit1"),("C","unit2"),("D","tot_unit"),("E","pd_unit")]:
            c = ws1[f"{col}{row_l}"]
            c.value = m[key]
            _apply(c, font=_FONT_DATA, border=_BORDER, alignment=_CENTER,
                   number_format=_PCT_FMT if key == "pd_unit" else None)
        for col, key in [("F","op1"),("G","op2"),("H","tot_op")]:
            c = ws1[f"{col}{row_l}"]
            c.value = m[key]; _apply(c, font=_FONT_DATA, border=_BORDER,
                                     alignment=_CENTER, number_format=_NUM_FMT)
        c = ws1[f"I{row_l}"]
        c.value = m["pd_op"]
        _apply(c, font=_FONT_DATA, border=_BORDER, alignment=_CENTER, number_format=_PCT_FMT)
        row_l += 1

    ws2 = wb.create_sheet("Raw Data")

    _sheet_header(ws2, 5, f"F6PD REPORT AS OF {d['formatted_date']}")

    for ref, val in [("A4","Contract No."),("B4","Customer Name"),
                     ("C4","OD Days"),("D4","Outstanding Principal"),("E4","CMO")]:
        _subtitle(ws2, ref, val)

    for col, w in {"A":25,"B":30,"C":12,"D":20,"E":20}.items():
        ws2.column_dimensions[col].width = w

    row_m = 5
    for r in d["raw_data"]:
        ws2[f"A{row_m}"].value = r["lease_no"]
        ws2[f"B{row_m}"].value = r["lessee_nm"]
        ws2[f"C{row_m}"].value = r["od"]
        ws2[f"D{row_m}"].value = r["outs_princ"]
        ws2[f"E{row_m}"].value = r["cmo"]
        _apply(ws2[f"A{row_m}"], font=_FONT_DATA, border=_BORDER)
        _apply(ws2[f"B{row_m}"], font=_FONT_DATA, border=_BORDER)
        _apply(ws2[f"C{row_m}"], font=_FONT_DATA, border=_BORDER, alignment=_CENTER)
        _apply(ws2[f"D{row_m}"], font=_FONT_DATA, border=_BORDER,
               alignment=_CENTER, number_format=_NUM_FMT)
        _apply(ws2[f"E{row_m}"], font=_FONT_DATA, border=_BORDER)
        row_m += 1

    ws1.freeze_panes = "A6"
    ws2.freeze_panes = "A5"

    return wb

@f6pd_bp.route("/F6PD/data")
@login_required
def get_data():
    bulan = request.args.get("bulan_awal", "").strip()
    tahun = request.args.get("tahun_awal", "").strip()
    if not bulan or not tahun:
        return jsonify({"error": "bulan_awal and tahun_awal required"}), 400
    try:
        _period(bulan, tahun)
    except (ValueError, TypeError, calendar.IllegalMonthError):
        return jsonify({"error": "Invalid bulan_awal or tahun_awal"}), 400
    try:
        return jsonify(_fetch_all(bulan, tahun))
    except Exception:
        current_app.logger.exception("F6PD data error")
        return jsonify({"error": "Failed to load data"}), 500

@f6pd_bp.route("/F6PD/excel")
@login_required
def export_excel():
    bulan = request.args.get("bulan_awal", "").strip()
    tahun = request.args.get("tahun_awal", "").strip()
    if not bulan or not tahun:
        return jsonify({"error": "bulan_awal and tahun_awal required"}), 400
    try:
        _period(bulan, tahun)
    except (ValueError, TypeError, calendar.IllegalMonthError):
        return jsonify({"error": "Invalid bulan_awal or tahun_awal"}), 400
    try:
        d = _fetch_all(bulan, tahun)
        return workbook_response(_build_excel(d), "F6PDAging.xlsx")
    except Exception:
        current_app.logger.exception("F6PD Excel error")
        return jsonify({"error": "Failed to generate Excel"}), 500