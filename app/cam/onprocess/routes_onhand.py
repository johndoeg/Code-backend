from flask import Blueprint, jsonify, request, current_app, session
from app import db
from app.auth.decorators import login_required
from sqlalchemy import text

onhand_cam_bp = Blueprint("onhand_cam_bp", __name__, url_prefix="/CAM")

def _get_session_ctx() -> dict:
    return {
        "emp_id":       session.get("emp_id", ""),
        "username":     session.get("username", ""),
        "access_level": session.get("accesslevel", ""),
        "branch_cd":    session.get("branchcode", ""),
    }

def _call_onhand_sp(emp_id: str, username: str, offset: int, end: int,
                    order: str, search_by: str, search_val: str):

    if search_val and search_by == "1":
        sp = ("EXEC USP_CAM_ONHANDSEARCHBYCAM "
              ":emp_id, :username, :offset, :end, :order, :search_val")
        params = dict(emp_id=emp_id, username=username, offset=offset,
                      end=end, order=order, search_val=search_val)
    elif search_val and search_by == "2":
        sp = ("EXEC USP_CAM_ONHANDSEARCHBYNM "
              ":emp_id, :username, :offset, :end, :order, :search_val")
        params = dict(emp_id=emp_id, username=username, offset=offset,
                      end=end, order=order, search_val=search_val)
    else:
        sp = ("EXEC USP_CAM_ONHAND "
              ":emp_id, :username, :offset, :end, :order")
        params = dict(emp_id=emp_id, username=username,
                      offset=offset, end=end, order=order)
        
    result   = db.session.execute(text(sp), params)
    all_rows = result.mappings().all()

    if not all_rows:
        return 0, []

    total = int(all_rows[0]["TOTAL"]) if "TOTAL" in all_rows[0] else 0
    return total, all_rows

