import React, { useEffect, useState, useCallback } from "react";
import api from '../../../api/axiosInstance';

type ReportType = "premi" | "tpl" | "";

interface Company {
	ins_cd: string;
	ins_co: string;
}

interface Model {
	model: string;
	model_nm: string;
}

interface PremiRow {
	id: number | string;
	ins_co: string;
	model_nm: string;
	coverage: string;
	premi: string;
	insurance_area: string;
}

interface TplRow {
	ins_co: string;
	model_nm: string;
	tpl_amt: string;
	tpl_fee: string;
	tpl_fee2: string;
}


const Th: React.FC<{ children: React.ReactNode; className?: string }> = ({
	children, className = "",
}) => (
	<th className={`py-3 px-4 text-xs font-semibold text-slate-600 uppercase tracking-wider border border-slate-300 bg-slate-100 ${className}`}>
		{children}
	</th>
);

const Td: React.FC<{ children: React.ReactNode; className?: string }> = ({
	children, className = "",
}) => (
	<td className={`py-2 px-4 text-sm border-b border-slate-200 ${className}`}>
		{children}
	</td>
);

const ListOfInsuranceReportPage: React.FC = () => {
	const [companies, setCompanies] = useState<Company[]>([]);
	const [models, setModels] = useState<Model[]>([]);
	const [selIns, setSelIns] = useState("00");
	const [selModel, setSelModel] = useState("00");
	const [reportType, setReportType] = useState<ReportType>("");

	const [premiRows, setPremiRows] = useState<PremiRow[]>([]);
	const [tplRows, setTplRows] = useState<TplRow[]>([]);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [submitted, setSubmitted] = useState(false);

	useEffect(() => {
		api.get('/MasterData/api/companies')
			.then(r => setCompanies(r.data))
			.catch(() => setError("Failed to load insurance companies."));

		api.get('/MasterData/api/models')
			.then(r => setModels(r.data))
			.catch(() => setError("Failed to load models."));
	}, []);

	const handlePreview = useCallback(async () => {
		if (!reportType) {
			alert("Please select a report type (Premi or TPL).");
			return;
		}

		setLoading(true);
		setError(null);
		setSubmitted(false);
		setPremiRows([]);
		setTplRows([]);

		const params = { ins_cd: selIns, model: selModel };

		try {
			if (reportType === "premi") {
				const res = await api.get('/MasterData/api/premi', { params });
				setPremiRows(res.data);
			} else {
				const res = await api.get('/MasterData/api/tpl',{ params });
				setTplRows(res.data);
			}
			setSubmitted(true);
		} catch {
			setError("Failed to load data. Please try again.");
		} finally {
			setLoading(false);
		}
	}, [reportType, selIns, selModel]);

	const hasResults = submitted && (premiRows.length > 0 || tplRows.length > 0);
	const noResults = submitted && premiRows.length === 0 && tplRows.length === 0;

	return (
		<div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 p-4 md:p-6">
			<div className="max-w-6xl mx-auto space-y-6">

				<div className="bg-white rounded-2xl shadow-lg p-6 print:hidden">
					<h1 className="text-2xl md:text-3xl font-bold text-slate-800 mb-6">
						List of Insurance Premi
					</h1>

					<div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">

						<div>
							<label className="block text-sm font-medium text-slate-700 mb-1">
								Insurance Company
							</label>
							<select
								value={selIns}
								onChange={e => setSelIns(e.target.value)}
								className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
							>
								<option value="00">Select</option>
								{companies.map(c => (
									<option key={c.ins_cd} value={c.ins_cd}>{c.ins_co}</option>
								))}
							</select>
						</div>

						<div>
							<label className="block text-sm font-medium text-slate-700 mb-1">
								Model Name
							</label>
							<select
								value={selModel}
								onChange={e => setSelModel(e.target.value)}
								className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
							>
								<option value="00">Select</option>
								{models.map(m => (
									<option key={m.model} value={m.model}>{m.model_nm}</option>
								))}
							</select>
						</div>
					</div>

					<div className="mb-6">
						<p className="block text-sm font-medium text-slate-700 mb-2">Report</p>
						<div className="flex items-center gap-6">
							<label className="flex items-center gap-2 cursor-pointer text-sm text-slate-700">
								<input
									type="radio"
									name="report_type"
									value="premi"
									checked={reportType === "premi"}
									onChange={() => setReportType("premi")}
									className="accent-blue-600 w-4 h-4"
								/>
								Premi
							</label>
							<label className="flex items-center gap-2 cursor-pointer text-sm text-slate-700">
								<input
									type="radio"
									name="report_type"
									value="tpl"
									checked={reportType === "tpl"}
									onChange={() => setReportType("tpl")}
									className="accent-blue-600 w-4 h-4"
								/>
								TPL
							</label>
						</div>
					</div>

					<div className="flex items-center gap-3">
						<button
							onClick={handlePreview}
							disabled={loading}
							className="px-5 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white rounded-lg text-sm font-medium transition-colors"
						>
							{loading ? (
								<span className="flex items-center gap-2">
									<svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
										<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
										<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
									</svg>
									Loading…
								</span>
							) : "Preview"}
						</button>

						{hasResults && (
							<button
								onClick={() => window.print()}
								className="px-5 py-2 bg-slate-600 hover:bg-slate-700 text-white rounded-lg text-sm font-medium transition-colors"
							>
								🖨 Print
							</button>
						)}
					</div>

					{error && (
						<div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
							{error}
						</div>
					)}
				</div>

				{submitted && (
					<div className="bg-white rounded-2xl shadow-lg p-6">

						<h2 className="text-xl font-bold text-slate-800 text-center mb-6 tracking-widest uppercase">
							List of Insurance
						</h2>

						{noResults && (
							<div className="flex flex-col items-center justify-center py-14 text-slate-400">
								<svg className="w-16 h-16 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
										d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
								</svg>
								<p className="text-lg">No records found</p>
							</div>
						)}

						{reportType === "premi" && premiRows.length > 0 && (
							<div className="overflow-x-auto rounded-xl border border-slate-200">
								<table className="w-full text-sm">
									<thead>
										<tr>
											<Th className="text-center w-12">No</Th>
											<Th>Insurance Company</Th>
											<Th>Model</Th>
											<Th>Coverage</Th>
											<Th className="text-right">Premi</Th>
											<Th>Insurance Area</Th>
										</tr>
									</thead>
									<tbody>
										{premiRows.map((row, idx) => (
											<tr
												key={row.id ?? idx}
												className={idx % 2 === 0 ? "bg-white" : "bg-slate-50"}
											>
												<Td className="text-center">{idx + 1}</Td>
												<Td>{row.ins_co}</Td>
												<Td>{row.model_nm}</Td>
												<Td>{row.coverage}</Td>
												<Td className="text-right">{row.premi}</Td>
												<Td>{row.insurance_area}</Td>
											</tr>
										))}
									</tbody>
								</table>
							</div>
						)}

						{reportType === "tpl" && tplRows.length > 0 && (
							<div className="overflow-x-auto rounded-xl border border-slate-200">
								<table className="w-full text-sm">
									<thead>
										<tr>
											<Th className="text-center w-12">No</Th>
											<Th>Insurance Company</Th>
											<Th>Model</Th>
											<Th className="text-right">TPL AMT</Th>
											<Th className="text-right">TPL FEE</Th>
											<Th className="text-right">TPL FEE2</Th>
										</tr>
									</thead>
									<tbody>
										{tplRows.map((row, idx) => (
											<tr
												key={`${row.ins_co}-${row.model_nm}-${idx}`}
												className={idx % 2 === 0 ? "bg-white" : "bg-slate-50"}
											>
												<Td className="text-center">{idx + 1}</Td>
												<Td>{row.ins_co}</Td>
												<Td>{row.model_nm}</Td>
												<Td className="text-right font-mono">{row.tpl_amt}</Td>
												<Td className="text-right font-mono">{row.tpl_fee}</Td>
												<Td className="text-right font-mono">{row.tpl_fee2}</Td>
											</tr>
										))}
									</tbody>
								</table>
							</div>
						)}
					</div>
				)}
			</div>
		</div>
	);
};

export default ListOfInsuranceReportPage;