import React, { useState, useCallback } from 'react';
import api from '../../api/axiosInstance';
import Pagination from '../../helpers/Pagination';
import { DEFAULT_PAGE_LIMIT } from '../../constants/DefaultValue';

type CertType =
	| 'fidusia'
	| 'roya_fidusia'
	| 'fiducia_not_accepted'
	| 'roya_fiducia_not_accepted'
	| 'fiducia_not_scan'
	| '';

type SearchBy = 'disb_date' | 'bpkb_date' | 'cont_number' | 'cust_name' | '';

interface ContractRow {
	lease_no: string;
	lessee_nm: string;
	date: string;
	has_file: boolean;
}

const SEARCH_BY_OPTIONS: Record<
	'fidusia' | 'roya_fidusia',
	{ value: SearchBy; label: string }[]
> = {
	fidusia: [
		{ value: 'disb_date', label: 'Disbursement Date' },
		{ value: 'cont_number', label: 'Contract Number' },
		{ value: 'cust_name', label: 'Customer Name' },
	],
	roya_fidusia: [
		{ value: 'bpkb_date', label: 'BPKB Release Date' },
		{ value: 'cont_number', label: 'Contract Number' },
		{ value: 'cust_name', label: 'Customer Name' },
	],
};

const PRINT_ONLY_TYPES = new Set([
	'fiducia_not_accepted',
	'roya_fiducia_not_accepted',
	'fiducia_not_scan',
]);

const todayISO = (): string => new Date().toISOString().split('T')[0];

