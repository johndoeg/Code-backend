import io
from datetime import datetime

from flask import Blueprint, jsonify, request, current_app, send_file
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import text

from app import db
from app.auth.decorators import login_required

deleted_dealer_report_bp = Blueprint("deleted_dealer_report_bp", __name__, url_prefix="/MasterData")

ALL_BRANCHES = "000"

DELETED_DEALER_SQL = text("""
    SELECT
        del.form_no,
        br.branch_name,
        del.supp,
        sup.[name],
        sup.[address],
        sup.created_by,
        sup.CREATE_DATE  AS create_date,
        app.fullname     AS delete_by,
        del.delete_date,
        del.reason
    FROM  clfsupp_delete del
        INNER JOIN clfsupp    sup ON sup.supp        = del.supp
        LEFT  JOIN umfbranch  br  ON br.branch_cd    = sup.branch_cd
        INNER JOIN app_usrmst app ON app.employee_id = del.delete_by
    WHERE
        (sup.branch_cd = :branch OR :branch = '000')
        AND (
            (del.supp = :lempar            AND :cekcek = '1')
            OR (sup.name LIKE :lempar_like AND :cekcek = '2')
            OR (:cekcek = '')
        )
        AND sup.flgdel = '1'
    ORDER BY sup.[name] ASC
""")

EXCEL_COLUMNS = (
    ("No.", "no", 6),
    ("Branch", "branch_name", 18),
    ("Dealer ID", "supp", 14),
    ("Dealer Name", "name", 32),
    ("Address", "address", 45),
    ("Created By", "created_by", 16),
    ("Create Date", "create_date", 13),
    ("Delete By", "delete_by", 22),
    ("Delete Date", "delete_date", 13),
    ("Reason", "reason", 40),
)
CENTERED_KEYS = {"no", "create_date", "delete_date"}

