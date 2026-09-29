from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app import db
from app.utils.helpers.aws_helpers import copy_object  
_APP_TZ = ZoneInfo("Asia/Jakarta")

def _now() -> datetime:
    return datetime.now(_APP_TZ)

class CamCreationError(Exception):
    def __init__(self, message: str, field_errors: Optional[list[str]] = None):
        super().__init__(message)
        self.message = message
        self.field_errors = field_errors or [message]

def _claim_next_number(property_group_name: str) -> tuple[Optional[int], Optional[date]]:
    row = db.session.execute(
        text(
            "SELECT NextNumber, LastUpdate"
            "FROM TANUMBER WITH (UPDLOCK, HOLDLOCK) "
            "WHERE PropertyGroupName = :group_name"
        ),
        {"group_name": property_group_name},
    ).first()
    if row is None:
        return None, None
    return row.NextNumber, row.LastUpdate

def _store_next_number(property_group_name: str, next_number: int) -> None:
    db.session.execute(
        text(
            "UPDATE TANUMBER SET NextNumber = :next_number, LastUpdate = GETDATE() "
            "WHERE PropertyGroupName = :group_name"
        ),
        {"next_number": next_number, "group_name": property_group_name},
    )

def _generate_appl_no(emp_id: str) -> str:
    last4 = (emp_id or "")[-4:]
    group_name = f"APPL_NO{last4}"

    current_number, last_update = _claim_next_number(group_name)
    if current_number is None:
        raise CamCreationError("Cannot create CAM, please call helpdesk")

    this_month = _now().strftime("%Y-%m")
    last_update_month = last_update.strftime("%Y-%m") if last_update else None

    seq = current_number if last_update_month == this_month else 1
    seq_padded = str(seq).zfill(3)
    _store_next_number(group_name, seq + 1)

    now = _now()
    return f"{last4}{now.strftime('%y')}{now.strftime('%m')}{seq_padded}"

def _generate_cafequip_id() -> int:
    current_number, _ = _claim_next_number("CAFEQUIP_ID")
    if current_number is None:
        raise CamCreationError("Cannot create CAM, please call helpdesk (CAFEQUIP_ID not provisioned)")
    _store_next_number("CAFEQUIP_ID", current_number + 1)
    return current_number

def get_purpose_of_finance_options() -> list[dict]:
    rows = db.session.execute(
        text("SELECT PURPOFFINC, [DESC] FROM MSTPURPOFFINC WITH (NOLOCK) WHERE Flag_Active = '1'")
    ).all()
    return [{"value": r.PURPOFFINC, "label": r[1]} for r in rows]

_FINANCE_TYPE_FILTERS = {
    "1": "Cons_Leas IN ('C','F')",
    "2": "Cons_Leas IN ('C','F')",
    "3": "Cons_Leas IN ('F','S','I')",
    "4": "Cons_Leas IN ('S','M','W')",
}

def get_finance_type_options(purpoffinc: str, lessee_tp: str) -> list[dict]:
    if purpoffinc in _FINANCE_TYPE_FILTERS:
        where = _FINANCE_TYPE_FILTERS[purpoffinc]
    elif purpoffinc == "5":
        if lessee_tp == "PR":
            where = "Cons_Leas IN ('F','I','D')"
        elif lessee_tp == "PT":
            where = "Cons_Leas = 'I'"
        else:
            return []
    else:
        where = "Cons_Leas IN ('I')"

    rows = db.session.execute(
        text(f"SELECT Cons_Leas, name FROM MSTCFFL WITH (NOLOCK) WHERE {where} AND Flag_Active = '1'")
    ).all()
    return [{"value": r.Cons_Leas, "label": r.name} for r in rows]

@dataclass
class PortfolioLimitCheck:
    total_mitsui_d: float
    total_mitsui_m: float
    limit_bisa: float
    ok_lanjut_d: bool
    ok_lanjut_m: bool

def get_portfolio_limit_check() -> PortfolioLimitCheck:
    total_outs = _scalar("SELECT SUM(outstanding) AS totalOuts FROM V_CustomerOutstanding") or 0
    total_outs_d = _scalar(
        "SELECT SUM(outstanding) AS totalOuts FROM V_CustomerOutstanding a WHERE a.Cons_Leas = 'D'"
    ) or 0

    total_outs_m = _scalar(
        "SELECT SUM(OutsPrinc_ACC) AS totalOuts FROM V_CustomerOutstanding a WHERE a.Cons_Leas = 'M'"
    ) or 0

    opundis_d = _sum_undisbursed_net_finance(cons_leas="D")
    opundis_m = _sum_undisbursed_net_finance(cons_leas="M")

    total_mitsui_d = opundis_d + total_outs_d
    total_mitsui_m = opundis_m + total_outs_m
    total_mitsui_all = _sum_undisbursed_net_finance(cons_leas=None) + total_outs

    limit_bisa = total_mitsui_all * 25 / 100

    return PortfolioLimitCheck(
        total_mitsui_d=total_mitsui_d,
        total_mitsui_m=total_mitsui_m,
        limit_bisa=limit_bisa,
        ok_lanjut_d=total_mitsui_d > limit_bisa,
        ok_lanjut_m=total_mitsui_m > limit_bisa,
    )

