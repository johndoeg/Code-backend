import { useCallback, useEffect, useState } from "react";
import api from "../../../../../api/axiosInstance";

export interface CAMFinancingInsurancePageProps {
    apless: string;
    applNo: string;
    finType: string;
    onSaved: (result: { apless: string; applno: string }) => void;
}

interface ComboOption {
    value: string;
    label: string;
}

const CLAUSE_NAMES = ["SRCC", "EQ", "FW", "AW", "COM", "TS"] as const;
type ClauseName = (typeof CLAUSE_NAMES)[number];

interface InsuranceRow {
    year: number;
    insAmt: number;
    tplAmt: string;
    tloAr: string;
    prerAmt: number;
    prepAmt: number;
    savePremi: number;
    savePremicla: number;
    clauseCodes: Partial<Record<ClauseName, string>>;
    clauseSelected: Partial<Record<ClauseName, boolean>>;
    clauseDisabled: boolean;
}

interface IncomeSummary {
    ttlIncome: number;
    ttlIncomeNet: number;
    survInc: number;
    subSurv: number;
    ttlSurv: number;
    baseSurv: number;
    exceSurv: number;
    survInc2: number;
    subSurv2: number;
    ttlSurv2: number;
    baseSurv2: number;
    exceSurv2: number;
    provInc: number;
    subProv: number;
    ttlProv: number;
    provExec: number;
    interestIncome: number;
    subInt: number;
    ttlInt: number;
    baseInterest: number;
    excInt: number;
    subsidyTotal: number;
    ttlSubTot: number;
    execInc: number;
    ttlExcTot: number;
    maxComm: number;
    percentage: number;
    eligibleComm: number;
    marketingFee: number;
}

function fmt(value: number | undefined | null) {
    if (value === undefined || value === null || Number.isNaN(value)) return "0";
    const digits = Math.round(value).toString();
    return digits.replace(/\B(?=(\d{3})+(?!\d))/g, ",").replace(/^-,/, "-");
}

const readonlyBoxCls = "w-32 rounded-lg border border-slate-200 bg-slate-50 p-2 text-right text-sm";
const selectCls = "w-full max-w-xs rounded-lg border border-slate-300 bg-white p-2 text-sm disabled:bg-slate-100";
const textInputCls = "w-32 rounded-lg border border-slate-300 bg-white p-2 text-sm";

