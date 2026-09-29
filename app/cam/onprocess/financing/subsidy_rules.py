from __future__ import annotations

from typing import Dict, NamedTuple, Optional, Tuple

SUBSIDY_DEALER = "SD"
SUBSIDY_APM = "SA"
INCENTIVE_APM = "IA"
REFUND_DEALER = "RD"

COLUMN_SUBSIDY = "SUBSIDY"
COLUMN_SUBSIDY_SUPP = "Subsidy_Supp"
COLUMN_REFUND_SUPP = "Refund_Supp"

AMOUNT_TYPE_BY_CODE: Dict[str, str] = {
    "1": "DP",
    "2": "Installment",
    "3": "Insurance",
    "4": "Survey",
    "5": "Provision",
    "6": "Interest",
    "7": "SurveyFee2",
}

MIRRORED_AMOUNT_TYPES = ("DP", "Installment", "Insurance")

SUBSIDY_TYPE_LABELS: Dict[str, str] = {
    SUBSIDY_DEALER: "Subsidy From Dealer",
    SUBSIDY_APM: "Subsidy From APM",
    INCENTIVE_APM: "Incentive From APM",
    REFUND_DEALER: "Refund To Dealer",
}

AMOUNT_TYPE_LABELS: Dict[str, str] = {
    "Survey": "Survey Fee 1",
    "SurveyFee2": "Survey Fee 2",
}

DEALER_OPTION_DEALER = {"value": "1", "label": SUBSIDY_TYPE_LABELS[SUBSIDY_DEALER]}
DEALER_OPTION_APM = {"value": "2", "label": SUBSIDY_TYPE_LABELS[SUBSIDY_APM]}
DEALER_OPTION_INCENTIVE = {"value": "3", "label": SUBSIDY_TYPE_LABELS[INCENTIVE_APM]}

BRAND_MITSUBISHI = "MIT"
BRANDS_WITH_APM_SUBSIDY = ("ISZ", "HIN")

PAYMENT_FOR_BASE = (
    {"value": "1", "label": "For DP"},
    {"value": "2", "label": "For Installment"},
    {"value": "3", "label": "For Insurance"},
    {"value": "4", "label": "For Survey Fee 1"},
)

PAYMENT_FOR_SURVEY_FEE_2 = {"value": "7", "label": "For Survey Fee 2"}

PAYMENT_FOR_TAIL = (
    {"value": "5", "label": "For Provision Fee"},
    {"value": "6", "label": "For Interest"},
)

ROLLUP_AMOUNT_TYPES = ("DP", "Installment", "Insurance", "Survey", "Provision", "Interest", "SurveyFee2")
EXCESS_AMOUNT_TYPES = ("Survey", "Provision", "Interest", "SurveyFee2")


class AddRule(NamedTuple):
    subsidy_type: str
    header_column: str
    incentive: Optional[int]
    mirror_type: Optional[str]


ADD_RULES: Dict[str, AddRule] = {
    "1": AddRule(SUBSIDY_DEALER, COLUMN_SUBSIDY_SUPP, None, None),
    "2": AddRule(SUBSIDY_APM, COLUMN_SUBSIDY, 0, REFUND_DEALER),
    "3": AddRule(INCENTIVE_APM, COLUMN_SUBSIDY, 1, REFUND_DEALER),
}


class DeleteRule(NamedTuple):
    header_column: str
    subtrahend_from_request: bool
    subtrahend_row_type: Optional[str]
    refund_row_type: Optional[str]
    incentive: Optional[int]
    delete_types: Tuple[str, ...]