def _scalar(sql: str, params: Optional[dict] = None):
    row = db.session.execute(text(sql), params or {}).first()
    return row[0] if row else None

def _sum_undisbursed_net_finance(cons_leas: Optional[str]) -> float:
    cons_leas_filter_a = " AND a.Cons_Leas = :cons_leas" if cons_leas else ""
    cons_leas_filter_b = " AND b.Cons_Leas = :cons_leas" if cons_leas else ""
    params = {"cons_leas": cons_leas} if cons_leas else {}

    sql = f"""
        SELECT a.APPL_NO, a.LEASE_NO, a.L_AMOUNT, a.SECURITY, a.OTHERLOAN, a.RENTAL, c.CREDITAMT, umf.NICKNAME
        FROM CLFCONT a WITH (NOLOCK)
            LEFT JOIN CAFCONT b WITH (NOLOCK) ON a.APPL_NO = b.APPL_NO
            LEFT JOIN CLFINSU c WITH (NOLOCK) ON a.LEASE_NO = c.LEASE_NO
            LEFT JOIN MCMORevisi g WITH (NOLOCK) ON a.APPL_NO = g.oldAppl_No
            LEFT JOIN TACrossNo h WITH (NOLOCK) ON a.LEASE_NO = h.CROSSNO
            INNER JOIN UMFBRANCH umf ON umf.BRANCH_CD = a.BRANCH_CD
        WHERE a.UPD_STAT = 'Y' AND a.EXECUTION IS NULL AND a.FLGDEL = '0'
            AND a.APPL_NO <> ISNULL(g.oldAppl_No, 0) AND h.CROSSNO IS NULL{cons_leas_filter_a}

        UNION

        SELECT b.APPL_NO, '' AS LEASE_NO, b.L_AMOUNT, b.SECURITY, b.OTHERLOAN, b.RENTAL, c.CREDITAMT, umf.NICKNAME
        FROM CAFCONT b WITH (NOLOCK)
            LEFT JOIN CAFINSU c WITH (NOLOCK) ON b.APPL_NO = c.APPL_NO
            LEFT JOIN MCMORevisi g WITH (NOLOCK) ON b.APPL_NO = g.oldAppl_No
            INNER JOIN UMFBRANCH umf ON umf.BRANCH_CD = b.BRANCH_CD
        WHERE b.DateTrans IS NULL AND b.APPL_NO <> ISNULL(g.oldAppl_No, 0){cons_leas_filter_b}
            AND b.APPL_NO IN (SELECT appl_no FROM MCMOCAMCOMPLETELIST WHERE Admsts = '1')
    """
    rows = db.session.execute(text(sql), params).all()

    total = 0.0
    for row in rows:
        if row.LEASE_NO:
            net_finance = _scalar(
                "SELECT Net_Finance FROM V_NetFinance WHERE LEASE_NO = :lease_no",
                {"lease_no": row.LEASE_NO},
            )
        else:
            net_finance = _scalar(
                "SELECT Net_Finance FROM V_NetFinance WHERE APPL_NO = :appl_no",
                {"appl_no": row.APPL_NO},
            )
        total += net_finance or 0
    return total

def get_dp_ratio_info() -> dict:
    ratio_row = db.session.execute(text("EXEC USP_CHECK_RATIO ''")).first()
    dp_row = db.session.execute(text("EXEC USP_CHECK_DP ''")).first()
    return {
        "ratioResult": ratio_row.hasil if ratio_row else None,
        "asOfDate": ratio_row.tgl_acuan if ratio_row else None,
        "periodFrom": ratio_row.tgl_from if ratio_row else None,
        "periodTo": ratio_row.tgl_to if ratio_row else None,
        "minDpInvestasiPct": dp_row.I if dp_row else None,
        "minDpMultigunaPct": dp_row.M if dp_row else None,
        "npfPct": dp_row.npf if dp_row else None,
    }

_REQUIRED_FIELD_MESSAGES = [
    ("purpoffinc", "Purpose of Finance must not empty"),
    ("fin_type", "Finance type must not empty"),
    ("ind_cor", "Customer type must not empty"),
    ("guarantor", "Guarantor availability must not empty"),
    ("new_car", "Vehicle condition must not empty"),
]

def validate_new_cam_fields(fields: dict) -> list[str]:
    errors = []
    for key, message in _REQUIRED_FIELD_MESSAGES:
        if not fields.get(key):
            errors.append(message)

    if fields.get("public") == "1" and not fields.get("boa"):
        errors.append("Beneficial Owner Availibility must not empty")
    if fields.get("boa") == "2" and not fields.get("bot"):
        errors.append("Beneficial Owner Type must not empty")

    return errors

