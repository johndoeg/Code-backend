from flask import Blueprint, jsonify, request, current_app
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text
import calendar

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.utils import get_column_letter

from app.utils.helpers.base_format import (
    WRAP_TOP_LEFT,
    _username,
    title_font,
    today_ddmmyyyy,
    workbook_response,
)
from app.utils.helpers.settings_helpers import company_name as get_company_name

laporan_pelunasan_bp = Blueprint("laporan_pelunasan", __name__, url_prefix="/CAM/Others")

_MONTHS_ID = ["","Januari","Februari","Maret","April","Mei","Juni",
               "Juli","Agustus","September","Oktober","November","Desember"]

_SUMMARY_SQL = text("""
    SELECT a.BRANCH_CD, a.BRANCH_NAME,
           ISNULL(b.unit_new, 0) AS unit_new,
           ISNULL(b.nf_new,   0) AS nf_new,
           ISNULL(c.unit_used,0) AS unit_used,
           ISNULL(c.nf_used,  0) AS nf_used
    FROM UMFBRANCH a WITH(NOLOCK)
        LEFT JOIN (
            SELECT a.BRANCH_CD,
                SUM(e.unit)          AS unit_new,
                SUM(b.Net_Finance)   AS nf_new
            FROM clfcont a WITH(NOLOCK)
                INNER JOIN V_NetFinance b WITH(NOLOCK) ON a.LEASE_NO = b.LEASE_NO
                INNER JOIN (
                    SELECT LEASE_NO, COUNT(*) AS unit
                    FROM CLFEQUIP WITH(NOLOCK)
                    WHERE FLGDEL = 0 AND CONDITION = 'NEW'
                    GROUP BY LEASE_NO
                ) e ON a.LEASE_NO = e.LEASE_NO
            WHERE a.EXECUTION BETWEEN :from1 AND :to1
            GROUP BY a.BRANCH_CD
        ) b ON a.BRANCH_CD = b.BRANCH_CD
        LEFT JOIN (
            SELECT a.BRANCH_CD,
                SUM(e.unit)          AS unit_used,
                SUM(b.Net_Finance)   AS nf_used
            FROM clfcont a WITH(NOLOCK)
                INNER JOIN V_NetFinance b WITH(NOLOCK) ON a.LEASE_NO = b.LEASE_NO
                INNER JOIN (
                    SELECT LEASE_NO, COUNT(*) AS unit
                    FROM CLFEQUIP WITH(NOLOCK)
                    WHERE FLGDEL = 0 AND CONDITION = 'USED'
                    GROUP BY LEASE_NO
                ) e ON a.LEASE_NO = e.LEASE_NO
            WHERE a.EXECUTION BETWEEN :from1 AND :to1
            GROUP BY a.BRANCH_CD
        ) c ON a.BRANCH_CD = c.BRANCH_CD
    WHERE a.BRANCH_CD NOT IN ('000','100')
    ORDER BY a.BRANCH_CD
""")

_DETAIL_SQL = text("""
    SELECT a.BRANCH_CD,
           a.APPL_NO, a.LEASE_NO,
           b.LESSEE_NM,
           c.Net_Finance,
           ISNULL(e.unit, 0) AS unit,
           a.EXECUTION,
           d.Employee_fullname
    FROM CLFCONT a WITH(NOLOCK)
            INNER JOIN CLFLESS        b WITH(NOLOCK) ON a.LESSEE_NO = b.LESSEE_NO
            INNER JOIN V_NetFinance   c WITH(NOLOCK) ON a.LEASE_NO  = c.LEASE_NO
            INNER JOIN EMPLOYEE_DATA  d WITH(NOLOCK) ON a.CMO        = d.Employee_ID
            INNER JOIN (
                SELECT LEASE_NO, COUNT(*) AS unit, Condition
                FROM CLFEQUIP WITH(NOLOCK)
                WHERE FLGDEL = 0
                GROUP BY LEASE_NO, Condition
            ) e ON a.LEASE_NO = e.LEASE_NO AND e.Condition = :condition
    WHERE a.EXECUTION BETWEEN :from1 AND :to1
        AND a.BRANCH_CD NOT IN ('000','100')
    ORDER BY a.BRANCH_CD, a.EXECUTION
""")

def _date_range(bulan: str, tahun: str) -> tuple[str, str]:
    m, y    = int(bulan), int(tahun)
    last    = calendar.monthrange(y, m)[1]
    return f"{y}-{m:02d}-01", f"{y}-{m:02d}-{last:02d}"

