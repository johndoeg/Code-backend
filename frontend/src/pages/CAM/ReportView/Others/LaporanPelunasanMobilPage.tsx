import { useState, useEffect } from "react";
import * as XLSX from "xlsx";
import api from "../../../../api/axiosInstance";

interface Totals {
	tot_new: number;
	tot_nf_new: number;
	tot_used: number;
	tot_nf_used: number;
}

interface SummaryRow {
	branch_name: string;
	unit_new: number;
	nf_new: number;
	unit_used: number;
	nf_used: number;
}

interface Contract {
	appl_no: string;
	lease_no: string;
	lessee_nm: string;
	net_finance: number;
	unit: number;
	execution: string | null;
	employee_fullname: string;
}

interface BranchDetail {
	branch_cd: string;
	branch_name: string;
	contracts: Contract[];
}

interface ReportData {
	month_name: string;
	totals: Totals;
	summary: SummaryRow[];
	detail_new: BranchDetail[];
	detail_used: BranchDetail[];
}

const MONTHS_ID = [
	"", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
	"Juli", "Agustus", "September", "Oktober", "November", "Desember",
];

const CUR_YEAR = new Date().getFullYear();
const CUR_MONTH = new Date().getMonth() + 1;
const YEARS = Array.from({ length: 21 }, (_, i) => CUR_YEAR + 10 - i);

const DETAIL_HEADERS = ["No.", "No. CAM", "No. Kontrak", "Nama Customer", "Net Finance", "Total Unit", "Tanggal Pelunasan", "CMO", "Keterangan"];

const fmtNum = (v: number) => new Intl.NumberFormat("id-ID").format(v);
const fmtPct = (unit: number, total: number) => total === 0 ? "0.00" : (unit / total * 100).toFixed(2);
const fmtDate = (s: string | null) => {
	if (!s) return "";
	const [y, m, d] = s.split("-");
	return `${d}-${m}-${y}`;
};

function exportExcel(data: ReportData, bulan: number, tahun: number): void {
	const rows: (string | number | null)[][] = [];
	const merges: XLSX.Range[] = [];
	const C = 11;

	const push = (row: (string | number | null)[]) => rows.push(row);
	const merge = (r1: number, c1: number, r2: number, c2: number) =>
		merges.push({ s: { r: r1, c: c1 }, e: { r: r2, c: c2 } });

	const totAll = data.totals.tot_new + data.totals.tot_used;
	const blank = Array(C).fill(null);

	push(["LAPORAN PELUNASAN MOBIL BARU DAN BEKAS", ...Array(C - 1).fill(null)]);
	merge(0, 0, 0, C - 1);
	push(blank);

	push(["NEW CAR", null, null, null, null, "USED CAR", null, null, null, null, null]);
	merge(2, 0, 2, 4);
	merge(2, 5, 2, 10);

	push(["MONTH", "BRANCH", "NET FINANCE", "UNIT", "Persentase", "MONTH", "BRANCH", "NET FINANCE", "UNIT", "Persentase", "Jumlah"]);

	data.summary.forEach((row, i) => {
		const period = i === 0 ? data.month_name : "";
		const pctNew = parseFloat(fmtPct(row.unit_new, totAll));
		const pctUsed = parseFloat(fmtPct(row.unit_used, totAll));
		push([period, row.branch_name, row.nf_new, row.unit_new, pctNew, period, row.branch_name, row.nf_used, row.unit_used, pctUsed, row.unit_new + row.unit_used]);
	});

	push(["", "TOTAL", data.totals.tot_nf_new, data.totals.tot_new, parseFloat(fmtPct(data.totals.tot_new, totAll)),
		"", "TOTAL", data.totals.tot_nf_used, data.totals.tot_used, parseFloat(fmtPct(data.totals.tot_used, totAll)), totAll]);

	push(blank);

	const totR = rows.length;
	push(["Total Mobil Baru dan Bekas", null, "Net Finance", "Unit", ...Array(C - 4).fill(null)]);
	push([null, null, data.totals.tot_nf_new + data.totals.tot_nf_used, totAll, ...Array(C - 4).fill(null)]);
	merge(totR, 0, totR + 1, 1);

	push(blank);

	const pushDetailSection = (title: string, details: BranchDetail[]) => {
		const titleR = rows.length;
		push([title, ...Array(C - 1).fill(null)]);
		merge(titleR, 0, titleR, 8);

		details.forEach((branch) => {
			const brR = rows.length;
			push([branch.branch_name.toUpperCase(), ...Array(C - 1).fill(null)]);
			merge(brR, 0, brR, 8);

			push([...DETAIL_HEADERS, null, null]);

			let totUnit = 0, totNf = 0;
			branch.contracts.forEach((c, ci) => {
				totUnit += c.unit;
				totNf += c.net_finance;
				push([ci + 1, c.appl_no, c.lease_no, c.lessee_nm, c.net_finance, c.unit, fmtDate(c.execution), c.employee_fullname, "", null, null]);
			});

			push(["", "", "", "", totNf, totUnit, "", "", "", null, null]);
		});

		push(blank);
	};

	pushDetailSection("Data Customer Pelunasan Mobil Baru", data.detail_new);
	pushDetailSection("Data Customer Pelunasan Mobil Bekas", data.detail_used);

	const ws = XLSX.utils.aoa_to_sheet(rows);
	ws["!merges"] = merges;
	ws["!cols"] = [
		{ wch: 12 }, { wch: 22 }, { wch: 18 }, { wch: 8 }, { wch: 10 },
		{ wch: 12 }, { wch: 22 }, { wch: 18 }, { wch: 8 }, { wch: 10 }, { wch: 8 },
	];

	const wb = XLSX.utils.book_new();
	XLSX.utils.book_append_sheet(wb, ws, "LaporanPelunasan");
	XLSX.writeFile(wb, "LaporanPelunasanMobil.xlsx");
}

