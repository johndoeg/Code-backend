from sqlalchemy import text

def _pembulatan(value, rounding):
    value = float(value or 0)
    rounding = float(rounding or 0)
    if not rounding:
        return round(value)
    return round(value / rounding) * rounding

def _irr(investment, flow, precision=0.000001, max_iterations=20):
    if not flow:
        return 0.0
    if sum(flow.values()) < investment:
        return 0.0

    min_rate, max_rate = 0.0, 1.0
    net_present_value = 1.0
    guess = 0.0
    i = 0
    while abs(net_present_value - investment) > precision and i < max_iterations:
        net_present_value = 0.0
        guess = (min_rate + max_rate) / 2
        for period, cashflow in flow.items():
            net_present_value += cashflow / ((1 + guess) ** (period + 1))
        if net_present_value - investment > 0:
            min_rate = guess
        else:
            max_rate = guess
        i += 1
    return guess * 100

def hitung_irr(db, appl_no):
    row = db.session.execute(text("""
        SELECT (-(CASE WHEN cc.Cons_Leas='I' THEN (CASE WHEN cc.AdmFee>=2500000 THEN 2500000 ELSE ISNULL(cc.AdmFee,0) END)
                       ELSE (CASE WHEN cc.AdmFee>=5000000 THEN 5000000 ELSE ISNULL(cc.AdmFee,0) END) END)
              - ISNULL(Survey_Fee_Cigna,0) - ISNULL(cc.Provision,0)
              - (ISNULL(cc.gross,0) - ISNULL(cc.Notary,0) - ISNULL(cc.fiduciary,0))
              - (ISNULL(ServiceAgencyFee,0) - ISNULL(NettServiceAgencyFee,0))
              + ISNULL(Credit_Protection,0))
            + (-(ISNULL(gross_prem,0) - ISNULL(net,0)))
            + (ISNULL(commission, 0))
            + (ROUND((ISNULL(cc.Refund_Supp,0) - ISNULL(cc.Subsidy_Supp,0)
                     - (CASE WHEN cc.INCENTIVE = 1 THEN ISNULL(cc.Subsidy,0)/0.85 ELSE ISNULL(cc.Subsidy,0) END)), 0)) AS atr,
            cc.l_type, h.Net_Finance, cc.adv_arr, cc.rental, cc.tenor, ISNULL(cc.G_PERIOD, 0) AS G_PERIOD,
            cc.PAY_CYCLE, cc.G_INT_AMT, cc.DECLRATE, i.ROUNDING,
            CASE WHEN a.EXECUTION IS NULL THEN '0' ELSE '1' END AS Disb
        FROM CAFCONT cc WITH (NOLOCK)
            LEFT JOIN CLFCONT a WITH (NOLOCK) ON cc.APPL_NO = a.APPL_NO
            LEFT JOIN cigna_fee b WITH (NOLOCK) ON cc.APPL_NO = b.APPL_NO
            LEFT JOIN BBN c WITH (NOLOCK) ON cc.APPL_NO = c.APPL_No AND c.BBNVia = 'MLCI'
            LEFT JOIN VDISBURSE d WITH (NOLOCK) ON cc.APPL_NO = d.APPL_NO
            LEFT JOIN CAFINSU e WITH (NOLOCK) ON cc.APPL_NO = e.APPL_NO
            LEFT JOIN (SELECT INS_POL, SUM(PREP_AMT) AS net FROM CAFINSUD WITH (NOLOCK) GROUP BY INS_POL) f ON e.INS_POL = f.INS_POL
            LEFT JOIN (SELECT appl_no, ROUND(SUM(ISNULL(GrossAmount,0)+ISNULL(PPNAMOUNT,0)),0) AS commission
                        FROM CAFKOMIS WITH (NOLOCK)
                        GROUP BY APPL_NO) g ON cc.APPL_NO = g.APPL_NO
            LEFT JOIN V_NetFinance h WITH (NOLOCK) ON cc.APPL_NO = h.APPL_NO
            LEFT JOIN UMFCURR i WITH (NOLOCK) ON cc.CURR_CODE = i.CURR_CODE
        WHERE cc.appl_no = :appl_no
    """), {"appl_no": appl_no}).mappings().first()

    if not row:
        return 0.0

    l_type = row["l_type"]
    net_finance = float(row["Net_Finance"] or 0)
    net_finance_psak = net_finance + float(row["atr"] or 0)
    g_period = float(row["G_PERIOD"] or 0)
    pay_cycle = float(row["PAY_CYCLE"] or 1)
    tenor = float(row["tenor"] or 0)
    declrate = float(row["DECLRATE"] or 0)
    rounding = row["ROUNDING"]
    disburse_date = row["Disb"]
    net_finance_fix = net_finance

    if disburse_date == '0':
        flow = {}
        n = 0
        investment = net_finance_psak
        start = 1

        if g_period > 0:
            start = int(g_period + 1)
            sisa_tenor = (tenor - g_period) / pay_cycle
            for _ in range(int(g_period / pay_cycle)):
                flow[n] = float(row["G_INT_AMT"] or 0)
                n += 1
        else:
            sisa_tenor = tenor / pay_cycle
            if row["adv_arr"] == 'V':
                if l_type == '3':
                    step = db.session.execute(
                        text("EXEC USP_GET_STEP_RENTAL :appl_no, '1'"),
                        {"appl_no": appl_no},
                    ).mappings().first() or {}
                    investment = net_finance_psak - float(step.get("rental") or 0)
                else:
                    investment = net_finance_psak - float(row["rental"] or 0)
                    net_finance_fix = net_finance - float(row["rental"] or 0)
                start = 2
            elif row["adv_arr"] == 'R':
                investment = net_finance_psak
                start = 1

        i = start
        while i <= sisa_tenor:
            if l_type in ('0', '1'):
                flow[n] = float(row["rental"] or 0)
            elif l_type == '2':
                recovery = net_finance / sisa_tenor if sisa_tenor else 0
                income = (net_finance_fix * declrate) * (pay_cycle / 1200)
                flow[n] = _pembulatan(recovery + income, rounding)
                net_finance_fix -= recovery
            elif l_type == '3':
                step = db.session.execute(
                    text("EXEC USP_GET_STEP_RENTAL :appl_no, :i"),
                    {"appl_no": appl_no, "i": i},
                ).mappings().first() or {}
                flow[n] = float(step.get("rental") or 0)
            elif l_type == '6':
                income = (net_finance * declrate) * (pay_cycle / 1200)
                flow[n] = _pembulatan(income, rounding)
                if i == sisa_tenor:
                    flow[n] = _pembulatan(income + net_finance, rounding)
            n += 1
            i += 1

        irr = _irr(investment, flow) * 12 / pay_cycle if pay_cycle else 0
    else:
        actual = db.session.execute(text("""
            SELECT IRR_Actual FROM CAFCONT_IRR WHERE APPL_NO = :appl_no
        """), {"appl_no": appl_no}).mappings().first()
        irr = float(actual["IRR_Actual"]) if actual and actual["IRR_Actual"] is not None else 0.0

    irr = round(irr, 2)

    existing = db.session.execute(text("""
        SELECT xx.APPL_NO, xx.IRR_Actual,
               CASE WHEN zz.EXECUTION IS NULL THEN '0' ELSE '1' END AS Disb
        FROM CAFCONT_IRR xx
            LEFT JOIN CLFCONT zz ON zz.APPL_NO = xx.APPL_NO
        WHERE xx.APPL_NO = :appl_no
    """), {"appl_no": appl_no}).mappings().first()

    if existing and existing["APPL_NO"] and existing["Disb"] == '0':
        db.session.execute(text("""
            UPDATE CAFCONT_IRR SET IRR_Actual = :irr WHERE APPL_NO = :appl_no
        """), {"irr": irr, "appl_no": appl_no})
    else:
        db.session.execute(text("""
            INSERT INTO CAFCONT_IRR (APPL_NO, IRR_Actual) VALUES (:appl_no, :irr)
        """), {"appl_no": appl_no, "irr": irr})

    return irr