DELETE_RULES: Dict[Tuple[str, str], DeleteRule] = {
    (INCENTIVE_APM, "DP"): DeleteRule(COLUMN_SUBSIDY, True, None, REFUND_DEALER, 0, (INCENTIVE_APM, REFUND_DEALER)),
    (INCENTIVE_APM, "Installment"): DeleteRule(COLUMN_SUBSIDY, True, None, REFUND_DEALER, 0, (INCENTIVE_APM, REFUND_DEALER)),
    (INCENTIVE_APM, "Insurance"): DeleteRule(COLUMN_SUBSIDY, True, None, REFUND_DEALER, 0, (INCENTIVE_APM, REFUND_DEALER)),
    (INCENTIVE_APM, "Survey"): DeleteRule(COLUMN_SUBSIDY, True, None, None, None, (INCENTIVE_APM,)),
    (INCENTIVE_APM, "Provision"): DeleteRule(COLUMN_SUBSIDY, True, None, None, None, (INCENTIVE_APM,)),
    (INCENTIVE_APM, "Interest"): DeleteRule(COLUMN_SUBSIDY, True, None, None, None, (INCENTIVE_APM,)),
    (INCENTIVE_APM, "SurveyFee2"): DeleteRule(COLUMN_SUBSIDY, True, None, None, None, (INCENTIVE_APM,)),
    (SUBSIDY_APM, "DP"): DeleteRule(COLUMN_SUBSIDY, True, None, REFUND_DEALER, None, (SUBSIDY_APM, REFUND_DEALER)),
    (SUBSIDY_APM, "Installment"): DeleteRule(COLUMN_SUBSIDY, False, REFUND_DEALER, REFUND_DEALER, None, (SUBSIDY_APM, REFUND_DEALER)),
    (SUBSIDY_APM, "Insurance"): DeleteRule(COLUMN_SUBSIDY, False, REFUND_DEALER, REFUND_DEALER, None, (SUBSIDY_APM, REFUND_DEALER)),
    (SUBSIDY_APM, "Survey"): DeleteRule(COLUMN_SUBSIDY, False, SUBSIDY_APM, None, None, (SUBSIDY_APM,)),
    (SUBSIDY_APM, "Provision"): DeleteRule(COLUMN_SUBSIDY, False, SUBSIDY_APM, None, None, (SUBSIDY_APM,)),
    (SUBSIDY_APM, "Interest"): DeleteRule(COLUMN_SUBSIDY, False, SUBSIDY_APM, None, None, (SUBSIDY_APM,)),
    (SUBSIDY_APM, "SurveyFee2"): DeleteRule(COLUMN_SUBSIDY, False, SUBSIDY_APM, None, None, (SUBSIDY_APM,)),
    (SUBSIDY_DEALER, "DP"): DeleteRule(COLUMN_SUBSIDY_SUPP, False, SUBSIDY_DEALER, None, None, (SUBSIDY_DEALER,)),
    (SUBSIDY_DEALER, "Installment"): DeleteRule(COLUMN_SUBSIDY_SUPP, False, SUBSIDY_DEALER, None, None, (SUBSIDY_DEALER,)),
    (SUBSIDY_DEALER, "Insurance"): DeleteRule(COLUMN_SUBSIDY_SUPP, False, SUBSIDY_DEALER, None, None, (SUBSIDY_DEALER,)),
    (SUBSIDY_DEALER, "Survey"): DeleteRule(COLUMN_SUBSIDY_SUPP, False, SUBSIDY_DEALER, None, None, (SUBSIDY_DEALER,)),
    (SUBSIDY_DEALER, "Provision"): DeleteRule(COLUMN_SUBSIDY_SUPP, False, SUBSIDY_DEALER, None, None, (SUBSIDY_DEALER,)),
    (SUBSIDY_DEALER, "Interest"): DeleteRule(COLUMN_SUBSIDY_SUPP, False, SUBSIDY_DEALER, None, None, (SUBSIDY_DEALER,)),
    (SUBSIDY_DEALER, "SurveyFee2"): DeleteRule(COLUMN_SUBSIDY_SUPP, False, SUBSIDY_DEALER, None, None, (SUBSIDY_DEALER,)),
}

RESET_SURVEY_FEE_2_COLUMNS: Dict[str, str] = {
    INCENTIVE_APM: COLUMN_SUBSIDY,
    SUBSIDY_APM: COLUMN_SUBSIDY,
    SUBSIDY_DEALER: COLUMN_SUBSIDY_SUPP,
}


def dealer_options(brand: str):
    normalised = (brand or "").strip()
    if normalised == BRAND_MITSUBISHI:
        return [DEALER_OPTION_DEALER, DEALER_OPTION_INCENTIVE]
    if normalised in BRANDS_WITH_APM_SUBSIDY:
        return [DEALER_OPTION_DEALER, DEALER_OPTION_APM]
    return [DEALER_OPTION_DEALER]


def payment_for_options(survey_fee_2_enabled: bool):
    options = list(PAYMENT_FOR_BASE)
    if survey_fee_2_enabled:
        options.append(PAYMENT_FOR_SURVEY_FEE_2)
    options.extend(PAYMENT_FOR_TAIL)
    return options


def amount_type_label(amount_type: str) -> str:
    return AMOUNT_TYPE_LABELS.get(amount_type, amount_type)
