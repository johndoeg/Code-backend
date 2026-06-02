import React, { useState } from 'react';
import DatePicker from 'react-datepicker';
import 'react-datepicker/dist/react-datepicker.css';
import { format } from 'date-fns';

const SipesatPage: React.FC = () => {
	const [period, setPeriod] = useState<Date | null>(null);
	const [isLoading, setIsLoading] = useState(false);

	const API_BASE = import.meta.env.VITE_API_URL;

	const handleExport = () => {
		if (!period) {
			alert('Please select period first');
			return;
		}

		setIsLoading(true);
		const formattedPeriod = format(period, 'MM-yyyy');

		window.open(`${API_BASE}/SIPESAT/api/export/excel?period=${encodeURIComponent(formattedPeriod)}`, '_blank');

		setTimeout(() => setIsLoading(false), 500);
	};

	return (
		<div className="min-h-screen bg-gray-50 py-6 print:bg-white print:py-0">
			<div className="max-w-3xl mx-auto px-4 print:max-w-none print:px-0">

				{/* Main Form Card */}
				<div className="bg-white rounded-lg shadow print:shadow-none print:rounded-none">
					<div className="p-6 print:p-0">

						{/* Title */}
						<h1 className="text-xl font-bold text-gray-800 mb-6 print:text-2xl print:text-center print:mb-8">
							PELAPORAN SIPESAT
						</h1>

						<div className="space-y-6">
							{/* Period Selector */}
							<div className="flex flex-col sm:flex-row sm:items-center gap-4">
								<label className="w-full sm:w-32 text-sm font-medium text-gray-700">
									As Of <span className="text-red-500">*</span>
								</label>
								<div className="flex-1 max-w-xs">
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
									/>
								</div>
							</div>

							{/* Action Button */}
							<div className="no-print flex gap-4 pt-4 border-t border-gray-100">
								<button
									onClick={handleExport}
									disabled={isLoading || !period}
									className={`px-6 py-2.5 rounded-lg font-medium text-white transition-all flex items-center gap-2
                                        ${isLoading || !period
											? 'bg-orange-300 cursor-not-allowed'
											: 'bg-orange-500 hover:bg-orange-600 active:bg-orange-700 shadow-sm hover:shadow'
										}`}
								>
									{isLoading ? (
										<>
											<svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
												<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
												<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
											</svg>
											Generating...
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

				{/* Footer */}
				<div className="no-print mt-6 text-center text-sm text-gray-500">
					<p>SIPESAT Reporting Module • {new Date().getFullYear()}</p>
				</div>

			</div>

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

export default SipesatPage;