import { useState, useEffect } from "react";
import * as XLSX from "xlsx";
import api from "../../../../api/axiosInstance";

interface DateInfo { day_num: number; day_str: string; is_holiday: boolean; }
interface Employee {
	no: number; employee_id: string; fullname: string;
	is_cmh: boolean; name_color: string; resigned: boolean;
	daily_counts: number[]; total: number; avg_per_day: number;
}

interface Branch {
	branch_cd: string; branch_name: string; cmo_count: number;
	employees: Employee[]; day_totals: number[];
	branch_total: number; branch_avg: number;
}

interface ReportData {
	asof: string; working_days: number; to_date: string;
	dates: DateInfo[]; branches: Branch[];
	grand_day_totals: number[];
	grand_total: number; grand_avg: number; grand_cmo_count: number;
}

const MONTHS_ID = [
	"", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
	"Juli", "Agustus", "September", "Oktober", "November", "Desember",
];
const CUR_YEAR = new Date().getFullYear();
const CUR_MONTH = new Date().getMonth() + 1;
const YEARS = Array.from({ length: 21 }, (_, i) => CUR_YEAR + 10 - i);

const NO_W = 40;
const NAME_W = 170;

const CMH_BG = "#89CFF0";
const HOLIDAY_BG = "#ffcccc";
const WHITE = "#ffffff";
const GRAY_TOTAL = "#f3f4f6";
const GRAY_GRAND = "#e5e7eb";

function rowBg(emp: Employee) { return emp.is_cmh ? CMH_BG : WHITE; }
function dayCellBg(isHoliday: boolean) { return isHoliday ? HOLIDAY_BG : "transparent"; }

function exportExcel(data: ReportData): void {
	if (!data.dates.length) return;
	const numDays = data.dates.length;
	const totCols = numDays + 4;
	const rows: (string | number | null)[][] = [];
	const merges: XLSX.Range[] = [];

	const addRow = (r: (string | number | null)[]) => rows.push(r);
	const merge = (r1: number, c1: number, r2: number, c2: number) =>
		merges.push({ s: { r: r1, c: c1 }, e: { r: r2, c: c2 } });

	addRow(["CMO PRODUCTIVITY", ...Array(totCols - 1).fill(null)]);
	merge(0, 0, 0, totCols - 1);
	addRow([`Approval Date : ${data.asof}`, ...Array(totCols - 1).fill(null)]);
	merge(1, 0, 1, totCols - 1);
	addRow([`${data.working_days} Working Days`, ...Array(totCols - 1).fill(null)]);
	merge(2, 0, 2, totCols - 1);

	for (const branch of data.branches) {
		const hr = rows.length;
		addRow(["No.", "Name", branch.branch_name, ...Array(numDays - 1).fill(null), "Total", "Avg/Day"]);
		merge(hr, 0, hr + 1, 0);
		merge(hr, 1, hr + 1, 1);
		merge(hr, 2, hr, numDays + 1);
		merge(hr, numDays + 2, hr + 1, numDays + 2);
		merge(hr, numDays + 3, hr + 1, numDays + 3);

		addRow([null, null, ...data.dates.map(d => Number(d.day_str)), null, null]);

		for (const emp of branch.employees) {
			addRow([emp.no, emp.fullname, ...emp.daily_counts, emp.total, emp.avg_per_day]);
		}

		addRow([branch.cmo_count, "Total", ...branch.day_totals, branch.branch_total, branch.branch_avg]);
	}

	addRow([data.grand_cmo_count, "Grand Total",
	...data.grand_day_totals, data.grand_total, data.grand_avg]);

	const ws = XLSX.utils.aoa_to_sheet(rows);
	ws["!merges"] = merges;
	ws["!cols"] = [
		{ wch: 5 }, { wch: 22 },
		...Array(numDays).fill({ wch: 4 }),
		{ wch: 8 }, { wch: 8 },
	];
	const wb = XLSX.utils.book_new();
	XLSX.utils.book_append_sheet(wb, ws, "CMOProductivity");
	XLSX.writeFile(wb, "SummaryCAMbyCMO.xlsx");
}

