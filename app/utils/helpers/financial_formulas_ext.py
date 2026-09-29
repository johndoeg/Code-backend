from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Sequence

from app.utils.helpers import financial_formulas as ff

from .php_compat import number_format, php_float

ADVANCE = "V"
ARREARS = "R"

def _require_adv_arr(adv_arr: str) -> str:
    mode = (adv_arr or "").strip().upper()
    if mode not in (ADVANCE, ARREARS):
        raise ValueError(f"adv_arr must be '{ADVANCE}' or '{ARREARS}', got {adv_arr!r}")
    return mode

def _at(values: Sequence, index: int) -> float:
    if index < 0 or index >= len(values):
        return 0.0
    return php_float(values[index])

def pangkat(x: float, n: float) -> float:
    return math.exp(n * math.log(x))

def calc_flat_rental_1000(
    op: float,
    tenor: float,
    pay_cycle: float,
    installment: float,
    g_period: float,
    tenor_asli: float,
) -> float:
    sisa_tenor = tenor_asli - tenor
    total_paid = ((tenor / pay_cycle) * installment) + ((sisa_tenor / pay_cycle) * 1000)
    return ((total_paid - op) / op) * (12 / (tenor_asli - g_period)) * 100

def _newton_decl_rate(n: float, mrate: float, adv_arr: str, seed_gap: float, pay_cycle: float) -> float:
    mode = _require_adv_arr(adv_arr)
    a = n / (mrate * n + 1)
    q1 = 1 + (2 * mrate)
    q0 = q1 + seed_gap
    iterations = 0

    if mode == ADVANCE:
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

    while abs(q0 - q1) > 0.00000001 and iterations < 30:
        v = 1.0
        rq = 1 / q1
        j = 1
        while j <= xn - 1:
            v = v * rq
            j = j + 1
        q0 = q1
        q1 = q1 - (a * q1 * q1 - b * q1 + v) / (c * q1 - d)
        iterations = iterations + 1

    return (q1 - 1) * (1200 / pay_cycle)

def calc_decl_flat_1000(
    flat_rate: float,
    pay_cycle: float,
    tenor: float,
    g_period: float,
    adv_arr: str,
    tot_net_finance: float,
    tenor1000: float,
    installment: float,
) -> float:
    mode = _require_adv_arr(adv_arr)
    n = (tenor - g_period) / pay_cycle
    sisa_tenor = tenor - tenor1000
    mrate = flat_rate / 1200 * pay_cycle
    decl_rate = _newton_decl_rate(n, mrate, mode, 0.01, pay_cycle)
    interest = decl_rate / 1200

    def run(rate: float) -> float:
        current = tot_net_finance
        int_pay = tenor1000 / pay_cycle
        if mode == ADVANCE:
            current = current - installment
            int_pay = int_pay - 1
        current = ff.fv(rate, int_pay, installment, -current, 0)
        return ff.fv(rate, sisa_tenor / pay_cycle, 1000, -current, 0)

    prev_sign = run(interest) >= 0
    additive = 0.01

    while True:
        cur_value = run(interest)
        cur_sign = cur_value >= 0
        if abs(cur_value) < 0.001:
            break
        interest = interest + additive if cur_value < 0 else interest - additive
        if prev_sign != cur_sign:
            additive = additive * 0.01
            prev_sign = cur_sign

    return interest * 1200

def calc_op_in_arr(i: float, tenor: float, op: float, rental: float) -> float:
    x1 = 1 + i
    x2 = pangkat(x1, tenor)
    x3 = pangkat(x1, tenor) - 1
    x4 = i * pangkat(x1, tenor)
    return x2 * (op - (rental * (x3 / x4)))

def calc_op_in_adv(i: float, tenor: float, op: float, rental: float) -> float:
    x1 = 1 + i
    x2 = pangkat(x1, tenor - 1)
    x3 = pangkat(x1, tenor) - 1
    x4 = i * pangkat(x1, tenor)
    return x2 * (op - (rental * (x3 / x4)))

def calc_rental(i: float, tenor: float, op: float) -> float:
    x1 = 1 + i
    x2 = pangkat(x1, tenor) - 1
    x3 = i * pangkat(x1, tenor)
    return (op / x1) * (x3 / x2)

def dik_installment1(op: float, tenor: float, pay_cycle: float, totbyr: float, adv_arr: str) -> float:
    n = tenor / pay_cycle
    flat_rate = ((totbyr - op) / op) * 12 / tenor * 100
    mrate = flat_rate * pay_cycle / 1200
    return _newton_decl_rate(n, mrate, adv_arr, 0.01, pay_cycle)

@dataclass(frozen=True)
class StepRentalResult:
    last_payment: Optional[str]
    last_payment_mlci: Optional[str]
    cur_value: float

def _run_steps(
    no_step: int,
    rental_steps: Sequence,
    months: Sequence,
    start_value: float,
    interest: float,
    pay_cycle: float,
    adv_arr: str,
) -> float:
    current = start_value
    for index in range(0, no_step):
        int_pay = _at(months, index) / pay_cycle
        if index == 0 and adv_arr == ADVANCE:
            current = current - _at(rental_steps, 0)
            int_pay = int_pay - 1
        current = ff.fv(interest, int_pay, _at(rental_steps, index), -current, 0)
    return current

def step_rental(
    no_step: int,
    rental_steps: Sequence,
    tot_net_finance: float,
    months: Sequence,
    decl_rate: float,
    mlci_decl: float,
    adv_arr: str,
    pay_cycle: float,
    rounding,
    mlci_fallback_to_rental: bool = False,
    install=None,
) -> StepRentalResult:
    mode = (adv_arr or "").strip().upper()
    interest = (php_float(decl_rate) * pay_cycle / 12) / 100
    interest2 = (php_float(mlci_decl) * pay_cycle / 12) / 100

    cur_value = _run_steps(no_step, rental_steps, months, tot_net_finance, interest, pay_cycle, mode)
    payment = ff.pmt(interest, _at(months, no_step) / pay_cycle, -cur_value, 0, 0)
    last_payment = number_format(ff.pembulatan(payment, rounding), 0) if payment >= 1 else None

    if php_float(mlci_decl) != 0:
        cur_value2 = _run_steps(no_step, rental_steps, months, tot_net_finance, interest2, pay_cycle, mode)
        payment2 = ff.pmt(interest2, _at(months, no_step) / pay_cycle, -cur_value2, 0, 0)
        last_payment_mlci = number_format(ff.pembulatan(payment2, rounding), 0) if payment2 >= 1 else None
    elif mlci_fallback_to_rental:
        last_payment_mlci = number_format(ff.pembulatan(_at(rental_steps, no_step), rounding), 0)
    else:
        last_payment_mlci = None

    if install is not None and str(install).strip() != "":
        install_value = php_float(str(install).replace(",", ""))
        current_step1 = php_float(last_payment.replace(",", "")) if (no_step == 1 and last_payment) else 0.0
        difference = install_value - current_step1
        if difference > 0 and (difference <= 1000 or _at(months, 1) in (1.0, 2.0)):
            if no_step == 1:
                last_payment = number_format(install_value, 0)

    return StepRentalResult(last_payment, last_payment_mlci, cur_value)

def split_pipe(raw) -> List[str]:
    if raw is None:
        return [""]
    if isinstance(raw, (list, tuple)):
        return [str(item) for item in raw]
    return str(raw).split("||")