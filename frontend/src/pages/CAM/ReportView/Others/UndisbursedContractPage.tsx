import { useState, useEffect, useMemo } from "react";
import * as XLSX from "xlsx";
import api from "../../../../api/axiosInstance";
import { DEFAULT_PAGE_LIMIT } from "../../../../constants/DefaultValue";

interface Branch {
	branch_cd: string;
	branch_name: string;
}

interface UndisburseRow {
	appl_no: string;
	cust_name: string;
	brand: string;
	type_nm: string;
	net_finance: number | null;
	emp_name: string;
	branch: string;
	lease_no: string;
	adm_date: string | null;
}

const ROWS_PER_PAGE = DEFAULT_PAGE_LIMIT;

const TABLE_HEADERS = [
	"No.",
	"CAM No.",
	"Customer Name",
	"Collateral",
	"Total Net Finance",
	"CMO (Branch)",
	"Contract No.",
	"Last Approval Date",
];

function fmtNumber(v: number | null | undefined): string {
	if (v == null) return "";
	return new Intl.NumberFormat("id-ID").format(v);
}

function fmtDate(dateStr: string | null): string {
	if (!dateStr) return "";
	const d = new Date(dateStr);
	return d.toLocaleDateString("id-ID", { day: "2-digit", month: "long", year: "numeric" });
}

function getPageNumbers(current: number, total: number): (number | "…")[] {
	if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
	if (current <= 4) return [1, 2, 3, 4, 5, "…", total];
	if (current >= total - 3) return [1, "…", total - 4, total - 3, total - 2, total - 1, total];
	return [1, "…", current - 1, current, current + 1, "…", total];
}

function exportExcel(data: UndisburseRow[], branchName: string): void {
	const now = new Date().toLocaleDateString("id-ID", { day: "2-digit", month: "long", year: "numeric" });
	const rows: (string | number | null)[][] = [];

	rows.push([`List of Undisburse Contract`, null, null, null, null, null, null, null]);
	rows.push([`Branch : ${branchName}`, null, null, null, null, null, null, null]);
	rows.push([`Date : ${now}`, null, null, null, null, null, null, null]);
	rows.push(TABLE_HEADERS);

	let total = 0;
	data.forEach((r, i) => {
		const nf = r.net_finance ?? 0;
		total += nf;
		rows.push([
			i + 1,
			r.appl_no,
			r.cust_name,
			`${r.brand} ${r.type_nm}`.trim(),
			nf,
			`${r.emp_name} (${r.branch})`,
			r.lease_no,
			fmtDate(r.adm_date),
		]);
	});

	rows.push(["", "", "", "TOTAL", total, "", "", ""]);

	const ws = XLSX.utils.aoa_to_sheet(rows);
	ws["!cols"] = [
		{ wch: 5 }, { wch: 16 }, { wch: 28 }, { wch: 22 },
		{ wch: 18 }, { wch: 30 }, { wch: 16 }, { wch: 20 },
	];
	ws["!merges"] = [
		{ s: { r: 0, c: 0 }, e: { r: 0, c: 7 } },
		{ s: { r: 1, c: 0 }, e: { r: 1, c: 7 } },
		{ s: { r: 2, c: 0 }, e: { r: 2, c: 7 } },
	];

	const wb = XLSX.utils.book_new();
	XLSX.utils.book_append_sheet(wb, ws, "UndisburseContract");
	XLSX.writeFile(wb, "UndisburseContract.xlsx");
}

