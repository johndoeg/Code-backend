import { useState, useEffect, useMemo } from "react";
import api from "../../../../api/axiosInstance";
import AsOfDatePicker from "../../../../components/AsOfDatePickerComponent";
import { DEFAULT_PAGE_LIMIT } from "../../../../constants/DefaultValue";

interface Branch { branch_cd: string; branch_name: string; }

interface SummaryRow {
	periode: string; bulan: string;
	if_osp: string | number; if_ar: string | number;
	if_unit: string | number; if_rundownosp: string | number;
	sl_osp: string | number; sl_ar: string | number;
	sl_unit: string | number; sl_rundownosp: string | number;
	total_osp: string | number; total_ar: string | number;
	total_unit: string | number; total_rundownosp: string | number;
}

interface DetailRow {
	appl_no: string; lessee_nm: string;
	ntf: string | number; osp: string | number; ar: string | number;
	payment: number; tenor: number;
}

const toISO = (d: Date) => d.toISOString().split("T")[0];

function getPageNumbers(cur: number, total: number): (number | "…")[] {
	if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
	if (cur <= 4) return [1, 2, 3, 4, 5, "…", total];
	if (cur >= total - 3) return [1, "…", total - 4, total - 3, total - 2, total - 1, total];
	return [1, "…", cur - 1, cur, cur + 1, "…", total];
}

const ROWS_PER_PAGE = DEFAULT_PAGE_LIMIT;

interface DetailModalProps {
	periode: string;
	bulan: string;
	params: { start_dt: string; end_dt: string; until: string; branch_cd: string };
	onClose: () => void;
}

function DetailModal({ periode, bulan, params, onClose }: DetailModalProps) {
	const [rows, setRows] = useState<DetailRow[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		api.get<DetailRow[]>("/CAM/Others/SummaryRundownOSP/api/detail", {
			params: { ...params, bulan: periode },
		})
			.then((res) => setRows(res.data))
			.catch(() => setError("Gagal memuat detail."))
			.finally(() => setLoading(false));
	}, [periode, params]);

	const TH = "px-3 py-2 text-xs font-semibold text-gray-600 bg-gray-50 border border-gray-300 text-center whitespace-nowrap";
	const TD = "px-3 py-1.5 text-sm border border-gray-200";

	return (
		<div className="fixed inset-0 z-50 flex items-center justify-center">
			<div className="absolute inset-0 bg-black/40" onClick={onClose} />
			<div className="relative bg-white rounded-xl shadow-2xl w-full max-w-5xl max-h-[85vh] flex flex-col mx-4">

				<div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
					<div>
						<h2 className="font-semibold text-gray-800">Detail — {bulan}</h2>
						<p className="text-xs text-gray-400 mt-0.5">Periode: {periode}</p>
					</div>
					<button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">✕</button>
				</div>

				<div className="overflow-auto flex-1">
					{loading && <div className="py-10 text-center text-sm text-gray-400">Memuat data…</div>}
					{error && <div className="py-10 text-center text-sm text-red-500">{error}</div>}
					{!loading && !error && rows.length === 0 && (
						<div className="py-10 text-center text-sm text-gray-400">Tidak ada data</div>
					)}
					{!loading && rows.length > 0 && (
						<table className="w-full border-collapse text-sm">
							<thead className="sticky top-0">
								<tr>
									<th className={TH} style={{ width: 50 }}>No.</th>
									<th className={TH}>CAM No.</th>
									<th className={TH}>Customer Name</th>
									<th className={TH}>Net Finance</th>
									<th className={TH}>OSP</th>
									<th className={TH}>AR</th>
									<th className={TH}>Payment of Tenor</th>
								</tr>
							</thead>
							<tbody>
								{rows.map((r, i) => (
									<tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-gray-50"}>
										<td className={TD + " text-center"}>{i + 1}</td>
										<td className={TD + " whitespace-nowrap"}>{r.appl_no}</td>
										<td className={TD}>{r.lessee_nm}</td>
										<td className={TD + " text-right tabular-nums"}>{r.ntf}</td>
										<td className={TD + " text-right tabular-nums"}>{r.osp}</td>
										<td className={TD + " text-right tabular-nums"}>{r.ar}</td>
										<td className={TD + " text-center"}>{r.payment} of {r.tenor}</td>
									</tr>
								))}
							</tbody>
						</table>
					)}
				</div>
			</div>
		</div>
	);
}

