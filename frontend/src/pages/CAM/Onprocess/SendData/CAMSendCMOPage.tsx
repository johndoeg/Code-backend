import React, { useEffect, useState } from "react";
import api from '../../../../api/axiosInstance';

interface CamSendCmoItem {
	applNo: string;
	strRevisi: string;
	lesseeName: string;
	cmoUsername: string;
}

interface ApproverOption {
	value: string;
	label: string;
}

interface GpsVendorOption {
	value: string;
	label: string;
}

interface PurposeOption {
	value: string;
	label: string;
}

interface InitData {
	ketMultiple: string;
	items: CamSendCmoItem[];
	watchlistMessage: string | null;
	approverOptions: ApproverOption[];
	gpsVendorOptions: GpsVendorOption[];
	showPurposeOfFinanceEdit: boolean;
	purposeOfFinanceValue: string | null;
	purposeOfFinanceOptions: PurposeOption[];
	purposeOfFinanceNotice: string | null;
	purposeOfFinanceCondition: string | null;
	totalNetFinanceExternal: number;
	lesseeType: string | null;
}

interface CAMSendCMOPageProps {
	applNos: string[];
	multiple: boolean;
	onDone: () => void;
}

const formatIDR = (n: number) => new Intl.NumberFormat("id-ID").format(n);

