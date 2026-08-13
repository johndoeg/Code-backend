import React, { useState } from 'react';
import api from '../../../../../api/axiosInstance';
import AsOfDatePicker from '../../../../../components/AsOfDatePickerComponent';

interface Party {
	reg_no: string;
	type: string;
	name: string;
	address: string;
	dealer_type: string;
	dealer_status: string;
	npwp: string;
	skb: string;
	ppn: string;
}

interface HistoryRow {
	no: number;
	customer_name: string;
	contract_no: string;
	disbursement_date: string | null;
	commission_date: string | null;
	gross_amount: number;
	ppn_amount: number;
	tax_amount: number;
	net_payment: number;
	commission_cam: number;
}

interface HistoryTotals {
	gross_amount: number;
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
	const [selectedParty, setSelectedParty] = useState<Party | null>(null);

	const [sortCommissionDate, setSortCommissionDate] = useState(false);
	const [sortDisbursementDate, setSortDisbursementDate] = useState(false);

	const [history, setHistory] = useState<HistoryRow[]>([]);
	const [totals, setTotals] = useState<HistoryTotals | null>(null);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const [pickerOpen, setPickerOpen] = useState(false);
	const [pickerQuery, setPickerQuery] = useState('');
	const [pickerResults, setPickerResults] = useState<Party[]>([]);
	const [pickerLoading, setPickerLoading] = useState(false);

	const isDealer = selectedParty?.type === 'DEALER';

