import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import Pagination from "../../../helpers/Pagination";

interface Karoseri {
	ID_Key: string;
	KAROSERI: string;
	KAROSERI_DESC: string;
	isActive: boolean;
	MODEL: string;
	MODEL_NM: string;
}

interface ModelOption {
	MODEL: string;
	MODEL_NM: string;
}

const API_URL = import.meta.env.VITE_API_URL;

const KaroseriPage: React.FC = () => {
	const [karoseri, setKaroseri] = useState<Karoseri[]>([]);
	const [total, setTotal] = useState(0);
	const [page, setPage] = useState(1);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const limit = 25;

	// live input state (what the user is typing)
	const [searchBy, setSearchBy] = useState("1");
	const [searchVal, setSearchVal] = useState("");
	// applied/committed state (what was last searched)
	const [appliedSearchBy, setAppliedSearchBy] = useState("1");
	const [appliedSearchVal, setAppliedSearchVal] = useState("");

	const [akses, setAkses] = useState("");
	const [modelOptions, setModelOptions] = useState<ModelOption[]>([]);
	const [formModel, setFormModel] = useState("");
	const [formKaroseri, setFormKaroseri] = useState("");
	const [formDesc, setFormDesc] = useState("");
	const [formActive, setFormActive] = useState("");
	const [formLoading, setFormLoading] = useState(false);
	const [formMessage, setFormMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

	// ✅ Fix 1: depends on applied* values, not live input values
	const fetchKaroseri = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			const response = await axios.get(`${API_URL}/MasterData/api/karoseri`, {
				params: { search_val: appliedSearchVal, search_by: appliedSearchBy, page, limit },
				timeout: 10000,
			});
			setKaroseri(response.data.data);
			setTotal(response.data.total);
			setAkses(response.data.akses);
		} catch {
			setError("Failed to load karoseri data. Please try again.");
		} finally {
			setLoading(false);
		}
	}, [appliedSearchVal, appliedSearchBy, page]);

	const fetchModelOptions = useCallback(async () => {
		try {
			const res = await axios.get(`${API_URL}/MasterData/api/karoseri/models`);
			setModelOptions(res.data.data);
		} catch {
			// non-critical; form simply won't populate
		}
	}, []);

	const fetchNextCode = useCallback(async (model: string) => {
		if (!model) { setFormKaroseri(""); return; }
		try {
			const res = await axios.get(`${API_URL}/MasterData/api/karoseri/next-code`, {
				params: { model },
			});
			setFormKaroseri(res.data.next_code);
		} catch {
			setFormKaroseri("");
		}
	}, []);

	// ✅ Fix 2: only one useEffect for fetchKaroseri (duplicate removed)
	useEffect(() => { fetchKaroseri(); }, [fetchKaroseri]);
	useEffect(() => { if (akses === "9") fetchModelOptions(); }, [akses, fetchModelOptions]);

	// ✅ Fix 3: commits all three state updates atomically so fetchKaroseri
	//           always sees page=1 together with the new search terms
	const handleSearch = () => {
		setAppliedSearchVal(searchVal);
		setAppliedSearchBy(searchBy);
		setPage(1);
	};

	const handleModelChange = (model: string) => {
		setFormModel(model);
		fetchNextCode(model);
	};

	const handleSave = async () => {
		setFormLoading(true);
		setFormMessage(null);
		try {
			await axios.post(`${API_URL}/MasterData/api/karoseri`, {
				model: formModel,
				karoseri: formKaroseri,
				karoseri_desc: formDesc,
				isActive: formActive,
			});
			setFormMessage({ type: "success", text: "Successful Insert" });
			setFormDesc("");
			setFormActive("");
			setFormModel("");
			setFormKaroseri("");
			fetchKaroseri();
		} catch (err: any) {
			const msgs = err.response?.data?.message;
			setFormMessage({
				type: "error",
				text: Array.isArray(msgs) ? msgs.join(", ") : "Failed Insert",
			});
		} finally {
			setFormLoading(false);
		}
	};

	const handleDelete = async (model: string, kode: string) => {
		if (!window.confirm(`Delete karoseri ${kode} from model ${model}?`)) return;
		try {
			await axios.delete(`${API_URL}/MasterData/api/karoseri/${model}/${kode}`);
			fetchKaroseri();
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
						<h2 className="text-xl font-bold text-gray-800 mb-4">Add Karoseri</h2>

						<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Model</label>
								<select
									value={formModel}
									onChange={(e) => handleModelChange(e.target.value)}
									className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
								>
									<option value="">Select</option>
									{modelOptions.map((m) => (
										<option key={m.MODEL} value={m.MODEL}>{m.MODEL_NM}</option>
									))}
								</select>
							</div>

							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
								<select
									value={formActive}
									onChange={(e) => setFormActive(e.target.value)}
									className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
								>
									<option value="">Select</option>
									<option value="1">Active</option>
									<option value="0">Inactive</option>
								</select>
							</div>

							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Karoseri Code</label>
								<input
									type="text"
									value={formKaroseri}
									readOnly
									className="w-full border border-gray-200 bg-gray-50 rounded-lg px-3 py-2 text-gray-500 cursor-not-allowed"
								/>
							</div>

							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Karoseri Description</label>
								<input
									type="text"
									value={formDesc}
									onChange={(e) => setFormDesc(e.target.value)}
									placeholder="Enter description"
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

				{/* ── List / Search ── */}
				<div className="bg-white rounded-2xl shadow-lg p-6">
					<div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
						<div>
							<h1 className="text-2xl md:text-3xl font-bold text-gray-800">Karoseri</h1>
							<p className="text-gray-600 mt-1">View and manage your karoseri records</p>
						</div>
						<span className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm font-medium self-start md:self-auto">
							Total: {total}
						</span>
					</div>

					{/* ✅ Fix 4: restored proper <input> + single Search <button> */}
					<div className="flex flex-col md:flex-row gap-3 mb-6">
						<select
							value={searchBy}
							onChange={(e) => setSearchBy(e.target.value)}
							className="border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
						>
							<option value="1">Model</option>
							<option value="2">Karoseri Description</option>
						</select>

						<div className="relative flex-1">
							<input
								type="text"
								placeholder="Search..."
								value={searchVal}
								onChange={(e) => setSearchVal(e.target.value)}
								onKeyDown={(e) => { if (e.key === "Enter") handleSearch(); }}
								className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
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
							<button onClick={fetchKaroseri} className="ml-4 underline text-red-900">Retry</button>
						</div>
					)}

					<div className="overflow-x-auto rounded-lg border border-gray-200">
						<table className="w-full">
							<thead className="bg-gradient-to-r from-gray-50 to-gray-100">
								<tr>
									<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Model</th>
									<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Karoseri</th>
									<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Description</th>
									<th className="py-4 px-6 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
									{akses === "9" && (
										<th className="py-4 px-6 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Action</th>
									)}
								</tr>
							</thead>
							<tbody className="divide-y divide-gray-200">
								{karoseri.length === 0 && !loading ? (
									<tr>
										<td colSpan={5} className="py-10 px-6 text-center text-gray-500">
											<div className="flex flex-col items-center justify-center">
												<svg className="w-16 h-16 text-gray-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
													<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
												</svg>
												<p className="text-lg">No karoseri records found</p>
												<p className="text-sm mt-1">Try adjusting your search query</p>
											</div>
										</td>
									</tr>
								) : (
									<>
										{karoseri.map((row, idx) => (
											<tr
												key={`${row.MODEL}-${row.KAROSERI}`}
												className={`hover:bg-blue-50 transition-colors ${idx % 2 === 0 ? "bg-white" : "bg-gray-50"}`}
											>
												<td className="py-4 px-6 text-sm text-gray-900 font-medium">{row.MODEL_NM}</td>
												<td className="py-4 px-6 text-sm text-gray-700">{row.KAROSERI}</td>
												<td className="py-4 px-6 text-sm text-gray-700">{row.KAROSERI_DESC}</td>
												<td className="py-4 px-6 text-center">
													<span className={`inline-flex px-2 py-1 rounded-full text-xs font-semibold ${row.isActive ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`}>
														{row.isActive ? "Active" : "Inactive"}
													</span>
												</td>
												{akses === "9" && (
													<td className="py-4 px-6 text-center">
														<div className="flex justify-center gap-2">
															<button
																onClick={() => window.location.href = `/karoseri-edit?model=${row.MODEL}&karoseri=${row.KAROSERI}`}
																className="bg-yellow-400 hover:bg-yellow-500 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
															>
																Edit
															</button>
															<button
																onClick={() => handleDelete(row.MODEL, row.KAROSERI)}
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

export default KaroseriPage;