function MonthYearSelect({ month, year, onMonthChange, onYearChange }: {
	month: number; year: number;
	onMonthChange: (m: number) => void; onYearChange: (y: number) => void;
}) {
	const cls = "px-2 py-1.5 text-sm border border-gray-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500";
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

const tdBase: React.CSSProperties = { border: "1px solid #ccc", padding: "2px 4px", fontSize: 11 };
const thBase: React.CSSProperties = { ...tdBase, fontWeight: "bold", backgroundColor: "#f9fafb" };

const MonthlySummaryCAMApprovedPage: React.FC = () => {
	const [bulan, setBulan] = useState<number>(CUR_MONTH);
	const [tahun, setTahun] = useState<number>(CUR_YEAR);
	const [data, setData] = useState<ReportData | null>(null);
	const [loading, setLoading] = useState<boolean>(false);
	const [error, setError] = useState<string | null>(null);
	const [shouldPrint, setShouldPrint] = useState<boolean>(false);

	useEffect(() => {
		if (shouldPrint && data) { window.print(); setShouldPrint(false); }
	}, [shouldPrint, data]);

	const fetchData = async (): Promise<ReportData | null> => {
		setLoading(true); setError(null);
		try {
			const res = await api.get<ReportData>("/CAM/Others/MonthlySummaryCAMApproved/api/data", { params: { bulan, tahun } });
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
		if (data) { window.print(); }
		else { const d = await fetchData(); if (d) setShouldPrint(true); }
	};

	const handleExport = async () => {
		const d = data ?? await fetchData();
		if (d) exportExcel(d);
	};

	const dates = data?.dates ?? [];
	const numDays = dates.length;

	const TableBody = ({ isPrint }: { isPrint: boolean }) => {
		if (!data || !numDays) return null;
		const cellSz = isPrint ? 10 : 11;
		const tdS = (extra?: React.CSSProperties): React.CSSProperties =>
			({ ...tdBase, fontSize: cellSz, textAlign: "center", ...extra });
		const thS = (extra?: React.CSSProperties): React.CSSProperties =>
			({ ...thBase, fontSize: cellSz, textAlign: "center", ...extra });

		return (
			<>
				{data.branches.map((branch) => (
					<>
						<tr key={`${branch.branch_cd}-h1`}>
							<th rowSpan={2} style={thS({ width: NO_W, minWidth: NO_W })}>No.</th>
							<th rowSpan={2} style={thS({ minWidth: NAME_W, textAlign: "left", paddingLeft: 4 })}>Name</th>
							<th colSpan={numDays} style={thS()}>{branch.branch_name}</th>
							<th rowSpan={2} style={thS()}>Total</th>
							<th rowSpan={2} style={thS()}>Avg/Day</th>
						</tr>
						<tr key={`${branch.branch_cd}-h2`}>
							{dates.map((d) => (
								<th key={d.day_num} style={thS({ backgroundColor: d.is_holiday ? HOLIDAY_BG : "#f9fafb", width: 22, minWidth: 22 })}>
									{d.day_str}
								</th>
							))}
						</tr>

						{branch.employees.map((emp) => {
							const bg = rowBg(emp);
							return (
								<tr key={emp.employee_id} style={{ backgroundColor: bg }}>
									<td style={tdS({ backgroundColor: bg })}>{emp.no}</td>
									<td style={tdS({ textAlign: "left", paddingLeft: 4, backgroundColor: bg, color: emp.name_color || "#000", fontWeight: emp.is_cmh ? "bold" : "normal", whiteSpace: "nowrap" })}>
										{emp.fullname}
									</td>
									{emp.daily_counts.map((count, di) => (
										<td key={di} style={tdS({ backgroundColor: dates[di].is_holiday ? HOLIDAY_BG : bg })}>
											{count > 0 ? count : ""}
										</td>
									))}
									<td style={tdS({ backgroundColor: bg })}>{emp.total}</td>
									<td style={tdS({ backgroundColor: bg })}>{emp.avg_per_day}</td>
								</tr>
							);
						})}

						<tr key={`${branch.branch_cd}-tot`} style={{ backgroundColor: GRAY_TOTAL }}>
							<td style={tdS({ backgroundColor: GRAY_TOTAL, fontWeight: "bold" })}>{branch.cmo_count}</td>
							<td style={tdS({ backgroundColor: GRAY_TOTAL, fontWeight: "bold", textAlign: "left", paddingLeft: 4 })}>Total</td>
							{branch.day_totals.map((t, di) => (
								<td key={di} style={tdS({ backgroundColor: dates[di].is_holiday ? HOLIDAY_BG : GRAY_TOTAL, fontWeight: "bold" })}>
									{t > 0 ? t : ""}
								</td>
							))}
							<td style={tdS({ backgroundColor: GRAY_TOTAL, fontWeight: "bold" })}>{branch.branch_total}</td>
							<td style={tdS({ backgroundColor: GRAY_TOTAL, fontWeight: "bold" })}>{branch.branch_avg}</td>
						</tr>
					</>
				))}

				<tr style={{ backgroundColor: GRAY_GRAND }}>
					<td style={tdS({ backgroundColor: GRAY_GRAND, fontWeight: "bold" })}>{data.grand_cmo_count}</td>
					<td style={tdS({ backgroundColor: GRAY_GRAND, fontWeight: "bold", textAlign: "left", paddingLeft: 4 })}>Grand Total</td>
					{data.grand_day_totals.map((t, di) => (
						<td key={di} style={tdS({ backgroundColor: dates[di].is_holiday ? HOLIDAY_BG : GRAY_GRAND, fontWeight: "bold" })}>
							{t > 0 ? t : ""}
						</td>
					))}
					<td style={tdS({ backgroundColor: GRAY_GRAND, fontWeight: "bold" })}>{data.grand_total}</td>
					<td style={tdS({ backgroundColor: GRAY_GRAND, fontWeight: "bold" })}>{data.grand_avg}</td>
				</tr>
			</>
		);
	};

	return (
		<>
			<style>{`
				@media print {
					.screen-only { display: none !important; }
					.print-only  { display: block !important; }
					body { font-family: Tahoma, Arial, sans-serif; font-size: 10px; }
					@page { size: landscape; margin: 8mm; }
				}
				@media screen { .print-only { display: none; } }
				.sticky-no   { position: sticky; left: 0; z-index: 2; }
				.sticky-name { position: sticky; left: ${NO_W}px; z-index: 2; }
			`}</style>

			<div className="screen-only min-h-screen bg-gray-50 p-4 md:p-6">
				<div className="max-w-full mx-auto">

					<div className="mb-6">
						<h1 className="text-2xl font-semibold text-gray-800">CMO Productivity</h1>
						<p className="text-sm text-gray-500 mt-1">Monthly Summary CAM Approved by CMO</p>
					</div>

					<div className="bg-white rounded-xl border border-gray-200 p-4 mb-6 flex flex-wrap gap-3 items-end">
						<div>
							<label className="block text-xs font-medium text-gray-500 mb-1">Approval Date</label>
							<div className="flex gap-2">
								<MonthYearSelect month={bulan} year={tahun} onMonthChange={setBulan} onYearChange={setTahun} />
							</div>
						</div>
						<button onClick={handlePreview} disabled={loading}
							className="px-4 py-2 text-sm font-medium rounded-lg bg-blue-50 text-blue-800 border border-blue-200 hover:bg-blue-100 disabled:opacity-40 disabled:cursor-not-allowed">
							{loading ? "Memuat…" : "Preview"}
						</button>
						<button onClick={handlePrint} disabled={loading}
							className="px-4 py-2 text-sm font-medium rounded-lg bg-gray-50 text-gray-700 border border-gray-200 hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed">
							Print
						</button>
						<button onClick={handleExport} disabled={loading}
							className="px-4 py-2 text-sm font-medium rounded-lg bg-green-50 text-green-800 border border-green-200 hover:bg-green-100 disabled:opacity-40 disabled:cursor-not-allowed">
							Export to Excel
						</button>
					</div>

					{error && (
						<div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{error}</div>
					)}
					{loading && <div className="py-16 text-center text-sm text-gray-400">Memuat data… (memerlukan beberapa saat)</div>}

					{!loading && !data && (
						<div className="py-16 text-center text-sm text-gray-400 border border-dashed border-gray-300 rounded-xl">
							Pilih periode dan klik <span className="font-medium">Preview</span> untuk menampilkan data
						</div>
					)}

					{!loading && data && (
						<>
							<div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
								{[
									{ label: "As of", value: data.asof },
									{ label: "Working Days", value: data.working_days },
									{ label: "Total CMOs", value: data.grand_cmo_count },
									{ label: "Grand Total CAMs", value: data.grand_total },
								].map((m) => (
									<div key={m.label} className="bg-gray-50 rounded-lg p-3">
										<div className="text-xs text-gray-400 mb-1">{m.label}</div>
										<div className="text-lg font-semibold tabular-nums text-gray-800">{m.value}</div>
									</div>
								))}
							</div>

							<div className="flex gap-4 mb-3 text-xs text-gray-500">
								<span className="flex items-center gap-1">
									<span className="inline-block w-3 h-3 rounded" style={{ backgroundColor: CMH_BG }} /> CMH (Manager)
								</span>
								<span className="flex items-center gap-1">
									<span className="inline-block w-3 h-3 rounded" style={{ backgroundColor: HOLIDAY_BG }} /> Holiday / Weekend
								</span>
								<span className="flex items-center gap-1 text-red-600 font-medium">● Resigned / Kondisi Merah</span>
							</div>

							<div className="bg-white rounded-xl border border-gray-200 overflow-auto">
								<table style={{ borderCollapse: "collapse", fontSize: 11, whiteSpace: "nowrap" }}>
									<tbody>
										{data.branches.map((branch) => (
											<>
												<tr key={`${branch.branch_cd}-h1`}>
													<th rowSpan={2} className="sticky-no"
														style={{ ...thBase, width: NO_W, minWidth: NO_W, textAlign: "center" }}>No.</th>
													<th rowSpan={2} className="sticky-name"
														style={{ ...thBase, minWidth: NAME_W, textAlign: "left", paddingLeft: 4 }}>Name</th>
													<th colSpan={numDays}
														style={{ ...thBase, textAlign: "center", backgroundColor: "#dbeafe" }}>
														{branch.branch_name}
													</th>
													<th rowSpan={2} style={{ ...thBase, textAlign: "center" }}>Total</th>
													<th rowSpan={2} style={{ ...thBase, textAlign: "center" }}>Avg/Day</th>
												</tr>
												<tr key={`${branch.branch_cd}-h2`}>
													{dates.map((d) => (
														<th key={d.day_num} style={{
															...thBase, textAlign: "center",
															width: 26, minWidth: 26,
															backgroundColor: d.is_holiday ? HOLIDAY_BG : "#f9fafb",
															color: d.is_holiday ? "#b91c1c" : "#374151",
														}}>
															{d.day_str}
														</th>
													))}
												</tr>

												{branch.employees.map((emp) => {
													const bg = rowBg(emp);
													return (
														<tr key={emp.employee_id} style={{ backgroundColor: bg }}>
															<td className="sticky-no" style={{ ...tdBase, width: NO_W, textAlign: "center", backgroundColor: bg }}>{emp.no}</td>
															<td className="sticky-name" style={{
																...tdBase, minWidth: NAME_W, textAlign: "left", paddingLeft: 4,
																backgroundColor: bg, color: emp.name_color || "#000",
																fontWeight: emp.is_cmh ? "bold" : "normal",
															}}>
																{emp.fullname}
															</td>
															{emp.daily_counts.map((count, di) => (
																<td key={di} style={{
																	...tdBase, textAlign: "center",
																	backgroundColor: dates[di].is_holiday ? HOLIDAY_BG : bg,
																}}>
																	{count > 0 ? count : ""}
																</td>
															))}
															<td style={{ ...tdBase, textAlign: "center", fontWeight: "bold" }}>{emp.total}</td>
															<td style={{ ...tdBase, textAlign: "center" }}>{emp.avg_per_day}</td>
														</tr>
													);
												})}

												<tr key={`${branch.branch_cd}-tot`} style={{ backgroundColor: GRAY_TOTAL }}>
													<td className="sticky-no" style={{ ...tdBase, width: NO_W, textAlign: "center", fontWeight: "bold", backgroundColor: GRAY_TOTAL }}>{branch.cmo_count}</td>
													<td className="sticky-name" style={{ ...tdBase, fontWeight: "bold", textAlign: "left", paddingLeft: 4, backgroundColor: GRAY_TOTAL }}>Total</td>
													{branch.day_totals.map((t, di) => (
														<td key={di} style={{ ...tdBase, textAlign: "center", fontWeight: "bold", backgroundColor: dates[di].is_holiday ? HOLIDAY_BG : GRAY_TOTAL }}>
															{t > 0 ? t : ""}
														</td>
													))}
													<td style={{ ...tdBase, textAlign: "center", fontWeight: "bold" }}>{branch.branch_total}</td>
													<td style={{ ...tdBase, textAlign: "center", fontWeight: "bold" }}>{branch.branch_avg}</td>
												</tr>
											</>
										))}

										<tr style={{ backgroundColor: GRAY_GRAND }}>
											<td className="sticky-no" style={{ ...tdBase, width: NO_W, textAlign: "center", fontWeight: "bold", backgroundColor: GRAY_GRAND }}>{data.grand_cmo_count}</td>
											<td className="sticky-name" style={{ ...tdBase, fontWeight: "bold", textAlign: "left", paddingLeft: 4, backgroundColor: GRAY_GRAND }}>Grand Total</td>
											{data.grand_day_totals.map((t, di) => (
												<td key={di} style={{ ...tdBase, textAlign: "center", fontWeight: "bold", backgroundColor: dates[di].is_holiday ? HOLIDAY_BG : GRAY_GRAND }}>
													{t > 0 ? t : ""}
												</td>
											))}
											<td style={{ ...tdBase, textAlign: "center", fontWeight: "bold" }}>{data.grand_total}</td>
											<td style={{ ...tdBase, textAlign: "center", fontWeight: "bold" }}>{data.grand_avg}</td>
										</tr>
									</tbody>
								</table>
							</div>
						</>
					)}
				</div>
			</div>

			{data && (
				<div className="print-only" style={{ fontFamily: "Tahoma, Arial, sans-serif", fontSize: 10, padding: "10px 15px" }}>
					<table style={{ width: "100%", borderCollapse: "collapse", marginBottom: 8 }}>
						<tbody>
							<tr>
								<td colSpan={4} align="center" style={{ fontSize: 14, fontWeight: "bold", letterSpacing: "0.15em" }}>
									CMO PRODUCTIVITY
								</td>
							</tr>
							<tr>
								<td colSpan={4} align="center" style={{ fontSize: 12, fontWeight: "bold" }}>
									Approval Date : {data.asof}
								</td>
							</tr>
							<tr>
								<td colSpan={4} align="center" style={{ fontSize: 11 }}>
									({data.working_days} Working Days)
								</td>
							</tr>
						</tbody>
					</table>

					<table border={1} cellPadding={2} cellSpacing={0} style={{ width: "100%", borderCollapse: "collapse" }}>
						<tbody>
							<TableBody isPrint />
						</tbody>
					</table>
				</div>
			)}
		</>
	);
};

export default MonthlySummaryCAMApprovedPage;