import React, { useState } from 'react';
import api from '../../../../../api/axiosInstance';
import AsOfDatePicker from '../../../../../components/AsOfDatePickerComponent';

interface SalesPerson {
	reg_no: string;
	type: string;
	name: string;
	address: string;
	npwp: string | null;
	npwp_number: string | null;
}

interface HistoryRow {
	no: number;
	customer_name: string;
	contract_no: string;
	disbursement_date: string | null;
	commission_date: string | null;
	gross_amount: number;
	tax_amount: number;
	net_payment: number;
	dpp_cumulative: number;
	pph21_cumulative: number;
}

interface HistoryTotals {
	gross_amount: number;
	tax_amount: number;
	net_payment: number;
}

const toISO = (d: Date): string => {
	const year = d.getFullYear();
	const month = String(d.getMonth() + 1).padStart(2, '0');
	const day = String(d.getDate()).padStart(2, '0');
	return `${year}-${month}-${day}`;
};

const formatMoney = (n: number) => n.toLocaleString('id-ID', { maximumFractionDigits: 0 });

const HistoryCommissionReportPage: React.FC = () => {
	const [asOf, setAsOf] = useState<Date>(new Date());
	const [selectedSales, setSelectedSales] = useState<SalesPerson | null>(null);

	const [sortCommissionDate, setSortCommissionDate] = useState(false);
	const [sortDisbursementDate, setSortDisbursementDate] = useState(false);

	const [history, setHistory] = useState<HistoryRow[]>([]);
	const [totals, setTotals] = useState<HistoryTotals | null>(null);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const [pickerOpen, setPickerOpen] = useState(false);
	const [pickerQuery, setPickerQuery] = useState('');
	const [pickerResults, setPickerResults] = useState<SalesPerson[]>([]);
	const [pickerLoading, setPickerLoading] = useState(false);

	const fetchHistory = async (regNo: string, sortByExecution: boolean, asOfDate: Date) => {
		setLoading(true);
		setError(null);
		try {
			const response = await api.get<{ data: HistoryRow[]; totals: HistoryTotals }>(
				'/CAM/Commission/api/commission-individual-history-report/history',
				{
					params: {
						as_of: toISO(asOfDate),
						reg_no: regNo,
						sort_by_execution: sortByExecution ? '1' : '0',
					},
				}
			);
			setHistory(response.data.data);
			setTotals(response.data.totals);
		} catch (err) {
			console.error('Commission history error:', err);
			setError('Failed to load history. Please try again.');
		} finally {
			setLoading(false);
		}
	};

	const handleDateChange = (d: Date | null) => {
		if (!d) return;
		setAsOf(d);
		if (selectedSales) {
			fetchHistory(selectedSales.reg_no, sortCommissionDate || sortDisbursementDate, d);
		}
	};

	const runPickerSearch = async (query: string = pickerQuery) => {
		setPickerLoading(true);
		try {
			const response = await api.get<SalesPerson[]>(
				'/CAM/Commission/api/commission-individual-history-report/sales',
				{ params: { as_of: toISO(asOf), search: query } }
			);
			setPickerResults(response.data);
		} catch (err) {
			console.error('Sales picker search error:', err);
		} finally {
			setPickerLoading(false);
		}
	};

	const openPicker = () => {
		setPickerQuery('');
		setPickerResults([]);
		setPickerOpen(true);
		runPickerSearch('');
	};

	const selectSales = (person: SalesPerson) => {
		setSelectedSales(person);
		setPickerOpen(false);
		fetchHistory(person.reg_no, sortCommissionDate || sortDisbursementDate, asOf);
	};

	const toggleSort = (which: 'commission' | 'disbursement', checked: boolean) => {
		const nextCommission = which === 'commission' ? checked : sortCommissionDate;
		const nextDisbursement = which === 'disbursement' ? checked : sortDisbursementDate;
		setSortCommissionDate(nextCommission);
		setSortDisbursementDate(nextDisbursement);
		if (selectedSales) {
			fetchHistory(selectedSales.reg_no, nextCommission || nextDisbursement, asOf);
		}
	};

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-6xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6 mb-6">
					<div className="mb-6 text-center">
						<h1 className="text-xl md:text-2xl font-bold text-gray-800">
							History of Commission/Incentive Payment Report — Individual
						</h1>
					</div>

					<div className="max-w-xs mx-auto mb-6">
						<AsOfDatePicker label="As Of" value={asOf} onChange={handleDateChange} required />
					</div>

					<div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6 text-sm">
						<div className="grid grid-cols-[140px_10px_1fr] gap-y-2 items-start">
							<span className="text-gray-500">Registration Number</span>
							<span>:</span>
							<span className="font-medium text-gray-800">{selectedSales?.reg_no ?? '-'}</span>

							<span className="text-gray-500">Type</span>
							<span>:</span>
							<span className="font-medium text-gray-800">{selectedSales?.type ?? '-'}</span>

							<span className="text-gray-500">
								<button
									onClick={openPicker}
									className="text-blue-600 hover:text-blue-800 hover:underline transition-colors text-left"
								>
									Commission Receiver Name
								</button>
							</span>
							<span>:</span>
							<span className="font-medium text-gray-800">{selectedSales?.name ?? '-'}</span>

							<span className="text-gray-500">Commission Receiver Address</span>
							<span>:</span>
							<span className="font-medium text-gray-800">{selectedSales?.address ?? '-'}</span>
						</div>

						<div>
							<div className="grid grid-cols-[140px_10px_1fr] gap-y-2 items-start mb-4">
								<span className="text-gray-500">NPWP</span>
								<span>:</span>
								<span className="font-medium text-gray-800">{selectedSales?.npwp ?? '-'}</span>

								<span className="text-gray-500">NPWP Number</span>
								<span>:</span>
								<span className="font-medium text-gray-800">{selectedSales?.npwp_number ?? '-'}</span>
							</div>

							<div>
								<span className="text-gray-500 block mb-1">Sort By</span>
								<label className="flex items-center gap-2 text-sm mb-1">
									<input
										type="checkbox"
										checked={sortCommissionDate}
										onChange={(e) => toggleSort('commission', e.target.checked)}
									/>
									Commission Date
								</label>
								<label className="flex items-center gap-2 text-sm">
									<input
										type="checkbox"
										checked={sortDisbursementDate}
										onChange={(e) => toggleSort('disbursement', e.target.checked)}
									/>
									Disbursement Date
								</label>
							</div>
						</div>
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
									<th className="border border-gray-300 px-2 py-2">No.</th>
									<th className="border border-gray-300 px-2 py-2">Customer Name</th>
									<th className="border border-gray-300 px-2 py-2">Contract Number</th>
									<th className="border border-gray-300 px-2 py-2">Disbursement Date</th>
									<th className="border border-gray-300 px-2 py-2">Commission Date</th>
									<th className="border border-gray-300 px-2 py-2">Commission Amount</th>
									<th className="border border-gray-300 px-2 py-2">PPh 21 with Hold</th>
									<th className="border border-gray-300 px-2 py-2">Net Payment</th>
									<th className="border border-gray-300 px-2 py-2">DPP Cumulative</th>
									<th className="border border-gray-300 px-2 py-2">PPh 21 Progressive Cumulative</th>
								</tr>
							</thead>
							<tbody>
								{loading ? (
									<tr>
										<td colSpan={10} className="py-10 text-center">
											<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto" />
										</td>
									</tr>
								) : !selectedSales ? (
									<tr>
										<td colSpan={10} className="border border-gray-300 px-2 py-8 text-center text-gray-400">
											Choose a Commission Receiver Name above to see payment history.
										</td>
									</tr>
								) : (
									<>
										{history.length === 0 ? (
											<tr>
												<td colSpan={10} className="border border-gray-300 px-2 py-4 text-center text-gray-400">
													No commission transactions found for this period.
												</td>
											</tr>
										) : (
											history.map((row) => (
												<tr key={row.no} className="odd:bg-gray-50">
													<td className="border border-gray-300 px-2 py-1 text-center">{row.no}</td>
													<td className="border border-gray-300 px-2 py-1">{row.customer_name}</td>
													<td className="border border-gray-300 px-2 py-1 text-center">{row.contract_no}</td>
													<td className="border border-gray-300 px-2 py-1 text-center">{row.disbursement_date}</td>
													<td className="border border-gray-300 px-2 py-1 text-center">{row.commission_date}</td>
													<td className="border border-gray-300 px-2 py-1 text-right">{formatMoney(row.gross_amount)}</td>
													<td className="border border-gray-300 px-2 py-1 text-right">{formatMoney(row.tax_amount)}</td>
													<td className="border border-gray-300 px-2 py-1 text-right">{formatMoney(row.net_payment)}</td>
													<td className="border border-gray-300 px-2 py-1 text-right">{formatMoney(row.dpp_cumulative)}</td>
													<td className="border border-gray-300 px-2 py-1 text-right">{formatMoney(row.pph21_cumulative)}</td>
												</tr>
											))
										)}
										{totals && (
											<tr className="bg-gray-100 font-semibold">
												<td colSpan={5} className="border border-gray-300 px-2 py-1 text-center">Total</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{formatMoney(totals.gross_amount)}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{formatMoney(totals.tax_amount)}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{formatMoney(totals.net_payment)}</td>
												<td className="border border-gray-300 px-2 py-1" colSpan={2}></td>
											</tr>
										)}
									</>
								)}
							</tbody>
						</table>
					</div>
				</div>
			</div>

			{pickerOpen && (
				<div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
					<div className="bg-white rounded-2xl shadow-xl w-full max-w-4xl max-h-[80vh] overflow-hidden flex flex-col">
						<div className="flex justify-between items-center p-4 border-b">
							<h3 className="font-bold text-gray-800">List Commission Receiver</h3>
							<button onClick={() => setPickerOpen(false)} className="text-gray-400 hover:text-gray-600 text-2xl leading-none transition-colors">
								×
							</button>
						</div>
						<div className="p-4 border-b flex gap-2">
							<input
								type="text"
								value={pickerQuery}
								onChange={(e) => setPickerQuery(e.target.value)}
								onKeyDown={(e) => e.key === 'Enter' && runPickerSearch()}
								placeholder="Search by name"
								className="flex-1 px-3 py-2 rounded-lg border border-gray-300 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
							/>
							<button
								onClick={() => runPickerSearch()}
								className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
							>
								Search
							</button>
						</div>
						<div className="overflow-y-auto flex-grow">
							{pickerLoading ? (
								<div className="flex justify-center py-10">
									<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
								</div>
							) : (
								<table className="w-full text-sm">
									<thead className="bg-gray-50 sticky top-0">
										<tr>
											<th className="py-2 px-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
											<th className="py-2 px-3 text-left text-xs font-medium text-gray-500 uppercase">Reg. Number</th>
											<th className="py-2 px-3 text-left text-xs font-medium text-gray-500 uppercase">Address</th>
											<th className="py-2 px-3 text-left text-xs font-medium text-gray-500 uppercase">NPWP Number</th>
										</tr>
									</thead>
									<tbody className="divide-y divide-gray-100">
										{pickerResults.map((p) => (
											<tr key={p.reg_no} className="hover:bg-gray-50 cursor-pointer transition-colors" onClick={() => selectSales(p)}>
												<td className="py-2 px-3 text-blue-600 font-medium">{p.name}</td>
												<td className="py-2 px-3">{p.reg_no}</td>
												<td className="py-2 px-3 text-gray-500">{p.address}</td>
												<td className="py-2 px-3 text-gray-500">{p.npwp_number}</td>
											</tr>
										))}
										{pickerResults.length === 0 && (
											<tr><td colSpan={4} className="py-8 text-center text-gray-400 text-sm">Search for a commission receiver above.</td></tr>
										)}
									</tbody>
								</table>
							)}
						</div>
					</div>
				</div>
			)}
		</div>
	);
};

export default HistoryCommissionReportPage;