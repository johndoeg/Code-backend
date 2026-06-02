import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import Pagination from "../../../helpers/Pagination";

interface Insurance {
	INS_CD: string;
	INS_CO: string;
}

type SearchBy = "1" | "2";

const SEARCH_OPTIONS: { value: SearchBy; label: string }[] = [
	{ value: "1", label: "Insurance Code" },
	{ value: "2", label: "Insurance Company" },
];

const InsurancePage: React.FC = () => {
	const [insurances, setInsurances] = useState<Insurance[]>([]);
	const [searchBy, setSearchBy] = useState<SearchBy>("1");
	const [searchVal, setSearchVal] = useState("");
	const [page, setPage] = useState(1);
	const [total, setTotal] = useState(0);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
	const [deleteLoading, setDeleteLoading] = useState(false);
	const limit = 25;

	const accessLevel = "9";

	const fetchInsurance = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			const response = await axios.get(
				`${import.meta.env.VITE_API_URL}/MasterData/api/insurance`,
				{
					params: { search_by: searchBy, search_val: searchVal, page, limit },
					timeout: 10000,
				}
			);
			setInsurances(response.data.data);
			setTotal(response.data.total);
		} catch (err) {
			if (axios.isCancel(err)) return;
			console.error(err);
			setError("Failed to load insurance data. Please try again.");
		} finally {
			setLoading(false);
		}
	}, [searchBy, searchVal, page, limit]);

	useEffect(() => {
		fetchInsurance();
	}, [fetchInsurance]);

	const handleSearch = () => {
		setPage(1);
		fetchInsurance();
	};

	const handleDelete = async (insCode: string) => {
		setDeleteLoading(true);
		try {
			await axios.delete(
				`${import.meta.env.VITE_API_URL}/MasterData/api/insurance/${insCode}`
			);
			setDeleteTarget(null);
			fetchInsurance();
		} catch (err) {
			console.error(err);
			setError("Failed to delete insurance record. Please try again.");
		} finally {
			setDeleteLoading(false);
		}
	};

	const totalPages = Math.ceil(total / limit);

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-7xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6 mb-6">
					{/* Header */}
					<div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
						<div>
							<h1 className="text-2xl md:text-3xl font-bold text-gray-800">
								Insurance
							</h1>
							<p className="text-gray-600 mt-1">
								View and manage your insurance records
							</p>
						</div>
						<div className="flex items-center gap-3">
							<span className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm font-medium">
								Total: {total}
							</span>
							{accessLevel === "9" && (
								<button
									onClick={() =>
										(window.location.href = "/insurance/add")
									}
									className="bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-600 hover:to-emerald-700 text-white px-4 py-2 rounded-lg font-medium shadow-md hover:shadow-lg transition-all flex items-center gap-2"
								>
									<svg
										className="w-4 h-4"
										fill="none"
										stroke="currentColor"
										viewBox="0 0 24 24"
									>
										<path
											strokeLinecap="round"
											strokeLinejoin="round"
											strokeWidth="2"
											d="M12 4v16m8-8H4"
										/>
									</svg>
									Add
								</button>
							)}
						</div>
					</div>

					{/* Search bar */}
					<div className="flex flex-col md:flex-row gap-3 mb-6">
						<select
							value={searchBy}
							onChange={(e) => setSearchBy(e.target.value as SearchBy)}
							className="border border-gray-300 rounded-lg px-3 py-3 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all bg-white min-w-[170px]"
						>
							{SEARCH_OPTIONS.map((opt) => (
								<option key={opt.value} value={opt.value}>
									{opt.label}
								</option>
							))}
						</select>

						<div className="relative flex-1">
							<input
								type="text"
								placeholder={`Search by ${searchBy === "1" ? "insurance code" : "company name"
									}...`}
								value={searchVal}
								onChange={(e) => setSearchVal(e.target.value)}
								onKeyDown={(e) => e.key === "Enter" && handleSearch()}
								className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all"
							/>
							<svg
								className="w-5 h-5 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2"
								fill="none"
								viewBox="0 0 24 24"
							>
								<path
									d="M15.5 14H14.71L14.43 13.73C15.41 12.59 16 11.11 16 9.5C16 5.91 13.09 3 9.5 3C5.91 3 3 5.91 3 9.5C3 13.09 5.91 16 9.5 16C11.11 16 12.59 15.41 13.73 14.43L14 14.71V15.5L19 20.49L20.49 19L15.5 14ZM9.5 14C7.01 14 5 11.99 5 9.5C5 7.01 7.01 5 9.5 5C11.99 5 14 7.01 14 9.5C14 11.99 11.99 14 9.5 14Z"
									fill="currentColor"
								/>
							</svg>
						</div>

						<button
							onClick={handleSearch}
							disabled={loading}
							className={`bg-gradient-to-r from-blue-600 to-indigo-700 hover:from-blue-700 hover:to-indigo-800 text-white px-6 py-3 rounded-lg font-medium shadow-md hover:shadow-lg transition-all flex items-center justify-center gap-2 ${loading ? "opacity-75 cursor-not-allowed" : ""
								}`}
						>
							{loading ? (
								<>
									<svg
										className="animate-spin h-4 w-4 text-white"
										fill="none"
										viewBox="0 0 24 24"
									>
										<circle
											className="opacity-25"
											cx="12"
											cy="12"
											r="10"
											stroke="currentColor"
											strokeWidth="4"
										/>
										<path
											className="opacity-75"
											fill="currentColor"
											d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
										/>
									</svg>
									Searching...
								</>
							) : (
								<>
									<svg
										className="w-5 h-5"
										fill="none"
										viewBox="0 0 24 24"
									>
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

					{/* Error banner */}
					{error && (
						<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 flex items-center justify-between">
							<span>{error}</span>
							<button
								onClick={fetchInsurance}
								className="ml-4 text-red-900 underline text-sm"
							>
								Retry
							</button>
						</div>
					)}

					{/* Table */}
					<div className="overflow-x-auto rounded-lg border border-gray-200">
						<table className="w-full">
							<thead className="bg-gradient-to-r from-gray-50 to-gray-100">
								<tr>
									<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-1/4">
										Insurance Code
									</th>
									<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
										Insurance Company
									</th>
									<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-40">
										Actions
									</th>
								</tr>
							</thead>
							<tbody className="divide-y divide-gray-200">
								{insurances.length === 0 && !loading ? (
									<tr>
										<td
											colSpan={3}
											className="py-10 px-6 text-center text-gray-500"
										>
											<div className="flex flex-col items-center justify-center">
												<svg
													className="w-16 h-16 text-gray-300 mb-4"
													fill="none"
													stroke="currentColor"
													viewBox="0 0 24 24"
												>
													<path
														strokeLinecap="round"
														strokeLinejoin="round"
														strokeWidth="2"
														d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
													/>
												</svg>
												<p className="text-lg">No insurance records found</p>
												<p className="text-sm mt-1">
													Try adjusting your search query
												</p>
											</div>
										</td>
									</tr>
								) : (
									<>
										{insurances.map((ins, idx) => (
											<tr
												key={ins.INS_CD}
												className={`hover:bg-blue-50 transition-colors ${idx % 2 === 0 ? "bg-white" : "bg-gray-50"
													}`}
											>
												<td className="py-4 px-6 whitespace-nowrap text-sm font-semibold text-gray-900">
													{ins.INS_CD}
												</td>
												<td className="py-4 px-6 text-sm text-gray-700">
													{ins.INS_CO}
												</td>
												<td className="py-4 px-6 whitespace-nowrap text-sm">
													<div className="flex items-center gap-2">
														{accessLevel === "9" ? (
															<>
																<button
																	onClick={() =>
																		(window.location.href = `/insurance/edit/${ins.INS_CD}`)
																	}
																	className="text-blue-600 hover:text-blue-900 hover:underline font-medium flex items-center gap-1"
																>
																	<svg
																		className="w-4 h-4"
																		fill="none"
																		stroke="currentColor"
																		viewBox="0 0 24 24"
																	>
																		<path
																			strokeLinecap="round"
																			strokeLinejoin="round"
																			strokeWidth="2"
																			d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
																		/>
																	</svg>
																	Edit
																</button>
																<span className="text-gray-300">|</span>
																<button
																	onClick={() =>
																		setDeleteTarget(ins.INS_CD)
																	}
																	className="text-red-500 hover:text-red-700 hover:underline font-medium flex items-center gap-1"
																>
																	<svg
																		className="w-4 h-4"
																		fill="none"
																		stroke="currentColor"
																		viewBox="0 0 24 24"
																	>
																		<path
																			strokeLinecap="round"
																			strokeLinejoin="round"
																			strokeWidth="2"
																			d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
																		/>
																	</svg>
																	Delete
																</button>
															</>
														) : (
															<button
																onClick={() =>
																	(window.location.href = `/insurance/view/${ins.INS_CD}`)
																}
																className="text-blue-600 hover:text-blue-900 hover:underline font-medium flex items-center gap-1"
															>
																<svg
																	className="w-4 h-4"
																	fill="none"
																	stroke="currentColor"
																	viewBox="0 0 24 24"
																>
																	<path
																		strokeLinecap="round"
																		strokeLinejoin="round"
																		strokeWidth="2"
																		d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
																	/>
																	<path
																		strokeLinecap="round"
																		strokeLinejoin="round"
																		strokeWidth="2"
																		d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
																	/>
																</svg>
																View
															</button>
														)}
													</div>
												</td>
											</tr>
										))}
										{loading && (
											<tr>
												<td colSpan={3} className="py-4 px-6 text-center">
													<div className="flex justify-center">
														<svg
															className="animate-spin h-6 w-6 text-blue-600"
															fill="none"
															viewBox="0 0 24 24"
														>
															<circle
																className="opacity-25"
																cx="12"
																cy="12"
																r="10"
																stroke="currentColor"
																strokeWidth="4"
															/>
															<path
																className="opacity-75"
																fill="currentColor"
																d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
															/>
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

			{/* Delete confirmation modal */}
			{deleteTarget && (
				<div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
					<div className="bg-white rounded-2xl shadow-2xl p-6 max-w-sm w-full mx-4">
						<div className="flex items-center gap-3 mb-4">
							<div className="bg-red-100 p-2 rounded-full">
								<svg
									className="w-6 h-6 text-red-600"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
								>
									<path
										strokeLinecap="round"
										strokeLinejoin="round"
										strokeWidth="2"
										d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
									/>
								</svg>
							</div>
							<h2 className="text-lg font-semibold text-gray-800">
								Confirm Delete
							</h2>
						</div>
						<p className="text-gray-600 mb-6">
							Are you sure you want to delete insurance{" "}
							<span className="font-semibold text-gray-800">
								{deleteTarget}
							</span>
							? This will also remove all associated records and cannot be
							undone.
						</p>
						<div className="flex gap-3 justify-end">
							<button
								onClick={() => setDeleteTarget(null)}
								disabled={deleteLoading}
								className="px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 font-medium transition-all"
							>
								Cancel
							</button>
							<button
								onClick={() => handleDelete(deleteTarget)}
								disabled={deleteLoading}
								className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white font-medium shadow transition-all flex items-center gap-2 disabled:opacity-75"
							>
								{deleteLoading ? (
									<>
										<svg
											className="animate-spin h-4 w-4"
											fill="none"
											viewBox="0 0 24 24"
										>
											<circle
												className="opacity-25"
												cx="12"
												cy="12"
												r="10"
												stroke="currentColor"
												strokeWidth="4"
											/>
											<path
												className="opacity-75"
												fill="currentColor"
												d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
											/>
										</svg>
										Deleting...
									</>
								) : (
									"Delete"
								)}
							</button>
						</div>
					</div>
				</div>
			)}
		</div>
	);
};

export default InsurancePage;