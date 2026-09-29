from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any, NamedTuple, Optional

from sqlalchemy import text
from app import db

TYPE_DISBURSEMENT = "1"
TYPE_UNDISBURSEMENT = "2"
TYPE_UNAPPROVE = "3"
TYPE_GROUP = "4"
TYPE_GUARANTOR = "5"

_SUMMARY_KEYS = {
    1: "disbursement",
    2: "undisbursement",
    3: "unapprove",
    4: "group",
    5: "guarantor",
}

def _n(value: Any) -> float:
    if value is None:
        return 0.0
    return float(value)

def _round2(value: float) -> float:
    return math.floor(abs(value) * 100 + 0.5) / 100 * (-1 if value < 0 else 1)

def _ratio(numerator: float, denominator: float) -> float:
    if not numerator or not denominator:
        return 0.0
    return _round2(numerator / denominator * 100)

def get_latest_snapshot(appl_no: str) -> dict[str, Any]:
    row = db.session.execute(text("""
        SELECT TOP 1 ASOF, OUTS_NOTES
        FROM CAFCUST_OUTS WITH (NOLOCK)
        WHERE APPL_NO = :appl_no
        ORDER BY ASOF DESC
    """), {"appl_no": appl_no}).fetchone()

    if not row or row.ASOF is None:
        return {"asof": None, "notes": ""}

    return {"asof": row.ASOF, "notes": row.OUTS_NOTES or ""}

def empty_exposure_summary() -> dict[str, Any]:
    zero = {"unit": 0, "amount": 0.0}
    summary = {name: dict(zero) for name in _SUMMARY_KEYS.values()}
    summary["total"] = dict(zero)
    return summary

def get_exposure_summary(appl_no: str, asof) -> dict[str, Any]:
    if asof is None:
        return empty_exposure_summary()

    rows = db.session.execute(text("""
        SELECT [TYPE], UNIT, OUTS
        FROM CAFCUST_OUTS WITH (NOLOCK)
        WHERE APPL_NO = :appl_no AND ASOF = :asof
        ORDER BY [TYPE]
    """), {"appl_no": appl_no, "asof": asof}).fetchall()

    by_type = {t: {"unit": 0, "amount": 0.0} for t in range(1, 6)}
    for r in rows:
        t = int(r.TYPE)
        if t in by_type:
            by_type[t]["unit"] += int(r.UNIT or 0)
            by_type[t]["amount"] += _n(r.OUTS)

    summary = {_SUMMARY_KEYS[t]: v for t, v in by_type.items()}
    summary["total"] = {
        "unit": sum(v["unit"] for v in by_type.values()),
        "amount": sum(v["amount"] for v in by_type.values()),
    }
    
    return summary

def _fetch_outstanding_rows(appl_no: str, type_code: str) -> list[dict]:
    rs = db.session.execute(
        text("EXEC USP_CAM_OUTSTANDING :appl_no, :type_code"),
        {"appl_no": appl_no, "type_code": type_code},
    )
    return [dict(r._mapping) for r in rs.fetchall()]

def build_disbursement_section(appl_no: str) -> dict[str, Any]:
    rows = _fetch_outstanding_rows(appl_no, TYPE_DISBURSEMENT)

    out_rows: list[dict] = []
    tot_rental = tot_op = tot_mrkt = 0.0

    tot_mrkt_cross = tot_mrkt_noncross = 0.0
    rental_cross = rental_noncross = 0.0

    op_cross = op_noncross = 0.0
    op_leasing_tot = op_consumer_tot = op_install_tot = 0.0
    op_finance_tot = op_sale_tot = 0.0
    unit_leasing = unit_consumer = unit_install = unit_finance = unit_sale = 0

    for i, row in enumerate(rows, start=1):
        op = _n(row.get("op"))
        rental = _n(row.get("RENTAL"))
        market_price = _n(row.get("MARKETPRICE"))
        remark = row.get("REMARK") or ""
        cons_leas = row.get("Cons_Leas") or ""

        tot_rental += rental
        tot_op += op
        tot_mrkt += market_price

        if remark == "Cross Collateral":
            rental_cross += rental
            tot_mrkt_cross += market_price
            op_cross += op
        else:
            rental_noncross += rental
            tot_mrkt_noncross += market_price
            op_noncross += op

        if cons_leas == "I":
            unit_install += 1
            op_install_tot += op
        elif cons_leas == "S":
            unit_sale += 1
            op_sale_tot += op
        elif cons_leas == "C":
            unit_consumer += 1
            op_consumer_tot += op
        elif cons_leas == "L":
            unit_leasing += 1
            op_leasing_tot += op
        if cons_leas == "F":
            unit_finance += 1
            op_finance_tot += op

        out_rows.append({
            "no": i,
            "contractNo": row.get("LEASE_NO"),
            "brandType": row.get("brand_type"),
            "carYear": row.get("TAHUN"),
            "marketPrice": market_price,
            "outstandingPrincipal": op,
            "installmentPerMonth": rental,
            "term": row.get("TERM"),
            "tenor": row.get("tenor"),
            "paymentStatus": row.get("PAYMENTSTATUS"),
            "userOfCar": row.get("USERUSAGE"),
            "loanRatio": _round2(_n(row.get("loan_ratio"))),
            "branch": row.get("NickName"),
            "remark": remark,
            "leaseKey": row.get("LEASE_NO") or "",
        })

    return {
        "rows": out_rows,
        "subTotal": {
            "marketPrice": tot_mrkt,
            "outstandingPrincipal": tot_op,
            "installmentPerMonth": tot_rental,
            "loanRatioPct": _ratio(tot_op, tot_mrkt),
        },
        "crossCollateral": {
            "cross": {
                "marketPrice": tot_mrkt_cross,
                "outstandingPrincipal": op_cross,
                "installmentPerMonth": rental_cross,
                "loanRatioPct": _ratio(op_cross, tot_mrkt_cross),
            },
            "nonCross": {
                "marketPrice": tot_mrkt_noncross,
                "outstandingPrincipal": op_noncross,
                "installmentPerMonth": rental_noncross,
                "loanRatioPct": _ratio(op_noncross, tot_mrkt_noncross),
            },
            "totalExposure": {
                "marketPrice": tot_mrkt_cross + tot_mrkt_noncross,
                "outstandingPrincipal": op_cross + op_noncross,
                "installmentPerMonth": rental_cross + rental_noncross,
                "loanRatioPct": _ratio(op_cross + op_noncross, tot_mrkt_cross + tot_mrkt_noncross),
            },
        },
        "financeTypeBreakdown": {
            "leasing": {"outstandingPrincipal": op_leasing_tot, "units": unit_leasing},
            "consumerFinance": {"outstandingPrincipal": op_consumer_tot, "units": unit_consumer},
            "installmentFinancing": {"outstandingPrincipal": op_install_tot, "units": unit_install},
            "financeLease": {"outstandingPrincipal": op_finance_tot, "units": unit_finance},
            "saleLeaseback": {"outstandingPrincipal": op_sale_tot, "units": unit_sale},
        },
    }