@onhand_cam_bp.route("/onhand")
@login_required
def get_cam_onhand():
    ctx         = _get_session_ctx()
    emp_id      = ctx["emp_id"]
    username    = ctx["username"]
    access_level = ctx["access_level"]
    
    page       = request.args.get("page",       1,  type=int)
    limit      = request.args.get("limit",      25, type=int)
    search_by  = request.args.get("search_by",  "")
    search_val = request.args.get("search_val", "")

    offset = (page - 1) * limit
    end    = page * limit
    order  = "CMO" if access_level == "CMO" else ""

    is_approver_row = access_level not in ("CMO", "HD")

    try:
        total, rows = _call_onhand_sp(
            emp_id, username, offset, end, order, search_by, search_val
        )

        data = []
        seen_appl = set()

        for row in rows:
            appl_no = str(row.get("APPL_NO", "")).strip()
            if not appl_no or appl_no in seen_appl:
                continue
            seen_appl.add(appl_no)

            tgl_raw = row.get("tgl")
            tgl = (
                tgl_raw.strftime("%d-%m-%Y %H:%M:%S")
                if tgl_raw and tgl_raw.year != 2011
                else ""
            )

            str_revisi   = str(row.get("str_revisi",   "") or "")
            str_multiple = str(row.get("str_multiple", "") or "")

            namacmo_raw = str(row.get("NAMACMO", "") or "")
            can_manage = namacmo_raw in ("NAMACMO", "Reject")

            namacmo = namacmo_raw
            color = "revise" if str_revisi else "default"
            reject_person  = ""
            reject_comment = ""

            if namacmo_raw == "NAMACMO":
                namacmo = username
            elif namacmo_raw == "Reject":
                rj = db.session.execute(
                    text("SELECT TOP 1 appr_id, LEFT(comment,10) AS comment "
                         "FROM MCMOCAMStatus WITH(NOLOCK) "
                         "WHERE APPL_NO=:appl AND appr_sts='R' "
                         "ORDER BY CreateDate DESC"),
                    {"appl": appl_no}
                ).mappings().first()

                if not rj:
                    rj = db.session.execute(
                        text("SELECT TOP 1 appr_id, LEFT(comment,10) AS comment "
                             "FROM MCMOCAMOUTSSTATUS WITH(NOLOCK) "
                             "WHERE APPL_NO=:appl AND appr_sts='R' "
                             "ORDER BY Create_Date DESC"),
                        {"appl": appl_no}
                    ).mappings().first()

                if rj:
                    reject_person  = rj["appr_id"]
                    reject_comment = rj["comment"]
                    color = "reject"
                namacmo = ""

            peer_rejects = db.session.execute(
                text("SELECT DISTINCT APPR_STS, APPR_ID "
                     "FROM Mcmocamstatus WITH(NOLOCK) "
                     "WHERE APPR_STS LIKE '%R%' AND APPL_NO=:appl "
                     "AND APPR_ID IN (SELECT APPR_ID FROM MCMOCAMStatus "
                     "               WHERE APPL_NO=:appl AND APPR_STS LIKE '%R%')"),
                {"appl": appl_no}
            ).mappings().all()

            for pr in peer_rejects:
                appr_id = pr["APPR_ID"]
                peer_cam = db.session.execute(
                    text("SELECT ACCESSCAM FROM APP_USRMST WHERE USERNAME=:uid"),
                    {"uid": appr_id}
                ).scalar()
                own_cam = db.session.execute(
                    text("SELECT ACCESSCAM FROM APP_USRMST WHERE USERNAME=:uid"),
                    {"uid": username}
                ).scalar()
                if (peer_cam and peer_cam == own_cam) or appr_id == username:
                    color = "reject"
                    break

            extra = db.session.execute(
                text("SELECT c.RESTRUCTURING_CHANGE, b.LESSEE_NM, d.GO_PUBLIC "
                     "FROM CAFCONT a WITH(NOLOCK) "
                     "LEFT JOIN CAFLESS b WITH(NOLOCK) "
                     "       ON a.APLESS = b.APLESS "
                     "LEFT JOIN CAFCONT_RESTRUCTURING c WITH(NOLOCK) "
                     "       ON a.APPL_NO = c.APPL_NO "
                     "LEFT JOIN CAFLESS_DETAIL d WITH(NOLOCK) "
                     "       ON a.APLESS = d.APLESS "
                     "WHERE a.APPL_NO=:appl"),
                {"appl": appl_no}
            ).mappings().first()
            r_change  = str(extra["RESTRUCTURING_CHANGE"] or "") if extra else ""
            go_public = str(extra["GO_PUBLIC"]            or "") if extra else ""
            lessee_nm = str(extra["LESSEE_NM"]             or "") if extra else ""

            if is_approver_row:
                bo_row = db.session.execute(
                    text("SELECT BO_TYPE FROM BENEFICIARY_LINK WITH(NOLOCK) "
                         "WHERE APPL_NO=:appl"),
                    {"appl": appl_no}
                ).mappings().first()

                menmen = 10 if bo_row else 9

                outs_row = db.session.execute(
                    text("SELECT SUM(OUTS) AS tot_outs FROM CAFCUST_OUTS WITH(NOLOCK) "
                         "WHERE APPL_NO=:appl "
                         "AND ASOF=(SELECT MAX(ASOF) FROM CAFCUST_OUTS WITH(NOLOCK) "
                         "          WHERE APPL_NO=:appl)"),
                    {"appl": appl_no}
                ).mappings().first()
                tot_outs = float(outs_row["tot_outs"] or 0) if outs_row else 0.0

                picked_by = db.session.execute(
                    text("SELECT Picked_by FROM MCMOCAMCOMPLETELIST "
                         "WHERE APPL_NO=:appl"),
                    {"appl": appl_no}
                ).scalar() or ""

                mstr_ca = db.session.execute(
                    text("SELECT MSTR_CA FROM TAMASTER WHERE APPL_NO=:appl"),
                    {"appl": appl_no}
                ).scalar() or ""
            else:
                menmen    = 0
                tot_outs  = 0.0
                picked_by = ""
                mstr_ca   = ""

            data.append({
                "appl_no":        appl_no,
                "tgl":            tgl,
                "cons_leas":      str(row.get("Cons_Leas", "") or ""),
                "lessee_nm":      lessee_nm,
                "namacmo":        namacmo,
                "can_manage":     can_manage,
                "reject_person":  reject_person,
                "reject_comment": reject_comment,
                "cbgnow":         str(row.get("cbgnow",  "") or ""),
                "cmo_now":        str(row.get("CMOnow",  "") or ""),
                "brch_code":      str(row.get("brch_code", "") or ""),
                "color":          color,
                "str_revisi":     str_revisi,
                "str_multiple":   str_multiple,
                "fin_type":       str(row.get("Cons_Leas",   "") or ""),
                "ind_cor":        str(row.get("ind_cor",     "") or ""),
                "guarantor":      str(row.get("guarantor",   "") or ""),
                "new_car":        str(row.get("new_car",     "") or ""),
                "tenor":          str(row.get("tenor",       "") or ""),
                "c2c":            str(row.get("c2c",         "") or ""),
                "purpoffinc":     str(row.get("PURPOFFINC",  "") or ""),
                "cont_type":      str(row.get("Cont_type",   "") or ""),
                "apless":         str(row.get("apless",      "") or ""),
                "r_change":       r_change,
                "go_public":      go_public,
                "menmen":         menmen,
                "tot_outs":       tot_outs,
                "picked_by":      picked_by,
                "mstr_ca":        mstr_ca,
                "cbgnow_co":      str(row.get("cbgnow", "") or "") == "CO",
            })

        return jsonify({"data": data, "total": total})

    except Exception:
        current_app.logger.exception("CAM onhand error")
        return jsonify({"error": "Failed to load data"}), 500