def create_new_cam(
    *,
    apless: str,
    prechecking_id: str,
    lessee_tp: str,
    purpoffinc: str,
    fin_type: str,
    guarantor: str,
    new_car: str,
    repeat: str = "1",
    public: str = "",
    boa: str = "",
    bot: str = "",
    emp_id: str,
    branch_cd: str,
) -> dict:
    ind_cor = "1" if lessee_tp == "PR" else "2"

    errors = validate_new_cam_fields(
        {
            "purpoffinc": purpoffinc,
            "fin_type": fin_type,
            "ind_cor": ind_cor,
            "guarantor": guarantor,
            "new_car": new_car,
            "public": public,
            "boa": boa,
            "bot": bot,
        }
    )
    if errors:
        raise CamCreationError("; ".join(errors), field_errors=errors)

    has_guarantor = "0" if guarantor == "1" else "1" if guarantor == "2" else None
    if new_car == "1":
        condition, tahun = "USED", ""
    elif new_car == "2":
        condition, tahun = "NEW", str(_now().year)
    else:
        condition, tahun = None, None

    try:
        applno = _generate_appl_no(emp_id)

        db.session.execute(
            text(
                "INSERT INTO CAFCONT (APPL_NO, APLESS, CREATE_DATE, Disc_Cust, CURR_CODE, "
                "Cons_Leas, BRANCH_CD, CMO, HAS_GUARANTOR, purpoffinc, Cont_type, prechecking_id) "
                "VALUES (:applno, :apless, GETDATE(), '0', 'IDR', :cons_leas, :branch_cd, :cmo, "
                ":has_guarantor, :purpoffinc, 'NEW', :prechecking_id)"
            ),
            {
                "applno": applno,
                "apless": apless,
                "cons_leas": fin_type,
                "branch_cd": branch_cd,
                "cmo": emp_id,
                "has_guarantor": has_guarantor,
                "purpoffinc": purpoffinc,
                "prechecking_id": prechecking_id,
            },
        )

        cafequip_id = _generate_cafequip_id()
        db.session.execute(
            text(
                "INSERT INTO CAFEQUIP (CAFEQUIP_ID, APPL_NO, CONDITION, TAHUN) "
                "VALUES (:cafequip_id, :applno, :condition, :tahun)"
            ),
            {"cafequip_id": cafequip_id, "applno": applno, "condition": condition, "tahun": tahun},
        )

        db.session.commit()
    except CamCreationError:
        db.session.rollback()
        raise
    except Exception as exc:
        db.session.rollback()
        raise CamCreationError(f"Failed to create CAM: {exc}") from exc

    warnings: list[str] = []
    try:
        db.session.execute(
            text("EXEC USP_Copy_Document :prechecking_id, :applno"),
            {"prechecking_id": prechecking_id, "applno": applno},
        )
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        warnings.append(f"USP_Copy_Document failed: {exc}")

    try:
        db.session.execute(
            text("EXEC USP_CAM_REQUEST_MOVESIKDOC :prechecking_id, :applno"),
            {"prechecking_id": prechecking_id, "applno": applno},
        )
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        warnings.append(f"USP_CAM_REQUEST_MOVESIKDOC failed: {exc}")

    migration_errors = _migrate_temp_documents_to_s3(prechecking_id, applno)

    return {
        "applno": applno,
        "apless": apless,
        "finType": fin_type,
        "indCor": ind_cor,
        "repeat": repeat,
        "guarantor": guarantor,
        "newCar": new_car,
        "status": "New",
        "purpoffinc": purpoffinc,
        "contype": "NEW",
        "boa": boa,
        "bot": bot,
        "public": public,
        "warnings": warnings,
        "documentMigrationErrors": migration_errors,
    }

def _migrate_temp_documents_to_s3(prechecking_id: str, applno: str) -> list[str]:
    rows = db.session.execute(
        text(
            "SELECT DISTINCT cd.Apless, cd.Prechecking_Id, DocumentName, cd.AWSKey, cl.FINAL_APLESS "
            "FROM TEMP_CUSTOMER_DOCUMENT cd "
            "INNER JOIN TEMP_CAFLESS cl ON cl.Apless = cd.Apless AND cd.Prechecking_Id = cl.Prechecking_Id "
            "WHERE cd.Prechecking_Id = :prechecking_id"
        ),
        {"prechecking_id": prechecking_id},
    ).all()

    errors = []
    for row in rows:
        apless_old, apless_new = row.Apless, row.FINAL_APLESS
        aws_key_old = row.AWSKey
        if not aws_key_old:
            continue
        aws_key_new = aws_key_old.replace(apless_old, apless_new).replace(prechecking_id, applno)
        if not copy_object(aws_key_old, aws_key_new):
            errors.append(f"{aws_key_old}: copy_object failed (see server logs — aws_helper logs a warning rather than raising)")
    return errors