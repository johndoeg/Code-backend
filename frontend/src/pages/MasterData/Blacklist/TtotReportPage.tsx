import React, { useState } from 'react';
import api from '../../../api/axiosInstance';
import AsOfDatePicker from '../../../components/AsOfDatePickerComponent';

const toISO = (d: Date): string => d.toISOString().split('T')[0];

interface TtotRow {
	no: number;
	blacklist_id: string | number;
	name: string;
	alias: string;
	address: string;
}

interface TtotListResponse {
	data: TtotRow[];
	total: number;
	date_from: string;
	date_to: string;
}

const TtotReportPage: React.FC = () => {
	const [dateFrom, setDateFrom] = useState<Date>(new Date());
	const [dateTo, setDateTo] = useState<Date>(new Date());

	const [results, setResults] = useState<TtotRow[]>([]);
	const [hasSearched, setHasSearched] = useState(false);

	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const handleSearch = async () => {
		if (!dateFrom || !dateTo) {
			alert('Please fill both dates.');
			return;
		}
		if (dateFrom > dateTo) {
			alert('Date From cannot be later than Date To.');
			return;
		}

		setLoading(true);
		setError(null);

		try {
			const response = await api.get<TtotListResponse>('/MasterData/api/ttot-report/list', {
				params: { date_from: toISO(dateFrom), date_to: toISO(dateTo) },
			});
			setResults(response.data.data);
			setHasSearched(true);
		} catch (err) {
			console.error('TTOT search error:', err);
			setError('Failed to load data. Please try again.');
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

	const handleViewDetail = (row: TtotRow) => {
		console.log('View detail for blacklist_id', row.blacklist_id);
	};

	const handleDateFromChange = (d: Date | null) => {
		if (!d) return;
		setDateFrom(d);
		if (d > dateTo) setDateTo(d);
	};

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<style>{`
				@media print {
					body * { visibility: hidden; }
					#ttot-print-area, #ttot-print-area * { visibility: visible; }
					#ttot-print-area {
						position: absolute;
						inset: 0;
						width: 100%;
						margin: 0;
						padding: 0;
						box-shadow: none;
						border-radius: 0;
					}
					#ttot-print-area .overflow-x-auto { overflow: visible !important; }
					#ttot-print-area table { width: 100% !important; }
					#ttot-print-area th,
					#ttot-print-area td {
						white-space: normal !important;
						word-break: break-word;
						overflow-wrap: break-word;
					}
				}
			`}</style>

			<div className="max-w-7xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6 mb-6 print:hidden">
					<div className="mb-6">
						<h1 className="text-2xl md:text-3xl font-bold text-gray-800">
							List Pelaporan Terduga Teroris dan Organisasi Teroris
						</h1>
					</div>

					<div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
						<AsOfDatePicker
							label="Periode Dari"
							value={dateFrom}
							onChange={handleDateFromChange}
							maxDate={dateTo}
							required
						/>
						<AsOfDatePicker
							label="Periode Sampai"
							value={dateTo}
							onChange={(d) => { if (d) setDateTo(d); }}
							minDate={dateFrom}
							required
						/>
					</div>

					{error && (
						<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
							{error}
						</div>
					)}

					<div className="flex flex-wrap gap-2">
						<button
							onClick={handleSearch}
							disabled={loading}
							className="bg-gradient-to-r from-blue-600 to-indigo-700
							           hover:from-blue-700 hover:to-indigo-800
							           text-white px-4 py-2 text-sm rounded-lg font-medium
							           shadow-md hover:shadow-lg transition-all disabled:opacity-60
							           flex items-center gap-2"
						>
							{loading ? (
								<>
									<svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
										<circle className="opacity-25" cx="12" cy="12" r="10"
											stroke="currentColor" strokeWidth="4" />
										<path className="opacity-75" fill="currentColor"
											d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962
										         7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
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
							className="bg-white border border-gray-300 text-gray-700
							           hover:bg-gray-50 px-4 py-2 text-sm rounded-lg font-medium
							           shadow-sm transition-all disabled:opacity-60"
						>
							Print
						</button>
					</div>
				</div>

				{hasSearched && (
					<div id="ttot-print-area" className="bg-white rounded-2xl shadow-lg p-6">
						<h2 className="text-xl font-bold text-gray-800 text-center">
							LIST PELAPORAN TERDUGA TERORIS DAN ORGANISASI TERORIS
						</h2>
						<p className="text-center text-sm text-gray-600 mb-4">
							Periode {dateFrom.toLocaleDateString('id-ID', { day: '2-digit', month: 'long', year: 'numeric' })}
							{' - '}
							{dateTo.toLocaleDateString('id-ID', { day: '2-digit', month: 'long', year: 'numeric' })}
						</p>

						<div className="overflow-x-auto">
							<table className="w-full text-sm border-collapse">
								<thead>
									<tr className="bg-gray-100 text-gray-700">
										<th className="border border-gray-300 px-2 py-2 w-[5%]">No.</th>
										<th className="border border-gray-300 px-2 py-2 w-[30%]">Customer Name</th>
										<th className="border border-gray-300 px-2 py-2 w-[25%]">Alias Name</th>
										<th className="border border-gray-300 px-2 py-2 w-[30%]">Address</th>
										<th className="border border-gray-300 px-2 py-2 w-[10%] print:hidden">Detail</th>
									</tr>
								</thead>
								<tbody>
									{results.length === 0 ? (
										<tr>
											<td colSpan={5} className="border border-gray-300 px-2 py-4 text-center text-red-600 font-medium">
												Data Not Found
											</td>
										</tr>
									) : (
										results.map((row, idx) => (
											<tr
												key={`${row.blacklist_id}-${row.no}`}
												className={idx % 2 === 0 ? 'bg-gray-50' : 'bg-white'}
											>
												<td className="border border-gray-300 px-2 py-1 text-center">{row.no}.</td>
												<td className="border border-gray-300 px-2 py-1">{row.name}</td>
												<td className="border border-gray-300 px-2 py-1">{row.alias}</td>
												<td className="border border-gray-300 px-2 py-1">{row.address}</td>
												<td className="border border-gray-300 px-2 py-1 text-center print:hidden">
													<button
														onClick={() => handleViewDetail(row)}
														className="bg-blue-600 hover:bg-blue-700 text-white
														           px-3 py-1 rounded text-xs font-medium transition-colors"
													>
														View
													</button>
												</td>
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

export default TtotReportPage;