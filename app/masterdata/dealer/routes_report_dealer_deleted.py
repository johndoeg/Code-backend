from flask import Blueprint, jsonify, request, current_app
from app import db
from sqlalchemy import text
from datetime import datetime

deleted_dealer_report_bp = Blueprint("deleted_dealer_report_bp", __name__, url_prefix="/MasterData")

def _fmt_date(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d-%m-%Y")
    return str(value)


@deleted_dealer_report_bp.route("/api/branches")
def get_branches():
    branch_cd = request.args.get("branch_cd", "100")
    try:
        if branch_cd != "100":
            stmt = text(
                "SELECT BRANCH_CD, BRANCH_NAME FROM UMFBRANCH WITH (NOLOCK) "
                "WHERE BRANCH_CD = :branch_cd ORDER BY BRANCH_NAME"
            )
            params = {"branch_cd": branch_cd}
        else:
            stmt = text(
                "SELECT BRANCH_CD, BRANCH_NAME FROM UMFBRANCH WITH (NOLOCK) "
                "ORDER BY BRANCH_NAME"
            )
            params = {}

        result = db.session.execute(stmt, params)
        branches = [
            {"BRANCH_CD": row.BRANCH_CD, "BRANCH_NAME": row.BRANCH_NAME}
            for row in result
        ]
        return jsonify(branches)

    except Exception:
        current_app.logger.exception("Branch list error")
        return jsonify([]), 500

@deleted_dealer_report_bp.route("/api/dealer-deleted-report")
def get_dealer_deleted_report():
    branch: str = request.args.get("branch", "").strip()
    cekcek: str = request.args.get("cekcek", "").strip()
    lempar: str = request.args.get("lempar", "").strip()

    try:
        stmt = text("""
            SELECT
                del.form_no,
                br.branch_name,
                del.supp,
                sup.[name],
                sup.[address],
                sup.created_by,
                sup.CREATE_DATE  AS create_date,
                app.fullname     AS delete_by,
                del.delete_date,
                del.reason
            FROM  clfsupp_delete del
            INNER JOIN clfsupp    sup ON sup.supp        = del.supp
            LEFT  JOIN umfbranch  br  ON br.branch_cd    = sup.branch_cd
            INNER JOIN app_usrmst app ON app.employee_id = del.delete_by
            WHERE
                (sup.branch_cd = :branch OR :branch = '000')
                AND (
                    (del.supp = :lempar            AND :cekcek = '1')
                    OR (sup.name LIKE :lempar_like AND :cekcek = '2')
                    OR (:cekcek = '')
                )
                AND sup.flgdel = '1'
            ORDER BY sup.[name] ASC
        """)

        result = db.session.execute(
            stmt,
            {
                "branch":      branch,
                "cekcek":      cekcek,
                "lempar":      lempar,
                "lempar_like": f"%{lempar}%",
            },
        )

        data = [
            {
                "form_no":     row.form_no     or "",
                "branch_name": row.branch_name or "",
                "supp":        row.supp        or "",
                "name":        row.name        or "",
                "address":     row.address     or "",
                "created_by":  row.created_by  or "",
                "create_date": _fmt_date(row.create_date),
                "delete_by":   row.delete_by   or "",
                "delete_date": _fmt_date(row.delete_date),
                "reason":      row.reason      or "",
            }
            for row in result
        ]

        return jsonify({"data": data, "total": len(data)})

    except Exception:
        current_app.logger.exception("Dealer deleted report error")
        return jsonify({"data": [], "total": 0}), 500