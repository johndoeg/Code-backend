import React, { useState, useEffect } from 'react';
import api from '../../../../api/axiosInstance';

type SearchMode = '' | 'dealer' | 'cmo';

interface Branch {
	branch_cd: string;
	branch_name: string;
}

interface CmoOption {
	employee_id: string;
	full_name: string;
}

interface Dealer {
	supp: string;
	name: string;
	nickname: string;
	address: string;
	phone: string;
	contact: string;
}

interface MonthlyRow {
	month: number;
	month_name: string;
	total_income: number;
	incentive_3rd_party: number;
	incentive_excess: number;
	paid_incentive: number;
	monthly_fee_pct: number | null;
	ytd_fee_pct: number | null;
}

const currentYear = new Date().getFullYear();
const YEAR_OPTIONS = Array.from({ length: 21 }, (_, i) => currentYear + 10 - i);

const formatMoney = (n: number) => n.toLocaleString('id-ID', { maximumFractionDigits: 0 });
const formatPct = (n: number | null) => (n === null ? '-' : `${n.toFixed(2)}%`);

const DetailIncentive3rdPartyReportPage: React.FC = () => {
	const [year, setYear] = useState(currentYear);
	const [branches, setBranches] = useState<Branch[]>([]);
	const [branchCd, setBranchCd] = useState('');

	const [searchMode, setSearchMode] = useState<SearchMode>('');
	const [selectedDealer, setSelectedDealer] = useState<Dealer | null>(null);
	const [cmoOptions, setCmoOptions] = useState<CmoOption[]>([]);
	const [selectedCmo, setSelectedCmo] = useState('');

	const [dealerPickerOpen, setDealerPickerOpen] = useState(false);
	const [dealerQuery, setDealerQuery] = useState('');
	const [dealerResults, setDealerResults] = useState<Dealer[]>([]);
	const [dealerLoading, setDealerLoading] = useState(false);

	const [results, setResults] = useState<MonthlyRow[]>([]);
	const [hasSearched, setHasSearched] = useState(false);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		api.get<Branch[]>('/CAM/Incentive/api/detail-incentive-3rd-party-report/branches')
			.then((res) => setBranches(res.data))
			.catch((err) => console.error('Branch list error:', err));
	}, []);

	useEffect(() => {
		if (searchMode !== 'cmo') return;
		api.get<CmoOption[]>('/CAM/Incentive/api/detail-incentive-3rd-party-report/cmo-options', {
			params: { branch_cd: branchCd },
		})
			.then((res) => setCmoOptions(res.data))
			.catch((err) => console.error('CMO options error:', err));
	}, [searchMode, branchCd]);

	const handleBranchChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
		setBranchCd(e.target.value);
		setSelectedCmo('');
	};

	const handleSearchModeChange = (mode: SearchMode) => {
		setSearchMode(mode);
		if (mode !== 'dealer') setSelectedDealer(null);
		if (mode !== 'cmo') setSelectedCmo('');
	};

	const openDealerPicker = () => {
		setDealerQuery('');
		setDealerResults([]);
		setDealerPickerOpen(true);
	};

	const runDealerSearch = async () => {
		setDealerLoading(true);
		try {
			const response = await api.get<Dealer[]>('/CAM/Incentive/api/detail-incentive-3rd-party-report/dealers', {
				params: { branch_cd: branchCd, search: dealerQuery },
			});
			setDealerResults(response.data);
		} catch (err) {
			console.error('Dealer search error:', err);
		} finally {
			setDealerLoading(false);
		}
	};

	const selectDealer = (dealer: Dealer) => {
		setSelectedDealer(dealer);
		setDealerPickerOpen(false);
	};

	const handleSearch = async () => {
		setLoading(true);
		setError(null);
		try {
			const response = await api.get<{ data: MonthlyRow[]; year: number }>(
				'/CAM/Incentive/api/detail-incentive-3rd-party-report/monthly',
				{
					params: {
						year,
						branch_cd: branchCd,
						supplier: searchMode === 'dealer' ? selectedDealer?.supp ?? '' : '',
						cmo: searchMode === 'cmo' ? selectedCmo : '',
					},
				}
			);
			setResults(response.data.data);
			setHasSearched(true);
		} catch (err) {
			console.error('Monthly report error:', err);
			setError('Failed to load report. Please try again.');
		} finally {
			setLoading(false);
		}
	};

	const handlePrint = () => {
		if (results.length === 0) {
			alert('Please search first.');
			return;
		}
		window.print();
	};

	const branchName = branches.find((b) => b.branch_cd === branchCd)?.branch_name ?? '';
	const cmoName = cmoOptions.find((c) => c.employee_id === selectedCmo)?.full_name ?? '';

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<style>{`
				@page {
					size: landscape;
					margin: 10mm;
				}
				@media print {
					body * { visibility: hidden; }
					#incentive-print-area, #incentive-print-area * { visibility: visible; }
					#incentive-print-area {
						position: absolute;
						inset: 0;
						width: 100%;
						margin: 0;
						padding: 0;
						box-shadow: none;
						border-radius: 0;
					}
					#incentive-print-area .overflow-x-auto {
						overflow: visible !important;
					}
					#incentive-print-area table {
						width: 100% !important;
					}
					#incentive-print-area th,
					#incentive-print-area td {
						white-space: normal !important;
					}
				}
			`}</style>

			<div className="max-w-5xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6 mb-6 print:hidden">
					<div className="mb-6 text-center">
						<h1 className="text-2xl md:text-3xl font-bold text-gray-800">
							Incentive to 3rd Party Monthly Report
						</h1>
					</div>

					<div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
						<div>
							<label className="block text-sm font-medium text-gray-700 mb-1">Year</label>
							<select
								value={year}
								onChange={(e) => setYear(Number(e.target.value))}
								className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
							>
								{YEAR_OPTIONS.map((y) => (
									<option key={y} value={y}>{y}</option>
								))}
							</select>
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700 mb-1">Branch</label>
							<select
								value={branchCd}
								onChange={handleBranchChange}
								className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
							>
								<option value="">All Branches</option>
								{branches.map((b) => (
									<option key={b.branch_cd} value={b.branch_cd}>{b.branch_name}</option>
								))}
							</select>
						</div>
					</div>

					<div className="mb-6 space-y-3">
						<label className="block text-sm font-medium text-gray-700">Search by</label>

						<div className="flex flex-wrap items-center gap-3">
							<label className="flex items-center gap-2 text-sm">
								<input
									type="radio"
									checked={searchMode === 'dealer'}
									onChange={() => handleSearchModeChange('dealer')}
								/>
								Dealer
							</label>
							<button
								onClick={openDealerPicker}
								disabled={searchMode !== 'dealer'}
								className="bg-gray-100 hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed
								           text-gray-700 px-3 py-1.5 rounded-lg text-sm transition-colors"
							>
								{selectedDealer ? selectedDealer.name : 'Choose dealer…'}
							</button>
						</div>

						<div className="flex flex-wrap items-center gap-3">
							<label className="flex items-center gap-2 text-sm">
								<input
									type="radio"
									checked={searchMode === 'cmo'}
									onChange={() => handleSearchModeChange('cmo')}
								/>
								CMO
							</label>
							<select
								value={selectedCmo}
								onChange={(e) => setSelectedCmo(e.target.value)}
								disabled={searchMode !== 'cmo'}
								className="px-3 py-2 rounded-lg border border-gray-300 text-sm min-w-[200px]
								           disabled:bg-gray-50 disabled:text-gray-400 focus:ring-2 focus:ring-blue-500 focus:outline-none"
							>
								<option value="">Select</option>
								{cmoOptions.map((c) => (
									<option key={c.employee_id} value={c.employee_id}>{c.full_name}</option>
								))}
							</select>
						</div>
					</div>

					{error && (
						<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
							{error}
						</div>
					)}

					<div className="flex flex-wrap gap-2">
						<button
							onClick={handleSearch}
							disabled={loading}
							className="bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white px-4 py-2 text-sm
							           rounded-lg font-medium transition-colors flex items-center gap-2"
						>
							{loading ? (
								<>
									<svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
										<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
										<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
									</svg>
									Searching…
								</>
							) : (
								'Search'
							)}
						</button>
						<button
							onClick={handlePrint}
							disabled={results.length === 0}
							className="bg-white border border-gray-300 text-gray-700 hover:bg-gray-50 disabled:opacity-60
							           px-4 py-2 text-sm rounded-lg font-medium transition-colors"
						>
							Print
						</button>
					</div>
				</div>

				{hasSearched && (
					<div id="incentive-print-area" className="bg-white rounded-2xl shadow-lg p-6">
						<h2 className="text-xl font-bold text-gray-800 text-center">
							Incentive to 3rd Party Monthly Report
						</h2>
						<p className="text-center text-sm text-gray-600 mb-4">Year {year}</p>

						<div className="text-sm text-gray-600 mb-4 space-y-1">
							<p><span className="font-medium text-gray-700">Branch:</span> {branchName || 'All Branches'}</p>
							{searchMode === 'dealer' && selectedDealer && (
								<p><span className="font-medium text-gray-700">Search by:</span> {selectedDealer.name}</p>
							)}
							{searchMode === 'cmo' && selectedCmo && (
								<p><span className="font-medium text-gray-700">Search by:</span> {cmoName}</p>
							)}
						</div>

						<div className="overflow-x-auto">
							<table className="w-full text-sm border-collapse">
								<thead>
									<tr className="bg-gray-100 text-gray-700">
										<th rowSpan={2} className="border border-gray-300 px-2 py-2">Month</th>
										<th rowSpan={2} className="border border-gray-300 px-2 py-2">Total Income (Include Subsidy)</th>
										<th rowSpan={2} className="border border-gray-300 px-2 py-2">Incentive to 3rd Party</th>
										<th rowSpan={2} className="border border-gray-300 px-2 py-2">Incentive Excess</th>
										<th rowSpan={2} className="border border-gray-300 px-2 py-2">Paid Incentive</th>
										<th colSpan={2} className="border border-gray-300 px-2 py-2">Incentive Fee (%)</th>
									</tr>
									<tr className="bg-gray-100 text-gray-700">
										<th className="border border-gray-300 px-2 py-2">Monthly</th>
										<th className="border border-gray-300 px-2 py-2">YTD</th>
									</tr>
								</thead>
								<tbody>
									{results.length === 0 ? (
										<tr>
											<td colSpan={7} className="border border-gray-300 px-2 py-4 text-center text-red-600 font-medium">
												Data Not Found
											</td>
										</tr>
									) : (
										results.map((row) => (
											<tr key={row.month} className="odd:bg-gray-50">
												<td className="border border-gray-300 px-2 py-1">{row.month_name}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{formatMoney(row.total_income)}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{formatMoney(row.incentive_3rd_party)}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{formatMoney(row.incentive_excess)}</td>
												<td className="border border-gray-300 px-2 py-1 text-right">{formatMoney(row.paid_incentive)}</td>
												<td className="border border-gray-300 px-2 py-1 text-center">{formatPct(row.monthly_fee_pct)}</td>
												<td className="border border-gray-300 px-2 py-1 text-center">{formatPct(row.ytd_fee_pct)}</td>
											</tr>
										))
									)}
								</tbody>
							</table>
						</div>
					</div>
				)}
			</div>

			{dealerPickerOpen && (
				<div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4 print:hidden">
					<div className="bg-white rounded-2xl shadow-xl w-full max-w-3xl max-h-[80vh] overflow-hidden flex flex-col">
						<div className="flex justify-between items-center p-4 border-b">
							<h3 className="font-bold text-gray-800">Dealer Information</h3>
							<button onClick={() => setDealerPickerOpen(false)} className="text-gray-400 hover:text-gray-600 text-2xl leading-none transition-colors">
								×
							</button>
						</div>
						<div className="p-4 border-b flex gap-2">
							<input
								type="text"
								value={dealerQuery}
								onChange={(e) => setDealerQuery(e.target.value)}
								onKeyDown={(e) => e.key === 'Enter' && runDealerSearch()}
								placeholder="Search by name"
								className="flex-1 px-3 py-2 rounded-lg border border-gray-300 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
							/>
							<button
								onClick={runDealerSearch}
								className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
							>
								Search
							</button>
						</div>
						<div className="overflow-y-auto flex-grow">
							{dealerLoading ? (
								<div className="flex justify-center py-10">
									<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
								</div>
							) : (
								<table className="w-full text-sm">
									<thead className="bg-gray-50 sticky top-0">
										<tr>
											<th className="py-2 px-3 text-left text-xs font-medium text-gray-500 uppercase">Code</th>
											<th className="py-2 px-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
											<th className="py-2 px-3 text-left text-xs font-medium text-gray-500 uppercase">Address</th>
											<th className="py-2 px-3 text-left text-xs font-medium text-gray-500 uppercase">Contact</th>
										</tr>
									</thead>
									<tbody className="divide-y divide-gray-100">
										{dealerResults.map((d) => (
											<tr key={d.supp} className="hover:bg-gray-50 cursor-pointer transition-colors" onClick={() => selectDealer(d)}>
												<td className="py-2 px-3 text-blue-600 font-medium">{d.supp}</td>
												<td className="py-2 px-3">{d.name}</td>
												<td className="py-2 px-3 text-gray-500">{d.address}</td>
												<td className="py-2 px-3 text-gray-500">{d.contact}</td>
											</tr>
										))}
										{dealerResults.length === 0 && (
											<tr><td colSpan={4} className="py-8 text-center text-gray-400 text-sm">Search for a dealer above.</td></tr>
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

export default DetailIncentive3rdPartyReportPage;