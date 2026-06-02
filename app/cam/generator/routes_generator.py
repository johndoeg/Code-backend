from flask import Blueprint, request, jsonify, current_app
from app import db
from sqlalchemy import text
from datetime import datetime

generator_bp = Blueprint('generator', __name__, url_prefix='/generator')

def update_temp_precheckingid(username: str) -> bool:
    try:
        update_sql = text(f"""
            UPDATE ta
            SET 
                NextRunningNumber = NextRunningNumber + 1,
                UpdatedBy = ?,
                UpdatedDate = GETDATE()
            FROM TEMP_PRECHECKING_ID ta
            WHERE [Year] = YEAR(GETDATE())
              AND [Month] = MONTH(GETDATE())
              AND [Date] = DAY(GETDATE())
        """)
        db.session.execute(update_sql, (username,))
        return True
    except Exception as e:
        current_app.logger.error(f"Update failed: {str(e)}")
        return False

@generator_bp.route('/cam_request_generate_temp_precheckingid', methods=['POST'])
def generate_temp_precheckingid():
    try:
        username = request.headers.get('X-Username', 'system')

        today = datetime.now()
        year_part = today.year
        month_part = today.month
        day_part = today.day
        
        query = text(f"""
            SELECT TOP 1 
                RIGHT([Year], 2) AS YearPart, 
                [Month] AS MonthPart, 
                [Date] AS DayPart, 
                NextRunningNumber 
            FROM TEMP_PRECHECKING_ID WITH(NOLOCK) 
            WHERE [Year] = ? AND [Month] = ? AND [Date] = ?
            ORDER BY Id DESC
        """)
        result = db.session.execute(query, (year_part, month_part, day_part))
        row = result.fetchone()
        
        if row:
            next_running = row.NextRunningNumber
            year_str = row.YearPart
            month_str = str(row.MonthPart).zfill(2)
            day_str = str(row.DayPart).zfill(2)
        else:
            next_running = 1
            year_str = str(year_part)[-2:]
            month_str = str(month_part).zfill(2)
            day_str = str(day_part).zfill(2)
            
            insert_sql = """
                INSERT INTO TEMP_PRECHECKING_ID 
                ([Year], [Month], [Date], NextRunningNumber, CreatedBy, CreatedDate) 
                VALUES (?, ?, ?, 1, ?, GETDATE())
            """
            db.session.execute(insert_sql, (year_part, month_part, day_part, username))
        
        apless = f"{year_str}{month_str}{day_str}{str(next_running).zfill(4)}"
        
        update_temp_precheckingid(username)
        
        current_app.logger.info(f"Generated prechecking ID: {apless} for user: {username}")
        return jsonify(apless), 200
        
    except Exception as e:
        current_app.logger.error(f"Unexpected error: {str(e)}")
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500
    