const PTD_STYLE: React.CSSProperties = { border: "1px solid #000", padding: "2px 4px", fontSize: 11, fontFamily: "Tahoma, Arial, sans-serif" };

function PrintBranchDetail({ branch }: { branch: BranchDetail }) {
	let totUnit = 0, totNf = 0;
	return (
		<>
			<tr>
				<td colSpan={9} align="center" style={{ ...PTD_STYLE, fontWeight: "bold" }}>
					{branch.branch_name.toUpperCase()}
				</td>
			</tr>
			<tr align="center">
				{DETAIL_HEADERS.map((h) => (
					<td key={h} style={{ ...PTD_STYLE, fontWeight: "bold" }}>{h}</td>
				))}
			</tr>
			{branch.contracts.map((c, ci) => {
				totUnit += c.unit;
				totNf += c.net_finance;
				return (
					<tr key={ci}>
						<td align="center" style={PTD_STYLE}>{ci + 1}</td>
						<td style={PTD_STYLE}>{c.appl_no}</td>
						<td style={PTD_STYLE}>{c.lease_no}</td>
						<td style={PTD_STYLE}>{c.lessee_nm}</td>
						<td align="right" style={PTD_STYLE}>{fmtNum(c.net_finance)}</td>
						<td align="center" style={PTD_STYLE}>{c.unit}</td>
						<td align="center" style={PTD_STYLE}>{fmtDate(c.execution)}</td>
						<td style={PTD_STYLE}>{c.employee_fullname}</td>
						<td style={PTD_STYLE}></td>
					</tr>
				);
			})}
			<tr>
				<td colSpan={4} style={PTD_STYLE}></td>
				<td align="right" style={{ ...PTD_STYLE, fontWeight: "bold" }}>{fmtNum(totNf)}</td>
				<td align="center" style={{ ...PTD_STYLE, fontWeight: "bold" }}>{totUnit}</td>
				<td colSpan={3} style={PTD_STYLE}></td>
			</tr>
		</>
	);
}