def _group_detail(rows, branch_order: list[dict]) -> list[dict]:
   
    contracts_by_branch: dict[str, list] = {}
    for r in rows:
        bc = r["BRANCH_CD"]
        if bc not in contracts_by_branch:
            contracts_by_branch[bc] = []
        exec_ = r["EXECUTION"]
        contracts_by_branch[bc].append({
            "appl_no":          r["APPL_NO"]           or "",
            "lease_no":         r["LEASE_NO"]           or "",
            "lessee_nm":        r["LESSEE_NM"]          or "",
            "net_finance":      float(r["Net_Finance"])  if r["Net_Finance"] else 0.0,
            "unit":             int(r["unit"])           if r["unit"]        else 0,
            "execution":        exec_.strftime("%Y-%m-%d") if exec_ else None,
            "employee_fullname": r["Employee_fullname"] or "",
        })

    return [
        {
            "branch_cd":   b["branch_cd"],
            "branch_name": b["branch_name"],
            "contracts":   contracts_by_branch[b["branch_cd"]],
        }
        for b in branch_order
        if contracts_by_branch.get(b["branch_cd"])
    ]

def _fmt_date(s) -> str:
    if not s:
        return ""
    y, m, d = str(s).split("-")
    return f"{d}-{m}-{y}"

def _build_payload(bulan: str, tahun: str) -> dict:
    from1, to1 = _date_range(bulan, tahun)
    params     = {"from1": from1, "to1": to1}

    summary_rows = db.session.execute(_SUMMARY_SQL, params).mappings().all()

    summary = []
    tot_new = tot_used = 0
    tot_nf_new = tot_nf_used = 0.0

    for r in summary_rows:
        un  = int(r["unit_new"]  or 0)
        nfn = float(r["nf_new"]  or 0)
        uu  = int(r["unit_used"] or 0)
        nfu = float(r["nf_used"] or 0)

        summary.append({
            "branch_name": r["BRANCH_NAME"] or "",
            "unit_new":  un,
            "nf_new":    nfn,
            "unit_used": uu,
            "nf_used":   nfu,
        })
        tot_new     += un
        tot_nf_new  += nfn
        tot_used    += uu
        tot_nf_used += nfu

    branch_order = [
        {"branch_cd": r["BRANCH_CD"], "branch_name": r["BRANCH_NAME"] or ""}
        for r in summary_rows
    ]

    new_rows  = db.session.execute(_DETAIL_SQL, {**params, "condition": "NEW"}).mappings().all()
    used_rows = db.session.execute(_DETAIL_SQL, {**params, "condition": "USED"}).mappings().all()

    return {
        "month_name":  _MONTHS_ID[int(bulan)],
        "totals": {
            "tot_new":     tot_new,
            "tot_nf_new":  tot_nf_new,
            "tot_used":    tot_used,
            "tot_nf_used": tot_nf_used,
        },
        "summary":      summary,
        "detail_new":   _group_detail(new_rows,  branch_order),
        "detail_used":  _group_detail(used_rows, branch_order),
        "company_name": get_company_name(),
        "printed_by":   _username(),
    }

_THIN    = Side(style="thin", color="000000")
_BORDER  = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_CENTER  = Alignment(horizontal="center", vertical="center", wrap_text=True)
_LEFT    = Alignment(horizontal="left",   vertical="center")
_SPAN    = Alignment(horizontal="centerContinuous", vertical="center")
_RIGHT   = Alignment(horizontal="right",  vertical="center")
_F_BOLD  = Font(name="Tahoma", size=10, bold=True)
_F_DATA  = Font(name="Tahoma", size=10)
_NUM_FMT = "#,##0"
_PCT_FMT = "#,##0.00"
_COLS    = 11

_DETAIL_HEADERS = ["No.", "No. CAM", "No. Kontrak", "Nama Customer", "Net Finance",
                   "Total Unit", "Tanggal Pelunasan", "CMO", "Keterangan"]

def _pct(unit: float, total: float) -> float:
    return 0.0 if not total else round(unit / total * 100, 2)

def _put(ws, row, col, value, font=None, align=None, border=False, fmt=None):
    c = ws.cell(row=row, column=col, value=value)
    c.font = font or _F_DATA
    if align:  c.alignment = align
    if border: c.border = _BORDER
    if fmt:    c.number_format = fmt
    return c

