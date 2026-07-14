import React, { useEffect, useState, useCallback, useRef } from "react";
import api from "../../../api/axiosInstance";
import * as XLSX from "xlsx";
interface Branch {
	branchCd: string;
	branchName: string;
	cityName?: string;
}
interface DealerDeletedRow {
	form_no: string;
	branch_name: string;
	supp: string;
	name: string;
	address: string;
	created_by: string;
	create_date: string;
	delete_by: string;
	delete_date: string;
	reason: string;
}

type SearchType = "1" | "2" | "";

const DealerDeletedReportPage: React.FC = () => {
	const [branches, setBranches] = useState<Branch[]>([]);
	const [selectedBranch, setSelectedBranch] = useState<string>("");
	const [searchType, setSearchType] = useState<SearchType>("");
	const [searchVal, setSearchVal] = useState("");
	const [rows, setRows] = useState<DealerDeletedRow[]>([]);
	const [loading, setLoading] = useState(false);
	const [searched, setSearched] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const printRef = useRef<HTMLDivElement>(null);

	const isConsolidate = selectedBranch === "000";

	useEffect(() => {
		api
			.get('/MasterData/api/branches')
			.then((res) => {
				setBranches(res.data);
				if (res.data.length > 0) setSelectedBranch(res.data[0].branchCd);
			})
			.catch(console.error);
	}, []);

	const handleSearch = useCallback(async () => {
		setLoading(true);
		setError(null);
		setSearched(false);
		try {
			const res = await api.get(
				'/MasterData/api/dealer-deleted-report',
				{
					params: {
						branch: selectedBranch,
						cekcek: searchType,
						lempar: searchType !== "" ? searchVal : "",
					},
				}
			);
			setRows(res.data.data);
			setSearched(true);
		} catch (err) {
			console.error(err);
			setError("Failed to load data. Please try again.");
		} finally {
			setLoading(false);
		}
	}, [selectedBranch, searchType, searchVal]);

	const handleExport = () => {
		const branchLabel =
			branches.find((b) => b.branchCd === selectedBranch)?.branchName ?? selectedBranch

		const headers = isConsolidate
			? ["No.", "Branch", "Dealer ID", "Dealer Name", "Address", "Created By", "Create Date", "Delete By", "Delete Date", "Reason"]
			: ["No.", "Dealer ID", "Dealer Name", "Address", "Created By", "Create Date", "Delete By", "Delete Date", "Reason"];

		const data = rows.map((r, idx) =>
			isConsolidate
				? [idx + 1, r.branch_name, r.supp, r.name, r.address, r.created_by, r.create_date, r.delete_by, r.delete_date, r.reason]
				: [idx + 1, r.supp, r.name, r.address, r.created_by, r.create_date, r.delete_by, r.delete_date, r.reason]
		);

		const ws = XLSX.utils.aoa_to_sheet([
			["DEALER DELETED REPORT"],
			[`As Of ${new Date().toLocaleDateString("en-GB", { day: "2-digit", month: "long", year: "numeric" })}`],
			[],
			[`Branch : ${branchLabel}`],
			[],
			headers,
			...data,
		]);
		const wb = XLSX.utils.book_new();
		XLSX.utils.book_append_sheet(wb, ws, "Dealer Deleted Report");
		XLSX.writeFile(wb, "Dealer_Deleted_Report.xlsx");
	};

	const handlePrint = () => window.print();

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<style>{`
				@media print {
					.no-print { display: none !important; }
					.print-only { display: block !important; }
					body { font-size: 11px; }
				}
				.print-only { display: none; }
			`}</style>

			<div className="max-w-7xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6 mb-6 no-print">
					<div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2 mb-6">
						<div>
							<h1 className="text-2xl md:text-3xl font-bold text-gray-800">
								Dealer Deleted Report
							</h1>
							<p className="text-gray-500 mt-1 text-sm">
								As of{" "}
								{new Date().toLocaleDateString("en-GB", {
									day: "2-digit",
									month: "short",
									year: "numeric",
								})}
							</p>
						</div>
					</div>

					<div className="grid grid-cols-1 md:grid-cols-2 gap-6">
						<div>
							<label className="block text-sm font-medium text-gray-700 mb-1">
								Branch
							</label>
							<select
								value={selectedBranch}
								onChange={(e) => setSelectedBranch(e.target.value)}
								className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all bg-white"
							>
								{branches.map((b, idx) => (
									<option key={b.branchCd || idx} value={b.branchCd}>
										{b.branchName}
									</option>
								))}
							</select>
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700 mb-2">
								Search By
							</label>
							<div className="flex flex-col gap-2">
								<div className="flex items-center gap-3">
									<label className="flex items-center gap-2 cursor-pointer select-none">
										<input
											type="radio"
											name="searchType"
											value="1"
											checked={searchType === "1"}
											onChange={() => {
												setSearchType("1");
												setSearchVal("");
											}}
											className="accent-blue-600"
										/>
										<span className="text-sm text-gray-700">Dealer ID</span>
									</label>
									{searchType === "1" && (
										<input
											type="text"
											placeholder="Enter Dealer ID..."
											value={searchVal}
											onChange={(e) => setSearchVal(e.target.value)}
											onKeyDown={(e) => e.key === "Enter" && handleSearch()}
											className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all"
										/>
									)}
								</div>

								<div className="flex items-center gap-3">
									<label className="flex items-center gap-2 cursor-pointer select-none">
										<input
											type="radio"
											name="searchType"
											value="2"
											checked={searchType === "2"}
											onChange={() => {
												setSearchType("2");
												setSearchVal("");
											}}
											className="accent-blue-600"
										/>
										<span className="text-sm text-gray-700">Dealer Name</span>
									</label>
									{searchType === "2" && (
										<input
											type="text"
											placeholder="Enter dealer name..."
											value={searchVal}
											onChange={(e) => setSearchVal(e.target.value)}
											onKeyDown={(e) => e.key === "Enter" && handleSearch()}
											className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all"
										/>
									)}
								</div>
							</div>
						</div>
					</div>

					<div className="flex flex-wrap gap-3 mt-6">
						<button
							onClick={handleSearch}
							disabled={loading}
							className={`bg-gradient-to-r from-blue-600 to-indigo-700 hover:from-blue-700 hover:to-indigo-800 text-white px-6 py-2.5 rounded-lg font-medium shadow hover:shadow-lg transition-all flex items-center gap-2 ${loading ? "opacity-75 cursor-not-allowed" : ""
								}`}
						>
							{loading ? (
								<>
									<svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
										<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
										<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
									</svg>
									Searching...
								</>
							) : (
								<>
									<svg className="w-4 h-4" fill="none" viewBox="0 0 24 24">
										<path d="M15.5 14H14.71L14.43 13.73C15.41 12.59 16 11.11 16 9.5C16 5.91 13.09 3 9.5 3C5.91 3 3 5.91 3 9.5C3 13.09 5.91 16 9.5 16C11.11 16 12.59 15.41 13.73 14.43L14 14.71V15.5L19 20.49L20.49 19L15.5 14ZM9.5 14C7.01 14 5 11.99 5 9.5C5 7.01 7.01 5 9.5 5C11.99 5 14 7.01 14 9.5C14 11.99 11.99 14 9.5 14Z" fill="currentColor" />
									</svg>
									Search
								</>
							)}
						</button>

						{searched && rows.length > 0 && (
							<>
								<button
									onClick={handlePrint}
									className="bg-gradient-to-r from-gray-600 to-gray-700 hover:from-gray-700 hover:to-gray-800 text-white px-6 py-2.5 rounded-lg font-medium shadow hover:shadow-lg transition-all flex items-center gap-2"
								>
									<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" />
									</svg>
									Print
								</button>

								<button
									onClick={handleExport}
									className="bg-gradient-to-r from-green-600 to-emerald-700 hover:from-green-700 hover:to-emerald-800 text-white px-6 py-2.5 rounded-lg font-medium shadow hover:shadow-lg transition-all flex items-center gap-2"
								>
									<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
									</svg>
									Export to Excel
								</button>
							</>
						)}
					</div>
				</div>

				{error && (
					<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 flex items-center justify-between no-print">
						<span>{error}</span>
						<button onClick={handleSearch} className="ml-4 underline text-sm text-red-900">
							Retry
						</button>
					</div>
				)}

				{searched && (
					<div ref={printRef} className="bg-white rounded-2xl shadow-lg p-6">
						<div className="hidden print:block text-center mb-4">
							<p className="text-lg font-bold">DEALER DELETED REPORT</p>
							<p className="text-sm">
								As of{" "}
								{new Date().toLocaleDateString("en-GB", {
									day: "2-digit",
									month: "short",
									year: "numeric",
								})}
							</p>
							<p className="text-sm mt-1">
								Branch:{" "}
								{branches.find((b) => b.branchCd === selectedBranch)?.branchName ?? selectedBranch}
							</p>
						</div>

						<div className="flex items-center justify-between mb-4 no-print">
							<div>
								<h2 className="text-lg font-semibold text-gray-800">Results</h2>
								<p className="text-sm text-gray-500">
									Branch:{" "}
									<span className="font-medium">
										{branches.find((b) => b.branchCd === selectedBranch)?.branchName ?? selectedBranch}
									</span>
									{" — "}
									<span className="font-medium text-blue-700">
										{rows.length} record{rows.length !== 1 ? "s" : ""}
									</span>
								</p>
							</div>
						</div>

						<div className="overflow-x-auto rounded-lg border border-gray-200">
							<table className="w-full text-sm">
								<thead className="bg-gradient-to-r from-gray-50 to-gray-100">
									<tr>
										<th className="py-3 px-4 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider w-10">
											No.
										</th>
										{isConsolidate && (
											<th className="py-3 px-4 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
												Branch
											</th>
										)}
										<th className="py-3 px-4 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
											Dealer ID
										</th>
										<th className="py-3 px-4 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
											Dealer Name
										</th>
										<th className="py-3 px-4 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
											Address
										</th>
										<th className="py-3 px-4 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
											Created By
										</th>
										<th className="py-3 px-4 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
											Create Date
										</th>
										<th className="py-3 px-4 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
											Delete By
										</th>
										<th className="py-3 px-4 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
											Delete Date
										</th>
										<th className="py-3 px-4 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
											Reason
										</th>
									</tr>
								</thead>
								<tbody className="divide-y divide-gray-200">
									{rows.length === 0 ? (
										<tr>
											<td
												colSpan={isConsolidate ? 10 : 9}
												className="py-10 text-center text-gray-500"
											>
												<div className="flex flex-col items-center justify-center">
													<svg className="w-14 h-14 text-gray-300 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
														<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
													</svg>
													<p className="text-base">No records found</p>
													<p className="text-xs mt-1">Try adjusting your search filters</p>
												</div>
											</td>
										</tr>
									) : (
										rows.map((row, idx) => (
											<tr
												key={idx}
												className={`hover:bg-blue-50 transition-colors ${idx % 2 === 0 ? "bg-white" : "bg-gray-50"
													}`}
											>
												<td className="py-3 px-4 text-center text-gray-600 font-medium">
													{idx + 1}
												</td>
												{isConsolidate && (
													<td className="py-3 px-4 text-gray-700">{row.branch_name}</td>
												)}
												<td className="py-3 px-4 font-semibold text-gray-900">
													{row.supp}
												</td>
												<td className="py-3 px-4 text-gray-800">{row.name}</td>
												<td className="py-3 px-4 text-gray-600 max-w-xs">{row.address}</td>
												<td className="py-3 px-4 text-gray-600">{row.created_by}</td>
												<td className="py-3 px-4 text-gray-600 whitespace-nowrap">
													{row.create_date}
												</td>
												<td className="py-3 px-4 text-gray-600">{row.delete_by}</td>
												<td className="py-3 px-4 whitespace-nowrap">
													<span className="bg-red-100 text-red-700 px-2 py-0.5 rounded text-xs font-medium">
														{row.delete_date}
													</span>
												</td>
												<td className="py-3 px-4 text-gray-600">{row.reason}</td>
											</tr>
										))
									)}
								</tbody>
							</table>
						</div>

						{rows.length > 0 && (
							<p className="text-sm text-gray-500 mt-3 text-right">
								Total:{" "}
								<span className="font-semibold text-gray-800">{rows.length}</span>{" "}
								record{rows.length !== 1 ? "s" : ""}
							</p>
						)}
					</div>
				)}
			</div>
		</div>
	);
};

export default DealerDeletedReportPage;