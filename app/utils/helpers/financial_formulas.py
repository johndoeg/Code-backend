from __future__ import annotations

import math
from typing import Optional, Sequence

def pv(rate: float, nper: float, pmt: float, fv: float = 0.0, due: int = 0) -> float:
    if rate == 0:
        return -(fv + pmt * nper)
    pvif = (1 + rate) ** nper
    fvifa = (pvif - 1) / rate
    if due:
        fvifa *= (1 + rate)
    return -(fv + pmt * fvifa) / pvif

def fv(rate: float, nper: float, pmt: float, pv: float = 0.0, due: int = 0) -> float:
    if rate == 0:
        return -(pv + pmt * nper)
    pvif = (1 + rate) ** nper
    fvifa = (pvif - 1) / rate
    if due:
        fvifa *= (1 + rate)
    return -(pv * pvif + pmt * fvifa)

def pmt(rate: float, nper: float, pv: float, fv: float = 0.0, due: int = 0) -> float:
    if rate == 0:
        if nper == 0:
            return 0.0
        return -(pv + fv) / nper
    pvif = (1 + rate) ** nper
    payment = rate / (pvif - 1) * -(pv * pvif + fv)
    if due:
        payment /= (1 + rate)
    return payment

def pembulatan(value: float, base: float = 1) -> float:
    base = base or 1
    if base == 0:
        base = 1
    return math.floor(value / base + 0.5) * base

def calc_rental_flat(
    principal: float,
    tenor_months: float,
    pay_cycle: float,
    flat_rate_pa: float,
    grace_period: float = 0,
) -> float:
    n_payments = (tenor_months - grace_period) / pay_cycle
    total_interest = principal * flat_rate_pa * (tenor_months - grace_period) / 1200
    return (principal + total_interest) / n_payments

def calc_flat_rental(
    principal: float,
    tenor_months: float,
    pay_cycle: float,
    installment: float,
    grace_period: float = 0,
) -> float:
    n_payments = (tenor_months - grace_period) / pay_cycle
    total_interest = installment * n_payments - principal
    return (total_interest / principal) * (12 / (tenor_months - grace_period)) * 100

def calc_decl_flat(
    flat_rate_pa: float,
    pay_cycle: float,
    tenor_months: float,
    grace_period: float,
    adv_arr: str,
) -> float:
    n = (tenor_months - grace_period) / pay_cycle
    mrate = flat_rate_pa / 1200 * pay_cycle
    a = n / (mrate * n + 1)
    q1 = 1 + (2 * mrate)
    q0 = q1 + 0.001
    i = 0
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

    while abs(q0 - q1) > 0.00000001 and i < 30:
        v = 1
        rq = 1 / q1
        j = 1
        while j <= xn - 1:
            v = v * rq
            j += 1
        q0 = q1
        q1 = q1 - (a * q1 * q1 - b * q1 + v) / (c * q1 - d)
        i += 1

    return (q1 - 1) * (1200 / pay_cycle)

def calc_rental_decl(
    principal: float,
    tenor_months: float,
    pay_cycle: float,
    decl_rate_pa: float,
    adv_arr: str,
    grace_period: float = 0,
) -> float:
    n = (tenor_months - grace_period) / pay_cycle
    rate_per_period = decl_rate_pa * pay_cycle / 1200
    due = 1 if adv_arr == "V" else 0
    return pmt(rate_per_period, n, -principal, 0.0, due)

def calc_rental_decl_fl(
    l_amount: float,
    security: float,
    residual: float,
    tot_loan: float,
    tenor_months: float,
    pay_cycle: float,
    decl_rate_pa: float,
    adv_arr: str,
    grace_period: float = 0,
) -> float:
    principal = l_amount - security + tot_loan
    n = (tenor_months - grace_period) / pay_cycle
    rate_per_period = decl_rate_pa * pay_cycle / 1200
    due = 1 if adv_arr == "V" else 0
    return pmt(rate_per_period, n, -principal, residual, due)

def solve_step_declining_rate(
    principal: float,
    months_per_step: Sequence[float],
    rentals_per_step: Sequence[float],
    pay_cycle: float,
    adv_arr: str,
    seed_rate_pa: float,
    max_iterations: int = 5000,
) -> float:
    def run_schedule(interest_per_period: float) -> float:
        cur_value = principal
        for idx, (months, rental) in enumerate(zip(months_per_step, rentals_per_step)):
            n_pay = months / pay_cycle
            if idx == 0 and adv_arr == "V":
                cur_value = cur_value - rental
                n_pay = n_pay - 1
            cur_value = fv(interest_per_period, n_pay, rental, -cur_value, 0)
        return cur_value

    interest = seed_rate_pa / 1200
    additive = 0.01

    cur_value = run_schedule(interest)
    prev_sign = cur_value >= 0

    for _ in range(max_iterations):
        cur_value = run_schedule(interest)
        cur_sign = cur_value >= 0

        if abs(cur_value) < 0.001:
            return interest * 1200

        if cur_value < 0:
            interest += additive
        else:
            interest -= additive

        if prev_sign != cur_sign:
            additive *= 0.01
            prev_sign = cur_sign

    raise RuntimeError(
        
    )

