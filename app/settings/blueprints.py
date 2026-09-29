from __future__ import annotations

import importlib
import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import List, NamedTuple, Optional, Tuple

logger = logging.getLogger(__name__)
class BlueprintEntry(NamedTuple):
    module_path: str
    attr_name: str
    prefix: Optional[str] = None

BLUEPRINT_REGISTRY: List[BlueprintEntry] = [

    # ── System (health check, maintenance bypass)
    BlueprintEntry("app.system.routes_health",                                                          "health_bp"),

    # ── Auth & Core API
    BlueprintEntry("app.auth.routes_auth",                                                              "auth_bp",                               "/auth"),
    BlueprintEntry("app.api.routes_api_menus",                                                          "menu_bp",                               "/menu"),
    BlueprintEntry("app.services.common_api",                                                           "common_bp",                             "/Common"),

    # ── CAM Core
    BlueprintEntry("app.cam.add.routes_add_cam",                                                        "cam_bp",                                "/CAM"),
    BlueprintEntry("app.cam.onprocess.routes_onhand",                                                   "onhand_cam_bp",                         "/CAM"),
    BlueprintEntry("app.cam.onprocess.routes_cam_approval",                                             "cam_approval_bp",                       "/CAM/Approval"),
    BlueprintEntry("app.cam.onprocess.routes_cam_send_cmo",                                             "cam_send_cmo_bp",                       "/CAM/Approval/SendCMO"),
    BlueprintEntry("app.cam.onprocess.routes_reject_to_watchlist",                                      "cam_reject_watchlist_bp",               "/CAM/RejectWatchlist"),
    BlueprintEntry("app.cam.onprocess.routes_cam_onhand_delete",                                        "cam_onhand_delete_bp",                  "/CAM/Onhand/Delete"),
    BlueprintEntry("app.cam.onprocess.routes_inprogress",                                               "inprogress_cam_bp",                     "/CAM"),
    BlueprintEntry("app.cam.onprocess.routes_approved",                                                 "approved_cam_bp",                       "/CAM"),
    BlueprintEntry("app.cam.onprocess.routes_cam_revisi",                                               "revisi_cam_bp",                         "/CAM"),
    BlueprintEntry("app.cam.onprocess.routes_cam_edit",                                                 "cam_edit_bp",                           "/CAM/EditIndex"),
    
    BlueprintEntry("app.cam.onprocess.financing.routes_cam_financing",                                  "financing_bp",                          "/CAM/Financing"),
    
    BlueprintEntry("app.cam.customer_documents.routes",                                                 "customer_documents_bp",                 None),
    
    BlueprintEntry("app.cam.add.routes_cam_combo",                                                      "cam_combo_bp",                          "/CAM/Combo"),
    BlueprintEntry("app.cam.add.routes_cam_customer",                                                   "cam_customer_bp",                       "/CAM/Customer"),
    BlueprintEntry("app.cam.customer.routes_corporate_detail",                                          "corporate_detail_bp",                   "/CAM/CorporateDetail"),

    BlueprintEntry("app.cam.onprocess.routes_cam_view",                                                 "cam_view_bp",                           "/CAM/View"),

    # ── CAM Prechecking
    BlueprintEntry("app.cam.prechecking.routes_prechecking_individu",                                   "prechecking_individu_bp",               "/CAM/Prechecking"),
    BlueprintEntry("app.cam.prechecking.routes_prechecking_guarantor_individu",                         "prechecking_guarantor_bp",              "/CAM/Prechecking"),
    BlueprintEntry("app.cam.prechecking.routes_prechecking_corporate",                                  "prechecking_corporate_bp",              "/CAM/Prechecking"),
    BlueprintEntry("app.cam.prechecking.routes_prechecking_guarantor_corporate",                        "prechecking_guarantor_corporate_bp",    "/CAM/Prechecking"),
    BlueprintEntry("app.cam.prechecking.routes_ocr",                                                    "ocr_bp",                                "/Prechecking/OCR"),
    BlueprintEntry("app.cam.prechecking.routes_prechecking_onhand",                                     "prechecking_onhand_bp",                 "/Prechecking/Onhand"),
    BlueprintEntry("app.cam.prechecking.routes_view_prechecking",                                       "view_prechecking_bp",                   "/Prechecking/View"),
    BlueprintEntry("app.cam.prechecking.routes_prechecking_inprogress",                                 "prechecking_inprogress_bp",             "/Prechecking/Inprogress"),
    BlueprintEntry("app.cam.prechecking.routes_prechecking_approved",                                   "prechecking_approved_bp",               "/Prechecking/Approved"),
    BlueprintEntry("app.cam.prechecking.routes_approval_prechecking",                                   "approval_prechecking_bp",               "/Prechecking/Approval"),
    BlueprintEntry("app.cam.prechecking.routes_prechecking_rejected",                                   "prechecking_rejected_bp",               "/Prechecking/Rejected"),
    BlueprintEntry("app.cam.prechecking.routes_edit_prechecking_individu",                              "prechecking_edit_pr_bp",                "/Prechecking/EditPR"),
    BlueprintEntry("app.cam.prechecking.routes_edit_prechecking_corporate",                             "prechecking_edit_pt_bp",                "/Prechecking/EditPT"),
    BlueprintEntry("app.cam.prechecking.routes_onhand_detail",                                          "onhand_detail_bp",                      "/Prechecking/OnhandDetail"),

    # ── CAM Reports
    BlueprintEntry("app.cam.reportview.editcam.routes_edit_cam_by_ma",                                  "edit_cam_by_ma_bp",                     "/CAM/Edit"),
    BlueprintEntry("app.cam.reportview.editcam.routes_edit_insurance",                                  "edit_insurance_bp",                     "/CAM/Edit"),

    BlueprintEntry("app.cam.reportview.listapprovedcam.routes_list_in_progress_cam",                    "in_progress_cam_bp",                    "/CAM/Approved"),
    BlueprintEntry("app.cam.reportview.listapprovedcam.routes_list_cam_by_approval_date",               "cam_by_app_date_bp",                    "/CAM/Approved"),
    BlueprintEntry("app.cam.reportview.listapprovedcam.routes_list_cam_by_approver",                    "cam_by_approver_bp",                    "/CAM/Approved"),
    BlueprintEntry("app.cam.reportview.listapprovedcam.routes_list_cam_by_car_condition",               "cam_by_car_condition_bp",               "/CAM/Approved"),
    BlueprintEntry("app.cam.reportview.listapprovedcam.routes_approved_by_dealer",                      "approved_cam_by_dealer_bp",             "/CAM/Approved"),
    BlueprintEntry("app.cam.reportview.listapprovedcam.routes_list_rejected_cam",                       "rejected_cam_bp",                       "/CAM/Approved"),
    BlueprintEntry("app.cam.reportview.listapprovedcam.routes_summary_approved_cam",                    "summary_approved_cam_bp",               "/CAM/Approved"),
    BlueprintEntry("app.cam.reportview.listapprovedcam.routes_all_cam_data",                            "all_cam_data_bp",                       "/CAM/Approved"),
    BlueprintEntry("app.cam.reportview.listapprovedcam.routes_list_cam_by_disbursement_date",           "cam_by_disbursement_date_bp",           "/CAM/Approved"),
    BlueprintEntry("app.cam.reportview.listapprovedcam.routes_list_cam_by_customer_group",               "cam_by_cust_group_bp",                 "/CAM/Approved"),
    BlueprintEntry("app.cam.reportview.listapprovedcam.routes_all_insurance_data",                      "all_insurance_data_bp",                 "/CAM/Approved"),

    BlueprintEntry("app.cam.reportview.cmoproductivityreport.routes_cmo_daily_productivity",            "cmo_daily_productivity_bp",             "/CAM/CMO"),
    BlueprintEntry("app.cam.reportview.cmoproductivityreport.routes_cmo_daily_productivity_by_branch",  "cmo_daily_productivity_by_branch_bp",   "/CAM/CMO"),
    BlueprintEntry("app.cam.reportview.cmoproductivityreport.routes_cmo_daily_productivity_by_cmo",     "cmo_daily_productivity_by_cmo_bp",      "/CAM/CMO"),

    BlueprintEntry("app.cam.reportview.incentive.routes_detail_incentive",                              "detail_incentive_3rd_party_bp",         "/CAM/Incentive"),
    BlueprintEntry("app.cam.reportview.incentive.routes_history_incentive",                             "history_incentive_3rd_party_bp",        "/CAM/Incentive"),
    BlueprintEntry("app.cam.reportview.commission.company.routes_commission_company",                   "commission_company_bp",                 "/CAM/Commission"),
    BlueprintEntry("app.cam.reportview.commission.individu.routes_detail_commission",                   "commission_individual_detail_bp",       "/CAM/Commission"),
    BlueprintEntry("app.cam.reportview.commission.individu.routes_history_commission",                  "commission_individual_history_bp",      "/CAM/Commission"),

    BlueprintEntry("app.cam.reportview.others.routes_nett_booking_appi",                                "nett_booking_appi_bp",                  "/CAM/Others"),
    BlueprintEntry("app.cam.reportview.others.routes_undisbursed_contract",                             "undisburse_contract_bp",                "/CAM/Others"),
    BlueprintEntry("app.cam.reportview.others.routes_pending_contract_will_be_deleted",                 "pending_contract_delete_bp",            "/CAM/Others"),
    BlueprintEntry("app.cam.reportview.others.routes_history_bpkb_submission",                          "history_bpkb_submission_bp",            "/CAM/Others"),
    BlueprintEntry("app.cam.reportview.others.routes_laporan_pelunasan_mobil",                          "laporan_pelunasan_bp",                  "/CAM/Others"),
    BlueprintEntry("app.cam.reportview.others.routes_monthly_summary_cam_approved",                     "monthly_summary_cam_approved_bp",       "/CAM/Others"),
    BlueprintEntry("app.cam.reportview.others.routes_f6pd",                                             "f6pd_bp",                               "/CAM/Others"),
    BlueprintEntry("app.cam.reportview.others.routes_top_20_customer",                                  "top20_customer_bp",                     "/CAM/Others"),
    BlueprintEntry("app.cam.reportview.others.routes_prechecking_and_cam_sla",                          "prechecking_and_cam_sla_bp",            "/CAM/Others"),
    BlueprintEntry("app.cam.reportview.others.routes_customer_outstanding",                             "customer_outstanding_bp",               "/CAM/Others"),
    BlueprintEntry("app.cam.reportview.others.routes_summary_rundown_osp",                              "summary_rundown_osp_bp",                "/CAM/Others"),
    BlueprintEntry("app.cam.reportview.others.routes_history_mrp",                                      "history_mrp_bp",                        "/CAM/Others"),

    # ── Master Data
    BlueprintEntry("app.masterdata.sales.routes_sales",                                                 "sales_bp",                              "/MasterData"),
    BlueprintEntry("app.masterdata.sales.routes_sales_entry",                                           "sales_entry_bp",                        "/MasterData"),
    BlueprintEntry("app.masterdata.sales.routes_list_of_sales",                              			"sales_report_bp",                       "/MasterData"),
    BlueprintEntry("app.masterdata.dealer.routes_dealer",                                    			"dealer_bp",                             "/MasterData"),
    BlueprintEntry("app.masterdata.dealer.routes_list_of_dealer",                            			"dealer_report_bp",                      "/MasterData"),
    BlueprintEntry("app.masterdata.dealer.routes_report_dealer_deleted",                     			"deleted_dealer_report_bp",              "/MasterData"),
    BlueprintEntry("app.masterdata.objectcollateral.model.routes_model",                     			"model_bp",                              "/MasterData"),
    BlueprintEntry("app.masterdata.objectcollateral.model.routes_list_of_model",             			"list_model_bp",                         "/MasterData"),
    BlueprintEntry("app.masterdata.objectcollateral.karoseri.routes_karoseri",                			"karoseri_bp",                           "/MasterData"),
    BlueprintEntry("app.masterdata.objectcollateral.karoseri.routes_list_of_karoseri",       			"list_karoseri_bp",                      "/MasterData"),
    BlueprintEntry("app.masterdata.objectcollateral.brand.routes_brand",                     			"brand_bp",                              "/MasterData"),
    BlueprintEntry("app.masterdata.objectcollateral.brand.routes_brand_vehicle",             			"brand_vehicle_bp",                      "/MasterData"),
    BlueprintEntry("app.masterdata.objectcollateral.brand.routes_list_of_brand",             			"list_brand_bp",                         "/MasterData"),
    BlueprintEntry("app.masterdata.insurance.routes_insurance",                              			"insurance_master_bp",                   "/MasterData"),
    BlueprintEntry("app.masterdata.insurance.routes_list_of_insurance",                      			"insurance_list_bp",                     "/MasterData"),
    BlueprintEntry("app.masterdata.group.routes_group",                                      			"group_bp",                              "/MasterData"),
    BlueprintEntry("app.masterdata.group.routes_group_report",                               			"group_report_bp",                       "/MasterData"),
    BlueprintEntry("app.masterdata.watchlist.routes_watchlist",                              			"watchlist_bp",                          "/MasterData"),
    BlueprintEntry("app.masterdata.watchlist.routes_watchlist_report",                       			"watchlist_report_bp",                   "/MasterData"),
    BlueprintEntry("app.masterdata.watchlist.routes_watchlist_by_corsec",                    			"watchlist_by_corsec_bp",                "/MasterData"),
    BlueprintEntry("app.masterdata.watchlist.routes_search_customer",                        			"customer_lookup_bp",                    "/MasterData"),
    BlueprintEntry("app.masterdata.watchlist.routes_document",                               			"attachment_files_bp",                   "/MasterData"),
    BlueprintEntry("app.masterdata.blacklist.routes_blacklist",                              			"blacklist_bp",                          "/MasterData"),
    BlueprintEntry("app.masterdata.blacklist.routes_blacklist_report",                       			"blacklist_report_bp",                   "/MasterData"),
    BlueprintEntry("app.masterdata.blacklist.routes_list_pelaporan_terduga_teroris",         			"ttot_report_bp",                        "/MasterData"),
    BlueprintEntry("app.masterdata.thresholddeviation.routes_master_data_threshold",         			"master_data_threshold_bp",              "/MasterData"),
    BlueprintEntry("app.masterdata.thresholddeviation.routes_master_data_ratio",             			"master_data_ratio_bp",                  "/MasterData"),
    BlueprintEntry("app.masterdata.thresholddeviation.routes_master_date_npf",               			"master_data_npf_bp",                    "/MasterData"),
    BlueprintEntry("app.masterdata.thresholddeviation.routes_master_data_deviation_dp",      			"master_data_deviation_dp_bp",           "/MasterData"),
    BlueprintEntry("app.masterdata.thresholddeviation.routes_master_data_deviation_dp_view", 			"master_data_deviation_dp_view_bp",      "/MasterData"),
    BlueprintEntry("app.masterdata.industrial.routes_industrial_code",                       			"industry_bp",                           "/MasterData"),

    # ── System Admin
    BlueprintEntry("app.menuuseraccess.routes_menu_access",                                  			"menu_user_access_bp",					 "/SystemAdmin"),
    BlueprintEntry("app.menuuseraccess.routes_user_access",                                  			"uacc_bp",								 "/SystemAdmin"),
    BlueprintEntry("app.menuuseraccess.routes_users",                                        			"users_bp",								 "/SystemAdmin"),
    BlueprintEntry("app.menuuseraccess.routes_dashboard",                                        	    "dashboard_bp",							 "/SystemAdmin"),

    # ── Disbursement
    BlueprintEntry("app.disbursement.routes_jurnal_financing",                               			"jurnal_financing_bp",					 "/JurnalFinancing"),

    # ── History Payment
    BlueprintEntry("app.historypayment.routes_history_payment",                              			"history_payment_bp",					 "/HistoryPayment"),
    BlueprintEntry("app.historypayment.summaryaging.routes_summary_aging_report",            			"summary_aging_bp",						 "/SummaryAging"),

    # ── E-Pay / Virtual Account
    BlueprintEntry("app.espay.routes_espay_va",                                                 	    "va_bp",								 "/va"),
    BlueprintEntry("app.espay.routes_espay_invoice",                                                    "espay_bp",								 "/Espay"),

    # ── OJK
    BlueprintEntry("app.ojk.routes_form10",                                                  			"form10_bp",							 "/Form10"),
    BlueprintEntry("app.ojk.routes_sipesat",                                                 			"sipesat_bp",							 "/SIPESAT"),
    BlueprintEntry("app.ojk.routes_slik",                                                    			"slik_bp",								 "/SLIK"),

    # ── Insurance
    BlueprintEntry("app.insurance.routes_insurance",                                         			"insurance_bp",							 "/Insurance"),
    BlueprintEntry("app.insurance.routes_insurance_entry",                                   			"insurance_entry_bp",					 "/InsuranceEntry"),
    BlueprintEntry("app.insurance.routes_insurance_report",                                  			"insurance_report_bp",					 "/InsuranceReport"),

    # ── Delima & Fiducia
    BlueprintEntry("app.delima.routes_delima",                                               			"delima_bp",							 "/Delima"),
    BlueprintEntry("app.delima.routes_fiducia_report",                                       			"fiducia_bp",							 "/FiduciaReport"),

    # ── GPS
    BlueprintEntry("app.gps.routes_gps",                                                     			"gps_bp",								 "/GPS"),

    # ── Employee
    BlueprintEntry("app.employee.routes_employee",                                           			"employee_bp",							 "/Employee"),
    BlueprintEntry("app.employee.routes_employee_memo",                                      			"employee_memo_bp",						 "/Employee"),
]

