import React, { useEffect, useState } from "react";
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
	const [hasSearched, setHasSearched] = useState(false);

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
				setError("Failed to load search options. Please refresh.");
			}
		};
		fetchOptions();
	}, []);

	const fetchVaRecords = async () => {
		if (!leaseNo.trim()) {
			setError("Please enter a contract number.");
			return;
		}
		setLoading(true);
		setError(null);
		setHasSearched(true);
		try {
			const response = await api.get('/va/search', {
				params: { lease_no: leaseNo, search_by: searchBy },
			});
			setRecords(response.data || []);
		} catch (err) {
			setError("Failed to load VA records. Please check the contract number.");
			setRecords([]);
		} finally {
			setLoading(false);
		}
	};

	const handleSearch = () => fetchVaRecords();
	const handleKeyPress = (e: React.KeyboardEvent) => {
		if (e.key === 'Enter') handleSearch();
	};

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-7xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6 mb-6">

					<div className="mb-6">
						<h1 className="text-2xl md:text-3xl font-bold text-gray-800">
							VA List
						</h1>
						<p className="text-gray-600 mt-1">
							View and manage virtual account records for lease contracts
						</p>
					</div>

					<div className="bg-gray-50 rounded-xl p-4 border border-gray-200 mb-6">
						<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">
									Search By
								</label>
								<select
									value={searchBy}
									onChange={(e) => setSearchBy(e.target.value)}
									className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all bg-white"
								>
									{searchOptions.map((option) => (
										<option key={option.value} value={option.value}>
											{option.descValue}
										</option>
									))}
								</select>
							</div>
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">
									{searchOptions.find(o => o.value === searchBy)?.descValue ?? 'Contract No.'} *
								</label>
								<input
									type="text"
									value={leaseNo}
									onChange={(e) => setLeaseNo(e.target.value)}
									onKeyPress={handleKeyPress}
									placeholder={`Enter ${searchOptions.find(o => o.value === searchBy)?.descValue?.toLowerCase() ?? 'contract number'}`}
									className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all"
								/>
							</div>
						</div>

						<div className="flex flex-wrap gap-3 mt-4">
							<button
								onClick={handleSearch}
								disabled={loading || !leaseNo.trim()}
								className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
							>
								{loading ? (
									<>
										<svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
											<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
											<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
										</svg>
										Searching...
									</>
								) : (
									<>
										<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-4.35-4.35M17 11A6 6 0 105 11a6 6 0 0012 0z" />
										</svg>
										Search
									</>
								)}
							</button>

							{records.length > 0 && (
								<span className="inline-flex items-center px-3 py-2 rounded-lg bg-green-50 border border-green-200 text-green-700 text-sm font-medium">
									<svg className="w-4 h-4 mr-1.5" fill="currentColor" viewBox="0 0 20 20">
										<path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
									</svg>
									{records.length} record{records.length !== 1 ? 's' : ''} found
								</span>
							)}
						</div>
					</div>

					{error && (
						<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 flex items-start gap-3">
							<svg className="w-5 h-5 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
							</svg>
							<span>{error}</span>
						</div>
					)}

					{records.length > 0 && (
						<div className="overflow-x-auto rounded-lg border border-gray-200">
							<table className="w-full text-sm">
								<thead className="bg-gradient-to-r from-gray-50 to-gray-100 sticky top-0 z-10">
									<tr>
										<th className="py-3 px-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider border border-gray-300 bg-gray-100 w-16">
											No.
										</th>
										<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider border border-gray-300 bg-gray-100">
											Contract No.
										</th>
										<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider border border-gray-300 bg-gray-100">
											Bank
										</th>
										<th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider border border-gray-300 bg-gray-100">
											VA Number
										</th>
									</tr>
								</thead>
								<tbody className="divide-y divide-gray-200">
									{records.map((record, idx) => (
										<tr
											key={`${record.Lease_No}-${idx}`}
											className={`hover:bg-blue-50 transition-colors ${idx % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'}`}
										>
											<td className="py-2.5 px-4 text-center border border-gray-200 text-gray-500 font-medium text-sm">
												{idx + 1}
											</td>
											<td className="py-2.5 px-4 border border-gray-200 font-semibold text-gray-900 font-mono">
												{record.Lease_No}
											</td>
											<td className="py-2.5 px-4 border border-gray-200 text-gray-700">
												{record.Bank}
											</td>
											<td className="py-2.5 px-4 border border-gray-200 font-mono text-gray-700">
												{record.VA_No}
											</td>
										</tr>
									))}
								</tbody>
							</table>
						</div>
					)}

					{loading && (
						<div className="py-10 text-center">
							<div className="flex justify-center">
								<svg className="animate-spin h-8 w-8 text-blue-600" fill="none" viewBox="0 0 24 24">
									<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
									<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
								</svg>
							</div>
							<p className="mt-4 text-gray-600">Searching VA records...</p>
						</div>
					)}

					{!loading && hasSearched && records.length === 0 && !error && (
						<div className="py-10 text-center text-gray-500">
							<svg className="w-16 h-16 text-gray-300 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
							</svg>
							<p className="text-lg">No VA records found</p>
							<p className="text-sm mt-1">Try adjusting your search criteria</p>
						</div>
					)}

					{!loading && !hasSearched && !error && (
						<div className="py-10 text-center text-gray-500">
							<svg className="w-16 h-16 text-gray-300 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-4.35-4.35M17 11A6 6 0 105 11a6 6 0 0012 0z" />
							</svg>
							<p className="text-lg">Enter a Contract No. to view VA records</p>
							<p className="text-sm mt-1">Search will show all virtual accounts linked to the contract</p>
						</div>
					)}

				</div>
			</div>
		</div>
	);
};

export default VAListPage;