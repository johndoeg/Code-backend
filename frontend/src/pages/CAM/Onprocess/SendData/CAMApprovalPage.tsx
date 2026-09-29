import React, { useCallback, useEffect, useState } from "react";
import api from '../../../../api/axiosInstance';

interface OptionItem {
	value: string;
	label: string;
}

interface HistoryItem {
	date: string;
	approvedBy: string;
	statusLabel: string;
	recommendation: string;
	comment: string;
	lowRecommendation: boolean;
}

interface WatchlistInfo {
	listed: boolean;
	description?: string;
	byLabel?: string;
	by?: string;
	dateLabel?: string;
	date?: string;
}

interface CAMApprovalPageData {
	applNo: string;
	applNoDisplay: string;
	isMultiple: boolean;
	multipleApplNos: string[];
	lesseeName: string;
	cmoName: string | null;
	accessLevel: string;
	isCmo: boolean;
	allowRejectToWatchlist: boolean;
	showCreditRecommendation: boolean;
	showSurveyIndependent: boolean;
	surveyIndependentDisabled: boolean;
	resultIndependentDisabled: boolean;
	strength: string;
	weakness: string;
	tbo: string;
	isiSurv: string;
	isiResult: string;
	resultIndependentOptions: OptionItem[];
	redCodeChecked: boolean;
	gpsVendor: string;
	gpsVendorOptions: OptionItem[];
	approverOptions: OptionItem[];
	warningMessage: string | null;
	submitDisabled: boolean;
	alreadySentToAdmin: { sentAt: string } | null;
	watchlist: WatchlistInfo;
	history: HistoryItem[];
	lockedBy: string | null;
	rejectedMessage: string | null;
	withdrawnBy: string | null;
	completed: boolean;
	purposeRequiresYearlyAssessment: boolean;
	totalNetFinanceExternal: number | null;
	totalOutstanding: number;
}

interface DecisionResponse {
	success: boolean;
	message?: string;
	validationErrors?: string[];
}

interface CAMApprovalPageProps {
	applNo: string;
	onClose?: () => void;
}

const INDIVIDUAL_ASSESSMENT_THRESHOLD = 3_000_000_000;

