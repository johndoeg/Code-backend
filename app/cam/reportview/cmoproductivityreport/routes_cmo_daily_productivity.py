from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from flask import Blueprint, jsonify, request, current_app, session

from app import db
from app.auth.decorators import login_required

cmo_daily_productivity_bp = Blueprint('cmo_daily_productivity', __name__, url_prefix='/CAM/CMO')

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

def _exec_write(sql: str, params: list) -> None:
    raw_conn = db.session.connection().connection
    cursor = raw_conn.cursor()
    try:
        cursor.execute(sql, params)
        raw_conn.commit()
    except Exception:
        raw_conn.rollback()
        raise
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

def _fmt_value(val):
    if isinstance(val, (date, datetime)):
        return val.strftime('%d-%m-%Y')
    return val

def _fetch_context() -> dict:
    branch_cd = session.get('branchcode')
    access_level = session.get('accesslevel')
    employee_id = session.get("emp_id")
    is_hq = branch_cd == '100'

    if is_hq:
        branch_rows = _exec_rows(
            "SELECT BRANCH_CD, BRANCH_NAME FROM UMFBRANCH WHERE BRANCH_CD NOT IN ('100', '000')", []
        )
        branches = [{'branch_cd': '000', 'branch_name': 'Select'}] + [
            {'branch_cd': r.get('BRANCH_CD'), 'branch_name': r.get('BRANCH_NAME')} for r in branch_rows
        ]
        return {
            'is_hq': True,
            'own_branch': None,
            'branches': branches,
            'cmos': [],
            'access_level': access_level,
        }

    if branch_cd == '000':
        own_branch = {'branch_cd': '000', 'branch_name': 'All Branch'}
    else:
        row = _exec_rows("SELECT BRANCH_CD, BRANCH_NAME FROM UMFBRANCH WHERE BRANCH_CD = ?", [branch_cd])
        own_branch = (
            {'branch_cd': row[0]['BRANCH_CD'], 'branch_name': row[0]['BRANCH_NAME']}
            if row else {'branch_cd': branch_cd, 'branch_name': branch_cd}
        )

    if branch_cd == '000':
        cmo_rows = _exec_rows(
            "SELECT FULLNAME, EMPLOYEE_ID FROM APP_USRMST WHERE ACCESSCAM = 'CMO' AND RECSTATUS = 'A'", []
        )
        cmos = [{'employee_id': r.get('EMPLOYEE_ID'), 'full_name': r.get('FULLNAME')} for r in cmo_rows]
    elif access_level == 'CMO':
        cmo_rows = _exec_rows(
            "SELECT FULLNAME, EMPLOYEE_ID FROM APP_USRMST "
            "WHERE ACCESSCAM = 'CMO' AND BRANCHCODE = ? AND RECSTATUS = 'A' AND EMPLOYEE_ID = ?",
            [branch_cd, employee_id],
        )
        cmos = [{'employee_id': r.get('EMPLOYEE_ID'), 'full_name': r.get('FULLNAME')} for r in cmo_rows]
    else:
        cmo_rows = _exec_rows(
            "SELECT FULLNAME, EMPLOYEE_ID FROM APP_USRMST "
            "WHERE ACCESSCAM = 'CMO' AND BRANCHCODE = ? AND RECSTATUS = 'A'",
            [branch_cd],
        )
        cmos = [{'employee_id': '000', 'full_name': 'Consolidate'}] + [
            {'employee_id': r.get('EMPLOYEE_ID'), 'full_name': r.get('FULLNAME')} for r in cmo_rows
        ]

    return {
        'is_hq': False,
        'own_branch': own_branch,
        'branches': [],
        'cmos': cmos,
        'access_level': access_level,
    }

@cmo_daily_productivity_bp.route('/daily-productivity-detail/context')
@login_required
def get_context():
    try:
        return jsonify(_fetch_context())
    except Exception as e:
        current_app.logger.exception("CMO daily productivity detail context error")
        return jsonify({'error': str(e)}), 500

def _fetch_cmos_by_branch(branch_cd: str) -> list[dict]:
    rows = _exec_rows(
        "SELECT FULLNAME, EMPLOYEE_ID FROM APP_USRMST "
        "WHERE ACCESSCAM = 'CMO' AND RECSTATUS = 'A' AND BRANCHCODE = ?",
        [branch_cd],
    )
    return [{'employee_id': '000', 'full_name': 'Consolidate'}] + [
        {'employee_id': r.get('EMPLOYEE_ID'), 'full_name': r.get('FULLNAME')} for r in rows
    ]

@cmo_daily_productivity_bp.route('/daily-productivity-detail/cmos-by-branch')
@login_required
def get_cmos_by_branch():
    branch_cd = request.args.get('branch', '').strip()
    if not branch_cd:
        return jsonify({'error': 'branch is required'}), 400
    try:
        return jsonify(_fetch_cmos_by_branch(branch_cd))
    except Exception as e:
        current_app.logger.exception("CMO-by-branch lookup error")
        return jsonify({'error': str(e)}), 500

