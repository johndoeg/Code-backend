import { useCallback, useEffect, useMemo, useState } from "react";
import api from "../../../../../api/axiosInstance";

export interface CAMFinancingDisbursementPageProps {
	apless: string;
	applNo: string;
	finType: string;
	contType: string;
	onSaved: (result: { apless: string; applno: string }) => void;
}

interface ComboOption {
	value: string;
	label: string;
}

type CategoryKey = "dealer" | "karoseri" | "accessories" | "others";
const CATEGORY_LABELS: Record<CategoryKey, string> = {
	dealer: "Dealer",
	karoseri: "Karoseri",
	accessories: "Accessories",
	others: "Others",
};
const CATEGORY_ORDER: CategoryKey[] = ["dealer", "karoseri", "accessories", "others"];
const DEALER_ONLY_FIELDS = new Set(["notaryFeeGross", "businessTripFee", "agencyFeeGross", "bbnFee", "commissionToDealer"]);

interface CategoryFields {
	assetValue: number;
	dp: number;
	surveyFeeGross1: number;
	surveyFeeGross2: number;
	notaryFeeGross: number;
	provisionFee: number;
	businessTripFee: number;
	insurance: number;
	firstInstallment: number;
	advanceGraceMonths: number;
	advanceGraceAmount: number;
	agencyFeeGross: number;
	bbnFee: number;
	netFinance: number;
	commissionToDealer: number;
	totalPayment: number;
	othersFieldLabel?: string;
}

interface AccountRow {
	id?: number;
	split: string;
	bank: string;
	bankLabel?: string;
	bankBranch: string;
	accName: string;
	accNo: string;
	amount: number;
}

interface CrossAccountRow {
	id?: number;
	crossNo: string;
	amount: number;
	purpose: string;
	purposeLabel?: string;
}

const COL_WIDTH = "w-40";
const inputCls = `${COL_WIDTH} rounded border border-slate-300 bg-white px-2 py-1 text-right text-sm text-slate-700`;
const readonlyInputCls = `${COL_WIDTH} rounded border border-slate-200 bg-slate-100 px-2 py-1 text-right text-sm text-slate-600`;
const labelCls = "text-sm text-slate-700";
const sectionHeadingCls = "text-sm font-semibold text-slate-800";
const selectCls = "rounded border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-700";
const textInputCls = "rounded border border-slate-300 px-2 py-1 text-sm";
const roundIconBtnCls = "flex h-6 w-6 items-center justify-center rounded-full text-white text-sm font-bold leading-none";