const CAMApprovalPage: React.FC<CAMApprovalPageProps> = ({ applNo, onClose }) => {
	const [data, setData] = useState<CAMApprovalPageData | null>(null);
	const [loading, setLoading] = useState(true);
	const [submitting, setSubmitting] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [validationErrors, setValidationErrors] = useState<string[]>([]);

	const [approvalSts, setApprovalSts] = useState<"A" | "R" | "RW">("A");
	const [nextApprover, setNextApprover] = useState("");
	const [comment, setComment] = useState("");
	const [notRecommend, setNotRecommend] = useState(false);
	const [strength, setStrength] = useState("");
	const [weakness, setWeakness] = useState("");
	const [tbo, setTbo] = useState("");
	const [isiSurv, setIsiSurv] = useState("");
	const [isiResult, setIsiResult] = useState("");
	const [redCode, setRedCode] = useState(false);
	const [gpsVendor, setGpsVendor] = useState("");

	const fetchData = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			const response = await api.get(`/CAM/Approval/api/${applNo}`);
			const camData: CAMApprovalPageData = response.data;

			if (camData.withdrawnBy) {
				alert(`This Cam has been withdrawn by ${camData.withdrawnBy}`);
				onClose?.();
				return;
			}

			setData(camData);
			setNextApprover(camData.approverOptions[0]?.value ?? "");
			setStrength(camData.strength);
			setWeakness(camData.weakness);
			setTbo(camData.tbo);
			setIsiSurv(camData.isiSurv);
			setIsiResult(camData.isiResult);
			setRedCode(camData.redCodeChecked);
			setGpsVendor(camData.gpsVendor);
		} catch (err) {
			setError("Failed to load CAM approval data. Please try again.");
			console.error("API Error:", err);
		} finally {
			setLoading(false);
		}
	}, [applNo, onClose]);

	useEffect(() => {
		fetchData();
	}, [fetchData]);

	const handleApprovalStsChange = (value: "A" | "R" | "RW") => {
		setApprovalSts(value);
	};

	const surveyRequired = data ? !["CMO", "BM", "CMH", "NCH"].includes(data.accessLevel) : false;

	const gpsVendorCheckApplies = data ? data.isCmo || data.accessLevel === "CMH" : false;

	const handleSubmit = async () => {
		if (!data) return;

		let finalApproval: "A" | "R" | "RW" = data.isCmo ? "A" : approvalSts;

		if (finalApproval === "A") {
			if (
				data.isCmo &&
				data.purposeRequiresYearlyAssessment &&
				(data.totalNetFinanceExternal ?? 0) >= INDIVIDUAL_ASSESSMENT_THRESHOLD
			) {
				const proceed = window.confirm(
					"Total pembiayaan dari CAM ini \u2265 Rp 3.000.000.000\n" +
					"sehingga cabang wajib melakukan Individual Assessment setiap tahun.\n" +
					"Lanjutkan?"
				);
				if (!proceed) return;
			}

			if (gpsVendorCheckApplies && redCode && !gpsVendor) {
				alert("Please select GPS Vendor");
				return;
			}

			if (data.showSurveyIndependent && surveyRequired) {
				if (isiSurv === "") {
					alert("Survey Independent can`t be empty!");
					return;
				}
				if (isiSurv === "1" && isiResult === "") {
					alert("Result Survey Independent can`t be empty!");
					return;
				}
			}
		} else if (finalApproval === "RW") {
			const proceed = window.confirm("Are you sure Reject this CAM to Watchlist?");
			if (!proceed) return;
		} else {
			const proceed = window.confirm("Are you sure to reject this CAM?");
			if (!proceed) return;
		}

		setSubmitting(true);
		setError(null);
		setValidationErrors([]);
		try {
			const response = await api.post<DecisionResponse>(
				`/CAM/Approval/api/${applNo}/decision`,
				{
					approvalSts: finalApproval,
					nextApprover,
					comment,
					notRecommend,
					strength,
					weakness,
					tbo,
					isiSurv,
					isiResult,
					redCode,
					gpsVendor,
					sendToAdmin: false,
				}
			);

			if (response.data.success) {
				if (response.data.message) alert(response.data.message);
				onClose?.();
			} else if (response.data.validationErrors?.length) {
				setValidationErrors(response.data.validationErrors);
			} else {
				setError(response.data.message || "Failed to submit decision.");
			}
		} catch (err) {
			setError("Failed to submit decision. Please try again.");
			console.error("Decision API Error:", err);
		} finally {
			setSubmitting(false);
		}
	};

	if (loading) {
		return (
			<div className="flex h-64 w-[95vw] max-w-5xl items-center justify-center rounded-2xl bg-white shadow-2xl">
				<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
			</div>
		);
	}

	if (!data) {
		return (
			<div className="flex w-[95vw] max-w-lg flex-col rounded-2xl bg-white p-6 shadow-2xl">
				<div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
					{error || "CAM approval data not found."}
					<button onClick={fetchData} className="ml-4 text-red-900 underline">
						Retry
					</button>
				</div>
				<div className="flex justify-end mt-4">
					<button
						onClick={() => onClose?.()}
						className="px-4 py-2 border border-slate-300 rounded-lg text-slate-600 hover:bg-slate-50 text-sm"
					>
						Close
					</button>
				</div>
			</div>
		);
	}

	const formLocked = !!data.lockedBy;
	const showForm = !data.completed && !data.rejectedMessage;

	return (
		<div
			role="dialog"
			aria-modal="true"
			aria-label={`CAM ${data.applNoDisplay} approval`}
			className="flex max-h-[90vh] w-[95vw] max-w-5xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl"
		>
			<div className="min-h-0 flex-1 overflow-y-auto p-6">
				<h1 className="text-2xl md:text-3xl font-bold text-gray-800 mb-1">Approval Review</h1>

				{error && (
					<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
						{error}
					</div>
				)}

				{data.lockedBy && (
					<div className="mb-4 p-4 bg-blue-50 border border-blue-200 rounded-lg text-blue-700">
						In Progress: {data.lockedBy}
					</div>
				)}

				{data.rejectedMessage && (
					<div className="mb-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg text-yellow-800">
						{data.rejectedMessage}
					</div>
				)}

				{data.alreadySentToAdmin && (
					<div className="mb-4 p-4 bg-blue-50 border border-blue-200 rounded-lg text-blue-700">
						This CAM has been sent to <strong>ADMIN</strong> at{" "}
						<strong>{data.alreadySentToAdmin.sentAt}</strong>
					</div>
				)}

				<div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
					<div>
						<div className="text-xs font-medium text-gray-500 uppercase">CAM No.</div>
						<div className="text-gray-800 font-medium">{data.applNoDisplay}</div>
					</div>
					<div>
						<div className="text-xs font-medium text-gray-500 uppercase">Customer Name</div>
						<div className="text-gray-800 font-medium">{data.lesseeName}</div>
					</div>
					<div>
						<div className="text-xs font-medium text-gray-500 uppercase">CMO Name</div>
						<div className="text-gray-800 font-medium">{data.cmoName ?? "-"}</div>
					</div>
				</div>

				<h2 className="text-lg font-semibold text-gray-800 mb-3">CAM Approval Status</h2>
				<div className="overflow-x-auto rounded-lg border border-gray-200 mb-6">
					<table className="w-full min-w-[900px]">
						<thead className="bg-gradient-to-r from-gray-50 to-gray-100">
							<tr>
								<th className="py-3 px-5 text-left text-sm font-medium text-gray-500 uppercase tracking-wider">Date</th>
								<th className="py-3 px-5 text-left text-sm font-medium text-gray-500 uppercase tracking-wider">Approval By</th>
								<th className="py-3 px-5 text-left text-sm font-medium text-gray-500 uppercase tracking-wider">CAM Status</th>
								<th className="py-3 px-5 text-left text-sm font-medium text-gray-500 uppercase tracking-wider">Recommendation</th>
							</tr>
						</thead>
						<tbody className="divide-y divide-gray-200">
							{data.history.length === 0 ? (
								<tr>
									<td colSpan={4} className="py-6 px-5 text-center text-gray-500 text-base">
										No approval history yet
									</td>
								</tr>
							) : (
								data.history.map((item, idx) => (
									<tr key={idx} className={item.lowRecommendation ? "bg-pink-100" : idx % 2 === 0 ? "bg-white" : "bg-gray-50"}>
										<td className="py-3 px-5 text-base text-gray-800 align-top">{item.date}</td>
										<td className="py-3 px-5 align-top">
											<div className="text-base font-bold text-gray-900">{item.approvedBy}</div>
											<div className="mt-1 border-l-4 border-gray-300 bg-black/5 rounded-r-md pl-3 pr-3 py-1 leading-snug">
												<span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Comment</span>
												<p className="text-sm text-gray-700 mt-0 line-clamp-2">{item.comment || "-"}</p>
											</div>
										</td>
										<td className="py-3 px-5 text-base font-semibold text-gray-800 align-top">{item.statusLabel}</td>
										<td className="py-3 px-5 text-base font-semibold text-gray-800 align-top">{item.recommendation}</td>
									</tr>
								))
							)}
						</tbody>
					</table>
				</div>

				{data.showSurveyIndependent && (
					<div className="flex flex-wrap items-center gap-6 mb-6">
						<label className="flex items-center gap-2 text-sm font-medium text-gray-700">
							Survey Independent:
							<select
								value={isiSurv}
								onChange={(e) => {
									const val = e.target.value;
									setIsiSurv(val);

									if (val !== "1") setIsiResult("");
								}}
								disabled={data.surveyIndependentDisabled || formLocked}
								className="border border-gray-300 rounded px-2 py-1 text-sm"
							>
								<option value="">Select</option>
								<option value="0">No</option>
								<option value="1">Yes</option>
							</select>
						</label>
						<label className="flex items-center gap-2 text-sm font-medium text-gray-700">
							Result:
							<select
								value={isiResult}
								onChange={(e) => setIsiResult(e.target.value)}
								disabled={data.resultIndependentDisabled || formLocked || isiSurv !== "1"}
								className="border border-gray-300 rounded px-2 py-1 text-sm"
							>
								<option value="">Select</option>
								{isiSurv === "1" && data.resultIndependentOptions.map((opt) => (
									<option key={opt.value} value={opt.value}>{opt.label}</option>
								))}
							</select>
						</label>
					</div>
				)}

				{showForm && (
					<>
						<h2 className="text-lg font-semibold text-gray-800 mb-3">Approval Form</h2>

						<div className="space-y-4 mb-4">
							<div className="flex items-center gap-3">
								<label className="w-40 text-sm font-medium text-slate-700">Red Code</label>
								<input
									type="checkbox"
									checked={redCode}
									onChange={(e) => setRedCode(e.target.checked)}
									disabled={formLocked}
									className="w-4 h-4 accent-blue-600"
								/>
								<select
									value={gpsVendor}
									onChange={(e) => setGpsVendor(e.target.value)}
									disabled={formLocked}
									className="border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
								>
									<option value="">Select</option>
									{data.gpsVendorOptions.map((opt) => (
										<option key={opt.value} value={opt.value}>{opt.label}</option>
									))}
								</select>
							</div>

							{!data.isCmo && (
								<div className="flex items-center gap-3">
									<label className="w-40 text-sm text-gray-700">Approval Status</label>
									<select
										value={approvalSts}
										onChange={(e) => handleApprovalStsChange(e.target.value as "A" | "R" | "RW")}
										disabled={formLocked}
										className="border border-gray-300 rounded px-2 py-1 text-sm"
									>
										<option value="A">Approve</option>
										<option value="R">Reject -&gt; Back to CMO</option>
										{data.allowRejectToWatchlist && (
											<option value="RW" style={{ color: "#ff0000" }}>
												Reject -&gt; Added to Watchlist
											</option>
										)}
									</select>
									<label className="flex items-center gap-2 text-sm text-gray-700">
										<input
											type="checkbox"
											checked={notRecommend}
											onChange={(e) => setNotRecommend(e.target.checked)}
											disabled={formLocked}
										/>
										Not Recommended
									</label>
								</div>
							)}

							<div className="flex items-center gap-3">
								<label className="w-40 text-sm text-gray-700">
									{data.isCmo ? "1st Approval" : "Next Approval"}
								</label>
								<select
									value={nextApprover}
									onChange={(e) => setNextApprover(e.target.value)}
									disabled={formLocked || (!data.isCmo && approvalSts !== "A")}
									className="border border-gray-300 rounded px-2 py-1 text-sm"
								>
									{data.approverOptions.map((opt) => (
										<option key={opt.value} value={opt.value}>{opt.label}</option>
									))}
								</select>
							</div>

							<div>
								<label className="block text-sm text-gray-700 mb-1">Comment</label>
								<textarea
									value={comment}
									onChange={(e) => setComment(e.target.value)}
									maxLength={5000}
									rows={5}
									disabled={formLocked}
									className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
								/>
								{data.watchlist.listed && (
									<p className="text-red-600 text-sm mt-1">
										This Customer has been listed on watchlist
										<br />
										{data.watchlist.description}
										<br />
										{data.watchlist.byLabel}: {data.watchlist.by}
										<br />
										{data.watchlist.dateLabel}: {data.watchlist.date}
									</p>
								)}
							</div>

							{data.showCreditRecommendation && (
								<>
									<h3 className="font-semibold text-gray-800">Credit Recommendation</h3>
									<div>
										<label className="block text-sm text-gray-700 mb-1">Strength</label>
										<textarea
											value={strength}
											onChange={(e) => setStrength(e.target.value)}
											rows={8}
											disabled={formLocked}
											className="w-full border border-gray-300 rounded px-3 py-2 text-sm font-sans"
										/>
									</div>
									<div>
										<label className="block text-sm text-gray-700 mb-1">Weakness</label>
										<textarea
											value={weakness}
											onChange={(e) => setWeakness(e.target.value)}
											rows={8}
											disabled={formLocked}
											className="w-full border border-gray-300 rounded px-3 py-2 text-sm font-sans"
										/>
									</div>
									<div>
										<label className="block text-sm text-gray-700 mb-1">TBO / TC</label>
										<textarea
											value={tbo}
											onChange={(e) => setTbo(e.target.value)}
											rows={8}
											disabled={formLocked}
											className="w-full border border-gray-300 rounded px-3 py-2 text-sm font-sans"
										/>
									</div>
								</>
							)}
						</div>

						{data.warningMessage && (
							<div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-600 text-sm">
								{data.warningMessage}
							</div>
						)}

						{validationErrors.length > 0 && (
							<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
								<p className="font-medium mb-1">Please check the following:</p>
								<ul className="list-disc list-inside text-sm">
									{validationErrors.map((e, idx) => (
										<li key={idx}>{e}</li>
									))}
								</ul>
							</div>
						)}
					</>
				)}
			</div>

			<div className="flex justify-end gap-3 border-t border-slate-200 p-4">
				{showForm ? (
					<>
						<button
							onClick={handleSubmit}
							disabled={formLocked || submitting || data.submitDisabled}
							className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-4 py-2 rounded-md font-medium transition-colors"
						>
							{submitting ? "Processing..." : "Confirm"}
						</button>
						<button
							onClick={() => onClose?.()}
							className="bg-gray-500 hover:bg-gray-600 text-white px-4 py-2 rounded-md font-medium transition-colors"
						>
							Cancel
						</button>
					</>
				) : (
					<button
						onClick={() => onClose?.()}
						className="px-4 py-2 border border-slate-300 rounded-lg text-slate-600 hover:bg-slate-50 text-sm"
					>
						Close
					</button>
				)}
			</div>
		</div>
	);
};

export default CAMApprovalPage;