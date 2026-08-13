import React, { useState } from 'react';
import api from '../../../../api/axiosInstance';

interface InsuranceRow {
	appl_no: string;
	year_no: number;
	ins_amt: number;
	rate_premi: number;
	prer_amt: number;
	prep_amt: number;
}

interface SearchResponse {
	status: 'ok' | 'approved' | 'not_found' | 'error';
	message?: string;
	customer_name?: string;
	ins_company?: string;
	rows?: InsuranceRow[];
}

const fmt = (n: number) => (n ?? 0).toLocaleString('en-US', { maximumFractionDigits: 2 });

const EditInsurancePage: React.FC = () => {
	const [camNo, setCamNo] = useState('');
	const [customerName, setCustomerName] = useState('');
	const [insCompany, setInsCompany] = useState('');
	const [rows, setRows] = useState<InsuranceRow[]>([]);
	const [searching, setSearching] = useState(false);
	const [saving, setSaving] = useState(false);
	const [calculated, setCalculated] = useState(false);
	const [loaded, setLoaded] = useState(false);

	const reset = () => {
		setCamNo('');
		setCustomerName('');
		setInsCompany('');
		setRows([]);
		setCalculated(false);
		setLoaded(false);
	};

	const handleSearch = async () => {
		if (!camNo.trim().length) {
			alert('Please type CAM No. first');
			return;
		}
		if (camNo.trim().length < 11) {
			return;
		}

		setSearching(true);
		try {
			const res = await api.get<SearchResponse>('/CAM/Edit/api/edit-insurance/search', {
				params: { appl_no: camNo.trim() },
			});
			const data = res.data;

			if (data.status === 'approved') {
				alert('CAM already final approved');
				reset();
				return;
			}
			if (data.status === 'error') {
				alert(data.message || 'Error in query execution while checking CAM status');
				reset();
				return;
			}
			if (data.status === 'not_found' || !data.rows || data.rows.length === 0) {
				alert('Data Not Found!');
				setRows([]);
				setLoaded(false);
				return;
			}

			setCustomerName(data.customer_name || '');
			setInsCompany(data.ins_company || '');
			setRows(data.rows);
			setCalculated(false);
			setLoaded(true);
		} catch (err) {
			console.error('Insurance search error:', err);
			alert('Error in query execution while checking CAM status');
		} finally {
			setSearching(false);
		}
	};

	const updateRow = (index: number, key: 'rate_premi' | 'prer_amt', value: number) => {
		setRows((prev) => prev.map((r, i) => (i === index ? { ...r, [key]: value } : r)));
	};

	const handleRateBlur = (index: number) => {
		setRows((prev) => prev.map((r, i) => {
			if (i !== index) return r;
			let rate = r.rate_premi;
			if (Number.isNaN(rate)) rate = 0;
			if (rate > 100) rate = 100;
			if (rate < 0) rate = 0;
			return { ...r, rate_premi: rate };
		}));
	};

	const handleCalculate = () => {
		setRows((prev) => prev.map((r) => ({
			...r,
			prep_amt: Math.round(0.75 * r.prer_amt),
		})));
		setCalculated(true);
	};

	const handleSave = async () => {
		setSaving(true);
		try {
			const res = await api.post('/CAM/Edit/api/edit-insurance/save', { rows });
			if (res.data.success) {
				alert(res.data.message || 'Data has been updated!');
				reset();
			} else {
				alert(res.data.message || 'Save failed.');
			}
		} catch (err) {
			console.error('Insurance save error:', err);
			alert('Save failed. Please try again.');
		} finally {
			setSaving(false);
		}
	};

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-6xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6">
					<h1 className="text-xl md:text-2xl font-bold text-gray-800 mb-6">Edit Insurance</h1>

					<table className="w-full mb-4">
						<tbody>
							<tr>
								<td className="py-1 text-sm text-gray-600 w-40">CAM No.</td>
								<td className="py-1">
									<div className="flex gap-2">
										<input
											type="text"
											value={camNo}
											onChange={(e) => setCamNo(e.target.value)}
											maxLength={15}
											className="px-3 py-2 border border-gray-300 rounded text-sm flex-1"
										/>
										<button
											onClick={handleSearch}
											disabled={searching}
											className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white px-4 py-2 rounded text-sm font-medium"
										>
											{searching ? 'Searching…' : 'Search'}
										</button>
									</div>
								</td>
							</tr>
							<tr>
								<td className="py-1 text-sm text-gray-600">Customer Name</td>
								<td className="py-1">
									<input
										type="text"
										value={customerName}
										readOnly
										className="w-full px-3 py-2 border border-gray-300 rounded text-sm bg-gray-100"
									/>
								</td>
							</tr>
							<tr>
								<td className="py-1 text-sm text-gray-600">Ins. Company</td>
								<td className="py-1">
									<input
										type="text"
										value={insCompany}
										readOnly
										className="w-full px-3 py-2 border border-gray-300 rounded text-sm bg-gray-100"
									/>
								</td>
							</tr>
						</tbody>
					</table>

					{loaded && (
						<>
							<div className="overflow-x-auto border border-gray-300 rounded mb-4">
								<table className="w-full text-sm border-collapse">
									<thead>
										<tr className="bg-gray-100 text-gray-700 text-left">
											<th className="border border-gray-300 px-2 py-2">Year</th>
											<th className="border border-gray-300 px-2 py-2">Insurance Amount</th>
											<th className="border border-gray-300 px-2 py-2">Insurance Rate (%)</th>
											<th className="border border-gray-300 px-2 py-2">Premium Receive</th>
											<th className="border border-gray-300 px-2 py-2">Premium Payment</th>
										</tr>
									</thead>
									<tbody>
										{rows.map((row, idx) => (
											<tr key={`${row.year_no}-${idx}`} className="odd:bg-gray-50">
												<td className="border border-gray-300 px-2 py-1 text-center">{row.year_no}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.ins_amt)}</td>
												<td className="border border-gray-300 px-1 py-1">
													<input
														type="number"
														min={0}
														max={100}
														step="0.01"
														value={row.rate_premi}
														onChange={(e) => updateRow(idx, 'rate_premi', Number(e.target.value))}
														onBlur={() => handleRateBlur(idx)}
														className="w-full px-2 py-1 border border-gray-300 rounded text-right text-sm"
													/>
												</td>
												<td className="border border-gray-300 px-1 py-1">
													<input
														type="number"
														min={0}
														step="0.01"
														value={row.prer_amt}
														onChange={(e) => updateRow(idx, 'prer_amt', Number(e.target.value))}
														className="w-full px-2 py-1 border border-gray-300 rounded text-right text-sm"
													/>
												</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.prep_amt)}</td>
											</tr>
										))}
									</tbody>
								</table>
							</div>

							<div className="flex justify-center gap-2">
								<button
									onClick={handleCalculate}
									className="bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
								>
									Calculate
								</button>
								<button
									onClick={handleSave}
									disabled={!calculated || saving}
									className="bg-green-600 hover:bg-green-700 disabled:bg-gray-300 disabled:text-gray-500 text-white px-4 py-2 rounded-lg text-sm font-medium"
								>
									{saving ? 'Saving…' : 'Save'}
								</button>
								<button
									onClick={reset}
									className="bg-gray-200 hover:bg-gray-300 px-4 py-2 rounded-lg text-sm font-medium"
								>
									Cancel
								</button>
							</div>
						</>
					)}
				</div>
			</div>
		</div>
	);
};

export default EditInsurancePage;