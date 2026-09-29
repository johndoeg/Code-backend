import os
import json
from datetime import date
from flask import Blueprint, jsonify, request, current_app, session
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text
from app.utils.helpers.base_format import fmt_date

master_data_deviation_dp_bp = Blueprint('master_data_deviation_dp', __name__, url_prefix='/MasterData')

_ALLOWED_MIME_TYPES = {
    'application/pdf', 'image/jpeg', 'image/pjpeg',
    'image/x-png', 'image/png', 'image/bmp',
}
MAX_FILE_SIZE = 2_000_000

def _calc_as_of():
  
    today = date.today()
    year = today.year
    year_plus1 = year + 1
    year_minus1 = year - 1

    range1_start = date(year, 8, 1)
    range1_end = date(year_plus1, 1, 31)

    range2_start = date(year, 2, 1)
    range2_end = date(year, 7, 31)

    if range1_start <= today <= range1_end:
        return f"30 Juni {year}", date(year, 6, 30)
    elif range2_start <= today <= range2_end:
        return f"31 Desember {year_minus1}", date(year_minus1, 12, 31)
    else:
        return "", None

@master_data_deviation_dp_bp.route('/deviation-dp/npf-info')
@login_required
def get_npf_info():
    try:
        as_of_label, as_of_date = _calc_as_of()
        persenya = ""

        if as_of_date:
            row = db.session.execute(
                text("""
                    SELECT Remark, Actual_From, Actual_To
                    FROM [Ratio] WITH(NOLOCK)
                    WHERE Ratio = '3' AND As_Of = :as_of
                """),
                {"as_of": as_of_date}
            ).fetchone()

            if row:
                if row.Remark in ('1', '2'):
                    persenya = f"{row.Actual_From} %"
                elif row.Remark == '3':
                    persenya = f"{row.Actual_From} % s/d {row.Actual_To} %"

        return jsonify({
            "as_of_label": as_of_label,
            "as_of_date": as_of_date.isoformat() if as_of_date else "",
            "persenya": persenya,
        })
    except Exception as e:
        current_app.logger.exception("NPF info error")
        return jsonify({"error": str(e)}), 500

@master_data_deviation_dp_bp.route('/deviation-dp/customer-search')
@login_required
def customer_search():
    term = request.args.get('term', '').strip()
    if not term:
        return jsonify([])

    try:
        rows = db.session.execute(
            text("""
                SELECT DISTINCT APLESS, LESSEE_NM
                FROM cafless WITH(NOLOCK)
                WHERE LESSEE_NM LIKE :term
            """),
            {"term": f"%{term}%"}
        ).fetchall()

        return jsonify([
            {
                "apless": r.APLESS,
                "lessee_nm": r.LESSEE_NM,
                "label": f"{r.APLESS}--{r.LESSEE_NM}",
            }
            for r in rows
        ])
    except Exception as e:
        current_app.logger.exception("Customer search error")
        return jsonify({"error": str(e)}), 500

@master_data_deviation_dp_bp.route('/deviation-dp/cam-list')
@login_required
def get_cam_list():
    apless = request.args.get('apless', '').strip()

    if not apless:
        return jsonify([])

    try:
        rows = db.session.execute(
            text("EXEC USP_CAM_ONHAND_BY_APLESS @apless = :apless, @cmo = :cmo"),
            {"apless": apless, "cmo": "CMO"}
        ).fetchall()

        data = [{
            "appl_no": r.APPL_NO,
            "equipment": r.equipment,
            "cam_date": fmt_date(r.tgl, "%d-%m-%Y") if r.tgl else "",
            "cmo": r.CMOnow,
            "id_dev": r.id_dev,
            "dp": r.down_payment,
            "br": r.base_rate,
            "attachment": r.attachment or "",
        } for r in rows]

        return jsonify(data)
    except Exception as e:
        current_app.logger.exception("CAM list error")
        return jsonify({"error": str(e)}), 500