def _import_blueprint(entry: BlueprintEntry):
    try:
        module = importlib.import_module(entry.module_path)
        return entry, getattr(module, entry.attr_name)
    except (ImportError, AttributeError):
        logger.critical("Failed to load blueprint '%s' from '%s'", entry.attr_name, entry.module_path)
        raise

_cache_lock = Lock()
_resolved_cache: Optional[List[Tuple[BlueprintEntry, object]]] = None

def _resolve_blueprints(workers: int) -> List[Tuple[BlueprintEntry, object]]:
    global _resolved_cache
    if _resolved_cache is not None:
        return _resolved_cache

    with _cache_lock:
        if _resolved_cache is not None:
            return _resolved_cache

        seen = set()
        for e in BLUEPRINT_REGISTRY:
            if e.attr_name in seen:
                raise ValueError(f"Duplicate blueprint attr_name '{e.attr_name}'")
            seen.add(e.attr_name)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            _resolved_cache = list(pool.map(_import_blueprint, BLUEPRINT_REGISTRY))

    return _resolved_cache

def clear_blueprint_cache() -> None:
    global _resolved_cache
    with _cache_lock:
        _resolved_cache = None

def register_blueprints(app, version: str = "v1", workers: int = 16) -> int:
    results = _resolve_blueprints(workers)

    for entry, blueprint in results:
        kwargs = {"url_prefix": f"/api/{version}{entry.prefix}"} if entry.prefix else {}
        app.register_blueprint(blueprint, **kwargs)

    logger.info("Registered %d blueprints under /api/%s.", len(results), version)
    return len(results)