def _build_simple_section(
    appl_no: str,
    type_code: str,
    *,
    contract_no_field: str = "LEASE_NO",
    fallback_field: str = "APPL_NO",
    lease_key_field: str = "LEASE_NO",
    lease_key_fallback_field: Optional[str] = None,
) -> dict[str, Any]:
    rows = _fetch_outstanding_rows(appl_no, type_code)
    out_rows: list[dict] = []
    tot_rental = tot_op = tot_mrkt = 0.0

    for i, row in enumerate(rows, start=1):
        op = _n(row.get("op"))
        rental = _n(row.get("RENTAL"))
        market_price = _n(row.get("MARKETPRICE"))
        tot_rental += rental
        tot_op += op
        tot_mrkt += market_price

        contract_no = row.get(contract_no_field) or row.get(fallback_field)
        lease_key = row.get(lease_key_field) or ""
        if not lease_key and lease_key_fallback_field:
            lease_key = row.get(lease_key_fallback_field) or ""

        out_rows.append({
            "no": i,
            "contractNo": contract_no,
            "brandType": row.get("brand_type"),
            "carYear": row.get("TAHUN"),
            "marketPrice": market_price,
            "outstandingPrincipal": op,
            "installmentPerMonth": rental,
            "term": row.get("TERM"),
            "tenor": row.get("tenor"),
            "paymentStatus": row.get("PAYMENTSTATUS"),
            "userOfCar": row.get("USERUSAGE"),
            "loanRatio": _round2(_n(row.get("loan_ratio"))),
            "branch": row.get("NickName"),
            "consLeas": row.get("Cons_Leas"),
            "applNo": row.get("APPL_NO"),
            "leaseKey": lease_key,
        })

    return {
        "rows": out_rows,
        "subTotal": {
            "marketPrice": tot_mrkt,
            "outstandingPrincipal": tot_op,
            "installmentPerMonth": tot_rental,
            "loanRatioPct": _ratio(tot_op, tot_mrkt),
        },
    }

def build_undisbursement_section(appl_no: str) -> dict[str, Any]:
    return _build_simple_section(appl_no, TYPE_UNDISBURSEMENT, lease_key_field="APPL_NO")

def build_unapprove_section(appl_no: str) -> dict[str, Any]:
    return _build_simple_section(
        appl_no, TYPE_UNAPPROVE,
        contract_no_field="APPL_NO", fallback_field="APPL_NO",
        lease_key_field="APPL_NO",
    )

def build_group_section(appl_no: str) -> dict[str, Any]:
    return _build_simple_section(
        appl_no, TYPE_GROUP,
        lease_key_field="LEASE_NO", lease_key_fallback_field="APPL_NO",
    )

def build_guarantor_section(appl_no: str) -> dict[str, Any]:
    return _build_simple_section(appl_no, TYPE_GUARANTOR)

def compute_grand_totals(dis, undis, unapp, group, gua) -> dict[str, Any]:
    def g(section, key):
        return section["subTotal"][key]

    mrkt_1 = g(dis, "marketPrice") + g(undis, "marketPrice") + g(unapp, "marketPrice")
    op_1 = g(dis, "outstandingPrincipal") + g(undis, "outstandingPrincipal") + g(unapp, "outstandingPrincipal")
    rental_1 = g(dis, "installmentPerMonth") + g(undis, "installmentPerMonth") + g(unapp, "installmentPerMonth")

    has_group_or_guarantor = bool(group["rows"]) or bool(gua["rows"])

    mrkt_all = mrkt_1 + g(group, "marketPrice") + g(gua, "marketPrice")
    op_all = op_1 + g(group, "outstandingPrincipal") + g(gua, "outstandingPrincipal")
    rental_all = rental_1 + g(group, "installmentPerMonth") + g(gua, "installmentPerMonth")

    return {
        "disUndisUnapp": {
            "marketPrice": mrkt_1,
            "outstandingPrincipal": op_1,
            "installmentPerMonth": rental_1,
            "loanRatioPct": _ratio(op_1, mrkt_1),
        },
        "all": ({
            "marketPrice": mrkt_all,
            "outstandingPrincipal": op_all,
            "installmentPerMonth": rental_all,
            "loanRatioPct": _ratio(op_all, mrkt_all),
        } if has_group_or_guarantor else None),
    }

class FundModalTotals(NamedTuple):
    total_fd_dana: float
    total_fmu_modal: float
    total_fund: float

def compute_fund_and_modal_totals(apless: str, lessee_no: str, appl_no: str) -> FundModalTotals:
    return FundModalTotals(total_fd_dana=0.0, total_fmu_modal=0.0, total_fund=0.0)

