import React, { useCallback, useEffect, useState } from "react";
import api from "../../../../../api/axiosInstance";

export interface CAMEquipmentCrossCollateralPageProps {
	apless: string;
	applNo: string;
	onSaved: (result: { apless: string; applno: string }) => void;
}

interface CrossCollateralRow {
	leaseNo: string;
	customerName: string;
	brand: string;
	type: string;
	installmentPaid: number | null;
	installmentTenor: number | null;
	crossCollateral: boolean;
	remark: string;
}

export default function CAMEquipmentCrossCollateralPage({ apless, applNo, onSaved }: CAMEquipmentCrossCollateralPageProps) {
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState("");
	const [rows, setRows] = useState<CrossCollateralRow[]>([]);
	const [saving, setSaving] = useState(false);
	const [saveError, setSaveError] = useState("");

	const load = useCallback(async () => {
		setLoading(true);
		setError("");
		try {
			const res = await api.get("/CAM/EditIndex/cross-collateral", { params: { apless, applno: applNo } });
			setRows(res.data.rows || []);
		} catch {
			setError("Failed to load cross collateral data. Please try again.");
		} finally {
			setLoading(false);
		}
	}, [apless, applNo]);

	useEffect(() => {
		load();
	}, [load]);

	const toggleRow = (leaseNo: string) =>
		setRows(prev => prev.map(r => (r.leaseNo === leaseNo ? { ...r, crossCollateral: !r.crossCollateral } : r)));

	const handleNext = async () => {
		setSaving(true);
		setSaveError("");
		try {
			const res = await api.post("/CAM/EditIndex/cross-collateral/next", {
				apless,
				applno: applNo,
				rows: rows.map(r => ({ leaseNo: r.leaseNo, crossCollateral: r.crossCollateral })),
			});
			if (res.data.success) {
				onSaved({ apless, applno: applNo });
			} else {
				setSaveError(res.data.message || "Save failed.");
			}
		} catch (err: any) {
			setSaveError(err?.response?.data?.message || "Save failed. Please try again.");
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

	return (
		<div className="space-y-4 rounded-2xl bg-white p-6 shadow">
			<h2 className="text-base font-semibold text-slate-700">Cross Collateral</h2>
			{error && <p className="text-sm text-red-600">{error}</p>}

			<div className="overflow-x-auto rounded-lg border border-slate-200">
				<table className="w-full min-w-[820px] border-collapse text-sm">
					<thead>
						<tr className="bg-slate-100 text-center text-xs font-medium uppercase tracking-wide text-slate-500">
							<th className="px-3 py-2 w-12">No.</th>
							<th className="px-3 py-2">Customer Name</th>
							<th className="px-3 py-2">Contract Number</th>
							<th className="px-3 py-2">Brand / Type</th>
							<th className="px-3 py-2">Installment</th>
							<th className="px-3 py-2 w-32">Cross Collateral</th>
							<th className="px-3 py-2">Remarks</th>
						</tr>
					</thead>
					<tbody>
						{rows.length === 0 ? (
							<tr>
								<td colSpan={7} className="px-3 py-6 text-center text-sm text-slate-400">
									No other contracts found for this customer.
								</td>
							</tr>
						) : (
							rows.map((row, idx) => (
								<tr key={row.leaseNo} className={idx % 2 === 0 ? "bg-slate-50" : "bg-white"}>
									<td className="px-3 py-2 text-center">{idx + 1}</td>
									<td className="px-3 py-2">{row.customerName}</td>
									<td className="px-3 py-2 text-center">{row.leaseNo}</td>
									<td className="px-3 py-2 text-center">
										{row.brand} / {row.type}
									</td>
									<td className="px-3 py-2 text-center">
										{row.installmentPaid ?? "-"} / {row.installmentTenor ?? "-"}
									</td>
									<td className="px-3 py-2 text-center">
										<input
											type="checkbox"
											checked={row.crossCollateral}
											onChange={() => toggleRow(row.leaseNo)}
										/>
									</td>
									<td className="px-3 py-2">{row.remark || ""}</td>
								</tr>
							))
						)}
					</tbody>
				</table>
			</div>

			{saveError && <p className="text-sm text-red-600">{saveError}</p>}

			<div className="flex justify-end pt-2">
				<button
					type="button"
					onClick={handleNext}
					disabled={saving}
					className="rounded-lg bg-orange-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-orange-600 disabled:opacity-50"
				>
					{saving ? "Saving…" : "Next"}
				</button>
			</div>
		</div>
	);
}