export default function CAMFinancingInsurancePage({ apless, applNo, finType, onSaved }: CAMFinancingInsurancePageProps) {
    const [loading, setLoading] = useState(true);
    const [loadError, setLoadError] = useState("");

    const [insPol, setInsPol] = useState("");
    const [insCd, setInsCd] = useState("");
    const [payMethod, setPayMethod] = useState("");
    const [payMethodOptions, setPayMethodOptions] = useState<ComboOption[]>([]);
    const [model, setModel] = useState("");
    const [condition, setCondition] = useState("");
    const [conditionLabel, setConditionLabel] = useState("");
    const [bpkbArea, setBpkbArea] = useState("");
    const [insuranceAreaOptions, setInsuranceAreaOptions] = useState<ComboOption[]>([]);
    const [insuranceAreaDisabled, setInsuranceAreaDisabled] = useState(false);
    const [totalSeat, setTotalSeat] = useState("");
    const [grossPrem, setGrossPrem] = useState(0);
    const [netCom, setNetCom] = useState(0);

    const [companies, setCompanies] = useState<ComboOption[]>([]);
    const [models, setModels] = useState<ComboOption[]>([]);
    const [tplOptions, setTplOptions] = useState<string[]>([]);
    const [tloOptions, setTloOptions] = useState<ComboOption[]>([]);
    const [rows, setRows] = useState<InsuranceRow[]>([]);
    const [incomeSummary, setIncomeSummary] = useState<IncomeSummary | null>(null);

    const [calculating, setCalculating] = useState(false);
    const [calcError, setCalcError] = useState("");
    const [advancing, setAdvancing] = useState(false);
    const [nextErrors, setNextErrors] = useState<string[]>([]);

    const load = useCallback(async () => {
        setLoading(true);
        setLoadError("");
        try {
            const res = await api.get("/CAM/EditIndex/insurance", { params: { apless, applno: applNo, finType } });
            if (res.data.blocked) {
                setLoadError(res.data.message || "This application cannot be edited right now.");
                return;
            }
            const d = res.data;
            setInsPol(d.insPol || "");
            setInsCd(d.insCd || "");
            setPayMethod(d.payMethod || "");
            setPayMethodOptions(d.payMethodOptions || []);
            setModel(d.model || "");
            setCondition(d.condition || "");
            setConditionLabel(d.conditionLabel || "");
            setBpkbArea(d.bpkbArea || "");
            setInsuranceAreaOptions(d.insuranceAreaOptions || []);
            setInsuranceAreaDisabled(!!d.insuranceAreaDisabled);
            setTotalSeat(d.totalSeat || "");
            setGrossPrem(d.grossPrem || 0);
            setNetCom(d.netCom || 0);
            setCompanies(d.companies || []);
            setModels(d.models || []);
            setTplOptions(d.tplOptions || []);
            setTloOptions(d.tloOptions || []);
            setRows(d.rows || []);
            setIncomeSummary(d.incomeSummary || null);
        } catch {
            setLoadError("Failed to load Insurance. Please try again.");
        } finally {
            setLoading(false);
        }
    }, [apless, applNo, finType]);

    useEffect(() => {
        load();
    }, [load]);

    const refreshLookups = useCallback(
        async (overrides: { insCd?: string; model?: string; bpkbArea?: string; rowsOverride?: InsuranceRow[] } = {}) => {
            const effectiveInsCd = overrides.insCd ?? insCd;
            const effectiveModel = overrides.model ?? model;
            const effectiveBpkbArea = overrides.bpkbArea ?? bpkbArea;
            const effectiveRows = overrides.rowsOverride ?? rows;
            try {
                const res = await api.post("/CAM/EditIndex/insurance/lookups", {
                    applno: applNo,
                    apless,
                    insCd: effectiveInsCd,
                    model: effectiveModel,
                    bpkbArea: effectiveBpkbArea,
                    rows: effectiveRows.map(r => ({ year: r.year, tloAr: r.tloAr })),
                });
                setTplOptions(res.data.tplOptions || []);
                setTloOptions(res.data.tloOptions || []);
                const byYear: Record<number, { clauseCodes: Partial<Record<ClauseName, string>>; clauseDisabled: boolean }> = {};
                for (const r of res.data.rows || []) byYear[r.year] = { clauseCodes: r.clauseCodes || {}, clauseDisabled: !!r.clauseDisabled };
                setRows(prev =>
                    prev.map(r => {
                        const next = byYear[r.year];
                        if (!next) return r;
                        const clauseSelected: Partial<Record<ClauseName, boolean>> = {};
                        for (const name of CLAUSE_NAMES) {
                            if (r.clauseSelected[name] && next.clauseCodes[name]) clauseSelected[name] = true;
                        }
                        return { ...r, clauseCodes: next.clauseCodes, clauseDisabled: next.clauseDisabled, clauseSelected };
                    })
                );
            } catch {}
        },
        [apless, applNo, insCd, model, bpkbArea, rows]
    );

    const handleInsCdChange = (value: string) => {
        setInsCd(value);
        refreshLookups({ insCd: value });
    };
    const handleModelChange = (value: string) => {
        setModel(value);
        refreshLookups({ model: value });
    };
    const handleBpkbAreaChange = (value: string) => {
        setBpkbArea(value);
        refreshLookups({ bpkbArea: value });
    };
    const handleRowTloArChange = (year: number, value: string) => {
        setRows(prev => prev.map(r => (r.year === year ? { ...r, tloAr: value } : r)));
        const rowsOverride = rows.map(r => (r.year === year ? { ...r, tloAr: value } : r));
        refreshLookups({ rowsOverride });
    };

    const toggleClause = (year: number, name: ClauseName) => {
        setRows(prev =>
            prev.map(r => (r.year === year ? { ...r, clauseSelected: { ...r.clauseSelected, [name]: !r.clauseSelected[name] } } : r))
        );
    };

    const buildClauseSelectedCodes = (row: InsuranceRow) => {
        const out: Partial<Record<ClauseName, string>> = {};
        for (const name of CLAUSE_NAMES) {
            if (row.clauseSelected[name] && row.clauseCodes[name]) out[name] = row.clauseCodes[name];
        }
        return out;
    };

    const handleCalculate = async () => {
        setCalculating(true);
        setCalcError("");
        try {
            const res = await api.post("/CAM/EditIndex/insurance/calculate", {
                applno: applNo,
                apless,
                finType,
                insCd,
                model,
                bpkbArea,
                rows: rows.map(r => ({ year: r.year, insAmt: r.insAmt, tplAmt: r.tplAmt, tloAr: r.tloAr, clauseSelected: buildClauseSelectedCodes(r) })),
            });
            setGrossPrem(res.data.grossPrem || 0);
            setNetCom(res.data.netCom || 0);
            setIncomeSummary(res.data.incomeSummary || null);
            const byYear: Record<number, { prerAmt: number; prepAmt: number; savePremi: number; savePremicla: number }> = {};
            for (const r of res.data.rows || []) byYear[r.year] = r;
            setRows(prev => prev.map(r => (byYear[r.year] ? { ...r, ...byYear[r.year] } : r)));
        } catch (err: any) {
            setCalcError(err?.response?.data?.message || "Calculation failed. Please try again.");
        } finally {
            setCalculating(false);
        }
    };

    const handleClear = () => {
        setInsCd("");
        setTotalSeat("");
        setRows(prev =>
            prev.map(r => ({
                ...r,
                tplAmt: "",
                tloAr: "",
                prerAmt: 0,
                prepAmt: 0,
                savePremi: 0,
                savePremicla: 0,
                clauseSelected: {},
            }))
        );
        setCalcError("");
    };

    const handleNext = async () => {
        setAdvancing(true);
        setNextErrors([]);
        try {
            const res = await api.post("/CAM/EditIndex/insurance/next", {
                applno: applNo,
                apless,
                finType,
                insCd,
                payMethod,
                model,
                condition,
                bpkbArea,
                totalSeat,
                grossPrem,
                netCom,
                rows: rows.map(r => ({
                    year: r.year,
                    insAmt: r.insAmt,
                    tplAmt: r.tplAmt,
                    tloAr: r.tloAr,
                    prerAmt: r.prerAmt,
                    prepAmt: r.prepAmt,
                    savePremi: r.savePremi,
                    savePremicla: r.savePremicla,
                    clauseSelected: buildClauseSelectedCodes(r),
                })),
                eligibleComm: incomeSummary?.eligibleComm ?? 0,
                ttlSubTot: incomeSummary?.ttlSubTot ?? 0,
                maxComm: incomeSummary?.maxComm ?? 0,
            });
            if (res.data.success) {
                onSaved({ apless, applno: applNo });
            } else {
                setNextErrors(String(res.data.message || "Please try again.").split("<br>").filter(Boolean));
            }
        } catch (err: any) {
            setNextErrors([err?.response?.data?.message || "Save failed. Please try again."]);
        } finally {
            setAdvancing(false);
        }
    };

    if (loading) {
        return (
            <div className="rounded-2xl bg-white p-8 text-center shadow">
                <p className="text-sm text-slate-400">Loading…</p>
            </div>
        );
    }
    if (loadError) {
        return (
            <div className="rounded-2xl bg-white p-8 text-center shadow">
                <p className="text-sm text-red-600">{loadError}</p>
            </div>
        );
    }

    return (
        <div className="space-y-6 rounded-2xl bg-white p-6 shadow">
            <h2 className="text-base font-semibold text-slate-700">Insurance</h2>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Field label="Ins. Policy">
                    <input type="text" value={insPol} readOnly className={textInputCls + " bg-slate-50"} />
                </Field>
                <Field label="Pay Method *">
                    <Select value={payMethod} onChange={setPayMethod} options={payMethodOptions} />
                </Field>
                <Field label="Ins. Company *">
                    <Select value={insCd} onChange={handleInsCdChange} options={companies} />
                </Field>
                <Field label="Model *">
                    <Select value={model} onChange={handleModelChange} options={models} />
                </Field>
                <Field label="Insurance Area *">
                    <Select value={bpkbArea} onChange={handleBpkbAreaChange} options={insuranceAreaOptions} disabled={insuranceAreaDisabled} />
                </Field>
                <Field label="Condition *">
                    <input type="text" value={conditionLabel} readOnly className={textInputCls + " bg-slate-50"} />
                </Field>
                <Field label="Gross Premium">
                    <span className={readonlyBoxCls}>{fmt(grossPrem)}</span>
                </Field>
                <Field label="Seat">
                    <input
                        type="text"
                        inputMode="numeric"
                        maxLength={2}
                        value={totalSeat}
                        onChange={e => setTotalSeat(e.target.value.replace(/[^\d]/g, ""))}
                        className={textInputCls}
                    />
                </Field>
                <Field label="Net Premium">
                    <span className={readonlyBoxCls}>{fmt(netCom)}</span>
                </Field>
            </div>

            <div className="overflow-x-auto">
                <table className="w-full min-w-[900px] border-collapse text-sm">
                    <thead>
                        <tr className="border-b border-slate-200 text-left text-slate-500">
                            <th className="p-2">Year</th>
                            <th className="p-2">Insurance Amount</th>
                            <th className="p-2">TPL Amount</th>
                            <th className="p-2">TLO/CP</th>
                            <th className="p-2">Clause</th>
                            <th className="p-2">Premium Receive</th>
                            <th className="p-2">Premium Payment</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map(row => (
                            <tr key={row.year} className="border-b border-slate-100 align-top">
                                <td className="p-2">{row.year}</td>
                                <td className="p-2">
                                    <span className={readonlyBoxCls}>{fmt(row.insAmt)}</span>
                                </td>
                                <td className="p-2">
                                    <select
                                        className={selectCls}
                                        value={row.tplAmt}
                                        onChange={e => setRows(prev => prev.map(r => (r.year === row.year ? { ...r, tplAmt: e.target.value } : r)))}
                                    >
                                        <option value="">Select</option>
                                        {tplOptions.map(v => (
                                            <option key={v} value={v}>
                                                {v}
                                            </option>
                                        ))}
                                    </select>
                                </td>
                                <td className="p-2">
                                    <select className={selectCls} value={row.tloAr} onChange={e => handleRowTloArChange(row.year, e.target.value)}>
                                        <option value="">Select</option>
                                        {tloOptions.map(opt => (
                                            <option key={opt.value} value={opt.value}>
                                                {opt.label}
                                            </option>
                                        ))}
                                    </select>
                                </td>
                                <td className="p-2">
                                    <div className="flex flex-col gap-1">
                                        {CLAUSE_NAMES.filter(name => row.clauseCodes[name]).map(name => (
                                            <label key={name} className="flex items-center gap-1.5 text-xs text-slate-600">
                                                <input
                                                    type="checkbox"
                                                    checked={!!row.clauseSelected[name]}
                                                    disabled={row.clauseDisabled}
                                                    onChange={() => toggleClause(row.year, name)}
                                                />
                                                {name}
                                            </label>
                                        ))}
                                        {CLAUSE_NAMES.every(name => !row.clauseCodes[name]) && <span className="text-xs text-slate-400">—</span>}
                                    </div>
                                </td>
                                <td className="p-2">
                                    <span className={readonlyBoxCls}>{fmt(row.prerAmt)}</span>
                                </td>
                                <td className="p-2">
                                    <span className={readonlyBoxCls}>{fmt(row.prepAmt)}</span>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {calcError && <p className="text-sm text-red-600">{calcError}</p>}

            <div className="flex gap-3">
                <button
                    type="button"
                    onClick={handleCalculate}
                    disabled={calculating}
                    className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:opacity-50"
                >
                    {calculating ? "Calculating…" : "Calculate"}
                </button>
                <button
                    type="button"
                    onClick={handleClear}
                    className="rounded-lg bg-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-300"
                >
                    Clear
                </button>
            </div>

            {incomeSummary && (
                <div className="overflow-x-auto">
                    <table className="w-full min-w-[820px] border-collapse text-sm">
                        <thead>
                            <tr className="border-b border-slate-200 bg-slate-50 text-left text-slate-500">
                                <th className="p-2"></th>
                                <th className="p-2">Income</th>
                                <th className="p-2">Subsidy</th>
                                <th className="p-2">Total Income (Incl. Subsidy)</th>
                                <th className="p-2">Base Rate</th>
                                <th className="p-2">Max Refund</th>
                            </tr>
                        </thead>
                        <tbody>
                            <SummaryRow label="Insurance Income" income={incomeSummary.ttlIncome} maxRefund={incomeSummary.execInc} />
                            <SummaryRow label="Net Insurance Prem. Received" income={incomeSummary.ttlIncomeNet} subsidy={incomeSummary.subsidyTotal} />
                            <SummaryRow
                                label="Survey Fee 1"
                                income={incomeSummary.survInc}
                                subsidy={incomeSummary.subSurv}
                                total={incomeSummary.ttlSurv}
                                baseRate={incomeSummary.baseSurv}
                                maxRefund={incomeSummary.exceSurv}
                            />
                            <SummaryRow
                                label="Survey Fee 2"
                                income={incomeSummary.survInc2}
                                subsidy={incomeSummary.subSurv2}
                                total={incomeSummary.ttlSurv2}
                                baseRate={incomeSummary.baseSurv2}
                                maxRefund={incomeSummary.exceSurv2}
                            />
                            <SummaryRow
                                label="Provision Fee"
                                income={incomeSummary.provInc}
                                subsidy={incomeSummary.subProv}
                                total={incomeSummary.ttlProv}
                                maxRefund={incomeSummary.provExec}
                            />
                            <SummaryRow
                                label="Interest Income"
                                income={incomeSummary.interestIncome}
                                subsidy={incomeSummary.subInt}
                                total={incomeSummary.ttlInt}
                                baseRate={incomeSummary.baseInterest}
                                maxRefund={incomeSummary.excInt}
                            />
                            <tr className="border-t border-slate-300 font-semibold">
                                <td className="p-2">Total</td>
                                <td className="p-2"></td>
                                <td className="p-2 text-right">{fmt(incomeSummary.subsidyTotal)}</td>
                                <td className="p-2 text-right">{fmt(incomeSummary.ttlSubTot)}</td>
                                <td className="p-2"></td>
                                <td className="p-2 text-right">{fmt(incomeSummary.ttlExcTot)}</td>
                            </tr>
                            <tr>
                                <td className="p-2" colSpan={4}>
                                    Incentive to 3rd Party ({incomeSummary.percentage}%)
                                </td>
                                <td className="p-2"></td>
                                <td className="p-2 text-right font-semibold">{fmt(incomeSummary.maxComm)}</td>
                            </tr>
                            <tr>
                                <td className="p-2" colSpan={4}>
                                    Marketing Fee
                                </td>
                                <td className="p-2"></td>
                                <td className="p-2 text-right font-semibold">{fmt(incomeSummary.marketingFee)}</td>
                            </tr>
                            <tr>
                                <td className="p-2 font-semibold" colSpan={5}>
                                    Incentive To Be Paid
                                </td>
                                <td className="p-2 text-right font-semibold">{fmt(incomeSummary.eligibleComm)}</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            )}

            {nextErrors.length > 0 && (
                <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                    {nextErrors.map((e, i) => (
                        <p key={i}>{e}</p>
                    ))}
                </div>
            )}

            <div className="flex justify-end pt-2">
                <button
                    type="button"
                    onClick={handleNext}
                    disabled={advancing}
                    className="rounded-lg bg-orange-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-orange-600 disabled:opacity-50"
                >
                    {advancing ? "Please wait…" : "Next"}
                </button>
            </div>
        </div>
    );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
    return (
        <div className="space-y-1">
            <label className="block text-sm font-medium text-slate-600">{label}</label>
            {children}
        </div>
    );
}

function Select({
    value,
    onChange,
    options,
    disabled,
}: {
    value: string;
    onChange: (value: string) => void;
    options: ComboOption[];
    disabled?: boolean;
}) {
    return (
        <select className={selectCls} value={value || ""} disabled={disabled} onChange={e => onChange(e.target.value)}>
            <option value="">Select</option>
            {options.map(opt => (
                <option key={opt.value} value={opt.value}>
                    {opt.label}
                </option>
            ))}
        </select>
    );
}

function SummaryRow({
    label,
    income,
    subsidy,
    total,
    baseRate,
    maxRefund,
}: {
    label: string;
    income?: number;
    subsidy?: number;
    total?: number;
    baseRate?: number;
    maxRefund?: number;
}) {
    return (
        <tr className="border-b border-slate-100">
            <td className="p-2">{label}</td>
            <td className="p-2 text-right">{income !== undefined ? fmt(income) : ""}</td>
            <td className="p-2 text-right">{subsidy !== undefined ? fmt(subsidy) : ""}</td>
            <td className="p-2 text-right">{total !== undefined ? fmt(total) : ""}</td>
            <td className="p-2 text-right">{baseRate !== undefined ? fmt(baseRate) : ""}</td>
            <td className="p-2 text-right">{maxRefund !== undefined ? fmt(maxRefund) : ""}</td>
        </tr>
    );
}