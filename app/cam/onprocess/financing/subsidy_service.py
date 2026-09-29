from __future__ import annotations
from typing import Dict, List, Optional
from sqlalchemy import text
from app import db

from app.utils.helpers.php_compat import clamp_zero, money_input, number_format, php_float
from .subsidy_rules import (
    ADD_RULES,
    AMOUNT_TYPE_BY_CODE,
    COLUMN_REFUND_SUPP,
    DELETE_RULES,
    EXCESS_AMOUNT_TYPES,
    MIRRORED_AMOUNT_TYPES,
    RESET_SURVEY_FEE_2_COLUMNS,
    REFUND_DEALER,
    ROLLUP_AMOUNT_TYPES,
    SUBSIDY_TYPE_LABELS,
    amount_type_label,
    dealer_options,
    payment_for_options,
)

MESSAGE_MISSING_SELECTION = "Please choose Dealer/APM and Payment For what"
MESSAGE_MISSING_PAYMENT_FOR = "Please Choose Payment For"

class SubsidyError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

def _scalar(sql: str, params: Dict) -> Optional[object]:
    return db.session.execute(text(sql), params).scalar()

def _fetch_brand(applno: str) -> str:
    brand = _scalar("SELECT BRAND FROM CAFEQUIP WHERE APPL_NO = :applno", {"applno": applno})
    return (brand or "").strip()

def _detail_amount(applno: str, subsidy_type: str, amount_type: str) -> float:
    value = _scalar(
        """
        SELECT Amount FROM CafcontSubsidyDetail WITH (NOLOCK)
        WHERE APPL_NO = :applno AND SubsidyType = :subsidy_type AND AmountType = :amount_type
        """,
        {"applno": applno, "subsidy_type": subsidy_type, "amount_type": amount_type},
    )
    return php_float(value)

def _detail_exists(applno: str, subsidy_type: str, amount_type: str) -> bool:
    found = _scalar(
        """
        SELECT 1 FROM CafcontSubsidyDetail WITH (NOLOCK)
        WHERE APPL_NO = :applno AND SubsidyType = :subsidy_type AND AmountType = :amount_type
        """,
        {"applno": applno, "subsidy_type": subsidy_type, "amount_type": amount_type},
    )
    return found is not None

def _detail_total(applno: str, subsidy_type: str) -> float:
    value = _scalar(
        """
        SELECT SUM(Amount) FROM CafcontSubsidyDetail WITH (NOLOCK)
        WHERE APPL_NO = :applno AND SubsidyType = :subsidy_type
        """,
        {"applno": applno, "subsidy_type": subsidy_type},
    )
    return php_float(value)

def _header_value(applno: str, column: str) -> float:
    value = _scalar(
        f"SELECT [{column}] FROM CAFCONT WITH (NOLOCK) WHERE APPL_NO = :applno",
        {"applno": applno},
    )
    return php_float(value)

def _update_header(applno: str, assignments: Dict[str, object]) -> None:
    if not assignments:
        return
    clauses = ", ".join(f"[{column}] = :{column}" for column in assignments)
    params = dict(assignments)
    params["applno"] = applno
    db.session.execute(text(f"UPDATE CAFCONT SET {clauses} WHERE APPL_NO = :applno"), params)

def _upsert_detail(applno: str, subsidy_type: str, amount_type: str, amount: float, exists: bool) -> None:
    params = {
        "applno": applno,
        "subsidy_type": subsidy_type,
        "amount_type": amount_type,
        "amount": amount,
    }
    if exists:
        db.session.execute(
            text(
                """
                UPDATE CafcontSubsidyDetail SET Amount = :amount
                WHERE APPL_NO = :applno AND SubsidyType = :subsidy_type AND AmountType = :amount_type
                """
            ),
            params,
        )
        return
    db.session.execute(
        text(
            """
            INSERT INTO CafcontSubsidyDetail (APPL_No, SubsidyType, AmountType, Amount)
            VALUES (:applno, :subsidy_type, :amount_type, :amount)
            """
        ),
        params,
    )

def _delete_detail(applno: str, subsidy_type: str, amount_type: str) -> None:
    db.session.execute(
        text(
            """
            DELETE FROM CafcontSubsidyDetail
            WHERE APPL_NO = :applno AND SubsidyType = :subsidy_type AND AmountType = :amount_type
            """
        ),
        {"applno": applno, "subsidy_type": subsidy_type, "amount_type": amount_type},
    )