def _save_attachment(file, appl_no):
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)

    if file.mimetype not in _ALLOWED_MIME_TYPES:
        return False, "Tipe file tidak diizinkan (hanya PDF/JPEG/PNG/BMP)"
    if size > MAX_FILE_SIZE:
        return False, "Ukuran file maksimal 2MB"

    year = str(date.today().year)
    ext = os.path.splitext(file.filename)[1]
    appl_no_clean = str(appl_no).strip()

    folder = os.path.join(current_app.config['UPLOAD_FOLDER_DEVIATION'], year, appl_no_clean)
    os.makedirs(folder, exist_ok=True)

    destination_filename = f"{year}-{appl_no_clean}{ext}"
    file.save(os.path.join(folder, destination_filename))

    return True, destination_filename

@master_data_deviation_dp_bp.route('/deviation-dp/save', methods=['POST'])
@login_required
def save_deviation():
    emp_id = session.get("emp_id", "")
    as_of = request.form.get('as_of', '')

    try:
        rows = json.loads(request.form.get('rows', '[]'))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid rows payload"}), 400

    errors = []
    saved_any = False

    try:
        for i, row in enumerate(rows):
            appl_no = row.get('appl_no')
            idnya = row.get('idnya')
            dp = row.get('dp')
            br = row.get('br')
            paramx = row.get('paramx')
            editx = row.get('editx')

            file = request.files.get(f'attach_{i}')
            has_file = bool(file and file.filename)

            if paramx == 'edit':
                destination = None
                if has_file:
                    ok, result = _save_attachment(file, appl_no)
                    if not ok:
                        errors.append(f"{appl_no}: {result}")
                        continue
                    destination = result

                if editx == 'edit_nch':
                    if dp == '1' and br != '1':
                        set_clause = "down_payment = '1', base_rate = ''"
                    elif br == '1' and dp != '1':
                        set_clause = "base_rate = '1', down_payment = ''"
                    elif br == '1' and dp == '1':
                        set_clause = "base_rate = '1', down_payment = '1'"
                    else:
                        set_clause = None
                else:
                    if dp == '1':
                        set_clause = "down_payment = '1'"
                    elif br == '1':
                        set_clause = "base_rate = '1'"
                    else:
                        set_clause = None

                if set_clause is None:
                    continue

                params = {"emp_id": emp_id, "id": idnya}
                sql = f"UPDATE deviation_dp SET {set_clause}, update_by = :emp_id, update_date = GETDATE()"
                if destination:
                    sql += ", attachment = :attachment"
                    params["attachment"] = destination
                sql += " WHERE Id = :id"

                db.session.execute(text(sql), params)
                saved_any = True

            elif paramx == 'insert':
                if dp == '1' or br == '1':
                    if has_file:
                        ok, result = _save_attachment(file, appl_no)
                        if not ok:
                            errors.append(f"{appl_no}: {result}")
                            continue

                        db.session.execute(
                            text("""
                                INSERT INTO deviation_dp
                                    (Appl_No, Down_Payment, Base_Rate, Checked_By, Checked_Date, AsOf, Attachment)
                                VALUES
                                    (:appl_no, :dp, :br, :emp_id, GETDATE(), :as_of, :attachment)
                            """),
                            {
                                "appl_no": appl_no,
                                "dp": dp or '',
                                "br": br or '',
                                "emp_id": emp_id,
                                "as_of": as_of,
                                "attachment": result,
                            }
                        )
                        saved_any = True
                    else:
                        errors.append(f"Gagal karena attachment belum dilampirkan untuk cam no {appl_no}")

        if saved_any:
            db.session.commit()
        else:
            db.session.rollback()

        if errors and not saved_any:
            return jsonify({"message": "failed", "errors": errors}), 400

        return jsonify({"message": "success", "errors": errors})

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Save deviation error")
        return jsonify({"error": str(e)}), 500