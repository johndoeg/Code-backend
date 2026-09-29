from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from flask import Blueprint, jsonify, request, current_app, session

from app import db
from app.auth.decorators import login_required

cmo_daily_productivity_by_cmo_bp = Blueprint('cmo_daily_productivity_by_cmo', __name__, url_prefix='/CAM/CMO')

def _exec_rows(sql: str, params: list) -> list[dict]:
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

def _parse_date(raw: str) -> Optional[date]:
    raw = (raw or '').strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, '%Y-%m-%d').date()
    except ValueError:
        return None

def _fetch_branches(user_branch_cd: str) -> list[dict]:
   
    if user_branch_cd != '100':
        sql = "SELECT BRANCH_CD, BRANCH_NAME FROM UMFBRANCH WHERE BRANCH_CD = ?"
        params = [user_branch_cd]
    else:
        sql = "SELECT BRANCH_CD, BRANCH_NAME FROM UMFBRANCH WHERE BRANCH_CD NOT IN ('100', '000')"
        params = []

    rows = _exec_rows(sql, params)
    return [{'branch_cd': r.get('BRANCH_CD'), 'branch_name': r.get('BRANCH_NAME')} for r in rows]

@cmo_daily_productivity_by_cmo_bp.route('/daily-productivity-by-cmo/branches')
@login_required
def list_branches():
    try:
        return jsonify(_fetch_branches(session.get("branchcode", "")))
    except Exception as e:
        current_app.logger.exception("Branch list error")
        return jsonify({'error': str(e)}), 500

