import { useState, useEffect, useMemo } from "react";
import api from "../../../../api/axiosInstance";
import { DEFAULT_PAGE_LIMIT } from "../../../../constants/DefaultValue";

interface Brand { brand: string; brand_nm: string; }
interface Model { model: string; model_nm: string; }
interface VType { type: string; type_nm: string; }
interface MRPRow {
	brand_nm: string; model_nm: string; type_nm: string;
	karoseri: string; tahun: string;
	l_amount: number; execution: string;
}

const ROWS_PER_PAGE = DEFAULT_PAGE_LIMIT;

const fmtNum = (v: number) => new Intl.NumberFormat("id-ID").format(Math.round(v));

function getPageNumbers(cur: number, total: number): (number | "…")[] {
	const add = (p: number, set: Set<number>) => { if (p >= 1 && p <= total) set.add(p); };
	const s = new Set<number>();
	[1, 2, cur - 1, cur, cur + 1, total - 1, total].forEach(p => add(p, s));
	const pages = Array.from(s).sort((a, b) => a - b);
	const result: (number | "…")[] = [];
	pages.forEach((p, i) => {
		if (i > 0 && p - pages[i - 1] > 1) result.push("…");
		result.push(p);
	});
	return result;
}

const HistoryMRP: React.FC = () => {
	const [brands, setBrands] = useState<Brand[]>([]);
	const [models, setModels] = useState<Model[]>([]);
	const [types, setTypes] = useState<VType[]>([]);

	const [brand, setBrand] = useState<string>("");
	const [model, setModel] = useState<string>("");
	const [type, setType] = useState<string>("");

	const [rows, setRows] = useState<MRPRow[]>([]);
	const [loading, setLoading] = useState<boolean>(false);
	const [typeLoading, setTypeLoading] = useState<boolean>(false);
	const [error, setError] = useState<string | null>(null);
	const [hasSearched, setHasSearched] = useState<boolean>(false);
	const [currentPage, setCurrentPage] = useState<number>(1);

	useEffect(() => {
		api.get<Brand[]>("/CAM/Others/HistoryMRP/api/brands")
			.then(res => setBrands(res.data))
			.catch(() => { });
		api.get<Model[]>("/CAM/Others/HistoryMRP/api/models")
			.then(res => setModels(res.data))
			.catch(() => { });
	}, []);

	useEffect(() => {
		setType("");
		setTypes([]);
		if (!brand || !model) return;

		setTypeLoading(true);
		api.get<VType[]>("/CAM/Others/HistoryMRP/api/types", { params: { brand, model } })
			.then(res => setTypes(res.data))
			.catch(() => setTypes([]))
			.finally(() => setTypeLoading(false));
	}, [brand, model]);

	const handleSearch = async () => {
		if (!brand) { alert("Please select brand first!"); return; }
		if (!model) { alert("Please select model first!"); return; }
		if (!type) { alert("Please select type first!"); return; }

		setLoading(true);
		setError(null);
		setRows([]);
		setCurrentPage(1);
		setHasSearched(true);

		try {
			const res = await api.get<MRPRow[]>("/CAM/Others/HistoryMRP/api/data", {
				params: { brand, model, type },
			});
			setRows(res.data);
		} catch {
			setError("Gagal memuat data. Silakan coba lagi.");
		} finally {
			setLoading(false);
		}
	};

	const totalPages = Math.ceil(rows.length / ROWS_PER_PAGE);
	const paginated = useMemo(
		() => rows.slice((currentPage - 1) * ROWS_PER_PAGE, currentPage * ROWS_PER_PAGE),
		[rows, currentPage],
	);
	const pageNumbers = useMemo(() => getPageNumbers(currentPage, totalPages), [currentPage, totalPages]);

	const selectCls = (disabled?: boolean) =>
		`w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white text-gray-800
		 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500
		 ${disabled ? "opacity-60 cursor-not-allowed" : ""}`;

	const TH = "px-3 py-2 text-xs font-semibold text-gray-600 bg-gray-50 border-b border-gray-200 text-center whitespace-nowrap";
	const TD = (right = false) =>
		`px-3 py-1.5 text-sm border-b border-gray-100 ${right ? "text-right tabular-nums" : "text-center"} text-gray-700`;

	return (
		<div className="min-h-screen bg-gray-50 p-4 md:p-6">
			<div className="max-w-7xl mx-auto">

				<div className="mb-6">
					<h1 className="text-2xl font-semibold text-gray-800">History MRP</h1>
					<p className="text-sm text-gray-500 mt-1">Data disbursement 3 bulan terakhir</p>
				</div>

				<div className="bg-white rounded-xl border border-gray-200 p-4 mb-6">
					<div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
						<div>
							<label className="block text-xs font-medium text-gray-500 mb-1">
								Brand <span className="text-red-500">*</span>
							</label>
							<select
								value={brand}
								onChange={e => { setBrand(e.target.value); setRows([]); setHasSearched(false); }}
								className={selectCls()}
							>
								<option value="">Select</option>
								{brands.map(b => (
									<option key={b.brand} value={b.brand}>{b.brand_nm}</option>
								))}
							</select>
						</div>

						<div>
							<label className="block text-xs font-medium text-gray-500 mb-1">
								Model <span className="text-red-500">*</span>
							</label>
							<select
								value={model}
								onChange={e => { setModel(e.target.value); setRows([]); setHasSearched(false); }}
								className={selectCls()}
							>
								<option value="">Select</option>
								{models.map(m => (
									<option key={m.model} value={m.model}>{m.model_nm}</option>
								))}
							</select>
						</div>

						<div>
							<label className="block text-xs font-medium text-gray-500 mb-1">
								Type <span className="text-red-500">*</span>
							</label>
							<select
								value={type}
								onChange={e => { setType(e.target.value); setRows([]); setHasSearched(false); }}
								disabled={!brand || !model || typeLoading}
								className={selectCls(!brand || !model || typeLoading)}
							>
								<option value="">
									{typeLoading ? "Loading…" : (!brand || !model) ? "Select brand & model first" : "Select"}
								</option>
								{types.map(t => (
									<option key={t.type} value={t.type}>{t.type_nm}</option>
								))}
							</select>
						</div>
					</div>

					<button
						onClick={handleSearch}
						disabled={loading}
						className="px-4 py-2 text-sm font-medium rounded-lg bg-blue-50 text-blue-800
							border border-blue-200 hover:bg-blue-100
							disabled:opacity-40 disabled:cursor-not-allowed transition-all"
					>
						{loading ? "Mencari…" : "Search"}
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
						Pilih Brand, Model, dan Type, lalu klik <span className="font-medium">Search</span>
					</div>
				)}
				{!loading && hasSearched && rows.length === 0 && !error && (
					<div className="py-16 text-center text-sm text-gray-400 border border-dashed border-gray-300 rounded-xl">
						Tidak ada data untuk kombinasi yang dipilih
					</div>
				)}

				{!loading && rows.length > 0 && (
					<>
						<div className="flex items-center gap-3 mb-3">
							<span className="text-sm text-gray-500">
								<span className="font-medium text-gray-800">{rows.length}</span> records
								&nbsp;·&nbsp; 3 bulan terakhir
							</span>
						</div>

						<div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
							<div className="overflow-x-auto">
								<table className="w-full border-collapse">
									<thead>
										<tr>
											<th className={TH} style={{ width: 50 }}>No.</th>
											<th className={TH}>Brand</th>
											<th className={TH}>Model</th>
											<th className={TH}>Type</th>
											<th className={TH}>Karoseri</th>
											<th className={TH}>Year</th>
											<th className={TH}>Asset Value</th>
											<th className={TH}>Disbursement Date</th>
										</tr>
									</thead>
									<tbody>
										{paginated.map((row, idx) => {
											const globalIdx = (currentPage - 1) * ROWS_PER_PAGE + idx;
											return (
												<tr key={idx} className={globalIdx % 2 === 0 ? "bg-white" : "bg-gray-50"}>
													<td className={TD()}>{globalIdx + 1}.</td>
													<td className={TD()}>{row.brand_nm}</td>
													<td className="px-3 py-1.5 text-sm border-b border-gray-100 text-gray-700">{row.model_nm}</td>
													<td className="px-3 py-1.5 text-sm border-b border-gray-100 text-gray-700">{row.type_nm}</td>
													<td className="px-3 py-1.5 text-sm border-b border-gray-100 text-gray-700">{row.karoseri}</td>
													<td className={TD()}>{row.tahun}</td>
													<td className={TD(true)}>{fmtNum(row.l_amount)}</td>
													<td className={TD()}>{row.execution}</td>
												</tr>
											);
										})}
									</tbody>
								</table>
							</div>

							{totalPages > 1 && (
								<div className="flex items-center justify-center gap-1 py-3 border-t border-gray-200 flex-wrap">
									<button onClick={() => setCurrentPage(1)} disabled={currentPage === 1}
										className="px-2 py-1 text-xs rounded border border-gray-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-gray-50"
										title="First page">«</button>
									<button onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={currentPage === 1}
										className="px-2 py-1 text-xs rounded border border-gray-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-gray-50"
										title="Previous page">‹</button>

									{pageNumbers.map((p, i) =>
										p === "…" ? (
											<span key={`el-${i}`} className="px-1 text-xs text-gray-400">…</span>
										) : (
											<button key={p} onClick={() => setCurrentPage(p as number)}
												className={`px-3 py-1 text-xs rounded border transition-colors ${currentPage === p ? "bg-blue-600 text-white border-blue-600 font-bold" : "border-gray-300 hover:bg-gray-50"}`}>
												{p}
											</button>
										),
									)}

									<button onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))} disabled={currentPage === totalPages}
										className="px-2 py-1 text-xs rounded border border-gray-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-gray-50"
										title="Next page">›</button>
									<button onClick={() => setCurrentPage(totalPages)} disabled={currentPage === totalPages}
										className="px-2 py-1 text-xs rounded border border-gray-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-gray-50"
										title="Last page">»</button>
								</div>
							)}
						</div>
					</>
				)}
			</div>
		</div>
	);
};

export default HistoryMRP;