def get_full_view(appl_no: str) -> dict[str, Any]:
    snapshot = get_latest_snapshot(appl_no)
    summary = get_exposure_summary(appl_no, snapshot["asof"])

    dis = build_disbursement_section(appl_no)
    undis = build_undisbursement_section(appl_no)
    unapp = build_unapprove_section(appl_no)
    group = build_group_section(appl_no)
    gua = build_guarantor_section(appl_no)
    grand = compute_grand_totals(dis, undis, unapp, group, gua)

    asof = snapshot["asof"]
    return {
        "blocked": False,
        "calcDate": asof.isoformat() if hasattr(asof, "isoformat") else asof,
        "notes": snapshot["notes"],
        "summary": summary,
        "disbursement": dis,
        "undisbursement": undis,
        "unapprove": unapp,
        "group": group,
        "guarantor": gua,
        "grandTotal": grand,
    }

def _to_amount(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "").strip() or 0)
    except ValueError:
        return 0.0

def save_rows(appl_no: str, rows: Optional[list[dict]], type_code: str, *, editable_payment_status: bool) -> list[str]:
    errors: list[str] = []
    for row in rows or []:
        lease_no = row.get("leaseKey")
        if lease_no is None:
            lease_no = row.get("contractNo") or ""
        market_price = _to_amount(row.get("marketPrice"))

        if market_price < 1:
            errors.append("Market Price must not be 0 or empty")

        if editable_payment_status:
            db.session.execute(text("""
                UPDATE CAFLR SET MARKETPRICE = :mp, PAYMENTSTATUS = :ps
                WHERE APPL_NO = :appl_no AND LEASE_NO = :lease_no AND [TYPE] = :type_code
            """), {
                "mp": market_price, "ps": row.get("paymentStatus") or "",
                "appl_no": appl_no, "lease_no": lease_no, "type_code": type_code,
            })
        else:
            db.session.execute(text("""
                UPDATE CAFLR SET MARKETPRICE = :mp
                WHERE APPL_NO = :appl_no AND LEASE_NO = :lease_no AND [TYPE] = :type_code
            """), {
                "mp": market_price, "appl_no": appl_no, "lease_no": lease_no, "type_code": type_code,
            })
    return errors

def save_next(appl_no: str, payload: dict[str, Any]) -> tuple[bool, str]:
    errors: list[str] = []
    errors += save_rows(appl_no, payload.get("disbursementRows"), TYPE_DISBURSEMENT, editable_payment_status=True)
    errors += save_rows(appl_no, payload.get("undisbursementRows"), TYPE_UNDISBURSEMENT, editable_payment_status=True)
    errors += save_rows(appl_no, payload.get("unapproveRows"), TYPE_UNAPPROVE, editable_payment_status=False)
    errors += save_rows(appl_no, payload.get("groupRows"), TYPE_GROUP, editable_payment_status=True)
    errors += save_rows(appl_no, payload.get("guarantorRows"), TYPE_GUARANTOR, editable_payment_status=True)

    snapshot = get_latest_snapshot(appl_no)
    if snapshot["asof"] is None:
        db.session.commit()
        return False, "Please calculate Outstanding"

    db.session.execute(text("""
        UPDATE CAFCUST_OUTS SET OUTS_NOTES = :notes
        WHERE APPL_NO = :appl_no AND ASOF = :asof
    """), {"notes": payload.get("notes") or "", "appl_no": appl_no, "asof": snapshot["asof"]})

    db.session.commit()

    if errors:
        seen = []
        for e in errors:
            if e not in seen:
                seen.append(e)
        return False, "<br>".join(seen)

    return True, ""

def _calc_marketprice(appl_no: str = "", lease_no: str = "") -> float:
    row = db.session.execute(
        text("EXEC USP_CALC_MARKETPRICE :appl_no, :lease_no"),
        {"appl_no": appl_no or "", "lease_no": lease_no or ""},
    ).fetchone()
    return _n(row.marketprice) if row else 0.0

def _compute_jlh_byr(lease_no: str, *, require_execution_for_fallback: bool = False) -> int:
    if not lease_no:
        return 0

    row_terminate = db.session.execute(text("""
        SELECT TOP 1 [status], b.TENOR
        FROM bgiro a WITH (NOLOCK)
            INNER JOIN clfcont b WITH (NOLOCK) ON a.LEASE_NO = b.LEASE_NO
        WHERE a.LEASE_NO = :lease_no
        ORDER BY payment DESC, period DESC
    """), {"lease_no": lease_no}).fetchone()

    status = row_terminate.status if row_terminate else None
    if status == "T":
        return int(row_terminate.TENOR or 0)

    row1 = db.session.execute(text("""
        SELECT COUNT(payment) AS jlh_byr, b.ADV_ARR
        FROM bgiro a WITH (NOLOCK)
            INNER JOIN clfcont b WITH (NOLOCK) ON a.LEASE_NO = b.LEASE_NO
        WHERE a.LEASE_NO = :lease_no
            AND PAYMENT IS NOT NULL
            AND STATUS NOT IN ('T', 'P')
        GROUP BY b.ADV_ARR
    """), {"lease_no": lease_no}).fetchone()

    base = int(row1.jlh_byr) if row1 else 0
    if row1 and row1.ADV_ARR == "V":
        return base + 1

    if require_execution_for_fallback:
        row2 = db.session.execute(text("""
            SELECT ADV_ARR
            FROM clfcont WITH (NOLOCK)
            WHERE LEASE_NO = :lease_no AND EXECUTION IS NOT NULL
        """), {"lease_no": lease_no}).fetchone()
    else:
        row2 = db.session.execute(text("""
            SELECT ADV_ARR FROM clfcont WITH (NOLOCK) WHERE LEASE_NO = :lease_no
        """), {"lease_no": lease_no}).fetchone()

    if row2 and row2.ADV_ARR == "V":
        return base + 1
    return base

