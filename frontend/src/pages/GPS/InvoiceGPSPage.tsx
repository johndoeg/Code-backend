import React, { useEffect, useState, useCallback } from 'react';
import api from '../../api/axiosInstance';
import AsOfDatePicker from '../../components/AsOfDatePickerComponent';
import Pagination from '../../helpers/Pagination';
import { DEFAULT_PAGE_LIMIT } from '../../constants/DefaultValue';

const toISO = (d: Date): string => d.toISOString().split('T')[0];

interface InvoiceSummary {
	asof: string;
	disb_month: string;
	tot_kontrak_inv: string;
	tot_kontrak_sys: string;
	vendor: string;
}

interface InvoiceDetail {
	lease_no: string;
	lessee_nm: string;
	execution: string;
	invoice: string;
	system: string;
	remark: string;
}

interface Vendor {
	SUPP: string;
	NICKNAME: string;
}

const InvoiceGPSPage: React.FC = () => {
	const [invoiceSummaries, setInvoiceSummaries] = useState<InvoiceSummary[]>([]);
	const [invoiceDetails, setInvoiceDetails] = useState<InvoiceDetail[]>([]);
	const [vendors, setVendors] = useState<Vendor[]>([]);
	const [selectedVendor, setSelectedVendor] = useState<string>('');
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [page, setPage] = useState(1);
	const [total, setTotal] = useState(0);
	const limit = DEFAULT_PAGE_LIMIT;

	const [detailModalOpen, setDetailModalOpen] = useState(false);
	const [currentInvoiceNo, setCurrentInvoiceNo] = useState('');

	const [uploadModalOpen, setUploadModalOpen] = useState(false);
	const [selectedFile, setSelectedFile] = useState<File | null>(null);
	const [uploadDate, setUploadDate] = useState<Date>(new Date());
	const [uploading, setUploading] = useState(false);

	const fetchVendors = useCallback(async () => {
		try {
			const res = await api.get('/GPS/api/invoice/vendors');
			if (Array.isArray(res.data) && res.data.length > 0) {
				setVendors(res.data);
				setSelectedVendor(res.data[0].SUPP);
			} else {
				setVendors([]);
			}
		} catch {
			setError('Failed to load vendor list. Please try again.');
		}
	}, []);

	const fetchInvoiceSummaries = useCallback(async () => {
		if (!selectedVendor) return;
		setLoading(true);
		setError(null);
		try {
			const res = await api.get('/GPS/api/invoice', {
				params: { vendor: selectedVendor, page, limit },
			});
			if (res.data?.data && res.data.total !== undefined) {
				setInvoiceSummaries(res.data.data);
				setTotal(res.data.total);
			} else {
				setInvoiceSummaries([]);
				setTotal(0);
			}
		} catch {
			setError('Failed to load invoice data. Please try again.');
		} finally {
			setLoading(false);
		}
	}, [selectedVendor, page, limit]);

	const fetchInvoiceDetails = useCallback(async (invoiceNo: string) => {
		try {
			const res = await api.get('/GPS/api/invoice/detail', {
				params: { asof: invoiceNo, vendor: selectedVendor },
			});
			if (res.data?.data) {
				setInvoiceDetails(res.data.data);
				setCurrentInvoiceNo(invoiceNo);
				setDetailModalOpen(true);
			} else {
				setInvoiceDetails([]);
				setError('No details found for this invoice.');
			}
		} catch {
			setError('Failed to load invoice details. Please try again.');
		}
	}, [selectedVendor]);

	useEffect(() => { fetchVendors(); }, [fetchVendors]);

	useEffect(() => {
		if (selectedVendor) { setPage(1); }
	}, [selectedVendor]);

	useEffect(() => {
		if (selectedVendor) { fetchInvoiceSummaries(); }
	}, [selectedVendor, fetchInvoiceSummaries]);

	const handleVendorChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
		setSelectedVendor(e.target.value);
		setPage(1);
	};

	const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
		if (e.target.files?.[0]) setSelectedFile(e.target.files[0]);
	};

	const clearFile = () => {
		setSelectedFile(null);
		const input = document.getElementById('invoiceGPS') as HTMLInputElement;
		if (input) input.value = '';
	};

	const handleUpload = async (e: React.FormEvent) => {
		e.preventDefault();
		if (!selectedFile || !selectedVendor) return;

		const formData = new FormData();
		formData.append('invoiceGPS', selectedFile);
		formData.append('gps_vendor_upload', selectedVendor);
		formData.append('asof', toISO(uploadDate));

		setUploading(true);
		try {
			const res = await api.post('/GPS/api/invoice/upload', formData, {
				headers: { 'Content-Type': 'multipart/form-data' },
			});
			if (res.data.success) {
				alert(res.data.message || 'File uploaded successfully!');
				setUploadModalOpen(false);
				clearFile();
				fetchInvoiceSummaries();
			} else {
				alert(res.data.error || 'Upload failed. Please try again.');
			}
		} catch {
			alert('Upload failed. Please try again.');
		} finally {
			setUploading(false);
		}
	};

	const getVendorName = (supp: string) =>
		vendors.find(v => v.SUPP === supp)?.NICKNAME ?? '';

	const totalPages = Math.ceil(total / limit);
	const startIndex = (page - 1) * limit + 1;

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-7xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6 mb-6">

					{/* Header */}
					<div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
						<div>
							<h1 className="text-2xl md:text-3xl font-bold text-gray-800">Invoice GPS</h1>
							<p className="text-gray-600 mt-1">View and manage your invoice records</p>
						</div>
						<span className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm font-medium self-start md:self-auto">
							Total: {total}
						</span>
					</div>

					{/* Vendor selector */}
					<div className="mb-6">
						<label htmlFor="gps_vendor" className="block text-sm font-medium text-gray-700 mb-2">
							GPS Vendor:
						</label>
						<select
							id="gps_vendor"
							value={selectedVendor}
							onChange={handleVendorChange}
							className="w-full md:w-auto px-3 py-2 border border-gray-300 rounded-md shadow-sm
							           focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500
							           sm:text-sm"
							style={{ height: '2.2rem' }}
						>
							<option value="" disabled>Select a Vendor…</option>
							{vendors.map(v => (
								<option key={v.SUPP} value={v.SUPP}>{v.NICKNAME}</option>
							))}
						</select>
					</div>

					{/* Error banner */}
					{error && (
						<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 flex items-center gap-2">
							<svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
								<circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
							</svg>
							<span>{error}</span>
							<button
								onClick={() => { setError(null); fetchInvoiceSummaries(); }}
								className="ml-auto text-red-900 underline text-sm"
							>
								Retry
							</button>
						</div>
					)}

					{/* Table */}
					<div className="overflow-x-auto overflow-y-auto rounded-lg border border-gray-200 max-h-[70vh]">
						<table className="w-full">
							<thead className="bg-gradient-to-r from-gray-50 to-gray-100 sticky top-0">
								<tr>
									<th className="py-3 px-4 text-left   text-xs font-medium text-gray-500 uppercase tracking-wider" style={{ width: '5%' }}>No.</th>
									<th className="py-3 px-4 text-left   text-xs font-medium text-gray-500 uppercase tracking-wider" style={{ width: '15%' }}>Disbursement Month</th>
									<th className="py-3 px-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider" style={{ width: '20%' }}>Total Invoice</th>
									<th className="py-3 px-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider" style={{ width: '20%' }}>Total System</th>
									<th className="py-3 px-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider" style={{ width: '10%' }}>
										<button
											onClick={() => setUploadModalOpen(true)}
											disabled={!selectedVendor}
											className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400
											           text-white px-4 py-2 rounded-md text-sm font-medium
											           flex items-center gap-2 transition-colors mx-auto"
										>
											<svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
												<path fillRule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clipRule="evenodd" />
											</svg>
											Upload Invoice
										</button>
									</th>
								</tr>
							</thead>
							<tbody className="divide-y divide-gray-200">
								{loading ? (
									<tr>
										<td colSpan={5} className="py-10 text-center">
											<div className="flex justify-center">
												<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
											</div>
										</td>
									</tr>
								) : invoiceSummaries.length === 0 ? (
									<tr>
										<td colSpan={5} className="py-10 text-center text-gray-500">
											<svg className="w-16 h-16 text-gray-300 mb-3 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
											</svg>
											<p>No invoice records found</p>
										</td>
									</tr>
								) : (
									invoiceSummaries.map((s, idx) => (
										<tr key={s.asof} className={`hover:bg-gray-50 transition-colors ${idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}`}>
											<td className="py-4 px-4 text-sm font-medium text-gray-900 text-center">{startIndex + idx}</td>
											<td className="py-4 px-4 text-sm text-gray-700">{s.disb_month}</td>
											<td className="py-4 px-4 text-sm text-gray-700 text-right">{s.tot_kontrak_inv}</td>
											<td className="py-4 px-4 text-sm text-gray-700 text-right">{s.tot_kontrak_sys}</td>
											<td className="py-4 px-4 text-sm text-center">
												<button
													onClick={() => fetchInvoiceDetails(s.asof)}
													className="bg-red-500 hover:bg-red-600 text-white px-3 py-1 rounded text-sm font-medium transition-colors"
												>
													Detail
												</button>
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

			{/* Upload modal                                                         */}
			{uploadModalOpen && (
				<div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
					<div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl">
						<div className="flex justify-between items-center p-6 border-b">
							<h2 className="text-xl font-bold text-gray-800">
								Upload Invoice{' '}
								<span className="text-blue-600">({getVendorName(selectedVendor)})</span>
							</h2>
							<button onClick={() => { setUploadModalOpen(false); clearFile(); }} className="text-gray-500 hover:text-gray-700">
								<svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
								</svg>
							</button>
						</div>

						<form onSubmit={handleUpload} className="p-6 space-y-5">
							{/* As of date */}
							<AsOfDatePicker
								label="As of"
								value={uploadDate}
								onChange={(date) => { if (date) setUploadDate(date); }}
								required
							/>

							{/* File picker */}
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-2">Select File</label>
								<input
									type="file"
									id="invoiceGPS"
									name="invoiceGPS"
									accept=".xls,.xlsx"
									onChange={handleFileChange}
									className="hidden"
									required
								/>
								<label
									htmlFor="invoiceGPS"
									className="inline-block bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded cursor-pointer transition-colors text-sm font-medium"
								>
									Select Excel File
								</label>
								<div className="mt-2 flex items-center gap-3 flex-wrap">
									<span className="text-sm text-gray-600 italic">
										{selectedFile ? selectedFile.name : 'No file selected'}
									</span>
									{selectedFile && (
										<button type="button" onClick={clearFile} className="text-sm text-red-600 hover:text-red-800 font-medium">
											Clear
										</button>
									)}
								</div>
							</div>

							<div className="flex justify-end gap-3 pt-2">
								<button
									type="button"
									onClick={() => { setUploadModalOpen(false); clearFile(); }}
									className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 text-sm"
								>
									Cancel
								</button>
								<button
									type="submit"
									disabled={!selectedFile || uploading}
									className="px-4 py-2 rounded-md text-white font-medium text-sm flex items-center gap-2
									           bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 disabled:cursor-not-allowed
									           transition-colors"
								>
									{uploading ? (
										<>
											<svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
												<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
												<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
											</svg>
											Uploading…
										</>
									) : 'Upload File'}
								</button>
							</div>
						</form>
					</div>
				</div>
			)}

			{/* Detail modal                                                         */}
			{detailModalOpen && (
				<div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
					<div className="bg-white rounded-2xl shadow-xl w-full max-w-6xl max-h-[90vh] overflow-hidden flex flex-col">
						<div className="flex justify-between items-center p-6 border-b">
							<h2 className="text-xl font-bold text-gray-800">
								Invoice Details — {currentInvoiceNo}
							</h2>
							<button onClick={() => setDetailModalOpen(false)} className="text-gray-500 hover:text-gray-700">
								<svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
								</svg>
							</button>
						</div>

						<div className="overflow-y-auto flex-grow min-h-0">
							<table className="w-full">
								<thead className="bg-gray-50 sticky top-0">
									<tr>
										{['No.', 'Contract No.', 'Customer Name', 'Disbursement Date', 'Invoice', 'System', 'Remark'].map(h => (
											<th key={h} className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
												{h}
											</th>
										))}
									</tr>
								</thead>
								<tbody className="divide-y divide-gray-200">
									{invoiceDetails.length === 0 ? (
										<tr>
											<td colSpan={7} className="py-10 text-center text-gray-500">No details found</td>
										</tr>
									) : (
										invoiceDetails.map((d, idx) => {
											const isAnomalous = d.invoice === 'N' || d.system === 'N';
											return (
												<tr
													key={idx}
													className={isAnomalous
														? 'bg-red-500 text-white hover:opacity-90'
														: 'bg-white hover:bg-gray-50 transition-colors'
													}
												>
													<td className="py-3 px-4 text-sm text-center">{idx + 1}</td>
													<td className="py-3 px-4 text-sm">{d.lease_no}</td>
													<td className="py-3 px-4 text-sm">{d.lessee_nm}</td>
													<td className="py-3 px-4 text-sm text-center">{d.execution}</td>
													<td className="py-3 px-4 text-sm text-center">{d.invoice}</td>
													<td className="py-3 px-4 text-sm text-center">{d.system}</td>
													<td className="py-3 px-4 text-sm">{d.remark}</td>
												</tr>
											);
										})
									)}
								</tbody>
							</table>
						</div>

						<div className="p-4 border-t flex justify-end">
							<button
								onClick={() => setDetailModalOpen(false)}
								className="bg-gray-500 hover:bg-gray-600 text-white px-4 py-2 rounded-md font-medium text-sm transition-colors"
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

export default InvoiceGPSPage;