@cmo_daily_productivity_bp.route('/daily-productivity-detail/reject-statuses')
@login_required
def get_reject_statuses():
    try:
        rows = _exec_rows("SELECT VALUE, DESC_VALUE FROM MSTCOMBO WHERE CAT_VALUE = 'REJECT_STS'", [])
        return jsonify([{'value': r.get('VALUE'), 'label': r.get('DESC_VALUE')} for r in rows])
    except Exception as e:
        current_app.logger.exception("Reject status list error")
        return jsonify({'error': str(e)}), 500

def _fetch_detail(start_date: date, end_date: date, branch_cd: str, cmo: str, access_level: str) -> dict:
    consolidated = cmo == '000' or not cmo

    cmo_filter_sue = "" if consolidated else "AND a.CMO = ?"
    cmo_filter_reject = "" if consolidated else "AND cr.Create_By = ?"

    sql = f"""
        WITH Sue AS (
            SELECT
                a.APPL_NO,
                '' AS ID_Reject,
                aa.cust_name,
                a.CREATE_DATE AS tgl_buat,
                CASE
                    WHEN aa.apless2 IS NOT NULL AND CONVERT(date, a.CREATE_DATE) >= CONVERT(date, aa.createdate)
                        THEN 'CAM Created (Added to Watchlist ' + CONVERT(varchar, aa.createdate, 106) + ')'
                    WHEN aa.ktp2 IS NOT NULL AND CONVERT(date, a.CREATE_DATE) >= CONVERT(date, aa.createdate2)
                        THEN 'CAM Created (Added to Watchlist ' + CONVERT(varchar, aa.createdate2, 106) + ')'
                    ELSE 'CAM Created'
                END AS sts,
                a.CMO,
                a.BRANCH_CD,
                usr.fullname,
                '' AS Reject_Status
            FROM CAFCONT a WITH (NOLOCK)
                RIGHT JOIN (
                    SELECT DISTINCT
                        b.APLESS, b.id_card,
                        xx.APLESS AS apless2, ww.id_card AS ktp2,
                        xx.createdate, ww.createdate AS createdate2,
                        b.LESSEE_NM AS cust_name
                    FROM CAFLESS b WITH (NOLOCK)
                        LEFT JOIN mcmowatchlist xx ON xx.apless = b.apless AND xx.flag_type = 'W' AND xx.FlagDel = 0
                        LEFT JOIN mcmowatchlist ww ON ww.id_card = b.id_card AND ww.flag_type = 'W' AND ww.FlagDel = 0
                ) aa ON a.APLESS = aa.APLESS
                LEFT JOIN APP_USRMST usr WITH (NOLOCK) ON a.CMO = usr.Employee_id
            WHERE usr.ACCESSCAM = 'CMO'
                AND a.CMO IS NOT NULL
                {cmo_filter_sue}
                AND CONVERT(date, a.CREATE_DATE) BETWEEN ? AND ?
                AND a.BRANCH_CD = ?
        ),
        Combined AS (
            SELECT
                xx.APPL_NO, xx.ID_Reject, xx.cust_name, xx.tgl_buat, xx.sts,
                xx.CMO, xx.BRANCH_CD, xx.fullname, xx.Reject_Status,
                CASE WHEN zz.appr_sts IS NULL THEN 'O' ELSE zz.appr_sts END AS appr_sts,
                ROW_NUMBER() OVER (PARTITION BY xx.APPL_NO ORDER BY zz.[no] DESC) AS rn
            FROM Sue xx
                LEFT JOIN mcmocamstatus zz ON zz.appl_no = xx.APPL_NO
        )
        SELECT APPL_NO, ID_Reject, cust_name, tgl_buat, sts, CMO, BRANCH_CD, fullname, Reject_Status, appr_sts
        FROM Combined WHERE rn = 1

        UNION

        SELECT
            '' AS APPL_NO, cr.ID_Reject, cr.Cust_name AS cust_name, cr.Create_Date AS tgl_buat,
            mc.DESC_VALUE AS sts, cr.Create_By AS CMO, usr.branchcode AS BRANCH_CD, usr.fullname,
            cr.Reject_Status, '0' AS appr_sts
        FROM Customer_Reject cr WITH (NOLOCK)
            INNER JOIN MSTCOMBO mc WITH (NOLOCK) ON cr.Reject_Status = mc.VALUE
            LEFT JOIN APP_USRMST usr WITH (NOLOCK) ON cr.Create_By = usr.Employee_id
        WHERE mc.CAT_VALUE = 'REJECT_STS'
            AND cr.Create_By IS NOT NULL
            {cmo_filter_reject}
            AND CONVERT(date, cr.Create_Date) BETWEEN ? AND ?
            AND usr.branchcode = ?
        ORDER BY tgl_buat
    """
    
    params: list = []
    if not consolidated:
        params.append(cmo)
    params += [start_date, end_date, branch_cd]
    if not consolidated:
        params.append(cmo)
    params += [start_date, end_date, branch_cd]

    rows = _exec_rows(sql, params)

    show_actions = (not consolidated) and access_level == 'CMO'

    data = []
    totals = {
        'cam_created': 0,
        'reject_watchlist': 0,
        'not_feasible': 0,
        'financed_elsewhere': 0,
        'cancelled': 0,
        'total': 0,
    }

    for i, r in enumerate(rows, start=1):
        appr_sts = r.get('appr_sts')
        sts = r.get('sts') or ''
        is_rw = appr_sts == 'RW'
        status_label = 'Reject to Watchlist' if is_rw else sts

        karakter = sts[:11]
        if karakter == 'CAM Created' and not is_rw:
            totals['cam_created'] += 1
        if is_rw:
            totals['reject_watchlist'] += 1
        if sts == 'Customer is not feasible to be financed' and not is_rw:
            totals['not_feasible'] += 1
        if sts == 'Customer is financed by another leasing company' and not is_rw:
            totals['financed_elsewhere'] += 1
        if sts == 'Customer cancel their application' and not is_rw:
            totals['cancelled'] += 1
        totals['total'] += 1

        reject_status = r.get('Reject_Status') or ''

        data.append({
            'no': i,
            'appl_no': r.get('APPL_NO') or '',
            'id_reject': r.get('ID_Reject') or '',
            'customer_name': r.get('cust_name') or '-',
            'date': _fmt_value(r.get('tgl_buat')),
            'status': status_label,
            'cmo_name': r.get('fullname') or '-',
            'reject_status': reject_status,
            'editable': show_actions and bool(reject_status),
        })

    return {'data': data, 'totals': totals, 'show_actions': show_actions, 'consolidated': consolidated}