const CAMSendCMOPage: React.FC<CAMSendCMOPageProps> = ({ applNos, multiple, onDone }) => {
	const [data, setData] = useState<InitData | null>(null);
	const [loading, setLoading] = useState(true);
	const [submitting, setSubmitting] = useState(false);

	const [approval, setApproval] = useState("");
	const [comment, setComment] = useState("");
	const [redCode, setRedCode] = useState(false);
	const [gpsVendor, setGpsVendor] = useState("");
	const [purposeOfFinance, setPurposeOfFinance] = useState("");

	useEffect(() => {
		let cancelled = false;

		const load = async () => {
			setLoading(true);
			try {
				const res = await api.get('/CAM/Approval/SendCMO/api/init', {
					params: { appl_nos: applNos.join(","), multiple: multiple ? "1" : "0" },
				});
				if (cancelled) return;

				if (res.data.blocking) {
					alert(res.data.message);
					onDone();
					return;
				}

				const init: InitData = res.data;
				setData(init);
				setApproval(init.approverOptions[0]?.value ?? "");
				setPurposeOfFinance(init.purposeOfFinanceValue ?? "");
			} catch {
				if (!cancelled) {
					alert("Failed to load approval form. Please try again.");
					onDone();
				}
			} finally {
				if (!cancelled) setLoading(false);
			}
		};

		load();
		return () => {
			cancelled = true;
		};
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [applNos, multiple]);

	const requiresYearlyAssessmentConfirm = () => {
		if (!data) return true;
		const purpofinc = data.purposeOfFinanceCondition;
		if (purpofinc === "3" || purpofinc === "4") {
			if (data.totalNetFinanceExternal >= 5_000_000_000) {
				return window.confirm(
					`Total pembiayaan dari CAM ini \u2265 Rp 5.000.000.000\nsehingga cabang wajib melakukan Individual Assessment setiap tahun.\nLanjutkan?`
				);
			}
		}
		return true;
	};

	const handleConfirm = async () => {
		if (!approval) {
			alert("Please choose an approver.");
			return;
		}
		if (redCode && !gpsVendor) {
			alert("Please select GPS Vendor");
			return;
		}
		if (!requiresYearlyAssessmentConfirm()) return;

		setSubmitting(true);
		try {
			const res = await api.post('/CAM/Approval/SendCMO/api/confirm', {
				appl_nos: applNos,
				multiple,
				approval,
				comment,
				redCode,
				gpsVendor,
				purposeOfFinance,
			});
			alert(res.data.message);
			onDone();
		} catch {
			alert("Failed to submit approval. Please try again.");
			onDone();
		} finally {
			setSubmitting(false);
		}
	};

	return (
		<div className="flex max-h-[90vh] w-[95vw] max-w-3xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
			<div className="min-h-0 flex-1 overflow-y-auto p-6">
				<h2 className="text-2xl font-bold text-slate-800 mb-1">1st Approval</h2>
				{data && (
					<p className="text-sm text-slate-500 mb-6">Status: {data.ketMultiple}</p>
				)}

				{loading ? (
					<div className="flex justify-center py-14">
						<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
					</div>
				) : data ? (
					<>
						<div className="overflow-x-auto rounded-xl border border-slate-200 mb-6">
							<table className="w-full text-sm">
								<thead>
									<tr className="bg-gradient-to-r from-slate-100 to-slate-200">
										<th className="py-3 px-4 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">CAM No.</th>
										<th className="py-3 px-4 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">Customer Name</th>
										<th className="py-3 px-4 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider">CMO</th>
									</tr>
								</thead>
								<tbody className="divide-y divide-slate-100">
									{data.items.map((item, idx) => (
										<tr key={item.applNo || idx} className={idx % 2 === 0 ? "bg-white" : "bg-slate-50"}>
											<td className="py-3 px-4">{item.applNo}{item.strRevisi}</td>
											<td className="py-3 px-4">{item.lesseeName}</td>
											<td className="py-3 px-4">{item.cmoUsername}</td>
										</tr>
									))}
								</tbody>
							</table>
						</div>

						<h3 className="text-lg font-bold text-slate-800 mb-4">Approval Form</h3>
						<div className="space-y-5">
							<div className="flex items-center gap-3">
								<label className="w-40 text-sm font-medium text-slate-700">Red Code</label>
								<input
									type="checkbox"
									checked={redCode}
									onChange={e => setRedCode(e.target.checked)}
									className="w-4 h-4 accent-blue-600"
								/>
								<select
									value={gpsVendor}
									onChange={e => setGpsVendor(e.target.value)}
									className="border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
								>
									<option value="">Select</option>
									{data.gpsVendorOptions.map(v => (
										<option key={v.value} value={v.value}>{v.label}</option>
									))}
								</select>
							</div>

							{data.showPurposeOfFinanceEdit && (
								<div className="flex items-start gap-3">
									<label className="w-40 text-sm font-medium text-slate-700 pt-2">Purpose of Finance</label>
									<div>
										<select
											value={purposeOfFinance}
											disabled
											className="border border-slate-300 rounded-lg px-3 py-2 text-sm w-56 bg-slate-100 text-slate-500"
										>
											<option value="">Select</option>
											{data.purposeOfFinanceOptions.map(o => (
												<option key={o.value} value={o.value}>{o.label}</option>
											))}
										</select>
										{data.purposeOfFinanceNotice && (
											<p className="text-red-600 italic text-sm mt-1">{data.purposeOfFinanceNotice}</p>
										)}
									</div>
								</div>
							)}

							<div className="flex items-center gap-3">
								<label className="w-40 text-sm font-medium text-slate-700">1st Approval</label>
								<div>
									<select
										value={approval}
										onChange={e => setApproval(e.target.value)}
										className="border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 min-w-[220px]"
									>
										{data.approverOptions.length === 0 && <option value="">No approver available</option>}
										{data.approverOptions.map(a => (
											<option key={a.value} value={a.value}>{a.label}</option>
										))}
									</select>
									{data.watchlistMessage && (
										<p className="text-red-600 text-sm mt-1">{data.watchlistMessage}</p>
									)}
								</div>
							</div>

							<div className="flex items-start gap-3">
								<label className="w-40 text-sm font-medium text-slate-700 pt-2">Comment</label>
								<textarea
									value={comment}
									onChange={e => setComment(e.target.value)}
									maxLength={5000}
									rows={4}
									className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
								/>
							</div>

							{data.totalNetFinanceExternal > 0 && (
								<p className="text-xs text-slate-400">
									Net Finance (external): Rp {formatIDR(data.totalNetFinanceExternal)}
								</p>
							)}
						</div>
					</>
				) : null}
			</div>

			{!loading && data && (
				<div className="flex justify-end gap-3 border-t border-slate-200 p-4">
					<button
						onClick={onDone}
						className="px-4 py-2 border border-slate-300 rounded-lg text-slate-600 hover:bg-slate-50 text-sm"
					>
						Cancel
					</button>
					<button
						onClick={handleConfirm}
						disabled={submitting}
						className="px-4 py-2 bg-orange-500 hover:bg-orange-600 disabled:bg-slate-300 text-white rounded-lg text-sm font-medium"
					>
						{submitting ? "Submitting…" : "Confirm"}
					</button>
				</div>
			)}
		</div>
	);
};

export default CAMSendCMOPage;