def _build_workbook(payload: dict, tahun: str) -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "LaporanPelunasan"

    last = get_column_letter(_COLS)
    totals = payload["totals"]
    tot_all    = totals["tot_new"] + totals["tot_used"]
    tot_nf_all = totals["tot_nf_new"] + totals["tot_nf_used"]

    _put(ws, 1, 1, payload["company_name"])
    _put(ws, 1, _COLS, f"Date : {today_ddmmyyyy()}\nPrint By : {payload['printed_by']}",
         align=WRAP_TOP_LEFT)
    ws.row_dimensions[1].height = 30

    ws.merge_cells(f"A2:{last}2")
    _put(ws, 2, 1, "LAPORAN PELUNASAN MOBIL BARU DAN BEKAS", font=title_font(16), align=_CENTER)
    ws.row_dimensions[2].height = 24

    ws.merge_cells(f"A3:{last}3")
    _put(ws, 3, 1, f"Periode : {payload['month_name']} {tahun}", align=_CENTER)

    r = 5
    for col in range(1, _COLS + 1):
        _put(ws, r, col, None, font=_F_BOLD, align=_SPAN, border=True)
    ws.cell(row=r, column=1).value = "NEW CAR"
    ws.cell(row=r, column=6).value = "USED CAR"

    r += 1
    for col, h in enumerate(["MONTH", "BRANCH", "NET FINANCE", "UNIT", "Persentase",
                             "MONTH", "BRANCH", "NET FINANCE", "UNIT", "Persentase",
                             "Jumlah"], 1):
        _put(ws, r, col, h, font=_F_BOLD, align=_CENTER, border=True)

    for i, row in enumerate(payload["summary"]):
        r += 1
        period = payload["month_name"] if i == 0 else ""
        _put(ws, r, 1,  period,            align=_CENTER, border=True)
        _put(ws, r, 2,  row["branch_name"], align=_LEFT,   border=True)
        _put(ws, r, 3,  row["nf_new"],      align=_RIGHT,  border=True, fmt=_NUM_FMT)
        _put(ws, r, 4,  row["unit_new"],    align=_CENTER, border=True, fmt=_NUM_FMT)
        _put(ws, r, 5,  _pct(row["unit_new"], tot_all),  align=_CENTER, border=True, fmt=_PCT_FMT)
        _put(ws, r, 6,  period,            align=_CENTER, border=True)
        _put(ws, r, 7,  row["branch_name"], align=_LEFT,   border=True)
        _put(ws, r, 8,  row["nf_used"],     align=_RIGHT,  border=True, fmt=_NUM_FMT)
        _put(ws, r, 9,  row["unit_used"],   align=_CENTER, border=True, fmt=_NUM_FMT)
        _put(ws, r, 10, _pct(row["unit_used"], tot_all), align=_CENTER, border=True, fmt=_PCT_FMT)
        _put(ws, r, 11, row["unit_new"] + row["unit_used"], align=_CENTER, border=True, fmt=_NUM_FMT)

    r += 1
    _put(ws, r, 1,  None,                      border=True)
    _put(ws, r, 2,  "TOTAL",                   font=_F_BOLD, align=_CENTER, border=True)
    _put(ws, r, 3,  totals["tot_nf_new"],      font=_F_BOLD, align=_RIGHT,  border=True, fmt=_NUM_FMT)
    _put(ws, r, 4,  totals["tot_new"],         font=_F_BOLD, align=_CENTER, border=True, fmt=_NUM_FMT)
    _put(ws, r, 5,  _pct(totals["tot_new"], tot_all),  font=_F_BOLD, align=_CENTER, border=True, fmt=_PCT_FMT)
    _put(ws, r, 6,  None,                      border=True)
    _put(ws, r, 7,  "TOTAL",                   font=_F_BOLD, align=_CENTER, border=True)
    _put(ws, r, 8,  totals["tot_nf_used"],     font=_F_BOLD, align=_RIGHT,  border=True, fmt=_NUM_FMT)
    _put(ws, r, 9,  totals["tot_used"],        font=_F_BOLD, align=_CENTER, border=True, fmt=_NUM_FMT)
    _put(ws, r, 10, _pct(totals["tot_used"], tot_all), font=_F_BOLD, align=_CENTER, border=True, fmt=_PCT_FMT)
    _put(ws, r, 11, tot_all,                   font=_F_BOLD, align=_CENTER, border=True, fmt=_NUM_FMT)

    r += 2
    for col in (1, 2):
        _put(ws, r, col, None, font=_F_BOLD, align=_SPAN, border=True)
        _put(ws, r + 1, col, None, border=True)
    ws.cell(row=r, column=1).value = "Total Mobil Baru dan Bekas"
    _put(ws, r, 3, "Net Finance", font=_F_BOLD, align=_CENTER, border=True)
    _put(ws, r, 4, "Unit",        font=_F_BOLD, align=_CENTER, border=True)
    _put(ws, r + 1, 3, tot_nf_all, font=_F_BOLD, align=_RIGHT,  border=True, fmt=_NUM_FMT)
    _put(ws, r + 1, 4, tot_all,    font=_F_BOLD, align=_CENTER, border=True, fmt=_NUM_FMT)
    r += 2

    def _section(start: int, title: str, details: list) -> int:
        row = start + 1
        _put(ws, row, 1, title, font=title_font(12), align=_CENTER)
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=9)
        row += 1

        for branch in details:
            for col in range(1, 10):
                _put(ws, row, col, None, font=_F_BOLD, align=_SPAN, border=True)
            ws.cell(row=row, column=1).value = branch["branch_name"].upper()
            row += 1

            for col, h in enumerate(_DETAIL_HEADERS, 1):
                _put(ws, row, col, h, font=_F_BOLD, align=_CENTER, border=True)
            row += 1

            tot_unit = 0
            tot_nf   = 0.0
            for i, c in enumerate(branch["contracts"], 1):
                tot_unit += c["unit"]
                tot_nf   += c["net_finance"]
                _put(ws, row, 1, i,                   align=_CENTER, border=True)
                _put(ws, row, 2, c["appl_no"],        align=_LEFT,   border=True)
                _put(ws, row, 3, c["lease_no"],       align=_LEFT,   border=True)
                _put(ws, row, 4, c["lessee_nm"],      align=_LEFT,   border=True)
                _put(ws, row, 5, c["net_finance"],    align=_RIGHT,  border=True, fmt=_NUM_FMT)
                _put(ws, row, 6, c["unit"],           align=_CENTER, border=True, fmt=_NUM_FMT)
                _put(ws, row, 7, _fmt_date(c["execution"]), align=_CENTER, border=True)
                _put(ws, row, 8, c["employee_fullname"], align=_LEFT, border=True)
                _put(ws, row, 9, None,                border=True)
                row += 1

            for col in (1, 2, 3, 4, 7, 8, 9):
                _put(ws, row, col, None, border=True)
            _put(ws, row, 5, tot_nf,   font=_F_BOLD, align=_RIGHT,  border=True, fmt=_NUM_FMT)
            _put(ws, row, 6, tot_unit, font=_F_BOLD, align=_CENTER, border=True, fmt=_NUM_FMT)
            row += 2

        return row

    r = _section(r, "Data Customer Pelunasan Mobil Baru", payload["detail_new"])
    _section(r, "Data Customer Pelunasan Mobil Bekas", payload["detail_used"])

    for col, width in enumerate([12, 24, 20, 30, 18, 10, 16, 24, 14, 12, 10], 1):
        ws.column_dimensions[get_column_letter(col)].width = width

    return wb

