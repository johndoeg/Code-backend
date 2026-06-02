import React, { useState } from 'react';
import axios from "axios";
import DatePicker from 'react-datepicker';
import 'react-datepicker/dist/react-datepicker.css';
import { format } from 'date-fns';

interface SegmentOption {
	value: string;
	label: string;
}

interface ModalState {
	isOpen: boolean;
	type: 'available' | 'nodata' | null;
	isLoading: boolean;
}

const SEGMENTS: SegmentOption[] = [
	{ value: 'D01', label: 'D01 - Debitur Perseorangan' },
	{ value: 'D02', label: 'D02 - Debitur Badan Usaha' },
	{ value: 'F01', label: 'F01 - Fasilitas Kredit atau Pembiayaan' },
	{ value: 'A01', label: 'A01 - Agunan' },
	{ value: 'P01', label: 'P01 - Penjamin' },
	{ value: 'M01', label: 'M01 - Pengurus dan/atau Pemilik Debitur Badan Usaha' },
	{ value: 'All', label: 'All Segments' },
];

const REPORT_MAP: Record<string, string> = {
	D01: 'rpt_slik_d01',
	D02: 'rpt_slik_d02',
	F01: 'rpt_slik_f01',
	A01: 'rpt_slik_a01',
	P01: 'rpt_slik_p01',
	M01: 'rpt_slik_m01',
};