@cmo_daily_productivity_bp.route('/daily-productivity-detail/list')
@login_required
def get_detail():
    start_date = _parse_date(request.args.get('start_date', ''))
    end_date = _parse_date(request.args.get('end_date', ''))
    branch_cd = request.args.get('branch', '').strip()
    cmo = request.args.get('cmo', '').strip()

    if start_date is None or end_date is None:
        return jsonify({'error': 'start_date and end_date are required (YYYY-MM-DD)'}), 400
    if not branch_cd:
        return jsonify({'error': 'branch is required'}), 400

    try:
        return jsonify(_fetch_detail(start_date, end_date, branch_cd, cmo, session.get("accesslevel")))
    except Exception as e:
        current_app.logger.exception("CMO daily productivity detail list error")
        return jsonify({'error': str(e)}), 500

@cmo_daily_productivity_bp.route('/daily-productivity-detail/reject/<id_reject>')
@login_required
def get_reject(id_reject):
    rows = _exec_rows("SELECT * FROM Customer_Reject WHERE ID_Reject = ?", [id_reject])
    if not rows:
        return jsonify({'error': 'not found'}), 404
    r = rows[0]
    return jsonify({
        'id_reject': r.get('ID_Reject'),
        'customer_name': r.get('Cust_name'),
        'reject_status': r.get('Reject_Status'),
        'create_by': r.get('Create_By'),
        'create_date': _fmt_value(r.get('Create_Date')),
    })

@cmo_daily_productivity_bp.route('/daily-productivity-detail/reject', methods=['POST'])
@login_required
def create_reject():
    body = request.get_json(force=True) or {}
    sts_date = _parse_date(body.get('date', ''))
    cust_name = (body.get('customer_name') or '').strip()
    reject_status = (body.get('reject_status') or '').strip()

    if sts_date is None or not cust_name or not reject_status:
        return jsonify({'error': 'kosong'}), 400

    try:
        _exec_write(
            "INSERT INTO Customer_Reject (Cust_name, Reject_Status, Create_By, Create_Date) VALUES (?, ?, ?, ?)",
            [cust_name, reject_status, session.get("emp_id"), sts_date],
        )
        return jsonify({'status': 'success'})
    except Exception as e:
        current_app.logger.exception("Customer_Reject create error")
        return jsonify({'error': str(e)}), 500

@cmo_daily_productivity_bp.route('/daily-productivity-detail/reject/<id_reject>', methods=['PUT'])
@login_required
def update_reject(id_reject):
    body = request.get_json(force=True) or {}
    sts_date = _parse_date(body.get('date', ''))
    cust_name = (body.get('customer_name') or '').strip()
    reject_status = (body.get('reject_status') or '').strip()

    if sts_date is None or not cust_name or not reject_status:
        return jsonify({'error': 'kosong'}), 400

    try:
        _exec_write(
            "UPDATE Customer_Reject SET Cust_name = ?, Reject_Status = ?, Create_By = ?, Create_Date = ? "
            "WHERE ID_Reject = ?",
            [cust_name, reject_status, session.get("emp_id"), sts_date, id_reject],
        )
        return jsonify({'status': 'success'})
    except Exception as e:
        current_app.logger.exception("Customer_Reject update error")
        return jsonify({'error': str(e)}), 500

@cmo_daily_productivity_bp.route('/daily-productivity-detail/reject/<id_reject>', methods=['DELETE'])
@login_required
def delete_reject(id_reject):
    try:
        _exec_write("DELETE FROM Customer_Reject WHERE ID_Reject = ?", [id_reject])
        return jsonify({'status': 'success'})
    except Exception as e:
        current_app.logger.exception("Customer_Reject delete error")
        return jsonify({'error': str(e)}), 500