def _outstanding_amount_from_clfpay(lease_no: str, jlh_byr: int, fallback_amount: Any) -> float:
    has_payment = db.session.execute(text("""
        SELECT 1 FROM CLFPAY WITH (NOLOCK) WHERE LEASE_NO = :lease_no AND DATE_PAY <> ''
    """), {"lease_no": lease_no}).fetchone() is not None

    if not has_payment:
        return _n(fallback_amount)

    row = db.session.execute(text("""
        SELECT OUTS_PRINC FROM CLFPAY WITH (NOLOCK)
        WHERE LEASE_NO = :lease_no AND period = :period
    """), {"lease_no": lease_no, "period": jlh_byr}).fetchone()
    out = _n(row.OUTS_PRINC) if row else 0.0

    bgiro = db.session.execute(text("""
        SELECT TOP 1 [status], nominal FROM bgiro WITH (NOLOCK)
        WHERE LEASE_NO = :lease_no AND PAYMENT IS NOT NULL
        ORDER BY payment DESC
    """), {"lease_no": lease_no}).fetchone()
    if bgiro and bgiro.status == "p":
        out += _n(bgiro.nominal)

    return out

def _passes_group_appl_filter(group_appl: str, lease_no: str) -> bool:
    group_appl = group_appl or ""
    if not group_appl:
        return True
    if not lease_no:
        return True
    return lease_no not in group_appl

def disburse(appl_no: str, lessee_no: str, cons_leas: str, create_date: Any, apless: str) -> tuple[float, int]:
    tot_out = 0.0
    tot_unit = 0
    lessee_no = lessee_no or ""

    if cons_leas != "T":
        rows = db.session.execute(text("""
            SELECT a.EXECUTION, a.LEASE_NO
            FROM CLFCONT a WITH (NOLOCK)
            WHERE a.EXECUTION IS NOT NULL AND a.UPD_STAT = 'Y' AND a.FLGDEL = '0'
                AND a.LESSEE_NO = :lessee_no AND a.Cons_Leas = :cons_leas
        """), {"lessee_no": lessee_no, "cons_leas": cons_leas}).fetchall()
    else:
        rows = db.session.execute(text("""
            SELECT a.EXECUTION, a.LEASE_NO
            FROM CLFCONT a WITH (NOLOCK)
            WHERE a.EXECUTION IS NOT NULL AND a.UPD_STAT = 'Y' AND a.FLGDEL = '0'
                AND a.LESSEE_NO = :lessee_no AND a.Cons_Leas NOT IN ('C', 'L')
        """), {"lessee_no": lessee_no}).fetchall()

    for row in rows:
        is_cross_slave = db.session.execute(text("""
            SELECT crossno FROM TACrossNo WITH (NOLOCK)
            WHERE appl_no IN (SELECT appl_no FROM cafcont WITH (NOLOCK) WHERE apless = :apless)
                AND crossno IS NOT NULL AND crossno <> ''
                AND crossno = :lease_no
        """), {"apless": apless, "lease_no": row.LEASE_NO}).fetchone()
        if is_cross_slave is not None:
            continue
        jlh_byr = _compute_jlh_byr(row.LEASE_NO)

        fallback = db.session.execute(text("""
            SELECT b.Net_Finance AS ntf
            FROM CLFCONT a WITH (NOLOCK)
            INNER JOIN V_NetFinance b WITH (NOLOCK) ON a.LEASE_NO = b.LEASE_NO
            WHERE a.LEASE_NO = :lease_no
        """), {"lease_no": row.LEASE_NO}).fetchone()
        fallback_amount = fallback.ntf if fallback else 0

        out = _outstanding_amount_from_clfpay(row.LEASE_NO, jlh_byr, fallback_amount)
        tot_out += out
        tot_unit += 1

        market_price = _calc_marketprice(lease_no=row.LEASE_NO)

        db.session.execute(text("""
            INSERT INTO CAFLR (APPL_NO, LEASE_NO, TERM, MARKETPRICE, OUTSTANDING, [TYPE])
            VALUES (:appl_no, :lease_no, :term, :market_price, :out, '1')
        """), {
            "appl_no": appl_no, "lease_no": row.LEASE_NO, "term": jlh_byr,
            "market_price": market_price, "out": out,
        })

    return tot_out, tot_unit