def fetch_grid(applno: str, survey_fee_2_enabled: bool) -> Dict:
    rows = db.session.execute(
        text(
            """
            SELECT b.SubsidyType, b.AmountType, b.Amount
            FROM CAFCONT a WITH (NOLOCK)
            INNER JOIN CafcontSubsidyDetail b WITH (NOLOCK) ON a.APPL_NO = b.APPL_No
            WHERE a.APPL_NO = :applno
            """
        ),
        {"applno": applno},
    ).fetchall()

    brand = _fetch_brand(applno)
    entries: List[Dict] = []
    for row in rows:
        subsidy_type = (row.SubsidyType or "").strip()
        amount_type = (row.AmountType or "").strip()
        entries.append(
            {
                "applNo": applno,
                "subsidyType": subsidy_type,
                "subsidyLabel": SUBSIDY_TYPE_LABELS.get(subsidy_type, subsidy_type),
                "amountType": amount_type,
                "amountTypeLabel": amount_type_label(amount_type),
                "amount": php_float(row.Amount),
                "amountDisplay": number_format(row.Amount, 0),
                "deletable": subsidy_type != REFUND_DEALER,
            }
        )

    return {
        "rows": entries,
        "dealerOptions": dealer_options(brand),
        "paymentForOptions": payment_for_options(survey_fee_2_enabled),
    }

def _amount_type_sums(applno: str) -> Dict[str, float]:
    rows = db.session.execute(
        text(
            """
            SELECT b.AmountType, SUM(b.Amount) AS jumlah
            FROM CAFCONT a WITH (NOLOCK)
            INNER JOIN CafcontSubsidyDetail b WITH (NOLOCK) ON a.APPL_NO = b.APPL_No
            WHERE a.APPL_NO = :applno
            GROUP BY b.AmountType
            """
        ),
        {"applno": applno},
    ).fetchall()
    sums = {amount_type: 0.0 for amount_type in ROLLUP_AMOUNT_TYPES}
    for row in rows:
        key = (row.AmountType or "").strip()
        if key in sums:
            sums[key] = php_float(row.jumlah)
    return sums

def _excess_sum(applno: str, subsidy_types) -> float:
    placeholders = ", ".join(f":type_{index}" for index in range(len(subsidy_types)))
    amount_placeholders = ", ".join(f":amt_{index}" for index in range(len(EXCESS_AMOUNT_TYPES)))
    params: Dict[str, object] = {"applno": applno}
    for index, value in enumerate(subsidy_types):
        params[f"type_{index}"] = value
    for index, value in enumerate(EXCESS_AMOUNT_TYPES):
        params[f"amt_{index}"] = value
    value = _scalar(
        f"""
        SELECT SUM(b.Amount)
        FROM CAFCONT a WITH (NOLOCK)
        INNER JOIN CafcontSubsidyDetail b WITH (NOLOCK) ON a.APPL_NO = b.APPL_No
        WHERE a.APPL_NO = :applno
          AND b.SubsidyType IN ({placeholders})
          AND b.AmountType IN ({amount_placeholders})
        """,
        params,
    )
    return php_float(value)

def fetch_totals(applno: str, survinc2) -> Dict:
    header = db.session.execute(
        text(
            """
            SELECT AdmFee, PROVISION, BaseAdmFee, InterestIncome, BaseInterestFee
            FROM CAFCONT WITH (NOLOCK)
            WHERE APPL_NO = :applno
            """
        ),
        {"applno": applno},
    ).fetchone()

    survinc = php_float(header.AdmFee) if header else 0.0
    provinc = php_float(header.PROVISION) if header else 0.0
    basesurv = php_float(header.BaseAdmFee) if header else 0.0
    gross_int_rate = php_float(header.InterestIncome) if header else 0.0
    net_int_rate = php_float(header.BaseInterestFee) if header else 0.0

    sums = _amount_type_sums(applno)
    jumlah_subdel = _excess_sum(applno, ("SD",))
    jumlah_subapm = _excess_sum(applno, ("SA", "IA"))

    ins_policy = _scalar("SELECT INS_POL FROM CAFINSU WHERE APPL_NO = :applno", {"applno": applno})
    total_net_insu = php_float(
        _scalar(
            "SELECT SUM(PREP_AMT) FROM CAFINSUD WITH (NOLOCK) WHERE INS_POL = :policy",
            {"policy": ins_policy},
        )
    )

    disb = db.session.execute(
        text("SELECT GROSS_PREM, NET_COM FROM CAFDISB WITH (NOLOCK) WHERE APPL_NO = :applno"),
        {"applno": applno},
    ).fetchone()
    gross_prem = php_float(disb.GROSS_PREM) if disb else 0.0
    net_com = php_float(disb.NET_COM) if disb else 0.0

    ttl_income = gross_prem - net_com
    ttl_income_net = gross_prem - total_net_insu

    jumlah_sur = sums["Survey"]
    jumlah_prov = sums["Provision"]
    jumlah_int = sums["Interest"]
    jumlah_surv = sums["SurveyFee2"]

    jumlah_semua = jumlah_sur + jumlah_prov + jumlah_int + jumlah_surv
    exec_inc = ttl_income
    exec_inc_net = ttl_income_net

    ttl_int = gross_int_rate + jumlah_int
    exc_int = ttl_int - net_int_rate
    ttl_surv = survinc + jumlah_sur
    ttl_surv2 = money_input(survinc2) + jumlah_surv
    base_surv2 = 0.8 * ttl_surv2
    exce_surv = ttl_surv - basesurv
    exce_surv2 = ttl_surv2 - base_surv2
    ttl_prov = provinc + jumlah_prov
    prov_exec = ttl_prov

    ttl_sub_tot = ttl_prov + ttl_int + ttl_surv + ttl_income_net + ttl_surv2
    ttl_exc_tot = exec_inc + exce_surv + prov_exec + exc_int + exce_surv2
    max_comm = ttl_sub_tot * 15 / 100
    eligible_comm = ttl_exc_tot

    marketing_fees = eligible_comm - max_comm
    if marketing_fees >= 0:
        marketing_fee = 0.0 if eligible_comm <= marketing_fees else marketing_fees
    else:
        marketing_fee = 0.0

    values = {
        "jumlahInsurance": sums["Insurance"],
        "jumlahSurvey": jumlah_sur,
        "jumlahProvision": jumlah_prov,
        "jumlahInterest": jumlah_int,
        "jumlahSemua": jumlah_semua,
        "jumlahSubsidyDealer": jumlah_subdel,
        "jumlahSubsidyApm": jumlah_subapm,
        "totalIncomeNet": ttl_income_net,
        "excessIncome": exec_inc,
        "totalSubsidy": ttl_sub_tot,
        "totalExcess": ttl_exc_tot,
        "maxCommission": max_comm,
        "eligibleCommission": eligible_comm,
        "totalSurveyFee1": ttl_surv,
        "totalProvision": ttl_prov,
        "totalInterest": ttl_int,
        "excessSurveyFee1": exce_surv,
        "excessInterest": exc_int,
        "incomeNet": ttl_income_net,
        "marketingFee": marketing_fee,
        "excessIncomeNet": exec_inc_net,
        "jumlahSurveyFee2": jumlah_surv,
        "totalSurveyFee2": ttl_surv2,
        "excessSurveyFee2": exce_surv2,
        "baseSurveyFee2": base_surv2,
    }

    return {
        "values": values,
        "display": {key: number_format(value, 0) for key, value in values.items()},
    }


