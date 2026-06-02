import React, { useEffect, useState, useCallback } from "react";
import api from '../../api/axiosInstance';

interface VaRecord {
	Lease_No: string;
	Bank: string;
	VA_No: string;
}

interface SearchOption {
	value: string;
	descValue: string;
}

const VAListPage: React.FC = () => {
	const [records, setRecords] = useState<VaRecord[]>([]);
	const [searchOptions, setSearchOptions] = useState<SearchOption[]>([]);
	const [searchBy, setSearchBy] = useState<string>("");
	const [leaseNo, setLeaseNo] = useState<string>("");
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		const fetchOptions = async () => {
			try {
				const response = await api.get('/va/search-options');
				setSearchOptions(response.data);
				if (response.data.length > 0) {
					setSearchBy(response.data[0].value);
				}
			} catch (err) {
				console.error("Failed to load search options:", err);
				setError("Failed to load search options. Please try again.");
			}
		};
		fetchOptions();
	}, []);

	const fetchVaRecords = useCallback(async () => {
		if (!leaseNo.trim()) {
			setRecords([]);
			return;
		}

		if (leaseNo.length > 9) {
			setLoading(true);
			setError(null);
			try {
				const response = await api.get('/va/search', {
					params: {
						lease_no: leaseNo,
						search_by: searchBy
					},
				});

				setRecords(response.data || []);
			} catch (err) {
				if (err) return;
				setError("Failed to load VA records. Please try again.");
				setRecords([]);
			} finally {
				setLoading(false);
			}
		}
	}, [leaseNo, searchBy]);

	useEffect(() => {
		fetchVaRecords();
	}, [fetchVaRecords]);

	const handleSearch = () => {
		fetchVaRecords();
	};

	const handleKeyPress = (e: React.KeyboardEvent) => {
		if (e.key === 'Enter') handleSearch();
	};

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-7xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6 mb-6">
					<div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
						<div>
							<h1 className="text-2xl md:text-3xl font-bold text-gray-800">VA List</h1>
							<p className="text-gray-600 mt-1">View and manage your virtual account records</p>
						</div>
						<div className="flex items-center gap-3">
							<span className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm font-medium">
								Total: {records.length}
							</span>
						</div>
					</div>

					{/* Search Controls */}
					<div className="flex flex-col md:flex-row gap-4 mb-6">
						<div className="w-full md:w-64">
							<select
								id="search_by"
								value={searchBy}
								onChange={(e) => setSearchBy(e.target.value)}
								className="w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
							>
								{searchOptions.map((option) => (
									<option key={option.value} value={option.value}>
										{option.descValue}
									</option>
								))}
							</select>
						</div>

						<div className="flex-1 relative">
							<input
								type="text"
								id="lease_no"
								placeholder="Enter contract number..."
								value={leaseNo}
								onChange={(e) => setLeaseNo(e.target.value)}
								onKeyPress={handleKeyPress}
								className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all"
							/>
							<svg
								className="w-5 h-5 text-gray-400 absolute left-3 top-1/2 transform -translate-y-1/2"
								viewBox="0 0 24 24"
								fill="currentColor"
							>
								<path d="M15.5 14H14.71L14.43 13.73C15.41 12.59 16 11.11 16 9.5C16 5.91 13.09 3 9.5 3C5.91 3 3 5.91 3 9.5C3 13.09 5.91 16 9.5 16C11.11 16 12.59 15.41 13.73 14.43L14 14.71V15.5L19 20.49L20.49 19L15.5 14ZM9.5 14C7.01 14 5 11.99 5 9.5C5 7.01 7.01 5 9.5 5C11.99 5 14 7.01 14 9.5C14 11.99 11.99 14 9.5 14Z" />
							</svg>
						</div>

						<button
							onClick={handleSearch}
							disabled={loading || !leaseNo.trim()}
							className={`bg-gradient-to-r from-blue-600 to-indigo-700 hover:from-blue-700 hover:to-indigo-800 text-white px-6 py-3 rounded-lg font-medium shadow-md hover:shadow-lg transition-all flex items-center justify-center gap-2 ${loading || !leaseNo.trim() ? 'opacity-75 cursor-not-allowed' : ''
								}`}
						>
							{loading ? (
								<>
									<svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
										<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
										<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
									</svg>
									Searching...
								</>
							) : (
								<>
									<svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
										<path d="M15.5 14H14.71L14.43 13.73C15.41 12.59 16 11.11 16 9.5C16 5.91 13.09 3 9.5 3C5.91 3 3 5.91 3 9.5C3 13.09 5.91 16 9.5 16C11.11 16 12.59 15.41 13.73 14.43L14 14.71V15.5L19 20.49L20.49 19L15.5 14ZM9.5 14C7.01 14 5 11.99 5 9.5C5 7.01 7.01 5 9.5 5C11.99 5 14 7.01 14 9.5C14 11.99 11.99 14 9.5 14Z" />
									</svg>
									Search
								</>
							)}
						</button>
					</div>

					{error && (
						<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
							{error}
							<button
								onClick={fetchVaRecords}
								className="ml-4 text-red-900 underline"
							>
								Retry
							</button>
						</div>
					)}

					{/* Table */}
					<div className="overflow-x-auto rounded-lg border border-gray-200">
						<table className="w-full">
							<thead className="bg-gradient-to-r from-gray-50 to-gray-100">
								<tr>
									<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-16">No.</th>
									<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Contract No.</th>
									<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Bank</th>
									<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">VA Number</th>
								</tr>
							</thead>
							<tbody className="divide-y divide-gray-200">
								{records.length === 0 && !loading ? (
									<tr>
										<td colSpan={4} className="py-10 px-6 text-center text-gray-500">
											<div className="flex flex-col items-center justify-center">
												<svg className="w-16 h-16 text-gray-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
													<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
												</svg>
												<p className="text-lg">No VA records found</p>
												<p className="text-sm mt-1">Try adjusting your search criteria</p>
											</div>
										</td>
									</tr>
								) : (
									<>
										{records.map((record, idx) => (
											<tr
												key={`${record.leaseNo}-${idx}`}
												className={`hover:bg-gray-50 transition-colors ${idx % 2 === 0 ? "bg-white" : "bg-gray-50"
													}`}
											>
												<td className="py-4 px-6 whitespace-nowrap text-sm text-center text-gray-700">{idx + 1}</td>
												<td className="py-4 px-6 whitespace-nowrap text-sm font-medium text-gray-900">{record.Lease_No}</td>
												<td className="py-4 px-6 whitespace-nowrap text-sm text-gray-700">{record.Bank}</td>
												<td className="py-4 px-6 whitespace-nowrap text-sm font-mono text-gray-700">{record.VA_No}</td>
											</tr>
										))}
										{loading && (
											<tr>
												<td colSpan={4} className="py-4 px-6 text-center">
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
				</div>
			</div>
		</div>
	);
};

export default VAListPage;