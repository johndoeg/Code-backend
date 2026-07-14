import React, { useEffect, useState, useCallback } from "react";
import api from "../../../../api/axiosInstance";
import Pagination from "../../../../helpers/Pagination";
import { DEFAULT_PAGE_LIMIT } from "../../../../constants/DefaultValue";

interface VehicleRow {
	TYPE: string;
	TYPE_NM: string;
	BRAND_NM: string;
	MODEL_NM: string;
}

interface SelectOption {
	value: string;
	label: string;
}

const ListBrandPage: React.FC = () => {
	const [rows, setRows] = useState<VehicleRow[]>([]);
	const [total, setTotal] = useState(0);
	const [page, setPage] = useState(1);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [previewed, setPreviewed] = useState(false);
	const limit = DEFAULT_PAGE_LIMIT;

	const [brand, setBrand] = useState("");
	const [model, setModel] = useState("");
	const [appliedBrand, setAppliedBrand] = useState("");
	const [appliedModel, setAppliedModel] = useState("");

	const [brandOptions, setBrandOptions] = useState<SelectOption[]>([]);
	const [modelOptions, setModelOptions] = useState<SelectOption[]>([]);

	const [exporting, setExporting] = useState(false);

	useEffect(() => {
		const fetchOptions = async () => {
			try {
				const [brandsRes, modelsRes] = await Promise.all([
					api.get('/MasterData/api/list-brand/brand-options'),
					api.get('/MasterData/api/list-brand/model-options'),
				]);
				setBrandOptions(brandsRes.data.data.map((b: any) => ({ value: b.BRAND, label: b.BRAND_NM })));
				setModelOptions(modelsRes.data.data.map((m: any) => ({ value: m.MODEL, label: m.MODEL_NM })));
			} catch { }
		};
		fetchOptions();
	}, []);

	const fetchList = useCallback(async () => {
		if (!appliedBrand && !appliedModel) return;
		setLoading(true);
		setError(null);
		try {
			const response = await api.get('/MasterData/api/list-brand', {
				params: { brand: appliedBrand, model: appliedModel, page, limit },
			});
			setRows(response.data.data);
			setTotal(response.data.total);
		} catch {
			setError("Failed to load data. Please try again.");
		} finally {
			setLoading(false);
		}
	}, [appliedBrand, appliedModel, page]);

	useEffect(() => {
		if (previewed) fetchList();
	}, [fetchList, previewed]);

	const handlePreview = () => {
		if (!brand && !model) {
			alert("Please select at least Brand or Model.");
			return;
		}
		setAppliedBrand(brand);
		setAppliedModel(model);
		setPage(1);
		setPreviewed(true);
	};

	const handleExportExcel = async () => {
		if (!appliedBrand && !appliedModel) {
			alert("Please run Preview first.");
			return;
		}
		setExporting(true);
		try {
			const res = await api.get('/MasterData/api/list-brand/export', {
				params: { brand: appliedBrand, model: appliedModel },
			});
			const data: VehicleRow[] = res.data.data;

			const XLSX = await import("xlsx");
			const wsData = [
				["No.", "Brand", "Model", "Type", "Type Name"],
				...data.map((r, i) => [i + 1, r.BRAND_NM, r.MODEL_NM, r.TYPE, r.TYPE_NM]),
			];
			const ws = XLSX.utils.aoa_to_sheet(wsData);
			const wb = XLSX.utils.book_new();
			XLSX.utils.book_append_sheet(wb, ws, "List of Brand");
			XLSX.writeFile(wb, "list_of_brand.xlsx");
		} catch {
			alert("Export failed. Please try again.");
		} finally {
			setExporting(false);
		}
	};

	const handlePrint = async () => {
		if (!appliedBrand && !appliedModel) {
			alert("Please run Preview first.");
			return;
		}
		try {
			const res = await api.get('/MasterData/api/list-brand/export', {
				params: { brand: appliedBrand, model: appliedModel },
			});
			const data: VehicleRow[] = res.data.data;

			const rows = data.map((r, i) => `
                <tr>
                    <td>${i + 1}</td>
                    <td>${r.BRAND_NM}</td>
                    <td>${r.MODEL_NM}</td>
                    <td>${r.TYPE}</td>
                    <td>${r.TYPE_NM}</td>
                </tr>
            `).join("");

			const win = window.open("", "_blank");
			if (!win) return;
			win.document.write(`
                <html>
                <head>
                    <title>List of Brand</title>
                    <style>
                        body { font-family: Arial, sans-serif; font-size: 12px; margin: 20px; }
                        h2 { text-align: center; margin-bottom: 16px; }
                        table { width: 100%; border-collapse: collapse; }
                        th, td { border: 1px solid #ccc; padding: 6px 10px; text-align: left; }
                        th { background-color: #f0f0f0; font-weight: bold; }
                        tr:nth-child(even) { background-color: #f9f9f9; }
                    </style>
                </head>
                <body>
                    <h2>List of Brand</h2>
                    <table>
                        <thead>
                            <tr>
                                <th>No.</th>
                                <th>Brand</th>
                                <th>Model</th>
                                <th>Type</th>
                                <th>Type Name</th>
                            </tr>
                        </thead>
                        <tbody>${rows}</tbody>
                    </table>
                    <script>window.onload = () => { window.print(); window.close(); }<\/script>
                </body>
                </html>
            `);
			win.document.close();
		} catch {
			alert("Print failed. Please try again.");
		}
	};

	const totalPages = Math.ceil(total / limit);

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-7xl mx-auto space-y-6">

				<div className="bg-white rounded-2xl shadow-lg p-6">
					<h1 className="text-2xl md:text-3xl font-bold text-gray-800 mb-6">List of Brand</h1>

					<div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
						<div>
							<label className="block text-sm font-medium text-gray-700 mb-1">Brand</label>
							<select
								value={brand}
								onChange={(e) => setBrand(e.target.value)}
								className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
							>
								<option value="">Select</option>
								{brandOptions.map((b) => (
									<option key={b.value} value={b.value}>{b.label}</option>
								))}
							</select>
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700 mb-1">Model</label>
							<select
								value={model}
								onChange={(e) => setModel(e.target.value)}
								className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
							>
								<option value="">Select</option>
								{modelOptions.map((m) => (
									<option key={m.value} value={m.value}>{m.label}</option>
								))}
							</select>
						</div>
					</div>

					<div className="flex flex-wrap gap-3">
						<button
							onClick={handlePreview}
							disabled={loading}
							className={`bg-gradient-to-r from-blue-600 to-indigo-700 hover:from-blue-700 hover:to-indigo-800 text-white px-6 py-2 rounded-lg font-medium shadow-md transition-all flex items-center gap-2 ${loading ? "opacity-75 cursor-not-allowed" : ""}`}
						>
							{loading ? (
								<>
									<svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
										<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
										<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
									</svg>
									Loading...
								</>
							) : (
								<>
									<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
										<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
									</svg>
									Preview
								</>
							)}
						</button>

						<button
							onClick={handlePrint}
							disabled={!previewed}
							className={`border border-gray-300 text-gray-700 hover:bg-gray-50 px-6 py-2 rounded-lg font-medium transition-all flex items-center gap-2 ${!previewed ? "opacity-40 cursor-not-allowed" : ""}`}
						>
							<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" />
							</svg>
							Print
						</button>

						<button
							onClick={handleExportExcel}
							disabled={!previewed || exporting}
							className={`bg-green-600 hover:bg-green-700 text-white px-6 py-2 rounded-lg font-medium transition-all flex items-center gap-2 ${(!previewed || exporting) ? "opacity-40 cursor-not-allowed" : ""}`}
						>
							<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
							</svg>
							{exporting ? "Exporting..." : "Export to Excel"}
						</button>
					</div>
				</div>

				{previewed && (
					<div className="bg-white rounded-2xl shadow-lg p-6">
						<div className="flex items-center justify-between mb-4">
							<h2 className="text-lg font-semibold text-gray-800">Results</h2>
							<span className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm font-medium">
								Total: {total}
							</span>
						</div>

						{error && (
							<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
								{error}
								<button onClick={fetchList} className="ml-4 underline text-red-900">Retry</button>
							</div>
						)}

						<div className="overflow-x-auto rounded-lg border border-gray-200">
							<table className="w-full">
								<thead className="bg-gradient-to-r from-gray-50 to-gray-100">
									<tr>
										<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-16">No.</th>
										<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Brand</th>
										<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Model</th>
										<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
										<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type Name</th>
									</tr>
								</thead>
								<tbody className="divide-y divide-gray-200">
									{rows.length === 0 && !loading ? (
										<tr>
											<td colSpan={5} className="py-10 px-6 text-center text-red-500 font-medium text-lg">
												Data Not Found..
											</td>
										</tr>
									) : (
										<>
											{rows.map((row, idx) => (
												<tr
													key={`${row.TYPE}-${idx}`}
													className={`hover:bg-blue-50 transition-colors ${idx % 2 === 0 ? "bg-white" : "bg-gray-50"}`}
												>
													<td className="py-4 px-6 text-sm text-gray-500">
														{(page - 1) * limit + idx + 1}
													</td>
													<td className="py-4 px-6 text-sm font-medium text-gray-900">{row.BRAND_NM}</td>
													<td className="py-4 px-6 text-sm text-gray-700">{row.MODEL_NM}</td>
													<td className="py-4 px-6 text-sm text-gray-700">{row.TYPE}</td>
													<td className="py-4 px-6 text-sm text-gray-700">{row.TYPE_NM}</td>
												</tr>
											))}
											{loading && (
												<tr>
													<td colSpan={5} className="py-4 px-6 text-center">
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

						{!loading && total > 0 && (
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
				)}
			</div>
		</div>
	);
};

export default ListBrandPage;