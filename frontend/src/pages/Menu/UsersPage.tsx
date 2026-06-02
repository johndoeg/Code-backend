import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import Pagination from "../../helpers/Pagination";

interface User {
	EMPLOYEE_ID: string;
	USERNAME: string;
	FULLNAME: string;
	ACCESSCAM: string;
	BRANCH_NAME: string;
	SUPERIOR: string;
	STATUS: string;
}

const SEARCH_OPTIONS = [
	{ value: "1", label: "All" },
	{ value: "2", label: "Username" },
	{ value: "3", label: "Employee ID" },
	{ value: "4", label: "Group Access" },
];

const API_URL = import.meta.env.VITE_API_URL;

const UsersPage: React.FC = () => {
	const navigate = useNavigate();

	const [users, setUsers] = useState<User[]>([]);
	const [total, setTotal] = useState(0);
	const [page, setPage] = useState(1);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const limit = 25;

	const [searchBy, setSearchBy] = useState("1");
	const [searchVal, setSearchVal] = useState("");
	const [appliedSearchBy, setAppliedSearchBy] = useState("1");
	const [appliedSearchVal, setAppliedSearchVal] = useState("");

	const [akses, setAkses] = useState("");

	const fetchUsers = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			const res = await axios.get(`${API_URL}/SystemAdmin/api/users`, {
				params: {
					search_by: appliedSearchBy,
					search_val: appliedSearchVal,
					page,
					limit,
				},
				timeout: 10000,
			});
			setUsers(res.data.data);
			setTotal(res.data.total);
			setAkses(res.data.akses);
		} catch {
			setError("Failed to load user data. Please try again.");
		} finally {
			setLoading(false);
		}
	}, [appliedSearchBy, appliedSearchVal, page]);

	useEffect(() => { fetchUsers(); }, [fetchUsers]);

	const handleSearch = () => {
		if (searchBy !== "1" && !searchVal.trim()) {
			alert("Please fill the search field.");
			return;
		}
		setAppliedSearchBy(searchBy);
		setAppliedSearchVal(searchVal);
		setPage(1);
	};

	const handleDelete = async (employee_id: string, username: string) => {
		if (!window.confirm(`Delete user "${username}" (${employee_id})?`)) return;
		try {
			await axios.delete(`${API_URL}/SystemAdmin/api/users/${employee_id}`);
			fetchUsers();
		} catch {
			alert("Delete failed.");
		}
	};

	const totalPages = Math.ceil(total / limit);

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-7xl mx-auto space-y-6">
				<div className="bg-white rounded-2xl shadow-lg p-6">

					{/* ── Header ── */}
					<div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
						<div>
							<h1 className="text-2xl md:text-3xl font-bold text-gray-800">Users</h1>
							<p className="text-gray-600 mt-1">View and manage system users</p>
						</div>
						<div className="flex items-center gap-3">
							<span className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm font-medium">
								Total: {total}
							</span>
							{/* Add button — admin only */}
							{akses === "9" && (
								<button
									onClick={() => navigate("/user-entry?id=Add")}
									className="bg-gradient-to-r from-blue-600 to-indigo-700 hover:from-blue-700 hover:to-indigo-800 text-white px-4 py-2 rounded-lg text-sm font-medium shadow-md transition-all flex items-center gap-2"
								>
									<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
									</svg>
									Add User
								</button>
							)}
						</div>
					</div>

					{/* ── Search bar ── */}
					<div className="flex flex-col md:flex-row gap-3 mb-6">
						<select
							value={searchBy}
							onChange={(e) => setSearchBy(e.target.value)}
							className="border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
						>
							{SEARCH_OPTIONS.map((opt) => (
								<option key={opt.value} value={opt.value}>{opt.label}</option>
							))}
						</select>

						<div className="relative flex-1">
							<input
								type="text"
								placeholder="Search..."
								value={searchVal}
								onChange={(e) => setSearchVal(e.target.value)}
								onKeyDown={(e) => { if (e.key === "Enter") handleSearch(); }}
								disabled={searchBy === "1"}
								className={`w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${searchBy === "1" ? "bg-gray-50 text-gray-400 cursor-not-allowed" : ""}`}
							/>
							<svg className="w-5 h-5 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" viewBox="0 0 24 24" fill="none">
								<path d="M15.5 14H14.71L14.43 13.73C15.41 12.59 16 11.11 16 9.5C16 5.91 13.09 3 9.5 3C5.91 3 3 5.91 3 9.5C3 13.09 5.91 16 9.5 16C11.11 16 12.59 15.41 13.73 14.43L14 14.71V15.5L19 20.49L20.49 19L15.5 14ZM9.5 14C7.01 14 5 11.99 5 9.5C5 7.01 7.01 5 9.5 5C11.99 5 14 7.01 14 9.5C14 11.99 11.99 14 9.5 14Z" fill="currentColor" />
							</svg>
						</div>

						<button
							onClick={handleSearch}
							disabled={loading}
							className={`bg-gradient-to-r from-blue-600 to-indigo-700 hover:from-blue-700 hover:to-indigo-800 text-white px-6 py-2 rounded-lg font-medium shadow-md transition-all flex items-center gap-2 ${loading ? "opacity-75 cursor-not-allowed" : ""}`}
						>
							{loading ? "Searching..." : "Search"}
						</button>
					</div>

					{error && (
						<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
							{error}
							<button onClick={fetchUsers} className="ml-4 underline text-red-900">Retry</button>
						</div>
					)}

					{/* ── Table ── */}
					<div className="overflow-x-auto rounded-lg border border-gray-200">
						<table className="w-full">
							<thead className="bg-gradient-to-r from-gray-50 to-gray-100">
								<tr>
									{[
										"Employee ID",
										"Username",
										"Full Name",
										"Branch",
										"Access Group",
										"Superior",
										"Status",
										"Action",
									].map((h) => (
										<th key={h} className="py-4 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
											{h}
										</th>
									))}
								</tr>
							</thead>
							<tbody className="divide-y divide-gray-200">
								{users.length === 0 && !loading ? (
									<tr>
										<td colSpan={8} className="py-10 px-6 text-center text-gray-500">
											<div className="flex flex-col items-center justify-center">
												<svg className="w-16 h-16 text-gray-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
													<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
												</svg>
												<p className="text-lg">No user records found</p>
												<p className="text-sm mt-1">Try adjusting your search query</p>
											</div>
										</td>
									</tr>
								) : (
									<>
										{users.map((row, idx) => (
											<tr
												key={row.EMPLOYEE_ID}
												className={`hover:bg-blue-50 transition-colors ${idx % 2 === 0 ? "bg-white" : "bg-gray-50"}`}
											>
												<td className="py-3 px-4 text-sm font-mono text-gray-900">{row.EMPLOYEE_ID}</td>
												<td className="py-3 px-4 text-sm font-medium text-gray-900">{row.USERNAME}</td>
												<td className="py-3 px-4 text-sm text-gray-700">{row.FULLNAME}</td>
												<td className="py-3 px-4 text-sm text-gray-600">{row.BRANCH_NAME}</td>
												<td className="py-3 px-4 text-sm text-gray-600">{row.ACCESSCAM}</td>
												<td className="py-3 px-4 text-sm text-gray-600">{row.SUPERIOR}</td>
												<td className="py-3 px-4">
													<span className={`inline-flex px-2 py-1 rounded-full text-xs font-semibold ${row.STATUS === "Active" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`}>
														{row.STATUS}
													</span>
												</td>
												<td className="py-3 px-4">
													<div className="flex gap-2">
														{/* View — always visible */}
														<button
															onClick={() => navigate(`/user-entry?id=View&employee_id=${row.EMPLOYEE_ID}`)}
															className="bg-blue-500 hover:bg-blue-600 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
														>
															View
														</button>

														{/* Edit & Delete — admin only */}
														{akses === "9" && (
															<>
																<button
																	onClick={() => navigate(`/user-entry?id=Edit&employee_id=${row.EMPLOYEE_ID}`)}
																	className="bg-yellow-400 hover:bg-yellow-500 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
																>
																	Edit
																</button>
																<button
																	onClick={() => handleDelete(row.EMPLOYEE_ID, row.USERNAME)}
																	className="bg-red-500 hover:bg-red-600 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
																>
																	Delete
																</button>
															</>
														)}
													</div>
												</td>
											</tr>
										))}
										{loading && (
											<tr>
												<td colSpan={8} className="py-4 px-6 text-center">
													<div className="flex justify-center">
														<svg className="animate-spin h-6 w-6 text-blue-600" fill="none" viewBox="0 0 24 24">
															<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
															<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
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

export default UsersPage;