@onhand_cam_bp.route("/onhand/send", methods=["POST"])
@login_required
def send_cam():
    ctx      = _get_session_ctx()
    body     = request.get_json(force=True) or {}
    appl_nos = body.get("appl_nos", [])
    multiple = bool(body.get("multiple", False))

    if not appl_nos:
        return jsonify({"success": False, "message": "No items selected"}), 400

    if multiple:
        in_clause = ", ".join(f"'{a}'" for a in appl_nos)
        try:
            row = db.session.execute(
                text(f"""
                    SELECT COUNT(DISTINCT
                        CONCAT(
                            LTRIM(RTRIM(b.APLESS)), '|',
                            LTRIM(RTRIM(a.SUPP)),   '|',
                            LTRIM(RTRIM(a.PARK_LOC)), '|',
                            CAST(b.ADV_ARR AS VARCHAR), '|',
                            CAST(b.TENOR  AS VARCHAR),  '|',
                            c.ins_cd, '|',
                            LTRIM(RTRIM(zz.acc_no)), '|',
                            LTRIM(RTRIM(zz.acc_nm)), '|',
                            LTRIM(RTRIM(zz.BANK))
                        )
                    ) AS cnt
                    FROM CAFEQUIP a WITH(NOLOCK)
                        INNER JOIN CAFCONT       b  WITH(NOLOCK) ON a.APPL_NO = b.APPL_NO
                        INNER JOIN CAFINSU       c  WITH(NOLOCK) ON b.APPL_NO = c.APPL_NO
                        INNER JOIN cafdisbacc    zz             ON zz.APPL_NO = a.APPL_NO
                    WHERE b.APPL_NO IN ({in_clause})
                      AND zz.SPLIT = 'Dealer'
                """)
            ).scalar()

            if row != 1:
                return jsonify({
                    "success": False,
                    "message": (
                        "Multiple CAM requires Customer, Dealer, "
                        "First Installment Payment, Parking Location, "
                        "Tenor, Contract Type, Insurance Company, "
                        "Dealer Bank Account must be the same."
                    ),
                }), 400

        except Exception:
            current_app.logger.exception("Multiple CAM validation error")
            return jsonify({"success": False, "message": "Validation failed"}), 500

    return jsonify({
        "success":  True,
        "redirect": f"/cam_send_cmo?appl_nos={','.join(appl_nos)}&multiple={int(multiple)}",
    })

@onhand_cam_bp.route("/onhand/pick", methods=["POST"])
@login_required
def pick_cam():
    ctx     = _get_session_ctx()
    emp_id  = ctx["emp_id"]
    body    = request.get_json(force=True) or {}
    appl_nos = body.get("appl_nos", [])

    if not appl_nos:
        return jsonify({"success": False, "message": "No items selected"}), 400

    try:
        for appl in appl_nos:
            db.session.execute(
                text("EXEC USP_SAVE_CRH_PICK :emp_id, :appl_no"),
                {"emp_id": emp_id, "appl_no": appl},
            )
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("CRH pick error")
        return jsonify({"success": False, "message": "Save failed"}), 500
    
@onhand_cam_bp.route("/onhand/<appl_no>", methods=["DELETE"])
@login_required
def delete_cam(appl_no: str):
    apless = request.args.get("apless", "")
    try:
        db.session.execute(
            text("EXEC USP_DELETE_CAM :apless, :appl_no"),
            {"apless": apless, "appl_no": appl_no},
        )
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("CAM delete error")
        return jsonify({"success": False, "message": "Delete failed"}), 500

@onhand_cam_bp.route("/onhand/<appl_no>/reject-watchlist", methods=["POST"])
@login_required
def reject_watchlist(appl_no: str):
    apless = (request.get_json(force=True) or {}).get("apless", "")
    try:
        db.session.execute(
            text("EXEC USP_REJ_WATCHLIST :apless, :appl_no"),
            {"apless": apless, "appl_no": appl_no},
        )
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Reject watchlist error")
        return jsonify({"success": False, "message": "Action failed"}), 500
    
@onhand_cam_bp.route('/onhand/validate', methods=['POST'])
@login_required
def validate_cam():
    body = request.get_json(force=True) or {}
    appl_no = body.get("appl_no")
    if not appl_no:
        return jsonify({"blocked": False})

    access_level = session.get("accesslevel", "")
    username = session.get("username", "")

    if access_level in ("CMO", "NCH", "ODH"):
        return jsonify({"blocked": False})

    try:
        row = db.session.execute(
            text("""
                SELECT TOP 1 APPR_STS, APPR_ID, APPR_ID_From
                FROM MCMOCAMStatus WITH (NOLOCK)
                WHERE APPL_NO = :appl_no
                ORDER BY No DESC
            """),
            {"appl_no": appl_no},
        ).mappings().first()

        if row is None:
            return jsonify({"blocked": False})

        appr_sts = row["APPR_STS"]
        appr_id = row["APPR_ID"]
        appr_id_from = row["APPR_ID_From"]

        if appr_sts == 'T' and appr_id == username:
            return jsonify({
                "blocked": True,
                "message": f"this CAM has been withdraw by {appr_id_from}",
            })
        elif appr_sts == 'R' and appr_id != username:
            return jsonify({
                "blocked": True,
                "message": f"this CAM has been rejected by {appr_id}",
            })

        return jsonify({"blocked": False})

    except Exception:
        current_app.logger.exception("validate_cam error")
        return jsonify({"blocked": False})