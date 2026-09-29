from flask import Blueprint, request, jsonify, current_app, session

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app import db
from app.auth.decorators import login_required
from sqlalchemy import text

approval_prechecking_bp = Blueprint("approval_prechecking", __name__, url_prefix="/Prechecking/Approval")

def _username():    return session.get("username", "")
def _accesslevel(): return session.get("accesslevel", "")

@approval_prechecking_bp.route("/approval-form", methods=["GET"])
@login_required
def get_approval_form():
    apless         = request.args.get("apless", "")
    prechecking_id = request.args.get("prechecking_id_send", "")
    access_level   = _accesslevel()
    
    print('oke')

    try:
        row = db.session.execute(text("""
            SELECT Apless, Prechecking_Id, IdCardNo, LesseeType,
                   LesseeName, CreatedBy AS CMO
            FROM TEMP_CAFLESS WITH(NOLOCK)
            WHERE Apless = :apless AND Prechecking_Id = :pid
        """), {"apless": apless, "pid": prechecking_id}).fetchone()

        if not row:
            return jsonify({"error": "Prechecking not found"}), 404

        rej = db.session.execute(text("""
            SELECT TOP 1 a.Remarks, a.CreatedBy, a.CreatedDate
            FROM DocumentApprovalHistory a
                INNER JOIN DocumentApproval b ON a.DocumentApprovalId = b.Id
            WHERE b.LastApprovalActionCode = 'reject'
              AND a.ApprovalActionCode      = 'reject'
              AND b.DocumentNumber          = :pid
            ORDER BY a.CreatedDate DESC
        """), {"pid": prechecking_id}).fetchone()

        rejected      = rej is not None
        rejected_by   = rej.CreatedBy if rej else ""
        reject_comment= rej.Remarks   if rej else ""
        rejected_date = (
            rej.CreatedDate.strftime("%d-%m-%Y %H:%M:%S")
            if rej and rej.CreatedDate else ""
        )

        cr_approver = "Admin"
        if access_level == "CMO":
            try:
                cr_row = db.session.execute(
                    text("EXEC USP_CAM_GETVALIDCR")
                ).fetchone()
                if cr_row and cr_row.Username:
                    cr_approver = cr_row.Username
            except Exception:
                cr_approver = "Admin"

        return jsonify({
            "apless":          row.Apless         or "",
            "prechecking_id":  row.Prechecking_Id or "",
            "lessee_name":     row.LesseeName     or "",
            "cmo":             row.CMO             or "",
            "rejected":        rejected,
            "rejected_by":     rejected_by,
            "rejected_date":   rejected_date,
            "reject_comment":  reject_comment,
            "access_level":    access_level,
            "cr_approver":     cr_approver,
        })

    except Exception:
        current_app.logger.exception("get_approval_form error")
        return jsonify({"error": "Server error"}), 500

@approval_prechecking_bp.route("/approval-confirm", methods=["POST"])
@login_required
def post_approval_confirm():
    username     = _username()
    access_level = _accesslevel()

    body           = request.get_json(force=True) or {}
    apless         = (body.get("apless")         or "").strip()
    prechecking_id = (body.get("prechecking_id") or "").strip()
    comment        = (body.get("comment")        or "").replace("'", "`")
    approval       = (body.get("approval")       or "Admin").strip()
    approval_status= (body.get("approval_status")or "A").strip()

    if not prechecking_id:
        return jsonify({"success": False, "message": "prechecking_id required"}), 400

    in_progress = db.session.execute(text("""
        SELECT TOP 1 Progress, LastApprovalActionCode, DocumentStatusCode
        FROM DocumentApproval a WITH(NOLOCK)
            INNER JOIN TEMP_CAFLESS b WITH(NOLOCK) ON a.DocumentNumber = b.Prechecking_Id
        WHERE b.IdCardNo = (
            SELECT IdCardNo FROM TEMP_CAFLESS WITH(NOLOCK)
            WHERE Prechecking_Id = :pid
        )
        AND a.LastApprovalActionCode = 'submit'
    """), {"pid": prechecking_id}).fetchone()

    if (
        in_progress
        and str(in_progress.Progress) == "50"
        and in_progress.LastApprovalActionCode == "submit"
        and in_progress.DocumentStatusCode == "submitted"
    ):
        return jsonify({"success": False, "message": "This Customer is still in progress!"}), 409

    try:
        if access_level == "CMO":
            db.session.execute(
                text("EXEC USP_CAM_REQUEST_SENTBYCMO :pid, :username, :comment, :approval"),
                {
                    "pid":      prechecking_id,
                    "username": username,
                    "comment":  comment,
                    "approval": approval,
                },
            )
            db.session.commit()

        else:
            form_row = db.session.execute(
                text("SELECT TOP 1 Id FROM mstApprovalForm WHERE ApprovalFormKey = 'cam-request'")
            ).fetchone()
            approval_form_id = form_row.Id if form_row else 1

            db.session.execute(
                text("""
                    EXEC USP_CAM_REQUEST_SENTBYAPPLNO
                        :pid, :username, :comment,
                        :form_id, :access_level, :approval, :approval_status
                """),
                {
                    "pid":            prechecking_id,
                    "username":       username,
                    "comment":        comment,
                    "form_id":        approval_form_id,
                    "access_level":   access_level,
                    "approval":       approval,
                    "approval_status":approval_status,
                },
            )
            db.session.commit()

            if access_level == "CR":
                _move_s3_files_to_final_apless(apless, prechecking_id)

        return jsonify({"success": True, "approval": approval})

    except Exception:
        db.session.rollback()
        current_app.logger.exception("post_approval_confirm error")
        return jsonify({"success": False, "message": "Database error"}), 500

def _move_s3_files_to_final_apless(apless: str, prechecking_id: str) -> None:
   
    try:
        row = db.session.execute(
            text("SELECT FINAL_APLESS FROM TEMP_CAFLESS WITH(NOLOCK) WHERE Apless = :apless"),
            {"apless": apless},
        ).fetchone()

        if not row or not row.FINAL_APLESS:
            return

        final_apless = row.FINAL_APLESS
        if final_apless == apless:
            return

        cfg    = current_app.config
        s3     = boto3.client(
            "s3",
            aws_access_key_id=cfg["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=cfg["AWS_SECRET_ACCESS_KEY"],
            region_name=cfg.get("AWS_REGION", "ap-southeast-1"),
        )
        bucket = cfg["AWS_S3_BUCKET"]

        prefix   = f"upload_doc/{apless}/{prechecking_id}/"
        paginator = s3.get_paginator("list_objects_v2")

        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                old_key = obj["Key"]
                new_key = old_key.replace(
                    f"upload_doc/{apless}/",
                    f"upload_doc/{final_apless}/",
                    1,
                )
                s3.copy_object(
                    Bucket=bucket,
                    CopySource={"Bucket": bucket, "Key": old_key},
                    Key=new_key,
                )
                db.session.execute(
                    text("""
                        UPDATE TEMP_CUSTOMER_DOCUMENT
                        SET AWSKey = :new_key, Apless = :final_apless
                        WHERE AWSKey = :old_key AND Prechecking_Id = :pid
                    """),
                    {
                        "new_key":      new_key,
                        "final_apless": final_apless,
                        "old_key":      old_key,
                        "pid":          prechecking_id,
                    },
                )
                s3.delete_object(Bucket=bucket, Key=old_key)

        db.session.commit()

    except Exception:
        db.session.rollback()
        current_app.logger.exception("_move_s3_files_to_final_apless error")