	const fetchHistory = async (party: Party, sortByExecution: boolean, asOfDate: Date) => {
		setLoading(true);
		setError(null);
		try {
			const response = await api.get<{ data: HistoryRow[]; totals: HistoryTotals }>(
				'/CAM/Commission/api/commission-company-report/history',
				{
					params: {
						as_of: toISO(asOfDate),
						reg_no: party.reg_no,
						type: party.type,
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
		if (selectedParty) {
			fetchHistory(selectedParty, sortCommissionDate || sortDisbursementDate, d);
		}
	};

	const runPickerSearch = async (query: string = pickerQuery) => {
		setPickerLoading(true);
		try {
			const response = await api.get<Party[]>('/CAM/Commission/api/commission-company-report/parties', {
				params: { as_of: toISO(asOf), search: query },
			});
			setPickerResults(response.data);
		} catch (err) {
			console.error('Party picker search error:', err);
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

	const selectParty = (party: Party) => {
		setSelectedParty(party);
		setPickerOpen(false);
		fetchHistory(party, sortCommissionDate || sortDisbursementDate, asOf);
	};

	const toggleSort = (which: 'commission' | 'disbursement', checked: boolean) => {
		const nextCommission = which === 'commission' ? checked : sortCommissionDate;
		const nextDisbursement = which === 'disbursement' ? checked : sortDisbursementDate;
		setSortCommissionDate(nextCommission);
		setSortDisbursementDate(nextDisbursement);
		if (selectedParty) {
			fetchHistory(selectedParty, nextCommission || nextDisbursement, asOf);
		}
	};

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-6xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6 mb-6">
					<div className="mb-6 text-center">
						<h1 className="text-xl md:text-2xl font-bold text-gray-800">
							History of Commission/Incentive Payment Report — Company
						</h1>
					</div>

					<div className="max-w-xs mx-auto mb-6">
						<AsOfDatePicker label="As Of" value={asOf} onChange={handleDateChange} required />
					</div>

					<div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6 text-sm">
						<div className="grid grid-cols-[110px_10px_1fr] gap-y-2 items-start">
							<span className="text-gray-500">Registration Number</span>
							<span>:</span>
							<span className="font-medium text-gray-800">{selectedParty?.reg_no ?? '-'}</span>

							<span className="text-gray-500">Type</span>
							<span>:</span>
							<span className="font-medium text-gray-800">{selectedParty?.type ?? '-'}</span>

							<span className="text-gray-500">
								<button
									onClick={openPicker}
									className="text-blue-600 hover:text-blue-800 hover:underline transition-colors text-left"
								>
									Commission Receiver Name
								</button>
							</span>
							<span>:</span>
							<span className="font-medium text-gray-800">{selectedParty?.name ?? '-'}</span>
						</div>

						<div className="grid grid-cols-[110px_10px_1fr] gap-y-2 items-start">
							{selectedParty && !isDealer ? (
								<>
									<span className="text-gray-500">NPWP No.</span>
									<span>:</span>
									<span className="font-medium text-gray-800">{selectedParty.npwp || '-'}</span>
								</>
							) : (
								<>
									<span className="text-gray-500">Dealer Type</span>
									<span>:</span>
									<span className="font-medium text-gray-800">{selectedParty?.dealer_type || '-'}</span>

									<span className="text-gray-500">Dealer Status</span>
									<span>:</span>
									<span className="font-medium text-gray-800">{selectedParty?.dealer_status || '-'}</span>

									<span className="text-gray-500">NPWP No.</span>
									<span>:</span>
									<span className="font-medium text-gray-800">{selectedParty?.npwp || '-'}</span>
								</>
							)}

							<span className="text-gray-500 self-start pt-0.5">Commission Receiver Address</span>
							<span className="self-start pt-0.5">:</span>
							<span className="font-medium text-gray-800">{selectedParty?.address ?? '-'}</span>
						</div>

						<div>
							<div className="grid grid-cols-[80px_10px_1fr] gap-y-2 items-start mb-4">
								<span className="text-gray-500">SKB/PPN</span>
								<span>:</span>
								<span className="font-medium text-gray-800">
									{selectedParty ? `${selectedParty.skb} / ${selectedParty.ppn}` : '-'}
								</span>
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
									<th className="border border-gray-300 px-2 py-2">PPN (11%)</th>
									<th className="border border-gray-300 px-2 py-2">PPh 23 (2%)</th>
									<th className="border border-gray-300 px-2 py-2">Net Payment</th>
									<th className="border border-gray-300 px-2 py-2">Commission CAM</th>
								</tr>
							</thead>
							<tbody>
								{loading ? (
									<tr>
										<td colSpan={10} className="py-10 text-center">
											<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto" />
										</td>
									</tr>
								) : !selectedParty ? (
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
													<td className="border border-gray-300 px-2 py-1 text-right">{formatMoney(row.ppn_amount)}</td>
													<td className="border border-gray-300 px-2 py-1 text-right">{formatMoney(row.tax_amount)}</td>
													<td className="border border-gray-300 px-2 py-1 text-right">{formatMoney(row.net_payment)}</td>
													<td className="border border-gray-300 px-2 py-1 text-right">{formatMoney(row.commission_cam)}</td>
												</tr>
											))
										)}
										{totals && (
											<tr className="bg-gray-100 font-semibold">
												<td colSpan={5} className="border border-gray-300 px-2 py-1 text-center">Total</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{formatMoney(totals.gross_amount)}</td>
												<td className="border border-gray-300 px-2 py-1" colSpan={2}></td>
												<td className="border border-gray-300 px-2 py-1 text-right">{formatMoney(totals.net_payment)}</td>
												<td className="border border-gray-300 px-2 py-1"></td>
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
					<div className="bg-white rounded-2xl shadow-xl w-full max-w-5xl max-h-[80vh] overflow-hidden flex flex-col">
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
											<th className="py-2 px-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
											<th className="py-2 px-3 text-left text-xs font-medium text-gray-500 uppercase">Address</th>
											<th className="py-2 px-3 text-left text-xs font-medium text-gray-500 uppercase">Dealer Type</th>
											<th className="py-2 px-3 text-left text-xs font-medium text-gray-500 uppercase">Dealer Status</th>
											<th className="py-2 px-3 text-left text-xs font-medium text-gray-500 uppercase">NPWP</th>
											<th className="py-2 px-3 text-left text-xs font-medium text-gray-500 uppercase">SKB/PPN</th>
										</tr>
									</thead>
									<tbody className="divide-y divide-gray-100">
										{pickerResults.map((p) => (
											<tr key={`${p.reg_no}-${p.type}`} className="hover:bg-gray-50 cursor-pointer transition-colors" onClick={() => selectParty(p)}>
												<td className="py-2 px-3 text-blue-600 font-medium">{p.name}</td>
												<td className="py-2 px-3">{p.reg_no}</td>
												<td className="py-2 px-3">{p.type}</td>
												<td className="py-2 px-3 text-gray-500">{p.address}</td>
												<td className="py-2 px-3 text-gray-500">{p.dealer_type || '-'}</td>
												<td className="py-2 px-3 text-gray-500">{p.dealer_status || '-'}</td>
												<td className="py-2 px-3 text-gray-500">{p.npwp || '-'}</td>
												<td className="py-2 px-3 text-gray-500">{p.skb} / {p.ppn}</td>
											</tr>
										))}
										{pickerResults.length === 0 && (
											<tr><td colSpan={8} className="py-8 text-center text-gray-400 text-sm">Search for a commission receiver above.</td></tr>
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