function MonthYearSelect({ month, year, onMonthChange, onYearChange }: {
	month: number; year: number;
	onMonthChange: (m: number) => void;
	onYearChange: (y: number) => void;
}) {
	const cls = "px-2 py-1.5 text-sm border border-gray-300 rounded-lg bg-white text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500";
	return (
		<>
			<select value={month} onChange={(e) => onMonthChange(Number(e.target.value))} className={cls} style={{ width: 110 }}>
				{MONTHS_ID.slice(1).map((m, i) => <option key={i + 1} value={i + 1}>{m}</option>)}
			</select>
			<select value={year} onChange={(e) => onYearChange(Number(e.target.value))} className={cls} style={{ width: 80 }}>
				{YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
			</select>
		</>
	);
}

const LaporanPelunasanMobilPage: React.FC = () => {
	const [bulan, setBulan] = useState<number>(CUR_MONTH);
	const [tahun, setTahun] = useState<number>(CUR_YEAR);
	const [data, setData] = useState<ReportData | null>(null);
	const [loading, setLoading] = useState<boolean>(false);
	const [error, setError] = useState<string | null>(null);
	const [shouldPrint, setShouldPrint] = useState<boolean>(false);

	useEffect(() => {
		if (shouldPrint && data) {
			window.print();
			setShouldPrint(false);
		}
	}, [shouldPrint, data]);

	const fetchData = async (): Promise<ReportData | null> => {
		setLoading(true);
		setError(null);
		try {
			const res = await api.get<ReportData>("/LaporanPelunasan/api/data", { params: { bulan, tahun } });
			setData(res.data);
			return res.data;
		} catch {
			setError("Gagal memuat data. Silakan coba lagi.");
			return null;
		} finally {
			setLoading(false);
		}
	};

	const handlePreview = () => { setData(null); fetchData(); };

	const handlePrint = async () => {
		if (!data) {
			const d = await fetchData();
			if (d) setShouldPrint(true);
		} else {
			window.print();
		}
	};

	const handleExport = async () => {
		const d = data ?? await fetchData();
		if (d) exportExcel(d, bulan, tahun);
	};

	const totAll = data ? data.totals.tot_new + data.totals.tot_used : 0;
	const totNfAll = data ? data.totals.tot_nf_new + data.totals.tot_nf_used : 0;

	return (
		<>
			<style>{`
				@media print {
					.screen-only { display: none !important; }
					.print-only  { display: block !important; }
					body { font-family: Tahoma, Arial, sans-serif; font-size: 11px; }
					@page { size: landscape; margin: 10mm; }
				}
				@media screen { .print-only { display: none; } }
			`}</style>

			<div className="screen-only min-h-screen bg-gray-50 p-4 md:p-6">
				<div className="max-w-full mx-auto">

					<div className="mb-6">
						<h1 className="text-2xl font-semibold text-gray-800">Laporan Pelunasan Mobil Baru &amp; Bekas</h1>
					</div>

					<div className="bg-white rounded-xl border border-gray-200 p-4 mb-6 flex flex-wrap gap-3 items-end">
						<div>
							<label className="block text-xs font-medium text-gray-500 mb-1">Disbursement Date</label>
							<div className="flex gap-2">
								<MonthYearSelect month={bulan} year={tahun} onMonthChange={setBulan} onYearChange={setTahun} />
							</div>
						</div>

						<button onClick={handlePreview} disabled={loading}
							className="inline-flex items-center px-4 py-2 text-sm font-medium rounded-lg transition-all bg-blue-50 text-blue-800 border border-blue-200 hover:bg-blue-100 disabled:opacity-40 disabled:cursor-not-allowed">
							{loading ? "Memuat…" : "Preview"}
						</button>
						<button onClick={handlePrint} disabled={loading}
							className="inline-flex items-center px-4 py-2 text-sm font-medium rounded-lg transition-all bg-gray-50 text-gray-700 border border-gray-200 hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed">
							Print
						</button>
						<button onClick={handleExport} disabled={loading}
							className="inline-flex items-center px-4 py-2 text-sm font-medium rounded-lg transition-all bg-green-50 text-green-800 border border-green-200 hover:bg-green-100 disabled:opacity-40 disabled:cursor-not-allowed">
							Export to Excel
						</button>
					</div>

					{error && (
						<div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{error}</div>
					)}

					{loading && <div className="py-16 text-center text-sm text-gray-400">Memuat data…</div>}

					{!loading && !data && (
						<div className="py-16 text-center text-sm text-gray-400 border border-dashed border-gray-300 rounded-xl">
							Pilih periode dan klik <span className="font-medium">Preview</span> untuk menampilkan data
						</div>
					)}

					{!loading && data && (
						<>
							<div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
								{[
									{ label: "Total Unit NEW", value: data.totals.tot_new, cls: "bg-blue-50 text-blue-700" },
									{ label: "Net Finance NEW", value: fmtNum(data.totals.tot_nf_new), cls: "bg-blue-50 text-blue-700" },
									{ label: "Total Unit USED", value: data.totals.tot_used, cls: "bg-amber-50 text-amber-700" },
									{ label: "Net Finance USED", value: fmtNum(data.totals.tot_nf_used), cls: "bg-amber-50 text-amber-700" },
								].map((m) => (
									<div key={m.label} className={`rounded-lg p-3 ${m.cls}`}>
										<div className="text-xs opacity-70 mb-1">{m.label}</div>
										<div className="text-lg font-semibold tabular-nums">{m.value}</div>
									</div>
								))}
							</div>

							<div className="bg-white rounded-xl border border-gray-200 overflow-hidden mb-4">
								<div className="overflow-x-auto">
									<table className="w-full border-collapse text-sm">
										<thead>
											<tr>
												<th colSpan={5} className="px-3 py-2 text-xs font-semibold text-blue-800 bg-blue-50 border-b border-gray-200 text-center">NEW CAR</th>
												<th colSpan={5} className="px-3 py-2 text-xs font-semibold text-amber-800 bg-amber-50 border-b border-gray-200 text-center">USED CAR</th>
												<th rowSpan={2} className="px-3 py-2 text-xs font-medium text-gray-500 bg-gray-50 border-b border-l border-gray-200 text-center whitespace-nowrap">Jumlah</th>
											</tr>
											<tr>
												{["MONTH", "BRANCH", "NET FINANCE", "UNIT", "%", "MONTH", "BRANCH", "NET FINANCE", "UNIT", "%"].map((h, i) => (
													<th key={h + i} className={`px-3 py-1.5 text-xs font-medium text-gray-500 border-b border-gray-200 text-center whitespace-nowrap ${i < 5 ? "bg-blue-50/50" : "bg-amber-50/50"}`}>{h}</th>
												))}
											</tr>
										</thead>
										<tbody>
											{data.summary.map((row, i) => (
												<tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-gray-50"}>
													<td className="px-3 py-1.5 text-center border-b border-gray-100 text-gray-500 text-xs">{i === 0 ? data.month_name : ""}</td>
													<td className="px-3 py-1.5 border-b border-gray-100 text-gray-700 whitespace-nowrap">{row.branch_name}</td>
													<td className="px-3 py-1.5 text-right tabular-nums border-b border-gray-100">{fmtNum(row.nf_new)}</td>
													<td className="px-3 py-1.5 text-center border-b border-gray-100">{row.unit_new}</td>
													<td className="px-3 py-1.5 text-center border-b border-gray-100 text-gray-500">{fmtPct(row.unit_new, totAll)}</td>
													<td className="px-3 py-1.5 text-center border-b border-gray-100 border-l border-gray-200 text-gray-500 text-xs">{i === 0 ? data.month_name : ""}</td>
													<td className="px-3 py-1.5 border-b border-gray-100 text-gray-700 whitespace-nowrap">{row.branch_name}</td>
													<td className="px-3 py-1.5 text-right tabular-nums border-b border-gray-100">{fmtNum(row.nf_used)}</td>
													<td className="px-3 py-1.5 text-center border-b border-gray-100">{row.unit_used}</td>
													<td className="px-3 py-1.5 text-center border-b border-gray-100 text-gray-500">{fmtPct(row.unit_used, totAll)}</td>
													<td className="px-3 py-1.5 text-center border-b border-gray-100 border-l border-gray-200 font-medium">{row.unit_new + row.unit_used}</td>
												</tr>
											))}
											
											<tr className="bg-gray-100 font-semibold">
												<td className="px-3 py-2 border-t border-gray-200"></td>
												<td className="px-3 py-2 text-center border-t border-gray-200">TOTAL</td>
												<td className="px-3 py-2 text-right tabular-nums border-t border-gray-200">{fmtNum(data.totals.tot_nf_new)}</td>
												<td className="px-3 py-2 text-center border-t border-gray-200">{data.totals.tot_new}</td>
												<td className="px-3 py-2 text-center border-t border-gray-200">{fmtPct(data.totals.tot_new, totAll)}</td>
												<td className="px-3 py-2 border-t border-gray-200 border-l border-gray-200"></td>
												<td className="px-3 py-2 text-center border-t border-gray-200">TOTAL</td>
												<td className="px-3 py-2 text-right tabular-nums border-t border-gray-200">{fmtNum(data.totals.tot_nf_used)}</td>
												<td className="px-3 py-2 text-center border-t border-gray-200">{data.totals.tot_used}</td>
												<td className="px-3 py-2 text-center border-t border-gray-200">{fmtPct(data.totals.tot_used, totAll)}</td>
												<td className="px-3 py-2 text-center border-t border-gray-200 border-l border-gray-200">{totAll}</td>
											</tr>
										</tbody>
										<tfoot>
											<tr className="bg-gray-50">
												<td colSpan={2} rowSpan={2} className="px-3 py-2 text-center font-semibold border-t border-gray-300">
													Total Mobil Baru dan Bekas
												</td>
												<td className="px-3 py-2 text-center text-xs font-medium text-gray-500 border-t border-gray-300">Net Finance</td>
												<td className="px-3 py-2 text-center text-xs font-medium text-gray-500 border-t border-gray-300">Unit</td>
												<td colSpan={7} className="border-t border-gray-300"></td>
											</tr>
											<tr className="bg-gray-50">
												<td className="px-3 py-2 text-right tabular-nums font-semibold">{fmtNum(totNfAll)}</td>
												<td className="px-3 py-2 text-center font-semibold">{totAll}</td>
												<td colSpan={7}></td>
											</tr>
										</tfoot>
									</table>
								</div>
							</div>
						</>
					)}
				</div>
			</div>

			{data && (
				<div className="print-only" style={{ fontFamily: "Tahoma, Arial, sans-serif", fontSize: 11, padding: "10px 20px" }}>

					<table border={0} cellPadding={2} cellSpacing={0} style={{ width: "100%", borderCollapse: "collapse", marginBottom: 8 }}>
						<tbody>
							<tr>
								<td colSpan={4} align="center" style={{ fontSize: 14, fontWeight: "bold", letterSpacing: "0.1em" }}>
									LAPORAN PELUNASAN MOBIL BARU DAN BEKAS
								</td>
							</tr>
						</tbody>
					</table>

					<table border={0} cellPadding={2} cellSpacing={0} style={{ width: "100%", borderCollapse: "collapse", marginBottom: 8 }}>
						<tbody>
							<tr>
								<td colSpan={5} style={{ ...PTD_STYLE, fontWeight: "bold" }}>NEW CAR</td>
								<td colSpan={6} style={{ ...PTD_STYLE, fontWeight: "bold" }}>USED CAR</td>
							</tr>
							<tr align="center">
								{["MONTH", "BRANCH", "NET FINANCE", "UNIT", "Persentase", "MONTH", "BRANCH", "NET FINANCE", "UNIT", "Persentase", "Jumlah"].map((h) => (
									<td key={h} style={{ ...PTD_STYLE, fontWeight: "bold" }}>{h}</td>
								))}
							</tr>
							{data.summary.map((row, i) => (
								<tr key={i}>
									<td align="center" style={PTD_STYLE}>{i === 0 ? data.month_name : ""}</td>
									<td style={PTD_STYLE}>{row.branch_name}</td>
									<td align="right" style={PTD_STYLE}>{fmtNum(row.nf_new)}</td>
									<td align="center" style={PTD_STYLE}>{row.unit_new}</td>
									<td align="center" style={PTD_STYLE}>{fmtPct(row.unit_new, totAll)}</td>
									<td align="center" style={PTD_STYLE}>{i === 0 ? data.month_name : ""}</td>
									<td style={PTD_STYLE}>{row.branch_name}</td>
									<td align="right" style={PTD_STYLE}>{fmtNum(row.nf_used)}</td>
									<td align="center" style={PTD_STYLE}>{row.unit_used}</td>
									<td align="center" style={PTD_STYLE}>{fmtPct(row.unit_used, totAll)}</td>
									<td align="center" style={PTD_STYLE}>{row.unit_new + row.unit_used}</td>
								</tr>
							))}
							<tr>
								<td style={PTD_STYLE}></td>
								<td align="center" style={{ ...PTD_STYLE, fontWeight: "bold" }}>TOTAL</td>
								<td align="right" style={{ ...PTD_STYLE, fontWeight: "bold" }}>{fmtNum(data.totals.tot_nf_new)}</td>
								<td align="center" style={{ ...PTD_STYLE, fontWeight: "bold" }}>{data.totals.tot_new}</td>
								<td align="center" style={{ ...PTD_STYLE, fontWeight: "bold" }}>{fmtPct(data.totals.tot_new, totAll)}</td>
								<td style={PTD_STYLE}></td>
								<td align="center" style={{ ...PTD_STYLE, fontWeight: "bold" }}>TOTAL</td>
								<td align="right" style={{ ...PTD_STYLE, fontWeight: "bold" }}>{fmtNum(data.totals.tot_nf_used)}</td>
								<td align="center" style={{ ...PTD_STYLE, fontWeight: "bold" }}>{data.totals.tot_used}</td>
								<td align="center" style={{ ...PTD_STYLE, fontWeight: "bold" }}>{fmtPct(data.totals.tot_used, totAll)}</td>
								<td align="center" style={{ ...PTD_STYLE, fontWeight: "bold" }}>{totAll}</td>
							</tr>
							<tr><td colSpan={11}></td></tr>
							<tr>
								<td colSpan={2} rowSpan={2} align="center" style={{ ...PTD_STYLE, fontWeight: "bold" }}>Total Mobil Baru dan Bekas</td>
								<td align="center" style={{ ...PTD_STYLE, fontWeight: "bold" }}>Net Finance</td>
								<td align="center" style={{ ...PTD_STYLE, fontWeight: "bold" }}>Unit</td>
								<td colSpan={7}></td>
							</tr>
							<tr>
								<td align="right" style={{ ...PTD_STYLE, fontWeight: "bold" }}>{fmtNum(totNfAll)}</td>
								<td align="center" style={{ ...PTD_STYLE, fontWeight: "bold" }}>{totAll}</td>
								<td colSpan={7}></td>
							</tr>
						</tbody>
					</table>

					<table border={0} cellPadding={2} cellSpacing={0} style={{ width: "100%", borderCollapse: "collapse", marginBottom: 8 }}>
						<tbody>
							<tr>
								<td colSpan={9} align="center" style={{ fontSize: 13, fontWeight: "bold", letterSpacing: "0.1em" }}>
									Data Customer Pelunasan Mobil Baru
								</td>
							</tr>
							{data.detail_new.map((branch) => (
								<PrintBranchDetail key={branch.branch_cd} branch={branch} />
							))}

							<tr>
								<td colSpan={9} align="center" style={{ fontSize: 13, fontWeight: "bold", letterSpacing: "0.1em", paddingTop: 12 }}>
									Data Customer Pelunasan Mobil Bekas
								</td>
							</tr>
							{data.detail_used.map((branch) => (
								<PrintBranchDetail key={branch.branch_cd} branch={branch} />
							))}
						</tbody>
					</table>
				</div>
			)}
		</>
	);
};

export default LaporanPelunasanMobilPage;