def add_subsidy(applno: str, dealer_code: str, payment_for_code: str, amount) -> None:
    dealer = (dealer_code or "").strip()
    payment_for = (payment_for_code or "").strip()

    if not dealer or not payment_for:
        raise SubsidyError(MESSAGE_MISSING_SELECTION)

    rule = ADD_RULES.get(dealer)
    if rule is None:
        raise SubsidyError(MESSAGE_MISSING_SELECTION)

    amount_type = AMOUNT_TYPE_BY_CODE.get(payment_for)
    if amount_type is None:
        raise SubsidyError(MESSAGE_MISSING_PAYMENT_FOR)

    value = money_input(amount)
    mirror = rule.mirror_type if amount_type in MIRRORED_AMOUNT_TYPES else None
    exists = _detail_exists(applno, rule.subsidy_type, amount_type)

    _upsert_detail(applno, rule.subsidy_type, amount_type, value, exists)
    if mirror is not None:
        _upsert_detail(applno, mirror, amount_type, value, exists)

    assignments: Dict[str, object] = {rule.header_column: _detail_total(applno, rule.subsidy_type)}
    if rule.incentive is not None:
        assignments["Incentive"] = rule.incentive
    if mirror is not None:
        assignments[COLUMN_REFUND_SUPP] = _detail_total(applno, mirror)

    _update_header(applno, assignments)


def delete_subsidy(applno: str, subsidy_type: str, amount_type: str, amount) -> None:
    key = ((subsidy_type or "").strip(), (amount_type or "").strip())
    rule = DELETE_RULES.get(key)
    if rule is None:
        raise SubsidyError(MESSAGE_MISSING_SELECTION)

    if rule.subtrahend_from_request:
        subtrahend = money_input(amount)
    else:
        subtrahend = _detail_amount(applno, rule.subtrahend_row_type, key[1])

    assignments: Dict[str, object] = {
        rule.header_column: clamp_zero(_header_value(applno, rule.header_column) - subtrahend)
    }

    if rule.refund_row_type is not None:
        refund_row = _detail_amount(applno, rule.refund_row_type, key[1])
        assignments[COLUMN_REFUND_SUPP] = clamp_zero(_header_value(applno, COLUMN_REFUND_SUPP) - refund_row)

    if rule.incentive is not None:
        assignments["Incentive"] = rule.incentive

    _update_header(applno, assignments)

    for target in rule.delete_types:
        _delete_detail(applno, target, key[1])


def reset_survey_fee_2(applno: str) -> None:
    rows = db.session.execute(
        text(
            """
            SELECT SubsidyType FROM CafcontSubsidyDetail
            WHERE AmountType = 'SurveyFee2' AND APPL_No = :applno
            """
        ),
        {"applno": applno},
    ).fetchall()

    for row in rows:
        subsidy_type = (row.SubsidyType or "").strip()
        column = RESET_SURVEY_FEE_2_COLUMNS.get(subsidy_type)
        if column is None:
            continue
        row_amount = _detail_amount(applno, subsidy_type, "SurveyFee2")
        _update_header(applno, {column: clamp_zero(_header_value(applno, column) - row_amount)})
        _delete_detail(applno, subsidy_type, "SurveyFee2")
