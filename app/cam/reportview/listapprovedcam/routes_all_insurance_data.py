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

all_insurance_data_bp = Blueprint('all_insurance_data', __name__, url_prefix='/CAM/Approved')

_COLUMNS = [
    ('A', None, 'No.', 'style1'),
    ('B', 'appl_no', 'CAM No.', 'style1'),
    ('C', 'create_date', 'Created Date', 'style2'),
    ('D', 'last_approved', 'Final Approved Date', 'style2'),
    ('E', 'last_status', 'Last Status', 'style1'),
    ('F', 'LESSEE_NM', 'Customer Name', 'style1'),
    ('G', 'Dealer', 'Dealer Name', 'style1'),
    ('H', 'BRAND_NM', 'Brand', 'style1'),
    ('I', 'tipe_mobil', 'Type', 'style1'),
    ('J', 'model', 'Model/Karoseri', 'style1'),
    ('K', 'WHEELS', 'Wheels', 'style1'),
    ('L', 'tahun', 'Year/Condition', 'style1'),
    ('M', 'tipe_equip', 'Type of Equipment', 'style1'),
    ('N', 'STNK_VALIDDT', 'STNK Valid Date', 'style1'),
    ('O', 'CHASIS', 'Chasis No.', 'style1'),
    ('P', 'ENGINE', 'Engine No.', 'style1'),
    ('Q', 'POLICENO', 'Police No.', 'style1'),
    ('R', 'USERUSAGE', 'User Usage', 'style1'),
    ('S', 'vehicle_purpose', 'Vehicle Purpose', 'style1'),
    ('T', 'tenor', 'Tenor', 'style1'),
    ('U', 'L_AMOUNT', 'Asset Value', 'style1'),
    ('V', 'Ins_co', 'Ins. Company', 'style1'),
    ('W', 'year1', 'Year 1 (%)', 'style3'),
    ('X', 'year2', 'Year 2 (%)', 'style1'),
    ('Y', 'year3', 'Year 3 (%)', 'style1'),
    ('Z', 'year4', 'Year 4 (%)', 'style1'),
    ('AA', 'year5', 'Year 5 (%)', 'style1'),
    ('AB', 'ins_amt_year1', 'Year 1 (Insurance Amount)', 'style1'),
    ('AC', 'ins_amt_year2', 'Year 2 (Insurance Amount)', 'style1'),
    ('AD', 'ins_amt_year3', 'Year 3 (Insurance Amount)', 'style1'),
    ('AE', 'ins_amt_year4', 'Year 4 (Insurance Amount)', 'style1'),
    ('AF', 'ins_amt_year5', 'Year 5 (Insurance Amount)', 'style1'),
    ('AG', 'tpl_amt_year1', 'Year 1 (TPL Amount)', 'style1'),
    ('AH', 'tpl_amt_year2', 'Year 2 (TPL Amount)', 'style1'),
    ('AI', 'tpl_amt_year3', 'Year 3 (TPL Amount)', 'style1'),
    ('AJ', 'tpl_amt_year4', 'Year 4 (TPL Amount)', 'style1'),
    ('AK', 'tpl_amt_year5', 'Year 5 (TPL Amount)', 'style1'),
    ('AL', 'tlo_year1', 'Year 1 (TLO CP)', 'style1'),
    ('AM', 'tlo_year2', 'Year 2 (TLO CP)', 'style1'),
    ('AN', 'tlo_year3', 'Year 3 (TLO CP)', 'style1'),
    ('AO', 'tlo_year4', 'Year 4 (TLO CP)', 'style1'),
    ('AP', 'tlo_year5', 'Year 5 (TLO CP)', 'style1'),
    ('AQ', 'clause_year1', 'Year 1 (CLAUSE)', 'style1'),
    ('AR', 'clause_year2', 'Year 2 (CLAUSE)', 'style1'),
    ('AS', 'clause_year3', 'Year 3 (CLAUSE)', 'style1'),
    ('AT', 'clause_year4', 'Year 4 (CLAUSE)', 'style1'),
    ('AU', 'clause_year5', 'Year 5 (CLAUSE)', 'style1'),
    ('AV', 'prer_year1', 'Year 1 (PREMIUM RECEIVE)', 'style1'),
    ('AW', 'prer_year2', 'Year 2 (PREMIUM RECEIVE)', 'style1'),
    ('AX', 'prer_year3', 'Year 3 (PREMIUM RECEIVE)', 'style1'),
    ('AY', 'prer_year4', 'Year 4 (PREMIUM RECEIVE)', 'style1'),
    ('AZ', 'prer_year5', 'Year 5 (PREMIUM RECEIVE)', 'style1'),
    ('BA', 'CMO', 'CMO Name', 'style1'),
    ('BB', 'lease_no', 'Contract No.', 'style1'),
    ('BC', 'execution', 'Disbursement Date', 'style1'),
    ('BD', 'BRANCH_NAME', 'Branch Name', 'style1'),
    ('BE', 'NetInsurancePremReceived', 'Net Insurance Prem. Received', 'style1'),
    ('BF', 'policy_no', 'Policy No.', 'style1'),
    ('BG', 'cover', 'Cover Date', 'style1'),
]

@all_insurance_data_bp.route('/all-insurance-data/branches')
@login_required
def list_branches():
    try:
        return jsonify(fetch_branch_options())
    except Exception as e:
        current_app.logger.exception("Branch list error")
        return jsonify({'error': str(e)}), 500

def _build_workbook(search_by, date_from, date_to, branch_cd, username):
    rows = exec_rows(
        "EXEC USP_ALL_INSURANCE_DATA ?, ?, ?, ?",
        [search_by, sp_date(date_from), sp_date(date_to), branch_cd],
    )
    return build_report_workbook(
        sheet_title='AllInsuranceData',
        report_title='ALL INSURANCE DATA',
        columns=_COLUMNS,
        rows=rows,
        search_by=search_by,
        date_from=date_from,
        date_to=date_to,
        username=username,
    )

@all_insurance_data_bp.route('/all-insurance-data/export')
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
        return workbook_response(wb, 'AllInsuranceData.xlsx')
    except Exception as e:
        current_app.logger.exception("All Insurance Data export error")
        return jsonify({'error': str(e)}), 500