def disburse_grp(
    lessee_no: str, cons_leas: str, create_date: Any, apless: str, grpcode: str, thitung: int, appl_no: str
) -> tuple[float, int]:
    tot_out = 0.0
    tot_unit = 0
    lessee_no = lessee_no or ""

    if thitung < 2:
        if cons_leas != "T":
            rows = db.session.execute(text("""
                SELECT NULL AS Nomor, b.APPL_NO, a.LEASE_NO
                FROM CLFCONT a WITH (NOLOCK)
                    RIGHT JOIN CAFCONT b WITH (NOLOCK) ON a.APPL_NO = b.APPL_NO
                    RIGHT JOIN CAFLESS c WITH (NOLOCK) ON b.APLESS = c.APLESS
                WHERE b.APLESS <> :apless AND c.GrpCode = :grpcode
                    AND a.FLGDEL = '0'
                    AND a.LESSEE_NO = :lessee_no
                    AND a.UPD_STAT = 'Y'
                  
                UNION
                
                SELECT LEFT(b.APPL_NO, 2) AS Nomors, b.APPL_NO, NULL
                FROM CAFCONT b WITH (NOLOCK)
                    LEFT JOIN CAFINSU c WITH (NOLOCK) ON b.APPL_NO = c.APPL_NO
                    LEFT JOIN CAFLESS d WITH (NOLOCK) ON b.APLESS = d.APLESS
                WHERE b.APLESS <> :apless AND d.GrpCode = :grpcode
                    AND b.Cons_Leas = :cons_leas
                    AND b.DateTrans IS NULL
                ORDER BY Nomor DESC
            """), {"apless": apless, "grpcode": grpcode, "lessee_no": lessee_no, "cons_leas": cons_leas}).fetchall()
        else:
            rows = db.session.execute(text("""
                SELECT NULL AS Nomor, b.APPL_NO, a.LEASE_NO
                FROM CLFCONT a WITH (NOLOCK)
                    RIGHT JOIN CAFCONT b WITH (NOLOCK) ON a.APPL_NO = b.APPL_NO
                    RIGHT JOIN CAFLESS c WITH (NOLOCK) ON b.APLESS = c.APLESS
                    LEFT JOIN MCMORevisi d WITH (NOLOCK) ON a.APPL_NO = d.oldAppl_No
                WHERE b.APLESS <> :apless
                    AND c.GrpCode = :grpcode AND a.FLGDEL = '0'
                    AND a.APPL_NO <> ISNULL(d.oldAppl_No, 0)
                    AND a.LESSEE_NO = :lessee_no AND a.UPD_STAT = 'Y'
                    
                UNION
                
                SELECT LEFT(b.APPL_NO, 2) AS Nomors, b.APPL_NO, NULL
                FROM CAFCONT b WITH (NOLOCK)
                    LEFT JOIN CAFINSU c WITH (NOLOCK) ON b.APPL_NO = c.APPL_NO
                    LEFT JOIN CAFLESS d WITH (NOLOCK) ON b.APLESS = d.APLESS
                    LEFT JOIN MCMORevisi e WITH (NOLOCK) ON b.APPL_NO = e.oldAppl_No
                WHERE b.APLESS <> :apless AND b.APPL_NO <> ISNULL(e.oldAppl_No, 0)
                  AND d.GrpCode = :grpcode AND b.DateTrans IS NULL
                ORDER BY Nomor DESC
            """), {"apless": apless, "grpcode": grpcode, "lessee_no": lessee_no}).fetchall()
    else:
        if cons_leas != "T":
            rows = db.session.execute(text("""
                SELECT b.APPL_NO, a.LEASE_NO
                FROM CLFCONT a WITH (NOLOCK)
                    RIGHT JOIN CAFCONT b WITH (NOLOCK) ON a.APPL_NO = b.APPL_NO
                    RIGHT JOIN CAFLESS c WITH (NOLOCK) ON b.APLESS = c.APLESS
                WHERE b.APLESS <> :apless AND c.GrpCode = :grpcode AND a.FLGDEL = '0'
                  AND a.LESSEE_NO = :lessee_no AND a.Cons_Leas = :cons_leas AND a.UPD_STAT = 'Y'
                ORDER BY a.LEASE_NO
            """), {"apless": apless, "grpcode": grpcode, "lessee_no": lessee_no, "cons_leas": cons_leas}).fetchall()
        else:
            rows = db.session.execute(text("""
                SELECT a.APPL_NO, a.LEASE_NO
                FROM CLFCONT a WITH (NOLOCK)
                    RIGHT JOIN CAFCONT b WITH (NOLOCK) ON a.APPL_NO = b.APPL_NO
                    RIGHT JOIN CAFLESS c WITH (NOLOCK) ON b.APLESS = c.APLESS
                    LEFT JOIN MCMORevisi d WITH (NOLOCK) ON a.APPL_NO = d.oldAppl_No
                WHERE a.LESSEE_NO = :lessee_no AND a.FLGDEL = '0' AND b.APLESS <> :apless
                    AND a.Cons_Leas IN (SELECT Cons_Leas FROM CLFCONT WITH (NOLOCK) WHERE LESSEE_NO = :lessee_no)
                    AND a.UPD_STAT = 'Y'
                    AND c.GrpCode = :grpcode AND a.APPL_NO <> ISNULL(d.oldAppl_No, 0)
                ORDER BY a.LEASE_NO
            """), {"lessee_no": lessee_no, "apless": apless, "grpcode": grpcode}).fetchall()

    for row in rows:
        lease_no = row.LEASE_NO
        is_cross_slave = db.session.execute(text("""
            SELECT a.crossno FROM (
                SELECT a.Crossno
                FROM TACrossNo a WITH (NOLOCK)
                    LEFT JOIN clfcont b WITH (NOLOCK) ON a.Crossno = b.LEASE_NO
                    LEFT JOIN CAFCONT c WITH (NOLOCK) ON c.APPL_NO = b.APPL_NO
                WHERE c.APLESS IN (SELECT apless FROM cafless WITH (NOLOCK) WHERE GrpCode = :grpcode)
                  AND (a.Crossno IS NOT NULL AND a.Crossno <> '')
            ) a WHERE a.Crossno = :lease_no
        """), {"grpcode": grpcode, "lease_no": lease_no}).fetchone()
        if is_cross_slave is not None:
            continue

        jlh_byr = _compute_jlh_byr(lease_no)

        if lease_no:
            fallback_amount = db.session.execute(text("""
                SELECT Net_Finance FROM V_NetFinance WITH (NOLOCK) WHERE LEASE_NO = :lease_no
            """), {"lease_no": lease_no}).scalar()
            out = _outstanding_amount_from_clfpay(lease_no, jlh_byr, fallback_amount)
            market_price = _calc_marketprice(lease_no=lease_no)
            simpan = lease_no
        else:
            out = _n(db.session.execute(text("""
                SELECT Net_Finance FROM V_NetFinance WITH (NOLOCK) WHERE APPL_NO = :appl_no_row
            """), {"appl_no_row": row.APPL_NO}).scalar())
            market_price = _calc_marketprice(appl_no=row.APPL_NO)
            simpan = row.APPL_NO

        tot_out += out
        tot_unit += 1

        db.session.execute(text("""
            INSERT INTO CAFLR (APPL_NO, LEASE_NO, TERM, MARKETPRICE, OUTSTANDING, [TYPE])
            VALUES (:appl_no, :lease_no, :term, :market_price, :out, '4')
        """), {
            "appl_no": appl_no, "lease_no": simpan, "term": jlh_byr,
            "market_price": market_price, "out": out,
        })

    return tot_out, tot_unit

