from __future__ import annotations

from flask import Blueprint, jsonify, request, current_app

from app.auth.decorators import login_required
from app.utils.helpers.base_format import (
    _username,
    build_report_workbook,
    exec_rows,
    fetch_branch_options,
    parse_iso_date,
    sp_date,
    workbook_response,
)

all_cam_data_bp = Blueprint('all_cam_data', __name__, url_prefix='/CAM/Approved')

_COLUMNS = [
    ('A', None, 'No.', 'style1'),
    ('B', 'appl_no', 'CAM No.', 'style1'),
    ('C', 'create_date', 'Created Date', 'style2'),
    ('D', 'last_approved', 'Final Approved Date', 'style2'),
    ('E', 'last_approver', 'Last Approval Name', 'style1'),
    ('F', 'last_status', 'Last Status', 'style1'),
    ('G', 'LESSEE_NM', 'Customer Name', 'style1'),
    ('H', 'LESSEE_TP', 'Type', 'style1'),
    ('I', 'BRAND_NM', 'Brand', 'style1'),
    ('J', 'tipe_mobil', 'Type', 'style1'),
    ('K', 'model', 'Model/Karoseri', 'style1'),
    ('L', 'WHEELS', 'Wheels', 'style1'),
    ('M', 'TAHUN', 'Year', 'style1'),
    ('N', 'CONDITION', 'Condition', 'style1'),
    ('O', 'tipe_equip', 'Type of Equipment', 'style1'),
    ('P', 'STNK_VALIDDT', 'STNK Valid Date', 'style1'),
    ('Q', 'CHASIS', 'Chasis No.', 'style1'),
    ('R', 'ENGINE', 'Engine No.', 'style1'),
    ('S', 'POLICENO', 'Police No.', 'style1'),
    ('T', 'COLOUR', 'Color', 'style1'),
    ('U', 'USERUSAGE', 'User Usage', 'style1'),
    ('V', 'vehicle_purpose', 'Vehicle Purpose', 'style1'),
    ('W', 'cont_type', 'Contract Type', 'style3'),
    ('X', 'fin_purpose', 'Purpose of Finance', 'style1'),
    ('Y', 'tipe_pmt', 'Type of Payment', 'style1'),
    ('Z', 'fix_float', 'Fix/Float', 'style1'),
    ('AA', 'tenor', 'Tenor', 'style1'),
    ('AB', 'L_AMOUNT', 'Asset Value', 'style1'),
    ('AC', 'dp_persen', 'DP %', 'style1'),
    ('AD', 'dp', 'DP Amount', 'style1'),
    ('AE', 'ins_loan', 'Insurance Receive Onloan', 'style1'),
    ('AF', 'ins_cash', 'Insurance Receive Cash', 'style1'),
    ('AG', 'prov_loan', 'Provision Onloan', 'style1'),
    ('AH', 'prov_cash', 'Provision Cash', 'style1'),
    ('AI', 'adm_loan', 'Survey Fee Onloan', 'style1'),
    ('AJ', 'adm_cash', 'Survey Fee Cash', 'style1'),
    ('AK', 'FLATRATE', 'Flat Rate (%)', 'style1'),
    ('AL', 'DECLRATE', 'Eff Rate (%)', 'style1'),
    ('AM', 'RENTAL', 'Rental', 'style1'),
    ('AN', 'disb_dealer', 'Disbursement to Dealer', 'style1'),
    ('AO', 'tot_komisi', 'Total Commission', 'style1'),
    ('AP', 'TPL_AMT', 'TPL Amount (per year)', 'style1'),
    ('AQ', 'TLO_AR', 'TLO CP', 'style1'),
    ('AR', 'LTV', 'LTV', 'style1'),
    ('AS', 'IRR_Actual', 'IRR', 'style1'),
    ('AT', 'Ins_co', 'Ins. Company', 'style1'),
    ('AU', 'RedCode', 'Red Code', 'style1'),
    ('AV', 'CMO', 'CMO Name', 'style1'),
    ('AW', 'EXECUTION', 'Disbursement Date', 'style1'),
    ('AX', 'LEASE_NO', 'Contract No.', 'style1'),
    ('AY', 'UnIncome', 'Interest Income', 'style1'),
    ('AZ', 'ntf', 'Net Finance', 'style1'),
    ('BA', 'AlamatKTP', 'ID Address', 'style1'),
    ('BB', 'AlamatSurat', 'Mail Address', 'style1'),
    ('BC', 'HP', 'Mobile Phone', 'style1'),
    ('BD', 'Dealer', 'Dealer Name', 'style1'),
    ('BE', 'Dealer_Nickname', 'Dealer Nickname', 'style1'),
    ('BF', 'NamaBPKB', 'BPKB Name', 'style1'),
    ('BG', 'AlamatBPKB', 'BPKB Address', 'style1'),
    ('BH', 'BRANCH_NAME', 'Branch Name', 'style1'),
    ('BI', 'LESSEE_NO', 'Customer No.', 'style1'),
    ('BJ', 'IndusCode', 'Industrial Code', 'style1'),
    ('BK', 'BICust', 'BI Customer Type', 'style1'),
    ('BL', 'Rekomendasi', 'Not Recommended', 'style1'),
    ('BM', 'NetInsurancePremReceived', 'New Insurance Prem Received', 'style1'),
]

@all_cam_data_bp.route('/all-cam-data/branches')
@login_required
def list_branches():
    try:
        return jsonify(fetch_branch_options())
    except Exception as e:
        current_app.logger.exception("Branch list error")
        return jsonify({'error': str(e)}), 500

def _build_workbook(search_by, date_from, date_to, branch_cd, username):
    rows = exec_rows(
        "EXEC USP_ALL_CAM_DATA ?, ?, ?, ?",
        [search_by, sp_date(date_from), sp_date(date_to), branch_cd],
    )
    return build_report_workbook(
        sheet_title='AllCAMData',
        report_title='ALL CAM DATA',
        columns=_COLUMNS,
        rows=rows,
        search_by=search_by,
        date_from=date_from,
        date_to=date_to,
        username=username,
    )

@all_cam_data_bp.route('/all-cam-data/export')
@login_required
def export_excel():
    search_by = request.args.get('search_by', '1').strip()
    date_from = parse_iso_date(request.args.get('date_from', ''))
    date_to = parse_iso_date(request.args.get('date_to', ''))
    branch_cd = request.args.get('branch_cd', '').strip()

    if date_from is None or date_to is None:
        return jsonify({'error': 'date_from and date_to are required (YYYY-MM-DD)'}), 400

    try:
        wb = _build_workbook(search_by, date_from, date_to, branch_cd, _username())
        return workbook_response(wb, 'AllCAMData.xlsx')
    except Exception as e:
        current_app.logger.exception("All CAM Data export error")
        return jsonify({'error': str(e)}), 500