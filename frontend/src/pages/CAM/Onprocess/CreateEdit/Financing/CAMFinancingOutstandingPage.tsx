import { useCallback, useEffect, useState } from "react";
import api from "../../../../../api/axiosInstance";

export interface CAMFinancingOutstandingPageProps {
	apless: string;
	applNo: string;
	onSaved: (result: { apless: string; applno: string }) => void;
}

interface AmountRow {
	unit: number;
	amount: number;
}

interface ExposureSummary {
	disbursement: AmountRow;
	undisbursement: AmountRow;
	unapprove: AmountRow;
	group: AmountRow;
	guarantor: AmountRow;
	total: AmountRow;
}

interface DetailRow {
	no: number;
	contractNo: string | null;
	brandType: string | null;
	carYear: number | string | null;
	marketPrice: number;
	outstandingPrincipal: number;
	installmentPerMonth: number;
	term: number | string | null;
	tenor: number | string | null;
	paymentStatus?: string | null;
	userOfCar: string | null;
	loanRatio: number;
	branch: string | null;
	remark?: string | null;
	consLeas?: string | null;
}

interface SubTotal {
	marketPrice: number;
	outstandingPrincipal: number;
	installmentPerMonth: number;
	loanRatioPct: number;
}

interface SimpleSection {
	rows: DetailRow[];
	subTotal: SubTotal;
}

interface DisbursementSection extends SimpleSection {
	crossCollateral: {
		cross: SubTotal;
		nonCross: SubTotal;
		totalExposure: SubTotal;
	};
	financeTypeBreakdown: {
		leasing: { outstandingPrincipal: number; units: number };
		consumerFinance: { outstandingPrincipal: number; units: number };
		installmentFinancing: { outstandingPrincipal: number; units: number };
		financeLease: { outstandingPrincipal: number; units: number };
		saleLeaseback: { outstandingPrincipal: number; units: number };
	};
}

interface GrandTotals {
	disUndisUnapp: SubTotal;
	all: SubTotal | null;
}

interface OutstandingView {
	blocked?: boolean;
	message?: string;
	calcDate: string | null;
	notes: string;
	summary: ExposureSummary;
	disbursement: DisbursementSection;
	undisbursement: SimpleSection;
	unapprove: SimpleSection;
	group: SimpleSection;
	guarantor: SimpleSection;
	grandTotal: GrandTotals;
}

const PAYMENT_STATUS_OPTIONS = ["Medium", "Good"];

function fmt(value: number | null | undefined) {
	if (value === undefined || value === null || Number.isNaN(value)) return "0";
	const digits = Math.round(value).toString();
	return digits.replace(/\B(?=(\d{3})+(?!\d))/g, ",").replace(/^-,/, "-");
}

function pct(value: number | null | undefined) {
	if (value === undefined || value === null || Number.isNaN(value)) return "0.00";
	return value.toFixed(2);
}

function formatDate(iso: string | null) {
	if (!iso) return "-";
	const d = new Date(iso);
	if (Number.isNaN(d.getTime())) return iso;
	const dd = String(d.getDate()).padStart(2, "0");
	const mm = String(d.getMonth() + 1).padStart(2, "0");
	return `${dd}-${mm}-${d.getFullYear()}`;
}

function matchPaymentStatus(value: string | null | undefined) {
	const v = (value || "").toLowerCase();
	if (v === "medium") return "Medium";
	if (v === "good") return "Good";
	return "";
}

const readonlyBoxCls = "w-full rounded-lg border border-slate-200 bg-slate-50 p-2 text-right text-sm";
const editableBoxCls = "w-28 rounded-lg border border-slate-300 bg-white p-2 text-right text-sm";
const selectCls = "w-28 rounded-lg border border-slate-300 bg-white p-2 text-sm";

