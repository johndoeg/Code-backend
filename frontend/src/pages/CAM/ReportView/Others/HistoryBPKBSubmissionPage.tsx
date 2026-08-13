import { useState, useEffect, useMemo, useCallback } from "react";
import * as XLSX from "xlsx";
import api from "../../../../api/axiosInstance";
import { DEFAULT_PAGE_LIMIT } from "../../../../constants/DefaultValue";
import Pagination from "../../../../helpers/Pagination";

interface Branch { branch_cd: string; branch_name: string; }
interface Dealer { supp: string; name: string; nickname: string; address: string; phone: string; contact: string; }

interface BPKBRow {
	dealer_name: string;
	lessee_nm: string;
	lease_no: string;
	branch_name: string;
	execution: string | null;
	status_dt: string | null;
	status: string;
	remark: string;
}

type PrintBy = "0" | "1" | "2";

const MONTHS_ID = [
	"", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
	"Juli", "Agustus", "September", "Oktober", "November", "Desember",
];

const NOW = new Date();
const CUR_MONTH = NOW.getMonth() + 1;
const CUR_YEAR = NOW.getFullYear();
const YEARS = Array.from({ length: 21 }, (_, i) => CUR_YEAR + 10 - i);

const PRINT_BY_OPTIONS = [
	{ value: "0" as PrintBy, label: "Consolidate" },
	{ value: "1" as PrintBy, label: "Branch" },
	{ value: "2" as PrintBy, label: "Dealer" },
];

const HEADERS: Record<PrintBy, string[]> = {
	"0": ["Dealer/ Showroom Name", "Customer Name", "Contract No.", "Branch", "Disbursement Date", "Received Date (by CA)", "Status", "Remark"],
	"1": ["Dealer/ Showroom Name", "Customer Name", "Contract No.", "Disbursement Date", "Received Date (by CA)", "Status", "Remark"],
	"2": ["Customer Name", "Contract No.", "Branch", "Disbursement Date", "Received Date (by CA)", "Status", "Remark"],
};

const CENTER_COLS: Record<PrintBy, number[]> = {
	"0": [2, 4, 5],
	"1": [2, 3, 4],
	"2": [1, 3, 4],
};

const ROWS_PER_PAGE = DEFAULT_PAGE_LIMIT;

function fmtDateShort(dateStr: string | null): string {
	if (!dateStr) return "";
	const d = new Date(dateStr);
	const day = String(d.getDate()).padStart(2, "0");
	const month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][d.getMonth()];
	const year = String(d.getFullYear()).slice(-2);
	return `${day}-${month}-${year}`;
}

function getRowValues(row: BPKBRow, mode: PrintBy): (string | number)[] {
	const exec = fmtDateShort(row.execution);
	const recv = fmtDateShort(row.status_dt);
	if (mode === "0") return [row.dealer_name, row.lessee_nm, row.lease_no, row.branch_name, exec, recv, row.status, row.remark];
	if (mode === "1") return [row.dealer_name, row.lessee_nm, row.lease_no, exec, recv, row.status, row.remark];
	return [row.lessee_nm, row.lease_no, row.branch_name, exec, recv, row.status, row.remark];
}

function exportExcel(data: BPKBRow[], mode: PrintBy, period: string, subjudul: string): void {
	const headers = ["No.", ...HEADERS[mode]];
	const rows: (string | number | null)[][] = [];

	rows.push(["HISTORY OF BPKB SUBMISSION BY DEALER/ SHOWROOM"]);
	rows.push([`Period Received Date (by CA) : ${period}`]);
	rows.push([`Print by : ${subjudul}`]);
	rows.push([]);
	rows.push(headers);

	data.forEach((row, i) => {
		rows.push([i + 1, ...getRowValues(row, mode)]);
	});

	const ws = XLSX.utils.aoa_to_sheet(rows);
	const colCount = headers.length;
	ws["!merges"] = [
		{ s: { r: 0, c: 0 }, e: { r: 0, c: colCount - 1 } },
		{ s: { r: 1, c: 0 }, e: { r: 1, c: colCount - 1 } },
		{ s: { r: 2, c: 0 }, e: { r: 2, c: colCount - 1 } },
	];
	ws["!cols"] = headers.map((_, ci) => ({ wch: ci === 0 ? 5 : ci <= 2 ? 28 : 14 }));

	const wb = XLSX.utils.book_new();
	XLSX.utils.book_append_sheet(wb, ws, "HistoryBPKBSubmission");
	XLSX.writeFile(wb, "HistoryOfBPKBSubmission.xlsx");
}