const SlikReportingPage: React.FC = () => {
	const [period, setPeriod] = useState<Date | null>(null);
	const [segment, setSegment] = useState('D01');
	const [modal, setModal] = useState<ModalState>({
		isOpen: false,
		type: null,
		isLoading: false,
	});

	const API_URL = import.meta.env.VITE_API_URL;
	const formatPeriod = (date: Date | null): string => date ? format(date, 'MM-yyyy') : '';

	// const handleCheckData = async () => {
	// 	if (!period) {
	// 		alert('Please select period first');
	// 		return;
	// 	}

	// 	setModal(prev => ({ ...prev, isLoading: true }));
		
	// 	try {
	// 		const response = await axios.post(`${API_URL}/SLIK/api/slik-backend`, {
	// 			addmode: 1,
	// 			segment,
	// 			period: formatPeriod(period),
	// 	});

	// 	const hasData = response.data?.[0]?.data === true || response.data?.data === true;
	// 	setModal({
	// 			isOpen: true,
	// 			type: hasData ? 'available' : 'nodata',
	// 			isLoading: false,
	// 	});
		
	// 	} catch (error: any) {
	// 		console.error('Check data failed:', error);
	// 		alert('Failed to check data availability');
	// 		setModal(prev => ({ ...prev, isLoading: false }));
	// 	}
	// };
	// In SlikReportingPage.tsx - Update handleCheckData and handleReprocess

	const handleCheckData = async () => {
		if (!period) {
			alert('Please select period first');
			return;
		}

		setModal(prev => ({ ...prev, isLoading: true }));
	
		try {
			const formData = new URLSearchParams();
			formData.append('addmode', '1');
			formData.append('segment', segment);
			formData.append('period', formatPeriod(period));
			
			const response = await axios.post(`${API_URL}/SLIK/api/slik-backend`, formData, {
				headers: {
					'Content-Type': 'application/x-www-form-urlencoded',
				},
			});

			const hasData = response.data?.[0]?.data === true || response.data?.data === true;
				setModal({
					isOpen: true,
					type: hasData ? 'available' : 'nodata',
					isLoading: false,
				});
			
		} catch (error: any) {
			console.error('Check data failed:', error);
			alert('Failed to check data availability');
			setModal(prev => ({ ...prev, isLoading: false }));
		}
	};

	const handleReprocess = async () => {
		if (!period) return;
		
		setModal(prev => ({ ...prev, isLoading: true }));
		
		try {
			const formData = new URLSearchParams();
			formData.append('addmode', '2');
			formData.append('segment', segment);
			formData.append('period', formatPeriod(period));
			
			const response = await axios.post(`${API_URL}/SLIK/api/slik-backend`, formData, {
				headers: {
					'Content-Type': 'application/x-www-form-urlencoded',
				},
			});

			const isSuccess = Array.isArray(response.data) && response.data.length === 0;
			
			if (isSuccess) {
				handleExport();
				setModal({ isOpen: false, type: null, isLoading: false });
			} else {
				alert('There is error during process, please reprocess again!');
				setModal(prev => ({ ...prev, isLoading: false }));
			}
		} catch (error: any) {
			console.error('Reprocess failed:', error);
			alert('Reprocess failed. Please try again.');
			setModal(prev => ({ ...prev, isLoading: false }));
		}
	};

	// const handleReprocess = async () => {
	// 	if (!period) return;
		
	// 	setModal(prev => ({ ...prev, isLoading: true }));
		
	// 	try {
	// 	const response = await axios.post(`${API_URL}/SLIK/api/slik-backend`, {
	// 		addmode: 2,
	// 		segment,
	// 		period: formatPeriod(period),
	// 	});

	// 	const isSuccess = Array.isArray(response.data) && response.data.length === 0;
		
	// 		if (isSuccess) {
	// 			handleExport();
	// 			setModal({ isOpen: false, type: null, isLoading: false });
	// 		} else {
	// 			alert('There is error during process, please reprocess again!');
	// 			setModal(prev => ({ ...prev, isLoading: false }));
	// 		}
	// 	} catch (error: any) {
	// 		console.error('Reprocess failed:', error);
	// 		alert('Reprocess failed. Please try again.');
	// 		setModal(prev => ({ ...prev, isLoading: false }));
	// 	}
	// };

	const handleExport = () => {
		const p = formatPeriod(period);
		const baseUrl = `${API_URL}/export`;

		if (segment === 'All') {
			let delay = 250;
			Object.values(REPORT_MAP).forEach((report, index) => {
				setTimeout(() => {
					window.open(`${baseUrl}/${report}?period=${encodeURIComponent(p)}`, '_blank');
				}, delay * index);
			});
		} else {
			const reportName = REPORT_MAP[segment];
			if (reportName) {
				window.open(`${baseUrl}/${reportName}?period=${encodeURIComponent(p)}`, '_blank');
			}
		}
	};

	const closeModal = () => {
		setModal({ isOpen: false, type: null, isLoading: false });
	};

	const handleClose = () => {
		if (window.opener) {
			window.close();
		} else {
			window.history.back();
		}
	};

  return (
		<div className="min-h-screen bg-gray-50 py-6 print:bg-white print:py-0">
			<div className="max-w-5xl mx-auto px-4 print:max-w-none print:px-0">
				
				{/* Header */}
				<div className="no-print mb-6">
					<div className="bg-white rounded-lg shadow p-4 flex justify-between items-center">
						<h1 className="text-xl font-bold text-gray-800">Pelaporan SLIK</h1>
						<button
							onClick={handleClose}
							className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
						>
						Close
						</button>
					</div>
				</div>

				{/* Main Form Card */}
				<div className="bg-white rounded-lg shadow print:shadow-none print:rounded-none">
					<div className="p-6 print:p-0">
						{/* Form Title */}
						<div className="print:block hidden mb-6">
							<h1 className="text-2xl font-bold text-center text-gray-800">Pelaporan SLIK</h1>
						</div>

						<div className="space-y-6">
							{/* Period & Segment Grid */}
							<div className="grid grid-cols-1 md:grid-cols-3 gap-6">
								{/* Period Field */}
								<div className="space-y-2">
									<label className="block text-sm font-medium text-gray-700">
										As Of <span className="text-red-500">*</span>
									</label>
									<DatePicker
										selected={period}
										onChange={(date) => setPeriod(date)}
										showMonthYearPicker
										dateFormat="MM/yyyy"
										placeholderText="Select Month & Year"
										className={`w-full px-4 py-3 border rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500 transition-all text-slate-700 placeholder-slate-400
										print:border-none print:p-0 print:bg-transparent print:cursor-default`}
										popperPlacement="bottom-start"
										calendarClassName="rounded-lg shadow-xl border border-gray-200"
										dayClassName={() => "hidden"}
									/>
								</div>

								{/* Segment Field */}
								<div className="space-y-2">
									<label className="block text-sm font-medium text-gray-700">
										Segment
									</label>
									<select
										value={segment}
										onChange={(e) => setSegment(e.target.value)}
										className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500 transition-all bg-white text-slate-700 print:border-none print:p-0 print:bg-transparent"
									>
										{SEGMENTS.map((opt) => (
										<option key={opt.value} value={opt.value}>
											{opt.label}
										</option>
										))}
									</select>
								</div>

								{/* Info Text */}
								<div className="flex items-start h-full pt-1">
									<p className="text-sm text-red-500 italic leading-relaxed print:text-black print:italic">
										*Data yang disajikan merupakan data per akhir bulan dari bulan yang dipilih.
										<br /><br />
										Penarikan data untuk pelaporan dilakukan setiap tanggal 2.
									</p>
								</div>
							</div>

							{/* Action Buttons */}
							<div className="no-print flex flex-wrap gap-4 pt-4 border-t border-gray-100">
								<button
									onClick={handleClose}
									className="px-6 py-2.5 border border-gray-300 rounded-lg font-medium text-gray-700 hover:bg-gray-50 transition-colors"
								>
								Close
								</button>
								<button
									onClick={handleCheckData}
									disabled={modal.isLoading || !period}
									className={`px-6 py-2.5 rounded-lg font-medium text-white transition-all flex items-center gap-2
										${modal.isLoading || !period
										? 'bg-orange-300 cursor-not-allowed'
										: 'bg-orange-500 hover:bg-orange-600 active:bg-orange-700 shadow-sm hover:shadow'
										}`}
									>
									{modal.isLoading ? (
										<>
										<svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
											<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
											<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
										</svg>
										Checking...
										</>
									) : (
										<>
										<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
											d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" 
											/>
										</svg>
										Export to Excel
										</>
									)}
								</button>
							</div>
						</div>
					</div>
				</div>
			</div>

			{/* Modal Dialog */}
			{modal.isOpen && (
			<div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm no-print">
				<div className="bg-white rounded-xl shadow-2xl max-w-md w-full overflow-hidden animate-in fade-in zoom-in duration-200">
					{/* Modal Header */}
					<div className="bg-gradient-to-r from-blue-600 to-indigo-600 px-6 py-4">
						<h3 className="text-white font-bold text-lg">Notification</h3>
					</div>
					
					{/* Modal Body */}
					<div className="p-6">
						<p className="text-gray-700 text-center leading-relaxed">
							{modal.type === 'available' 
							? `Data untuk periode ${formatPeriod(period)} tersedia.`
							: `Data untuk periode ${formatPeriod(period)} tidak tersedia. Silakan diproses ulang!`
							}
						</p>
					</div>

					{/* Modal Footer */}
					<div className="px-6 py-4 bg-gray-50 flex justify-end gap-3">
						{modal.type === 'available' && (
							<button
							onClick={handleReprocess}
							disabled={modal.isLoading}
							className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 disabled:opacity-50 transition-colors font-medium text-sm"
							>
							{modal.isLoading ? 'Processing...' : 'Proses Ulang'}
							</button>
						)}
					
						{modal.type === 'available' && (
							<button
							onClick={handleExport}
							disabled={modal.isLoading}
							className="px-4 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600 disabled:opacity-50 transition-colors font-medium text-sm"
							>
							Export to Excel
							</button>
						)}
					
						{modal.type === 'nodata' && (
							<button
							onClick={handleReprocess}
							disabled={modal.isLoading}
							className="px-4 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600 disabled:opacity-50 transition-colors font-medium text-sm w-full"
							>
							{modal.isLoading ? 'Processing...' : 'Proses Ulang'}
							</button>
						)}
					
						<button
							onClick={closeModal}
							disabled={modal.isLoading}
							className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-100 disabled:opacity-50 transition-colors font-medium text-sm"
						>
							Close
						</button>
					</div>
				</div>
			</div>
		)}

		{/* Print Styles */}
		<style>{`
			@media print {
			.no-print { display: none !important; }
			body { background: white !important; padding: 0 !important; margin: 0 !important; }
			input, select { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
			}
		`}</style>
		</div>
  	);
};

export default SlikReportingPage;