import React, { useEffect, useState } from 'react';
import api from '../../../../api/axiosInstance';
import AsOfDatePicker from '../../../../components/AsOfDatePickerComponent';
import Pagination from '../../../../helpers/Pagination';
import { DEFAULT_PAGE_LIMIT } from '../../../../constants/DefaultValue';

interface Branch {
	branch_cd: string;
	branch_name: string;
}

interface SummaryRow {
	no: number;
	employee_id: string;
	cmo_name: string;
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

const CmoDailyProductivityByCmoPage: React.FC = () => {
	const [branches, setBranches] = useState<Branch[]>([]);
	const [branch, setBranch] = useState('');
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

	useEffect(() => {
		(async () => {
			try {
				const response = await api.get<Branch[]>(
					'/CAM/CMO/api/daily-productivity-by-cmo/branches'
				);
				setBranches(response.data);

				const params = new URLSearchParams(window.location.search);
				const lemparStart = params.get('lempar_start_dt');
				const lemparEnd = params.get('lempar_end_dt');
				const lemparBranch = params.get('lempar_branch');

				const initialBranch = lemparBranch || (response.data.length === 1 ? response.data[0].branch_cd : '');
				const initialStart = lemparStart ? new Date(lemparStart) : null;
				const initialEnd = lemparEnd ? new Date(lemparEnd) : null;

				setBranch(initialBranch);
				setStartDate(initialStart);
				setEndDate(initialEnd);

				if (lemparBranch && initialStart && initialEnd) {
					await runSearch(initialBranch, initialStart, initialEnd);
				}
			} catch (err) {
				console.error('Branch list error:', err);
			}
		})();
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, []);

	const runSearch = async (branchCd: string, start: Date, end: Date) => {
		if (!branchCd || !start || !end) return;
		setLoading(true);
		setError(null);
		setHasSearched(true);
		setPage(1);
		try {
			const response = await api.get<{ data: SummaryRow[]; totals: SummaryTotals }>(
				'/CAM/CMO/api/daily-productivity-by-cmo/summary',
				{
					params: {
						start_date: toISO(start),
						end_date: toISO(end),
						branch: branchCd,
					},
				}
			);
			setRows(response.data.data);
			setTotals(response.data.totals);
		} catch (err) {
			console.error('CMO daily productivity summary error:', err);
			setError('Failed to load report. Please try again.');
		} finally {
			setLoading(false);
		}
	};

	const handleSearch = () => {
		if (!startDate || !endDate || !branch) return;
		runSearch(branch, startDate, endDate);
	};

	const buildDrillDownHref = (employeeId: string) => {
		if (!startDate || !endDate) return '#';
		const params = new URLSearchParams({
			lempar_start_dt: toISO(startDate),
			lempar_end_dt: toISO(endDate),
			lempar_branch: branch,
			lempar_cmo: employeeId,
		});
		return `/CAM/CMO/daily-productivity?${params.toString()}`;
	};

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-5xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6 mb-6">
					<div className="mb-6">
						<h1 className="text-xl md:text-2xl font-bold text-gray-800">
							Credit Marketing Officer Daily Productivity Global Report — By CMO
						</h1>
					</div>

					<div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6 text-sm items-end">
						<div>
							<label className="text-gray-500 block mb-1">Start Date</label>
							<AsOfDatePicker label="" value={startDate} onChange={setStartDate} required />
						</div>
						<div>
							<label className="text-gray-500 block mb-1">End Date</label>
							<AsOfDatePicker label="" value={endDate} onChange={setEndDate} required />
						</div>
						<div>
							<label className="text-gray-500 block mb-1">Branch</label>
							<select
								value={branch}
								onChange={(e) => setBranch(e.target.value)}
								className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
							>
								<option value="">Select branch</option>
								{branches.map((b) => (
									<option key={b.branch_cd} value={b.branch_cd}>
										{b.branch_name}
									</option>
								))}
							</select>
						</div>
					</div>

					<div className="mb-6">
						<button
							onClick={handleSearch}
							disabled={!startDate || !endDate || !branch}
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
									<th className="border border-gray-300 px-2 py-2">CMO</th>
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
											Choose a period and branch, then click Search.
										</td>
									</tr>
								) : (
									<>
										{pageRows.length === 0 ? (
											<tr>
												<td colSpan={8} className="border border-gray-300 px-2 py-4 text-center text-gray-400">
													No CMO activity found for this period.
												</td>
											</tr>
										) : (
											pageRows.map((row) => (
												<tr key={row.employee_id} className="odd:bg-gray-50">
													<td className="border border-gray-300 px-2 py-1 text-center">{row.no}</td>
													<td className="border border-gray-300 px-2 py-1 text-center">
														<a
															href={buildDrillDownHref(row.employee_id)}
															className="text-blue-600 hover:text-blue-800 hover:underline"
														>
															{row.cmo_name}
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

export default CmoDailyProductivityByCmoPage;