def _fetch_summary(start_date: date, end_date: date, branch_cd: str) -> dict:
    
    sql = """
        WITH CamCreated AS (
            SELECT
                a.APPL_NO,
                a.CMO,
                a.BRANCH_CD
            FROM CAFCONT a WITH (NOLOCK)
                RIGHT JOIN (
                    SELECT DISTINCT
                        b.APLESS, b.id_card,
                        xx.APLESS AS apless2, ww.id_card AS ktp2,
                        xx.createdate, ww.createdate AS createdate2,
                        b.LESSEE_NM AS cust_name
                    FROM CAFLESS b WITH (NOLOCK)
                        LEFT JOIN mcmowatchlist xx ON xx.apless = b.apless AND xx.flag_type = 'W' AND xx.flagdel = 0
                        LEFT JOIN mcmowatchlist ww ON ww.id_card = b.id_card AND ww.flag_type = 'W' AND ww.flagdel = 0
                ) aa ON a.APLESS = aa.APLESS
                LEFT JOIN APP_USRMST usr WITH (NOLOCK) ON a.CMO = usr.Employee_id
            WHERE usr.ACCESSCAM = 'CMO'
                AND a.CMO IS NOT NULL
                AND CONVERT(date, a.CREATE_DATE) BETWEEN ? AND ?
        ),
        CamStatus AS (
            SELECT
                c.CMO,
                CASE WHEN zz.appr_sts IS NULL THEN 'O' ELSE zz.appr_sts END AS appr_sts,
                ROW_NUMBER() OVER (PARTITION BY c.APPL_NO ORDER BY zz.[no] DESC) AS rn
            FROM CamCreated c
                LEFT JOIN mcmocamstatus zz ON zz.appl_no = c.APPL_NO
        ),
        CreatedByCmo AS (
            SELECT CMO, COUNT(*) AS total_created
            FROM CamStatus
            WHERE rn = 1 AND appr_sts <> 'RW'
            GROUP BY CMO
        ),
        RejectByCmo AS (
            SELECT CMO, COUNT(*) AS total_reject
            FROM CamStatus
            WHERE rn = 1 AND appr_sts = 'RW'
            GROUP BY CMO
        ),
        ManualReject AS (
            SELECT
                cr.Create_By AS CMO,
                cr.Reject_Status
            FROM Customer_Reject cr WITH (NOLOCK)
                INNER JOIN MSTCOMBO mc WITH (NOLOCK) ON cr.Reject_Status = mc.VALUE
                LEFT JOIN APP_USRMST usr WITH (NOLOCK) ON cr.Create_By = usr.Employee_id
            WHERE mc.CAT_VALUE = 'REJECT_STS'
                AND usr.ACCESSCAM = 'CMO'
                AND cr.Create_By IS NOT NULL
                AND CONVERT(date, cr.Create_Date) BETWEEN ? AND ?
        ),
        Defect1ByCmo AS (
            SELECT CMO, COUNT(*) AS total_defect1 FROM ManualReject WHERE Reject_Status = 1 GROUP BY CMO
        ),
        Defect2ByCmo AS (
            SELECT CMO, COUNT(*) AS total_defect2 FROM ManualReject WHERE Reject_Status = 2 GROUP BY CMO
        ),
        Defect3ByCmo AS (
            SELECT CMO, COUNT(*) AS total_defect3 FROM ManualReject WHERE Reject_Status = 3 GROUP BY CMO
        )
        SELECT
            aa.Employee_id,
            aa.fullname,
            ISNULL(bb.total_created, 0) AS total_created,
            ISNULL(cc.total_reject, 0) AS total_reject,
            ISNULL(ee.total_defect1, 0) AS total_defect1,
            ISNULL(ff.total_defect2, 0) AS total_defect2,
            ISNULL(gg.total_defect3, 0) AS total_defect3
        FROM APP_USRMST aa WITH (NOLOCK)
            LEFT JOIN CreatedByCmo bb ON aa.Employee_id = bb.CMO
            LEFT JOIN RejectByCmo cc ON aa.Employee_id = cc.CMO
            LEFT JOIN Defect1ByCmo ee ON aa.Employee_id = ee.CMO
            LEFT JOIN Defect2ByCmo ff ON aa.Employee_id = ff.CMO
            LEFT JOIN Defect3ByCmo gg ON aa.Employee_id = gg.CMO
        WHERE aa.ACCESSCAM = 'CMO'
            AND aa.branchcode = ?
        ORDER BY aa.fullname ASC
    """
    rows = _exec_rows(sql, [start_date, end_date, start_date, end_date, branch_cd])

    data = []
    totals = {
        'total_created': 0,
        'total_reject': 0,
        'total_defect1': 0,
        'total_defect2': 0,
        'total_defect3': 0,
        'sub_total': 0,
    }

    for i, r in enumerate(rows, start=1):
        total_created = r.get('total_created') or 0
        total_reject = r.get('total_reject') or 0
        total_defect1 = r.get('total_defect1') or 0
        total_defect2 = r.get('total_defect2') or 0
        total_defect3 = r.get('total_defect3') or 0
        sub_total = total_created + total_reject + total_defect1 + total_defect2 + total_defect3

        totals['total_created'] += total_created
        totals['total_reject'] += total_reject
        totals['total_defect1'] += total_defect1
        totals['total_defect2'] += total_defect2
        totals['total_defect3'] += total_defect3
        totals['sub_total'] += sub_total

        data.append({
            'no': i,
            'employee_id': r.get('Employee_id'),
            'cmo_name': r.get('fullname') or '-',
            'total_created': total_created,
            'total_reject': total_reject,
            'total_defect1': total_defect1,
            'total_defect2': total_defect2,
            'total_defect3': total_defect3,
            'sub_total': sub_total,
        })

    return {'data': data, 'totals': totals}

@cmo_daily_productivity_by_cmo_bp.route('/daily-productivity-by-cmo/summary')
@login_required
def get_summary():
    start_date = _parse_date(request.args.get('start_date', ''))
    end_date = _parse_date(request.args.get('end_date', ''))
    branch_cd = request.args.get('branch', '').strip()

    if start_date is None or end_date is None:
        return jsonify({'error': 'start_date and end_date are required (YYYY-MM-DD)'}), 400
    if not branch_cd:
        return jsonify({'error': 'branch is required'}), 400

    try:
        return jsonify(_fetch_summary(start_date, end_date, branch_cd))
    except Exception as e:
        current_app.logger.exception("CMO daily productivity summary error")
        return jsonify({'error': str(e)}), 500