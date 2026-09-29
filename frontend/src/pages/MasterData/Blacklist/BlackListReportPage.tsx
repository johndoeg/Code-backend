import React, { useEffect, useState } from 'react';
import api from '../../../api/axiosInstance';
import Pagination from '../../../helpers/Pagination';
import { DEFAULT_PAGE_LIMIT } from "../../../constants/DefaultValue";
import AsOfDatePicker from '../../../components/AsOfDatePickerComponent';

const toISO = (d: Date): string => d.toISOString().split('T')[0];

type SearchBy = '' | '1' | '2' | '3';

interface ReasonOption {
	VALUE: string;
	DESC_VALUE: string;
}

interface BlacklistRow {
	no: number;
	name: string;
	customer_no: string;
	address: string;
	identitas: string;
	phone: string;
	reason: string;
	create_user: string;
	create_date: string;
	status: 'Active' | 'Deleted';
	delete_by: string;
	attachment: string | null;
	lessee_type: string;
}

interface PreviewResponse {
	data: BlacklistRow[];
	page: number;
	page_size: number;
	total: number;
	total_pages: number;
	search_desc: string;
	view_desc: string;
	as_of: string;
}

const PAGE_SIZE = DEFAULT_PAGE_LIMIT;

const BlacklistReportPage: React.FC = () => {
	const [asOf, setAsOf] = useState<Date>(new Date());
	const [searchBy, setSearchBy] = useState<SearchBy>('');
	const [searchByText, setSearchByText] = useState('');
	const [reasonCat, setReasonCat] = useState('');
	const [reasons, setReasons] = useState<ReasonOption[]>([]);
	const [existing, setExisting] = useState(false);
	const [deleted, setDeleted] = useState(false);

	const [results, setResults] = useState<BlacklistRow[]>([]);
	const [searchDesc, setSearchDesc] = useState('');
	const [viewDesc, setViewDesc] = useState('');
	const [page, setPage] = useState(1);
	const [totalPages, setTotalPages] = useState(1);
	const [total, setTotal] = useState(0);
	const [hasSearched, setHasSearched] = useState(false);

	const [loading, setLoading] = useState(false);
	const [exportingExcel, setExportingExcel] = useState(false);
	const [exportingWord, setExportingWord] = useState(false);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		const loadReasons = async () => {
			try {
				const response = await api.get('/MasterData/api/blacklist-report/reasons');
				setReasons(response.data);
			} catch (err) {
				console.error('Failed to load reason categories:', err);
			}
		};
		loadReasons();
	}, []);

	const buildParams = (targetPage: number) => ({
		as_of: toISO(asOf),
		searchby: searchBy,
		searchbytext: searchBy === '3' ? '' : searchByText,
		reason_cat: searchBy === '3' ? reasonCat : '',
		existing: existing ? 'existing' : '',
		deleted: deleted ? 'deleted' : '',
		page: targetPage,
		page_size: PAGE_SIZE,
	});

	const handlePreview = async (targetPage: number = 1) => {
		if (!asOf) {
			alert('Please fill the As Of date first.');
			return;
		}

		setLoading(true);
		setError(null);

		try {
			const response = await api.get<PreviewResponse>('/MasterData/api/blacklist-report/preview', {
				params: buildParams(targetPage),
			});

			setResults(response.data.data);
			setSearchDesc(response.data.search_desc);
			setViewDesc(response.data.view_desc);
			setPage(response.data.page);
			setTotalPages(response.data.total_pages);
			setTotal(response.data.total);
			setHasSearched(true);
		} catch (err) {
			console.error('Preview error:', err);
			setError('Failed to load preview. Please try again.');
		} finally {
			setLoading(false);
		}
	};

	const handlePrint = () => {
		if (results.length === 0) {
			alert('Please preview the data first.');
			return;
		}
		window.print();
	};

	const handleExport = async (kind: 'excel' | 'word') => {
		if (!asOf) {
			alert('Please fill the As Of date first.');
			return;
		}

		const setBusy = kind === 'excel' ? setExportingExcel : setExportingWord;
		setBusy(true);
		setError(null);

		try {
			const response = await api.get(`/MasterData/api/blacklist-report/${kind}`, {
				params: buildParams(1),
				responseType: 'blob',
			});

			const mime = kind === 'excel'
				? 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
				: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
			const ext = kind === 'excel' ? 'xlsx' : 'docx';

			const blob = new Blob([response.data], { type: mime });
			const url = URL.createObjectURL(blob);
			const anchor = document.createElement('a');
			anchor.href = url;
			anchor.download = `BlacklistReport_${toISO(asOf)}.${ext}`;
			anchor.click();
			URL.revokeObjectURL(url);
		} catch (err) {
			console.error('Export error:', err);
			setError('Failed to export. Please try again.');
		} finally {
			setBusy(false);
		}
	};

	const handleSearchByChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
		const value = e.target.value as SearchBy;
		setSearchBy(value);
		setSearchByText('');
		setReasonCat('');
	};

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<style>{`
				@page {
					size: landscape;
					margin: 10mm;
				}
				@media print {
					body * { visibility: hidden; }
					#blacklist-print-area, #blacklist-print-area * { visibility: visible; }
					#blacklist-print-area {
						position: absolute;
						inset: 0;
						width: 100%;
						margin: 0;
						padding: 0;
						box-shadow: none;
						border-radius: 0;
					}
					#blacklist-print-area .overflow-x-auto {
						overflow: visible !important;
					}
					#blacklist-print-area table {
						width: 100% !important;
						table-layout: fixed;
						border-collapse: collapse;
						font-size: 8px;
					}
					#blacklist-print-area th,
					#blacklist-print-area td {
						padding: 2px 3px !important;
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
							Blacklist Report
						</h1>
					</div>

					<div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
						<div>
							<label className="block text-sm font-medium text-gray-700 mb-1">
								Branch
							</label>
							<div className="px-3 py-2 rounded-lg border border-gray-200 bg-gray-50 text-gray-600 text-sm">
								Consolidate
							</div>
						</div>

						<AsOfDatePicker
							label="As Of"
							value={asOf}
							onChange={(date) => { if (date) setAsOf(date); }}
							required
						/>
					</div>

					<div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
						<div>
							<label className="block text-sm font-medium text-gray-700 mb-1">
								Search by
							</label>
							<select
								value={searchBy}
								onChange={handleSearchByChange}
								className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm
								           focus:outline-none focus:ring-2 focus:ring-emerald-500"
							>
								<option value="">Select</option>
								<option value="1">Customer No</option>
								<option value="2">Customer Name</option>
								<option value="3">Reason</option>
							</select>
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700 mb-1">
								{searchBy === '3' ? 'Reason' : 'Keyword'}
							</label>
							{searchBy === '3' ? (
								<select
									value={reasonCat}
									onChange={(e) => setReasonCat(e.target.value)}
									className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm
									           focus:outline-none focus:ring-2 focus:ring-emerald-500"
								>
									<option value="">Select</option>
									{reasons.map((r) => (
										<option key={r.VALUE} value={r.VALUE}>
											{r.DESC_VALUE}
										</option>
									))}
								</select>
							) : (
								<input
									type="text"
									value={searchByText}
									onChange={(e) => setSearchByText(e.target.value)}
									disabled={searchBy === ''}
									placeholder={searchBy === '' ? 'Choose "Search by" first' : ''}
									className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm
									           focus:outline-none focus:ring-2 focus:ring-emerald-500
									           disabled:bg-gray-50 disabled:text-gray-400"
								/>
							)}
						</div>
					</div>

					<div className="mb-6">
						<label className="block text-sm font-medium text-gray-700 mb-2">
							View
						</label>
						<div className="flex flex-wrap gap-6">
							<label className="flex items-center gap-2 text-sm text-gray-700">
								<input
									type="checkbox"
									checked={existing}
									onChange={(e) => setExisting(e.target.checked)}
									className="h-4 w-4 rounded border-gray-300 text-emerald-600"
								/>
								Existing in blacklist report
							</label>
							<label className="flex items-center gap-2 text-sm text-gray-700">
								<input
									type="checkbox"
									checked={deleted}
									onChange={(e) => setDeleted(e.target.checked)}
									className="h-4 w-4 rounded border-gray-300 text-emerald-600"
								/>
								Data deleted from blacklist report
							</label>
						</div>
					</div>

					{error && (
						<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
							{error}
						</div>
					)}

					<div className="flex flex-wrap gap-2">
						<button
							onClick={() => handlePreview(1)}
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
									Loading…
								</>
							) : (
								'Preview'
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

						<button
							onClick={() => handleExport('word')}
							disabled={exportingWord}
							className="bg-gradient-to-r from-sky-600 to-blue-700
							           hover:from-sky-700 hover:to-blue-800
							           text-white px-4 py-2 text-sm rounded-lg font-medium
							           shadow-md hover:shadow-lg transition-all disabled:opacity-60"
						>
							{exportingWord ? 'Exporting…' : 'Export to Word'}
						</button>

						<button
							onClick={() => handleExport('excel')}
							disabled={exportingExcel}
							className="bg-gradient-to-r from-green-600 to-emerald-700
							           hover:from-green-700 hover:to-emerald-800
							           text-white px-4 py-2 text-sm rounded-lg font-medium
							           shadow-md hover:shadow-lg transition-all disabled:opacity-60"
						>
							{exportingExcel ? 'Exporting…' : 'Export to Excel'}
						</button>
					</div>
				</div>

				{hasSearched && (
					<div id="blacklist-print-area" className="bg-white rounded-2xl shadow-lg p-6">
						<h2 className="text-xl font-bold text-gray-800 text-center">
							BLACKLIST REPORT
						</h2>
						<p className="text-center text-sm text-gray-600 mb-4">
							As of {asOf.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}
						</p>

						<div className="text-sm text-gray-600 mb-4 space-y-1">
							<p><span className="font-medium text-gray-700">Branch:</span> Consolidate</p>
							<p><span className="font-medium text-gray-700">Search by:</span> {searchDesc}</p>
							<p><span className="font-medium text-gray-700">View:</span> {viewDesc}</p>
						</div>

						<div className="overflow-x-auto">
							<table className="w-full text-sm border-collapse">
								<colgroup>
									<col style={{ width: '4%' }} />
									<col style={{ width: '12%' }} />
									<col style={{ width: '9%' }} />
									<col style={{ width: '16%' }} />
									<col style={{ width: '8%' }} />
									<col style={{ width: '9%' }} />
									<col style={{ width: '8%' }} />
									<col style={{ width: '7%' }} />
									<col style={{ width: '7%' }} />
									<col style={{ width: '6%' }} />
									<col style={{ width: '7%' }} />
									<col style={{ width: '7%' }} />
								</colgroup>
								<thead>
									<tr className="bg-gray-100 text-gray-700">
										<th className="border border-gray-300 px-2 py-2 whitespace-nowrap">No</th>
										<th className="border border-gray-300 px-2 py-2 whitespace-nowrap">Customer Name</th>
										<th className="border border-gray-300 px-2 py-2 whitespace-nowrap">Customer Number</th>
										<th className="border border-gray-300 px-2 py-2 whitespace-nowrap">Address</th>
										<th className="border border-gray-300 px-2 py-2 whitespace-nowrap">No Identitas</th>
										<th className="border border-gray-300 px-2 py-2 whitespace-nowrap">Phone</th>
										<th className="border border-gray-300 px-2 py-2 whitespace-nowrap">Reason</th>
										<th className="border border-gray-300 px-2 py-2 whitespace-nowrap">Create By</th>
										<th className="border border-gray-300 px-2 py-2 whitespace-nowrap">Create Date</th>
										<th className="border border-gray-300 px-2 py-2 whitespace-nowrap">Status</th>
										<th className="border border-gray-300 px-2 py-2 whitespace-nowrap">Delete By</th>
										<th className="border border-gray-300 px-2 py-2 whitespace-nowrap">Attachment</th>
									</tr>
								</thead>
								<tbody>
									{results.length === 0 ? (
										<tr>
											<td colSpan={12} className="border border-gray-300 px-2 py-4 text-center text-red-600 font-medium">
												Data Not Found
											</td>
										</tr>
									) : (
										results.map((row, idx) => (
											<tr
												key={`${row.customer_no}-${row.no}`}
												className={idx % 2 === 0 ? 'bg-gray-50' : 'bg-white'}
											>
												<td className="border border-gray-300 px-2 py-1 text-center">{row.no}</td>
												<td className="border border-gray-300 px-2 py-1">{row.name}</td>
												<td className="border border-gray-300 px-2 py-1">{row.customer_no}</td>
												<td className="border border-gray-300 px-2 py-1">{row.address}</td>
												<td className="border border-gray-300 px-2 py-1">{row.identitas}</td>
												<td className="border border-gray-300 px-2 py-1">{row.phone}</td>
												<td className="border border-gray-300 px-2 py-1">{row.reason}</td>
												<td className="border border-gray-300 px-2 py-1">{row.create_user}</td>
												<td className="border border-gray-300 px-2 py-1 whitespace-nowrap">{row.create_date}</td>
												<td className="border border-gray-300 px-2 py-1 text-center">
													<span
														className={
															row.status === 'Deleted'
																? 'text-red-600 font-medium'
																: 'text-green-700 font-medium'
														}
													>
														{row.status}
													</span>
												</td>
												<td className="border border-gray-300 px-2 py-1 text-center">{row.delete_by}</td>
												<td className="border border-gray-300 px-2 py-1">{row.attachment ?? '-'}</td>
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
								onPageChange={(newPage) => handlePreview(newPage)}
								totalItems={total}
								itemsPerPage={PAGE_SIZE}
								className="mt-6 print:hidden"
							/>
						)}
					</div>
				)}
			</div>
		</div>
	);
};

export default BlacklistReportPage;