def _newton_flat_to_effective_q1(mrate: float, n: float, adv_arr: str) -> float:
    a = n / (mrate * n + 1)
    q1 = 1 + (2 * mrate)
    q0 = q1 + 0.01
    i = 0

    if adv_arr == "V":
        xn = n - 1
        d = a * (n - 1)
        b = a
        a = a - 1
        c = a * n
    elif adv_arr == "R":
        xn = n
        b = a + 1
        d = (a + 1) * n
        c = a * (n + 1)
    else:
        raise ValueError(f"adv_arr must be 'V' or 'R', got {adv_arr!r}")

    while abs(q0 - q1) > 0.00000001 and i < 30:
        v = 1.0
        rq = 1 / q1
        j = 1
        while j <= xn - 1:
            v = v * rq
            j = j + 1
        q0 = q1
        q1 = q1 - (a * q1 * q1 - b * q1 + v) / (c * q1 - d)
        i = i + 1

    return q1

def dik_installment1(
    op: float,
    tenor_months: float,
    pay_cycle: float,
    totbyr: float,
    adv_arr: str,
) -> float:
    n = tenor_months / pay_cycle
    flat_rate = ((totbyr - op) / op) * 12 / tenor_months * 100
    mrate = flat_rate * pay_cycle / 1200
    q1 = _newton_flat_to_effective_q1(mrate, n, adv_arr)
    return (q1 - 1) * (1200 / pay_cycle)

def hitung_step_rental(
    no_step: int,
    rental_step: Sequence[float],
    total_net_finance: float,
    tenor_months: float,
    grace_period: float,
    months: Sequence[float],
    decl_rate_pa: float,
    mlci_decl_pa: float,
    adv_arr: str,
    pay_cycle: float,
    rounding: float = 1,
) -> tuple[Optional[float], Optional[float]]:
    del tenor_months, grace_period

    interest = (decl_rate_pa * pay_cycle / 12) / 100
    interest2 = (mlci_decl_pa * pay_cycle / 12) / 100

    last_step_selling: Optional[float] = None
    cur_value = total_net_finance
    for idx in range(no_step):
        n_pay = months[idx] / pay_cycle
        if idx == 0 and adv_arr == "V":
            cur_value -= rental_step[0]
            n_pay -= 1
        cur_value = fv(interest, n_pay, rental_step[idx], -cur_value, 0)
    n_pay_last = months[no_step] / pay_cycle
    payment = pmt(interest, n_pay_last, -cur_value, 0, 0)
    if payment >= 1:
        last_step_selling = pembulatan(payment, rounding)

    last_step_base: Optional[float] = None
    if mlci_decl_pa != 0:
        cur_value2 = total_net_finance
        for idx in range(no_step):
            n_pay = months[idx] / pay_cycle
            if idx == 0 and adv_arr == "V":
                cur_value2 -= rental_step[0]
                n_pay -= 1
            cur_value2 = fv(interest2, n_pay, rental_step[idx], -cur_value2, 0)
        n_pay_last2 = months[no_step] / pay_cycle
        payment2 = pmt(interest2, n_pay_last2, -cur_value2, 0, 0)
        if payment2 >= 1:
            last_step_base = pembulatan(payment2, rounding)

    return last_step_selling, last_step_base

def calc_decl_flat_1000(
    flat_rate_pa: float,
    pay_cycle: float,
    tenor_months: float,
    grace_period: float,
    adv_arr: str,
    total_net_finance: float,
    tenor1000_months: float,
    installment: float,
) -> float:
    n = (tenor_months - grace_period) / pay_cycle
    sisa_tenor = tenor_months - tenor1000_months
    mrate = flat_rate_pa / 1200 * pay_cycle
    q1 = _newton_flat_to_effective_q1(mrate, n, adv_arr)
    seed_rate_pa = (q1 - 1) * (1200 / pay_cycle)

    return solve_step_declining_rate(
        principal=total_net_finance,
        months_per_step=[tenor1000_months, sisa_tenor],
        rentals_per_step=[installment, 1000],
        pay_cycle=pay_cycle,
        adv_arr=adv_arr,
        seed_rate_pa=seed_rate_pa,
    )

def calc_flat_rental_1000(
    op: float,
    tenor1000_months: float,
    pay_cycle: float,
    installment: float,
    grace_period: float,
    tenor_asli_months: float,
) -> float:
    sisa_tenor = tenor_asli_months - tenor1000_months
    total_paid = (tenor1000_months / pay_cycle) * installment + (sisa_tenor / pay_cycle) * 1000
    return ((total_paid - op) / op) * (12 / (tenor_asli_months - grace_period)) * 100