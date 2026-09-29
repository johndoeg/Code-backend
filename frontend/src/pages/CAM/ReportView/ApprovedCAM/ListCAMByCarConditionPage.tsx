import React, { useEffect, useState } from 'react';
import api from '../../../../api/axiosInstance';
import AsOfDatePicker from '../../../../components/AsOfDatePickerComponent';

interface BranchOption {
	branch_cd: string;
	branch_name: string;
}

interface DetailRow {
	approval_date: string;
	new_nontruck_unit: number;
	new_nontruck_amt: number;
	new_truck_unit: number;
	new_truck_amt: number;
	used_nontruck_unit: number;
	used_nontruck_amt: number;
	used_truck_unit: number;
	used_truck_amt: number;
}

interface Bucket {
	units: number;
	pct_units: number;
	net_finance: number;
	pct_net_finance: number;
}

interface Summary {
	by_condition: { new: Bucket; used: Bucket; total: Bucket };
	by_type: { non_truck: Bucket; truck: Bucket; total: Bucket };
	totals_row: {
		new_nontruck_unit: number; new_nontruck_amt: number;
		new_truck_unit: number; new_truck_amt: number;
		used_nontruck_unit: number; used_nontruck_amt: number;
		used_truck_unit: number; used_truck_amt: number;
	};
}