const FiduciaReportPage: React.FC = () => {
	const [certType, setCertType] = useState<CertType>('');
	const [searchBy, setSearchBy] = useState<SearchBy>('');
	const [dateBefore, setDateBefore] = useState('');
	const [dateAfter, setDateAfter] = useState('');
	const [customerName, setCustomerName] = useState('');
	const [asOf, setAsOf] = useState('');

	const [contractRows, setContractRows] = useState<string[]>(['']);

	const [records, setRecords] = useState<ContractRow[]>([]);
	const [checked, setChecked] = useState<Set<string>>(new Set());
	const [checkAll, setCheckAll] = useState(false);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const [page, setPage] = useState(1);
	const limit = DEFAULT_PAGE_LIMIT;

	const isPrintOnly = PRINT_ONLY_TYPES.has(certType);
	const isTableMode = certType === 'fidusia' || certType === 'roya_fidusia';
	const showDateRange = isTableMode && (searchBy === 'disb_date' || searchBy === 'bpkb_date');
	const showCustName = isTableMode && searchBy === 'cust_name';
	const showContNum = isTableMode && searchBy === 'cont_number';
	const showAsOf = isPrintOnly;

	const dateHeader = certType === 'roya_fidusia' ? 'BPKB Release Date' : 'Disbursement Date';

	const pagedRecords = records.slice((page - 1) * limit, page * limit);
	const totalPages = Math.ceil(records.length / limit);

	const handleCertTypeChange = (value: CertType) => {
		setCertType(value);
		setSearchBy('');
		setRecords([]);
		setChecked(new Set());
		setCheckAll(false);
		setError(null);
		setContractRows(['']);
		setPage(1);

		if (PRINT_ONLY_TYPES.has(value)) setAsOf(todayISO());
		else setAsOf('');
	};

	const handleSearchByChange = (value: SearchBy) => {
		setSearchBy(value);
		setRecords([]);
		setChecked(new Set());
		setCheckAll(false);
		setContractRows(['']);
		setPage(1);
	};

	const handleCancel = () => {
		setCertType('');
		setSearchBy('');
		setDateBefore('');
		setDateAfter('');
		setCustomerName('');
		setAsOf('');
		setRecords([]);
		setChecked(new Set());
		setCheckAll(false);
		setError(null);
		setContractRows(['']);
		setPage(1);
	};

	const fetchData = useCallback(async (leaseNo = '') => {
		if (!certType) { alert('Please select a Certificate Type'); return; }
		if (isPrintOnly) { handlePrint(); return; }
		if (!searchBy) { alert('Please select a Search By option'); return; }

		setLoading(true);
		setError(null);

		try {
			const res = await api.post('/FiduciaReport/api/fiducia-data', {
				cert_type: certType,
				search_by: searchBy,
				lease_no: leaseNo,
				lessee_nm: customerName,
				date_before: dateBefore,
				date_after: dateAfter,
			});

			const raw = res.data?.data ?? [];

			const normalised: ContractRow[] = raw.map((r: Record<string, string | boolean>) => ({
				lease_no: r.lease_no as string,
				lessee_nm: r.lessee_nm as string,
				date: (r.DisbDate ?? r.ReleaseDate ?? '') as string,
				has_file: !!(r.has_certificate ?? r.has_file),
			}));

			setRecords(normalised);
			setChecked(new Set());
			setCheckAll(false);
			setPage(1);

			if (normalised.length === 0) {
				alert('Data Not Found!');
			}
		} catch (err) {
			console.error(err);
			setError('Failed to load data. Please try again.');
			setRecords([]);
		} finally {
			setLoading(false);
		}
	}, [certType, searchBy, customerName, dateBefore, dateAfter, isPrintOnly]);

	const handleSearch = () => fetchData();

	const handleContractKeyPress = async (
		e: React.KeyboardEvent<HTMLInputElement>,
		idx: number
	) => {
		if (e.key !== 'Enter') return;
		const leaseNo = contractRows[idx];
		if (leaseNo.length <= 10) return;

		setLoading(true);
		try {
			const res = await api.post('/FiduciaReport/api/fiducia-data', {
				cert_type: certType,
				search_by: '',
				lease_no: leaseNo,
				lessee_nm: '',
				date_before: '',
				date_after: '',
			});

			const raw = res.data?.data ?? [];
			if (!raw.length) { alert('Data Not Found!'); return; }

			const hit = raw[0];
			const newRecord: ContractRow = {
				lease_no: hit.lease_no,
				lessee_nm: hit.lessee_nm,
				date: hit.DisbDate ?? hit.ReleaseDate ?? '',
				has_file: !!(hit.has_certificate ?? hit.has_file),
			};

			setRecords(prev => {
				const next = [...prev];
				next[idx] = newRecord;
				return next;
			});

			setContractRows(prev => {
				const next = [...prev];
				if (idx === prev.length - 1) next.push('');
				return next;
			});
		} catch {
			alert('Data Not Found!');
		} finally {
			setLoading(false);
		}
	};

	const handleViewFile = async (leaseNo: string) => {
		try {
			const response = await api.get('/FiduciaReport/api/fiducia-file', {
				params: { lease_no: leaseNo, trans_type: certType },
				responseType: 'blob',
			});
			const blob = new Blob([response.data], { type: 'application/pdf' });
			const url = URL.createObjectURL(blob);
			window.open(url, '_blank');

			setTimeout(() => URL.revokeObjectURL(url), 10_000);
		} catch (err) {
			console.error('View file error:', err);
			alert('Failed to load the file. Please try again.');
		}
	};

	const handleDownload = async () => {
		if (!checked.size) {
			alert('Please select at least one contract!');
			return;
		}
		const leaseList = Array.from(checked).join(',');
		const isMultiple = checked.size > 1;

		try {
			const response = await api.get('/FiduciaReport/api/fiducia-file', {
				params: { lease_no: leaseList, trans_type: certType },
				responseType: 'blob',
			});

			const mimeType = isMultiple ? 'application/zip' : 'application/pdf';
			const fileName = isMultiple
				? `download_${certType}_pdf.zip`
				: `${certType}_${leaseList}.pdf`;

			const blob = new Blob([response.data], { type: mimeType });
			const url = URL.createObjectURL(blob);

			const anchor = document.createElement('a');
			anchor.href = url;
			anchor.download = fileName;
			anchor.click();
			URL.revokeObjectURL(url);
		} catch (err) {
			console.error('Download error:', err);
			alert('Failed to download the file. Please try again.');
		}
	};

	const handlePrint = async () => {
		if (!certType || !asOf) { alert('Please fill in all fields'); return; }
		try {
			const response = await api.get('/FiduciaReport/api/fiducia-print', {
				params: { cert_type: certType, asof: asOf },
				responseType: 'blob',
			});
			const blob = new Blob([response.data], { type: 'application/pdf' });
			const url = URL.createObjectURL(blob);
			window.open(url, '_blank');
			setTimeout(() => URL.revokeObjectURL(url), 10_000);
		} catch (err) {
			console.error('Print error:', err);
			alert('Failed to open the report. Please try again.');
		}
	};

	const toggleRow = (leaseNo: string) => {
		setChecked(prev => {
			const next = new Set(prev);
			next.has(leaseNo) ? next.delete(leaseNo) : next.add(leaseNo);
			return next;
		});
	};

	const toggleAll = () => {
		if (checkAll) {
			setChecked(new Set());
		} else {
			setChecked(new Set(records.filter(r => r.has_file).map(r => r.lease_no)));
		}
		setCheckAll(prev => !prev);
	};

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-7xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6 mb-6">

					{/* Header */}
					<div className="mb-6">
						<h1 className="text-2xl md:text-3xl font-bold text-gray-800">
							Fiducia Report
						</h1>
					</div>

					{/* ── Filters ── */}
					<div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-4">

						{/* Certificate Type */}
						<div>
							<label className="block text-sm font-medium text-gray-700 mb-1">
								Certificate Type
							</label>
							<select
								value={certType}
								onChange={e => handleCertTypeChange(e.target.value as CertType)}
								className="w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
							>
								<option value="">Select an option</option>
								<option value="fidusia">Fidusia</option>
								<option value="roya_fidusia">Roya Fidusia</option>
								<option value="fiducia_not_accepted">Fidusia Belum Diterima</option>
								<option value="roya_fiducia_not_accepted">Roya Fidusia Belum Diterima</option>
								<option value="fiducia_not_scan">List Fidusia Belum Di Scan</option>
							</select>
						</div>

						{/* Search By (only for fidusia / roya_fidusia) */}
						{isTableMode && (
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">
									Search By
								</label>
								<select
									value={searchBy}
									onChange={e => handleSearchByChange(e.target.value as SearchBy)}
									className="w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
								>
									<option value="">Select an option</option>
									{SEARCH_BY_OPTIONS[certType as 'fidusia' | 'roya_fidusia'].map(o => (
										<option key={o.value} value={o.value}>{o.label}</option>
									))}
								</select>
							</div>
						)}
					</div>

					{/* Date Range */}
					{showDateRange && (
						<div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">
									Date From
								</label>
								<input
									type="date"
									value={dateBefore}
									onChange={e => setDateBefore(e.target.value)}
									className="w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
								/>
							</div>
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">
									Date To
								</label>
								<input
									type="date"
									value={dateAfter}
									onChange={e => setDateAfter(e.target.value)}
									className="w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
								/>
							</div>
						</div>
					)}

					{/* Customer Name */}
					{showCustName && (
						<div className="mb-4">
							<label className="block text-sm font-medium text-gray-700 mb-1">
								Customer Name
							</label>
							<input
								type="text"
								value={customerName}
								onChange={e => setCustomerName(e.target.value)}
								onKeyPress={e => { if (e.key === 'Enter') handleSearch(); }}
								maxLength={50}
								className="w-full md:w-1/2 px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
								placeholder="Enter customer name…"
							/>
						</div>
					)}

					{/* As Of (print-only types) */}
					{showAsOf && (
						<div className="mb-4">
							<label className="block text-sm font-medium text-gray-700 mb-1">
								As Of
							</label>
							<input
								type="date"
								value={asOf}
								onChange={e => setAsOf(e.target.value)}
								className="w-full md:w-1/3 px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
							/>
						</div>
					)}

					{/* Action Buttons */}
					<div className="flex flex-wrap gap-2 mb-6">
						<button
							onClick={handleCancel}
							className="bg-gradient-to-r from-gray-400 to-gray-500 hover:from-gray-500 hover:to-gray-600 text-white px-4 py-2 text-sm rounded-lg font-medium shadow-md hover:shadow-lg transition-all"
						>
							Cancel
						</button>
						<button
							onClick={handleSearch}
							disabled={loading}
							className="bg-gradient-to-r from-blue-600 to-indigo-700 hover:from-blue-700 hover:to-indigo-800 text-white px-4 py-2 text-sm rounded-lg font-medium shadow-md hover:shadow-lg transition-all disabled:opacity-60"
						>
							{loading ? 'Searching…' : 'Search'}
						</button>
						{isTableMode && (
							<button
								onClick={handleDownload}
								className="bg-gradient-to-r from-green-600 to-emerald-700 hover:from-green-700 hover:to-emerald-800 text-white px-4 py-2 text-sm rounded-lg font-medium shadow-md hover:shadow-lg transition-all"
							>
								Download
							</button>
						)}
					</div>

					{/* Error Banner */}
					{error && (
						<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
							{error}
						</div>
					)}

					{/* ── Table (only for fidusia / roya_fidusia) ── */}
					{isTableMode && (
						<>
							<div className="overflow-x-auto rounded-lg border border-gray-200">
								<table className="w-full">
									<thead className="bg-gradient-to-r from-gray-50 to-gray-100">
										<tr>
											<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-12">No.</th>
											<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Contract No.</th>
											<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Customer Name</th>
											<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{dateHeader}</th>
											<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Action</th>
											<th className="py-3 px-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
												<div className="flex items-center justify-center gap-2">
													Select All
													<input
														type="checkbox"
														checked={checkAll}
														onChange={toggleAll}
														className="w-4 h-4 accent-blue-600"
													/>
												</div>
											</th>
										</tr>
									</thead>

									<tbody className="divide-y divide-gray-200">
										{/* Contract-number input rows */}
										{showContNum && contractRows.map((val, idx) => (
											<tr key={`input-${idx}`} className={idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
												<td className="py-3 px-4 text-sm text-center text-gray-700">{idx + 1}</td>
												<td className="py-3 px-4">
													<input
														type="text"
														value={val}
														maxLength={15}
														onChange={e => {
															const next = [...contractRows];
															next[idx] = e.target.value;
															setContractRows(next);
														}}
														onKeyPress={e => handleContractKeyPress(e, idx)}
														className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
														placeholder="Enter contract no. & press Enter…"
													/>
												</td>
												<td className="py-3 px-4 text-sm text-gray-700">
													{records[idx]?.lessee_nm ?? ''}
												</td>
												<td className="py-3 px-4 text-sm text-gray-700">
													{records[idx]?.date ?? ''}
												</td>
												<td className="py-3 px-4">
													{records[idx]?.has_file && (
														<button
															onClick={() => handleViewFile(records[idx].lease_no)}
															className="bg-cyan-500 hover:bg-cyan-600 text-white px-3 py-1 rounded text-xs font-medium transition-colors"
														>
															View
														</button>
													)}
												</td>
												<td className="py-3 px-4 text-center">
													{records[idx]?.has_file && (
														<input
															type="checkbox"
															checked={checked.has(records[idx].lease_no)}
															onChange={() => toggleRow(records[idx].lease_no)}
															className="w-4 h-4 accent-blue-600"
														/>
													)}
												</td>
											</tr>
										))}

										{/* Normal search result rows */}
										{!showContNum && pagedRecords.length === 0 && !loading && (
											<tr>
												<td colSpan={6} className="py-10 px-4 text-center text-gray-500">
													<div className="flex flex-col items-center justify-center">
														<svg className="w-16 h-16 text-gray-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
															<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
																d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
														</svg>
														<p className="text-lg">No records found</p>
														<p className="text-sm mt-1">Select options and click Search</p>
													</div>
												</td>
											</tr>
										)}

										{!showContNum && pagedRecords.map((record, idx) => (
											<tr
												key={record.lease_no}
												className={`hover:bg-gray-50 transition-colors ${(page - 1) * limit + idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}`}
											>
												<td className="py-3 px-4 text-sm text-center text-gray-700">
													{(page - 1) * limit + idx + 1}
												</td>
												<td className="py-3 px-4 text-sm font-medium text-gray-900 font-mono whitespace-nowrap">
													{record.lease_no}
												</td>
												<td className="py-3 px-4 text-sm text-gray-700 whitespace-nowrap">
													{record.lessee_nm}
												</td>
												<td className="py-3 px-4 text-sm text-gray-700 whitespace-nowrap">
													{record.date || '-'}
												</td>
												<td className="py-3 px-4">
													{record.has_file && (
														<button
															onClick={() => handleViewFile(record.lease_no)}
															className="bg-cyan-500 hover:bg-cyan-600 text-white px-3 py-1 rounded text-xs font-medium transition-colors"
														>
															View
														</button>
													)}
												</td>
												<td className="py-3 px-4 text-center">
													{record.has_file && (
														<input
															type="checkbox"
															checked={checked.has(record.lease_no)}
															onChange={() => toggleRow(record.lease_no)}
															className="w-4 h-4 accent-blue-600"
														/>
													)}
												</td>
											</tr>
										))}

										{loading && (
											<tr>
												<td colSpan={6} className="py-4 px-4 text-center">
													<div className="flex justify-center">
														<svg className="animate-spin h-6 w-6 text-blue-600" fill="none" viewBox="0 0 24 24">
															<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
															<path className="opacity-75" fill="currentColor"
																d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
														</svg>
													</div>
												</td>
											</tr>
										)}
									</tbody>
								</table>
							</div>

							{/* Pagination */}
							{!loading && !showContNum && records.length > 0 && (
								<Pagination
									page={page}
									totalPages={totalPages}
									onPageChange={setPage}
									totalItems={records.length}
									itemsPerPage={limit}
									className="mt-6"
								/>
							)}
						</>
					)}
				</div>
			</div>
		</div>
	);
};

export default FiduciaReportPage;