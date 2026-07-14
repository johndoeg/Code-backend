import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import api from "../../../api/axiosInstance";
import Pagination from "../../../helpers/Pagination";
import { DEFAULT_PAGE_LIMIT } from '../../../constants/DefaultValue';

interface CMORow {
	apless: string;
	LESSEE_NM: string;
	PRECHECKING_ID: string;
	NAMACMO: string;
	LastApprovalActionCode: string;
	ApprovalActionCode: string;
	LESSEE_TP: string;
	tgl: string;
}

interface CRRow {
	APLESS: string;
	LESSEE_NM: string;
	NAMACMO: string;
	Prechecking_Id: string;
	tgl: string;
	tgl_cek: string;
}

type OnHandRow = CMORow | CRRow;

const isCMORow = (row: OnHandRow): row is CMORow =>
	"PRECHECKING_ID" in row;

const PreCheckingOnHandPage: React.FC = () => {
	const navigate = useNavigate();

	const [rows, setRows] = useState<OnHandRow[]>([]);
	const [total, setTotal] = useState(0);
	const [page, setPage] = useState(1);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const limit = DEFAULT_PAGE_LIMIT;

	const [accesslevel, setAccesslevel] = useState("");
	const [username, setUsername] = useState("");

	const [searchBy, setSearchBy] = useState("1");
	const [searchVal, setSearchVal] = useState("");
	const [appliedSearchBy, setAppliedSearchBy] = useState("");
	const [appliedSearchVal, setAppliedSearchVal] = useState("");

	const [selectedIds, setSelectedIds] = useState<string[]>([]);

	const fetchOnhand = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			const res = await api.get('/Prechecking/Onhand/api/data', {
				params: {
					search_by: appliedSearchBy,
					search_val: appliedSearchVal,
					page,
					limit,
				},
			});
			setRows(res.data.data);
			setTotal(res.data.total);
			setAccesslevel(res.data.accesslevel || "");
			setUsername(res.data.username || "");
		} catch {
			setError("Failed to load on-hand data. Please try again.");
		} finally {
			setLoading(false);
		}
	}, [appliedSearchBy, appliedSearchVal, page]);

	useEffect(() => { fetchOnhand(); }, [fetchOnhand]);

	const handleSearch = () => {
		setAppliedSearchBy(searchBy);
		setAppliedSearchVal(searchVal);
		setSelectedIds([]);
		setPage(1);
	};

	const handleSend = (precheckingId: string, apless: string) => {
		navigate(
			`/cam-request-approval?apless=${encodeURIComponent(apless)}&prechecking_id_send=${encodeURIComponent(precheckingId)}`
		);
	};

	const handleDelete = (apless: string, precheckingId: string) => {
		if (!window.confirm("Are you sure to delete this prechecking data?")) return;
		navigate(
			`/cam-request-delete?apless=${encodeURIComponent(apless)}&prechecking_id=${encodeURIComponent(precheckingId)}`
		);
	};

	const handleEdit = (apless: string, precheckingId: string, lesseeType: string) => {
		if (precheckingId.length > 12) {
			alert("The CAM No is invalid.");
			return;
		}
		if (!window.confirm("Are you sure to update data?")) return;
		if (lesseeType === 'PR') {
			navigate(`/cam-request-edit-pr?apless=${encodeURIComponent(apless)}&prechecking_id=${encodeURIComponent(precheckingId)}`);
		} else if (lesseeType === 'PT') {
			navigate(`/cam-request-edit-pt?apless=${encodeURIComponent(apless)}&prechecking_id=${encodeURIComponent(precheckingId)}`);
		}
	};

	const totalPages = Math.ceil(total / limit);

	const searchOptions =
		accesslevel === 'CR'
			? [{ value: "2", label: "Customer Name" }]
			: [
				{ value: "1", label: "Customer No" },
				{ value: "2", label: "Customer Name" },
			];

	const isCMO = accesslevel === 'CMO' || accesslevel === 'CMH';

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-7xl mx-auto space-y-6">
				<div className="bg-white rounded-2xl shadow-lg p-6">

					<div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
						<div>
							<h1 className="text-2xl md:text-3xl font-bold text-gray-800">
								Prechecking — On Hand
							</h1>
							<p className="text-gray-500 mt-1 text-sm">
								{isCMO ? "Your active prechecking submissions" : "Submissions pending your review"}
							</p>
						</div>
						<span className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm font-medium self-start md:self-auto">
							Total: {total}
						</span>
					</div>

					<div className="flex flex-col md:flex-row gap-3 mb-6">
						<select
							value={searchBy}
							onChange={(e) => setSearchBy(e.target.value)}
							className="border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
						>
							{searchOptions.map((o) => (
								<option key={o.value} value={o.value}>{o.label}</option>
							))}
						</select>

						<div className="relative flex-1">
							<input
								type="text"
								placeholder="Search..."
								value={searchVal}
								onChange={(e) => setSearchVal(e.target.value)}
								onKeyDown={(e) => { if (e.key === "Enter") handleSearch(); }}
								className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
							/>
							<svg className="w-5 h-5 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" viewBox="0 0 24 24" fill="none">
								<path d="M15.5 14H14.71L14.43 13.73C15.41 12.59 16 11.11 16 9.5C16 5.91 13.09 3 9.5 3C5.91 3 3 5.91 3 9.5C3 13.09 5.91 16 9.5 16C11.11 16 12.59 15.41 13.73 14.43L14 14.71V15.5L19 20.49L20.49 19L15.5 14ZM9.5 14C7.01 14 5 11.99 5 9.5C5 7.01 7.01 5 9.5 5C11.99 5 14 7.01 14 9.5C14 11.99 11.99 14 9.5 14Z" fill="currentColor" />
							</svg>
						</div>

						<button
							onClick={handleSearch}
							disabled={loading}
							className={`bg-gradient-to-r from-blue-600 to-indigo-700 hover:from-blue-700 hover:to-indigo-800 text-white px-6 py-2 rounded-lg font-medium shadow-md transition-all flex items-center gap-2 ${loading ? "opacity-75 cursor-not-allowed" : ""}`}
						>
							{loading ? "Searching..." : "Search"}
						</button>
					</div>

					{error && (
						<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
							{error}
							<button onClick={fetchOnhand} className="ml-4 underline text-red-900">Retry</button>
						</div>
					)}

					{isCMO && (
						<div className="overflow-x-auto rounded-lg border border-gray-200">
							<table className="w-full">
								<thead className="bg-gradient-to-r from-gray-50 to-gray-100">
									<tr>
										{["Date", "Customer No.", "Customer Name", "Prechecking ID", "Status", "Action", "Send"].map((h) => (
											<th key={h} className="py-4 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
												{h}
											</th>
										))}
									</tr>
								</thead>
								<tbody className="divide-y divide-gray-200">
									{rows.length === 0 && !loading ? (
										<tr>
											<td colSpan={7} className="py-10 px-6 text-center text-gray-500">
												<EmptyState />
											</td>
										</tr>
									) : (
										<>
											{(rows as CMORow[]).map((row, idx) => {
												const isRejected = row.LastApprovalActionCode === 'reject';
												const isOwner = row.NAMACMO === username;
												const everRejected = row.ApprovalActionCode === 'reject';

												return (
													<tr
														key={`${row.PRECHECKING_ID}-${idx}`}
														className={`transition-colors ${idx % 2 === 0 ? "bg-white" : "bg-gray-50"} ${isRejected ? "hover:bg-red-50" : "hover:bg-blue-50"}`}
													>
														<td className={`py-3 px-4 text-sm whitespace-nowrap ${isRejected ? "text-red-600" : "text-gray-600"}`}>
															{row.tgl}
														</td>
														<td className="py-3 px-4 text-sm whitespace-nowrap">
															<button
																onClick={() => navigate(`/view-prechecking?apless=${encodeURIComponent(row.apless)}&prechecking_id=${encodeURIComponent(row.PRECHECKING_ID)}`)}
																className={`hover:underline font-medium ${isRejected ? "text-red-600" : "text-blue-600 hover:text-blue-800"}`}
															>
																{row.apless}
															</button>
														</td>
														<td className={`py-3 px-4 text-sm ${isRejected ? "text-red-600" : "text-gray-800"}`}>
															{row.LESSEE_NM}
														</td>
														<td className={`py-3 px-4 text-sm font-mono whitespace-nowrap ${isRejected ? "text-red-600" : "text-gray-700"}`}>
															{row.PRECHECKING_ID}
														</td>
														<td className="py-3 px-4 text-sm">
															<span className={`inline-flex items-center gap-1 text-xs font-medium ${isRejected ? "text-red-600" : "text-gray-700"}`}>
																{row.NAMACMO}
																<span className={`px-1.5 py-0.5 rounded-full text-xs ${isRejected
																	? "bg-red-100 text-red-700"
																	: row.LastApprovalActionCode === 'pending'
																		? "bg-yellow-100 text-yellow-700"
																		: "bg-gray-100 text-gray-600"
																	}`}>
																	{row.LastApprovalActionCode}
																</span>
															</span>
														</td>
														<td className="py-3 px-4 whitespace-nowrap">
															{isOwner && (
																<div className="flex gap-2">
																	<button
																		onClick={() => handleEdit(row.apless, row.PRECHECKING_ID, row.LESSEE_TP)}
																		className="bg-yellow-400 hover:bg-yellow-500 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
																	>
																		Edit
																	</button>
																	{!everRejected && (
																		<button
																			onClick={() => handleDelete(row.apless, row.PRECHECKING_ID)}
																			className="bg-red-500 hover:bg-red-600 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
																		>
																			Delete
																		</button>
																	)}
																</div>
															)}
														</td>
														<td className="py-3 px-4 whitespace-nowrap">
															{isOwner && (
																<button
																	onClick={() => handleSend(row.PRECHECKING_ID, row.apless)}
																	className="bg-blue-500 hover:bg-blue-600 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
																>
																	Send
																</button>
															)}
														</td>
													</tr>
												);
											})}
											{loading && <LoadingRow colSpan={7} />}
										</>
									)}
								</tbody>
							</table>
						</div>
					)}

					{accesslevel === 'CR' && (
						<div className="overflow-x-auto rounded-lg border border-gray-200">
							<table className="w-full">
								<thead className="bg-gradient-to-r from-gray-50 to-gray-100">
									<tr>
										{["Date", "Customer No.", "Customer Name", "Prechecking ID", "CMO", "Last Checking", "Review"].map((h) => (
											<th key={h} className="py-4 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
												{h}
											</th>
										))}
									</tr>
								</thead>
								<tbody className="divide-y divide-gray-200">
									{rows.length === 0 && !loading ? (
										<tr>
											<td colSpan={7} className="py-10 px-6 text-center text-gray-500">
												<EmptyState />
											</td>
										</tr>
									) : (
										<>
											{(rows as CRRow[]).map((row, idx) => (
												<tr
													key={`${row.Prechecking_Id}-${idx}`}
													className={`hover:bg-blue-50 transition-colors ${idx % 2 === 0 ? "bg-white" : "bg-gray-50"}`}
												>
													<td className="py-3 px-4 text-sm text-gray-600 whitespace-nowrap">{row.tgl}</td>
													<td className="py-3 px-4 text-sm whitespace-nowrap">
														<button
															onClick={() => navigate(`/view-prechecking?apless=${encodeURIComponent(row.APLESS)}&prechecking_id=${encodeURIComponent(row.Prechecking_Id)}`)}
															className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
														>
															{row.APLESS}
														</button>
													</td>
													<td className="py-3 px-4 text-sm text-gray-800 whitespace-nowrap">{row.LESSEE_NM}</td>
													<td className="py-3 px-4 text-sm font-mono text-gray-700 whitespace-nowrap">{row.Prechecking_Id}</td>
													<td className="py-3 px-4 text-sm text-gray-600 whitespace-nowrap">{row.NAMACMO}</td>
													<td className="py-3 px-4 text-sm text-gray-600 whitespace-nowrap">{row.tgl_cek}</td>
													<td className="py-3 px-4">
														<button
															onClick={() => navigate(`/cam-request-onhand-detail?apless=${encodeURIComponent(row.APLESS)}&prechecking_id=${encodeURIComponent(row.Prechecking_Id)}`)}
															className="bg-orange-500 hover:bg-orange-600 text-white text-xs font-bold px-4 py-2 rounded-lg transition-colors"
														>
															Review
														</button>
													</td>
												</tr>
											))}
											{loading && <LoadingRow colSpan={7} />}
										</>
									)}
								</tbody>
							</table>
						</div>
					)}

					{!loading && (
						<Pagination
							page={page}
							totalPages={totalPages}
							onPageChange={setPage}
							totalItems={total}
							itemsPerPage={limit}
							className="mt-6"
						/>
					)}
				</div>
			</div>
		</div>
	);
};

const EmptyState: React.FC = () => (
	<div className="flex flex-col items-center justify-center">
		<svg className="w-16 h-16 text-gray-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
		</svg>
		<p className="text-lg">No on-hand records found</p>
		<p className="text-sm mt-1">Try adjusting your search query</p>
	</div>
);

const LoadingRow: React.FC<{ colSpan: number }> = ({ colSpan }) => (
	<tr>
		<td colSpan={colSpan} className="py-4 px-6 text-center">
			<div className="flex justify-center">
				<svg className="animate-spin h-6 w-6 text-blue-600" fill="none" viewBox="0 0 24 24">
					<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
					<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
				</svg>
			</div>
		</td>
	</tr>
);

export default PreCheckingOnHandPage;