interface ListResponse {
	data: DetailRow[];
	summary: Summary;
	has_data: boolean;
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

const ListCAMByCarConditionPage: React.FC = () => {
	const [branches, setBranches] = useState<BranchOption[]>([]);
	const [branchDisabled, setBranchDisabled] = useState(false);

	const [startDate, setStartDate] = useState<Date | null>(null);
	const [endDate, setEndDate] = useState<Date | null>(null);
	const [branchCd, setBranchCd] = useState('');

	const [rows, setRows] = useState<DetailRow[]>([]);
	const [summary, setSummary] = useState<Summary | null>(null);
	const [hasData, setHasData] = useState(false);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [hasSearched, setHasSearched] = useState(false);
	const [exporting, setExporting] = useState(false);

	useEffect(() => {
		(async () => {
			try {
				const [branchRes, ctxRes] = await Promise.all([
					api.get<BranchOption[]>('/CAM/Approved/api/cam-by-car-condition/branches'),
					api.get('/CAM/Approved/api/cam-by-car-condition/context'),
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

	const buildParams = () => ({
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
			const response = await api.get<ListResponse>('/CAM/Approved/api/cam-by-car-condition/list', {
				params: buildParams(),
			});
			setRows(response.data.data);
			setSummary(response.data.summary);
			setHasData(response.data.has_data);
		} catch (err) {
			console.error('CAM by Car Condition list error:', err);
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
		const params = new URLSearchParams(buildParams());
		const baseURL = (api.defaults.baseURL || '').replace(/\/$/, '');
		window.open(`${baseURL}/CAM/Approved/api/cam-by-car-condition/print?${params.toString()}`, '_blank');
	};

	const handleExport = async () => {
		if (!startDate || !endDate || !branchCd) {
			alert('Please fill in all required fields');
			return;
		}
		setExporting(true);
		try {
			const response = await api.get('/CAM/Approved/api/cam-by-car-condition/export', {
				params: buildParams(),
				responseType: 'blob',
			});
			const blob = new Blob([response.data], {
				type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
			});
			const url = window.URL.createObjectURL(blob);
			const link = document.createElement('a');
			link.href = url;
			link.download = 'ApprovedCamByCarCond.xlsx';
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

	const renderBreakdownTable = (title: string, rowsSpec: [string, Bucket][]) => (
		<div className="max-w-md">
			<table className="w-full text-sm border-collapse">
				<thead>
					<tr className="bg-gray-100 text-gray-700">
						<th className="border border-gray-300 px-2 py-1"></th>
						<th className="border border-gray-300 px-2 py-1">Unit</th>
						<th className="border border-gray-300 px-2 py-1">%</th>
						<th className="border border-gray-300 px-2 py-1">Net Finance</th>
						<th className="border border-gray-300 px-2 py-1">%</th>
					</tr>
				</thead>
				<tbody>
					{rowsSpec.map(([label, bucket], idx) => (
						<tr key={idx} className={label === 'Total' ? 'font-semibold bg-gray-50' : ''}>
							<td className="border border-gray-300 px-2 py-1">{label}</td>
							<td className="border border-gray-300 px-2 py-1 text-right">{fmt(bucket.units)}</td>
							<td className="border border-gray-300 px-2 py-1 text-right">{bucket.pct_units}%</td>
							<td className="border border-gray-300 px-2 py-1 text-right">{fmt(bucket.net_finance)}</td>
							<td className="border border-gray-300 px-2 py-1 text-right">{bucket.pct_net_finance}%</td>
						</tr>
					))}
				</tbody>
			</table>
		</div>
	);

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-6xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6">
					<div className="mb-6">
						<h1 className="text-xl md:text-2xl font-bold text-gray-800">List Approved CAM by Car's Condition</h1>
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

					<div className="overflow-x-auto rounded-lg border border-gray-200 mb-6">
						<table className="w-full text-sm border-collapse">
							<thead>
								<tr className="bg-gray-100 text-gray-700">
									<th className="border border-gray-300 px-2 py-2" rowSpan={3}>Approval Date</th>
									<th className="border border-gray-300 px-2 py-2" colSpan={4}>NEW</th>
									<th className="border border-gray-300 px-2 py-2" colSpan={4}>USED</th>
								</tr>
								<tr className="bg-gray-100 text-gray-700">
									<th className="border border-gray-300 px-2 py-2" colSpan={2}>Non Truck</th>
									<th className="border border-gray-300 px-2 py-2" colSpan={2}>Truck</th>
									<th className="border border-gray-300 px-2 py-2" colSpan={2}>Non Truck</th>
									<th className="border border-gray-300 px-2 py-2" colSpan={2}>Truck</th>
								</tr>
								<tr className="bg-gray-100 text-gray-700">
									<th className="border border-gray-300 px-2 py-2">Unit</th>
									<th className="border border-gray-300 px-2 py-2">Net Finance</th>
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
										<td colSpan={9} className="py-10 text-center">
											<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto" />
										</td>
									</tr>
								) : !hasSearched ? (
									<tr>
										<td colSpan={9} className="border border-gray-300 px-2 py-8 text-center text-gray-400">
											Choose a period and branch, then click Preview.
										</td>
									</tr>
								) : !hasData ? (
									<tr>
										<td colSpan={9} className="border border-gray-300 px-2 py-4 text-center text-red-600 font-bold">
											Data Not Found
										</td>
									</tr>
								) : (
									<>
										{rows.map((row, idx) => (
											<tr key={idx} className="odd:bg-gray-50">
												<td className="border border-gray-300 px-2 py-1">{row.approval_date}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.new_nontruck_unit)}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.new_nontruck_amt)}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.new_truck_unit)}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.new_truck_amt)}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.used_nontruck_unit)}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.used_nontruck_amt)}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.used_truck_unit)}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.used_truck_amt)}</td>
											</tr>
										))}
										{summary && (
											<tr className="bg-gray-100 font-semibold">
												<td className="border border-gray-300 px-2 py-1"></td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(summary.totals_row.new_nontruck_unit)}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(summary.totals_row.new_nontruck_amt)}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(summary.totals_row.new_truck_unit)}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(summary.totals_row.new_truck_amt)}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(summary.totals_row.used_nontruck_unit)}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(summary.totals_row.used_nontruck_amt)}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(summary.totals_row.used_truck_unit)}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(summary.totals_row.used_truck_amt)}</td>
											</tr>
										)}
									</>
								)}
							</tbody>
						</table>
					</div>

					{summary && hasSearched && hasData && (
						<div className="flex flex-col md:flex-row gap-8">
							{renderBreakdownTable('By Condition', [
								['New', summary.by_condition.new],
								['Used', summary.by_condition.used],
								['Total', summary.by_condition.total],
							])}
							{renderBreakdownTable('By Type', [
								['Non Truck', summary.by_type.non_truck],
								['Truck', summary.by_type.truck],
								['Total', summary.by_type.total],
							])}
						</div>
					)}
				</div>
			</div>
		</div>
	);
};

export default ListCAMByCarConditionPage;