def disburse_gua(
    lessee_no: str, cons_leas: str, create_date: Any, thitung_gua: int, group_appl: str, appl_no: str
) -> tuple[float, int]:
    tot_out = 0.0
    tot_unit = 0
    lessee_no = lessee_no or ""
    group_appl = group_appl or ""

    apless_rows = db.session.execute(text("""
        SELECT DISTINCT b.APLESS
        FROM CAFCONT b WITH (NOLOCK)
            LEFT JOIN CLFCONT c WITH (NOLOCK) ON b.APPL_NO = c.APPL_NO
        WHERE c.LESSEE_NO = :lessee_no
    """), {"lessee_no": lessee_no}).fetchall()

    for apl_row in apless_rows:
        apless_val = apl_row.APLESS

        if thitung_gua < 2:
            if cons_leas != "T":
                rows = db.session.execute(text("""
                    SELECT NULL AS Nomor, b.APPL_NO, a.LEASE_NO, c.Net_Finance
                    FROM CLFCONT a WITH (NOLOCK)
                        INNER JOIN V_DataKredit c ON a.lease_no = c.lease_no
                        RIGHT JOIN CAFCONT b WITH (NOLOCK) ON a.APPL_NO = b.APPL_NO
                    WHERE b.APLESS = :apless AND a.FLGDEL = '0' AND a.LESSEE_NO = :lessee_no
                        AND a.Cons_Leas = :cons_leas AND a.UPD_STAT = 'Y'
                """), {"apless": apless_val, "lessee_no": lessee_no, "cons_leas": cons_leas}).fetchall()
            else:
                rows = db.session.execute(text("""
                    SELECT NULL AS Nomor, b.APPL_NO, a.LEASE_NO, c.Net_Finance
                    FROM CLFCONT a WITH (NOLOCK)
                        INNER JOIN V_DataKredit c ON a.lease_no = c.lease_no
                        RIGHT JOIN CAFCONT b WITH (NOLOCK) ON a.APPL_NO = b.APPL_NO
                    WHERE b.APLESS = :apless AND a.FLGDEL = '0' AND a.LESSEE_NO = :lessee_no
                      AND a.Cons_Leas NOT IN ('C', 'L') AND a.UPD_STAT = 'Y'
                """), {"apless": apless_val, "lessee_no": lessee_no}).fetchall()
        else:
            if cons_leas != "T":
                rows = db.session.execute(text("""
                    SELECT b.APPL_NO, a.LEASE_NO, c.Net_Finance
                    FROM CLFCONT a WITH (NOLOCK)
                        INNER JOIN V_DataKredit c ON a.lease_no = c.lease_no
                        RIGHT JOIN CAFCONT b WITH (NOLOCK) ON a.APPL_NO = b.APPL_NO
                    WHERE b.APLESS = :apless AND a.FLGDEL = '0' AND a.LESSEE_NO = :lessee_no
                        AND a.Cons_Leas = :cons_leas AND a.UPD_STAT = 'Y'
                    ORDER BY a.LEASE_NO
                """), {"apless": apless_val, "lessee_no": lessee_no, "cons_leas": cons_leas}).fetchall()
            else:
                rows = db.session.execute(text("""
                    SELECT b.APPL_NO, a.LEASE_NO, c.Net_Finance
                    FROM CLFCONT a WITH (NOLOCK)
                        INNER JOIN V_DataKredit c ON a.lease_no = c.lease_no
                        RIGHT JOIN CAFCONT b WITH (NOLOCK) ON a.APPL_NO = b.APPL_NO
                    WHERE b.APLESS = :apless AND a.FLGDEL = '0' AND a.LESSEE_NO = :lessee_no
                        AND a.Cons_Leas NOT IN ('C', 'L') AND a.UPD_STAT = 'Y'
                    ORDER BY a.LEASE_NO
                """), {"apless": apless_val, "lessee_no": lessee_no}).fetchall()

        for row in rows:
            lease_no = row.LEASE_NO or ""
            jlh_byr = _compute_jlh_byr(lease_no, require_execution_for_fallback=True)

            if not _passes_group_appl_filter(group_appl, lease_no):
                continue

            if lease_no:
                fallback_amount = db.session.execute(text("""
                    SELECT b.Net_Finance
                    FROM CLFCONT a WITH (NOLOCK)
                    INNER JOIN V_DataKredit b ON a.LEASE_NO = b.LEASE_NO
                    WHERE a.LEASE_NO = :lease_no
                """), {"lease_no": lease_no}).scalar()
                out = _outstanding_amount_from_clfpay(lease_no, jlh_byr, fallback_amount)
            else:
                out = _n(row.Net_Finance)

            tot_out += out
            tot_unit += 1

            market_price = _calc_marketprice(lease_no=lease_no)

            db.session.execute(text("""
                INSERT INTO CAFLR (APPL_NO, LEASE_NO, TERM, MARKETPRICE, OUTSTANDING, [TYPE])
                VALUES (:appl_no, :lease_no, :term, :market_price, :out, '5')
            """), {
                "appl_no": appl_no, "lease_no": lease_no, "term": jlh_byr,
                "market_price": market_price, "out": out,
            })

    return tot_out, tot_unit

