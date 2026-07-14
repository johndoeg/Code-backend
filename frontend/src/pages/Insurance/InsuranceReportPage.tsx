import React, { useState, useCallback } from 'react';
import api from '../../api/axiosInstance';
import AsOfDatePicker from '../../components/AsOfDatePickerComponent';
import Pagination from '../../helpers/Pagination';
import { DEFAULT_PAGE_LIMIT } from '../../constants/DefaultValue';

const toISO = (d: Date): string => d.toISOString().split('T')[0];

interface InsuranceReportRow {
	lease_no: string;
	lessee_nm: string;
	ins_co: string;
	policy_no: string;
	status: string;
	message: string;
	success_dt: string;
}

interface InsuranceCompany {
	INS_CD: string;
	INS_CO: string;
}

type SearchBy = '' | '1' | '2';

const InsuranceReportPage: React.FC = () => {
	const [companies, setCompanies] = useState<InsuranceCompany[]>([]);
	const [selectedIns, setSelectedIns] = useState<string>('');
	const [searchBy, setSearchBy] = useState<SearchBy>('');
	const [searchText, setSearchText] = useState<string>('');
	const [dateFrom, setDateFrom] = useState<Date>(new Date());
	const [dateTo, setDateTo] = useState<Date>(new Date());
	const [records, setRecords] = useState<InsuranceReportRow[]>([]);
	const [loading, setLoading] = useState<boolean>(false);
	const [exporting, setExporting] = useState<boolean>(false);
	const [error, setError] = useState<string | null>(null);
	const [searched, setSearched] = useState<boolean>(false);
	const [page, setPage] = useState<number>(1);
	const [total, setTotal] = useState<number>(0);
	const limit = DEFAULT_PAGE_LIMIT;

	React.useEffect(() => {
		api.get('/InsuranceReport/api/companies')
			.then(res => {
				const data: InsuranceCompany[] = res.data ?? [];
				setCompanies(data);
				if (data.length > 0) setSelectedIns(data[0].INS_CD);
			})
			.catch(() => {});
	}, []);

	const validate = (): string | null => {
		if (!searchBy) return null;
		if (searchBy === '1' && !searchText.trim()) return 'Please fill Contract No.';
		if (searchBy === '2' && !dateFrom) return 'Please select date from.';
		if (searchBy === '2' && !dateTo) return 'Please select date to.';
		if (searchBy === '2' && dateFrom > dateTo) return 'Date from cannot be greater than date to.';

		return null;
	};

	const buildParams = () => ({
		ins_cd: selectedIns,
		search_by: searchBy,
		search_val: searchBy === '1' ? searchText.trim() : '',
		search_val1: searchBy === '2' ? toISO(dateFrom) : '',
		search_val2: searchBy === '2' ? toISO(dateTo) : '',
		page,
		limit,
	});

	const handleSearch = useCallback(async (overridePage = 1) => {
		const err = validate();
		if (err) { alert(err); return; }

		setLoading(true);
		setError(null);
		setPage(overridePage);

		try {
			const res = await api.get('/InsuranceReport/api/list', {
				params: { ...buildParams(), page: overridePage },
			});
			if (res.data?.data) {
				setRecords(res.data.data);
				setTotal(res.data.total ?? res.data.data.length);
			} else {
				setRecords([]);
				setTotal(0);
			}
			setSearched(true);
		} catch {
			setError('Failed to load data. Please try again.');
		} finally {
			setLoading(false);
		}
	}, [selectedIns, searchBy, searchText, dateFrom, dateTo, limit]);

	React.useEffect(() => {
		if (searched) handleSearch(page);
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [page]);

	const handleExport = async () => {
		const err = validate();
		if (err) { alert(err); return; }

		setExporting(true);
		setError(null);
		try {
			const res = await api.get('/InsuranceReport/api/excel', {
				params: buildParams(),
				responseType: 'blob',
			});
			const blob = new Blob([res.data], {
				type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
			});
			const url = URL.createObjectURL(blob);
			const anchor = document.createElement('a');
			anchor.href = url;
			anchor.download = `InsuranceReport_${toISO(new Date())}.xlsx`;
			anchor.click();
			URL.revokeObjectURL(url);
		} catch {
			setError('Failed to export. Please try again.');
		} finally {
			setExporting(false);
		}
	};

	const totalPages = Math.ceil(total / limit);
	const startIndex = (page - 1) * limit + 1;

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-7xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6 mb-6">

					<div className="mb-6">
						<h1 className="text-2xl md:text-3xl font-bold text-gray-800">Insurance Report</h1>
					</div>

					<div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6 mb-6">
						<div className="flex flex-col gap-1.5">
							<label htmlFor="ins_cd" className="text-sm font-medium text-gray-700">
								Insurance Company
							</label>
							<select
								id="ins_cd"
								value={selectedIns}
								onChange={e => setSelectedIns(e.target.value)}
								className="px-3 py-2 border border-gray-300 rounded-lg text-sm shadow-sm
								           focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
							>
								{companies.map(c => (
									<option key={c.INS_CD} value={c.INS_CD}>{c.INS_CO}</option>
								))}
							</select>
						</div>

						<div className="flex flex-col gap-1.5">
							<label htmlFor="search_by" className="text-sm font-medium text-gray-700">
								Search By
							</label>
							<select
								id="search_by"
								value={searchBy}
								onChange={e => { setSearchBy(e.target.value as SearchBy); setSearchText(''); }}
								className="px-3 py-2 border border-gray-300 rounded-lg text-sm shadow-sm
								           focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
							>
								<option value="">— Search by —</option>
								<option value="1">Contract No.</option>
								<option value="2">Disbursement Date</option>
							</select>
						</div>

						{searchBy === '1' && (
							<div className="flex flex-col gap-1.5">
								<label className="text-sm font-medium text-gray-700">Contract No.</label>
								<input
									type="text"
									value={searchText}
									onChange={e => setSearchText(e.target.value)}
									onKeyDown={e => e.key === 'Enter' && handleSearch(1)}
									placeholder="Enter contract no."
									className="px-3 py-2 border border-gray-300 rounded-lg text-sm shadow-sm
									           focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
								/>
							</div>
						)}

						{searchBy === '2' && (
							<>
								<AsOfDatePicker
									label="Date From"
									value={dateFrom}
									onChange={date => {
										if (date) {
											setDateFrom(date);
											if (date > dateTo) setDateTo(date);
										}
									}}
									maxDate={dateTo}
									required
								/>
								<AsOfDatePicker
									label="Date To"
									value={dateTo}
									onChange={date => { if (date) setDateTo(date); }}
									minDate={dateFrom}
									required
								/>
							</>
						)}
					</div>

					{error && (
						<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700
						                flex items-center gap-2 text-sm">
							<svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24"
								stroke="currentColor" strokeWidth={2}>
								<circle cx="12" cy="12" r="10" />
								<line x1="12" y1="8" x2="12" y2="12" />
								<line x1="12" y1="16" x2="12.01" y2="16" />
							</svg>
							{error}
						</div>
					)}

					<div className="flex flex-wrap gap-2 mb-6">
						<button
							onClick={() => handleSearch(1)}
							disabled={loading}
							className="bg-gradient-to-r from-emerald-600 to-green-700
							           hover:from-emerald-700 hover:to-green-800
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
											d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
									</svg>
									Searching…
								</>
							) : 'Search'}
						</button>

						<button
							onClick={handleExport}
							disabled={exporting || !searched}
							className="bg-gradient-to-r from-green-600 to-emerald-700
							           hover:from-green-700 hover:to-emerald-800
							           text-white px-4 py-2 text-sm rounded-lg font-medium
							           shadow-md hover:shadow-lg transition-all disabled:opacity-60
							           flex items-center gap-2"
						>
							{exporting ? (
								<>
									<svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
										<circle className="opacity-25" cx="12" cy="12" r="10"
											stroke="currentColor" strokeWidth="4" />
										<path className="opacity-75" fill="currentColor"
											d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
									</svg>
									Exporting…
								</>
							) : 'Export to Excel'}
						</button>
					</div>

					<div className="overflow-x-auto overflow-y-auto rounded-lg border border-gray-200 max-h-[65vh]">
						<table className="w-full text-sm">
							<thead className="bg-gradient-to-r from-gray-50 to-gray-100 sticky top-0">
								<tr>
									{[
										{ label: 'No.', w: '5%' },
										{ label: 'Contract No.', w: '15%' },
										{ label: 'Customer Name', w: '25%' },
										{ label: 'Insurance Company', w: '15%' },
										{ label: 'Policy No.', w: '15%' },
										{ label: 'Status', w: '5%' },
										{ label: 'Message', w: '10%' },
										{ label: 'Success Date', w: '10%' },
									].map(({ label, w }) => (
										<th
											key={label}
											style={{ width: w }}
											className="py-3 px-4 text-left text-xs font-medium text-gray-500
											           uppercase tracking-wider whitespace-nowrap"
										>
											{label}
										</th>
									))}
								</tr>
							</thead>
							<tbody className="divide-y divide-gray-200">
								{loading ? (
									<tr>
										<td colSpan={8} className="py-10 text-center">
											<div className="flex justify-center">
												<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
											</div>
										</td>
									</tr>
								) : !searched ? (
									<tr>
										<td colSpan={8} className="py-10 text-center text-gray-400 italic text-sm">
											Select filters and click Search to load data.
										</td>
									</tr>
								) : records.length === 0 ? (
									<tr>
										<td colSpan={8} className="py-10 text-center text-gray-500">
											No records found.
										</td>
									</tr>
								) : (
									records.map((r, idx) => (
										<tr
											key={r.lease_no + idx}
											className={`hover:bg-gray-50 transition-colors
											            ${idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}`}
										>
											<td className="py-3 px-4 text-center font-medium text-gray-900">
												{startIndex + idx}
											</td>
											<td className="py-3 px-4 text-gray-700">{r.lease_no}</td>
											<td className="py-3 px-4 text-gray-700 max-w-[200px] truncate"
												title={r.lessee_nm}>{r.lessee_nm}</td>
											<td className="py-3 px-4 text-gray-700 max-w-[160px] truncate"
												title={r.ins_co}>{r.ins_co}</td>
											<td className="py-3 px-4 text-gray-700">{r.policy_no}</td>
											<td className="py-3 px-4 text-gray-700">{r.status}</td>
											<td className="py-3 px-4 text-gray-700 max-w-[160px] truncate"
												title={r.message}>{r.message}</td>
											<td className="py-3 px-4 text-gray-700 whitespace-nowrap">
												{r.success_dt}
											</td>
										</tr>
									))
								)}
							</tbody>
						</table>
					</div>

					{!loading && total > 0 && (
						<Pagination
							page={page}
							totalPages={totalPages}
							onPageChange={setPage}
							totalItems={total}
							itemsPerPage={limit}
							className="mt-6"
						/>
					)}
				</div>
			</div>
		</div>
	);
};

export default InsuranceReportPage;