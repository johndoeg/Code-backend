import { useCallback, useEffect, useState } from "react";
import api from "../../../../../api/axiosInstance";
import { CurrencyInput, SelectInput } from "./FinancingFormControls";

export interface CAMFinancingSubsidyPanelProps {
	applNo: string;
	includeSurveyFee2Option: boolean;
	onClose: () => void;
	onChanged: () => void;
}

interface SubsidyRow {
	subsidyType: string;
	subsidyTypeLabel: string;
	amountType: string;
	amountTypeLabel: string;
	amount: number;
	deletable: boolean;
}

const AMOUNT_TYPE_OPTIONS: [string, string][] = [
	["1", "For DP"],
	["2", "For Installment"],
	["3", "For Insurance"],
	["4", "For Survey Fee 1"],
	["7", "For Survey Fee 2"],
	["5", "For Provision Fee"],
	["6", "For Interest"],
];

const SUBSIDY_TYPE_CODES: Record<string, string> = {
	"Subsidy From Dealer": "1",
	"Subsidy From APM": "2",
	"Incentive From APM": "3",
};

export default function CAMFinancingSubsidyPanel({
	applNo,
	includeSurveyFee2Option,
	onClose,
	onChanged,
}: CAMFinancingSubsidyPanelProps) {
	const [grid, setGrid] = useState<SubsidyRow[]>([]);
	const [dealerApmOptions, setDealerApmOptions] = useState<string[]>(["Subsidy From Dealer"]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState("");
	const [dealer, setDealer] = useState("");
	const [dpinstal, setDpinstal] = useState("");
	const [amount, setAmount] = useState("");
	const [saving, setSaving] = useState(false);

	const load = useCallback(async () => {
		setLoading(true);
		setError("");
		try {
			const res = await api.get("/CAM/EditIndex/fin-financing/subsidies", { params: { applno: applNo } });
			setGrid(res.data.grid);
			setDealerApmOptions(res.data.dealerApmOptions);
		} catch {
			setError("Failed to load subsidy list.");
		} finally {
			setLoading(false);
		}
	}, [applNo]);

	useEffect(() => {
		load();
	}, [load]);

	useEffect(() => {
		const handleKeyDown = (e: KeyboardEvent) => {
			if (e.key === "Escape") onClose();
		};
		window.addEventListener("keydown", handleKeyDown);
		return () => window.removeEventListener("keydown", handleKeyDown);
	}, [onClose]);

	const amountTypeOptions = includeSurveyFee2Option
		? AMOUNT_TYPE_OPTIONS
		: AMOUNT_TYPE_OPTIONS.filter(([code]) => code !== "7");

	const handleAdd = async () => {
		if (!dealer || !dpinstal) {
			setError("Please choose Dealer/APM and Payment For what");
			return;
		}
		setSaving(true);
		setError("");
		try {
			await api.post("/CAM/EditIndex/fin-financing/subsidies", {
				applno: applNo,
				dealer: SUBSIDY_TYPE_CODES[dealer] ?? dealer,
				dpinstal,
				amount: parseFloat(amount.replace(/,/g, "")) || 0,
			});
			setAmount("");
			await load();
			onChanged();
		} catch (err: any) {
			setError(err?.response?.data?.error || "Failed to add.");
		} finally {
			setSaving(false);
		}
	};

	const handleDelete = async (row: SubsidyRow) => {
		try {
			await api.delete("/CAM/EditIndex/fin-financing/subsidies", {
				data: {
					applno: applNo,
					subsidyType: row.subsidyType,
					amountType: row.amountType,
					amount: row.amount,
				},
			});
			await load();
			onChanged();
		} catch {
			setError("Failed to delete.");
		}
	};

	return (
		<div
			className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
			onClick={onClose}
		>
			<div
				className="w-full max-w-2xl rounded-2xl bg-white p-6 shadow-xl"
				onClick={(e) => e.stopPropagation()}
			>
				<div className="mb-4 flex items-center justify-between">
					<h3 className="text-base font-semibold text-slate-700">Input Subsidy and Refund</h3>
					<button type="button" onClick={onClose} className="text-slate-400 hover:text-slate-600">
						✕
					</button>
				</div>

				<div className="mb-4 flex flex-wrap items-end gap-3">
					<div className="w-56">
						<label className="mb-1 block text-xs text-slate-500">Dealer / APM</label>
						<SelectInput value={dealer} onChange={setDealer} placeholder="Select">
							{dealerApmOptions.map((opt) => (
								<option key={opt} value={opt}>{opt}</option>
							))}
						</SelectInput>
					</div>
					<div className="w-56">
						<label className="mb-1 block text-xs text-slate-500">Payment For</label>
						<SelectInput value={dpinstal} onChange={setDpinstal} placeholder="Select">
							{amountTypeOptions.map(([code, label]) => (
								<option key={code} value={code}>{label}</option>
							))}
						</SelectInput>
					</div>
					<div className="w-32">
						<label className="mb-1 block text-xs text-slate-500">Amount</label>
						<CurrencyInput value={amount} onChange={setAmount} />
					</div>
					<button
						type="button"
						onClick={handleAdd}
						disabled={saving}
						className="rounded-lg bg-orange-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-orange-600 disabled:opacity-50"
					>
						{saving ? "Adding…" : "Add"}
					</button>
				</div>

				{error && <p className="mb-3 text-sm text-red-600">{error}</p>}

				<div className="overflow-hidden rounded-lg border border-slate-200">
					<table className="w-full text-sm">
						<thead className="bg-orange-500 text-white">
							<tr>
								<th className="px-3 py-2 text-left">Subsidy / Refund / Incentive</th>
								<th className="px-3 py-2 text-left">Payment For</th>
								<th className="px-3 py-2 text-right">Amount</th>
								<th className="px-3 py-2 text-center">Action</th>
							</tr>
						</thead>
						<tbody>
							{loading ? (
								<tr><td colSpan={4} className="px-3 py-4 text-center text-slate-400">Loading…</td></tr>
							) : grid.length === 0 ? (
								<tr><td colSpan={4} className="px-3 py-4 text-center text-slate-400">No entries yet.</td></tr>
							) : (
								grid.map((row, idx) => (
									<tr key={`${row.subsidyType}-${row.amountType}-${idx}`} className="border-t border-slate-100">
										<td className="px-3 py-2 font-medium">{row.subsidyTypeLabel}</td>
										<td className="px-3 py-2">For {row.amountTypeLabel.replace("For ", "")}</td>
										<td className="px-3 py-2 text-right">{row.amount.toLocaleString()}</td>
										<td className="px-3 py-2 text-center">
											{row.deletable && (
												<button
													type="button"
													onClick={() => handleDelete(row)}
													className="rounded-md bg-red-600 px-2 py-1 text-xs font-medium text-white hover:bg-red-700"
												>
													Delete
												</button>
											)}
										</td>
									</tr>
								))
							)}
						</tbody>
					</table>
				</div>

				<div className="mt-4 flex justify-end">
					<button
						type="button"
						onClick={onClose}
						className="rounded-lg bg-slate-700 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
					>
						Close
					</button>
				</div>
			</div>
		</div>
	);
}