def recalculate(appl_no: str, apless: str, notes: str = "", group_appl: str = "") -> None:
    db.session.execute(text("""
        INSERT INTO Temp_CAFLR
        SELECT APPL_NO, LEASE_NO, TERM, MARKETPRICE, PAYMENTSTATUS, OUTSTANDING, [TYPE]
        FROM CAFLR WHERE APPL_NO = :appl_no
    """), {"appl_no": appl_no})
    db.session.execute(text("DELETE FROM CAFLR WHERE APPL_NO = :appl_no"), {"appl_no": appl_no})

    lessee_no = db.session.execute(text("""
        SELECT TOP 1 b.LESSEE_NO
        FROM CAFCONT a WITH (NOLOCK)
        RIGHT JOIN CLFCONT b WITH (NOLOCK) ON a.APPL_NO = b.APPL_NO
        WHERE a.APLESS = :apless
    """), {"apless": apless}).scalar() or ""

    create_date_row = db.session.execute(text("""
        SELECT CREATE_DATE, YEAR(CREATE_DATE) AS YEARS
        FROM CAFCONT WITH (NOLOCK) WHERE APLESS = :apless AND APPL_NO = :appl_no
    """), {"apless": apless, "appl_no": appl_no}).fetchone()
    create_date = create_date_row.CREATE_DATE if create_date_row else None
    create_datess = (create_date_row.YEARS if create_date_row and create_date_row.YEARS
                      else datetime.now().year)

    notcl_undis_rows = db.session.execute(text("""
        SELECT a.appl_no, b.Net_Finance
        FROM CLFCONT a WITH (NOLOCK)
            INNER JOIN V_NetFinance b WITH (NOLOCK) ON a.LEASE_NO = b.LEASE_NO
            LEFT JOIN MCMORevisi d WITH (NOLOCK) ON a.APPL_NO = d.oldAppl_No
            LEFT JOIN TACrossNo h WITH (NOLOCK) ON a.LEASE_NO = h.CROSSNO
        WHERE a.EXECUTION IS NULL AND a.FLGDEL = '0'
            AND a.LESSEE_NO = :lessee_no AND a.APPL_NO <> ISNULL(d.oldAppl_No, 0)
            AND h.CROSSNO IS NULL
            
        UNION
        
        SELECT a.appl_no, b.Net_Finance
        FROM CAFCONT a WITH (NOLOCK)
            INNER JOIN V_NetFinance b WITH (NOLOCK) ON a.APPL_NO = b.APPL_NO
            LEFT JOIN MCMORevisi g WITH (NOLOCK) ON a.APPL_NO = g.oldAppl_No
        WHERE a.DateTrans IS NULL AND a.APPL_NO <> ISNULL(g.oldAppl_No, 0)
             AND a.APLESS = :apless AND b.APPL_NO IN (
                SELECT appl_no FROM MCMOCAMStatus WHERE APPR_STS = 'E' AND APPL_NO IN (
                    SELECT appl_no FROM CAFCONT a2 INNER JOIN CAFLESS b2 ON a2.APLESS = b2.APLESS
                    WHERE a2.APLESS = :apless
                )
          )
    """), {"lessee_no": lessee_no, "apless": apless}).fetchall()

    notcl_undis = 0.0
    notcl_undis_unit = 0
    for row in notcl_undis_rows:
        market_price = _calc_marketprice(appl_no=row.appl_no)
        notcl_undis += _n(row.Net_Finance)
        notcl_undis_unit += 1
        db.session.execute(text("""
            INSERT INTO CAFLR (APPL_NO, LEASE_NO, TERM, MARKETPRICE, OUTSTANDING, [TYPE])
            VALUES (:appl_no, :lease_no, '0', :market_price, :net_finance, '2')
        """), {
            "appl_no": appl_no, "lease_no": row.appl_no,
            "market_price": market_price, "net_finance": row.Net_Finance,
        })

    notcl_unapp_rows = db.session.execute(text("""
        SELECT a.appl_no, b.Net_Finance, a.L_AMOUNT
        FROM CAFCONT a WITH (NOLOCK)
            INNER JOIN V_NetFinance b WITH (NOLOCK) ON a.APPL_NO = b.APPL_NO
        WHERE a.DateTrans IS NULL AND a.APLESS = :apless
            AND a.APPL_NO NOT IN (
                SELECT appl_no
                FROM MCMOCAMStatus
                WHERE (APPR_STS = 'E' OR APPR_STS = 'RW')
                    AND APPL_NO IN (
                        SELECT a2.appl_no FROM CAFCONT a2
                            INNER JOIN CAFLESS b2 ON a2.APLESS = b2.APLESS
                            INNER JOIN (
                                SELECT appl_no, appr_sts FROM mcmocamstatus a3
                                WHERE no = (SELECT MAX(no) FROM mcmocamstatus WHERE APPL_NO = a3.APPL_NO)
                            ) d ON a2.APPL_NO = d.APPL_NO
                            WHERE a2.APLESS = :apless AND (d.APPR_STS = 'E' OR d.APPR_STS = 'RW')
                    )
            )
    """), {"apless": apless}).fetchall()

    notcl_unapp = 0.0
    notcl_unapp_unit = 0
    for row in notcl_unapp_rows:
        notcl_unapp += _n(row.Net_Finance)
        notcl_unapp_unit += 1
        db.session.execute(text("""
            INSERT INTO CAFLR (APPL_NO, LEASE_NO, TERM, MARKETPRICE, OUTSTANDING, [TYPE])
            VALUES (:appl_no, :lease_no, '0', :market_price, :net_finance, '3')
        """), {
            "appl_no": appl_no, "lease_no": row.appl_no,
            "market_price": row.L_AMOUNT, "net_finance": row.Net_Finance,
        })

    cf_dis, cf_dis_unit = disburse(appl_no, lessee_no, "C", create_datess, apless)
    fl_dis, fl_dis_unit = disburse(appl_no, lessee_no, "L", create_datess, apless)
    notcl_dis, notcl_dis_unit = disburse(appl_no, lessee_no, "T", create_datess, apless)

    cf_group = 0.0
    cf_group_unit = 0
    fl_group = 0.0
    fl_group_unit = 0
    notcl_group = 0.0
    notcl_group_unit = 0

    grpcode = db.session.execute(text("""
        SELECT GrpCode FROM CAFLESS WITH (NOLOCK) WHERE APLESS = :apless
    """), {"apless": apless}).scalar() or ""

    if grpcode.strip():
        thitung = 1
        sibling_rows = db.session.execute(text("""
            SELECT APLESS FROM CAFLESS WITH (NOLOCK)
            WHERE GrpCode = :grpcode AND APLESS <> :apless AND GrpCode NOT IN ('001', '002')
            ORDER BY APLESS
        """), {"grpcode": grpcode, "apless": apless}).fetchall()

        for sib in sibling_rows:
            sib_lessee_no = db.session.execute(text("""
                SELECT TOP 1 b.LESSEE_NO
                FROM CAFCONT a WITH (NOLOCK)
                    RIGHT JOIN CLFCONT b WITH (NOLOCK) ON a.APPL_NO = b.APPL_NO
                WHERE a.APLESS = :apless AND b.LESSEE_NO IS NOT NULL
                ORDER BY b.LESSEE_NO
            """), {"apless": sib.APLESS}).scalar() or ""

            g_out, g_unit = disburse_grp(sib_lessee_no, "T", create_date, apless, grpcode, thitung, appl_no)
            notcl_group += g_out
            notcl_group_unit += g_unit
            thitung += 1

    cf_gua = 0.0
    cf_gua_unit = 0
    fl_gua = 0.0
    fl_gua_unit = 0
    notcl_gua = 0.0
    notcl_gua_unit = 0

    guarantor_rows = db.session.execute(text("""
        SELECT LESSEE_NO FROM CAFGUARN WITH (NOLOCK) WHERE APPL_NO = :appl_no AND LESSEE_NO <> ''
    """), {"appl_no": appl_no}).fetchall()

    thitung_gua = 1
    for g_row in guarantor_rows:
        g_lessee_no = g_row.LESSEE_NO

        out1, unit1_ = disburse_gua(g_lessee_no, "C", create_date, thitung_gua, group_appl, appl_no)
        cf_gua += out1
        cf_gua_unit += unit1_

        out2, unit2_ = disburse_gua(g_lessee_no, "L", create_date, thitung_gua, group_appl, appl_no)
        fl_gua += out2
        fl_gua_unit += unit2_

        out3, unit3_ = disburse_gua(g_lessee_no, "T", create_date, thitung_gua, group_appl, appl_no)
        notcl_gua += out3
        notcl_gua_unit += unit3_

        thitung_gua += 1

    cf_undis = 0.0
    cf_undis_unit = 0
    cf_unapp = 0.0
    cf_unapp_unit = 0
    fl_undis = 0.0
    fl_undis_unit = 0
    fl_unapp = 0.0
    fl_unapp_unit = 0

    cf_tot_unit = cf_undis_unit + cf_unapp_unit + cf_dis_unit + cf_group_unit + cf_gua_unit
    cf_tot = cf_undis + cf_unapp + cf_dis + cf_group + cf_gua
    fl_tot_unit = fl_undis_unit + fl_unapp_unit + fl_dis_unit + fl_group_unit + fl_gua_unit
    fl_tot = fl_undis + fl_unapp + fl_dis + fl_group + fl_gua
    notcl_tot_unit = notcl_undis_unit + notcl_unapp_unit + notcl_dis_unit + notcl_group_unit + notcl_gua_unit
    notcl_tot = notcl_undis + notcl_unapp + notcl_dis + notcl_group + notcl_gua

    dis_unit = cf_dis_unit + fl_dis_unit + notcl_dis_unit
    undis_unit = cf_undis_unit + fl_undis_unit + notcl_undis_unit
    unapp_unit = cf_unapp_unit + fl_unapp_unit + notcl_unapp_unit
    group_unit = cf_group_unit + fl_group_unit + notcl_group_unit
    gua_unit = cf_gua_unit + fl_gua_unit + notcl_gua_unit
    dis = cf_dis + fl_dis + notcl_dis
    undis = cf_undis + fl_undis + notcl_undis
    unapp = cf_unapp + fl_unapp + notcl_unapp
    group = cf_group + fl_group + notcl_group
    gua = cf_gua + fl_gua + notcl_gua

    unit3 = {1: dis_unit, 2: undis_unit, 3: unapp_unit, 4: group_unit, 5: gua_unit}
    amount3 = {1: dis, 2: undis, 3: unapp, 4: group, 5: gua}

    today = date.today()
    db.session.execute(text("""
        DELETE FROM CAFCUST_OUTS WHERE APPL_NO = :appl_no AND ASOF = :today
    """), {"appl_no": appl_no, "today": today})

    type_rows = db.session.execute(text("SELECT ID_TYPE FROM MSTTYPECUSTOUTS WITH (NOLOCK)")).fetchall()
    for t_row in type_rows:
        t = int(t_row.ID_TYPE)
        amt = amount3.get(t, 0.0)
        unit = unit3.get(t, 0)
        if amt != 0 or unit != 0:
            db.session.execute(text("""
                INSERT INTO CAFCUST_OUTS (APPL_NO, ASOF, CONS_LEAS, [TYPE], OUTS, UNIT, OUTS_NOTES)
                VALUES (:appl_no, SYSDATETIME(), '', :type_code, :outs, :unit, :notes)
            """), {"appl_no": appl_no, "type_code": str(t), "outs": amt, "unit": unit, "notes": notes})

    restore_rows = db.session.execute(text("""
        SELECT b.MARKETPRICE, b.PAYMENTSTATUS, b.LEASE_NO, b.[TYPE]
        FROM CAFLR a WITH (NOLOCK)
            INNER JOIN Temp_CAFLR b WITH (NOLOCK)
                ON a.appl_no = b.appl_no AND a.lease_no = b.lease_no AND a.[type] = b.[type]
        WHERE a.appl_no = :appl_no
    """), {"appl_no": appl_no}).fetchall()

    for r in restore_rows:
        db.session.execute(text("""
            UPDATE CAFLR SET MARKETPRICE = :mp, PAYMENTSTATUS = :ps
            WHERE APPL_NO = :appl_no AND LEASE_NO = :lease_no AND [TYPE] = :type_code
        """), {
            "mp": r.MARKETPRICE, "ps": r.PAYMENTSTATUS,
            "appl_no": appl_no, "lease_no": r.LEASE_NO, "type_code": r.TYPE,
        })

    db.session.execute(text("DELETE FROM Temp_CAFLR WHERE APPL_NO = :appl_no"), {"appl_no": appl_no})