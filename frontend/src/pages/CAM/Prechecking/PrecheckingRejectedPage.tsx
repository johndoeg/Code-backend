import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import Pagination from "../../../helpers/Pagination";

interface RejectedRow {
	Prechecking_Id: string;
	Apless: string;
	LesseeName: string;
	CreatedBy: string;
	Rejected_By: string;
	Rejected_Date: string;
}

const SEARCH_OPTIONS = [
	{ value: "1", label: "Customer No" },
	{ value: "2", label: "Customer Name" },
];

const API_URL = import.meta.env.VITE_API_URL;

const PrecheckingRejectedPage: React.FC = () => {
	const navigate = useNavigate();

	const [rows, setRows] = useState<RejectedRow[]>([]);
	const [total, setTotal] = useState(0);
	const [page, setPage] = useState(1);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const limit = 25;

	const [searchBy, setSearchBy] = useState("1");
	const [searchVal, setSearchVal] = useState("");
	const [appliedSearchBy, setAppliedSearchBy] = useState("");
	const [appliedSearchVal, setAppliedSearchVal] = useState("");

	const fetchRejected = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			const res = await axios.get(`${API_URL}/Prechecking/api/rejected`, {
				params: {
					search_by: appliedSearchBy,
					search_val: appliedSearchVal,
					page,
					limit,
				},
				timeout: 15000,
			});
			setRows(res.data.data);
			setTotal(res.data.total);
		} catch {
			setError("Failed to load rejected data. Please try again.");
		} finally {
			setLoading(false);
		}
	}, [appliedSearchBy, appliedSearchVal, page]);

	useEffect(() => { fetchRejected(); }, [fetchRejected]);

	const handleSearch = () => {
		setAppliedSearchBy(searchBy);
		setAppliedSearchVal(searchVal);
		setPage(1);
	};

	const totalPages = Math.ceil(total / limit);

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-7xl mx-auto space-y-6">
				<div className="bg-white rounded-2xl shadow-lg p-6">

					{/* ── Header ── */}
					<div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
						<div>
							<h1 className="text-2xl md:text-3xl font-bold text-gray-800">
								Prechecking — Rejected
							</h1>
							<p className="text-gray-500 mt-1 text-sm">
								Showing rejections from the last 30 days by default
							</p>
						</div>
						<span className="bg-red-100 text-red-700 px-3 py-1 rounded-full text-sm font-medium self-start md:self-auto">
							Total: {total}
						</span>
					</div>

					{/* ── Search bar ── */}
					<div className="flex flex-col md:flex-row gap-3 mb-6">
						<select
							value={searchBy}
							onChange={(e) => setSearchBy(e.target.value)}
							className="border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
						>
							{SEARCH_OPTIONS.map((o) => (
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
							<button onClick={fetchRejected} className="ml-4 underline text-red-900">
								Retry
							</button>
						</div>
					)}

					{/* ── Table ── */}
					<div className="overflow-x-auto rounded-lg border border-gray-200">
						<table className="w-full">
							<thead className="bg-gradient-to-r from-gray-50 to-gray-100">
								<tr>
									{[
										"Rejected Date",
										"Customer No.",
										"Customer Name",
										"Prechecking ID",
										"CMO",
										"Rejected By",
									].map((h) => (
										<th
											key={h}
											className="py-4 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap"
										>
											{h}
										</th>
									))}
								</tr>
							</thead>
							<tbody className="divide-y divide-gray-200">
								{rows.length === 0 && !loading ? (
									<tr>
										<td colSpan={6} className="py-10 px-6 text-center text-gray-500">
											<div className="flex flex-col items-center justify-center">
												<svg className="w-16 h-16 text-gray-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
													<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
												</svg>
												<p className="text-lg">No rejected records found</p>
												<p className="text-sm mt-1">Try adjusting your search or date range</p>
											</div>
										</td>
									</tr>
								) : (
									<>
										{rows.map((row, idx) => (
											<tr
												key={`${row.Prechecking_Id}-${idx}`}
												className={`hover:bg-red-50 transition-colors ${idx % 2 === 0 ? "bg-white" : "bg-gray-50"}`}
											>
												<td className="py-3 px-4 text-sm text-gray-600 whitespace-nowrap">
													{row.Rejected_Date}
												</td>
												<td className="py-3 px-4 text-sm whitespace-nowrap">
													{/* Link to view_prechecking, mirroring the PHP <a href> */}
													<button
														onClick={() => navigate(
															`/view-prechecking?apless=${encodeURIComponent(row.Apless)}&prechecking_id=${encodeURIComponent(row.Prechecking_Id)}`
														)}
														className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
													>
														{row.Apless}
													</button>
												</td>
												<td className="py-3 px-4 text-sm text-gray-800">{row.LesseeName}</td>
												<td className="py-3 px-4 text-sm text-gray-700 whitespace-nowrap font-mono">
													{row.Prechecking_Id}
												</td>
												<td className="py-3 px-4 text-sm text-gray-700">{row.CreatedBy}</td>
												<td className="py-3 px-4 text-sm text-gray-700">{row.Rejected_By}</td>
											</tr>
										))}
										{loading && (
											<tr>
												<td colSpan={6} className="py-4 px-6 text-center">
													<div className="flex justify-center">
														<svg className="animate-spin h-6 w-6 text-blue-600" fill="none" viewBox="0 0 24 24">
															<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
															<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
														</svg>
													</div>
												</td>
											</tr>
										)}
									</>
								)}
							</tbody>
						</table>
					</div>

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

export default PrecheckingRejectedPage;