export default function CAMFinancingOutstandingPage({ apless, applNo, onSaved }: CAMFinancingOutstandingPageProps) {
	const [loading, setLoading] = useState(true);
	const [loadError, setLoadError] = useState("");
	const [view, setView] = useState<OutstandingView | null>(null);
	const [notes, setNotes] = useState("");

	const [disRows, setDisRows] = useState<DetailRow[]>([]);
	const [undisRows, setUndisRows] = useState<DetailRow[]>([]);
	const [unappRows, setUnappRows] = useState<DetailRow[]>([]);
	const [groupRows, setGroupRows] = useState<DetailRow[]>([]);
	const [guaRows, setGuaRows] = useState<DetailRow[]>([]);

	const [calculating, setCalculating] = useState(false);
	const [calcError, setCalcError] = useState("");
	const [advancing, setAdvancing] = useState(false);
	const [nextErrors, setNextErrors] = useState<string[]>([]);

	const applyView = (d: OutstandingView) => {
		setView(d);
		setNotes(d.notes || "");
		setDisRows(d.disbursement.rows);
		setUndisRows(d.undisbursement.rows);
		setUnappRows(d.unapprove.rows);
		setGroupRows(d.group.rows);
		setGuaRows(d.guarantor.rows);
	};

	const load = useCallback(async () => {
		setLoading(true);
		setLoadError("");
		try {
			const res = await api.get("/CAM/EditIndex/outstanding", { params: { apless, applno: applNo } });
			if (res.data.blocked) {
				setLoadError(res.data.message || "This application cannot be edited right now.");
				return;
			}
			applyView(res.data);
		} catch {
			setLoadError("Failed to load Outstanding. Please try again.");
		} finally {
			setLoading(false);
		}
	}, [apless, applNo]);

	useEffect(() => {
		load();
	}, [load]);

	const handleCalculate = async () => {
		setCalculating(true);
		setCalcError("");
		try {
			const res = await api.post("/CAM/EditIndex/outstanding/calculate", { apless, applno: applNo, notes });
			if (res.data.success === false) {
				setCalcError(res.data.message || "Calculation failed. Please try again.");
				return;
			}
			applyView(res.data);
		} catch (err: any) {
			setCalcError(err?.response?.data?.message || "Calculation failed. Please try again.");
		} finally {
			setCalculating(false);
		}
	};

	const handleNext = async () => {
		setAdvancing(true);
		setNextErrors([]);
		try {
			const res = await api.post("/CAM/EditIndex/outstanding/next", {
				apless,
				applno: applNo,
				notes,
				disbursementRows: disRows,
				undisbursementRows: undisRows,
				unapproveRows: unappRows,
				groupRows,
				guarantorRows: guaRows,
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
	if (!view) return null;

	return (
		<div className="space-y-6 rounded-2xl bg-white p-6 shadow">
			<h2 className="text-base font-semibold text-slate-700">Outstanding</h2>

			<div className="mx-auto w-full max-w-md">
				<table className="w-full border-collapse text-sm">
					<thead>
						<tr>
							<th className="p-2"></th>
							<th className="p-2 text-center" colSpan={2}>
								OUTSTANDING EXPOSURE
							</th>
						</tr>
						<tr className="text-center text-slate-500">
							<th className="p-2 text-left">Outstanding</th>
							<th className="p-2">Unit</th>
							<th className="p-2">Amount</th>
						</tr>
					</thead>
					<tbody>
						<ExposureRow label="Disbursement" row={view.summary.disbursement} />
						<ExposureRow label="Undisbursement" row={view.summary.undisbursement} />
						<ExposureRow label="Unapprove" row={view.summary.unapprove} />
						<ExposureRow label="Group" row={view.summary.group} />
						<ExposureRow label="Guarantor" row={view.summary.guarantor} />
						<tr>
							<td className="p-1" colSpan={3}></td>
						</tr>
						<tr className="border-t border-slate-200 font-semibold">
							<td className="p-2">Total</td>
							<td className="p-2">
								<span className={readonlyBoxCls}>{fmt(view.summary.total.unit)}</span>
							</td>
							<td className="p-2">
								<span className={readonlyBoxCls}>{fmt(view.summary.total.amount)}</span>
							</td>
						</tr>
					</tbody>
				</table>

				<div className="mt-3 flex items-center justify-between text-sm">
					<span className="font-medium text-slate-600">Calculation Date</span>
					<span className="text-slate-700">{formatDate(view.calcDate)}</span>
				</div>

				<div className="mt-3 text-center">
					<button
						type="button"
						onClick={handleCalculate}
						disabled={calculating}
						className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:opacity-50"
					>
						{calculating ? "Calculating…" : "Calculate"}
					</button>
				</div>
				{calcError && <p className="mt-2 text-sm text-red-600">{calcError}</p>}

				<div className="mt-4 space-y-1">
					<label className="block text-sm font-medium text-slate-600">Outstanding Notes</label>
					<textarea
						value={notes}
						onChange={e => setNotes(e.target.value)}
						rows={3}
						className="w-full rounded-lg border border-slate-300 p-2 text-sm"
					/>
				</div>
			</div>

			{disRows.length > 0 && <DisbursementTable rows={disRows} setRows={setDisRows} section={view.disbursement} />}

			{undisRows.length > 0 && (
				<SimpleDetailTable
					title="Undisbursement"
					contractNoLabel="Contract No / Cam No"
					rows={undisRows}
					setRows={setUndisRows}
					subTotal={view.undisbursement.subTotal}
					showPaymentStatus
					marketPriceEditable
				/>
			)}

			{unappRows.length > 0 && (
				<SimpleDetailTable
					title="Unapprove"
					contractNoLabel="Cam No"
					rows={unappRows}
					setRows={setUnappRows}
					subTotal={view.unapprove.subTotal}
					showPaymentStatus={false}
					showFinanceType
					marketPriceEditable={false}
				/>
			)}

			<GrandTotalTable title="Grand Total" totals={view.grandTotal.disUndisUnapp} />

			{groupRows.length > 0 && (
				<SimpleDetailTable
					title="Group"
					contractNoLabel="Cam / Contract No"
					rows={groupRows}
					setRows={setGroupRows}
					subTotal={view.group.subTotal}
					showPaymentStatus
					marketPriceEditable
				/>
			)}

			{guaRows.length > 0 && (
				<SimpleDetailTable
					title="Guarantor"
					contractNoLabel="Cam / Contract No"
					rows={guaRows}
					setRows={setGuaRows}
					subTotal={view.guarantor.subTotal}
					showPaymentStatus
					marketPriceEditable
				/>
			)}

			{view.grandTotal.all && <GrandTotalTable title="Grand Total" totals={view.grandTotal.all} />}

			<RemarksLegend />

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

function ExposureRow({ label, row }: { label: string; row: AmountRow }) {
	return (
		<tr>
			<td className="p-2 text-left">{label}</td>
			<td className="p-2">
				<span className={readonlyBoxCls}>{fmt(row.unit)}</span>
			</td>
			<td className="p-2">
				<span className={readonlyBoxCls}>{fmt(row.amount)}</span>
			</td>
		</tr>
	);
}

function DisbursementTable({
	rows,
	setRows,
	section,
}: {
	rows: DetailRow[];
	setRows: (rows: DetailRow[]) => void;
	section: DisbursementSection;
}) {
	const updateRow = (no: number, patch: Partial<DetailRow>) => {
		setRows(rows.map(r => (r.no === no ? { ...r, ...patch } : r)));
	};

	return (
		<div className="space-y-3">
			<p className="font-semibold text-slate-700">Customer Records (For Repeat Order Customer)</p>
			<p className="font-medium text-slate-600">Disbursement</p>
			<div className="overflow-x-auto">
				<table className="w-full min-w-[1200px] border-collapse text-sm">
					<thead>
						<tr className="border-b border-slate-200 bg-slate-50 text-left text-slate-500">
							<th className="p-2">No.</th>
							<th className="p-2">Contract No</th>
							<th className="p-2">Brand/ Type</th>
							<th className="p-2">Car Year</th>
							<th className="p-2">Market Price</th>
							<th className="p-2">Outstanding Principal</th>
							<th className="p-2">Installment/ Month</th>
							<th className="p-2">Terms</th>
							<th className="p-2">Payment Status</th>
							<th className="p-2">User of Car</th>
							<th className="p-2">Loan Ratio (%)</th>
							<th className="p-2">Branch</th>
							<th className="p-2">Remark</th>
						</tr>
					</thead>
					<tbody>
						{rows.map(row => (
							<tr key={row.no} className="border-b border-slate-100">
								<td className="p-2 text-center">{row.no}</td>
								<td className="p-2">{row.contractNo}</td>
								<td className="p-2">{row.brandType}</td>
								<td className="p-2 text-right">{row.carYear}</td>
								<td className="p-2">
									<input
										type="text"
										className={editableBoxCls}
										value={row.marketPrice}
										onChange={e =>
											updateRow(row.no, { marketPrice: Number(e.target.value.replace(/[^\d.]/g, "")) || 0 })
										}
									/>
								</td>
								<td className="p-2 text-right">{fmt(row.outstandingPrincipal)}</td>
								<td className="p-2 text-right">{fmt(row.installmentPerMonth)}</td>
								<td className="p-2 text-center">
									{row.term ?? ""} of {row.tenor}
								</td>
								<td className="p-2">
									<select
										className={selectCls}
										value={matchPaymentStatus(row.paymentStatus)}
										onChange={e => updateRow(row.no, { paymentStatus: e.target.value })}
									>
										<option value="">Select</option>
										{PAYMENT_STATUS_OPTIONS.map(opt => (
											<option key={opt} value={opt}>
												{opt}
											</option>
										))}
									</select>
								</td>
								<td className="p-2">{row.userOfCar}</td>
								<td className="p-2 text-right">{pct(row.loanRatio)}</td>
								<td className="p-2">{row.branch}</td>
								<td className="p-2">{row.remark}</td>
							</tr>
						))}
						<tr className="border-t border-slate-300 bg-slate-50 font-semibold">
							<td className="p-2" colSpan={4}>
								Sub Total
							</td>
							<td className="p-2 text-right">{fmt(section.subTotal.marketPrice)}</td>
							<td className="p-2 text-right">{fmt(section.subTotal.outstandingPrincipal)}</td>
							<td className="p-2 text-right">{fmt(section.subTotal.installmentPerMonth)}</td>
							<td className="p-2"></td>
							<td className="p-2"></td>
							<td className="p-2"></td>
							<td className="p-2 text-right">{pct(section.subTotal.loanRatioPct)}</td>
							<td className="p-2"></td>
							<td className="p-2"></td>
						</tr>
					</tbody>
				</table>
			</div>

			<div className="overflow-x-auto">
				<table className="w-full max-w-3xl border-collapse text-sm">
					<thead>
						<tr className="border-b border-slate-200 text-center text-slate-500">
							<th className="p-2" colSpan={3}></th>
							<th className="p-2">Market Price</th>
							<th className="p-2">Outstanding Principal</th>
							<th className="p-2">Installment/ Month</th>
							<th className="p-2">Loan Ratio</th>
						</tr>
					</thead>
					<tbody>
						<BreakdownRow label="Total Cross Collateral Customer" totals={section.crossCollateral.cross} />
						<BreakdownRow label="Total non Cross Collateral Customer" totals={section.crossCollateral.nonCross} />
						<BreakdownRow label="Total Exposure Customer" totals={section.crossCollateral.totalExposure} />
						<FinanceTypeRow label="Leasing" data={section.financeTypeBreakdown.leasing} />
						<FinanceTypeRow label="Consumer Finance" data={section.financeTypeBreakdown.consumerFinance} />
						<FinanceTypeRow label="Installment Financing" data={section.financeTypeBreakdown.installmentFinancing} />
						<FinanceTypeRow label="Finance Lease" data={section.financeTypeBreakdown.financeLease} />
						<FinanceTypeRow label="Sale & Leaseback" data={section.financeTypeBreakdown.saleLeaseback} />
					</tbody>
				</table>
			</div>
		</div>
	);
}

function BreakdownRow({ label, totals }: { label: string; totals: SubTotal }) {
	return (
		<tr className="border-b border-slate-100">
			<td className="p-2" colSpan={3}>
				{label}
			</td>
			<td className="p-2 text-right">{fmt(totals.marketPrice)}</td>
			<td className="p-2 text-right">{fmt(totals.outstandingPrincipal)}</td>
			<td className="p-2 text-right">{fmt(totals.installmentPerMonth)}</td>
			<td className="p-2 text-right">{pct(totals.loanRatioPct)}</td>
		</tr>
	);
}

function FinanceTypeRow({ label, data }: { label: string; data: { outstandingPrincipal: number; units: number } }) {
	return (
		<tr className="border-b border-slate-100">
			<td className="p-2" colSpan={4}>
				{label}
			</td>
			<td className="p-2 text-right">{fmt(data.outstandingPrincipal)}</td>
			<td className="p-2 text-right">{data.units} Unit</td>
			<td className="p-2"></td>
		</tr>
	);
}

function SimpleDetailTable({
	title,
	contractNoLabel,
	rows,
	setRows,
	subTotal,
	showPaymentStatus,
	showFinanceType,
	marketPriceEditable,
}: {
	title: string;
	contractNoLabel: string;
	rows: DetailRow[];
	setRows: (rows: DetailRow[]) => void;
	subTotal: SubTotal;
	showPaymentStatus: boolean;
	showFinanceType?: boolean;
	marketPriceEditable: boolean;
}) {
	const updateRow = (no: number, patch: Partial<DetailRow>) => {
		setRows(rows.map(r => (r.no === no ? { ...r, ...patch } : r)));
	};

	return (
		<div className="space-y-3">
			<p className="font-medium text-slate-600">{title}</p>
			<div className="overflow-x-auto">
				<table className="w-full min-w-[1000px] border-collapse border border-slate-200 text-sm">
					<thead>
						<tr className="border-b border-slate-200 bg-slate-50 text-left text-slate-500">
							<th className="border border-slate-200 p-2">No</th>
							<th className="border border-slate-200 p-2">{contractNoLabel}</th>
							<th className="border border-slate-200 p-2">Brand/Type</th>
							<th className="border border-slate-200 p-2">Car Year</th>
							<th className="border border-slate-200 p-2">Market Price</th>
							<th className="border border-slate-200 p-2">Outstanding Principal</th>
							<th className="border border-slate-200 p-2">Installment/ Month</th>
							<th className="border border-slate-200 p-2">Terms</th>
							{showPaymentStatus && <th className="border border-slate-200 p-2">Payment Status</th>}
							<th className="border border-slate-200 p-2">User of Car</th>
							<th className="border border-slate-200 p-2">Loan Ratio (%)</th>
							<th className="border border-slate-200 p-2">Branch</th>
							{showFinanceType && <th className="border border-slate-200 p-2">Finance Type</th>}
						</tr>
					</thead>
					<tbody>
						{rows.map(row => (
							<tr key={row.no}>
								<td className="border border-slate-200 p-2 text-center">{row.no}</td>
								<td className="border border-slate-200 p-2">{row.contractNo}</td>
								<td className="border border-slate-200 p-2">{row.brandType}</td>
								<td className="border border-slate-200 p-2 text-right">{row.carYear}</td>
								<td className="border border-slate-200 p-2">
									{marketPriceEditable ? (
										<input
											type="text"
											className={editableBoxCls}
											value={row.marketPrice}
											onChange={e =>
												updateRow(row.no, {
													marketPrice: Number(e.target.value.replace(/[^\d.]/g, "")) || 0,
												})
											}
										/>
									) : (
										<span className={readonlyBoxCls}>{fmt(row.marketPrice)}</span>
									)}
								</td>
								<td className="border border-slate-200 p-2 text-right">{fmt(row.outstandingPrincipal)}</td>
								<td className="border border-slate-200 p-2 text-right">{fmt(row.installmentPerMonth)}</td>
								<td className="border border-slate-200 p-2 text-center">
									{row.term ?? ""} of {row.tenor}
								</td>
								{showPaymentStatus && (
									<td className="border border-slate-200 p-2">
										<select
											className={selectCls}
											value={matchPaymentStatus(row.paymentStatus)}
											onChange={e => updateRow(row.no, { paymentStatus: e.target.value })}
										>
											<option value="">Select</option>
											{PAYMENT_STATUS_OPTIONS.map(opt => (
												<option key={opt} value={opt}>
													{opt}
												</option>
											))}
										</select>
									</td>
								)}
								<td className="border border-slate-200 p-2">{row.userOfCar}</td>
								<td className="border border-slate-200 p-2 text-right">{pct(row.loanRatio)}</td>
								<td className="border border-slate-200 p-2">{row.branch}</td>
								{showFinanceType && <td className="border border-slate-200 p-2 text-center">{row.consLeas}</td>}
							</tr>
						))}
						<tr className="bg-slate-50 font-semibold">
							<td className="border border-slate-200 p-2" colSpan={4}>
								Sub Total
							</td>
							<td className="border border-slate-200 p-2 text-right">{fmt(subTotal.marketPrice)}</td>
							<td className="border border-slate-200 p-2 text-right">{fmt(subTotal.outstandingPrincipal)}</td>
							<td className="border border-slate-200 p-2 text-right">{fmt(subTotal.installmentPerMonth)}</td>
							<td className="border border-slate-200 p-2"></td>
							{showPaymentStatus && <td className="border border-slate-200 p-2"></td>}
							<td className="border border-slate-200 p-2"></td>
							<td className="border border-slate-200 p-2 text-right">{pct(subTotal.loanRatioPct)}</td>
							<td className="border border-slate-200 p-2"></td>
							{showFinanceType && <td className="border border-slate-200 p-2"></td>}
						</tr>
					</tbody>
				</table>
			</div>
		</div>
	);
}

function GrandTotalTable({ title, totals }: { title: string; totals: SubTotal }) {
	return (
		<div className="overflow-x-auto">
			<table className="w-full max-w-2xl border-collapse border border-slate-200 text-sm">
				<thead>
					<tr className="border-b border-slate-200 bg-slate-50 text-center text-slate-500">
						<th className="border border-slate-200 p-2" colSpan={3}></th>
						<th className="border border-slate-200 p-2">Market Price</th>
						<th className="border border-slate-200 p-2">Outstanding Principal</th>
						<th className="border border-slate-200 p-2">Installment/ Month</th>
						<th className="border border-slate-200 p-2">Loan Ratio</th>
					</tr>
				</thead>
				<tbody>
					<tr className="font-semibold">
						<td className="border border-slate-200 p-2" colSpan={3}>
							{title}
						</td>
						<td className="border border-slate-200 p-2 text-right">{fmt(totals.marketPrice)}</td>
						<td className="border border-slate-200 p-2 text-right">{fmt(totals.outstandingPrincipal)}</td>
						<td className="border border-slate-200 p-2 text-right">{fmt(totals.installmentPerMonth)}</td>
						<td className="border border-slate-200 p-2 text-right">{pct(totals.loanRatioPct)}</td>
					</tr>
				</tbody>
			</table>
		</div>
	);
}

function RemarksLegend() {
	const items: [string, string][] = [
		["F", "Finance Lease (FL)"],
		["I", "Installment Financing (IF)"],
		["S", "Sale & Leaseback (SL)"],
		["D", "Fund Facility (FD)"],
		["M", "Business Capital Facility (FMU)"],
	];
	return (
		<div className="text-sm text-slate-600">
			<p className="mb-1 font-medium">Remark for Finance Type :</p>
			<ul className="space-y-0.5">
				{items.map(([code, label]) => (
					<li key={code}>
						- {code} = {label}
					</li>
				))}
			</ul>
		</div>
	);
}
