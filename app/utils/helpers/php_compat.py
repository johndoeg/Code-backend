from __future__ import annotations

import math
import re
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

_LEADING_NUMBER = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?")

def php_float(value: Any) -> float:
    if value is None or value is False:
        return 0.0
    if value is True:
        return 1.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, Decimal):
        return float(value)
    text = str(value).strip()
    if not text:
        return 0.0
    match = _LEADING_NUMBER.match(text)
    if match is None:
        return 0.0
    return float(match.group(0))

def php_int(value: Any) -> int:
    number = php_float(value)
    if math.isnan(number) or math.isinf(number):
        return 0
    return int(number)

def php_str(value: Any) -> str:
    if value is None:
        return ""
    if value is True:
        return "1"
    if value is False:
        return ""
    return str(value).strip()

def strip_thousands(value: Any) -> str:
    return php_str(value).replace(",", "")

def money_input(value: Any) -> float:
    return php_float(strip_thousands(value))

def number_format(value: Any, decimals: int = 0) -> str:
    number = php_float(value)
    if math.isnan(number) or math.isinf(number):
        number = 0.0
    quantum = Decimal(1).scaleb(-decimals)
    rounded = Decimal(repr(number)).quantize(quantum, rounding=ROUND_HALF_UP)
    sign = "-" if rounded < 0 else ""
    digits = f"{abs(rounded):.{decimals}f}"
    if decimals > 0:
        whole, fraction = digits.split(".")
    else:
        whole, fraction = digits, ""
    grouped = f"{int(whole):,}"
    if decimals > 0:
        return f"{sign}{grouped}.{fraction}"
    return f"{sign}{grouped}"

def clamp_zero(value: float) -> float:
    return 0.0 if value < 0 else value