const UndisburseContractPage: React.FC = () => {
	const [branches, setBranches] = useState<Branch[]>([]);
	const [selectedBranch, setSelectedBranch] = useState<string>("");
	const [data, setData] = useState<UndisburseRow[]>([]);
	const [branchLoading, setBranchLoading] = useState<boolean>(true);
	const [loading, setLoading] = useState<boolean>(false);
	const [error, setError] = useState<string | null>(null);
	const [currentPage, setCurrentPage] = useState<number>(1);

	useEffect(() => {
		api.get<Branch[]>("/CAM/Others/UndisbursedContract/api/branches")
			.then((res) => setBranches(res.data))
			.catch(() => setError("Gagal memuat daftar cabang."))
			.finally(() => setBranchLoading(false));
	}, []);

	const handleBranchChange = async (branchCd: string) => {
		setSelectedBranch(branchCd);
		setData([]);
		setCurrentPage(1);
		setError(null);
		if (!branchCd) return;

		setLoading(true);
		try {
			const res = await api.get<UndisburseRow[]>("/CAM/Others/UndisbursedContract/api/data", {
				params: { branch_cd: branchCd },
			});
			setData(res.data);
		} catch {
			setError("Gagal memuat data. Silakan coba lagi.");
		} finally {
			setLoading(false);
		}
	};

	const handleExport = () => {
		if (!data.length) return;
		const branchName = branches.find((b) => b.branch_cd === selectedBranch)?.branch_name ?? selectedBranch;
		exportExcel(data, branchName);
	};

	const totalNetFinance = useMemo(
		() => data.reduce((sum, r) => sum + (r.net_finance ?? 0), 0),
		[data],
	);

	const totalPages = Math.ceil(data.length / ROWS_PER_PAGE);

	const paginatedData = useMemo(() => {
		const start = (currentPage - 1) * ROWS_PER_PAGE;
		return data.slice(start, start + ROWS_PER_PAGE);
	}, [data, currentPage]);

	const pageNumbers = useMemo(
		() => getPageNumbers(currentPage, totalPages),
		[currentPage, totalPages],
	);

	return (
		<div className="min-h-screen bg-gray-50 p-4 md:p-6">
			<div className="max-w-7xl mx-auto">

				<div className="mb-6">
					<h1 className="text-2xl font-semibold text-gray-800">List of Undisburse Contract</h1>
					<p className="text-sm text-gray-500 mt-1">
						Daftar kontrak yang belum dicairkan
					</p>
				</div>

				<div className="bg-white rounded-xl border border-gray-200 p-4 mb-6 flex flex-wrap gap-3 items-end">
					<div className="flex-1 min-w-[220px] max-w-sm">
						<label className="block text-xs font-medium text-gray-500 mb-1">
							Branch <span className="text-red-500 ml-1">*</span>
						</label>
						<select
							value={selectedBranch}
							onChange={(e) => handleBranchChange(e.target.value)}
							disabled={branchLoading}
							className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white text-gray-800
								focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500
								disabled:opacity-60 disabled:cursor-not-allowed"
						>
							<option value="">Select</option>
							{branches.map((b) => (
								<option key={b.branch_cd} value={b.branch_cd}>
									{b.branch_name}
								</option>
							))}
						</select>
					</div>

					<button
						onClick={handleExport}
						disabled={!data.length}
						className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-all
							bg-green-50 text-green-800 border border-green-200
							hover:bg-green-100 disabled:opacity-40 disabled:cursor-not-allowed"
					>
						Export to Excel
					</button>
				</div>

				{error && (
					<div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
						{error}
					</div>
				)}

				{loading && (
					<div className="py-16 text-center text-sm text-gray-400">Memuat data…</div>
				)}

				{!loading && !selectedBranch && (
					<div className="py-16 text-center text-sm text-gray-400 border border-dashed border-gray-300 rounded-xl">
						Pilih cabang untuk menampilkan data
					</div>
				)}

				{!loading && selectedBranch && data.length === 0 && !error && (
					<div className="py-16 text-center text-sm text-gray-400 border border-dashed border-gray-300 rounded-xl">
						Tidak ada data untuk cabang yang dipilih
					</div>
				)}

				{!loading && data.length > 0 && (
					<>
						<div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-4">
							<div className="bg-gray-50 rounded-lg p-3">
								<div className="text-xs text-gray-400 mb-1">Total Kontrak</div>
								<div className="text-lg font-semibold tabular-nums text-gray-800">
									{data.length}
								</div>
							</div>
							<div className="bg-gray-50 rounded-lg p-3 col-span-1 md:col-span-2">
								<div className="text-xs text-gray-400 mb-1">Total Net Finance</div>
								<div className="text-lg font-semibold tabular-nums text-gray-800">
									{fmtNumber(totalNetFinance)}
								</div>
							</div>
						</div>

						<div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
							<div className="overflow-x-auto">
								<table className="w-full border-collapse text-sm">
									<thead>
										<tr className="bg-gray-50">
											{TABLE_HEADERS.map((h) => (
												<th
													key={h}
													className="px-3 py-2 text-xs font-medium text-gray-500 border-b border-gray-200 text-center whitespace-nowrap"
												>
													{h}
												</th>
											))}
										</tr>
									</thead>
									<tbody>
										{paginatedData.map((row, idx) => {
											const globalIdx = (currentPage - 1) * ROWS_PER_PAGE + idx;
											return (
												<tr
													key={`${row.appl_no}-${globalIdx}`}
													className={globalIdx % 2 === 0 ? "bg-white" : "bg-gray-50"}
												>
													<td className="px-3 py-2 text-center border-b border-gray-100 text-gray-400 tabular-nums">
														{globalIdx + 1}
													</td>
													<td className="px-3 py-2 border-b border-gray-100 whitespace-nowrap text-gray-700">
														{row.appl_no}
													</td>
													<td className="px-3 py-2 border-b border-gray-100 whitespace-nowrap text-gray-700">
														{row.cust_name}
													</td>
													<td className="px-3 py-2 border-b border-gray-100 whitespace-nowrap text-gray-700">
														{`${row.brand} ${row.type_nm}`.trim()}
													</td>
													<td className="px-3 py-2 border-b border-gray-100 text-right tabular-nums whitespace-nowrap text-gray-800">
														{fmtNumber(row.net_finance)}
													</td>
													<td className="px-3 py-2 border-b border-gray-100 whitespace-nowrap text-gray-700">
														{row.emp_name}
														{row.branch && (
															<><br /><span className="text-gray-400 text-xs">({row.branch})</span></>
														)}
													</td>
													<td className="px-3 py-2 border-b border-gray-100 whitespace-nowrap text-gray-700">
														{row.lease_no}
													</td>
													<td className="px-3 py-2 border-b border-gray-100 whitespace-nowrap text-gray-700">
														{fmtDate(row.adm_date)}
													</td>
												</tr>
											);
										})}
									</tbody>
									<tfoot>
										<tr className="bg-blue-50 font-semibold">
											<td colSpan={4} className="px-3 py-2 text-right text-gray-700 border-t border-gray-200">
												TOTAL
											</td>
											<td className="px-3 py-2 text-right tabular-nums text-gray-800 border-t border-gray-200">
												{fmtNumber(totalNetFinance)}
											</td>
											<td colSpan={3} className="border-t border-gray-200" />
										</tr>
									</tfoot>
								</table>
							</div>

							{totalPages > 1 && (
								<div className="flex items-center justify-center gap-1.5 py-3 border-t border-gray-200 flex-wrap">
									<button
										onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
										disabled={currentPage === 1}
										className="px-3 py-1 text-sm rounded border border-gray-300
											disabled:opacity-40 disabled:cursor-not-allowed hover:bg-gray-50 transition-colors"
									>
										Previous
									</button>

									{pageNumbers.map((p, i) =>
										p === "…" ? (
											<span key={`ellipsis-${i}`} className="px-2 py-1 text-sm text-gray-400">
												…
											</span>
										) : (
											<button
												key={p}
												onClick={() => setCurrentPage(p as number)}
												className={`px-3 py-1 text-sm rounded border transition-colors ${currentPage === p
													? "bg-blue-600 text-white border-blue-600"
													: "border-gray-300 hover:bg-gray-50"
													}`}
											>
												{p}
											</button>
										),
									)}

									<button
										onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
										disabled={currentPage === totalPages}
										className="px-3 py-1 text-sm rounded border border-gray-300
											disabled:opacity-40 disabled:cursor-not-allowed hover:bg-gray-50 transition-colors"
									>
										Next
									</button>
								</div>
							)}
						</div>
					</>
				)}
			</div>
		</div>
	);
};

export default UndisburseContractPage;