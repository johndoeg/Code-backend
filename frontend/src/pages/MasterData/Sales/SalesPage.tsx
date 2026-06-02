import React, { useEffect, useState, useCallback } from "react";
import api from "../../../api/axiosInstance";
import Pagination from "../../../helpers/Pagination";
import { useNavigate } from "react-router-dom";

interface Sales {
	SALES_NO: string;
	NAME: string;
	ADDRESS: string;
	IDCARD: string;
	Status: string;
	Sales_Type?: string;
	IsSalesTV?: boolean;
}

const SalesPage: React.FC = () => {
	const [sales, setSales] = useState<Sales[]>([]);
	const [search, setSearch] = useState("");
	const [page, setPage] = useState(1);
	const [total, setTotal] = useState(0);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const limit = 25;

	const fetchSales = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			const response = await api.get('/MasterData/api/sales', {
				params: { search_val: search, page, limit },
				timeout: 10000,
			});
			setSales(response.data.data);
			setTotal(response.data.total);
		} catch (err) {
			if (err) {
				return;
			}
			console.error(err);
			setError('Failed to load sales data. Please try again.');
		} finally {
			setLoading(false);
		}
	}, [search, page, limit]);

	useEffect(() => {
		fetchSales();
	}, [fetchSales]);

	const totalPages = Math.ceil(total / limit);

	const navigate = useNavigate();
	
	const handleEdit = (salesNo: string, salesType?: string) => {
		navigate(`/sales-entry?id=Edit&salesno=${salesNo}&sal_type=${salesType || ""}`);
	};

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-7xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6 mb-6">
					<div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
						<div>
							<h1 className="text-2xl md:text-3xl font-bold text-gray-800">Sales</h1>
							<p className="text-gray-600 mt-1">View and manage your sales records</p>
						</div>
						<div className="flex items-center gap-3">
							<span className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm font-medium">
								Total: {total}
							</span>
						</div>
					</div>

					<div className="flex flex-col md:flex-row gap-4 mb-6">
						<div className="relative flex-1">
							<input
								type="text"
								placeholder="Search sales by name, ID, or address..."
								value={search}
								onChange={(e) => setSearch(e.target.value)}
								className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all"
							/>
							<svg 
								className="w-5 h-5 text-gray-400 absolute left-3 top-1/2 transform -translate-y-1/2" 
								focusable="false" 
								aria-hidden="true" 
								viewBox="0 0 24 24" 
								fill="none"
							>
								<path d="M15.5 14H14.71L14.43 13.73C15.41 12.59 16 11.11 16 9.5C16 5.91 13.09 3 9.5 3C5.91 3 3 5.91 3 9.5C3 13.09 5.91 16 9.5 16C11.11 16 12.59 15.41 13.73 14.43L14 14.71V15.5L19 20.49L20.49 19L15.5 14ZM9.5 14C7.01 14 5 11.99 5 9.5C5 7.01 7.01 5 9.5 5C11.99 5 14 7.01 14 9.5C14 11.99 11.99 14 9.5 14Z" fill="currentColor"></path>
							</svg>
						</div>
						<button
							onClick={() => {
								setPage(1);
								fetchSales();
							}}
							disabled={loading}
							className={`bg-gradient-to-r from-blue-600 to-indigo-700 hover:from-blue-700 hover:to-indigo-800 text-white px-6 py-3 rounded-lg font-medium shadow-md hover:shadow-lg transition-all flex items-center justify-center gap-2 ${
								loading ? 'opacity-75 cursor-not-allowed' : ''
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
									<svg className="w-5 h-5" focusable="false" aria-hidden="true" viewBox="0 0 24 24" fill="none">
										<path d="M15.5 14H14.71L14.43 13.73C15.41 12.59 16 11.11 16 9.5C16 5.91 13.09 3 9.5 3C5.91 3 3 5.91 3 9.5C3 13.09 5.91 16 9.5 16C11.11 16 12.59 15.41 13.73 14.43L14 14.71V15.5L19 20.49L20.49 19L15.5 14ZM9.5 14C7.01 14 5 11.99 5 9.5C5 7.01 7.01 5 9.5 5C11.99 5 14 7.01 14 9.5C14 11.99 11.99 14 9.5 14Z" fill="currentColor"></path>
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
								onClick={fetchSales}
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
									<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Sales No</th>
									<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
									<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Address</th>
									<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ID Card</th>
									<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
									<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
								</tr>
							</thead>
							<tbody className="divide-y divide-gray-200">
								{sales.length === 0 && !loading ? (
									<tr>
										<td colSpan={6} className="py-10 px-6 text-center text-gray-500">
											<div className="flex flex-col items-center justify-center">
												<svg className="w-16 h-16 text-gray-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
													<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
												</svg>
												<p className="text-lg">No sales records found</p>
												<p className="text-sm mt-1">Try adjusting your search query</p>
											</div>
										</td>
									</tr>
								) : (
									<>
										{sales.map((s, idx) => (
											<tr 
												key={s.SALES_NO} 
												className={`hover:bg-gray-50 transition-colors ${idx % 2 === 0 ? "bg-white" : "bg-gray-50"}`}
											>
												<td className="py-4 px-6 whitespace-nowrap text-sm font-medium text-gray-900">{s.SALES_NO}</td>
												<td className="py-4 px-6 whitespace-nowrap text-sm text-gray-700 font-medium">{s.NAME}</td>
												<td className="py-4 px-6 text-sm text-gray-600 max-w-xs truncate">{s.ADDRESS}</td>
												<td className="py-4 px-6 whitespace-nowrap text-sm text-gray-600">{s.IDCARD}</td>
												<td className="py-4 px-6 whitespace-nowrap">
													<span className={`px-3 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${
														s.Status === "Active" 
															? "bg-green-100 text-green-800" 
															: "bg-red-100 text-red-800"
													}`}>
														{s.Status === "Active" ? "Active" : "Inactive"}
													</span>
												</td>
												<td className="py-4 px-6 whitespace-nowrap text-sm">
													

													<button
														onClick={() => handleEdit(s.SALES_NO, s.Sales_Type)}
														className="px-3 py-1 bg-blue-500 text-white text-xs rounded hover:bg-blue-600"
														>
														View
													</button>
												</td>
											</tr>
										))}
										{loading && (
											<tr>
												<td colSpan={6} className="py-4 px-6 text-center">
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

					{!loading && (
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

export default SalesPage;