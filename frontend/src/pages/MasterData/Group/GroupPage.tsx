import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import Pagination from "../../../helpers/Pagination";

interface Group {
	GrpCode: string;
	GrpName: string;
}

interface SelectOption {
	value: string;
	label: string;
}

const GROUP_TYPE_OPTIONS: SelectOption[] = [
	{ value: "I", label: "Individual" },
	{ value: "C", label: "Corporate" },
];

const API_URL = import.meta.env.VITE_API_URL;

const GroupPage: React.FC = () => {
	const navigate = useNavigate();

	const [groups, setGroups] = useState<Group[]>([]);
	const [total, setTotal] = useState(0);
	const [page, setPage] = useState(1);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const limit = 25;

	const [searchBy, setSearchBy] = useState("1");
	const [searchVal, setSearchVal] = useState("");
	const [appliedSearchBy, setAppliedSearchBy] = useState("");
	const [appliedSearchVal, setAppliedSearchVal] = useState("");

	const [akses, setAkses] = useState("");
	const [grpcode, setGrpcode] = useState("");
	const [formPasscode, setFormPasscode] = useState("");
	const [formSlik, setFormSlik] = useState("");
	const [formName, setFormName] = useState("");
	const [formDesc, setFormDesc] = useState("");
	const [formType, setFormType] = useState("");
	const [formLoading, setFormLoading] = useState(false);
	const [formMessage, setFormMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

	const [sippOptions, setSippOptions] = useState<SelectOption[]>([]);
	const [slikOptions, setSlikOptions] = useState<SelectOption[]>([]);

	const fetchGroups = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			const res = await axios.get(`${API_URL}/MasterData/api/group`, {
				params: {
					search_by: appliedSearchBy,
					search_val: appliedSearchVal,
					page,
					limit,
				},
				timeout: 10000,
			});
			setGroups(res.data.data);
			setTotal(res.data.total);
			setAkses(res.data.akses);
		} catch {
			setError("Failed to load group data. Please try again.");
		} finally {
			setLoading(false);
		}
	}, [appliedSearchBy, appliedSearchVal, page]);

	const fetchNextCode = useCallback(async () => {
		try {
			const res = await axios.get(`${API_URL}/MasterData/api/group/next-code`);
			setGrpcode(res.data.next_code);
		} catch {
			setGrpcode("");
		}
	}, []);

	const fetchDropdowns = useCallback(async () => {
		try {
			const [sippRes, slikRes] = await Promise.all([
				axios.get(`${API_URL}/MasterData/api/group/sipp-options`),
				axios.get(`${API_URL}/MasterData/api/group/slik-options`),
			]);
			setSippOptions(sippRes.data.data);
			setSlikOptions(slikRes.data.data);
		} catch {
			// non-critical
		}
	}, []);

	useEffect(() => { fetchGroups(); }, [fetchGroups]);

	useEffect(() => {
		if (akses === "9") {
			fetchNextCode();
			fetchDropdowns();
		}
	}, [akses, fetchNextCode, fetchDropdowns]);

	const handleSearch = () => {
		setAppliedSearchBy(searchBy);
		setAppliedSearchVal(searchVal);
		setPage(1);
	};

	const handleSave = async () => {
		setFormLoading(true);
		setFormMessage(null);
		try {
			await axios.post(`${API_URL}/MasterData/api/group`, {
				grpcode,
				grpname: formName,
				grpdesc: formDesc,
				grptype: formType,
				grppasscode: formPasscode,
				slikgroupcode: formSlik,
			});
			setFormMessage({ type: "success", text: "Successful" });
			setFormName("");
			setFormDesc("");
			setFormType("");
			setFormPasscode("");
			setFormSlik("");
			fetchGroups();
			fetchNextCode();
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

	const handleDelete = async (code: string, name: string) => {
		if (!window.confirm(`Delete group "${name}" (${code})?`)) return;
		try {
			await axios.delete(`${API_URL}/MasterData/api/group/${code}`);
			fetchGroups();
			fetchNextCode();
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
						<h2 className="text-xl font-bold text-gray-800 mb-4">Add Group</h2>

						<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
							{/* Group Code — read-only auto */}
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Group Code</label>
								<input
									type="text"
									value={grpcode}
									readOnly
									className="w-full border border-gray-200 bg-gray-50 rounded-lg px-3 py-2 text-gray-500 cursor-not-allowed"
								/>
							</div>

							{/* Group Type */}
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Group Type</label>
								<select
									value={formType}
									onChange={(e) => setFormType(e.target.value)}
									className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
								>
									<option value="">Select</option>
									{GROUP_TYPE_OPTIONS.map((o) => (
										<option key={o.value} value={o.value}>{o.label}</option>
									))}
								</select>
							</div>

							{/* Group SIPP */}
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Group SIPP</label>
								<select
									value={formPasscode}
									onChange={(e) => setFormPasscode(e.target.value)}
									className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
								>
									<option value="">Select</option>
									{sippOptions.map((o) => (
										<option key={o.value} value={o.value}>{o.label}</option>
									))}
								</select>
							</div>

							{/* Group SLIK */}
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Group SLIK</label>
								<select
									value={formSlik}
									onChange={(e) => setFormSlik(e.target.value)}
									className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
								>
									<option value="">Select</option>
									{slikOptions.map((o) => (
										<option key={o.value} value={o.value}>{o.label}</option>
									))}
								</select>
							</div>

							{/* Group Name */}
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Group Name</label>
								<input
									type="text"
									value={formName}
									onChange={(e) => setFormName(e.target.value)}
									maxLength={100}
									placeholder="Enter group name"
									className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
								/>
							</div>

							{/* Group Description */}
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Group Description</label>
								<input
									type="text"
									value={formDesc}
									onChange={(e) => setFormDesc(e.target.value)}
									placeholder="Enter group description"
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
							<h1 className="text-2xl md:text-3xl font-bold text-gray-800">Group</h1>
							<p className="text-gray-600 mt-1">View and manage customer groups</p>
						</div>
						<span className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm font-medium self-start md:self-auto">
							Total: {total}
						</span>
					</div>

					{/* Search bar */}
					<div className="flex flex-col md:flex-row gap-3 mb-6">
						<select
							value={searchBy}
							onChange={(e) => setSearchBy(e.target.value)}
							className="border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
						>
							<option value="1">Code</option>
							<option value="2">Group Name</option>
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
							<button onClick={fetchGroups} className="ml-4 underline text-red-900">Retry</button>
						</div>
					)}

					{/* Table */}
					<div className="overflow-x-auto rounded-lg border border-gray-200">
						<table className="w-full">
							<thead className="bg-gradient-to-r from-gray-50 to-gray-100">
								<tr>
									<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Code</th>
									<th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Group Name</th>
									<th className="py-4 px-6 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Action</th>
								</tr>
							</thead>
							<tbody className="divide-y divide-gray-200">
								{groups.length === 0 && !loading ? (
									<tr>
										<td colSpan={3} className="py-10 px-6 text-center text-gray-500">
											<div className="flex flex-col items-center justify-center">
												<svg className="w-16 h-16 text-gray-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
													<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
												</svg>
												<p className="text-lg">No group records found</p>
												<p className="text-sm mt-1">Try adjusting your search query</p>
											</div>
										</td>
									</tr>
								) : (
									<>
										{groups.map((row, idx) => (
											<tr
												key={row.GrpCode}
												className={`hover:bg-blue-50 transition-colors ${idx % 2 === 0 ? "bg-white" : "bg-gray-50"}`}
											>
												<td className="py-4 px-6 text-sm font-mono font-medium text-gray-900">{row.GrpCode}</td>
												<td className="py-4 px-6 text-sm text-gray-800">{row.GrpName}</td>
												<td className="py-4 px-6 text-center">
													<div className="flex justify-center gap-2">
														{/* Member — always visible */}
														<button
															onClick={() => navigate(`/group-member?grpcode=${row.GrpCode}`)}
															className="bg-blue-500 hover:bg-blue-600 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
														>
															Member
														</button>

														{/* Edit & Delete — admin only */}
														{akses === "9" && (
															<>
																<button
																	onClick={() => navigate(`/group-edit?grpcode=${row.GrpCode}`)}
																	className="bg-yellow-400 hover:bg-yellow-500 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
																>
																	Edit
																</button>
																<button
																	onClick={() => handleDelete(row.GrpCode, row.GrpName)}
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
												<td colSpan={3} className="py-4 px-6 text-center">
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

export default GroupPage;