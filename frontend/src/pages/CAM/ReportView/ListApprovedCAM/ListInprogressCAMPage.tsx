import React, { useEffect, useState, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import api from "../../../../api/axiosInstance";
import Pagination from "../../../../helpers/Pagination";
import { DEFAULT_PAGE_LIMIT } from "../../../../constants/DefaultValue";

interface CAMRecord {
	appl_no: string;
	cam_no: string;
	cons_leas: string;
	apless: string;
	has_guarantor: string;
	lessee_nm: string;
	lessee_tp: string;
	brand_type: string;
	net_finance: number;
	interest: number;
	tenor: number;
	create_date: string;
	cmo: string;
	approver: string;
	condition: string;
	revision: string;
}

interface GrandTotalGroup {
	fin: number;
	unit: number;
}

interface GrandTotals {
	passenger_new: GrandTotalGroup;
	passenger_used: GrandTotalGroup;
	commercial_new: GrandTotalGroup;
	commercial_used: GrandTotalGroup;
	grand_fin: number;
	grand_unit: number;
}

interface Branch {
	branch_cd: string;
	branch_name: string;
}

interface ApiResponse {
	data: CAMRecord[];
	total: number;
	grand_totals: GrandTotals;
	branches: Branch[];
	branch_locked: boolean;
	access_level: string;
}

const formatNumber = (n: number, decimals = 0) =>
	n.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });

const GrandTotalTable: React.FC<{ totals: GrandTotals; dateLabel: string }> = ({
	totals,
	dateLabel,
}) => (
	<div className="mt-6 overflow-x-auto">
		<p className="text-sm font-semibold text-gray-700 mb-2 underline">
			Grand Total* ({dateLabel}):
		</p>
		<table className="border border-gray-300 border-collapse text-sm w-auto">
			<thead>
				<tr className="bg-gray-100">
					<th className="border border-gray-300 px-4 py-2 text-left">Type</th>
					<th className="border border-gray-300 px-4 py-2 text-left">Condition</th>
					<th className="border border-gray-300 px-4 py-2 text-right">Net Finance</th>
					<th className="border border-gray-300 px-4 py-2 text-right">Units</th>
				</tr>
			</thead>
			<tbody>
				{[
					{ label: "Passenger", cond: "New", g: totals.passenger_new },
					{ label: "Passenger", cond: "Used", g: totals.passenger_used },
					{ label: "Commercial", cond: "New", g: totals.commercial_new },
					{ label: "Commercial", cond: "Used", g: totals.commercial_used },
				].map(({ label, cond, g }) => (
					<tr key={`${label}-${cond}`} className="hover:bg-gray-50">
						<td className="border border-gray-300 px-4 py-2">{label}</td>
						<td className="border border-gray-300 px-4 py-2">{cond}</td>
						<td className="border border-gray-300 px-4 py-2 text-right">{formatNumber(g.fin)}</td>
						<td className="border border-gray-300 px-4 py-2 text-right">{g.unit}</td>
					</tr>
				))}
				<tr className="bg-gray-100 font-semibold">
					<td colSpan={2} className="border border-gray-300 px-4 py-2 text-center">Grand Total</td>
					<td className="border border-gray-300 px-4 py-2 text-right">{formatNumber(totals.grand_fin)}</td>
					<td className="border border-gray-300 px-4 py-2 text-right">{totals.grand_unit}</td>
				</tr>
			</tbody>
		</table>
		<p className="text-xs text-gray-500 mt-1 italic">
			*Grand Total Net Finance and Unit based on latest revised CAM (if any)
		</p>
	</div>
);

