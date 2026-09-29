from flask import Blueprint, jsonify, request, current_app
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text
import calendar

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
            SELECT a.branch_cd,
                COUNT(a.lease_no)    AS unit_new,
                SUM(b.net_finance)   AS nf_new
            FROM clfcont a WITH(NOLOCK)
                INNER JOIN V_NetFinance b WITH(NOLOCK) ON a.LEASE_NO = b.LEASE_NO
                INNER JOIN CLFEQUIP c     WITH(NOLOCK) ON a.LEASE_NO = c.LEASE_NO AND c.FLGDEL = 0
            WHERE a.EXECUTION BETWEEN :from1 AND :to1
                AND c.CONDITION = 'NEW'
            GROUP BY a.BRANCH_CD
        ) b ON a.BRANCH_CD = b.BRANCH_CD
        LEFT JOIN (
            SELECT a.branch_cd,
                COUNT(a.lease_no)    AS unit_used,
                SUM(b.net_finance)   AS nf_used
            FROM clfcont a WITH(NOLOCK)
                INNER JOIN V_NetFinance b WITH(NOLOCK) ON a.LEASE_NO = b.LEASE_NO
                INNER JOIN CLFEQUIP c     WITH(NOLOCK) ON a.LEASE_NO = c.LEASE_NO AND c.FLGDEL = 0
            WHERE a.EXECUTION BETWEEN :from1 AND :to1
                AND c.CONDITION = 'USED'
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
            LEFT JOIN (
                SELECT LEASE_NO, COUNT(*) AS unit, Condition
                FROM CLFEQUIP WITH(NOLOCK)
                WHERE FLGDEL = '0'
                GROUP BY LEASE_NO, Condition
            ) e ON a.LEASE_NO = e.LEASE_NO
    WHERE a.EXECUTION BETWEEN :from1 AND :to1
        AND e.Condition = :condition
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
            "contracts":   contracts_by_branch.get(b["branch_cd"], []),
        }
        for b in branch_order
    ]

@laporan_pelunasan_bp.route("/LaporanPelunasan/data")
@login_required
def get_data():
   
    bulan = request.args.get("bulan", "").strip()
    tahun = request.args.get("tahun", "").strip()

    if not bulan or not tahun:
        return jsonify({"error": "bulan and tahun are required"}), 400

    try:
        from1, to1 = _date_range(bulan, tahun)
        params     = {"from1": from1, "to1": to1}

        summary_rows = db.session.execute(_SUMMARY_SQL, params).mappings().all()

        summary = []
        tot_new = tot_nf_new = tot_used = tot_nf_used = 0.0

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
            tot_new    += un
            tot_nf_new += nfn
            tot_used   += uu
            tot_nf_used += nfu

        branch_order = [
            {"branch_cd": r["BRANCH_CD"], "branch_name": r["BRANCH_NAME"] or ""}
            for r in summary_rows
        ]

        new_rows  = db.session.execute(_DETAIL_SQL, {**params, "condition": "NEW"}).mappings().all()
        used_rows = db.session.execute(_DETAIL_SQL, {**params, "condition": "USED"}).mappings().all()

        return jsonify({
            "month_name":  _MONTHS_ID[int(bulan)],
            "totals": {
                "tot_new":     int(tot_new),
                "tot_nf_new":  tot_nf_new,
                "tot_used":    int(tot_used),
                "tot_nf_used": tot_nf_used,
            },
            "summary":     summary,
            "detail_new":  _group_detail(new_rows,  branch_order),
            "detail_used": _group_detail(used_rows, branch_order),
        })

    except Exception:
        current_app.logger.exception("Laporan Pelunasan data fetch error")
        return jsonify({"error": "Failed to load data"}), 500