def _fmt_date(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d-%m-%Y")
    return str(value)

def _read_filters(args) -> dict:
    cekcek = args.get("cekcek", "").strip()
    return {
        "branch": args.get("branch", "").strip(),
        "cekcek": cekcek,
        "lempar": args.get("lempar", "").strip() if cekcek else "",
    }

def _query_deleted_dealers(filters: dict) -> list:
    rows = db.session.execute(
        DELETED_DEALER_SQL,
        {
            "branch": filters["branch"],
            "cekcek": filters["cekcek"],
            "lempar": filters["lempar"],
            "lempar_like": f"%{filters['lempar']}%",
        },
    )
    return [
        {
            "form_no": row.form_no or "",
            "branch_name": row.branch_name or "",
            "supp": row.supp or "",
            "name": row.name or "",
            "address": row.address or "",
            "created_by": row.created_by or "",
            "create_date": _fmt_date(row.create_date),
            "delete_by": row.delete_by or "",
            "delete_date": _fmt_date(row.delete_date),
            "reason": row.reason or "",
        }
        for row in rows
    ]

def _branch_label(branch_cd: str) -> str:
    if not branch_cd:
        return ""
    row = db.session.execute(
        text("SELECT BRANCH_NAME FROM UMFBRANCH WITH (NOLOCK) WHERE BRANCH_CD = :b"),
        {"b": branch_cd},
    ).fetchone()
    if row and (row.BRANCH_NAME or "").strip():
        return row.BRANCH_NAME.strip()
    return "Consolidate" if branch_cd == ALL_BRANCHES else branch_cd

@deleted_dealer_report_bp.route("/branches")
@login_required
def get_branches():
    branch_cd = request.args.get("branch_cd", "100")
    try:
        if branch_cd != "100":
            stmt = text(
                "SELECT BRANCH_CD, BRANCH_NAME FROM UMFBRANCH WITH (NOLOCK) "
                "WHERE BRANCH_CD = :branch_cd ORDER BY BRANCH_NAME"
            )
            params = {"branch_cd": branch_cd}
        else:
            stmt = text(
                "SELECT BRANCH_CD, BRANCH_NAME FROM UMFBRANCH WITH (NOLOCK) "
                "ORDER BY BRANCH_NAME"
            )
            params = {}

        result = db.session.execute(stmt, params)
        branches = [
            {
                "branchCd":   (row.BRANCH_CD   or "").strip(),
                "branchName": (row.BRANCH_NAME or "").strip(),
            }
            for row in result
        ]
        return jsonify({"data": branches, "total": len(branches)})

    except Exception:
        current_app.logger.exception("Branch list error")
        return jsonify({"data": [], "total": 0}), 500

@deleted_dealer_report_bp.route("/dealer-deleted-report")
@login_required
def get_dealer_deleted_report():
    try:
        data = _query_deleted_dealers(_read_filters(request.args))
        return jsonify({"data": data, "total": len(data)})
    except Exception:
        current_app.logger.exception("Dealer deleted report error")
        return jsonify({"data": [], "total": 0}), 500

@deleted_dealer_report_bp.route("/dealer-deleted-report/excel")
@login_required
def export_dealer_deleted_report():
    filters = _read_filters(request.args)
    try:
        rows = _query_deleted_dealers(filters)
        consolidate = filters["branch"] == ALL_BRANCHES
        columns = [c for c in EXCEL_COLUMNS if consolidate or c[1] != "branch_name"]
        col_count = len(columns)
        last_col = get_column_letter(col_count)

        thin = Side(style="thin", color="000000")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)
        base_font = Font(name="Tahoma", size=9)
        header_font = Font(name="Tahoma", size=9, bold=True)
        header_fill = PatternFill("solid", fgColor="F0F0F0")

        wb = Workbook()
        ws = wb.active
        ws.title = "Dealer Deleted Report"

        ws.merge_cells(f"A1:{last_col}1")
        ws["A1"] = "DEALER DELETED REPORT"
        ws["A1"].font = Font(name="Tahoma", size=14, bold=True)
        ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 22

        ws.merge_cells(f"A2:{last_col}2")
        ws["A2"] = f"As of {datetime.now().strftime('%d %b %Y')}"
        ws["A2"].font = Font(name="Tahoma", size=10)
        ws["A2"].alignment = Alignment(horizontal="center")

        ws.merge_cells(f"A4:{last_col}4")
        ws["A4"] = f"Branch : {_branch_label(filters['branch'])}"
        ws["A4"].font = Font(name="Tahoma", size=10, bold=True)

        header_row = 6
        for idx, (label, _, width) in enumerate(columns, start=1):
            cell = ws.cell(row=header_row, column=idx, value=label)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            ws.column_dimensions[get_column_letter(idx)].width = width
        ws.row_dimensions[header_row].height = 20

        if rows:
            for r_idx, row in enumerate(rows, start=1):
                excel_row = header_row + r_idx
                values = {**row, "no": r_idx}
                for c_idx, (_, key, _) in enumerate(columns, start=1):
                    cell = ws.cell(row=excel_row, column=c_idx, value=values[key])
                    cell.font = base_font
                    cell.border = border
                    cell.alignment = Alignment(
                        horizontal="center" if key in CENTERED_KEYS else "left",
                        vertical="top",
                        wrap_text=key not in CENTERED_KEYS,
                    )
            total_row = header_row + len(rows) + 2
            ws.cell(row=total_row, column=1, value=f"Total : {len(rows)} record{'s' if len(rows) != 1 else ''}").font = Font(name="Tahoma", size=9, bold=True)
            ws.auto_filter.ref = f"A{header_row}:{last_col}{header_row + len(rows)}"
        else:
            empty_row = header_row + 1
            ws.merge_cells(f"A{empty_row}:{last_col}{empty_row}")
            cell = ws.cell(row=empty_row, column=1, value="Data Not Found")
            cell.font = Font(name="Tahoma", size=10, bold=True, color="DC2626")
            cell.alignment = Alignment(horizontal="center")
            for c_idx in range(1, col_count + 1):
                ws.cell(row=empty_row, column=c_idx).border = border

        ws.freeze_panes = f"A{header_row + 1}"
        ws.print_title_rows = f"{header_row}:{header_row}"
        ws.page_setup.orientation = "landscape"
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"Dealer_Deleted_Report_{datetime.now().strftime('%Y%m%d')}.xlsx",
        )

    except Exception:
        current_app.logger.exception("Dealer deleted report excel error")
        return jsonify({"error": "Error exporting to Excel"}), 500