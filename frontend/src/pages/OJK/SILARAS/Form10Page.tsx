import React, { useState } from 'react';
import api from '../../../api/axiosInstance';
import AsOfDatePicker from '../../../components/AsOfDatePickerComponent';

const toISO = (d: Date): string => d.toISOString().split('T')[0];

const Form10Page: React.FC = () => {
	const [dateFrom, setDateFrom] = useState<Date>(new Date());
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const handleExportExcel = async () => {
		setLoading(true);
		setError(null);

		try {
			const response = await api.get('/Form10/api/excel', {
				params: { date_from: toISO(dateFrom) },
				responseType: 'blob',
			});

			const blob = new Blob([response.data], {
				type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
			});
			const url = URL.createObjectURL(blob);
			const anchor = document.createElement('a');
			anchor.href = url;
			anchor.download = `Form_10_${toISO(dateFrom)}.xlsx`;
			anchor.click();
			URL.revokeObjectURL(url);
		} catch (err) {
			console.error('Export error:', err);
			setError('Failed to export. Please try again.');
		} finally {
			setLoading(false);
		}
	};

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-7xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6 mb-6">

					{/* Header */}
					<div className="mb-6">
						<h1 className="text-2xl md:text-3xl font-bold text-gray-800">
							Form 10
						</h1>
					</div>

					{/* Filters */}
					<div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
						<AsOfDatePicker
							label="As of"
							value={dateFrom}
							onChange={(date) => { if (date) setDateFrom(date); }}
							required
						/>
					</div>

					{/* Error banner */}
					{error && (
						<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
							{error}
						</div>
					)}

					{/* Action */}
					<div className="flex flex-wrap gap-2">
						<button
							onClick={handleExportExcel}
							disabled={loading}
							className="bg-gradient-to-r from-green-600 to-emerald-700
							           hover:from-green-700 hover:to-emerald-800
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
									Exporting…
								</>
							) : (
								'Export to Excel'
							)}
						</button>
					</div>

				</div>
			</div>
		</div>
	);
};

export default Form10Page;