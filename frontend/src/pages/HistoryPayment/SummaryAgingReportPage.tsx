import React, { useState, useEffect } from 'react';
import api from '../../api/axiosInstance';
import AsOfDatePicker from '../../components/AsOfDatePickerComponent';

const toISO = (d: Date): string => d.toISOString().split('T')[0];

interface ComboOption {
	value: string;
	label: string;
}

const SummaryAgingReportPage: React.FC = () => {
	const [asof, setAsof] = useState<Date>(new Date());
	const [by, setBy] = useState('0');
	const [excludeJf, setExcludeJf] = useState(false);
	const [byOptions, setByOptions] = useState<ComboOption[]>([]);
	const [loading, setLoading] = useState(false);
	const [comboLoad, setComboLoad] = useState(true);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		api.get('/SummaryAging/api/combo')
			.then(res => setByOptions(res.data ?? []))
			.catch(() => setError('Failed to load filter options.'))
			.finally(() => setComboLoad(false));
	}, []);

	const handleExport = async (type: 'excel' | 'pdf') => {
		if (!asof) { alert('Please select a date first.'); return; }
		if (type === 'pdf' && by !== '0') {
			alert('PDF export is only available for By Branch.');
			return;
		}

		setLoading(true);
		setError(null);

		try {
			const response = await api.get(`/SummaryAging/api/${type}`, {
				params: { asof: toISO(asof), by, cek_jf: excludeJf ? '1' : '0' },
				responseType: 'blob',
			});

			const mimeType = type === 'excel'
				? 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
				: 'application/pdf';
			const blob = new Blob([response.data], { type: mimeType });
			const url = URL.createObjectURL(blob);

			if (type === 'pdf') {
				window.open(url, '_blank');
				setTimeout(() => URL.revokeObjectURL(url), 10_000);
			} else {
				const anchor = document.createElement('a');
				anchor.href = url;
				anchor.download = `SummaryAging_${toISO(asof)}.xlsx`;
				anchor.click();
				URL.revokeObjectURL(url);
			}
		} catch (err) {
			console.error(err);
			setError(`Failed to export ${type.toUpperCase()}. Please try again.`);
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
							Summary Aging Report
						</h1>
						<p className="text-sm text-gray-500 mt-1">Car Financing Only</p>
					</div>

					{/* Filters */}
					<div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-4">
						<AsOfDatePicker value={asof} onChange={setAsof} format="DD MMM YYYY" />
						<div>
							<label className="block text-sm font-medium text-gray-700 mb-1">
								By
							</label>
							<select
								value={by}
								onChange={e => setBy(e.target.value)}
								disabled={comboLoad}
								className="w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm
								           focus:outline-none focus:ring-2 focus:ring-blue-500
								           focus:border-blue-500 disabled:bg-gray-100"
							>
								{byOptions.map(o => (
									<option key={o.value} value={o.value}>{o.label}</option>
								))}
							</select>
						</div>
					</div>

					{/* Exclude JF checkbox */}
					<div className="mb-6">
						<label className="flex items-center gap-2 cursor-pointer w-fit">
							<input
								type="checkbox"
								checked={excludeJf}
								onChange={e => setExcludeJf(e.target.checked)}
								className="w-4 h-4 accent-blue-600"
							/>
							<span className="text-sm text-gray-700">Exclude JF Portion</span>
						</label>
					</div>

					{/* Error banner */}
					{error && (
						<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
							{error}
						</div>
					)}

					{/* Action buttons */}
					<div className="flex flex-wrap gap-2">
						<button
							onClick={() => handleExport('excel')}
							disabled={loading}
							className="bg-gradient-to-r from-green-600 to-emerald-700
							           hover:from-green-700 hover:to-emerald-800
							           text-white px-4 py-2 text-sm rounded-lg font-medium
							           shadow-md hover:shadow-lg transition-all disabled:opacity-60"
						>
							{loading ? 'Exporting…' : 'Export to Excel'}
						</button>

						<button
							onClick={() => handleExport('pdf')}
							disabled={loading || by !== '0'}
							title={by !== '0' ? 'PDF is only available for By Branch' : ''}
							className="bg-gradient-to-r from-red-600 to-rose-700
							           hover:from-red-700 hover:to-rose-800
							           text-white px-4 py-2 text-sm rounded-lg font-medium
							           shadow-md hover:shadow-lg transition-all disabled:opacity-60"
						>
							Export to PDF
						</button>
					</div>

				</div>
			</div>
		</div>
	);
};

export default SummaryAgingReportPage;