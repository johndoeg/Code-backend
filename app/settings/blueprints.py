def register_blueprints(app):

    from app.auth.routes_auth import auth_bp
    from app.api.routes import api_bp
    from app.services.common_api import common_bp
  
    from app.cam.routes import cam_bp
    from app.cam.onprocess.routes_onhand import onhand_cam_bp
    from app.cam.generator.routes_generator import generator_bp
    from app.cam.customer.routes_customer_detail import customer_bp
    from app.cam.prechecking.routes_prechecking_individu import prechecking_individu_bp
    from app.cam.prechecking.routes_prechecking_onhand import prechecking_onhand_bp
    from app.cam.prechecking.routes_rejected import prechecking_rejected_bp
    
    from app.masterdata.sales.routes_sales import sales_bp
    from app.masterdata.sales.routes_list_of_sales import sales_report_bp
    from app.masterdata.dealer.routes_dealer import dealer_bp
    from app.masterdata.dealer.routes_list_of_dealer import dealer_report_bp
    from app.masterdata.dealer.routes_report_dealer_deleted import deleted_dealer_report_bp
    from app.masterdata.objectcollateral.routes_model import model_bp
    from app.masterdata.objectcollateral.routes_karoseri import karoseri_bp
    from app.masterdata.objectcollateral.routes_brand import brand_bp
    from app.masterdata.objectcollateral.routes_brand_vehicle import brand_vehicle_bp
    from app.masterdata.objectcollateral.routes_list_of_brand import list_brand_bp
    from app.masterdata.objectcollateral.routes_list_of_model import list_model_bp
    from app.masterdata.objectcollateral.routes_list_of_karoseri import list_karoseri_bp
    from app.masterdata.insurance.routes_insurance import insurance_master_bp
    from app.masterdata.insurance.routes_list_of_insurance import insurance_list_bp
    from app.masterdata.group.routes_group import group_bp
    from app.masterdata.group.routes_group_report import group_report_bp
    from app.masterdata.watchlist.route_watchlist import watchlist_bp
    from app.masterdata.blacklist.route_blacklist import blacklist_bp
    from app.masterdata.industrial.routes_industrial_code import industry_bp
    
    from app.menuuseraccess.routes_menu_access import menu_user_access_bp
    from app.menuuseraccess.routes_user_access import uacc_bp
    from app.menuuseraccess.routes_users import users_bp
    
    from app.disbursement.routes_jurnal_financing import jurnal_financing_bp
    
    from app.historypayment.routes_history_payment import history_payment_bp
    from app.historypayment.summaryaging.routes_summary_aging_report import summary_aging_bp
    
    from app.espay.routes_espay import va_bp
    
    from app.ojk.routes_form10 import form10_bp
    from app.ojk.routes_sipesat import sipesat_bp
    from app.ojk.routes_slik import slik_bp

    from app.insurance.routes_insurance import insurance_bp
    from app.insurance.routes_insurance_entry import insurance_entry_bp
    from app.insurance.routes_insurance_report import insurance_report_bp

    from app.delima.routes_delima import delima_bp
    from app.delima.routes_fiducia_report import fiducia_bp
    
    from app.gps.routes_gps import gps_bp
    
    from app.employee.routes_employee import employee_bp
    from app.employee.routes_employee_memo import employee_memo_bp
    
    BLUEPRINTS = [
        (auth_bp, "/auth"),
        (api_bp, "/api"),
        (common_bp, None),
        (cam_bp, None),
        (onhand_cam_bp, "/CAM"),
        (customer_bp, None),
        (generator_bp, None),
        (prechecking_individu_bp, None),
        (prechecking_onhand_bp, None),
        (prechecking_rejected_bp, None),
        
        (sales_bp, "/MasterData"),
        (sales_report_bp, "/MasterData"),
        (dealer_bp, "/MasterData"),
        (dealer_report_bp, "/MasterData"),
        (deleted_dealer_report_bp, "/MasterData"),
        (model_bp, "/MasterData"),
        (karoseri_bp, "/MasterData"),
        (brand_bp, "/MasterData"),
        (brand_vehicle_bp, "/MasterData"),
        (list_brand_bp, "/MasterData"),
        (list_model_bp, "/MasterData"),
        (list_karoseri_bp, "/MasterData"),
        (group_bp, "/MasterData"),
        (group_report_bp, "/MasterData"),
        (insurance_master_bp, "/MasterData"),
        (insurance_list_bp, "/MasterData"),
        (watchlist_bp, "/MasterData"),
        (blacklist_bp, "/MasterData"),
        (industry_bp, "/MasterData"),
        
        (menu_user_access_bp, "/SystemAdmin"),
        (uacc_bp, "/SystemAdmin"),
        (users_bp, "/SystemAdmin"),
        
        (jurnal_financing_bp, "/JurnalFinancing"),
        
        (history_payment_bp, "/HistoryPayment"),
        (summary_aging_bp, "/SummaryAging"),
        
        (va_bp, None),
        
        (form10_bp, "/Form10"),
        (sipesat_bp, None),
        (slik_bp, None),
        
        (insurance_bp, "/Insurance"),
        (insurance_entry_bp, "/InsuranceEntry"),
        (insurance_report_bp, "/InsuranceReport"),
        
        (delima_bp, None),
        (fiducia_bp, None),
        
        (gps_bp, "/GPS"),
        (employee_bp, None),
        (employee_memo_bp, None),
    ]

    for blueprint, prefix in BLUEPRINTS:
        if prefix:
            app.register_blueprint(blueprint, url_prefix=prefix)
        else:
            app.register_blueprint(blueprint)