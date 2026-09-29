import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import api from "../../../api/axiosInstance";
import Pagination from "../../../helpers/Pagination";
import { DEFAULT_PAGE_LIMIT } from "../../../constants/DefaultValue";

interface PreChecking {
	date: string;
	customer_no: string;
	customer_name: string;
	prechecking_id: string;
	cmo: string;
	approver: string;
	apless: string;
	is_own: boolean;
}

interface ApiResponse {
	data: PreChecking[];
	total: number;
	access_level: string;
}

const PrecheckingInProgressPage: React.FC = () => {
	const [records, setRecords] = useState<PreChecking[]>([]);
	const [searchBy, setSearchBy] = useState<"1" | "2">("1");
	const [searchVal, setSearchVal] = useState("");
	const [page, setPage] = useState(1);
	const [total, setTotal] = useState(0);
	const [accessLevel, setAccessLevel] = useState("");
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const limit = DEFAULT_PAGE_LIMIT;

	const navigate = useNavigate();

	const fetchRecords = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			const response = await api.get<ApiResponse>("/Prechecking/Inprogress/api/data", {
				params: { search_by: searchBy, search_val: searchVal, page, limit },
			});
			setRecords(response.data.data);
			setTotal(response.data.total);
			setAccessLevel(response.data.access_level);
		} catch (err) {
			if (err) {
				return;
			}
			console.error(err);
			setError("Failed to load data. Please try again.");
		} finally {
			setLoading(false);
		}
	}, [searchBy, searchVal, page, limit]);

	useEffect(() => {
		fetchRecords();
	}, [fetchRecords]);

	const totalPages = Math.ceil(total / limit);
	const isCMO = accessLevel === "CMO";

	const handleView = (apless: string, precheckingId: string) => {
		navigate(`/view-prechecking?apless=${encodeURIComponent(apless)}&prechecking_id=${precheckingId}`);
	};

	const handleWithdraw = async (apless: string, precheckingId: string) => {
		if (!window.confirm(`Withdraw prechecking ${precheckingId}?`)) return;
		try {
			await api.post("/Prechecking/Inprogress/api/withdraw", { apless, prechecking_id: precheckingId });
			fetchRecords();
		} catch {
			alert("Withdraw failed. Please try again.");
		}
	};

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-7xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6 mb-6">

					<div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
						<div>
							<h1 className="text-2xl md:text-3xl font-bold text-gray-800">
								Prechecking - In Progress
							</h1>
							<p className="text-gray-600 mt-1">View and manage prechecking requests</p>
						</div>
						<div className="flex items-center gap-3">
							<span className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm font-medium">
								Total: {total}
							</span>
						</div>
					</div>

					<div className="flex flex-col md:flex-row gap-4 mb-6">
						<select
							value={searchBy}
							onChange={(e) => setSearchBy(e.target.value as "1" | "2")}
							className="border border-gray-300 rounded-lg px-3 py-3 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all bg-white"
						>
							<option value="1">Customer No.</option>
							<option value="2">Customer Name</option>
						</select>

						<div className="relative flex-1">
							<input
								type="text"
								placeholder={
									searchBy === "1"
										? "Search by customer number..."
										: "Search by customer name..."
								}
								value={searchVal}
								onChange={(e) => setSearchVal(e.target.value)}
								onKeyDown={(e) => {
									if (e.key === "Enter") {
										setPage(1);
										fetchRecords();
									}
								}}
								className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all"
							/>
							<svg
								className="w-5 h-5 text-gray-400 absolute left-3 top-1/2 transform -translate-y-1/2"
								focusable="false"
								aria-hidden="true"
								viewBox="0 0 24 24"
								fill="none"
							>
								<path
									d="M15.5 14H14.71L14.43 13.73C15.41 12.59 16 11.11 16 9.5C16 5.91 13.09 3 9.5 3C5.91 3 3 5.91 3 9.5C3 13.09 5.91 16 9.5 16C11.11 16 12.59 15.41 13.73 14.43L14 14.71V15.5L19 20.49L20.49 19L15.5 14ZM9.5 14C7.01 14 5 11.99 5 9.5C5 7.01 7.01 5 9.5 5C11.99 5 14 7.01 14 9.5C14 11.99 11.99 14 9.5 14Z"
									fill="currentColor"
								/>
							</svg>
						</div>

						<button
							onClick={() => {
								setPage(1);
								fetchRecords();
							}}
							disabled={loading}
							className={`bg-gradient-to-r from-blue-600 to-indigo-700 hover:from-blue-700 hover:to-indigo-800 text-white px-6 py-3 rounded-lg font-medium shadow-md hover:shadow-lg transition-all flex items-center justify-center gap-2 ${loading ? "opacity-75 cursor-not-allowed" : ""
								}`}
						>
							{loading ? (
								<>
									<svg
										className="animate-spin -ml-1 mr-2 h-4 w-4 text-white"
										fill="none"
										viewBox="0 0 24 24"
									>
										<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
										<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
									</svg>
									Searching...
								</>
							) : (
								<>
									<svg className="w-5 h-5" focusable="false" aria-hidden="true" viewBox="0 0 24 24" fill="none">
										<path
											d="M15.5 14H14.71L14.43 13.73C15.41 12.59 16 11.11 16 9.5C16 5.91 13.09 3 9.5 3C5.91 3 3 5.91 3 9.5C3 13.09 5.91 16 9.5 16C11.11 16 12.59 15.41 13.73 14.43L14 14.71V15.5L19 20.49L20.49 19L15.5 14ZM9.5 14C7.01 14 5 11.99 5 9.5C5 7.01 7.01 5 9.5 5C11.99 5 14 7.01 14 9.5C14 11.99 11.99 14 9.5 14Z"
											fill="currentColor"
										/>
									</svg>
									Search
								</>
							)}
						</button>
					</div>

					{error && (
						<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
							{error}
							<button onClick={fetchRecords} className="ml-4 text-red-900 underline">
								Retry
							</button>
						</div>
					)}

					<div className="overflow-x-auto rounded-lg border border-gray-200">
						<table className="w-full">
							<thead className="bg-gradient-to-r from-gray-50 to-gray-100">
								<tr>
									<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
									<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Customer No.</th>
									<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Customer Name</th>
									<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Prechecking ID</th>
									{!isCMO && (
										<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">CMO</th>
									)}
									<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
										{isCMO ? "Status" : "Status"}
									</th>
									<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
								</tr>
							</thead>
							<tbody className="divide-y divide-gray-200">
								{records.length === 0 && !loading ? (
									<tr>
										<td colSpan={isCMO ? 6 : 7} className="py-10 px-6 text-center text-gray-500">
											<div className="flex flex-col items-center justify-center">
												<svg
													className="w-16 h-16 text-gray-300 mb-4"
													fill="none"
													stroke="currentColor"
													viewBox="0 0 24 24"
												>
													<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
												</svg>
												<p className="text-lg">No records found</p>
												<p className="text-sm mt-1">Try adjusting your search query</p>
											</div>
										</td>
									</tr>
								) : (
									<>
										{records.map((r, idx) => (
											<tr
												key={r.prechecking_id}
												className={`hover:bg-gray-50 transition-colors ${idx % 2 === 0 ? "bg-white" : "bg-gray-50"
													}`}
											>
												<td className="py-4 px-6 whitespace-nowrap text-sm text-gray-600">{r.date || "—"}</td>
												<td className="py-4 px-6 whitespace-nowrap text-sm font-medium text-blue-600 cursor-pointer hover:underline"
													onClick={() => handleView(r.apless, r.prechecking_id)}
												>
													{r.customer_no}
												</td>
												<td className="py-4 px-6 text-sm text-gray-700 font-medium">{r.customer_name}</td>
												<td className="py-4 px-6 whitespace-nowrap text-sm font-mono text-gray-600">{r.prechecking_id}</td>
												{!isCMO && (
													<td className="py-4 px-6 whitespace-nowrap text-sm text-gray-600">{r.cmo}</td>
												)}
												<td className="py-4 px-6 whitespace-nowrap text-sm text-gray-600">{r.approver}</td>
												<td className="py-4 px-6 whitespace-nowrap text-sm flex items-center gap-2">
													<button
														onClick={() => handleView(r.apless, r.prechecking_id)}
														className="px-3 py-1 bg-blue-500 text-white text-xs rounded hover:bg-blue-600"
													>
														View
													</button>
													{isCMO && r.is_own && (
														<button
															onClick={() => handleWithdraw(r.apless, r.prechecking_id)}
															className="px-3 py-1 bg-orange-500 text-white text-xs rounded hover:bg-orange-600"
														>
															Withdraw
														</button>
													)}
												</td>
											</tr>
										))}
										{loading && (
											<tr>
												<td colSpan={isCMO ? 6 : 7} className="py-4 px-6 text-center">
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

export default PrecheckingInProgressPage;