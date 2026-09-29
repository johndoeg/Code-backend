import { useState, useEffect } from "react";
import * as XLSX from "xlsx";
import api from "../../../../api/axiosInstance";

interface CustomerRow {
	lessee_nm: string;
	total: number;
}

const fmtNum = (v: number) =>
	new Intl.NumberFormat("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v);

function exportExcel(rows: CustomerRow[]): void {
	const data: (string | number)[][] = [
		["No.", "Customer Name", "Total Outstanding Principal"],
		...rows.map((r, i) => [i + 1, r.lessee_nm, r.total]),
	];

	const ws = XLSX.utils.aoa_to_sheet(data);
	ws["!cols"] = [{ wch: 5 }, { wch: 40 }, { wch: 25 }];

	const wb = XLSX.utils.book_new();
	XLSX.utils.book_append_sheet(wb, ws, "Top20Customer");
	XLSX.writeFile(wb, "Top20Customer.xlsx");
}

const Top20CustomerPage: React.FC = () => {
	const [data, setData] = useState<CustomerRow[]>([]);
	const [loading, setLoading] = useState<boolean>(true);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		api.get<CustomerRow[]>("/CAM/Others/Top20Customer/api/data")
			.then((res) => setData(res.data))
			.catch(() => setError("Gagal memuat data. Silakan refresh halaman."))
			.finally(() => setLoading(false));
	}, []);

	return (
		<div className="min-h-screen bg-gray-50 p-4 md:p-6">
			<div className="max-w-3xl mx-auto">
				<div className="mb-6 flex items-center justify-between flex-wrap gap-3">
					<div>
						<h1 className="text-2xl font-semibold text-gray-800">Top 20 Customer</h1>
						<p className="text-sm text-gray-500 mt-1">
							Ranked by total outstanding principal
						</p>
					</div>

					{data.length > 0 && (
						<button
							onClick={() => exportExcel(data)}
							className="inline-flex items-center px-4 py-2 text-sm font-medium rounded-lg
								bg-green-50 text-green-800 border border-green-200 hover:bg-green-100 transition-all"
						>
							Export to Excel
						</button>
					)}
				</div>

				{error && (
					<div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
						{error}
					</div>
				)}

				{loading && (
					<div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
						{Array.from({ length: 5 }).map((_, i) => (
							<div key={i} className="flex gap-4 px-4 py-3 border-b border-gray-100 animate-pulse">
								<div className="w-8 h-4 bg-gray-200 rounded" />
								<div className="flex-1 h-4 bg-gray-200 rounded" />
								<div className="w-32 h-4 bg-gray-200 rounded" />
							</div>
						))}
					</div>
				)}

				{!loading && data.length > 0 && (
					<div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
						<table className="w-full border-collapse text-sm">
							<thead>
								<tr className="bg-gray-50">
									<th className="px-4 py-3 text-xs font-medium text-gray-500 border-b border-gray-200 text-center w-14">
										No.
									</th>
									<th className="px-4 py-3 text-xs font-medium text-gray-500 border-b border-gray-200 text-left">
										Customer Name
									</th>
									<th className="px-4 py-3 text-xs font-medium text-gray-500 border-b border-gray-200 text-right">
										Total Outstanding Principal
									</th>
								</tr>
							</thead>
							<tbody>
								{data.map((row, i) => (
									<tr
										key={i}
										className={`${i % 2 === 0 ? "bg-white" : "bg-gray-50"} hover:bg-blue-50/40 transition-colors`}
									>
										<td className="px-4 py-2.5 text-center border-b border-gray-100">
											{i < 3 ? (
												<span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold text-white ${i === 0 ? "bg-yellow-400" : i === 1 ? "bg-gray-400" : "bg-amber-600"
													}`}>
													{i + 1}
												</span>
											) : (
												<span className="text-gray-400 tabular-nums">{i + 1}</span>
											)}
										</td>
										<td className="px-4 py-2.5 border-b border-gray-100 text-gray-800 font-medium">
											{row.lessee_nm}
										</td>
										<td className="px-4 py-2.5 border-b border-gray-100 text-right tabular-nums text-gray-700">
											{fmtNum(row.total)}
										</td>
									</tr>
								))}
							</tbody>
						</table>
					</div>
				)}

				{!loading && !error && data.length === 0 && (
					<div className="py-16 text-center text-sm text-gray-400 border border-dashed border-gray-300 rounded-xl">
						Tidak ada data
					</div>
				)}
			</div>
		</div>
	);
};

export default Top20CustomerPage;