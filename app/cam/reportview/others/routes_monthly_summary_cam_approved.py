from flask import Blueprint, jsonify, request, current_app
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text
from datetime import date, timedelta
import calendar

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

@monthly_summary_cam_approved_bp.route("/MonthlySummaryCAMApproved/data")
@login_required
def get_data():
   
    try:
        bulan = int(request.args.get("bulan", date.today().month))
        tahun = int(request.args.get("tahun", date.today().year))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid params"}), 400

    try:
        from_dt, to_dt = _date_range(bulan, tahun)

        if to_dt < from_dt:
            return jsonify({
                "asof": date(tahun, bulan, 1).strftime("%B %Y"),
                "working_days": 0, "to_date": to_dt,
                "dates": [], "branches": [],
                "grand_day_totals": [], "grand_total": 0,
                "grand_avg": 0, "grand_cmo_count": 0,
            })

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
            text("SELECT BRANCH_CD, BRANCH_NAME FROM UMFBRANCH WITH(NOLOCK) WHERE BRANCH_CD NOT IN ('000','100')")
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

                sub_rows = db.session.execute(text("""
                    SELECT EMPLOYEE_ID, FULLNAME,
                           CASE WHEN DATEDIFF(m, RESIGN_DATE, :to_dt) = 0 THEN 'red' ELSE '' END AS warna
                    FROM APP_USRMST WITH(NOLOCK)
                    WHERE ACCESSCAM = 'CMO' AND SUPERIOR = :sup AND BRANCHCODE = :bcd
                        AND (RECSTATUS = 'A' OR DATEDIFF(m, RESIGN_DATE, :to_dt) <= 0)
                """), {"to_dt": to_dt, "sup": emp_id, "bcd": bcd}).mappings().all()

                for sub in sub_rows:
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

        return jsonify({
            "asof":             date(tahun, bulan, 1).strftime("%B %Y"),
            "working_days":     working_days,
            "to_date":          to_dt,
            "dates":            dates,
            "branches":         branches_out,
            "grand_day_totals": grand_day_totals,
            "grand_total":      grand_total,
            "grand_avg":        grand_avg,
            "grand_cmo_count":  grand_cmo_count,
        })

    except Exception:
        current_app.logger.exception("CMO Productivity error")
        return jsonify({"error": "Failed to load data"}), 500