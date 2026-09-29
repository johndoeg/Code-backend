import glob
import os

from flask import Blueprint, current_app, jsonify, request, session
from sqlalchemy import text

from app import db
from app.auth.decorators import login_required

cam_onhand_delete_bp = Blueprint('cam_onhand_delete', __name__, url_prefix='/CAM/Onhand/Delete')

@cam_onhand_delete_bp.route('/<appl_no>', methods=['DELETE'])
@login_required
def delete_cam(appl_no):
    apless = request.args.get('apless', '')

    try:
        row = db.session.execute(text("""
            SELECT AdmSts FROM MCMOCAMCOMPLETELIST WITH (NOLOCK) WHERE APPL_NO = :appl_no
        """), {"appl_no": appl_no}).mappings().first()

        if row and row.get("AdmSts") == "1":
            return jsonify({
                "success": False,
                "message": "Cam has been send to admin.",
            })

        upload_root = current_app.config.get("CAM_UPLOAD_PATH")
        if upload_root and apless:
            pattern = os.path.join(upload_root, apless, f"{appl_no}*.*")
            for file_path in glob.glob(pattern):
                try:
                    os.remove(file_path)
                except OSError:
                    current_app.logger.warning("Could not remove CAM file %s", file_path)

        db.session.execute(text("EXEC USP_CAM_PROCDELETECAM :appl_no"), {"appl_no": appl_no})
        db.session.commit()

        return jsonify({"success": True, "message": "Delete success.."})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("delete_cam error (appl_no=%s)", appl_no)
        return jsonify({"success": False, "message": "Delete failed. Please try again."}), 500