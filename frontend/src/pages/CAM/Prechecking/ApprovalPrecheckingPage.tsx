import React, { useEffect, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import api from "../../../api/axiosInstance";

interface ApprovalData {
	apless: string;
	prechecking_id: string;
	lessee_name: string;
	cmo: string;
	rejected: boolean;
	rejected_by: string;
	rejected_date: string;
	reject_comment: string;
	access_level: string;
	cr_approver: string;
}

const ApprovalPrecheckingPage: React.FC = () => {
	const [searchParams] = useSearchParams();
	const navigate = useNavigate();

	const apless = searchParams.get("apless") ?? "";
	const prechecking_id = searchParams.get("prechecking_id_send") ?? "";

	const [data, setData] = useState<ApprovalData | null>(null);
	const [loading, setLoading] = useState(true);
	const [submitting, setSubmitting] = useState(false);
	const [done, setDone] = useState(false);
	const [doneMsg, setDoneMsg] = useState("");
	const [error, setError] = useState<string | null>(null);

	const [comment, setComment] = useState("");
	const [approvalStatus, setApprovalStatus] = useState<"A" | "R">("A");

	useEffect(() => {
		if (!apless || !prechecking_id) return;
		setLoading(true);
		api
			.get("/Prechecking/Approval/api/approval-form", {
				params: { apless, prechecking_id_send: prechecking_id },
			})
			.then((r) => setData(r.data))
			.catch(() => setError("Failed to load approval data."))
			.finally(() => setLoading(false));
	}, [apless, prechecking_id]);

	const handleConfirm = async () => {
		if (!data) return;
		setSubmitting(true);
		setError(null);
		try {
			const res = await api.post("/Prechecking/Approval/api/approval-confirm", {
				apless,
				prechecking_id,
				comment,
				approval: data.access_level === "CMO" ? data.cr_approver : "Admin",
				approval_status: data.access_level === "CR" ? approvalStatus : undefined,
				access_level: data.access_level,
			});

			if (res.data?.success) {
				setDoneMsg(
					data.access_level === "CMO"
						? `In Progress : ${data.cr_approver}`
						: approvalStatus === "A" ? "Approved successfully." : "Rejected."
				);
				setDone(true);
			} else {
				setError(res.data?.message ?? "Submission failed.");
			}
		} catch (e: any) {
			setError(e.response?.data?.message ?? "Submission failed.");
		} finally {
			setSubmitting(false);
		}
	};

	if (loading) return (
		<div className="min-h-screen bg-gray-50 flex items-center justify-center">
			<svg className="animate-spin h-10 w-10 text-blue-600" fill="none" viewBox="0 0 24 24">
				<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
				<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
			</svg>
		</div>
	);

	if (error && !data) return (
		<div className="min-h-screen bg-gray-50 flex items-center justify-center">
			<div className="bg-red-50 border border-red-200 rounded-xl p-8 text-center max-w-md">
				<p className="text-red-700 font-medium">{error}</p>
				<button onClick={() => navigate(-1)} className="mt-4 text-blue-600 hover:underline text-sm">← Go back</button>
			</div>
		</div>
	);

	if (!data) return null;
	const isCMO = data.access_level === "CMO";
	const isCR = data.access_level === "CR";

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-6xl mx-auto space-y-6">

				<div className="bg-gradient-to-r from-blue-900 via-blue-800 to-blue-600 rounded-2xl p-6 shadow-lg flex items-center justify-between">
					<div>
						<h1 className="text-white text-xl font-bold">Prechecking Request Approval</h1>
						<p className="text-blue-200 text-sm mt-1">
							{isCMO ? "Send for CR review" : "Review and approve / reject"}
						</p>
					</div>
					<button
						onClick={() => navigate(-1)}
						className="bg-white/15 hover:bg-white/25 border border-white/30 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors flex items-center gap-2"
					>
						<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
						</svg>
						Cancel
					</button>
				</div>

				{done && (
					<div className="bg-green-50 border border-green-200 rounded-2xl p-6 flex items-start gap-4">
						<svg className="w-6 h-6 text-green-600 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
						</svg>
						<div className="flex-1">
							<p className="text-green-800 font-semibold">{doneMsg}</p>
							<button
								onClick={() => navigate("/prechecking-onhand")}
								className="mt-3 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
							>
								Back to On Hand
							</button>
						</div>
					</div>
				)}

				{!done && (
					<>
						<div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
							<div className="bg-gradient-to-r from-blue-900 to-blue-700 px-5 py-3">
								<h2 className="text-white font-semibold text-sm uppercase tracking-wider">Prechecking Request</h2>
							</div>
							<div className="overflow-x-auto">
								<table className="w-full text-sm">
									<thead className="bg-gray-50">
										<tr>
											{["Apless No. (Temporary)", "Prechecking ID", "Customer Name", "CMO"].map((h) => (
												<th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">
													{h}
												</th>
											))}
										</tr>
									</thead>
									<tbody>
										<tr className="border-t border-gray-100">
											<td className="px-4 py-3 font-mono text-gray-800">{data.apless}</td>
											<td className="px-4 py-3 font-mono text-gray-800">{data.prechecking_id}</td>
											<td className="px-4 py-3 text-gray-800 font-medium">{data.lessee_name}</td>
											<td className="px-4 py-3 text-gray-600">{data.cmo}</td>
										</tr>
									</tbody>
								</table>
							</div>
						</div>

						{data.rejected && (
							<div className="bg-red-50 border border-red-200 rounded-2xl p-5 space-y-2">
								<div className="flex items-center gap-2 mb-3">
									<svg className="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
									</svg>
									<span className="text-red-800 font-semibold text-sm">Previously Rejected</span>
								</div>
								<div className="grid grid-cols-2 gap-x-8 gap-y-1 text-sm">
									<span className="text-red-600 font-medium">Rejected by</span>
									<span className="text-red-800">{data.rejected_by}</span>
									<span className="text-red-600 font-medium">Rejected date</span>
									<span className="text-red-800">{data.rejected_date}</span>
									<span className="text-red-600 font-medium">Remarks</span>
									<span className="text-red-800">{data.reject_comment}</span>
								</div>
							</div>
						)}

						<div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
							<div className="bg-gradient-to-r from-blue-900 to-blue-700 px-5 py-3">
								<h2 className="text-white font-semibold text-sm uppercase tracking-wider">Approval Form</h2>
							</div>
							<div className="p-6 space-y-5">

								<div className="flex flex-col gap-1.5">
									<label className="text-sm font-medium text-gray-700">
										{isCMO ? "1st Approval" : "Approval"}
									</label>
									<input
										readOnly
										value={isCMO ? (data.cr_approver || "Admin") : "Admin"}
										className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-gray-50 text-gray-700 w-64"
									/>
								</div>

								{isCR && (
									<div className="flex flex-col gap-1.5">
										<label className="text-sm font-medium text-gray-700">Action</label>
										<div className="flex gap-3">
											{(["A", "R"] as const).map((v) => (
												<button
													key={v}
													type="button"
													onClick={() => setApprovalStatus(v)}
													className={`px-5 py-2 rounded-lg text-sm font-semibold border transition-all ${approvalStatus === v
															? v === "A"
																? "bg-green-600 text-white border-green-600 shadow-sm"
																: "bg-red-600 text-white border-red-600 shadow-sm"
															: "bg-white text-gray-600 border-gray-300 hover:bg-gray-50"
														}`}
												>
													{v === "A" ? "Approve" : "Reject"}
												</button>
											))}
										</div>
									</div>
								)}

								<div className="flex flex-col gap-1.5">
									<label className="text-sm font-medium text-gray-700">Comment</label>
									<textarea
										rows={4}
										maxLength={5000}
										value={comment}
										onChange={(e) => setComment(e.target.value)}
										placeholder="Optional comment…"
										className="border border-gray-300 rounded-lg px-3 py-2 text-sm resize-vertical focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
									/>
									<span className="text-xs text-gray-400 text-right">{comment.length}/5000</span>
								</div>

								{error && (
									<div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
										{error}
									</div>
								)}

								<div className="flex gap-3 pt-1">
									<button
										type="button"
										onClick={handleConfirm}
										disabled={submitting}
										className={`bg-gradient-to-r from-blue-700 to-blue-600 hover:from-blue-800 hover:to-blue-700 text-white font-semibold px-6 py-2.5 rounded-lg shadow transition-all flex items-center gap-2 ${submitting ? "opacity-60 cursor-not-allowed" : ""}`}
									>
										{submitting && (
											<svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
												<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
												<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
											</svg>
										)}
										{submitting ? "Processing…" : "Confirm"}
									</button>
									<button
										type="button"
										onClick={() => navigate("/cam-request-onhand")}
										disabled={submitting}
										className="bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 font-semibold px-6 py-2.5 rounded-lg transition-colors"
									>
										Cancel
									</button>
								</div>

							</div>
						</div>
					</>
				)}

			</div>
		</div>
	);
};

export default ApprovalPrecheckingPage;