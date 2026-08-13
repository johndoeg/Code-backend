import React, { useEffect, useState } from 'react';
import api from '../../../../api/axiosInstance';
import AsOfDatePicker from '../../../../components/AsOfDatePickerComponent';

interface BranchOption {
	branch_cd: string;
	branch_name: string;
}

const toISO = (d: Date): string => {
	const year = d.getFullYear();
	const month = String(d.getMonth() + 1).padStart(2, '0');
	const day = String(d.getDate()).padStart(2, '0');
	return `${year}-${month}-${day}`;
};

const AllInsuranceDataPage: React.FC = () => {
	const [branches, setBranches] = useState<BranchOption[]>([]);
	const [searchBy, setSearchBy] = useState('1');
	const [dateFrom, setDateFrom] = useState<Date | null>(null);
	const [dateTo, setDateTo] = useState<Date | null>(null);
	const [branchCd, setBranchCd] = useState('');
	const [exporting, setExporting] = useState(false);

	useEffect(() => {
		(async () => {
			try {
				const res = await api.get<BranchOption[]>('/CAM/Approved/api/all-insurance-data/branches');
				setBranches(res.data);
			} catch (err) {
				console.error('Branch list error:', err);
			}
		})();
	}, []);

	const handleExport = async () => {
		if (!dateFrom || !dateTo) {
			alert('Please fill in both dates');
			return;
		}
		setExporting(true);
		try {
			const response = await api.get('/CAM/Approved/api/all-insurance-data/export', {
				params: {
					search_by: searchBy,
					date_from: toISO(dateFrom),
					date_to: toISO(dateTo),
					branch_cd: branchCd,
				},
				responseType: 'blob',
			});

			const blob = new Blob([response.data], {
				type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
			});
			const url = window.URL.createObjectURL(blob);
			const link = document.createElement('a');
			link.href = url;
			link.download = 'AllInsuranceData.xlsx';
			document.body.appendChild(link);
			link.click();
			document.body.removeChild(link);
			window.URL.revokeObjectURL(url);
		} catch (err) {
			console.error('Export error:', err);
			alert('Failed to export. Please try again.');
		} finally {
			setExporting(false);
		}
	};

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-6xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6">
					<div className="mb-6">
						<h1 className="text-xl md:text-2xl font-bold text-gray-800">All Insurance Data</h1>
					</div>

					<div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4 text-sm items-end">
						<div>
							<label className="text-gray-500 block mb-1">Search By</label>
							<select
								value={searchBy}
								onChange={(e) => setSearchBy(e.target.value)}
								className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
							>
								<option value="1">CAM Create Date</option>
								<option value="2">Disbursement Date</option>
							</select>
						</div>
						<div>
							<label className="text-gray-500 block mb-1">Date From</label>
							<AsOfDatePicker label="" value={dateFrom} onChange={setDateFrom} required />
						</div>
						<div>
							<label className="text-gray-500 block mb-1">Date To</label>
							<AsOfDatePicker label="" value={dateTo} onChange={setDateTo} required />
						</div>
					</div>

					<div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6 text-sm items-end">
						<div>
							<label className="text-gray-500 block mb-1">Branch</label>
							<select
								value={branchCd}
								onChange={(e) => setBranchCd(e.target.value)}
								className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
							>
								<option value="">Select</option>
								{branches.map((b) => (
									<option key={b.branch_cd} value={b.branch_cd}>
										{b.branch_name}
									</option>
								))}
							</select>
						</div>
					</div>

					<button
						onClick={handleExport}
						disabled={exporting}
						className="bg-green-600 hover:bg-green-700 disabled:bg-gray-300 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
					>
						{exporting ? 'Exporting…' : 'Export to Excel'}
					</button>
				</div>
			</div>
		</div>
	);
};

export default AllInsuranceDataPage;