const ListInprogressCAMPage: React.FC = () => {
	const [records, setRecords] = useState<CAMRecord[]>([]);
	const [total, setTotal] = useState(0);
	const [grandTotals, setGrandTotals] = useState<GrandTotals | null>(null);
	const [branches, setBranches] = useState<Branch[]>([]);
	const [branchLocked, setBranchLocked] = useState(false);
	const [page, setPage] = useState(1);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [hasSearched, setHasSearched] = useState(false);

	const [startDt, setStartDt] = useState("");
	const [endDt, setEndDt] = useState("");
	const [lesseeNm, setLesseeNm] = useState("");
	const [branch, setBranch] = useState("");

	const limit = DEFAULT_PAGE_LIMIT;
	const navigate = useNavigate();
	const printRef = useRef<HTMLDivElement>(null);

	const fetchRecords = useCallback(async (pg = page) => {
		setLoading(true);
		setError(null);
		try {
			const response = await api.get<ApiResponse>("/CAM/api/list/inprogress", {
				params: {
					page: pg,
					limit,
					lessee_nm: lesseeNm,
					branch,
					start_dt: startDt,
					end_dt: endDt,
				},
			});
			setRecords(response.data.data);
			setTotal(response.data.total);
			setGrandTotals(response.data.grand_totals);
			setBranches(response.data.branches);
			setBranchLocked(response.data.branch_locked);
			setHasSearched(true);
		} catch (err) {
			if (err) return;
			console.error(err);
			setError("Failed to load data. Please try again.");
		} finally {
			setLoading(false);
		}
	}, [page, limit, lesseeNm, branch, startDt, endDt]);

	useEffect(() => {
		api.get<ApiResponse>("/CAM/api/list/inprogress", { params: { page: 1, limit: 1 } })
			.then((r) => { setBranches(r.data.branches); setBranchLocked(r.data.branch_locked); })
			.catch(() => { });
	}, []);

	const totalPages = Math.ceil(total / limit);

	const handlePreview = () => {
		setPage(1);
		fetchRecords(1);
	};

	const handlePageChange = (p: number) => {
		setPage(p);
		fetchRecords(p);
	};

	const handleExportCSV = () => {
		const params = new URLSearchParams({
			lessee_nm: lesseeNm,
			branch,
			start_dt: startDt,
			end_dt: endDt,
		});
		window.open(`/CAM/api/list/inprogress/export/csv?${params.toString()}`);
	};

	const handlePrint = () => window.print();

	const handleViewCAM = (r: CAMRecord) => {
		const guarantor = r.has_guarantor === "0" ? 1 : 2;
		const finType = r.cons_leas === "C" ? 1 : 2;
		const indCor = r.lessee_tp === "PR" ? 1 : 2;
		const c2c = r.supp === "999999" ? 1 : 0;
		const newCar = r.condition.toUpperCase() === "NEW" ? 2 : 1;
		navigate(
			`/view-main?id1=${finType}&id2=${indCor}&id3=1&id4=${guarantor}` +
			`&id5=${newCar}&id6=Edit&id7=${r.tenor}&id8=${c2c}` +
			`&apless=${encodeURIComponent(r.apless)}&applno=${r.appl_no}`
		);
	};

	const dateLabel = startDt && endDt ? `${startDt} – ${endDt}` : "All Dates";

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-7xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6 mb-6">

					<div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
						<div>
							<h1 className="text-2xl md:text-3xl font-bold text-gray-800">List In Progress CAM</h1>
							<p className="text-gray-600 mt-1">Filter and preview in-progress CAM records</p>
						</div>
						{hasSearched && (
							<span className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm font-medium self-start">
								Total: {total}
							</span>
						)}
					</div>

					<div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6 print:hidden">
						<div>
							<label className="block text-sm font-medium text-gray-700 mb-1">Start Create Date</label>
							<input
								type="date"
								value={startDt}
								onChange={(e) => setStartDt(e.target.value)}
								className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all"
							/>
						</div>
						<div>
							<label className="block text-sm font-medium text-gray-700 mb-1">End Create Date</label>
							<input
								type="date"
								value={endDt}
								onChange={(e) => setEndDt(e.target.value)}
								className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all"
							/>
						</div>
						<div>
							<label className="block text-sm font-medium text-gray-700 mb-1">Customer Name</label>
							<input
								type="text"
								placeholder="Search by customer name..."
								value={lesseeNm}
								onChange={(e) => setLesseeNm(e.target.value)}
								onKeyDown={(e) => { if (e.key === "Enter") handlePreview(); }}
								className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all"
							/>
						</div>
						<div>
							<label className="block text-sm font-medium text-gray-700 mb-1">Branch</label>
							<select
								value={branch}
								onChange={(e) => setBranch(e.target.value)}
								disabled={branchLocked}
								className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all bg-white disabled:bg-gray-100 disabled:cursor-not-allowed"
							>
								<option value="">Select</option>
								{branches.map((b) => (
									<option key={b.branch_cd} value={b.branch_cd}>{b.branch_name}</option>
								))}
							</select>
						</div>
					</div>

					<div className="flex flex-wrap gap-3 mb-6 print:hidden">
						<button
							onClick={handlePreview}
							disabled={loading}
							className={`bg-gradient-to-r from-blue-600 to-indigo-700 hover:from-blue-700 hover:to-indigo-800 text-white px-6 py-2.5 rounded-lg font-medium shadow-md hover:shadow-lg transition-all flex items-center gap-2 ${loading ? "opacity-75 cursor-not-allowed" : ""}`}
						>
							{loading ? (
								<>
									<svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
										<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
										<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
									</svg>
									Loading...
								</>
							) : "Preview"}
						</button>

						{hasSearched && (
							<>
								<button
									onClick={handlePrint}
									className="bg-gray-600 hover:bg-gray-700 text-white px-6 py-2.5 rounded-lg font-medium shadow-md hover:shadow-lg transition-all flex items-center gap-2"
								>
									<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" />
									</svg>
									Print
								</button>

								<button
									onClick={handleExportCSV}
									className="bg-green-600 hover:bg-green-700 text-white px-6 py-2.5 rounded-lg font-medium shadow-md hover:shadow-lg transition-all flex items-center gap-2"
								>
									<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
									</svg>
									Export to Excel
								</button>
							</>
						)}
					</div>

					{error && (
						<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
							{error}
							<button onClick={() => fetchRecords()} className="ml-4 text-red-900 underline">Retry</button>
						</div>
					)}

					{hasSearched && (
						<div ref={printRef}>
							<div className="overflow-x-auto rounded-lg border border-gray-200">
								<table className="w-full text-sm">
									<thead className="bg-gradient-to-r from-gray-50 to-gray-100">
										<tr>
											<th className="py-3 px-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider w-10">No.</th>
											<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">CAM No.</th>
											<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Customer Name</th>
											<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Brand / Type</th>
											<th className="py-3 px-4 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Net Finance</th>
											<th className="py-3 px-4 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Interest (%)</th>
											<th className="py-3 px-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Tenor (Mo.)</th>
											<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Create Date</th>
											<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">CMO</th>
											<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
										</tr>
									</thead>
									<tbody className="divide-y divide-gray-200">
										{records.length === 0 && !loading ? (
											<tr>
												<td colSpan={10} className="py-10 px-6 text-center text-gray-500">
													<div className="flex flex-col items-center justify-center">
														<svg className="w-16 h-16 text-gray-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
															<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
														</svg>
														<p className="text-lg">No records found</p>
														<p className="text-sm mt-1">Try adjusting your filter criteria</p>
													</div>
												</td>
											</tr>
										) : (
											<>
												{records.map((r, idx) => (
													<tr
														key={r.appl_no}
														className={`hover:bg-blue-50 transition-colors cursor-pointer ${idx % 2 === 0 ? "bg-white" : "bg-gray-50"}`}
														onClick={() => handleViewCAM(r)}
													>
														<td className="py-3 px-4 text-center text-gray-600">
															{(page - 1) * limit + idx + 1}
														</td>
														<td className="py-3 px-4 whitespace-nowrap text-blue-600 font-medium hover:underline">
															{r.cam_no}
														</td>
														<td className="py-3 px-4 text-gray-700 font-medium">{r.lessee_nm}</td>
														<td className="py-3 px-4 whitespace-nowrap text-gray-600">{r.brand_type}</td>
														<td className="py-3 px-4 text-right whitespace-nowrap text-gray-600 font-mono">
															{formatNumber(r.net_finance)}
														</td>
														<td className="py-3 px-4 text-right whitespace-nowrap text-gray-600 font-mono">
															{formatNumber(r.interest, 4)}
														</td>
														<td className="py-3 px-4 text-center text-gray-600">{r.tenor}</td>
														<td className="py-3 px-4 whitespace-nowrap text-gray-600">{r.create_date}</td>
														<td className="py-3 px-4 whitespace-nowrap text-gray-600">{r.cmo}</td>
														<td className="py-3 px-4 whitespace-nowrap text-gray-600">{r.approver}</td>
													</tr>
												))}
												{loading && (
													<tr>
														<td colSpan={10} className="py-4 px-6 text-center">
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
									onPageChange={handlePageChange}
									totalItems={total}
									itemsPerPage={limit}
									className="mt-6"
								/>
							)}

							{grandTotals && <GrandTotalTable totals={grandTotals} dateLabel={dateLabel} />}
						</div>
					)}

				</div>
			</div>
		</div>
	);
};

export default ListInprogressCAMPage;