function fmt(value: number | undefined | null) {
	if (value === undefined || value === null || Number.isNaN(value)) return "0";
	const n = Math.round(value);
	const sign = n < 0 ? "-" : "";
	return sign + Math.abs(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function parseNum(raw: string) {
	const digits = raw.replace(/[^\d-]/g, "");
	return digits === "" || digits === "-" ? 0 : parseInt(digits, 10);
}

function NumberInput({ value, onChange, readOnly, className }: { value: number; onChange?: (v: number) => void; readOnly?: boolean; className: string }) {
	return (
		<input
			type="text"
			inputMode="numeric"
			className={className}
			value={fmt(value)}
			readOnly={readOnly}
			onChange={e => onChange?.(parseNum(e.target.value))}
		/>
	);
}

function computeNetFinance(f: CategoryFields, isDealer: boolean, refundToDealer: number, subsidyFromDealer: number) {
	const base =
		f.assetValue - f.dp - f.surveyFeeGross1 - f.provisionFee - f.insurance - f.firstInstallment -
		f.agencyFeeGross - f.bbnFee + refundToDealer - subsidyFromDealer - f.surveyFeeGross2;
	if (isDealer) {
		return base - f.advanceGraceAmount - f.notaryFeeGross - f.businessTripFee;
	}
	return base;
}

export default function CAMFinancingDisbursementPage({ apless, applNo, finType, contType, onSaved }: CAMFinancingDisbursementPageProps) {
	const [loading, setLoading] = useState(true);
	const [loadError, setLoadError] = useState("");
	const [locked, setLocked] = useState(false);
	const [lockMessage, setLockMessage] = useState("");
	const [ketDpSecurity, setKetDpSecurity] = useState("Down Payment");
	const [categories, setCategories] = useState<Partial<Record<CategoryKey, CategoryFields>>>({});
	const [refundToDealer, setRefundToDealer] = useState(0);
	const [subsidyFromDealer, setSubsidyFromDealer] = useState(0);
	const [readonlyFirstInstallment, setReadonlyFirstInstallment] = useState(false);
	const [gracePeriodMaxMonths, setGracePeriodMaxMonths] = useState(0);
	const [gracePeriodAmountPerMonth, setGracePeriodAmountPerMonth] = useState(0);
	const [splitView, setSplitView] = useState(false);

	const [externalAccounts, setExternalAccounts] = useState<AccountRow[]>([]);
	const [internalAccounts, setInternalAccounts] = useState<CrossAccountRow[]>([]);
	const [disbursementTypeOptions, setDisbursementTypeOptions] = useState<ComboOption[]>([]);
	const [disbursementTypeSelected, setDisbursementTypeSelected] = useState("");
	const [bankOptions, setBankOptions] = useState<ComboOption[]>([]);
	const [purposeOptions, setPurposeOptions] = useState<ComboOption[]>([]);
	const [disbursessToOptions, setDisbursessToOptions] = useState<ComboOption[]>([]);
	const [selectedDisbursementCategory, setSelectedDisbursementCategory] = useState("Dealer");

	const [calculating, setCalculating] = useState(false);
	const [resetting, setResetting] = useState(false);
	const [calcMessage, setCalcMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
	const [savingAccounts, setSavingAccounts] = useState(false);
	const [savingCross, setSavingCross] = useState(false);
	const [advancing, setAdvancing] = useState(false);
	const [nextError, setNextError] = useState("");

	const load = useCallback(async () => {
		setLoading(true);
		setLoadError("");
		try {
			const res = await api.get("/CAM/EditIndex/disbursement", { params: { apless, applno: applNo, finType, contType } });
			if (res.data.blocked) {
				setLoadError(res.data.message || "This application cannot be edited right now.");
				return;
			}
			const d = res.data;
			setLocked(!!d.locked);
			setLockMessage(d.lockMessage || "");
			setKetDpSecurity(d.ketDpSecurity || "Down Payment");
			setCategories(d.categories || {});
			setRefundToDealer(d.refundToDealer || 0);
			setSubsidyFromDealer(d.subsidyFromDealer || 0);
			setReadonlyFirstInstallment(!!d.readonlyFirstInstallment);
			setGracePeriodMaxMonths(d.gracePeriodMaxMonths || 0);
			setGracePeriodAmountPerMonth(d.gracePeriodAmountPerMonth || 0);
			const flatExternal: AccountRow[] = [];
			Object.entries(d.externalAccounts || {}).forEach(([split, rows]: [string, any]) => {
				(rows || []).forEach((r: any) => flatExternal.push({ ...r, split }));
			});
			setExternalAccounts(flatExternal);
			setInternalAccounts(d.internalAccounts || []);
			setDisbursementTypeOptions(d.disbursementTypeOptions || []);
			setDisbursementTypeSelected(d.disbursementTypeOptions?.length === 1 ? d.disbursementTypeOptions[0].value : "");
			setBankOptions(d.bankOptions || []);
			setPurposeOptions(d.purposeOptions || []);
			setDisbursessToOptions(d.disbursessToOptions || []);
			if (d.disbursessToOptions?.length) setSelectedDisbursementCategory(d.disbursessToOptions[0].value);
		} catch {
			setLoadError("Failed to load Disbursement. Please try again.");
		} finally {
			setLoading(false);
		}
	}, [apless, applNo, finType, contType]);

	useEffect(() => {
		load();
	}, [load]);

	const updateCategory = (key: CategoryKey, patch: Partial<CategoryFields>) =>
		setCategories(prev => (prev[key] ? { ...prev, [key]: { ...prev[key]!, ...patch } } : prev));

	const liveCategories = useMemo(() => {
		const out: Partial<Record<CategoryKey, CategoryFields>> = {};
		for (const key of CATEGORY_ORDER) {
			const c = categories[key];
			if (!c) continue;
			const netFinance = computeNetFinance(c, key === "dealer", refundToDealer, subsidyFromDealer);
			const commissionToDealer = key === "dealer" ? c.commissionToDealer : 0;
			out[key] = { ...c, netFinance, totalPayment: netFinance + commissionToDealer };
		}
		return out;
	}, [categories, refundToDealer, subsidyFromDealer]);

	const visibleKeys = splitView ? CATEGORY_ORDER : (["dealer"] as CategoryKey[]);
	const showTotalColumn = splitView;

	const totals = useMemo(() => {
		const sum = (fn: (c: CategoryFields) => number) =>
			visibleKeys.reduce((acc, key) => acc + (liveCategories[key] ? fn(liveCategories[key]!) : 0), 0);
		return {
			netFinance: sum(c => c.netFinance), totalPayment: sum(c => c.totalPayment), commissionToDealer: sum(c => c.commissionToDealer),
		};
	}, [liveCategories, visibleKeys]);

	const handleAdvanceGraceMonthsChange = (months: number) => {
		if (months > gracePeriodMaxMonths) {
			setCalcMessage({ type: "error", text: `Maximum advance grace period is ${gracePeriodMaxMonths} months` });
			return;
		}
		const amount = gracePeriodAmountPerMonth * months;
		updateCategory("dealer", { advanceGraceMonths: months, advanceGraceAmount: amount });
	};

	const handleCalculate = async () => {
		setCalculating(true);
		setCalcMessage(null);
		try {
			const body: Record<string, any> = { applno: applNo, apless, finType, splitPurchaseOrder: splitView, categories: {} };
			for (const key of visibleKeys) {
				if (categories[key]) body.categories[key] = categories[key];
			}
			const res = await api.post("/CAM/EditIndex/disbursement/calculate", body);
			if (res.data.success) {
				setCategories(prev => ({ ...prev, ...res.data.categories }));
				setCalcMessage({ type: "success", text: "Successful" });
			} else {
				setCalcMessage({ type: "error", text: res.data.message || "Failed" });
			}
		} catch (err: any) {
			setCalcMessage({ type: "error", text: err?.response?.data?.message || "Failed" });
		} finally {
			setCalculating(false);
		}
	};

	const handleReset = async () => {
		setResetting(true);
		setCalcMessage(null);
		try {
			const res = await api.post("/CAM/EditIndex/disbursement/reset", { applno: applNo, apless });
			if (res.data.success) {
				await load();
			} else {
				setCalcMessage({ type: "error", text: res.data.message || "Reset failed" });
			}
		} catch (err: any) {
			setCalcMessage({ type: "error", text: err?.response?.data?.message || "Reset failed" });
		} finally {
			setResetting(false);
		}
	};

	const categoryRows = externalAccounts.filter(r => r.split === selectedDisbursementCategory);
	const otherRows = externalAccounts.filter(r => r.split !== selectedDisbursementCategory);

	const updateCategoryRow = (idx: number, patch: Partial<AccountRow>) => {
		setExternalAccounts([...otherRows, ...categoryRows.map((r, i) => (i === idx ? { ...r, ...patch } : r))]);
	};
	const addCategoryRow = () => {
		setExternalAccounts([...otherRows, ...categoryRows, { split: selectedDisbursementCategory, bank: "", bankBranch: "", accName: "", accNo: "", amount: 0 }]);
	};
	const removeLastCategoryRow = () => {
		if (categoryRows.length === 0) return;
		setExternalAccounts([...otherRows, ...categoryRows.slice(0, -1)]);
	};

	const saveCategoryAccounts = async () => {
		setSavingAccounts(true);
		try {
			const res = await api.post("/CAM/EditIndex/disbursement/accounts/save", {
				applno: applNo, apless, split: selectedDisbursementCategory, rows: categoryRows,
			});
			if (res.data.success) {
				const saved = (res.data.accounts || []).map((a: any) => ({ ...a, split: selectedDisbursementCategory }));
				setExternalAccounts([...otherRows, ...saved]);
				setCalcMessage({ type: "success", text: "Successful" });
			} else {
				setCalcMessage({ type: "error", text: res.data.message || "Failed to save accounts" });
			}
		} catch (err: any) {
			setCalcMessage({ type: "error", text: err?.response?.data?.message || "Failed to save accounts" });
		} finally {
			setSavingAccounts(false);
		}
	};

	const deleteExternalAccount = async (id: number | undefined, row: AccountRow) => {
		if (!window.confirm("Are you sure to delete this record?")) return;
		if (id) {
			try {
				await api.delete(`/CAM/EditIndex/disbursement/accounts/${id}`, { params: { applno: applNo } });
			} catch { }
		}
		setExternalAccounts(prev => prev.filter(r => r !== row));
	};

	const saveInternalAccounts = async () => {
		setSavingCross(true);
		try {
			const res = await api.post("/CAM/EditIndex/disbursement/cross-accounts/save", { applno: applNo, rows: internalAccounts });
			if (res.data.success) {
				setInternalAccounts(res.data.accounts);
				setCalcMessage({ type: "success", text: "Successful" });
			} else {
				setCalcMessage({ type: "error", text: res.data.message || "Failed to save" });
			}
		} catch (err: any) {
			setCalcMessage({ type: "error", text: err?.response?.data?.message || "Failed to save" });
		} finally {
			setSavingCross(false);
		}
	};

	const deleteInternalAccount = async (id: number | undefined, row: CrossAccountRow) => {
		if (!window.confirm("Are you sure to delete this record?")) return;
		if (id) {
			try {
				await api.delete(`/CAM/EditIndex/disbursement/cross-accounts/${id}`, { params: { applno: applNo } });
			} catch {}
		}
		setInternalAccounts(prev => prev.filter(r => r !== row));
	};

	const handleNext = async () => {
		setAdvancing(true);
		setNextError("");
		try {
			const res = await api.post("/CAM/EditIndex/disbursement/next", {
				applno: applNo, apless, totalNetFinance: totals.totalPayment,
			});
			if (res.data.success) {
				onSaved({ apless, applno: applNo });
			} else {
				setNextError(res.data.message || "Please try again.");
			}
		} catch (err: any) {
			setNextError(err?.response?.data?.message || "Please try again.");
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
		<div className="space-y-1 rounded-2xl bg-white p-6 shadow">
			<h2 className="mb-4 text-base font-semibold text-slate-800">Disbursement</h2>

			{locked && (
				<div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">{lockMessage}</div>
			)}

			<Row label="Split Purchase Order">
				<label className="flex items-center gap-1.5 text-sm text-slate-700">
					<input type="radio" checked={!splitView} onChange={() => setSplitView(false)} /> No
				</label>
				<label className="flex items-center gap-1.5 text-sm text-slate-700">
					<input type="radio" checked={splitView} onChange={() => setSplitView(true)} /> Yes
				</label>
			</Row>

			<div className="flex gap-6 pb-1 pl-[220px]">
				{visibleKeys.map(key => (
					<div key={key} className={`${COL_WIDTH} text-center text-sm text-slate-600`}>
						{CATEGORY_LABELS[key]}
					</div>
				))}
				{showTotalColumn && <div className={`${COL_WIDTH} text-center text-sm text-slate-600`}>Total</div>}
			</div>

			<FieldRow label="Asset Value" visibleKeys={visibleKeys} categories={liveCategories} field="assetValue" editable={() => true}
				onChange={(k, v) => updateCategory(k, { assetValue: v })} />
			<FieldRow label={ketDpSecurity} visibleKeys={visibleKeys} categories={liveCategories} field="dp" editable={() => true}
				onChange={(k, v) => updateCategory(k, { dp: v })} />
			<FieldRow label="Survey Fee Gross 1" visibleKeys={visibleKeys} categories={liveCategories} field="surveyFeeGross1"
				editable={k => k === "dealer"} onChange={(k, v) => updateCategory(k, { surveyFeeGross1: v })} />
			<FieldRow label="Survey Fee Gross 2" visibleKeys={visibleKeys} categories={liveCategories} field="surveyFeeGross2"
				editable={k => k === "dealer"} onChange={(k, v) => updateCategory(k, { surveyFeeGross2: v })} />
			<FieldRow label="Notary Fee Gross" visibleKeys={visibleKeys} categories={liveCategories} field="notaryFeeGross"
				editable={k => k === "dealer"} onChange={(k, v) => updateCategory(k, { notaryFeeGross: v })} />
			<FieldRow label="Provision Fee" visibleKeys={visibleKeys} categories={liveCategories} field="provisionFee"
				editable={k => k === "dealer"} onChange={(k, v) => updateCategory(k, { provisionFee: v })} />
			<FieldRow label="Bussiness Trip Fee" visibleKeys={visibleKeys} categories={liveCategories} field="businessTripFee"
				editable={k => k === "dealer"} onChange={(k, v) => updateCategory(k, { businessTripFee: v })} />
			<FieldRow label="Insurance" visibleKeys={visibleKeys} categories={liveCategories} field="insurance"
				editable={k => k === "dealer"} onChange={(k, v) => updateCategory(k, { insurance: v })} />
			<FieldRow label="First Installment" visibleKeys={visibleKeys} categories={liveCategories} field="firstInstallment"
				editable={k => k === "dealer" && !readonlyFirstInstallment} onChange={(k, v) => updateCategory(k, { firstInstallment: v })} />

			<Row label="Advance Grace Period">
				{visibleKeys.map(key =>
					key === "dealer" ? (
						<span key={key} className="flex items-center gap-2">
							<input
								type="text"
								inputMode="numeric"
								className="w-16 rounded border border-slate-300 bg-white px-2 py-1 text-right text-sm text-slate-700"
								value={liveCategories.dealer?.advanceGraceMonths ?? 0}
								onChange={e => handleAdvanceGraceMonthsChange(parseNum(e.target.value))}
							/>
							<NumberInput value={liveCategories.dealer?.advanceGraceAmount ?? 0} readOnly className={readonlyInputCls} />
						</span>
					) : (
						<span key={key} className={COL_WIDTH} />
					)
				)}
				{showTotalColumn && <span className={COL_WIDTH} />}
			</Row>

			<FieldRow label="Agency Fee Gross" visibleKeys={visibleKeys} categories={liveCategories} field="agencyFeeGross" editable={() => false} />
			<FieldRow label="BBN Fee" visibleKeys={visibleKeys} categories={liveCategories} field="bbnFee" editable={() => false} />

			<Divider symbol="-" />

			<Row label="Refund to Dealer">
				<NumberInput value={refundToDealer} readOnly className={readonlyInputCls} />
			</Row>
			<Row label="Subsidy from Dealer">
				<NumberInput value={subsidyFromDealer} readOnly className={readonlyInputCls} />
			</Row>

			<Divider symbol="" />

			<FieldRow label="Disbursement to Dealer" visibleKeys={visibleKeys} categories={liveCategories} field="netFinance" editable={() => false} />
			<FieldRow label="Commission to Dealer (Gross)" visibleKeys={visibleKeys} categories={liveCategories} field="commissionToDealer" editable={() => false} />

			<Divider symbol="+" />

			<FieldRow label="Total Payment to Dealer" visibleKeys={visibleKeys} categories={liveCategories} field="totalPayment" editable={() => false} />

			{!locked && (
				<div className="flex gap-3 pt-3">
					<button
						type="button"
						onClick={handleReset}
						disabled={resetting}
						className="rounded bg-orange-500 px-4 py-1.5 text-sm font-medium text-white transition hover:bg-orange-600 disabled:opacity-50"
					>
						{resetting ? "Resetting…" : "Reset To Default"}
					</button>
					<button
						type="button"
						onClick={handleCalculate}
						disabled={calculating}
						className="rounded bg-orange-500 px-4 py-1.5 text-sm font-medium text-white transition hover:bg-orange-600 disabled:opacity-50"
					>
						{calculating ? "Calculating…" : "Calculate"}
					</button>
				</div>
			)}

			{calcMessage && (
				<p className={`pt-2 text-sm ${calcMessage.type === "success" ? "text-green-600" : "text-red-600"}`}>{calcMessage.text}</p>
			)}

			<div className="pt-8">
				<h3 className={sectionHeadingCls}>Disbursement To:</h3>
				<Row label="Disbursement Type">
					<select className={selectCls} value={disbursementTypeSelected} onChange={e => setDisbursementTypeSelected(e.target.value)}>
						<option value="">Select</option>
						{disbursementTypeOptions.map(opt => (
							<option key={opt.value} value={opt.value}>
								{opt.label}
							</option>
						))}
					</select>
				</Row>
			</div>

			{disbursementTypeSelected === "2" ? (
				<div className="pt-4">
					<div className="rounded-lg border border-slate-300 p-4">
						<h4 className={sectionHeadingCls + " mb-3"}>Disbursement To:</h4>
						<InternalStagingTable
							rows={internalAccounts}
							purposeOptions={purposeOptions}
							saving={savingCross}
							onChange={setInternalAccounts}
							onSave={saveInternalAccounts}
						/>
					</div>
				</div>
			) : (
				<div className="pt-4">
					<div className="rounded-lg border border-slate-300 p-4">
						<h4 className={sectionHeadingCls + " mb-3"}>Disbursement To:</h4>
						<Row label="Disbursement to">
							<select className={selectCls} value={selectedDisbursementCategory} onChange={e => setSelectedDisbursementCategory(e.target.value)}>
								{disbursessToOptions.map(opt => (
									<option key={opt.value} value={opt.value}>
										{opt.label}
									</option>
								))}
							</select>
						</Row>
						<ExternalStagingTable
							category={selectedDisbursementCategory}
							rows={categoryRows}
							bankOptions={bankOptions}
							saving={savingAccounts}
							onUpdateRow={updateCategoryRow}
							onAddRow={addCategoryRow}
							onRemoveRow={removeLastCategoryRow}
							onSave={saveCategoryAccounts}
						/>
					</div>
				</div>
			)}

			<div className="space-y-6 pt-8">
				<div>
					<h3 className={sectionHeadingCls + " mb-2"}>Internal Disbursement</h3>
					<InternalSummaryTable rows={internalAccounts} onDelete={deleteInternalAccount} />
				</div>
				<div>
					<h3 className={sectionHeadingCls + " mb-2"}>External Disbursement</h3>
					<ExternalSummaryTable rows={externalAccounts} onDelete={deleteExternalAccount} />
				</div>
			</div>

			{nextError && <p className="pt-3 text-sm text-red-600">{nextError}</p>}

			<div className="flex justify-end pt-6">
				<button
					type="button"
					onClick={handleNext}
					disabled={advancing}
					className="rounded bg-orange-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-orange-600 disabled:opacity-50"
				>
					{advancing ? "Please wait…" : "Next >>"}
				</button>
			</div>
		</div>
	);
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
	return (
		<div className="flex items-center gap-6 py-1.5">
			<label className={`${labelCls} w-[210px] shrink-0`}>{label}</label>
			<div className="flex items-center gap-6">{children}</div>
		</div>
	);
}

function FieldRow({
	label,
	visibleKeys,
	categories,
	field,
	editable,
	onChange,
}: {
	label: string;
	visibleKeys: CategoryKey[];
	categories: Partial<Record<CategoryKey, CategoryFields>>;
	field: keyof CategoryFields;
	editable: (key: CategoryKey) => boolean;
	onChange?: (key: CategoryKey, value: number) => void;
}) {
	const showTotal = visibleKeys.length > 1;
	const total = visibleKeys.reduce((acc, k) => acc + ((categories[k]?.[field] as number) ?? 0), 0);
	return (
		<Row label={label}>
			{visibleKeys.map(key => {
				if (key !== "dealer" && DEALER_ONLY_FIELDS.has(field as string)) {
					return <span key={key} className={COL_WIDTH} />;
				}
				const value = (categories[key]?.[field] as number) ?? 0;
				const canEdit = editable(key);
				return (
					<NumberInput
						key={key}
						value={value}
						readOnly={!canEdit}
						className={canEdit ? inputCls : readonlyInputCls}
						onChange={v => onChange?.(key, v)}
					/>
				);
			})}
			{showTotal && <NumberInput value={total} readOnly className={readonlyInputCls} />}
		</Row>
	);
}

function Divider({ symbol }: { symbol: "-" | "+" | "" }) {
	return (
		<div className="relative w-[210px] pb-3 pt-2">
			<div className="border-t border-slate-400" />
			{symbol && <span className="absolute -top-1 right-[-14px] text-base font-semibold text-slate-500">{symbol}</span>}
		</div>
	);
}

function ExternalStagingTable({
	category,
	rows,
	bankOptions,
	saving,
	onUpdateRow,
	onAddRow,
	onRemoveRow,
	onSave,
}: {
	category: string;
	rows: AccountRow[];
	bankOptions: ComboOption[];
	saving: boolean;
	onUpdateRow: (idx: number, patch: Partial<AccountRow>) => void;
	onAddRow: () => void;
	onRemoveRow: () => void;
	onSave: () => void;
}) {
	const total = rows.reduce((acc, r) => acc + (r.amount || 0), 0);
	return (
		<div className="mt-3 overflow-hidden rounded border border-slate-300">
			<table className="w-full border-collapse text-sm">
				<thead>
					<tr className="bg-slate-600 text-left text-white">
						<th className="p-2 font-medium">Disbursement to</th>
						<th className="p-2 font-medium">Bank Name</th>
						<th className="p-2 font-medium">Bank Branch</th>
						<th className="p-2 font-medium">Account Name</th>
						<th className="p-2 font-medium">Account Number</th>
						<th className="p-2 text-right font-medium">Amount</th>
						<th className="p-2 font-medium"></th>
					</tr>
				</thead>
				<tbody>
					{rows.map((r, idx) => (
						<tr key={r.id ?? idx} className="border-b border-slate-200">
							<td className="p-2 text-slate-600">{category}</td>
							<td className="p-2">
								<select className={selectCls} value={r.bank} onChange={e => onUpdateRow(idx, { bank: e.target.value })}>
									<option value="">Select</option>
									{bankOptions.map(opt => (
										<option key={opt.value} value={opt.value}>
											{opt.label}
										</option>
									))}
								</select>
							</td>
							<td className="p-2">
								<input type="text" className={textInputCls} value={r.bankBranch} onChange={e => onUpdateRow(idx, { bankBranch: e.target.value })} />
							</td>
							<td className="p-2">
								<input type="text" className={textInputCls} value={r.accName} onChange={e => onUpdateRow(idx, { accName: e.target.value })} />
							</td>
							<td className="p-2">
								<input type="text" className={textInputCls} value={r.accNo} onChange={e => onUpdateRow(idx, { accNo: e.target.value })} />
							</td>
							<td className="p-2">
								<NumberInput value={r.amount} className={inputCls} onChange={v => onUpdateRow(idx, { amount: v })} />
							</td>
							<td className="p-2"></td>
						</tr>
					))}
					<tr className="bg-white">
						<td className="p-2">
							<div className="flex gap-1.5">
								<button type="button" onClick={onAddRow} className={roundIconBtnCls + " bg-blue-500 hover:bg-blue-600"} title="Add row">
									+
								</button>
								<button type="button" onClick={onRemoveRow} className={roundIconBtnCls + " bg-slate-400 hover:bg-slate-500"} title="Remove last row">
									−
								</button>
							</div>
						</td>
						<td className="p-2 text-right font-semibold text-slate-700" colSpan={4}>
							Total
						</td>
						<td className="p-2 text-right">
							<span className={readonlyInputCls}>{fmt(total)}</span>
						</td>
						<td className="p-2"></td>
					</tr>
				</tbody>
			</table>
			<div className="flex justify-center border-t border-slate-200 bg-slate-50 p-2">
				<button
					type="button"
					onClick={onSave}
					disabled={saving}
					className="rounded bg-orange-500 px-4 py-1.5 text-sm font-medium text-white transition hover:bg-orange-600 disabled:opacity-50"
				>
					{saving ? "Saving…" : "Save"}
				</button>
			</div>
		</div>
	);
}

function InternalStagingTable({
	rows,
	purposeOptions,
	saving,
	onChange,
	onSave,
}: {
	rows: CrossAccountRow[];
	purposeOptions: ComboOption[];
	saving: boolean;
	onChange: (rows: CrossAccountRow[]) => void;
	onSave: () => void;
}) {
	const total = rows.reduce((acc, r) => acc + (r.amount || 0), 0);
	const updateRow = (idx: number, patch: Partial<CrossAccountRow>) => onChange(rows.map((r, i) => (i === idx ? { ...r, ...patch } : r)));

	return (
		<div className="overflow-hidden rounded border border-slate-300">
			<table className="w-full border-collapse text-sm">
				<thead>
					<tr className="bg-slate-600 text-left text-white">
						<th className="p-2 font-medium">Disbursement to</th>
						<th className="p-2 font-medium">Contract Number</th>
						<th className="p-2 text-right font-medium">Amount</th>
						<th className="p-2 font-medium">Purpose</th>
						<th className="p-2 font-medium"></th>
					</tr>
				</thead>
				<tbody>
					{rows.map((r, idx) => (
						<tr key={r.id ?? idx} className="border-b border-slate-200">
							<td className="p-2 text-slate-600">Company</td>
							<td className="p-2">
								<input type="text" className={textInputCls} value={r.crossNo} onChange={e => updateRow(idx, { crossNo: e.target.value })} />
							</td>
							<td className="p-2">
								<NumberInput value={r.amount} className={inputCls} onChange={v => updateRow(idx, { amount: v })} />
							</td>
							<td className="p-2">
								<select className={selectCls} value={r.purpose} onChange={e => updateRow(idx, { purpose: e.target.value })}>
									<option value="">Select</option>
									{purposeOptions.map(opt => (
										<option key={opt.value} value={opt.value}>
											{opt.label}
										</option>
									))}
								</select>
							</td>
							<td className="p-2"></td>
						</tr>
					))}
					<tr className="bg-white">
						<td className="p-2">
							<div className="flex gap-1.5">
								<button type="button" onClick={() => onChange([...rows, { crossNo: "", amount: 0, purpose: "" }])} className={roundIconBtnCls + " bg-blue-500 hover:bg-blue-600"} title="Add row">
									+
								</button>
								<button type="button" onClick={() => onChange(rows.slice(0, -1))} className={roundIconBtnCls + " bg-slate-400 hover:bg-slate-500"} title="Remove last row">
									−
								</button>
							</div>
						</td>
						<td className="p-2 text-right font-semibold text-slate-700">Total</td>
						<td className="p-2 text-right">
							<span className={readonlyInputCls}>{fmt(total)}</span>
						</td>
						<td className="p-2" colSpan={2}></td>
					</tr>
				</tbody>
			</table>
			<div className="flex justify-center border-t border-slate-200 bg-slate-50 p-2">
				<button
					type="button"
					onClick={onSave}
					disabled={saving}
					className="rounded bg-orange-500 px-4 py-1.5 text-sm font-medium text-white transition hover:bg-orange-600 disabled:opacity-50"
				>
					{saving ? "Saving…" : "Save"}
				</button>
			</div>
		</div>
	);
}

function ExternalSummaryTable({ rows, onDelete }: { rows: AccountRow[]; onDelete: (id: number | undefined, row: AccountRow) => void }) {
	const total = rows.reduce((acc, r) => acc + (r.amount || 0), 0);
	return (
		<div className="overflow-hidden rounded border border-slate-300">
			<table className="w-full border-collapse text-sm">
				<thead>
					<tr className="bg-slate-600 text-left text-white">
						<th className="p-2 font-medium">Disbursement to</th>
						<th className="p-2 font-medium">Bank Name</th>
						<th className="p-2 font-medium">Bank Branch</th>
						<th className="p-2 font-medium">Account Name</th>
						<th className="p-2 font-medium">Account Number</th>
						<th className="p-2 text-right font-medium">Amount</th>
						<th className="p-2 font-medium">Action</th>
					</tr>
				</thead>
				<tbody>
					{rows.map((r, idx) => (
						<tr key={r.id ?? idx} className="border-b border-slate-200 text-slate-600">
							<td className="p-2">{r.split}</td>
							<td className="p-2">{r.bankLabel || r.bank}</td>
							<td className="p-2">{r.bankBranch}</td>
							<td className="p-2">{r.accName}</td>
							<td className="p-2">{r.accNo}</td>
							<td className="p-2 text-right">{fmt(r.amount)}</td>
							<td className="p-2">
								<button type="button" onClick={() => onDelete(r.id, r)} className="text-xs font-medium text-red-600 hover:underline">
									Delete
								</button>
							</td>
						</tr>
					))}
					<tr className="bg-white font-semibold text-slate-700">
						<td className="p-2" colSpan={5}>
							Total
						</td>
						<td className="p-2 text-right">{fmt(total)}</td>
						<td className="p-2"></td>
					</tr>
				</tbody>
			</table>
		</div>
	);
}

function InternalSummaryTable({ rows, onDelete }: { rows: CrossAccountRow[]; onDelete: (id: number | undefined, row: CrossAccountRow) => void }) {
	const total = rows.reduce((acc, r) => acc + (r.amount || 0), 0);
	return (
		<div className="overflow-hidden rounded border border-slate-300">
			<table className="w-full border-collapse text-sm">
				<thead>
					<tr className="bg-slate-600 text-left text-white">
						<th className="p-2 font-medium">Disbursement to</th>
						<th className="p-2 font-medium">Contract Number</th>
						<th className="p-2 text-right font-medium">Amount</th>
						<th className="p-2 font-medium">Purpose</th>
						<th className="p-2 font-medium">Action</th>
					</tr>
				</thead>
				<tbody>
					{rows.map((r, idx) => (
						<tr key={r.id ?? idx} className="border-b border-slate-200 text-slate-600">
							<td className="p-2">Company</td>
							<td className="p-2">{r.crossNo}</td>
							<td className="p-2 text-right">{fmt(r.amount)}</td>
							<td className="p-2">{r.purposeLabel || r.purpose}</td>
							<td className="p-2">
								<button type="button" onClick={() => onDelete(r.id, r)} className="text-xs font-medium text-red-600 hover:underline">
									Delete
								</button>
							</td>
						</tr>
					))}
					<tr className="bg-white font-semibold text-slate-700">
						<td className="p-2">Total</td>
						<td className="p-2"></td>
						<td className="p-2 text-right">{fmt(total)}</td>
						<td className="p-2" colSpan={2}></td>
					</tr>
				</tbody>
			</table>
		</div>
	);
}