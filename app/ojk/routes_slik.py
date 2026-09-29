from flask import Blueprint, request, jsonify, current_app
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import Optional

slik_bp = Blueprint('slik', __name__, url_prefix='/SLIK')

SEGMENT_PROCEDURES = {
    'D01': {'get': 'USP_D01_GetData', 'process': 'USP_D01_Process'},
    'D02': {'get': 'USP_D02_GetData', 'process': 'USP_D02_Process'},
    'F01': {'get': 'USP_F01_GetData', 'process': 'USP_F01_Process'},
    'A01': {'get': 'USP_A01_GetData', 'process': 'USP_A01_Process'},
    'P01': {'get': 'USP_P01_GetData', 'process': 'USP_P01_Process'},
    'M01': {'get': 'USP_M01_GetData', 'process': 'USP_M01_Process'},
    'All': {'get': 'USP_F01_GetData', 'process': 'USP_AllSegment_Process'},
}

def _parse_period(period_str: str) -> Optional[str]:
   
    try:
        if len(period_str.split('-')[1]) == 2:
            dt = datetime.strptime(period_str, '%m-%y')
        else:
            dt = datetime.strptime(period_str, '%m-%Y')
        
        last_day = dt + relativedelta(months=1, day=1, days=-1)
        
        return last_day.strftime('%d-%b-%Y')
        
    except (ValueError, IndexError, TypeError):
        return None

@slik_bp.route('/slik-backend', methods=['POST'])
@login_required
def slik_backend():
    try:
        if request.is_json:
            data = request.get_json() or {}
            addmode = str(data.get('addmode', ''))
            segment = data.get('segment')
            period = data.get('period')
        else:
            addmode = request.form.get('addmode') or request.args.get('addmode', '')
            segment = request.form.get('segment') or request.args.get('segment')
            period = request.form.get('period') or request.args.get('period')
        
        current_app.logger.debug(f"Received: addmode={addmode}, segment={segment}, period={period}")
        
        if not segment or segment not in SEGMENT_PROCEDURES:
            return jsonify([{'error': f'Invalid segment: {segment}'}]), 400
        
        if not period:
            return jsonify([{'error': 'period parameter required'}]), 400
        
        selected_date = _parse_period(period)
        if not selected_date:
            return jsonify([{'error': 'Invalid period format. Use MM-YYYY (e.g., 11-2025)'}]), 400
        
        if addmode == '1':
            proc_name = SEGMENT_PROCEDURES[segment]['get']
            
            result = db.session.execute(
                text(f"EXEC {proc_name} :selected_date"),
                {"selected_date": selected_date}
            )
            
            has_data = result.first() is not None
            
            response = [{
                "message": f"Data untuk periode {period} {'tersedia' if has_data else 'tidak tersedia, silakan proses ulang'}!",
                "data": has_data
            }]
            
            return jsonify(response)
        
        elif addmode == '2':
            proc_name = SEGMENT_PROCEDURES[segment]['process']
            
            db.session.execute(
                text(f"EXEC {proc_name} :selected_date"),
                {"selected_date": selected_date}
            )
            db.session.commit()
            
            return jsonify([])
        
        else:
            return jsonify([{'error': f'Invalid addmode: {addmode}'}]), 400
            
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("SLIK backend error")
        return jsonify([{'error': 'Failed to process request'}]), 500