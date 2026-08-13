import { useCallback, useEffect, useState } from "react";
import api from "../../../../../api/axiosInstance";
import { EditCommissionModal, SalesDealerPickerModal, type SalesPickResult } from "./CommissionSharedComponents";

export interface CAMFinancingCommissionPageProps {
	apless: string;
	applNo: string;
	onSaved: (result: { apless: string; applno: string }) => void;
}

interface SdTypeOption {
	value: string;
	label: string;
}

interface CommissionRow {
	sdType: string;
	sdTypeLabel: string;
	salesNo: string;
	name: string;
	address: string;
	bank: string;
	accName: string;
	accNo: string;
	amount: number;
	incentive: boolean;
	incentiveLocked: boolean;
	canEditDelete: boolean;
}

interface AccountRow {
	bankDesc: string;
	bankBranch: string;
	accName: string;
	accNo: string;
	isDefault: boolean;
	amount: number | null;
	checked: boolean;
	amountDisabled: boolean;
}

interface CommissionView {
	blocked: boolean;
	blockMessage: string;
	rows: CommissionRow[];
	totalCommission: number;
	totalIncentive: number;
	remainingIncentive: number;
	dealer: { name: string; no: string; address: string };
	sdTypeOptions: SdTypeOption[];
}

function fmt(value: number | null | undefined) {
	if (value === undefined || value === null || Number.isNaN(value)) return "0";
	const digits = Math.round(value).toString();
	return digits.replace(/\B(?=(\d{3})+(?!\d))/g, ",").replace(/^-,/, "-");
}

