from __future__ import annotations

from flask import Blueprint

from .routes_calculation import calculation_bp
# from .routes_financing import financing_calc_bp
from .routes_subsidies import subsidies_bp

financing_bp = Blueprint("financing", __name__)

financing_bp.register_blueprint(calculation_bp)
# financing_bp.register_blueprint(financing_calc_bp)
financing_bp.register_blueprint(subsidies_bp)

__all__ = ["financing_bp"]
