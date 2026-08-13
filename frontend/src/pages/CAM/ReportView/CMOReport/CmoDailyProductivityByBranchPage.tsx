import React, { useState } from 'react';
import api from '../../../../api/axiosInstance';
import AsOfDatePicker from '../../../../components/AsOfDatePickerComponent';
import Pagination from '../../../../helpers/Pagination';
import { DEFAULT_PAGE_LIMIT } from '../../../../constants/DefaultValue';

interface SummaryRow {
	no: number;
	branch_cd: string;
	branch_name: string;
	total_created: number;
	total_reject: number;
	total_defect1: number;
	total_defect2: number;
	total_defect3: number;
	sub_total: number;
}

interface SummaryTotals {
	total_created: number;
	total_reject: number;
	total_defect1: number;
	total_defect2: number;
	total_defect3: number;
	sub_total: number;
}

const PAGE_SIZE = DEFAULT_PAGE_LIMIT;

const toISO = (d: Date): string => {
	const year = d.getFullYear();
	const month = String(d.getMonth() + 1).padStart(2, '0');
	const day = String(d.getDate()).padStart(2, '0');
	return `${year}-${month}-${day}`;
};

const CmoDailyProductivityByBranchPage: React.FC = () => {
	const [startDate, setStartDate] = useState<Date | null>(null);
	const [endDate, setEndDate] = useState<Date | null>(null);

	const [rows, setRows] = useState<SummaryRow[]>([]);
	const [totals, setTotals] = useState<SummaryTotals | null>(null);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [hasSearched, setHasSearched] = useState(false);

	const [page, setPage] = useState(1);
	const totalPages = Math.ceil(rows.length / PAGE_SIZE);
	const pageRows = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

	const handleSearch = async () => {
		if (!startDate || !endDate) return;
		setLoading(true);
		setError(null);
		setHasSearched(true);
		setPage(1);
		try {
			const response = await api.get<{ data: SummaryRow[]; totals: SummaryTotals }>(
				'/CAM/CMO/api/daily-productivity-by-branch/summary',
				{
					params: {
						start_date: toISO(startDate),
						end_date: toISO(endDate),
					},
				}
			);
			setRows(response.data.data);
			setTotals(response.data.totals);
		} catch (err) {
			console.error('CMO daily productivity by-branch summary error:', err);
			setError('Failed to load report. Please try again.');
		} finally {
			setLoading(false);
		}
	};

	const buildDrillDownHref = (branchCd: string) => {
		if (!startDate || !endDate) return '#';
		const params = new URLSearchParams({
			lempar_start_dt: toISO(startDate),
			lempar_end_dt: toISO(endDate),
			lempar_branch: branchCd,
		});
		return `/CAM/CMO/daily-productivity-by-cmo?${params.toString()}`;
	};

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-5xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6 mb-6">
					<div className="mb-6">
						<h1 className="text-xl md:text-2xl font-bold text-gray-800">
							Credit Marketing Officer Daily Productivity Global Report — By Branch
						</h1>
					</div>

					<div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6 text-sm items-end max-w-md">
						<div>
							<label className="text-gray-500 block mb-1">Start Date</label>
							<AsOfDatePicker label="" value={startDate} onChange={setStartDate} required />
						</div>
						<div>
							<label className="text-gray-500 block mb-1">End Date</label>
							<AsOfDatePicker label="" value={endDate} onChange={setEndDate} required />
						</div>
					</div>

					<div className="mb-6">
						<button
							onClick={handleSearch}
							disabled={!startDate || !endDate}
							className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
						>
							Search
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
									<th className="border border-gray-300 px-2 py-2">No.</th>
									<th className="border border-gray-300 px-2 py-2">Branch</th>
									<th className="border border-gray-300 px-2 py-2">CAM Created</th>
									<th className="border border-gray-300 px-2 py-2">Reject to Watchlist</th>
									<th className="border border-gray-300 px-2 py-2">Customer is not Feasible to be Financed</th>
									<th className="border border-gray-300 px-2 py-2">Customer is Financed Another Leasing Company</th>
									<th className="border border-gray-300 px-2 py-2">Customer Cancel Their Application</th>
									<th className="border border-gray-300 px-2 py-2">Total Application</th>
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
											Choose a period, then click Search.
										</td>
									</tr>
								) : (
									<>
										{pageRows.length === 0 ? (
											<tr>
												<td colSpan={8} className="border border-gray-300 px-2 py-4 text-center text-gray-400">
													No branch activity found for this period.
												</td>
											</tr>
										) : (
											pageRows.map((row) => (
												<tr key={row.branch_cd} className="odd:bg-gray-50">
													<td className="border border-gray-300 px-2 py-1 text-center">{row.no}</td>
													<td className="border border-gray-300 px-2 py-1 text-center">
														<a
															href={buildDrillDownHref(row.branch_cd)}
															className="text-blue-600 hover:text-blue-800 hover:underline"
														>
															{row.branch_name}
														</a>
													</td>
													<td className="border border-gray-300 px-2 py-1 text-center">{row.total_created}</td>
													<td className="border border-gray-300 px-2 py-1 text-center">{row.total_reject}</td>
													<td className="border border-gray-300 px-2 py-1 text-center">{row.total_defect1}</td>
													<td className="border border-gray-300 px-2 py-1 text-center">{row.total_defect2}</td>
													<td className="border border-gray-300 px-2 py-1 text-center">{row.total_defect3}</td>
													<td className="border border-gray-300 px-2 py-1 text-center">{row.sub_total}</td>
												</tr>
											))
										)}
										{totals && (
											<tr className="bg-gray-100 font-semibold">
												<td colSpan={2} className="border border-gray-300 px-2 py-1 text-center">Total</td>
												<td className="border border-gray-300 px-2 py-1 text-center">{totals.total_created}</td>
												<td className="border border-gray-300 px-2 py-1 text-center">{totals.total_reject}</td>
												<td className="border border-gray-300 px-2 py-1 text-center">{totals.total_defect1}</td>
												<td className="border border-gray-300 px-2 py-1 text-center">{totals.total_defect2}</td>
												<td className="border border-gray-300 px-2 py-1 text-center">{totals.total_defect3}</td>
												<td className="border border-gray-300 px-2 py-1 text-center">{totals.sub_total}</td>
											</tr>
										)}
									</>
								)}
							</tbody>
						</table>
					</div>

					{!loading && rows.length > PAGE_SIZE && (
						<Pagination
							page={page}
							totalPages={totalPages}
							onPageChange={setPage}
							totalItems={rows.length}
							itemsPerPage={PAGE_SIZE}
							className="mt-6"
						/>
					)}
				</div>
			</div>
		</div>
	);
};

export default CmoDailyProductivityByBranchPage;