import React, { useState } from 'react';
import api from '../../../api/axiosInstance';
import Pagination from '../../../helpers/Pagination';
import { DEFAULT_PAGE_LIMIT } from '../../../constants/DefaultValue';
import AsOfDatePicker from '../../../components/AsOfDatePickerComponent';

const toISO = (d: Date): string => d.toISOString().split('T')[0];

type SearchBy = '' | '1' | '2';

interface WatchlistRow {
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

interface ListResponse {
	data: WatchlistRow[];
	page: number;
	page_size: number;
	total: number;
	total_pages: number;
	search_desc: string;
	view_desc: string;
	as_of: string;
}

interface AddressBlock {
	address: string;
	city: string;
	zipcode: string;
	phone: string;
	fax: string | null;
}

interface ReferenceRow {
	no: number;
	name: string;
	phone: string;
	remark: string;
}

interface DocumentRow {
	label: string;
	filename: string | null;
}

interface PRDetail {
	lessee_type: 'PR';
	name: string;
	customer_type: string;
	group_name: string;
	id_address: AddressBlock | null;
	correspondence: AddressBlock | null;
	additional_1: AddressBlock | null;
	additional_2: AddressBlock | null;
	mobile: string;
	email: string;
	npwp: string;
	spouse: string;
	mothers_maiden_name: string;
	place_of_birth: string;
	date_of_birth: string;
	gender: string;
	marital_status: string;
	religion: string;
	citizenship: string;
	nationality: string;
	id_card_no: string;
	family_card_no: string;
	industrial_code: string;
	bi_customer_type: string;
	other_phone_1: string;
	other_phone_1_notes: string;
	other_phone_2: string;
	other_phone_2_notes: string;
	review_date: string;
	references: ReferenceRow[];
	documents: {
		citizen_type: string | null;
		citizen_docs: DocumentRow[];
		additional_docs: DocumentRow[];
		bpkb_docs: DocumentRow[];
		other_doc: DocumentRow;
	};
}

interface PTDetail {
	lessee_type: 'PT';
	name: string;
	customer_type: string;
	group_name: string;
	id_address: AddressBlock | null;
	correspondence: AddressBlock | null;
	additional_1: AddressBlock | null;
	additional_2: AddressBlock | null;
	mobile: string;
	email: string;
	npwp: string;
	contact: string;
	position: string;
	line_of_business: string;
	establishment_date: string;
	industrial_code: string;
	bi_customer_type: string;
	office_status: string;
	other_phone_1: string;
	other_phone_1_notes: string;
	other_phone_2: string;
	other_phone_2_notes: string;
	review_date: string;
	references: ReferenceRow[];
	documents: {
		org_type: string | null;
		org_docs: DocumentRow[];
		bpkb_docs: DocumentRow[];
		other_doc: DocumentRow;
	};
}

type CustomerDetail = PRDetail | PTDetail;

const PAGE_SIZE = DEFAULT_PAGE_LIMIT;

const Field: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
	<div className="border border-gray-200 rounded-lg px-3 py-2">
		<div className="text-xs font-medium text-gray-500">{label}</div>
		<div className="text-sm text-gray-800 mt-0.5">{children || '-'}</div>
	</div>
);

const AddressValue: React.FC<{ block: AddressBlock | null }> = ({ block }) => {
	if (!block) return <>-</>;
	return (
		<>
			{block.address}
			<br />
			{block.city}{block.city && block.zipcode ? ', ' : ''}{block.zipcode}
			<br />
			(P) {block.phone}{block.fax ? ` - (F) ${block.fax}` : ''}
		</>
	);
};

const DocumentList: React.FC<{ title: string; rows: DocumentRow[] }> = ({ title, rows }) => (
	<div className="mb-4">
		<div className="text-sm font-semibold text-gray-700 mb-2">{title}</div>
		<div className="space-y-1">
			{rows.map((row) => (
				<div key={row.label} className="flex justify-between text-sm border-b border-gray-100 py-1">
					<span className="text-gray-600">{row.label}</span>
					<span className="text-gray-800">{row.filename ?? '-'}</span>
				</div>
			))}
		</div>
	</div>
);

