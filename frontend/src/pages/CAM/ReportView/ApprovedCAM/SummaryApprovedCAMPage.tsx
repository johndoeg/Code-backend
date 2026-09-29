import React, { useEffect, useState } from 'react';
import api from '../../../../api/axiosInstance';
import AsOfDatePicker from '../../../../components/AsOfDatePickerComponent';

interface BranchOption {
	branch_cd: string;
	branch_name: string;
}

interface SummaryRow {
	type: 'detail' | 'subtotal' | 'grand_total';
	cmo_name?: string;
	approval_date?: string;
	unit_new: number;
	net_finance_new: number;
	unit_rev: number;
	net_finance_rev: number;
	total_unit: number;
	total_net_finance: number;
}

interface ListResponse {
	data: SummaryRow[];
	disabled: boolean;
	search_branch: string;
}

const toISO = (d: Date): string => {
	const year = d.getFullYear();
	const month = String(d.getMonth() + 1).padStart(2, '0');
	const day = String(d.getDate()).padStart(2, '0');
	return `${year}-${month}-${day}`;
};

const fmt = (n: number) => n.toLocaleString('id-ID', { maximumFractionDigits: 0 });

const SummaryApprovedCamPage: React.FC = () => {
	const [branches, setBranches] = useState<BranchOption[]>([]);
	const [branchDisabled, setBranchDisabled] = useState(false);

	const [startDate, setStartDate] = useState<Date | null>(null);
	const [endDate, setEndDate] = useState<Date | null>(null);
	const [branchCd, setBranchCd] = useState('');

	const [rows, setRows] = useState<SummaryRow[]>([]);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [hasSearched, setHasSearched] = useState(false);
	const [exporting, setExporting] = useState(false);

	useEffect(() => {
		(async () => {
			try {
				const [branchRes, ctxRes] = await Promise.all([
					api.get<BranchOption[]>('/CAM/Approved/api/summary-approved-cam/branches'),
					api.get('/CAM/Approved/api/summary-approved-cam/context'),
				]);
				setBranches(branchRes.data);
				setBranchDisabled(ctxRes.data.disabled);
				if (ctxRes.data.disabled) {
					setBranchCd(ctxRes.data.forced_branch_cd);
				}
			} catch (err) {
				console.error('Context load error:', err);
			}
		})();
	}, []);

	const buildQueryParams = () => ({
		start_date: startDate ? toISO(startDate) : '',
		end_date: endDate ? toISO(endDate) : '',
		branch_cd_search: branchCd,
	});

	const handlePreview = async () => {
		if (!startDate || !endDate || !branchCd) {
			alert('Please fill in all required fields');
			return;
		}
		setLoading(true);
		setError(null);
		setHasSearched(true);
		try {
			const response = await api.get<ListResponse>('/CAM/Approved/api/summary-approved-cam/list', {
				params: buildQueryParams(),
			});
			setRows(response.data.data);
		} catch (err) {
			console.error('Summary Approved CAM list error:', err);
			setError('Failed to load report. Please try again.');
		} finally {
			setLoading(false);
		}
	};

	const handlePrint = () => {
		if (!startDate || !endDate || !branchCd) {
			alert('Please fill in all required fields');
			return;
		}
		const params = new URLSearchParams(buildQueryParams());
		const baseURL = (api.defaults.baseURL || '').replace(/\/$/, '');
		window.open(
			`${baseURL}/CAM/Approved/api/summary-approved-cam/print?${params.toString()}`,
			'_blank'
		);
	};

	const handleExport = async () => {
		if (!startDate || !endDate || !branchCd) {
			alert('Please fill in all required fields');
			return;
		}
		setExporting(true);
		try {
			const response = await api.get('/CAM/Approved/api/summary-approved-cam/export', {
				params: buildQueryParams(),
				responseType: 'blob',
			});
			const blob = new Blob([response.data], {
				type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
			});
			const url = window.URL.createObjectURL(blob);
			const link = document.createElement('a');
			link.href = url;
			link.download = 'SummaryApprovedCam.xlsx';
			document.body.appendChild(link);
			link.click();
			document.body.removeChild(link);
			window.URL.revokeObjectURL(url);
		} catch (err) {
			console.error('Export error:', err);
			alert('Failed to export. Please try again.');
		} finally {
			setExporting(false);
		}
	};

	const grandTotal = rows.find((r) => r.type === 'grand_total');
	const dataNotFound = hasSearched && !loading && grandTotal && grandTotal.total_unit === 0;

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-6xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6">
					<div className="mb-6">
						<h1 className="text-xl md:text-2xl font-bold text-gray-800">Summary Approved CAM</h1>
					</div>

					<div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4 text-sm items-end">
						<div>
							<label className="text-gray-500 block mb-1">Start Approved Date</label>
							<AsOfDatePicker label="" value={startDate} onChange={setStartDate} required />
						</div>
						<div>
							<label className="text-gray-500 block mb-1">End Approved Date</label>
							<AsOfDatePicker label="" value={endDate} onChange={setEndDate} required />
						</div>
						<div>
							<label className="text-gray-500 block mb-1">Branch</label>
							<select
								value={branchCd}
								onChange={(e) => setBranchCd(e.target.value)}
								disabled={branchDisabled}
								className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none disabled:bg-gray-100"
							>
								<option value="">Select</option>
								{branches.map((b) => (
									<option key={b.branch_cd} value={b.branch_cd}>
										{b.branch_name}
									</option>
								))}
							</select>
						</div>
					</div>

					<div className="mb-6 flex gap-2">
						<button
							onClick={handlePreview}
							className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
						>
							Preview
						</button>
						<button
							onClick={handlePrint}
							className="bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
						>
							Print
						</button>
						<button
							onClick={handleExport}
							disabled={exporting}
							className="bg-green-600 hover:bg-green-700 disabled:bg-gray-300 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
						>
							{exporting ? 'Exporting…' : 'Export to Excel'}
						</button>
					</div>

					{error && (
						<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
							{error}
						</div>
					)}

					<div className="overflow-x-auto rounded-lg border border-gray-200">
						<table className="w-full text-sm border-collapse">
							<thead>
								<tr className="bg-gray-100 text-gray-700">
									<th className="border border-gray-300 px-2 py-2" rowSpan={2}>CMO</th>
									<th className="border border-gray-300 px-2 py-2" rowSpan={2}>Approval Date</th>
									<th className="border border-gray-300 px-2 py-2" colSpan={2}>New CAM</th>
									<th className="border border-gray-300 px-2 py-2" colSpan={2}>Revisi</th>
									<th className="border border-gray-300 px-2 py-2" colSpan={2}>Total</th>
								</tr>
								<tr className="bg-gray-100 text-gray-700">
									<th className="border border-gray-300 px-2 py-2">Unit</th>
									<th className="border border-gray-300 px-2 py-2">Net Finance</th>
									<th className="border border-gray-300 px-2 py-2">Unit</th>
									<th className="border border-gray-300 px-2 py-2">Net Finance</th>
									<th className="border border-gray-300 px-2 py-2">Unit</th>
									<th className="border border-gray-300 px-2 py-2">Net Finance</th>
								</tr>
							</thead>
							<tbody>
								{loading ? (
									<tr>
										<td colSpan={8} className="py-10 text-center">
											<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto" />
										</td>
									</tr>
								) : !hasSearched ? (
									<tr>
										<td colSpan={8} className="border border-gray-300 px-2 py-8 text-center text-gray-400">
											Fill in the fields above and click Preview.
										</td>
									</tr>
								) : dataNotFound ? (
									<tr>
										<td colSpan={8} className="border border-gray-300 px-2 py-4 text-center text-red-600 font-bold">
											Data Not Found
										</td>
									</tr>
								) : (
									rows.map((row, idx) =>
										row.type === 'grand_total' ? (
											<tr key={idx} className="bg-gray-100 font-semibold">
												<td className="border border-gray-300 px-2 py-1" colSpan={2}>Grand Total</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.unit_new)}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.net_finance_new)}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.unit_rev)}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.net_finance_rev)}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.total_unit)}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.total_net_finance)}</td>
											</tr>
										) : row.type === 'subtotal' ? (
											<tr key={idx} className="font-semibold border-b-2 border-gray-800">
												<td className="border border-gray-300 px-2 py-1"></td>
												<td className="border border-gray-300 px-2 py-1 text-right">Total</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.unit_new)}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.net_finance_new)}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.unit_rev)}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.net_finance_rev)}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.total_unit)}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.total_net_finance)}</td>
											</tr>
										) : (
											<tr key={idx} className="odd:bg-gray-50">
												<td className="border border-gray-300 px-2 py-1">{row.cmo_name}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{row.approval_date}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.unit_new)}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.net_finance_new)}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.unit_rev)}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.net_finance_rev)}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.total_unit)}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.total_net_finance)}</td>
											</tr>
										)
									)
								)}
							</tbody>
						</table>
					</div>
				</div>
			</div>
		</div>
	);
};

export default SummaryApprovedCamPage;