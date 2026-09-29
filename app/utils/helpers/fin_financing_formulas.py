from __future__ import annotations

import math
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP, InvalidOperation
from typing import Optional, Sequence

LOOP_GUARD = 200000


def to_float(value, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return default
        return float(value)
    if isinstance(value, Decimal):
        return float(value)
    text = str(value).strip().replace(",", "")
    if text == "":
        return default
    try:
        return float(text)
    except ValueError:
        return default


def php_empty(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        if text in ("", "0"):
            return True
        try:
            return float(text) == 0
        except ValueError:
            return False
    try:
        return float(value) == 0
    except (TypeError, ValueError):
        return False


def php_round(value: float, precision: int = 0) -> float:
    try:
        quant = Decimal(1).scaleb(-precision)
        return float(Decimal(repr(float(value))).quantize(quant, rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError):
        return float(value)


def php_str(value: float) -> str:
    text = f"{float(value):.14G}"
    if "E" in text:
        mantissa, exponent = text.split("E")
        if "." not in mantissa:
            mantissa = mantissa + ".0"
        text = f"{mantissa}E{int(exponent)}"
    return text


def trunc4(value) -> float:
    if value in (None, ""):
        return 0.0
    number = to_float(value)
    try:
        return float(Decimal(repr(number)).quantize(Decimal("0.0001"), rounding=ROUND_DOWN))
    except InvalidOperation:
        return number


def substr6(value) -> float:
    text = php_str(to_float(value))[:6]
    try:
        return float(text)
    except ValueError:
        return 0.0


def pangkat(x: float, n: float) -> float:
    return math.exp(n * math.log(x))


def fv(rate: float = 0, nper: float = 0, pmt_: float = 0, pv_: float = 0, type_: int = 0) -> float:
    if rate != 0.0:
        return -pv_ * math.pow(1 + rate, nper) - pmt_ * (1 + rate * type_) * ((math.pow(1 + rate, nper) - 1) / rate)
    return -pv_ - (pmt_ * nper)


def pv(rate: float = 0, nper: float = 0, pmt_: float = 0, fv_: float = 0, type_: int = 0) -> float:
    if rate != 0.0:
        return (-pmt_ * (1 + rate * type_) * ((math.pow(1 + rate, nper) - 1) / rate) - fv_) / math.pow(1 + rate, nper)
    return -fv_ - (pmt_ * nper)


def pmt(rate: float = 0, nper: float = 0, pv_: float = 0, fv_: float = 0, type_: int = 0) -> float:
    if rate != 0.0:
        return (-pv_ * math.pow(1 + rate, nper) - fv_) / ((1 + rate * type_) * ((math.pow(1 + rate, nper) - 1) / rate))
    if nper == 0:
        return 0.0
    return (-pv_ - fv_) / nper


def pembulatan(x: float, m) -> float:
    m_val = to_float(m)
    if m_val <= 0:
        return x
    m_int = int(m_val)
    if m_int == 0:
        return x
    if int(x) % m_int == 0:
        return x
    return math.ceil(x / m_val) * m_val


def calc_rental_decl(op: float, tenor: float, pay_cycle: float, decl_rate: float, adv_arr: str, g_period: float) -> float:
    n = (tenor - g_period) / pay_cycle
    i = decl_rate * pay_cycle / 1200
    x1 = 1 + i
    if adv_arr == "V":
        x2 = pangkat(x1, -n + 1)
        return (op * i) / (x1 - x2)
    x2 = pangkat(x1, -n)
    return (op * i) / (1 - x2)


def calc_rental_decl_fl(l_amount: float, security: float, residual: float, tot_loan: float, tenor: float,
                        pay_cycle: float, decl_rate: float, adv_arr: str, g_period: float) -> float:
    n = (tenor - g_period) / pay_cycle
    i = decl_rate * pay_cycle / 1200
    x1 = 1 + i
    x4 = pangkat(x1, n)
    base = (l_amount - security + tot_loan) - ((residual - security + tot_loan) / x4)
    if adv_arr == "V":
        x2 = pangkat(x1, -n + 1)
        return base * i / (x1 - x2)
    x2 = pangkat(x1, -n)
    return base * i / (1 - x2)


def calc_rental_flat(op: float, tenor: float, pay_cycle: float, flat_rate: float, g_period: float) -> float:
    n = (tenor - g_period) / pay_cycle
    mrate = flat_rate * (tenor - g_period) / 1200
    income = mrate * op
    return (op + income) / n


def calc_flat_rental(op: float, tenor: float, pay_cycle: float, installment: float, g_period: float) -> float:
    n = (tenor - g_period) / pay_cycle
    return ((installment * n - op) / op) * (12 / (tenor - g_period)) * 100


def calc_flat_rental_1000(op: float, tenor: float, pay_cycle: float, installment: float, g_period: float,
                          tenor_asli: float) -> float:
    sisa_tenor = tenor_asli - tenor
    total_bayar = ((tenor / pay_cycle) * installment) + ((sisa_tenor / pay_cycle) * 1000)
    return ((total_bayar - op) / op) * (12 / (tenor_asli - g_period)) * 100


def _newton_decl(n: float, mrate: float, adv_arr: str, q0_offset: float) -> float:
    a = n / (mrate * n + 1)
    q1 = 1 + (2 * mrate)
    q0 = q1 + q0_offset
    if adv_arr == "V":
        xn = n - 1
        d = a * (n - 1)
        b = a
        a = a - 1
        c = a * n
    else:
        xn = n
        b = a + 1
        d = (a + 1) * n
        c = a * (n + 1)
    i = 0
    while abs(q0 - q1) > 0.00000001 and i < 30:
        v = 1.0
        rq = 1 / q1
        j = 1
        while j <= xn - 1:
            v = v * rq
            j += 1
        q0 = q1
        denominator = c * q1 - d
        if denominator == 0:
            break
        q1 = q1 - (a * q1 * q1 - b * q1 + v) / denominator
        i += 1
    return q1


def calc_decl_flat(flat_rate: float, pay_cycle: float, tenor: float, g_period: float, adv_arr: str) -> float:
    n = (tenor - g_period) / pay_cycle
    mrate = flat_rate / 1200 * pay_cycle
    q1 = _newton_decl(n, mrate, adv_arr, 0.001)
    return (q1 - 1) * (1200 / pay_cycle)


def dik_installment1(op: float, tenor: float, pay_cycle: float, totbyr: float, adv_arr: str) -> float:
    n = tenor / pay_cycle
    flat_rate = ((totbyr - op) / op) * 12 / tenor * 100
    mrate = flat_rate * pay_cycle / 1200
    q1 = _newton_decl(n, mrate, adv_arr, 0.01)
    return (q1 - 1) * (1200 / pay_cycle)


def _search_interest(op: float, start_interest: float, project) -> float:
    cur_value = project(start_interest, op)
    prev_sign = cur_value >= 0
    interest = start_interest
    additive = 0.01
    guard = 0
    while guard < LOOP_GUARD:
        guard += 1
        cur_value = project(interest, op)
        cur_sign = cur_value >= 0
        if abs(cur_value) < 0.001:
            break
        if cur_value < 0:
            interest = interest + additive
        else:
            interest = interest - additive
        if prev_sign != cur_sign:
            additive = additive * 0.01
            prev_sign = cur_sign
    return interest


def calc_decl_flat_1000(flat_rate: float, pay_cycle: float, tenor: float, g_period: float, adv_arr: str,
                        totnetfinance1: float, tenor1000: float, installment: float) -> float:
    n = (tenor - g_period) / pay_cycle
    sisa_tenor = tenor - tenor1000
    mrate = flat_rate / 1200 * pay_cycle
    q1 = _newton_decl(n, mrate, adv_arr, 0.01)
    decl_rate = (q1 - 1) * (1200 / pay_cycle)

    def project(rate: float, op: float) -> float:
        cur_value = op
        int_pay = tenor1000 / pay_cycle
        if adv_arr == "V":
            cur_value = cur_value - installment
            int_pay = int_pay - 1
        cur_value = fv(rate, int_pay, installment, -cur_value, 0)
        int_pay = sisa_tenor / pay_cycle
        return fv(rate, int_pay, 1000, -cur_value, 0)

    interest = _search_interest(totnetfinance1, decl_rate / 1200, project)
    return interest * 1200


def calc_step_rental_decl(op: float, pay_cycle: float, adv_arr: str, months: Sequence[float],
                          rentals: Sequence[float], tenor: float) -> float:
    totbyr = 0.0
    for month, rental in zip(months, rentals):
        totbyr += (month / pay_cycle) * rental
    if op > totbyr:
        return -1.0
    start = dik_installment1(op, tenor, pay_cycle, totbyr, adv_arr) / 1200

    def project(rate: float, current: float) -> float:
        cur_value = current
        for idx, (month, rental) in enumerate(zip(months, rentals)):
            int_pay = month / pay_cycle
            if idx == 0 and adv_arr == "V":
                cur_value = cur_value - rental
                int_pay = int_pay - 1
            cur_value = fv(rate, int_pay, rental, -cur_value, 0)
        return cur_value

    interest = _search_interest(op, start, project)
    return interest * 1200


def step_last_payment(total_net_finance: float, months: Sequence[float], rentals: Sequence[float],
                      rate_pa: float, pay_cycle: float, adv_arr: str, rounding) -> Optional[float]:
    no_step = len(months) - 1
    interest = (rate_pa * pay_cycle / 12) / 100
    cur_value = total_net_finance
    for idx in range(no_step):
        int_pay = months[idx] / pay_cycle
        if idx == 0 and adv_arr == "V":
            cur_value = cur_value - rentals[0]
            int_pay = int_pay - 1
        cur_value = fv(interest, int_pay, rentals[idx], -cur_value, 0)
    int_pay_last = months[no_step] / pay_cycle
    if int_pay_last == 0:
        return None
    payment = pmt(interest, int_pay_last, -cur_value, 0, 0)
    if payment < 1:
        return None
    return php_round(pembulatan(payment, rounding), 0)


def cigna_rate_percent(tenor_months: float) -> Optional[float]:
    years = math.ceil(to_float(tenor_months) / 12)
    return {1: 5, 2: 7, 3: 9.3, 4: 12, 5: 14}.get(years)