const SummaryRundownOSP: React.FC = () => {
	const today = new Date();

	const [startDt, setStartDt] = useState<Date>(today);
	const [endDt, setEndDt] = useState<Date>(today);
	const [until, setUntil] = useState<Date>(today);
	const [branchCd, setBranchCd] = useState<string>("");

	const [branches, setBranches] = useState<Branch[]>([]);
	const [summaryRows, setSummaryRows] = useState<SummaryRow[]>([]);
	const [loading, setLoading] = useState<boolean>(false);
	const [branchLoading, setBranchLoading] = useState<boolean>(true);
	const [error, setError] = useState<string | null>(null);
	const [hasSearched, setHasSearched] = useState<boolean>(false);
	const [currentPage, setCurrentPage] = useState<number>(1);

	const [detailRow, setDetailRow] = useState<SummaryRow | null>(null);

	useEffect(() => {
		api.get<Branch[]>("/CAM/Others/SummaryRundownOSP/api/branches")
			.then((res) => setBranches(res.data))
			.catch(() => { })
			.finally(() => setBranchLoading(false));
	}, []);

	const filterParams = useMemo(() => ({
		start_dt: toISO(startDt),
		end_dt: toISO(endDt),
		until: toISO(until),
		branch_cd: branchCd,
	}), [startDt, endDt, until, branchCd]);

	const handlePreview = async () => {
		setLoading(true);
		setError(null);
		setSummaryRows([]);
		setCurrentPage(1);
		setHasSearched(true);
		try {
			const res = await api.get<SummaryRow[]>("/CAM/Others/SummaryRundownOSP/api/summary", {
				params: filterParams,
			});
			setSummaryRows(res.data);
		} catch {
			setError("Gagal memuat data. Silakan coba lagi.");
		} finally {
			setLoading(false);
		}
	};

	const totalPages = Math.ceil(summaryRows.length / ROWS_PER_PAGE);
	const paginated = useMemo(
		() => summaryRows.slice((currentPage - 1) * ROWS_PER_PAGE, currentPage * ROWS_PER_PAGE),
		[summaryRows, currentPage],
	);
	const pageNumbers = useMemo(() => getPageNumbers(currentPage, totalPages), [currentPage, totalPages]);

	const TH = "px-2 py-2 text-xs font-semibold text-gray-600 bg-gray-50 border border-gray-300 text-center whitespace-nowrap";
	const TD = "px-2 py-1.5 text-xs border border-gray-200 text-right tabular-nums";
	const TDC = "px-2 py-1.5 text-xs border border-gray-200 text-center";

	return (
		<div className="min-h-screen bg-gray-50 p-4 md:p-6">
			<div className="max-w-full mx-auto">

				<div className="mb-6">
					<h1 className="text-2xl font-semibold text-gray-800">Summary Rundown OSP</h1>
				</div>

				<div className="bg-white rounded-xl border border-gray-200 p-4 mb-6">
					<div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mb-4">
						<AsOfDatePicker
							label="Start Disbursement Date"
							value={startDt}
							onChange={(d) => { if (d) { setStartDt(d); if (d > endDt) setEndDt(d); } }}
							maxDate={endDt}
							required
						/>
						<AsOfDatePicker
							label="End Disbursement Date"
							value={endDt}
							onChange={(d) => { if (d) setEndDt(d); }}
							minDate={startDt}
							required
						/>
						<AsOfDatePicker
							label="Month Until"
							value={until}
							onChange={(d) => { if (d) setUntil(d); }}
							required
						/>

						<div>
							<label className="block text-xs font-medium text-gray-500 mb-1">
								Branch
							</label>
							<select
								value={branchCd}
								onChange={(e) => setBranchCd(e.target.value)}
								disabled={branchLoading}
								className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white
									focus:outline-none focus:ring-2 focus:ring-blue-500
									disabled:opacity-60 disabled:cursor-not-allowed"
							>
								<option value="">Select</option>
								{branches.map((b) => (
									<option key={b.branch_cd} value={b.branch_cd}>{b.branch_name}</option>
								))}
							</select>
						</div>
					</div>

					<button
						onClick={handlePreview}
						disabled={loading}
						className="px-4 py-2 text-sm font-medium rounded-lg bg-blue-50 text-blue-800
							border border-blue-200 hover:bg-blue-100 disabled:opacity-40 disabled:cursor-not-allowed"
					>
						{loading ? "Memuat…" : "Preview"}
					</button>
				</div>

				{error && (
					<div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
						{error}
					</div>
				)}

				{loading && <div className="py-12 text-center text-sm text-gray-400">Memuat data…</div>}

				{!loading && !hasSearched && (
					<div className="py-16 text-center text-sm text-gray-400 border border-dashed border-gray-300 rounded-xl">
						Atur filter dan klik <span className="font-medium">Preview</span> untuk menampilkan data
					</div>
				)}
				{!loading && hasSearched && summaryRows.length === 0 && !error && (
					<div className="py-16 text-center text-sm text-gray-400 border border-dashed border-gray-300 rounded-xl">
						Tidak ada data untuk filter yang dipilih
					</div>
				)}

				{!loading && summaryRows.length > 0 && (
					<div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
						<div className="overflow-x-auto">
							<table className="w-full border-collapse">
								<thead>
									<tr>
										<th rowSpan={2} className={TH} style={{ width: "10%" }}>Period</th>
										<th colSpan={4} className={TH + " border-l border-blue-300 bg-blue-50 text-blue-700"}>
											Installment Financing
										</th>
										<th colSpan={4} className={TH + " border-l border-amber-300 bg-amber-50 text-amber-700"}>
											Sale &amp; Leaseback
										</th>
										<th colSpan={4} className={TH + " border-l border-green-300 bg-green-50 text-green-700"}>
											Grand Total
										</th>
										<th rowSpan={2} className={TH} style={{ width: "5%" }}></th>
									</tr>
									<tr>
										{["OSP", "AR", "Unit", "Rundown OSP", "OSP", "AR", "Unit", "Rundown OSP", "OSP", "AR", "Unit", "Rundown OSP"].map((h, i) => (
											<th key={i} className={TH + (i === 0 || i === 4 || i === 8 ? " border-l" : "")}
												style={{ width: "5%" }}>
												{h}
											</th>
										))}
									</tr>
								</thead>
								<tbody>
									{paginated.map((row, i) => {
										const globalI = (currentPage - 1) * ROWS_PER_PAGE + i;
										return (
											<tr key={row.periode + i} className={globalI % 2 === 0 ? "bg-white" : "bg-gray-50"}>
												<td className={TDC + " font-medium text-gray-700"}>{row.bulan}</td>
												<td className={TD}>{row.if_osp}</td>
												<td className={TD}>{row.if_ar}</td>
												<td className={TDC}>{row.if_unit}</td>
												<td className={TD}>{row.if_rundownosp}</td>
												<td className={TD}>{row.sl_osp}</td>
												<td className={TD}>{row.sl_ar}</td>
												<td className={TDC}>{row.sl_unit}</td>
												<td className={TD}>{row.sl_rundownosp}</td>
												<td className={TD}>{row.total_osp}</td>
												<td className={TD}>{row.total_ar}</td>
												<td className={TDC}>{row.total_unit}</td>
												<td className={TD}>{row.total_rundownosp}</td>
												<td className={TDC}>
													<button
														onClick={() => setDetailRow(row)}
														className="px-3 py-1 text-xs font-medium rounded bg-red-500 text-white
															hover:bg-red-600 transition-colors"
													>
														Detail
													</button>
												</td>
											</tr>
										);
									})}
								</tbody>
							</table>
						</div>

						{totalPages > 1 && (
							<div className="flex items-center justify-center gap-1.5 py-3 border-t border-gray-200 flex-wrap">
								<button onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
									disabled={currentPage === 1}
									className="px-3 py-1 text-sm rounded border border-gray-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-gray-50">
									Previous
								</button>
								{pageNumbers.map((p, i) =>
									p === "…" ? (
										<span key={`el-${i}`} className="px-2 py-1 text-sm text-gray-400">…</span>
									) : (
										<button key={p} onClick={() => setCurrentPage(p as number)}
											className={`px-3 py-1 text-sm rounded border transition-colors ${currentPage === p ? "bg-blue-600 text-white border-blue-600" : "border-gray-300 hover:bg-gray-50"}`}>
											{p}
										</button>
									),
								)}
								<button onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
									disabled={currentPage === totalPages}
									className="px-3 py-1 text-sm rounded border border-gray-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-gray-50">
									Next
								</button>
							</div>
						)}
					</div>
				)}
			</div>

			{detailRow && (
				<DetailModal
					periode={detailRow.periode}
					bulan={detailRow.bulan}
					params={filterParams}
					onClose={() => setDetailRow(null)}
				/>
			)}
		</div>
	);
};

export default SummaryRundownOSP;