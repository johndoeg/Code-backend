import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import Pagination from "../../helpers/Pagination";

interface MenuItem {
	menu_id: string;
	menu_desc: string;
	menu_parent: string;
	parent_label: string;
	url: string;
}

interface ParentOption {
	menu_id: string;
	menu_desc: string;
}

const API_URL = import.meta.env.VITE_API_URL;

const MenuEntryPage: React.FC = () => {
	const [menus, setMenus] = useState<MenuItem[]>([]);
	const [total, setTotal] = useState(0);
	const [page, setPage] = useState(1);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const limit = 25;

	const [akses, setAkses] = useState("");
	const [parentOptions, setParentOptions] = useState<ParentOption[]>([]);
	const [formParent, setFormParent] = useState("");
	const [formDesc, setFormDesc] = useState("");
	const [formUrl, setFormUrl] = useState("");
	const [formLoading, setFormLoading] = useState(false);
	const [formMessage, setFormMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

	const fetchMenus = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			const res = await axios.get(`${API_URL}/SystemAdmin/api/menu`, {
				params: { page, limit },
				timeout: 10000,
			});
			setMenus(res.data.data);
			setTotal(res.data.total);
			setAkses(res.data.akses);
		} catch {
			setError("Failed to load menu data. Please try again.");
		} finally {
			setLoading(false);
		}
	}, [page]);

	const fetchParentOptions = useCallback(async () => {
		try {
			const res = await axios.get(`${API_URL}/SystemAdmin/api/menu/parent-options`);
			setParentOptions(res.data.data);
		} catch {
			// non-critical
		}
	}, []);

	useEffect(() => { fetchMenus(); }, [fetchMenus]);
	useEffect(() => { if (akses === "9") fetchParentOptions(); }, [akses, fetchParentOptions]);

	const handleSave = async () => {
		setFormLoading(true);
		setFormMessage(null);
		try {
			await axios.post(`${API_URL}/SystemAdmin/api/menu`, {
				menu_parent: formParent,
				menu_desc: formDesc,
				url: formUrl,
			});
			setFormMessage({ type: "success", text: "Successful" });
			setFormParent("");
			setFormDesc("");
			setFormUrl("");

			fetchMenus();
			fetchParentOptions();
		} catch (err: any) {
			const msgs = err.response?.data?.message;
			setFormMessage({
				type: "error",
				text: Array.isArray(msgs) ? msgs.join(", ") : "Failed",
			});
		} finally {
			setFormLoading(false);
		}
	};

	const handleDelete = async (menu_id: string, menu_desc: string) => {
		if (!window.confirm(`Delete menu "${menu_desc}" (${menu_id})?\nAll child menus will also be deleted.`)) return;
		try {
			await axios.delete(`${API_URL}/SystemAdmin/api/menu/${encodeURIComponent(menu_id)}`);
			fetchMenus();
			fetchParentOptions();
		} catch {
			alert("Delete failed.");
		}
	};

	const totalPages = Math.ceil(total / limit);

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-7xl mx-auto space-y-6">

				{/* ── Entry Form (admin only) ── */}
				{akses === "9" && (
					<div className="bg-white rounded-2xl shadow-lg p-6">
						<h2 className="text-xl font-bold text-gray-800 mb-4">Add Menu</h2>

						<div className="grid grid-cols-1 md:grid-cols-3 gap-4">
							{/* Menu Parent */}
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Menu Parent</label>
								<select
									value={formParent}
									onChange={(e) => setFormParent(e.target.value)}
									className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
								>
									<option value="">Select</option>
									<option value="0">Parent (top-level)</option>
									{parentOptions.map((p) => (
										<option key={p.menu_id} value={p.menu_id}>
											{p.menu_id} — {p.menu_desc}
										</option>
									))}
								</select>
							</div>

							{/* Menu Description */}
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Menu Description</label>
								<input
									type="text"
									value={formDesc}
									onChange={(e) => setFormDesc(e.target.value)}
									placeholder="Enter menu description"
									className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
								/>
							</div>

							{/* Menu URL */}
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Menu URL</label>
								<input
									type="text"
									value={formUrl}
									onChange={(e) => setFormUrl(e.target.value)}
									placeholder="/path/to/page"
									className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
								/>
							</div>
						</div>

						<div className="mt-4 flex items-center gap-4">
							<button
								onClick={handleSave}
								disabled={formLoading}
								className={`bg-gradient-to-r from-blue-600 to-indigo-700 hover:from-blue-700 hover:to-indigo-800 text-white px-6 py-2 rounded-lg font-medium shadow-md transition-all ${formLoading ? "opacity-75 cursor-not-allowed" : ""}`}
							>
								{formLoading ? "Saving..." : "Save"}
							</button>

							{formMessage && (
								<span className={`text-sm font-medium ${formMessage.type === "success" ? "text-green-600" : "text-red-600"}`}>
									{formMessage.text}
								</span>
							)}
						</div>
					</div>
				)}

				{/* ── List ── */}
				<div className="bg-white rounded-2xl shadow-lg p-6">
					<div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
						<div>
							<h1 className="text-2xl md:text-3xl font-bold text-gray-800">Menu</h1>
							<p className="text-gray-600 mt-1">View and manage application menu entries</p>
						</div>
						<span className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm font-medium self-start md:self-auto">
							Total: {total}
						</span>
					</div>

					{error && (
						<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
							{error}
							<button onClick={fetchMenus} className="ml-4 underline text-red-900">Retry</button>
						</div>
					)}

					<div className="overflow-x-auto rounded-lg border border-gray-200">
						<table className="w-full">
							<thead className="bg-gradient-to-r from-gray-50 to-gray-100">
								<tr>
									<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Menu ID</th>
									<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Description</th>
									<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Parent</th>
									<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">URL</th>
									{akses === "9" && (
										<th className="py-4 px-6 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Action</th>
									)}
								</tr>
							</thead>
							<tbody className="divide-y divide-gray-200">
								{menus.length === 0 && !loading ? (
									<tr>
										<td colSpan={5} className="py-10 px-6 text-center text-gray-500">
											<div className="flex flex-col items-center justify-center">
												<svg className="w-16 h-16 text-gray-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
													<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
												</svg>
												<p className="text-lg">No menu records found</p>
											</div>
										</td>
									</tr>
								) : (
									<>
										{menus.map((row, idx) => (
											<tr
												key={row.menu_id}
												className={`hover:bg-blue-50 transition-colors ${idx % 2 === 0 ? "bg-white" : "bg-gray-50"}`}
											>
												<td className="py-4 px-6 text-sm font-mono font-medium text-gray-900">
													{/* indent child menus visually by depth */}
													<span style={{ paddingLeft: `${(row.menu_id.split('.').length - 1) * 16}px` }}>
														{row.menu_id}
													</span>
												</td>
												<td className="py-4 px-6 text-sm text-gray-800">{row.menu_desc}</td>
												<td className="py-4 px-6 text-sm text-gray-500">{row.parent_label}</td>
												<td className="py-4 px-6 text-sm text-gray-500 font-mono">{row.url}</td>
												{akses === "9" && (
													<td className="py-4 px-6 text-center">
														<div className="flex justify-center gap-2">
															<button
																onClick={() => window.location.href = `/menu-edit?menu_id=${encodeURIComponent(row.menu_id)}`}
																className="bg-yellow-400 hover:bg-yellow-500 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
															>
																Edit
															</button>
															<button
																onClick={() => handleDelete(row.menu_id, row.menu_desc)}
																className="bg-red-500 hover:bg-red-600 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
															>
																Delete
															</button>
														</div>
													</td>
												)}
											</tr>
										))}
										{loading && (
											<tr>
												<td colSpan={5} className="py-4 px-6 text-center">
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

export default MenuEntryPage;