import React, { useEffect, useState, useCallback } from "react";
import api from '../../api/axiosInstance';
import Pagination from "../../helpers/Pagination";
import { DEFAULT_PAGE_LIMIT } from '../../constants/DefaultValue';
import Formatter from "../../helpers/Formatter"

interface InvoiceSummary {
	invoice_no: string;
	disb_month: string;
	tot_kontrak_inv: string;
	tot_biaya_inv: string;
	tot_kontrak_sys: string;
	tot_biaya_sys: string;
}

interface InvoiceDetail {
	lease_no: string;
	lessee_nm: string;
	execution: string;
	batchdt: string;
	totalnett: string;
	gross: string;
	invoice: string;
	system: string;
	remark: string;
}

const DelimaInvoice: React.FC = () => {
	const [invoiceSummaries, setInvoiceSummaries] = useState<InvoiceSummary[]>([]);
	const [invoiceDetails, setInvoiceDetails] = useState<InvoiceDetail[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [detailModalOpen, setDetailModalOpen] = useState(false);
	const [currentInvoiceNo, setCurrentInvoiceNo] = useState("");
	const [page, setPage] = useState(1);
	const limit = DEFAULT_PAGE_LIMIT;
	const [total, setTotal] = useState(0);

	const fetchInvoiceSummaries = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			const response = await api.get('/Delima/api/invoice', {
				params: { page, limit }
			});

			if (response.data && response.data !== 'null') {
				if (response.data.data && response.data.total !== undefined) {
					setInvoiceSummaries(response.data.data);
					setTotal(response.data.total);
				} else {
					setInvoiceSummaries(response.data);
					setTotal(response.data.length);
				}
			} else {
				setInvoiceSummaries([]);
				setTotal(0);
			}
		} catch (err: any) {
			setError('Failed to load invoice data. Please try again.');
			console.error("API Error:", err);
		} finally {
			setLoading(false);
		}
	}, [page, limit]);

	const fetchInvoiceDetails = useCallback(async (invoiceNo: string) => {
		setError(null);
		try {
			const response = await api.get('/Delima/api/invoice/detail', {
				params: { id: invoiceNo }
			});

			if (response.data && response.data !== 'null') {
				setInvoiceDetails(response.data);
				setCurrentInvoiceNo(invoiceNo);
				setDetailModalOpen(true);
			} else {
				setInvoiceDetails([]);
				setDetailModalOpen(true);
			}
		} catch (err: any) {
			setError('Failed to load invoice details. Please try again.');
			console.error("Details API Error:", err);
			setInvoiceDetails([]);
			setDetailModalOpen(true);
		}
	}, []);

	useEffect(() => {
		fetchInvoiceSummaries();
	}, [fetchInvoiceSummaries]);

	const startIndex = (page - 1) * limit;
	const totalPages = Math.ceil(total / limit);

	const handleViewDetail = (invoiceNo: string) => {
		fetchInvoiceDetails(invoiceNo);
	};

	const closeModal = () => {
		setDetailModalOpen(false);
		setError(null);
	};

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-7xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6 mb-6">
					<div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
						<div>
							<h1 className="text-2xl md:text-3xl font-bold text-gray-800">Invoice</h1>
							<p className="text-gray-600 mt-1">View and manage your invoice records</p>
						</div>
						<div className="flex items-center gap-3">
							<span className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm font-medium">
								Total: {total}
							</span>
						</div>
					</div>

					{error && (
						<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
							{error}
							<button
								onClick={fetchInvoiceSummaries}
								className="ml-4 text-red-900 underline"
							>
								Retry
							</button>
						</div>
					)}

					<div className="overflow-x-auto rounded-lg border border-gray-200">
						<table className="w-full">
							<thead className="bg-gradient-to-r from-gray-50 to-gray-100">
								<tr>
									<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" style={{ width: '5%' }}>No.</th>
									<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" style={{ width: '15%' }}>Invoice No.</th>
									<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" style={{ width: '15%' }}>Disbursement Month</th>
									<th colSpan={2} className="py-3 px-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider" style={{ width: '20%' }}>Total Invoice</th>
									<th colSpan={2} className="py-3 px-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider" style={{ width: '20%' }}>Total System</th>
									<th className="py-3 px-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider" style={{ width: '10%' }}></th>
								</tr>
								<tr>
									<th className="py-3 px-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider" style={{ width: '5%' }}></th>
									<th className="py-3 px-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider" style={{ width: '15%' }}></th>
									<th className="py-3 px-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider" style={{ width: '15%' }}></th>
									<th className="py-3 px-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider" style={{ width: '10%' }}>Contract</th>
									<th className="py-3 px-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider" style={{ width: '10%' }}>Amount</th>
									<th className="py-3 px-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider" style={{ width: '10%' }}>Contract</th>
									<th className="py-3 px-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider" style={{ width: '10%' }}>Amount</th>
									<th className="py-3 px-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider" style={{ width: '10%' }}></th>
								</tr>
							</thead>
							<tbody className="divide-y divide-gray-200">
								{loading ? (
									<tr>
										<td colSpan={8} className="py-10 px-6 text-center text-gray-500">
											<div className="flex justify-center">
												<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
											</div>
										</td>
									</tr>
								) : invoiceSummaries.length === 0 ? (
									<tr>
										<td colSpan={8} className="py-10 px-6 text-center text-gray-500">
											<div className="flex flex-col items-center justify-center">
												<svg className="w-16 h-16 text-gray-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
													<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
												</svg>
												<p className="text-lg">No invoice records found</p>
											</div>
										</td>
									</tr>
								) : (
									<>
										{invoiceSummaries.map((summary, index) => (
											<tr
												key={summary.invoice_no}
												className={`hover:bg-gray-50 transition-colors ${index % 2 === 0 ? "bg-white" : "bg-gray-50"}`}
											>
												<td className="py-4 px-4 whitespace-nowrap text-sm font-medium text-gray-900 text-center">
													{startIndex + index + 1}
												</td>
												<td className="py-4 px-4 whitespace-nowrap text-sm text-gray-700 font-medium">{summary.invoice_no}</td>
												<td className="py-4 px-4 whitespace-nowrap text-sm text-gray-700">{summary.disb_month}</td>
												<td className="py-4 px-4 whitespace-nowrap text-sm text-gray-700 text-right">{summary.tot_kontrak_inv}</td>
												<td className="py-4 px-4 whitespace-nowrap text-sm text-gray-700 text-right">{Formatter.formatThousands(summary.tot_biaya_inv)}</td>
												<td className="py-4 px-4 whitespace-nowrap text-sm text-gray-700 text-right">{summary.tot_kontrak_sys}</td>
												<td className="py-4 px-4 whitespace-nowrap text-sm text-gray-700 text-right">{Formatter.formatThousands(summary.tot_biaya_sys)}</td>
												<td className="py-4 px-4 whitespace-nowrap text-sm text-center">
													<button
														onClick={() => handleViewDetail(summary.invoice_no)}
														className="bg-red-500 hover:bg-red-600 text-white px-3 py-1 rounded text-sm font-medium transition-colors"
													>
														Detail
													</button>
												</td>
											</tr>
										))}
									</>
								)}
							</tbody>
						</table>
					</div>

					{/* Use the custom Pagination component */}
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

			{/* Detail Modal */}
			{detailModalOpen && (
				<div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
					<div className="bg-white rounded-2xl shadow-xl w-full max-w-6xl max-h-[90vh] overflow-hidden flex flex-col">
						<div className="flex justify-between items-center p-6 border-b">
							<h2 className="text-xl font-bold text-gray-800">Invoice Details - {currentInvoiceNo}</h2>
							<button
								onClick={closeModal}
								className="text-gray-500 hover:text-gray-700"
							>
								<svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
									<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path>
								</svg>
							</button>
						</div>
						<div className="overflow-y-auto flex-grow min-h-0">
							<table className="w-full">
								<thead className="bg-gray-50 sticky top-0">
									<tr>
										<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" style={{ width: '5%' }}>No.</th>
										<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" style={{ width: '10%' }}>Contract No.</th>
										<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" style={{ width: '15%' }}>Customer Name</th>
										<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" style={{ width: '5%' }}>Disbursement Date</th>
										<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" style={{ width: '5%' }}>Cover Date</th>
										<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" style={{ width: '10%' }}>Fiduciary Fee Invoice</th>
										<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" style={{ width: '10%' }}>Fiduciary Fee System</th>
										<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" style={{ width: '5%' }}>Invoice</th>
										<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" style={{ width: '5%' }}>System</th>
										<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" style={{ width: '30%' }}>Remark</th>
									</tr>
								</thead>
								<tbody className="divide-y divide-gray-200">
									{invoiceDetails.length === 0 ? (
										<tr>
											<td colSpan={10} className="py-10 px-6 text-center text-gray-500">
												<div className="flex flex-col items-center justify-center">
													<svg className="w-16 h-16 text-gray-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
														<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
													</svg>
													<p className="text-lg">No details found</p>
												</div>
											</td>
										</tr>
									) : (
										invoiceDetails.map((detail, index) => (
											<tr
												key={index}
												className={`${detail.invoice === 'N' || detail.system === 'N'
														? 'bg-red-500 text-white'
														: 'bg-white'
													} hover:opacity-90 transition-opacity`}
											>
												<td className="py-3 px-4 whitespace-nowrap text-sm text-center">{index + 1}</td>
												<td className="py-3 px-4 whitespace-nowrap text-sm">{detail.lease_no}</td>
												<td className="py-3 px-4 whitespace-nowrap text-sm">{detail.lessee_nm}</td>
												<td className="py-3 px-4 whitespace-nowrap text-sm text-center">{detail.execution}</td>
												<td className="py-3 px-4 whitespace-nowrap text-sm text-center">{detail.batchdt}</td>
												<td className="py-3 px-4 whitespace-nowrap text-sm text-right">{Formatter.formatThousands(detail.totalnett)}</td>
												<td className="py-3 px-4 whitespace-nowrap text-sm text-right">{Formatter.formatThousands(detail.gross)}</td>
												<td className="py-3 px-4 whitespace-nowrap text-sm text-center">{detail.invoice}</td>
												<td className="py-3 px-4 whitespace-nowrap text-sm text-center">{detail.system}</td>
												<td className="py-3 px-4 whitespace-nowrap text-sm">{detail.remark}</td>
											</tr>
										))
									)}
								</tbody>
							</table>
						</div>
						<div className="p-4 border-t flex justify-end">
							<button
								onClick={closeModal}
								className="bg-gray-500 hover:bg-gray-600 text-white px-4 py-2 rounded-md font-medium transition-colors"
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

export default DelimaInvoice;