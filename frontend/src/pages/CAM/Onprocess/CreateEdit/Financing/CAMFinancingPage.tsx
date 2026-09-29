import { useCallback, useEffect, useMemo, useState } from "react";
import api from "../../../../../api/axiosInstance";
import CAMFinancingSubsidyPanel from "./CAMFinancingSubsidyPanel";
import {
	CurrencyInput,
	Field,
	NumberInput,
	PercentInput,
	RadioPair,
	SelectInput,
} from "./FinancingFormControls";

export interface CAMFinancingPageProps {
	apless: string;
	applNo: string;
	finType: string;
	purpoffinc: string;
	contType: string;
	newCar: string;
	onSaved: (result: { apless: string; applno: string }) => void;
	onHome?: () => void;
}

interface FinancingData {
	apless: string;
	applno: string;
	blocked: boolean;
	blockMessage: string;
	npwp: string;
	contract: Record<string, any>;
	insurance: Record<string, any>;
	bbn: Record<string, any>;
	provisionLoan: number;
	cignaFee: Record<string, any>;
	subsidyDetails: Record<string, number>;
	subsidySourceTotals: { fromDealer: number; fromApm: number };
	subsidyGrid: any[];
	commissionPercentage: number;
	totalOutstandingBeforeThisContract: number;
	dpMinimum: { asOfDate: string | null; npfRatio: number | null; minDpInvestasi: number | null; minDpMultiguna: number | null };
	notaryLookup: { gross: number; nettNotary: number; nettFiduciary: number } | null;
	outstanding: { totalFDana: number; totalFModal: number; totFund: number };
	eligibility: { surveyFee2Disabled: boolean; guaranteedAcceptanceDisabled: boolean; reason: string };
	lookups: Record<string, any[]>;
}

const isFinanceLease = (finType: string) => finType === "S" || finType === "F";

function computeBbnFieldFlags(via?: string, paidBy?: string) {
	let occupationReadOnly = false;
	let bbnFeeReadOnly = false;
	let bbnLoanReadOnly = false;

	if (via === "MLCI" && paidBy === "Loan") {
		bbnLoanReadOnly = true;
	} else if (via === "MLCI" && paidBy === "Deduct from disbursement") {
		bbnLoanReadOnly = true;
	} else if (via === "Dealer" && paidBy === "Loan") {
		bbnFeeReadOnly = true;
		occupationReadOnly = true;
	} else if (via === "Dealer" && paidBy === "paid to Dealer") {
		bbnFeeReadOnly = true;
		occupationReadOnly = true;
		bbnLoanReadOnly = true;
	} else if (via === "MLCI" && paidBy === "Transfer") {
		bbnLoanReadOnly = true;
	}

	return {
		agencyNameDisabled: via !== "MLCI",
		occupationReadOnly,
		bbnFeeReadOnly,
		bbnLoanReadOnly,
	};
}

const PAID_BY_OPTIONS_BY_VIA: Record<string, [string, string][]> = {
	MLCI: [
		["Transfer", "Transfer"],
		["Deduct from disbursement", "Deduct from disbursement"],
		["Loan", "Loan"],
	],
	Dealer: [
		["Loan", "Loan"],
		["paid to Dealer", "Paid to Dealer"],
	],
};

const SUBSIDY_PANEL_ENABLED = false;