export default function CAMFinancingCommissionPage({ apless, applNo, onSaved }: CAMFinancingCommissionPageProps) {
	const [loading, setLoading] = useState(true);
	const [loadError, setLoadError] = useState("");
	const [view, setView] = useState<CommissionView | null>(null);

	const [sdType, setSdType] = useState("");
	const [salesNo, setSalesNo] = useState("");
	const [name, setName] = useState("");
	const [address, setAddress] = useState("");
	const [maxFee, setMaxFee] = useState(0);
	const [accountRows, setAccountRows] = useState<AccountRow[]>([]);
	const [pickerOpen, setPickerOpen] = useState(false);
	const [dealerNpwpMessage, setDealerNpwpMessage] = useState("");

	const [saving, setSaving] = useState(false);
	const [saveErrors, setSaveErrors] = useState<string[]>([]);
	const [editTarget, setEditTarget] = useState<{ salesNo: string; sdType: string; accNo: string } | null>(null);

	const load = useCallback(async () => {
		setLoading(true);
		setLoadError("");
		try {
			const res = await api.get("/CAM/EditIndex/commission", { params: { apless, applno: applNo } });
			if (res.data.blocked) {
				setLoadError(res.data.message || "This application cannot be edited right now.");
				return;
			}
			setView(res.data);
		} catch {
			setLoadError("Failed to load Commission. Please try again.");
		} finally {
			setLoading(false);
		}
	}, [apless, applNo]);

	useEffect(() => {
		load();
	}, [load]);

	const resetForm = () => {
		setSdType("");
		setSalesNo("");
		setName("");
		setAddress("");
		setMaxFee(0);
		setAccountRows([]);
		setDealerNpwpMessage("");
	};

	const loadAccountsAndMaxFee = async (nextSdType: string, nextSalesNo: string) => {
		const [accountsRes, maxFeeRes] = await Promise.all([
			api.get("/CAM/EditIndex/commission/accounts", { params: { salesNo: nextSalesNo, applno: applNo, sdType: nextSdType } }),
			api.get("/CAM/EditIndex/commission/max-fee", { params: { applno: applNo, salesNo: nextSalesNo, sdType: nextSdType, variant: "detail" } }),
		]);
		setAccountRows(accountsRes.data.rows || []);
		setMaxFee(maxFeeRes.data.maxFee || 0);
	};

	const handleSdTypeChange = async (value: string) => {
		setSdType(value);
		setSaveErrors([]);
		if (value === "D" && view) {
			setName(view.dealer.name);
			setSalesNo(view.dealer.no);
			setAddress(view.dealer.address);
			await loadAccountsAndMaxFee("D", view.dealer.no);
			const check = await api.get("/CAM/EditIndex/commission/dealer-check", { params: { salesNo: view.dealer.no } });
			setDealerNpwpMessage(check.data.valid ? "" : check.data.message);
		} else if (value === "S") {
			setName("");
			setSalesNo("");
			setAddress("");
			setAccountRows([]);
			setPickerOpen(true);
		}
	};

	const handlePickerSelect = async (result: SalesPickResult) => {
		setPickerOpen(false);
		setName(result.name);
		setSalesNo(result.salesNo);
		setAddress(result.address);
		await loadAccountsAndMaxFee("S", result.salesNo);
	};

	const updateAccountRow = (accNo: string, patch: Partial<AccountRow>) => {
		setAccountRows(rows => rows.map(r => (r.accNo === accNo ? { ...r, ...patch } : r)));
	};

	const handleSave = async () => {
		setSaving(true);
		setSaveErrors([]);
		try {
			const res = await api.post("/CAM/EditIndex/commission/save", {
				apless, applno: applNo, sdType, salesNo,
				category: sdType === "D" ? "Dealer" : "Sales",
				cekInsen: "1",
				rows: accountRows.map(r => ({
					accNo: r.accNo, accName: r.accName, accBank: null, accBankBranch: r.bankBranch,
					checked: r.checked, amount: r.amount,
				})),
			});
			if (res.data.success) {
				resetForm();
				await load();
			} else {
				setSaveErrors(String(res.data.message || "Please try again.").split("<br>").filter(Boolean));
			}
		} finally {
			setSaving(false);
		}
	};

	const handleClear = () => resetForm();

	const handleDelete = async (row: CommissionRow) => {
		await api.post("/CAM/EditIndex/commission/delete", {
			applno: applNo, salesNo: row.salesNo, accNo: row.accNo, feeSales: row.amount, variant: "detail",
		});
		await load();
	};

	const handleToggleIncentive = async (row: CommissionRow) => {
		if (row.incentiveLocked) return;
		await api.post("/CAM/EditIndex/commission/toggle-incentive", {
			salesNo: row.salesNo, applno: applNo, currentIncentive: row.incentive ? "1" : "0",
		});
		await load();
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
			<h2 className="text-base font-semibold text-slate-700">Commission</h2>

			{!view.blocked && (
				<div className="space-y-4">
					<div className="space-y-1">
						<label className="block text-sm font-medium text-slate-600">Commission Type *</label>
						<label className="flex items-center gap-2 text-sm text-slate-700">
							<input type="radio" checked readOnly />
							Incentive
						</label>
					</div>

					<div className="space-y-1">
						<label className="block text-sm font-medium text-slate-600">Commission To *</label>
						<select
							value={sdType}
							onChange={e => handleSdTypeChange(e.target.value)}
							className="w-full max-w-xs rounded-lg border border-slate-300 p-2 text-sm"
						>
							<option value="">Select</option>
							{view.sdTypeOptions.map(opt => (
								<option key={opt.value} value={opt.value}>
									{opt.label}
								</option>
							))}
						</select>
					</div>

					<div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
						<div className="space-y-1">
							<label className="block text-sm font-medium text-slate-600">Commission Receiver Name *</label>
							<input type="text" value={name} readOnly className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2 text-sm" />
						</div>
						<div className="space-y-1">
							<label className="block text-sm font-medium text-slate-600">Address</label>
							<textarea value={address} readOnly className="w-full rounded-lg border border-slate-200 bg-slate-50 p-2 text-sm" />
						</div>
					</div>

					{dealerNpwpMessage && <p className="text-sm text-red-600">{dealerNpwpMessage}</p>}

					<div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
						<div className="space-y-1">
							<label className="block text-sm font-medium text-slate-600">Sisa Incentive</label>
							<input
								type="text"
								readOnly
								value={fmt(view.remainingIncentive)}
								className="w-full max-w-[160px] rounded-lg border border-slate-200 bg-slate-50 p-2 text-right text-sm"
							/>
						</div>
						<div className="space-y-1">
							<label className="block text-sm font-medium text-slate-600">Commission To be Paid</label>
							<input
								type="text"
								readOnly
								value={fmt(maxFee)}
								className="w-full max-w-[160px] rounded-lg border border-slate-200 bg-slate-50 p-2 text-right text-sm"
							/>
						</div>
					</div>

					{accountRows.length > 0 && (
						<div className="space-y-2">
							<p className="text-sm font-medium text-slate-600">Payment To</p>
							<div className="overflow-x-auto">
								<table className="w-full min-w-[700px] border-collapse border border-slate-200 text-sm">
									<thead>
										<tr className="border-b border-slate-200 bg-slate-50 text-left text-slate-500">
											<th className="border border-slate-200 p-2">No</th>
											<th className="border border-slate-200 p-2">Bank Name *</th>
											<th className="border border-slate-200 p-2">Bank Branch *</th>
											<th className="border border-slate-200 p-2">Account Name *</th>
											<th className="border border-slate-200 p-2">Account Number *</th>
											<th className="border border-slate-200 p-2">Gross Commission *</th>
											<th className="border border-slate-200 p-2">Preference *</th>
										</tr>
									</thead>
									<tbody>
										{accountRows.map((r, i) => (
											<tr key={r.accNo}>
												<td className="border border-slate-200 p-2 text-center">{i + 1}</td>
												<td className="border border-slate-200 p-2">{r.bankDesc}</td>
												<td className="border border-slate-200 p-2">{r.bankBranch}</td>
												<td className="border border-slate-200 p-2">{r.accName}</td>
												<td className="border border-slate-200 p-2">{r.accNo}</td>
												<td className="border border-slate-200 p-2">
													<input
														type="text"
														disabled={r.amountDisabled}
														value={r.amount ?? ""}
														onChange={e =>
															updateAccountRow(r.accNo, {
																amount: e.target.value === "" ? null : Number(e.target.value.replace(/[^\d.]/g, "")) || 0,
															})
														}
														className="w-32 rounded-lg border border-slate-300 p-1.5 text-right text-sm disabled:bg-slate-100"
													/>
												</td>
												<td className="border border-slate-200 p-2 text-center">
													<input
														type="checkbox"
														checked={r.checked}
														onChange={e => updateAccountRow(r.accNo, { checked: e.target.checked })}
													/>
												</td>
											</tr>
										))}
									</tbody>
								</table>
							</div>
						</div>
					)}

					{saveErrors.length > 0 && (
						<div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
							{saveErrors.map((e, i) => (
								<p key={i}>{e}</p>
							))}
						</div>
					)}

					<div className="flex gap-3">
						<button
							type="button"
							onClick={handleSave}
							disabled={saving || !sdType || !salesNo}
							className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:opacity-50"
						>
							{saving ? "Saving…" : "Save"}
						</button>
						<button
							type="button"
							onClick={handleClear}
							className="rounded-lg bg-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-300"
						>
							Clear
						</button>
					</div>
				</div>
			)}

			<div className="space-y-2">
				<div className="overflow-x-auto">
					<table className="w-full min-w-[900px] border-collapse text-sm">
						<thead>
							<tr className="border-b border-slate-200 bg-slate-50 text-left text-slate-500">
								<th className="p-2">Commission To</th>
								<th className="p-2">Name</th>
								<th className="p-2">Address</th>
								<th className="p-2">Bank Name</th>
								<th className="p-2">Account Name</th>
								<th className="p-2">Account Number</th>
								<th className="p-2">Gross Commission</th>
								<th className="p-2">Incentive</th>
								<th className="p-2"></th>
							</tr>
						</thead>
						<tbody>
							{view.rows.map((r, i) => (
								<tr key={`${r.salesNo}-${r.accNo}-${i}`} className="border-b border-slate-100">
									<td className="p-2">{r.sdTypeLabel}</td>
									<td className="p-2">{r.name}</td>
									<td className="p-2">{r.address}</td>
									<td className="p-2">{r.bank}</td>
									<td className="p-2">{r.accName}</td>
									<td className="p-2">{r.accNo}</td>
									<td className="p-2 text-right">{fmt(r.amount)}</td>
									<td className="p-2 text-center">
										<input
											type="checkbox"
											checked={r.incentive}
											disabled={r.incentiveLocked}
											onChange={() => handleToggleIncentive(r)}
										/>
									</td>
									<td className="p-2 text-center">
										{r.canEditDelete && (
											<div className="flex justify-center gap-2">
												<button
													type="button"
													title="Edit"
													onClick={() => setEditTarget({ salesNo: r.salesNo, sdType: r.sdType, accNo: r.accNo })}
													className="text-blue-600 hover:underline"
												>
													Edit
												</button>
												<button
													type="button"
													title="Delete"
													onClick={() => handleDelete(r)}
													className="text-red-600 hover:underline"
												>
													Delete
												</button>
											</div>
										)}
									</td>
								</tr>
							))}
							<tr className="border-t border-slate-300 bg-slate-50 font-semibold">
								<td className="p-2" colSpan={6}>
									Total
								</td>
								<td className="p-2 text-right">{fmt(view.totalCommission)}</td>
								<td className="p-2" colSpan={2}></td>
							</tr>
							<tr className="bg-slate-50 font-semibold">
								<td className="p-2" colSpan={6}>
									Total Incentive
								</td>
								<td className="p-2 text-right">{fmt(view.totalIncentive)}</td>
								<td className="p-2" colSpan={2}></td>
							</tr>
							<tr className="bg-slate-50 font-semibold">
								<td className="p-2" colSpan={6}>
									Sisa Incentive
								</td>
								<td className="p-2 text-right">{fmt(view.remainingIncentive)}</td>
								<td className="p-2" colSpan={2}></td>
							</tr>
						</tbody>
					</table>
				</div>
			</div>

			{view.blockMessage && <p className="text-sm text-red-600">{view.blockMessage}</p>}

			<div className="flex justify-end pt-2">
				<button
					type="button"
					onClick={() => onSaved({ apless, applno: applNo })}
					className="rounded-lg bg-orange-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-orange-600"
				>
					Next
				</button>
			</div>

			<SalesDealerPickerModal
				open={pickerOpen}
				comType="1"
				onClose={() => setPickerOpen(false)}
				onSelect={handlePickerSelect}
			/>

			{editTarget && (
				<EditCommissionModal
					open
					applNo={applNo}
					salesNo={editTarget.salesNo}
					sdType={editTarget.sdType}
					accNo={editTarget.accNo}
					onClose={() => setEditTarget(null)}
					onSaved={load}
				/>
			)}
		</div>
	);
}
