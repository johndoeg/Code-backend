import React, { useState, useEffect, useCallback } from 'react';
import api from "../../../api/axiosInstance";
import { DEFAULT_PAGE_LIMIT } from "../../../constants/DefaultValue"
import Pagination from '../../../helpers/Pagination';

interface Branch {
	branchCd: string;
	cityName: string;
	branchName: string;
}

interface SalesRecord {
	no: number;
	salesNo: string;
	name: string;
	address: string;
	accNo: string;
	bankName: string;
	bankBranch: string;
	npwpNo: string;
	status: string;
}

const ListOfSalesPage: React.FC = () => {
	const [branches, setBranches] = useState<Branch[]>([]);
	const [selectedBranch, setSelectedBranch] = useState<string>('');
	const [records, setRecords] = useState<SalesRecord[]>([]);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [page, setPage] = useState(1);
	const [total, setTotal] = useState(0);
	const limit = DEFAULT_PAGE_LIMIT;

	useEffect(() => {
		const fetchBranches = async () => {
			try {
				const response = await api.get(`/MasterData/api/branches`);
				setBranches(response.data);
			} catch (err) {
				console.error('Failed to load branches:', err);
				setError('Failed to load branch list');
			}
		};
		fetchBranches();
	}, []);

	const fetchSalesRecords = useCallback(async () => {
		if (!selectedBranch) {
			setRecords([]);
			setTotal(0);
			return;
		}

		setLoading(true);
		setError(null);
		try {
			const response = await api.get(`/MasterData/api/sales-list`, {
				params: {
					branch_cd: selectedBranch,
					page,
					limit
				},
			});

			setRecords(response.data.data || []);
			setTotal(response.data.total || 0);
		} catch (err) {
			if (err) return;
			console.error('Failed to load sales records:', err);
			setError('Failed to load sales records. Please try again.');
			setRecords([]);
			setTotal(0);
		} finally {
			setLoading(false);
		}
	}, [selectedBranch, page, limit]);

	useEffect(() => {
		fetchSalesRecords();
	}, [fetchSalesRecords]);

	const handlePreview = () => {
		if (!selectedBranch.trim()) {
			alert('Please select a branch');
			return;
		}
		setPage(1);
		fetchSalesRecords();
	};

	const handleKeyPress = (e: React.KeyboardEvent) => {
		if (e.key === 'Enter') handlePreview();
	};

	const handlePrint = () => {
		if (!selectedBranch.trim()) {
			alert('Please select a branch');
			return;
		}
		window.open(`/MasterData/api/sales-list/print?branch_cd=${selectedBranch}`, '_blank');
	};

	const handleExportExcel = () => {
		if (!selectedBranch.trim()) {
			alert('Please select a branch');
			return;
		}
		window.open(`/MasterData/api/sales-list/excel?branch_cd=${selectedBranch}`, '_blank');
	};

	const totalPages = Math.ceil(total / limit);

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-7xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6 mb-6">
					<div className="mb-6">
						<h1 className="text-2xl md:text-3xl font-bold text-gray-800">List of Sales</h1>
					</div>

					{/* Branch Selection */}
					<div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
						<div>
							<label htmlFor="branch_cd" className="block text-sm font-medium text-gray-700 mb-1">
								Branch
							</label>
							<select
								id="branch_cd"
								value={selectedBranch}
								onChange={(e) => setSelectedBranch(e.target.value)}
								className="w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
							>
								<option value="">Select</option>
								{branches.map((branch) => (
									<option key={branch.branchCd} value={branch.branchCd}>
										{branch.branchName}
									</option>
								))}
							</select>
						</div>

						<div className="flex flex-wrap gap-2">
							<button
								onClick={handlePreview}
								className="bg-gradient-to-r from-blue-600 to-indigo-700 hover:from-blue-700 hover:to-indigo-800 text-white px-4 py-1 text-sm rounded-lg font-medium shadow-md hover:shadow-lg transition-all"
							>
								Preview
							</button>
							<button
								onClick={handlePrint}
								className="bg-gradient-to-r from-gray-600 to-gray-700 hover:from-gray-700 hover:to-gray-800 text-white px-4 py-1 text-sm rounded-lg font-medium shadow-md hover:shadow-lg transition-all"
							>
								Print
							</button>
							<button
								onClick={handleExportExcel}
								className="bg-gradient-to-r from-green-600 to-emerald-700 hover:from-green-700 hover:to-emerald-800 text-white px-4 py-1 text-sm rounded-lg font-medium shadow-md hover:shadow-lg transition-all"
							>
								Export to Excel
							</button>
						</div>
					</div>

					{error && (
						<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
							{error}
						</div>
					)}

					{/* Results Table */}
					<div className="overflow-x-auto rounded-lg border border-gray-200">
						<table className="w-full">
							<thead className="bg-gradient-to-r from-gray-50 to-gray-100">
								<tr>
									<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-12">No.</th>
									<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Sales No.</th>
									<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
									<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Address</th>
									<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Acc No.</th>
									<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Bank</th>
									<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Bank Branch</th>
									<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">NPWP</th>
									<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
								</tr>
							</thead>
							<tbody className="divide-y divide-gray-200">
								{records.length === 0 && !loading ? (
									<tr>
										<td colSpan={9} className="py-10 px-4 text-center text-gray-500">
											<div className="flex flex-col items-center justify-center">
												<svg className="w-16 h-16 text-gray-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
													<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
												</svg>
												<p className="text-lg">No sales records found</p>
												<p className="text-sm mt-1">Select a branch and click Preview</p>
											</div>
										</td>
									</tr>
								) : (
									<>
										{records.map((record) => (
											<tr
												key={record.salesNo}
												className={`hover:bg-gray-50 transition-colors ${record.no % 2 === 0 ? "bg-white" : "bg-gray-50"
													}`}
											>
												<td className="py-3 px-4 whitespace-nowrap text-sm text-center text-gray-700">{record.no}</td>
												<td className="py-3 px-4 whitespace-nowrap text-sm font-medium text-gray-900">{record.salesNo}</td>
												<td className="py-3 px-4 whitespace-nowrap text-sm text-gray-700">{record.name}</td>
												<td className="py-3 px-4 whitespace-nowrap text-sm text-gray-700 max-w-xs break-words">
													{record.address || '-'}
												</td>
												<td className="py-3 px-4 whitespace-nowrap text-sm text-gray-700 font-mono">{record.accNo || '-'}</td>
												<td className="py-3 px-4 whitespace-nowrap text-sm text-gray-700">{record.bankName || '-'}</td>
												<td className="py-3 px-4 whitespace-nowrap text-sm text-gray-700">{record.bankBranch || '-'}</td>
												<td className="py-3 px-4 whitespace-nowrap text-sm text-gray-700 font-mono">{record.npwpNo || '-'}</td>
												<td className="py-3 px-4 whitespace-nowrap text-sm">
													<span className={`px-2 py-1 rounded-full text-xs font-medium ${record.status === 'Active'
															? 'bg-green-100 text-green-800'
															: 'bg-red-100 text-red-800'
														}`}>
														{record.status}
													</span>
												</td>
											</tr>
										))}
										{loading && (
											<tr>
												<td colSpan={9} className="py-4 px-4 text-center">
													<div className="flex justify-center">
														<svg className="animate-spin h-6 w-6 text-blue-600" fill="none" viewBox="0 0 24 24">
															<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
															<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
														</svg>
													</div>
												</td>
											</tr>
										)}
									</>
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
		</div>
	);
};

export default ListOfSalesPage;