export default function CAMFinancingPage({
	apless,
	applNo,
	finType,
	purpoffinc,
	contType,
	newCar,
	onSaved,
	onHome,
}: CAMFinancingPageProps) {
	const [loading, setLoading] = useState(true);
	const [loadError, setLoadError] = useState("");
	const [data, setData] = useState<FinancingData | null>(null);
	const [form, setForm] = useState<Record<string, any>>({});
	const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
	const [calculating, setCalculating] = useState(false);
	const [saving, setSaving] = useState(false);
	const [showSubsidyPanel, setShowSubsidyPanel] = useState(false);

	const financeLease = isFinanceLease(finType);

	const isRestructuring = (contType || "").slice(0, 2) === "RS";
	const disbTypeEditable = contType === "NEW" ? ["S", "M", "D"].includes(finType) : !isRestructuring;
	const disbTypeForcedValue = contType === "NEW" && !["S", "M", "D"].includes(finType)
		? "N"
		: isRestructuring
			? "C"
			: null;

	const load = useCallback(async () => {
		setLoading(true);
		setLoadError("");
		try {
			const res = await api.get("/CAM/EditIndex/fin-financing", { params: { apless, applno: applNo } });
			setData(res.data);
			setForm({
				contSts: res.data.contract.contSts || "",
				currCode: res.data.contract.currCode || "IDR",
				colType: res.data.contract.colType || "",
				advArr: res.data.contract.advArr || (isFinanceLease(finType) ? "" : "V"),
				fixFloat: res.data.contract.fixFloat || "X",
				floatCyc: res.data.contract.floatCyc || "",
				tenor: res.data.contract.tenor || "",
				gPeriod: res.data.contract.gPeriod || 0,
				gIntRate: res.data.contract.gIntRate || 0,
				gIntAmt: res.data.contract.gIntAmt || 0,
				lAmount: res.data.contract.lAmount || "",
				security: res.data.contract.security || "",
				securityPersen: res.data.contract.lAmount
					? Math.round((res.data.contract.security * 100) / res.data.contract.lAmount * 100) / 100
					: "",
				creditAmt: res.data.insurance.creditAmt || "",
				commAdmFee: res.data.insurance.commAdmFee || "",
				otherLoan: res.data.contract.otherLoan || "",
				bbnLoan: res.data.bbn.bbnLoan || "",
				provisionLoan: res.data.provisionLoan || "",
				surveyLoan2: res.data.cignaFee.surveyLoanCigna || "",
				surveyFeeEnabled: !!res.data.cignaFee.surveyFeeCigna,
				survinc2: res.data.cignaFee.surveyFeeCigna || 0,
				creditProtection: res.data.cignaFee.creditProtection || 0,
				guaranteedAcceptance: res.data.cignaFee.guaranteedAcceptance,
				lType: res.data.contract.lType || "",
				flatRate: res.data.contract.flatRate || "",
				mlciFlat: res.data.contract.mlciFlat || "",
				declRate: res.data.contract.declRate || "",
				mlciDecl: res.data.contract.mlciDecl || "",
				rental: res.data.contract.rental || "",
				mlciRent: res.data.contract.mlciRent || "",
				notaryFeeGross: res.data.contract.notaryFeeGross || "",
				notary: res.data.contract.notary || "",
				fiduciary: res.data.contract.fiduciary || "",
				otherFee: res.data.contract.otherFee || "",
				businessTripFee: res.data.contract.businessTripFee || "",
				residual: res.data.contract.residual || "",
				adminFee: res.data.contract.adminFee || "",
				provision: res.data.contract.provision || "",
				commProvision: res.data.contract.commProvision || "",
				disbType: res.data.contract.disbType || "",
				crossNo: res.data.contract.crossNumbers?.[0] || "",
				bbn: { ...res.data.bbn },
				payCycle: res.data.contract.payCycle || 1,
				npwp: res.data.npwp || "",
				totalNetFinance: 0,
				totalNetFinancePlusSurveyLoan2: 0,
				loanToValue: 0,
			});
		} catch {
			setLoadError("Failed to load Financing data. Please try again.");
		} finally {
			setLoading(false);
		}
	}, [apless, applNo, finType]);

	useEffect(() => {
		load();
	}, [load]);

	useEffect(() => {
		if (disbTypeForcedValue && form.disbType !== disbTypeForcedValue) {
			setField("disbType", disbTypeForcedValue);
		}
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [disbTypeForcedValue, data]);

	const setField = (key: string, value: any) => setForm((prev) => ({ ...prev, [key]: value }));

	const handleSecurityAmountChange = (value: string) => {
		const amt = parseFloat(value.replace(/,/g, "")) || 0;
		const lAmt = parseFloat(String(form.lAmount).replace(/,/g, "")) || 0;
		setForm((prev) => ({
			...prev,
			security: amt,
			securityPersen: lAmt ? Math.round((amt / lAmt) * 100 * 100) / 100 : 0,
		}));
	};

	const handleSecurityPercentChange = (value: string) => {
		setField("securityPersen", value);
	};

	const handleSecurityPercentBlur = () => {
		const pct = parseFloat(String(form.securityPersen)) || 0;
		const lAmt = parseFloat(String(form.lAmount).replace(/,/g, "")) || 0;
		const minPct = purpoffinc === "3" ? data?.dpMinimum.minDpInvestasi : data?.dpMinimum.minDpMultiguna;
		if (minPct && pct < minPct) {
			setMessage({
				type: "error",
				text: `NPF as of ${data?.dpMinimum.asOfDate} is ${data?.dpMinimum.npfRatio}% -- minimum DP allowed is ${minPct}%`,
			});
			setField("securityPersen", "");
			return;
		}
		setForm((prev) => ({ ...prev, securityPersen: pct, security: Math.round((pct / 100) * lAmt) }));
	};

	const handleAdvArrChange = (newAdvArr: string) => {
		setForm((prev) => ({
			...prev,
			advArr: newAdvArr,
			flatRate: 0,
			mlciFlat: 0,
			declRate: 0,
			mlciDecl: 0,
			rental: prev.lType !== "3" ? 0 : prev.rental,
			mlciRent: prev.lType !== "3" ? 0 : prev.mlciRent,
			otherLoan: 0,
			security: 0,
			securityPersen: 0,
			creditAmt: 0,
			provisionLoan: 0,
		}));
	};

	const handleFlatRateBlur = () => {
		if (form.flatRate === "0" && form.lType === "0") {
			setMessage({ type: "error", text: "The Flat Rate cannot be 0" });
			setField("flatRate", "");
			return;
		}
		setForm((prev) => ({ ...prev, declRate: 0, rental: 0 }));
	};
	const handleMlciFlatBlur = () => {
		if (form.mlciFlat === "0" && form.lType !== "1") {
			setMessage({ type: "error", text: "The MLCI Flat Rate cannot be 0" });
			setField("mlciFlat", "");
			return;
		}
		setForm((prev) => ({ ...prev, mlciDecl: 0, mlciRent: 0 }));
	};
	const handleDeclRateBlur = () => {
		if (form.declRate === "0" && form.lType !== "1") {
			setMessage({ type: "error", text: "The effective Rate cannot be 0" });
			setField("declRate", "");
			return;
		}
		setForm((prev) => ({ ...prev, flatRate: 0, rental: 0 }));
	};
	const handleMlciDeclBlur = () => {
		if (form.mlciDecl === "0" && form.lType !== "1") {
			setMessage({ type: "error", text: "The MLCI effective Rate cannot be 0" });
			setField("mlciDecl", "");
			return;
		}
		setForm((prev) => ({ ...prev, mlciFlat: 0, mlciRent: 0 }));
	};
	const handleRentalBlur = () => setForm((prev) => ({ ...prev, declRate: 0, flatRate: 0 }));
	const handleMlciRentBlur = () => setForm((prev) => ({ ...prev, mlciDecl: 0, mlciFlat: 0 }));

	const handleBbnViaChange = (newVia: string) => {
		setForm((prev) => ({
			...prev,
			bbn: { ...prev.bbn, via: newVia, paidBy: "", bbnFee: 0, agencyFeeGross: 0, bbnLoan: 0 },
		}));
	};

	const handleBbnPaidByChange = (newPaidBy: string) => {
		setForm((prev) => {
			const via = prev.bbn?.via;
			const bbnFeeCurrent = parseFloat(String(prev.bbn?.bbnFee).replace(/,/g, "")) || 0;
			const agencyFeeGrossCurrent = parseFloat(String(prev.bbn?.agencyFeeGross).replace(/,/g, "")) || 0;
			let bbn = { ...prev.bbn, paidBy: newPaidBy };

			if (via === "MLCI" && newPaidBy === "Loan") {
				bbn.bbnLoan = agencyFeeGrossCurrent + bbnFeeCurrent;
			} else if (via === "MLCI" && newPaidBy === "Deduct from disbursement") {
				bbn = { ...bbn, bbnFee: 0, agencyName: "", agencyFeeNet: 0, agencyFeeGross: 0, bbnLoan: 0 };
			} else if (via === "Dealer" && (newPaidBy === "Loan" || newPaidBy === "paid to Dealer")) {
				bbn = { ...bbn, bbnFee: 0, agencyFeeGross: 0, bbnLoan: 0, agencyName: "", agencyFeeNet: 0 };
			} else if (via === "MLCI" && newPaidBy === "Transfer") {
				bbn = { ...bbn, agencyFeeGross: 0, bbnFee: 0, bbnLoan: 0, agencyName: "", agencyFeeNet: 0 };
			} else {
				bbn = { ...bbn, agencyFeeGross: 0, bbnFee: 0, bbnLoan: 0, agencyName: "", agencyFeeNet: 0 };
			}
			return { ...prev, bbn };
		});
	};

	const handleAgencyNameChange = async (agent: string) => {
		setForm((prev) => ({ ...prev, bbn: { ...prev.bbn, agencyName: agent } }));
		if (!agent) return;
		try {
			const res = await api.get("/CAM/EditIndex/fin-financing/agency-fee", { params: { agent } });
			const fee = res.data.fee || 0;
			setForm((prev) => {
				const via = prev.bbn?.via;
				const paidBy = prev.bbn?.paidBy;
				const bbn = { ...prev.bbn, agencyName: agent, agencyFeeGross: fee, agencyFeeNet: fee };
				const isTransferOrDeduct = via === "MLCI" && (paidBy === "Transfer" || paidBy === "Deduct from disbursement");
				if (!isTransferOrDeduct) {
					const bbnFeeCurrent = parseFloat(String(prev.bbn?.bbnFee).replace(/,/g, "")) || 0;
					bbn.bbnLoan = fee + bbnFeeCurrent;
				}
				return { ...prev, bbn };
			});
		} catch {}
	};

	const netFinance = useMemo(() => {
		const lAmt = parseFloat(String(form.lAmount).replace(/,/g, "")) || 0;
		const sec = parseFloat(String(form.security).replace(/,/g, "")) || 0;
		return lAmt - sec;
	}, [form.lAmount, form.security]);

	const totalNetFinance = useMemo(() => {
		const other = parseFloat(String(form.otherLoan).replace(/,/g, "")) || 0;
		const bbn = financeLease && newCar === "1" ? parseFloat(String(form.bbnLoan).replace(/,/g, "")) || 0 : 0;
		const prov = parseFloat(String(form.provisionLoan).replace(/,/g, "")) || 0;
		const credit = parseFloat(String(form.creditAmt).replace(/,/g, "")) || 0;
		return netFinance + other + bbn + prov + credit;
	}, [netFinance, form.otherLoan, form.bbnLoan, form.provisionLoan, form.creditAmt, financeLease, newCar]);

	const totalNetFinancePlusSurvey2 = useMemo(() => {
		const surveyLoan2 = parseFloat(String(form.surveyLoan2).replace(/,/g, "")) || 0;
		return totalNetFinance + surveyLoan2;
	}, [totalNetFinance, form.surveyLoan2]);

	const handleCalculate = async () => {
		setCalculating(true);
		setMessage(null);
		try {
			const res = await api.post("/CAM/EditIndex/fin-financing/calculate", {
				apless,
				applno: applNo,
				finType,
				lType: form.lType,
				tenor: form.tenor,
				payCycle: form.payCycle,
				advArr: form.advArr,
				gPeriod: form.gPeriod,
				currCode: form.currCode,
				lAmount: form.lAmount,
				security: form.security,
				creditAmt: form.creditAmt,
				otherLoan: form.otherLoan,
				bbnLoan: financeLease && newCar === "1" ? form.bbnLoan : 0,
				provLoan: form.provisionLoan,
				surveyLoan2: form.surveyLoan2,
				flatRate: form.flatRate,
				mlciFlat: form.mlciFlat,
				declRate: form.declRate,
				mlciDecl: form.mlciDecl,
				rental: form.rental,
				mlciRent: form.mlciRent,
				residual: form.residual,
				mlciTax: 0,
			});
			setForm((prev) => ({
				...prev,
				rental: res.data.rental ?? prev.rental,
				mlciRent: res.data.mlciRent ?? prev.mlciRent,
				flatRate: res.data.flatRate ?? prev.flatRate,
				mlciFlat: res.data.mlciFlat ?? prev.mlciFlat,
				declRate: res.data.declRate ?? prev.declRate,
				mlciDecl: res.data.mlciDecl ?? prev.mlciDecl,
				totalNetFinance: res.data.totalNetFinance,
				totalNetFinancePlusSurveyLoan2: res.data.totalNetFinancePlusSurveyLoan2,
				loanToValue: res.data.loanToValue,
			}));
			setMessage({ type: "success", text: "Calculated." });
		} catch (err: any) {
			const apiMessage = err?.response?.data?.error || "Calculation failed.";
			setMessage({ type: "error", text: apiMessage });
			if (err?.response?.data?.shouldClear) {
				await handleClear(true);
			}
		} finally {
			setCalculating(false);
		}
	};

	const handleClear = async (silent = false) => {
		try {
			await api.post("/CAM/EditIndex/fin-financing/clear", { applno: applNo, finType });
			await load();
			if (!silent) setMessage({ type: "success", text: "Cleared." });
		} catch {
			setMessage({ type: "error", text: "Failed to clear." });
		}
	};

	const handleSave = async () => {
		setSaving(true);
		setMessage(null);
		try {
			const res = await api.post("/CAM/EditIndex/fin-financing/save", {
				apless,
				applno: applNo,
				finType,
				purpoffinc,
				contType,
				...form,
				bbn: form.bbn,
			});
			if (res.data.success) {
				onSaved({ apless: res.data.apless, applno: res.data.applno });
			} else {
				setMessage({ type: "error", text: res.data.message || "Save failed." });
			}
		} catch (err: any) {
			setMessage({ type: "error", text: err?.response?.data?.message || err?.response?.data?.error || "Save failed." });
		} finally {
			setSaving(false);
		}
	};

	if (loading) {
		return (
			<div className="rounded-2xl bg-white p-8 text-center shadow">
				<p className="text-sm text-slate-400">Loading…</p>
			</div>
		);
	}
	if (loadError || !data) {
		return (
			<div className="rounded-2xl bg-white p-8 text-center shadow">
				<p className="text-sm text-red-600">{loadError || "No data."}</p>
			</div>
		);
	}
	if (data.blocked) {
		return (
			<div className="rounded-2xl bg-white p-8 text-center shadow">
				<p className="text-sm text-red-600">{data.blockMessage}</p>
			</div>
		);
	}

	const showStepRentalWarning = form.lType === "3" || form.lType === "4";
	const bbnFlags = computeBbnFieldFlags(form.bbn?.via, form.bbn?.paidBy);
	const paidByOptions = PAID_BY_OPTIONS_BY_VIA[form.bbn?.via] || [];

	return (
		<div className="space-y-4">
			<div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
				<div className="space-y-4 rounded-2xl bg-white p-6 shadow">
					<h2 className="text-base font-semibold text-slate-700">Financing</h2>

					<Field label="Status *">
						<SelectInput value={form.contSts} onChange={(v) => setField("contSts", v)} placeholder="Select">
							{data.lookups.contractStatuses.map((s: any) => (
								<option key={s.value} value={s.value}>{s.label}</option>
							))}
						</SelectInput>
					</Field>

					<Field label="Contract Type *">
						<input value={data.contract.contTypeName} readOnly className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500" />
					</Field>

					<Field label="Disbursement Type *">
						<SelectInput
							value={form.disbType}
							onChange={(v) => setField("disbType", v)}
							disabled={!disbTypeEditable}
							placeholder="Select"
						>
							{data.lookups.disbursementTypes.map((d: any) => (
								<option key={d.value} value={d.value}>{d.label}</option>
							))}
						</SelectInput>
						{!disbTypeEditable && (
							<p className="mt-1 text-xs text-slate-500">
								{disbTypeForcedValue === "N" ? "Fixed to NEW DISBURSEMENT for this contract." : "Fixed to CROSS DISBURSEMENT for this restructuring contract."}
							</p>
						)}
					</Field>

					{form.disbType === "C" && (
						<Field label="Cross No">
							<NumberInput value={form.crossNo} onChange={(v) => setField("crossNo", v)} />
						</Field>
					)}

					<Field label="Purpose of Finance *">
						<input value={data.contract.purpoffincDesc} readOnly className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500" />
					</Field>

					<Field label="Currency *">
						<SelectInput value={form.currCode} onChange={(v) => setField("currCode", v)}>
							{data.lookups.currencies.map((c: any) => (
								<option key={c.value} value={c.value}>{c.label}</option>
							))}
						</SelectInput>
					</Field>

					<Field label="Payment Method *">
						<SelectInput value={form.colType} onChange={(v) => setField("colType", v)} placeholder="Select">
							{data.lookups.paymentMethods.map((c: any) => (
								<option key={c.value} value={c.value}>{c.label}</option>
							))}
						</SelectInput>
					</Field>

					{financeLease && (
						<Field label="In Adv / In Arr *">
							<RadioPair
								name="advArr"
								value={form.advArr}
								options={[["V", "Adv"], ["R", "Arr"]]}
								onChange={handleAdvArrChange}
							/>
						</Field>
					)}

					<Field label="Fix / Float *">
						<RadioPair
							name="fixFloat"
							value={form.fixFloat}
							options={[["X", "Fix"], ["L", "Float"]]}
							onChange={(v) => setField("fixFloat", v)}
						/>
					</Field>

					{form.fixFloat === "L" && (
						<Field label="Float Cycle *">
							<NumberInput value={form.floatCyc} onChange={(v) => setField("floatCyc", v)} suffix="Month" />
						</Field>
					)}

					<Field label="Tenor *">
						<NumberInput value={form.tenor} onChange={(v) => setField("tenor", v)} suffix="Month" />
					</Field>

					<Field label="Payment Cycle *">
						<NumberInput value={form.payCycle} onChange={(v) => setField("payCycle", v)} suffix="Month" />
					</Field>

					<Field label="Grace Period">
						<NumberInput value={form.gPeriod} onChange={(v) => setField("gPeriod", v)} suffix="Month" />
					</Field>

					<Field label="Grace Int. Rate">
						<NumberInput value={form.gIntRate} readOnly suffix="%" />
					</Field>

					<Field label="Grace Int. Amount">
						<CurrencyInput value={form.gIntAmt} readOnly />
					</Field>

					{financeLease && (
						<Field label="Survey Fee 2 *">
							<RadioPair
								name="surveyFeeEnabled"
								value={form.surveyFeeEnabled ? "1" : "0"}
								options={[["1", "Yes"], ["0", "No"]]}
								disabled={data.eligibility.surveyFee2Disabled}
								onChange={(v) => setField("surveyFeeEnabled", v === "1")}
							/>
							{data.eligibility.surveyFee2Disabled && (
								<p className="mt-1 text-xs text-amber-600">{data.eligibility.reason}</p>
							)}
						</Field>
					)}

					<Field label="Asset Value *">
						<CurrencyInput value={form.lAmount} onChange={(v) => setField("lAmount", v)} />
					</Field>

					<Field label={financeLease ? "Security Deposit *" : "Down Payment *"}>
						<div className="flex gap-2">
							<CurrencyInput value={form.security} onChange={handleSecurityAmountChange} className="flex-1" />
							<PercentInput
								value={form.securityPersen}
								onChange={handleSecurityPercentChange}
								onBlur={handleSecurityPercentBlur}
								capDecimals={3}
								className="w-28"
							/>
						</div>
						{(data.dpMinimum.minDpInvestasi || data.dpMinimum.minDpMultiguna) && (
							<p className="mt-1 text-xs text-slate-500">
								NPF as of {data.dpMinimum.asOfDate} is {data.dpMinimum.npfRatio}% — minimum DP{" "}
								{purpoffinc === "3" ? data.dpMinimum.minDpInvestasi : data.dpMinimum.minDpMultiguna}%
							</p>
						)}
					</Field>

					<Field label="Net Finance *">
						<CurrencyInput value={netFinance} readOnly />
					</Field>

					{financeLease && newCar === "1" && (
						<Field label="BBN Loan *">
							<CurrencyInput
								value={form.bbnLoan}
								onChange={(v) => setField("bbnLoan", v)}
								readOnly={bbnFlags.bbnLoanReadOnly}
							/>
						</Field>
					)}

					<Field label="Provision Loan">
						<CurrencyInput value={form.provisionLoan} onChange={(v) => setField("provisionLoan", v)} />
					</Field>

					<Field label="Insurance Loan">
						<CurrencyInput value={form.creditAmt} onChange={(v) => setField("creditAmt", v)} />
					</Field>

					<Field label="Other Loan">
						<CurrencyInput value={form.otherLoan} onChange={(v) => setField("otherLoan", v)} />
					</Field>

					<Field label="Total Net Finance">
						<CurrencyInput value={totalNetFinance} readOnly />
					</Field>

					<Field label="Survey Loan 2">
						<CurrencyInput value={form.surveyLoan2} onChange={(v) => setField("surveyLoan2", v)} />
					</Field>

					<Field label="Total Net Finance + Survey Loan 2">
						<CurrencyInput value={totalNetFinancePlusSurvey2} readOnly />
					</Field>

					<Field label="Loan to Value (LtV)">
						<NumberInput value={form.loanToValue} readOnly suffix="%" />
					</Field>

					<Field label="Amortization Type *">
						<SelectInput value={form.lType} onChange={(v) => setField("lType", v)} placeholder="Select">
							{data.lookups.amortizationTypes.map((a: any) => (
								<option key={a.value} value={a.value}>{a.label}</option>
							))}
						</SelectInput>
					</Field>

					{showStepRentalWarning && (
						<div className="rounded-lg bg-amber-50 p-3 text-xs text-amber-700">
							Step Rental / Step 1000 amortization's rate-conversion
							formulas are ported in <code>financial_formulas.py</code>, but
							the <code>/fin-financing/calculate</code> endpoint doesn't wire
							them into these amortization types yet -- Calculate will return
							an explicit error until that's done.
						</div>
					)}

					{(form.lType === "0" || form.lType === "1" || form.lType === "2" || form.lType === "6") && (
						<>
							<Field label="Flat Rate *">
								<div className="flex gap-2">
									<PercentInput value={form.flatRate} onChange={(v) => setField("flatRate", v)} onBlur={handleFlatRateBlur} label="Selling" />
									<PercentInput value={form.mlciFlat} onChange={(v) => setField("mlciFlat", v)} onBlur={handleMlciFlatBlur} label="Base" />
								</div>
							</Field>
							<Field label="Effective Rate *">
								<div className="flex gap-2">
									<PercentInput value={form.declRate} onChange={(v) => setField("declRate", v)} onBlur={handleDeclRateBlur} label="Selling" />
									<PercentInput value={form.mlciDecl} onChange={(v) => setField("mlciDecl", v)} onBlur={handleMlciDeclBlur} label="Base" />
								</div>
							</Field>
							<Field label="Installment *">
								<div className="flex gap-2">
									<CurrencyInput value={form.rental} onChange={(v) => setField("rental", v)} onBlur={handleRentalBlur} className="flex-1" />
									<CurrencyInput value={form.mlciRent} onChange={(v) => setField("mlciRent", v)} onBlur={handleMlciRentBlur} className="flex-1" />
								</div>
							</Field>
						</>
					)}
				</div>

				<div className="space-y-4">
					<div className="space-y-4 rounded-2xl bg-white p-6 shadow">
						<h2 className="text-base font-semibold text-slate-700">Fees</h2>
						<Field label="Notary Fee Gross *">
							<CurrencyInput value={form.notaryFeeGross} onChange={(v) => setField("notaryFeeGross", v)} />
						</Field>
						<Field label="Nett Deed Fee *">
							<CurrencyInput value={form.notary} onChange={(v) => setField("notary", v)} />
						</Field>
						<Field label="Nett Certificate Fee *">
							<CurrencyInput value={form.fiduciary} onChange={(v) => setField("fiduciary", v)} />
						</Field>
						<Field label="Business Trip Fee">
							<CurrencyInput value={form.businessTripFee} onChange={(v) => setField("businessTripFee", v)} />
						</Field>
						<Field label="Other Fee">
							<CurrencyInput value={form.otherFee} onChange={(v) => setField("otherFee", v)} />
						</Field>
						{financeLease && (
							<Field label="Residual Value">
								<CurrencyInput value={form.residual} readOnly />
							</Field>
						)}
					</div>

					{financeLease && newCar === "1" && (
						<div className="space-y-4 rounded-2xl bg-white p-6 shadow">
							<h2 className="text-base font-semibold text-slate-700">BBN</h2>
							<Field label="BBN Via">
								<RadioPair
									name="bbnVia"
									value={form.bbn?.via}
									options={[["MLCI", "Company"], ["Dealer", "Dealer"]]}
									onChange={handleBbnViaChange}
								/>
							</Field>
							<Field label="Paid By">
								<SelectInput
									value={form.bbn?.paidBy || ""}
									onChange={handleBbnPaidByChange}
									disabled={!form.bbn?.via}
									placeholder="Select"
								>
									{paidByOptions.map(([val, label]) => (
										<option key={val} value={val}>{label}</option>
									))}
								</SelectInput>
							</Field>
							<Field label="Agency Name">
								<SelectInput
									value={form.bbn?.agencyName || ""}
									onChange={handleAgencyNameChange}
									disabled={bbnFlags.agencyNameDisabled}
									placeholder="Select"
								>
									{data.lookups.agencyNames.map((n: string) => (
										<option key={n} value={n}>{n}</option>
									))}
								</SelectInput>
							</Field>
							<Field label="Agency Fee Gross">
								<CurrencyInput
									value={form.bbn?.agencyFeeGross}
									onChange={(v) => setField("bbn", { ...form.bbn, agencyFeeGross: v })}
									readOnly={bbnFlags.occupationReadOnly}
								/>
							</Field>
							<Field label="Agency Fee Net">
								<CurrencyInput value={form.bbn?.agencyFeeNet} readOnly />
							</Field>
							<Field label="BBN Fee">
								<CurrencyInput
									value={form.bbn?.bbnFee}
									onChange={(v) => setField("bbn", { ...form.bbn, bbnFee: v })}
									readOnly={bbnFlags.bbnFeeReadOnly}
								/>
							</Field>
						</div>
					)}

					{financeLease && (
						<div className="space-y-4 rounded-2xl bg-white p-6 shadow">
							<h2 className="text-base font-semibold text-slate-700">Cigna / Guaranteed Acceptance</h2>
							<Field label="Credit Protection">
								<CurrencyInput value={form.creditProtection} readOnly />
							</Field>
							<Field label="Guaranteed Acceptance">
								<RadioPair
									name="guaranteedAcceptance"
									value={form.guaranteedAcceptance ? "1" : "0"}
									options={[["1", "Yes"], ["0", "No"]]}
									disabled={data.eligibility.guaranteedAcceptanceDisabled}
									onChange={(v) => setField("guaranteedAcceptance", v === "1")}
								/>
							</Field>
						</div>
					)}

					{(finType === "D" || finType === "M") && (
						<div className="space-y-2 rounded-2xl bg-white p-6 shadow">
							<h2 className="text-base font-semibold text-slate-700">
								{finType === "D" ? "Fund Facility (FF)" : "Business Capital Facility (FMU)"} Exposure
							</h2>
							<Field label={`Existing Outstanding (${finType === "D" ? "FF" : "FMU"})`}>
								<CurrencyInput value={finType === "D" ? data.outstanding.totalFDana : data.outstanding.totalFModal} readOnly />
							</Field>
							<Field label="Grand Total (existing + this contract)">
								<CurrencyInput
									value={(finType === "D" ? data.outstanding.totalFDana : data.outstanding.totalFModal) + totalNetFinancePlusSurvey2}
									readOnly
								/>
							</Field>
							<p className="text-xs text-slate-500">
								Limit: Rp {finType === "D" ? "500,000,000" : "10,000,000,000"}. Enforced authoritatively on
								Calculate/Next.
							</p>
						</div>
					)}

					{SUBSIDY_PANEL_ENABLED && (
						<div className="rounded-2xl bg-white p-6 shadow">
							<div className="flex items-center justify-between">
								<h2 className="text-base font-semibold text-slate-700">Subsidy / Refund / Incentive</h2>
								<button
									type="button"
									onClick={() => setShowSubsidyPanel(true)}
									className="rounded-lg bg-slate-700 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-slate-800"
								>
									Manage
								</button>
							</div>
							<dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
								<dt className="text-slate-500">From Dealer</dt>
								<dd className="text-right font-medium">{data.subsidySourceTotals.fromDealer.toLocaleString()}</dd>
								<dt className="text-slate-500">From APM / Incentive</dt>
								<dd className="text-right font-medium">{data.subsidySourceTotals.fromApm.toLocaleString()}</dd>
							</dl>
						</div>
					)}
				</div>
			</div>

			{message && (
				<p className={`text-sm ${message.type === "success" ? "text-green-600" : "text-red-600"}`}>{message.text}</p>
			)}

			<div className="flex items-center justify-end gap-3 rounded-2xl bg-white p-4 shadow">
				<button
					type="button"
					onClick={() => handleClear(false)}
					className="rounded-lg bg-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-300"
				>
					Clear
				</button>
				<button
					type="button"
					onClick={handleCalculate}
					disabled={calculating}
					className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-green-700 disabled:opacity-50"
				>
					{calculating ? "Calculating…" : "Calculate"}
				</button>
				<button
					type="button"
					onClick={handleSave}
					disabled={saving}
					className="rounded-lg bg-orange-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-orange-600 disabled:opacity-50"
				>
					{saving ? "Please wait…" : "Next"}
				</button>
			</div>

			{SUBSIDY_PANEL_ENABLED && showSubsidyPanel && (
				<CAMFinancingSubsidyPanel
					applNo={applNo}
					includeSurveyFee2Option={form.surveyFeeEnabled}
					onClose={() => setShowSubsidyPanel(false)}
					onChanged={() => load()}
				/>
			)}
		</div>
	);
}