@laporan_pelunasan_bp.route("/LaporanPelunasan/data")
@login_required
def get_data():

    bulan = request.args.get("bulan", "").strip()
    tahun = request.args.get("tahun", "").strip()

    if not bulan or not tahun:
        return jsonify({"error": "bulan and tahun are required"}), 400

    try:
        payload = _build_payload(bulan, tahun)
    except (ValueError, IndexError, KeyError):
        return jsonify({"error": "Invalid bulan or tahun"}), 400
    except Exception:
        current_app.logger.exception("Laporan Pelunasan data fetch error")
        return jsonify({"error": "Failed to load data"}), 500

    return jsonify(payload)

@laporan_pelunasan_bp.route("/LaporanPelunasan/excel")
@login_required
def export_excel():

    bulan = request.args.get("bulan", "").strip()
    tahun = request.args.get("tahun", "").strip()

    if not bulan or not tahun:
        return jsonify({"error": "bulan and tahun are required"}), 400

    try:
        payload = _build_payload(bulan, tahun)
    except (ValueError, IndexError, KeyError):
        return jsonify({"error": "Invalid bulan or tahun"}), 400

    try:
        wb = _build_workbook(payload, tahun)
        return workbook_response(wb, "LaporanPelunasanMobil.xlsx")
    except Exception:
        current_app.logger.exception("Laporan Pelunasan Excel export error")
        return jsonify({"error": "Failed to generate Excel"}), 500