const WatchlistReportPage: React.FC = () => {
	const [asOf, setAsOf] = useState<Date>(new Date());
	const [searchBy, setSearchBy] = useState<SearchBy>('');
	const [searchByText, setSearchByText] = useState('');
	const [existing, setExisting] = useState(false);
	const [deleted, setDeleted] = useState(false);

	const [results, setResults] = useState<WatchlistRow[]>([]);
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

	const [detailOpen, setDetailOpen] = useState(false);
	const [detailLoading, setDetailLoading] = useState(false);
	const [detailError, setDetailError] = useState<string | null>(null);
	const [detail, setDetail] = useState<CustomerDetail | null>(null);

	const buildParams = (targetPage: number) => ({
		as_of: toISO(asOf),
		searchby: searchBy,
		searchbytext: searchByText,
		existing: existing ? 'existing' : '',
		deleted: deleted ? 'deleted' : '',
		page: targetPage,
		page_size: PAGE_SIZE,
	});

	const handleSearch = async (targetPage: number = 1) => {
		if (!asOf) {
			alert('Please fill the As Of date first.');
			return;
		}

		setLoading(true);
		setError(null);

		try {
			const response = await api.get<ListResponse>('/MasterData/api/watchlist-report/list', {
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
			console.error('Watchlist search error:', err);
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
			const response = await api.get(`/MasterData/api/watchlist-report/${kind}`, {
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
			anchor.download = `WatchlistReport_${toISO(asOf)}.${ext}`;
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
		setSearchBy(e.target.value as SearchBy);
		setSearchByText('');
	};

	const openDetail = async (row: WatchlistRow) => {
		setDetailOpen(true);
		setDetail(null);
		setDetailError(null);
		setDetailLoading(true);

		try {
			const response = await api.get<CustomerDetail>(
				`/MasterData/api/watchlist-report/detail/${encodeURIComponent(row.customer_no)}`
			);
			setDetail(response.data);
		} catch (err) {
			console.error('Customer detail error:', err);
			setDetailError('Failed to load customer detail. Please try again.');
		} finally {
			setDetailLoading(false);
		}
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
					#watchlist-print-area, #watchlist-print-area * { visibility: visible; }
					#watchlist-print-area {
						position: absolute;
						inset: 0;
						width: 100%;
						margin: 0;
						padding: 0;
						box-shadow: none;
						border-radius: 0;
					}
					#watchlist-print-area .overflow-x-auto {
						overflow: visible !important;
					}
					#watchlist-print-area table {
						width: 100% !important;
						table-layout: fixed;
						border-collapse: collapse;
						font-size: 8px;
					}
					#watchlist-print-area th,
					#watchlist-print-area td {
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
							Watchlist Report
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
							</select>
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700 mb-1">
								Keyword
							</label>
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
								Existing in Watchlist Report
							</label>
							<label className="flex items-center gap-2 text-sm text-gray-700">
								<input
									type="checkbox"
									checked={deleted}
									onChange={(e) => setDeleted(e.target.checked)}
									className="h-4 w-4 rounded border-gray-300 text-emerald-600"
								/>
								Data Deleted from Watchlist Report
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
							onClick={() => handleSearch(1)}
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
					<div id="watchlist-print-area" className="bg-white rounded-2xl shadow-lg p-6">
						<h2 className="text-xl font-bold text-gray-800 text-center">
							WATCHLIST REPORT
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
												<td className="border border-gray-300 px-2 py-1">
													<button
														onClick={() => openDetail(row)}
														className="text-blue-600 hover:underline print:no-underline print:text-inherit"
													>
														{row.customer_no}
													</button>
												</td>
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
								onPageChange={(newPage) => handleSearch(newPage)}
								totalItems={total}
								itemsPerPage={PAGE_SIZE}
								className="mt-6 print:hidden"
							/>
						)}
					</div>
				)}
			</div>

			{detailOpen && (
				<div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4 print:hidden">
					<div className="bg-white rounded-2xl shadow-xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
						<div className="flex justify-between items-center p-6 border-b">
							<h2 className="text-xl font-bold text-gray-800">Customer Detail Review</h2>
							<button onClick={() => setDetailOpen(false)} className="text-gray-500 hover:text-gray-700">
								<svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
								</svg>
							</button>
						</div>

						<div className="p-6 overflow-y-auto flex-grow min-h-0">
							{detailLoading && (
								<div className="flex justify-center py-10">
									<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
								</div>
							)}

							{detailError && (
								<div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
									{detailError}
								</div>
							)}

							{!detailLoading && !detailError && detail && (
								<div className="space-y-6">
									<div>
										<h3 className="text-lg font-bold text-gray-800">{detail.name}</h3>
										<p className="text-sm text-gray-500">
											{detail.lessee_type === 'PR' ? 'Individual (PR)' : 'Company (PT)'}
											{' · '}{detail.customer_type}
										</p>
									</div>

									<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
										<Field label="ID Address"><AddressValue block={detail.id_address} /></Field>
										<Field label="Correspondence"><AddressValue block={detail.correspondence} /></Field>
										<Field label="Additional 1"><AddressValue block={detail.additional_1} /></Field>
										<Field label="Additional 2"><AddressValue block={detail.additional_2} /></Field>
										<Field label="Mobile">{detail.mobile}</Field>
										<Field label="Email">{detail.email}</Field>
										<Field label="NPWP">{detail.npwp}</Field>
										<Field label="Group">{detail.group_name}</Field>
										<Field label="Industrial Code">{detail.industrial_code}</Field>
										<Field label="BI Customer Type">{detail.bi_customer_type}</Field>
										<Field label="Review Date">{detail.review_date}</Field>

										{detail.lessee_type === 'PR' ? (
											<>
												<Field label="Spouse">{detail.spouse}</Field>
												<Field label="Mother's Maiden Name">{detail.mothers_maiden_name}</Field>
												<Field label="Date / Place of Birth">
													{detail.date_of_birth} / {detail.place_of_birth}
												</Field>
												<Field label="Gender">{detail.gender}</Field>
												<Field label="Marital Status">{detail.marital_status}</Field>
												<Field label="Religion">{detail.religion}</Field>
												<Field label="Citizenship">{detail.citizenship} / {detail.nationality}</Field>
												<Field label="ID Card No.">{detail.id_card_no}</Field>
												<Field label="Family Card No.">{detail.family_card_no}</Field>
											</>
										) : (
											<>
												<Field label="Contact">{detail.contact}</Field>
												<Field label="Position">{detail.position}</Field>
												<Field label="Line of Business">{detail.line_of_business}</Field>
												<Field label="Establishment Date">{detail.establishment_date}</Field>
												<Field label="Office Status">{detail.office_status}</Field>
											</>
										)}

										<Field label="Other Phone 1">
											{detail.other_phone_1}{detail.other_phone_1_notes ? ` (${detail.other_phone_1_notes})` : ''}
										</Field>
										<Field label="Other Phone 2">
											{detail.other_phone_2}{detail.other_phone_2_notes ? ` (${detail.other_phone_2_notes})` : ''}
										</Field>
									</div>

									{detail.references.length > 0 && (
										<div>
											<h4 className="text-sm font-semibold text-gray-700 mb-2">References</h4>
											<div className="overflow-x-auto rounded-lg border border-gray-200">
												<table className="w-full text-sm">
													<thead className="bg-gray-50">
														<tr>
															<th className="py-2 px-3 text-left text-xs font-medium text-gray-500 uppercase">No.</th>
															<th className="py-2 px-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
															<th className="py-2 px-3 text-left text-xs font-medium text-gray-500 uppercase">Phone</th>
															<th className="py-2 px-3 text-left text-xs font-medium text-gray-500 uppercase">Remark</th>
														</tr>
													</thead>
													<tbody className="divide-y divide-gray-100">
														{detail.references.map((ref) => (
															<tr key={ref.no}>
																<td className="py-2 px-3">{ref.no}</td>
																<td className="py-2 px-3">{ref.name}</td>
																<td className="py-2 px-3">{ref.phone}</td>
																<td className="py-2 px-3">{ref.remark}</td>
															</tr>
														))}
													</tbody>
												</table>
											</div>
										</div>
									)}

									<div>
										<h4 className="text-sm font-semibold text-gray-700 mb-2">Documents</h4>
										{detail.lessee_type === 'PR' ? (
											<>
												<DocumentList
													title={detail.documents.citizen_type ?? 'Identity Documents'}
													rows={detail.documents.citizen_docs}
												/>
												<DocumentList title="Dokumen Tambahan" rows={detail.documents.additional_docs} />
												<DocumentList title="Dokumen BPKB" rows={detail.documents.bpkb_docs} />
												<DocumentList title="Other" rows={[detail.documents.other_doc]} />
											</>
										) : (
											<>
												<DocumentList
													title={`Customer Type: ${detail.documents.org_type ?? '-'}`}
													rows={detail.documents.org_docs}
												/>
												<DocumentList title="Dokumen BPKB" rows={detail.documents.bpkb_docs} />
												<DocumentList title="Other" rows={[detail.documents.other_doc]} />
											</>
										)}
									</div>
								</div>
							)}
						</div>

						<div className="p-4 border-t flex justify-end">
							<button
								onClick={() => setDetailOpen(false)}
								className="px-4 py-2 border border-gray-300 rounded-md text-sm text-gray-700 hover:bg-gray-50 transition-colors"
							>
								Close
							</button>
						</div>
					</div>
				</div>
			)}
		</div>
	);
};

export default WatchlistReportPage;