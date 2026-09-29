import React, { useState } from "react";
import api from "../../../../api/axiosInstance";

interface ModelRow {
	MODEL_NM: string;
}

const ListModelPage: React.FC = () => {
	const [rows, setRows] = useState<ModelRow[]>([]);
	const [loading, setLoading] = useState(false);
	const [exporting, setExporting] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [previewed, setPreviewed] = useState(false);

	const fetchData = async (): Promise<ModelRow[]> => {
		const res = await api.get('/MasterData/api/list-model', {
		});
		return res.data.data;
	};

	const handlePreview = async () => {
		setLoading(true);
		setError(null);
		try {
			const data = await fetchData();
			setRows(data);
			setPreviewed(true);
		} catch {
			setError("Failed to load data. Please try again.");
		} finally {
			setLoading(false);
		}
	};

	const handlePrint = async () => {
		try {
			const data = previewed ? rows : await fetchData();
			const rowsHtml = data.map((r, i) => `
                <tr>
                    <td>${i + 1}</td>
                    <td>${r.MODEL_NM}</td>
                </tr>
            `).join("");

			const win = window.open("", "_blank");
			if (!win) return;
			win.document.write(`
                <html>
                <head>
                    <title>List of Model</title>
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
                    <h2>List of Model</h2>
                    <table>
                        <thead>
                            <tr>
                                <th width="10%">No.</th>
                                <th width="90%">Model</th>
                            </tr>
                        </thead>
                        <tbody>${rowsHtml}</tbody>
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

	const handleExportExcel = async () => {
		setExporting(true);
		try {
			const data = previewed ? rows : await fetchData();
			const XLSX = await import("xlsx");
			const wsData = [
				["No.", "Model"],
				...data.map((r, i) => [i + 1, r.MODEL_NM]),
			];
			const ws = XLSX.utils.aoa_to_sheet(wsData);
			const wb = XLSX.utils.book_new();
			XLSX.utils.book_append_sheet(wb, ws, "List of Model");
			XLSX.writeFile(wb, "list_of_model.xlsx");
		} catch {
			alert("Export failed. Please try again.");
		} finally {
			setExporting(false);
		}
	};

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-6xl mx-auto space-y-6">

				<div className="bg-white rounded-2xl shadow-lg p-6">
					<h1 className="text-2xl md:text-3xl font-bold text-gray-800 mb-6">List of Model</h1>

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
							disabled={loading}
							className="border border-gray-300 text-gray-700 hover:bg-gray-50 px-6 py-2 rounded-lg font-medium transition-all flex items-center gap-2"
						>
							<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" />
							</svg>
							Print
						</button>

						<button
							onClick={handleExportExcel}
							disabled={loading || exporting}
							className={`bg-green-600 hover:bg-green-700 text-white px-6 py-2 rounded-lg font-medium transition-all flex items-center gap-2 ${(loading || exporting) ? "opacity-75 cursor-not-allowed" : ""}`}
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
								Total: {rows.length}
							</span>
						</div>

						{error && (
							<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
								{error}
								<button onClick={handlePreview} className="ml-4 underline text-red-900">Retry</button>
							</div>
						)}

						<div className="overflow-x-auto rounded-lg border border-gray-200">
							<table className="w-full">
								<thead className="bg-gradient-to-r from-gray-50 to-gray-100">
									<tr>
										<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-20">No.</th>
										<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Model</th>
									</tr>
								</thead>
								<tbody className="divide-y divide-gray-200">
									{rows.length === 0 ? (
										<tr>
											<td colSpan={2} className="py-10 px-6 text-center text-red-500 font-medium text-lg">
												Data Not Found..
											</td>
										</tr>
									) : (
										rows.map((row, idx) => (
											<tr
												key={idx}
												className={`hover:bg-blue-50 transition-colors ${idx % 2 === 0 ? "bg-white" : "bg-gray-50"}`}
											>
												<td className="py-4 px-6 text-sm text-gray-500">{idx + 1}</td>
												<td className="py-4 px-6 text-sm text-gray-800 font-medium">{row.MODEL_NM}</td>
											</tr>
										))
									)}
								</tbody>
							</table>
						</div>
					</div>
				)}
			</div>
		</div>
	);
};

export default ListModelPage;