function StatusBadge({ status }: { status: string }) {
	if (status === "Not Due")
		return <span className="inline-flex px-2 py-0.5 text-xs font-medium rounded-full bg-green-50 text-green-700 border border-green-200">Not Due</span>;
	if (status === "Due")
		return <span className="inline-flex px-2 py-0.5 text-xs font-medium rounded-full bg-red-50 text-red-700 border border-red-200">Due</span>;
	return <span>{status}</span>;
}

interface DealerModalProps {
	isOpen: boolean;
	onClose: () => void;
	onSelect: (supp: string, nickname: string) => void;
}

function DealerModal({ isOpen, onClose, onSelect }: DealerModalProps) {
	const [query, setQuery] = useState<string>("");
	const [dealers, setDealers] = useState<Dealer[]>([]);
	const [loading, setLoading] = useState<boolean>(false);

	const fetchDealers = useCallback(async (q: string) => {
		setLoading(true);
		try {
			const res = await api.get<Dealer[]>("/CAM/Others/HistoryBPKBSubmission/api/dealers", { params: { q } });
			setDealers(res.data);
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		if (!isOpen) return;
		const timer = setTimeout(() => fetchDealers(query), 300);
		return () => clearTimeout(timer);
	}, [query, isOpen, fetchDealers]);

	useEffect(() => { if (!isOpen) setQuery(""); }, [isOpen]);

	if (!isOpen) return null;

	return (
		<div className="fixed inset-0 z-50 flex items-center justify-center">
			<div className="absolute inset-0 bg-black/40" onClick={onClose} />

			<div className="relative bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col mx-4">
				<div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
					<h2 className="font-semibold text-gray-800 text-sm">List Dealer</h2>
					<button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg leading-none">✕</button>
				</div>

				<div className="px-4 py-3 border-b border-gray-200">
					<input
						type="text"
						value={query}
						onChange={(e) => setQuery(e.target.value)}
						placeholder="Cari dealer / nickname…"
						autoFocus
						className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg
							focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
					/>
				</div>

				<div className="overflow-y-auto flex-1">
					{loading ? (
						<div className="py-10 text-center text-sm text-gray-400">Mencari…</div>
					) : dealers.length === 0 ? (
						<div className="py-10 text-center text-sm text-gray-400">Tidak ada data</div>
					) : (
						<table className="w-full text-sm border-collapse">
							<thead className="bg-gray-50 sticky top-0">
								<tr>
									{["Dealer Code", "Dealer Name", "Nickname", "Address", "Phone", "Contact"].map((h) => (
										<th key={h} className="px-3 py-2 text-xs font-medium text-gray-500 border-b border-gray-200 text-left whitespace-nowrap">
											{h}
										</th>
									))}
								</tr>
							</thead>
							<tbody>
								{dealers.map((d, i) => (
									<tr
										key={d.supp}
										onClick={() => { onSelect(d.supp, d.nickname); onClose(); }}
										className={`cursor-pointer hover:bg-blue-50 ${i % 2 === 0 ? "bg-white" : "bg-gray-50"}`}
									>
										<td className="px-3 py-1.5 border-b border-gray-100 text-blue-600 underline whitespace-nowrap">{d.supp}</td>
										<td className="px-3 py-1.5 border-b border-gray-100 whitespace-nowrap">{d.name}</td>
										<td className="px-3 py-1.5 border-b border-gray-100 whitespace-nowrap">{d.nickname}</td>
										<td className="px-3 py-1.5 border-b border-gray-100">{d.address}</td>
										<td className="px-3 py-1.5 border-b border-gray-100 whitespace-nowrap">{d.phone}</td>
										<td className="px-3 py-1.5 border-b border-gray-100 whitespace-nowrap">{d.contact}</td>
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

interface MonthYearSelectProps {
	month: number; year: number;
	onMonthChange: (m: number) => void;
	onYearChange: (y: number) => void;
}

function MonthYearSelect({ month, year, onMonthChange, onYearChange }: MonthYearSelectProps) {
	const selectCls = "px-2 py-1.5 text-sm border border-gray-300 rounded-lg bg-white text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500";
	return (
		<>
			<select value={month} onChange={(e) => onMonthChange(Number(e.target.value))} className={selectCls} style={{ width: 110 }}>
				{MONTHS_ID.slice(1).map((m, i) => (
					<option key={i + 1} value={i + 1}>{m}</option>
				))}
			</select>
			<select value={year} onChange={(e) => onYearChange(Number(e.target.value))} className={selectCls} style={{ width: 80 }}>
				{YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
			</select>
		</>
	);
}

interface PrintTableProps { data: BPKBRow[]; mode: PrintBy; }

function PrintTable({ data, mode }: PrintTableProps) {
	const headers = ["No.", ...HEADERS[mode]];
	const centerCols = new Set([0, ...CENTER_COLS[mode].map((c) => c + 1)]);
	return (
		<table border={1} cellPadding={2} cellSpacing={0} style={{ width: "100%", borderCollapse: "collapse" }}>
			<thead>
				<tr align="center" style={{ fontSize: 12, fontFamily: "Arial, Helvetica, sans-serif" }}>
					{headers.map((h) => (
						<td key={h} style={{ border: "1px solid #000", padding: "3px 6px", fontWeight: "bold" }}>{h}</td>
					))}
				</tr>
			</thead>
			<tbody>
				{data.map((row, idx) => {
					const values = [idx + 1, ...getRowValues(row, mode)];
					return (
						<tr key={`${row.lease_no}-p${idx}`} style={{ fontSize: 12, fontFamily: "Arial, Helvetica, sans-serif" }}>
							{values.map((val, ci) => (
								<td
									key={ci}
									align={centerCols.has(ci) ? "center" : "left"}
									style={{ border: "1px solid #000", padding: "2px 6px" }}
								>
									{val}
								</td>
							))}
						</tr>
					);
				})}
			</tbody>
		</table>
	);
}

const HistoryBPKBSubmissionPage: React.FC = () => {
	const [bulanAwal, setBulanAwal] = useState<number>(CUR_MONTH);
	const [tahunAwal, setTahunAwal] = useState<number>(CUR_YEAR);
	const [bulanAkhir, setBulanAkhir] = useState<number>(CUR_MONTH);
	const [tahunAkhir, setTahunAkhir] = useState<number>(CUR_YEAR);
	const [printBy, setPrintBy] = useState<PrintBy>("0");
	const [selectedBranch, setSelectedBranch] = useState<string>("");
	const [selectedSupp, setSelectedSupp] = useState<string>("");
	const [dealerNm, setDealerNm] = useState<string>("");

	const [branches, setBranches] = useState<Branch[]>([]);
	const [data, setData] = useState<BPKBRow[]>([]);
	const [loading, setLoading] = useState<boolean>(false);
	const [branchLoading, setBranchLoading] = useState<boolean>(true);
	const [error, setError] = useState<string | null>(null);
	const [hasSearched, setHasSearched] = useState<boolean>(false);
	const [currentPage, setCurrentPage] = useState<number>(1);
	const [dealerModalOpen, setDealerModalOpen] = useState<boolean>(false);

	const period = `${MONTHS_ID[bulanAwal]} ${tahunAwal} - ${MONTHS_ID[bulanAkhir]} ${tahunAkhir}`;
	const subjudul =
		printBy === "0" ? "Consolidate" :
			printBy === "1" ? `Branch - ${branches.find((b) => b.branch_cd === selectedBranch)?.branch_name ?? ""}` :
				`Dealer - ${dealerNm}`;

	useEffect(() => {
		api.get<Branch[]>("/CAM/Others/HistoryBPKBSubmission/api/branches")
			.then((res) => setBranches(res.data))
			.catch(() => setError("Gagal memuat daftar cabang."))
			.finally(() => setBranchLoading(false));
	}, []);

	const handlePrintByChange = (val: PrintBy) => {
		setPrintBy(val);
		setData([]);
		setHasSearched(false);
		setCurrentPage(1);
	};

	const handlePreview = async () => {
		if (printBy === "1" && !selectedBranch) { setError("Pilih cabang terlebih dahulu."); return; }
		if (printBy === "2" && !selectedSupp) { setError("Pilih dealer terlebih dahulu."); return; }
		setLoading(true);
		setError(null);
		setData([]);
		setCurrentPage(1);
		try {
			const res = await api.get<BPKBRow[]>("/CAM/Others/HistoryBPKBSubmission/api/data", {
				params: { bulan_awal: bulanAwal, tahun_awal: tahunAwal, bulan_akhir: bulanAkhir, tahun_akhir: tahunAkhir, print_by: printBy, branch_cd: selectedBranch, supp: selectedSupp },
			});
			setData(res.data);
			setHasSearched(true);
		} catch {
			setError("Gagal memuat data. Silakan coba lagi.");
		} finally {
			setLoading(false);
		}
	};

	const handleExport = () => {
		if (!data.length) return;
		exportExcel(data, printBy, period, subjudul);
	};

	const handlePrint = () => window.print();

	const handleDealerSelect = (supp: string, nickname: string) => {
		setSelectedSupp(supp);
		setDealerNm(nickname);
	};

	const totalPages = Math.ceil(data.length / ROWS_PER_PAGE);
	const paginatedData = useMemo(() => data.slice((currentPage - 1) * ROWS_PER_PAGE, currentPage * ROWS_PER_PAGE), [data, currentPage]);

	const headers = ["No.", ...HEADERS[printBy]];
	const centerCols = new Set([0, ...CENTER_COLS[printBy].map((c) => c + 1)]);

	return (
		<>
			<style>{`
				@media print {
					.screen-only { display: none !important; }
					.print-only  { display: block !important; }
					body { font-family: Tahoma, Arial, sans-serif; font-size: 12px; }
				}
				@media screen { .print-only { display: none; } }
			`}</style>

			<div className="screen-only min-h-screen bg-gray-50 p-4 md:p-6">
				<div className="max-w-7xl mx-auto">

					<div className="mb-6">
						<h1 className="text-2xl font-semibold text-gray-800">History of BPKB Submission by Dealer/ Showroom</h1>
					</div>

					<div className="bg-white rounded-xl border border-gray-200 p-4 mb-6">
						<div className="grid grid-cols-1 gap-3">

							<div className="flex flex-wrap items-center gap-2">
								<span className="text-sm text-gray-600 w-52">Period Received Date (by CA)</span>
								<MonthYearSelect month={bulanAwal} year={tahunAwal} onMonthChange={setBulanAwal} onYearChange={setTahunAwal} />
								<span className="text-gray-400 text-sm">–</span>
								<MonthYearSelect month={bulanAkhir} year={tahunAkhir} onMonthChange={setBulanAkhir} onYearChange={setTahunAkhir} />
							</div>

							<div className="flex flex-wrap items-center gap-2">
								<span className="text-sm text-gray-600 w-52">Print by</span>
								<select
									value={printBy}
									onChange={(e) => handlePrintByChange(e.target.value as PrintBy)}
									className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg bg-white text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
								>
									{PRINT_BY_OPTIONS.map((o) => (
										<option key={o.value} value={o.value}>{o.label}</option>
									))}
								</select>
							</div>

							{printBy === "1" && (
								<div className="flex flex-wrap items-center gap-2">
									<span className="text-sm text-gray-600 w-52">Branch</span>
									<select
										value={selectedBranch}
										onChange={(e) => setSelectedBranch(e.target.value)}
										disabled={branchLoading}
										className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg bg-white text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-60"
										style={{ minWidth: 180 }}
									>
										<option value="">Select</option>
										{branches.map((b) => (
											<option key={b.branch_cd} value={b.branch_cd}>{b.branch_name}</option>
										))}
									</select>
								</div>
							)}

							{printBy === "2" && (
								<div className="flex flex-wrap items-center gap-2">
									<span className="text-sm text-gray-600 w-52">
										<button onClick={() => setDealerModalOpen(true)} className="text-blue-600 hover:underline text-sm">
											Dealer Name/ Nickname
										</button>
									</span>
									<input
										type="text"
										value={dealerNm}
										readOnly
										placeholder="Klik link untuk memilih dealer…"
										className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg bg-gray-50 text-gray-700 cursor-pointer"
										style={{ minWidth: 220 }}
										onClick={() => setDealerModalOpen(true)}
									/>
								</div>
							)}

							<div className="flex flex-wrap gap-2 pt-1">
								<button
									onClick={handlePreview}
									disabled={loading}
									className="inline-flex items-center px-4 py-2 text-sm font-medium rounded-lg transition-all
										bg-blue-50 text-blue-800 border border-blue-200 hover:bg-blue-100
										disabled:opacity-40 disabled:cursor-not-allowed"
								>
									{loading ? "Memuat…" : "Preview"}
								</button>
								<button
									onClick={handlePrint}
									disabled={!data.length}
									className="inline-flex items-center px-4 py-2 text-sm font-medium rounded-lg transition-all
										bg-gray-50 text-gray-700 border border-gray-200 hover:bg-gray-100
										disabled:opacity-40 disabled:cursor-not-allowed"
								>
									Print
								</button>
								<button
									onClick={handleExport}
									disabled={!data.length}
									className="inline-flex items-center px-4 py-2 text-sm font-medium rounded-lg transition-all
										bg-green-50 text-green-800 border border-green-200 hover:bg-green-100
										disabled:opacity-40 disabled:cursor-not-allowed"
								>
									Export to Excel
								</button>
							</div>
						</div>

						{hasSearched && (
							<div className="mt-3 pt-3 border-t border-gray-100 flex flex-wrap gap-2 text-xs text-gray-500">
								<span>Periode: <strong className="text-gray-700">{period}</strong></span>
								<span className="text-gray-300">|</span>
								<span>Print by: <strong className="text-gray-700">{subjudul}</strong></span>
							</div>
						)}
					</div>

					{error && (
						<div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{error}</div>
					)}

					{loading && <div className="py-16 text-center text-sm text-gray-400">Memuat data…</div>}

					{!loading && !hasSearched && (
						<div className="py-16 text-center text-sm text-gray-400 border border-dashed border-gray-300 rounded-xl">
							Atur filter dan klik <span className="font-medium">Preview</span> untuk menampilkan data
						</div>
					)}
					{!loading && hasSearched && data.length === 0 && (
						<div className="py-16 text-center text-sm text-gray-400 border border-dashed border-gray-300 rounded-xl">
							Tidak ada data untuk filter yang dipilih
						</div>
					)}

					{!loading && data.length > 0 && (
						<>
							<div className="flex gap-3 mb-4">
								<div className="bg-gray-50 rounded-lg p-3">
									<div className="text-xs text-gray-400 mb-1">Total Records</div>
									<div className="text-lg font-semibold tabular-nums text-gray-800">{data.length}</div>
								</div>
								<div className="bg-green-50 rounded-lg p-3">
									<div className="text-xs text-gray-400 mb-1">Not Due</div>
									<div className="text-lg font-semibold tabular-nums text-green-700">{data.filter(r => r.status === "Not Due").length}</div>
								</div>
								<div className="bg-red-50 rounded-lg p-3">
									<div className="text-xs text-gray-400 mb-1">Due</div>
									<div className="text-lg font-semibold tabular-nums text-red-700">{data.filter(r => r.status === "Due").length}</div>
								</div>
							</div>

							<div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
								<div className="overflow-x-auto">
									<table className="w-full border-collapse text-sm">
										<thead>
											<tr className="bg-gray-50">
												{headers.map((h) => (
													<th key={h} className="px-3 py-2 text-xs font-medium text-gray-500 border-b border-gray-200 text-center whitespace-nowrap">
														{h}
													</th>
												))}
											</tr>
										</thead>
										<tbody>
											{paginatedData.map((row, idx) => {
												const globalIdx = (currentPage - 1) * ROWS_PER_PAGE + idx;
												const values = [globalIdx + 1, ...getRowValues(row, printBy)];
												const statusIdx = values.length - 2;
												return (
													<tr key={`${row.lease_no}-${globalIdx}`} className={globalIdx % 2 === 0 ? "bg-white" : "bg-gray-50"}>
														{values.map((val, ci) => (
															<td
																key={ci}
																className={`px-3 py-2 border-b border-gray-100 text-gray-700 whitespace-nowrap ${centerCols.has(ci) ? "text-center" : ""}`}
															>
																{ci === statusIdx ? <StatusBadge status={String(val)} /> : val}
															</td>
														))}
													</tr>
												);
											})}
										</tbody>
									</table>
								</div>

								{totalPages > 1 && (
									<Pagination
										page={currentPage}
										totalPages={totalPages}
										onPageChange={setCurrentPage}
										totalItems={data.length}
										itemsPerPage={ROWS_PER_PAGE}
										className="border-t border-gray-200"
									/>
								)}
							</div>
						</>
					)}
				</div>
			</div>

			<div className="print-only" style={{ fontFamily: "Tahoma, Arial, sans-serif", fontSize: 12, padding: 20 }}>
				<table border={0} cellPadding={2} cellSpacing={0} style={{ width: "100%", borderCollapse: "collapse" }}>
					<tbody>
						<tr>
							<td colSpan={4} align="center" style={{ fontSize: 16, fontWeight: "bold", letterSpacing: "0.1em" }}>
								HISTORY OF BPKB SUBMISSION BY DEALER/ SHOWROOM
							</td>
						</tr>
						<tr>
							<td colSpan={4} align="center">
								Period Received Date (by CA) : {period}
							</td>
						</tr>
						<tr>
							<td colSpan={4}>Print by : {subjudul}</td>
						</tr>
					</tbody>
				</table>
				<br />
				<PrintTable data={data} mode={printBy} />
			</div>

			<DealerModal
				isOpen={dealerModalOpen}
				onClose={() => setDealerModalOpen(false)}
				onSelect={handleDealerSelect}
			/>
		</>
	);
};

export default HistoryBPKBSubmissionPage;