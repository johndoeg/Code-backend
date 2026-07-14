import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import api from "../../../api/axiosInstance";
import Pagination from "../../../helpers/Pagination";
import { DEFAULT_PAGE_LIMIT } from "../../../constants/DefaultValue";

interface Group { GrpCode: string; GrpName: string; }
interface Opt { value: string; label: string; }
interface Msg { type: "success" | "error"; text: string; }

const GROUP_TYPES: Opt[] = [
	{ value: "I", label: "Individual" },
	{ value: "C", label: "Corporate" },
];

function Banner({ msg, onClose }: { msg: Msg; onClose: () => void }) {
	return (
		<div className={`flex items-start gap-3 rounded-lg px-4 py-3 text-sm border ${msg.type === "success"
			? "bg-green-50 border-green-200 text-green-700"
			: "bg-red-50   border-red-200   text-red-700"
			}`}>
			<span className="flex-1">{msg.text}</span>
			<button onClick={onClose} className="text-lg leading-none opacity-60 hover:opacity-100">×</button>
		</div>
	);
}

const GroupPage: React.FC = () => {
	const navigate = useNavigate();

	const [groups, setGroups] = useState<Group[]>([]);
	const [total, setTotal] = useState(0);
	const [page, setPage] = useState(1);
	const [loading, setLoading] = useState(false);
	const [listMsg, setListMsg] = useState<Msg | null>(null);
	const [akses, setAkses] = useState("0");
	const limit = DEFAULT_PAGE_LIMIT;

	const [searchBy, setSearchBy] = useState("1");
	const [searchVal, setSearchVal] = useState("");
	const [appliedSearchBy, setAppliedSearchBy] = useState("");
	const [appliedSearchVal, setAppliedSearchVal] = useState("");

	const [sippOptions, setSippOptions] = useState<Opt[]>([]);
	const [slikOptions, setSlikOptions] = useState<Opt[]>([]);

	const [grpcode, setGrpcode] = useState("");
	const [formSipp, setFormSipp] = useState("");
	const [formSlik, setFormSlik] = useState("");
	const [formName, setFormName] = useState("");
	const [formDesc, setFormDesc] = useState("");
	const [formType, setFormType] = useState("");
	const [addSaving, setAddSaving] = useState(false);
	const [addMsg, setAddMsg] = useState<Msg | null>(null);

	const [editCode, setEditCode] = useState("");
	const [editSipp, setEditSipp] = useState("");
	const [editSlik, setEditSlik] = useState("");
	const [editName, setEditName] = useState("");
	const [editDesc, setEditDesc] = useState("");
	const [editType, setEditType] = useState("");
	const [editOpen, setEditOpen] = useState(false);
	const [editSaving, setEditSaving] = useState(false);
	const [editMsg, setEditMsg] = useState<Msg | null>(null);

	const fetchGroups = useCallback(async () => {
		setLoading(true); setListMsg(null);
		try {
			const r = await api.get("/MasterData/api/group", {
				params: { search_by: appliedSearchBy, search_val: appliedSearchVal, page, limit },
			});
			setGroups(r.data.data || []);
			setTotal(r.data.total || 0);
			setAkses(r.data.akses || "0");
		} catch {
			setListMsg({ type: "error", text: "Failed to load group data." });
		} finally { setLoading(false); }
	}, [appliedSearchBy, appliedSearchVal, page, limit]);

	useEffect(() => { fetchGroups(); }, [fetchGroups]);

	const fetchNextCode = useCallback(async () => {
		try { const r = await api.get("/MasterData/api/group/next-code"); setGrpcode(r.data.next_code || ""); }
		catch { setGrpcode(""); }
	}, []);

	const fetchOptions = useCallback(async () => {
		try {
			const [s, k] = await Promise.all([
				api.get("/MasterData/api/group/sipp-options"),
				api.get("/MasterData/api/group/slik-options"),
			]);
			setSippOptions(s.data.data || []);
			setSlikOptions(k.data.data || []);
		} catch {}
	}, []);

	useEffect(() => {
		if (akses === "9") { fetchNextCode(); fetchOptions(); }
	}, [akses, fetchNextCode, fetchOptions]);

	const handleSearch = () => {
		setAppliedSearchBy(searchBy);
		setAppliedSearchVal(searchVal);
		setPage(1);
	};

	const handleSave = async () => {
		setAddSaving(true); setAddMsg(null);
		try {
			const r = await api.post("/MasterData/api/group", {
				grpcode, grpname: formName, grpdesc: formDesc, grptype: formType,
				grppasscode: formSipp, slikgroupcode: formSlik,
			});
			if (r.data.success) {
				setAddMsg({ type: "success", text: "Group saved successfully." });
				setFormName(""); setFormDesc(""); setFormType(""); setFormSipp(""); setFormSlik("");
				setPage(1); fetchGroups(); fetchNextCode();
			} else {
				setAddMsg({ type: "error", text: r.data.message || "Save failed." });
			}
		} catch (e: any) {
			const m = e.response?.data?.message;
			setAddMsg({ type: "error", text: Array.isArray(m) ? m.join(", ") : "Save failed." });
		} finally { setAddSaving(false); }
	};

	const openEdit = async (code: string) => {
		setEditMsg(null);
		try {
			const r = await api.get(`/MasterData/api/group/${code}`);
			const d = r.data;
			setEditCode(d.grpcode); setEditSipp(d.sipp_code); setEditSlik(d.slik_code);
			setEditName(d.grpname); setEditDesc(d.grpdesc); setEditType(d.grptype);

			if (sippOptions.length === 0) fetchOptions();
			setEditOpen(true);
		} catch {
			setListMsg({ type: "error", text: "Failed to load group details." });
		}
	};

	const handleUpdate = async () => {
		setEditSaving(true); setEditMsg(null);
		try {
			const r = await api.put(`/MasterData/api/group/${editCode}`, {
				grpname: editName, grpdesc: editDesc, grptype: editType,
				grppasscode: editSipp, slikgroupcode: editSlik,
			});
			if (r.data.success) {
				setEditMsg({ type: "success", text: "Group updated successfully." });
				fetchGroups();
				setTimeout(() => setEditOpen(false), 700);
			} else {
				setEditMsg({ type: "error", text: r.data.message || "Update failed." });
			}
		} catch { setEditMsg({ type: "error", text: "An error occurred." }); }
		finally { setEditSaving(false); }
	};

	const handleDelete = async (row: Group) => {
		if (!window.confirm(`Delete group "${row.GrpName}" (${row.GrpCode})?\n\nThis will clear the group from all associated customers.`)) return;
		try {
			const r = await api.delete(`/MasterData/api/group/${row.GrpCode}`);
			if (r.data.success) {
				setListMsg({ type: "success", text: `Group ${row.GrpCode} deleted.` });
				if (groups.length === 1 && page > 1) setPage(p => p - 1); else fetchGroups();
				fetchNextCode();
			} else {
				setListMsg({ type: "error", text: r.data.message || "Delete failed." });
			}
		} catch { setListMsg({ type: "error", text: "Delete failed." }); }
	};

	const totalPages = Math.ceil(total / limit);

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-6xl mx-auto space-y-5">

				{akses === "9" && (
					<div className="bg-white rounded-2xl shadow-lg p-6">
						<h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-4">
							Add Group
						</h2>
						<div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
							<div>
								<label className="block text-xs font-medium text-gray-500 mb-1">Group Code</label>
								<input readOnly value={grpcode}
									className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm bg-gray-100 font-mono" />
							</div>
							<div>
								<label className="block text-xs font-medium text-gray-500 mb-1">Group Type *</label>
								<select value={formType} onChange={e => setFormType(e.target.value)}
									className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500">
									<option value="">Select…</option>
									{GROUP_TYPES.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
								</select>
							</div>
							<div>
								<label className="block text-xs font-medium text-gray-500 mb-1">Group SIPP</label>
								<select value={formSipp} onChange={e => setFormSipp(e.target.value)}
									className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500">
									<option value="">Select…</option>
									{sippOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
								</select>
							</div>
							<div>
								<label className="block text-xs font-medium text-gray-500 mb-1">Group SLIK</label>
								<select value={formSlik} onChange={e => setFormSlik(e.target.value)}
									className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500">
									<option value="">Select…</option>
									{slikOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
								</select>
							</div>
							<div>
								<label className="block text-xs font-medium text-gray-500 mb-1">Group Name *</label>
								<input maxLength={100} value={formName} placeholder="Enter group name…"
									onChange={e => setFormName(e.target.value)}
									className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500" />
							</div>
							<div>
								<label className="block text-xs font-medium text-gray-500 mb-1">Group Description *</label>
								<input value={formDesc} placeholder="Enter description…"
									onChange={e => setFormDesc(e.target.value)}
									className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500" />
							</div>
						</div>
						<div className="mt-4">
							<button onClick={handleSave} disabled={addSaving}
								className="px-5 py-2.5 rounded-lg text-sm font-semibold text-white bg-blue-600
                           hover:bg-blue-700 disabled:opacity-60 transition-colors shadow-sm">
								{addSaving ? "Saving…" : "Save"}
							</button>
						</div>
						{addMsg && <div className="mt-3"><Banner msg={addMsg} onClose={() => setAddMsg(null)} /></div>}
					</div>
				)}

				<div className="bg-white rounded-2xl shadow-lg p-6">
					<div className="flex items-center justify-between mb-5">
						<div>
							<h1 className="text-2xl font-bold text-gray-800">Group</h1>
							<p className="text-sm text-gray-500 mt-0.5">View and manage customer groups</p>
						</div>
						<span className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm font-medium">
							Total: {total}
						</span>
					</div>

					<div className="flex gap-3 mb-5">
						<select value={searchBy} onChange={e => setSearchBy(e.target.value)}
							className="border border-gray-300 rounded-lg px-3 py-2.5 text-sm
                         focus:ring-2 focus:ring-blue-500 sm:w-40">
							<option value="1">Code</option>
							<option value="2">Group Name</option>
						</select>
						<div className="relative flex-1">
							<svg className="w-5 h-5 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2"
								fill="none" viewBox="0 0 24 24">
								<path fill="currentColor" d="M15.5 14H14.71L14.43 13.73C15.41 12.59 16 11.11 16
									9.5C16 5.91 13.09 3 9.5 3C5.91 3 3 5.91 3 9.5C3 13.09 5.91 16 9.5 16C11.11
									16 12.59 15.41 13.73 14.43L14 14.71V15.5L19 20.49L20.49 19L15.5 14ZM9.5 14C
									7.01 14 5 11.99 5 9.5C5 7.01 7.01 5 9.5 5C11.99 5 14 7.01 14 9.5C14 11.99
									11.99 14 9.5 14Z" />
							</svg>
							<input type="text" placeholder="Search…" value={searchVal}
								onChange={e => setSearchVal(e.target.value)}
								onKeyDown={e => e.key === "Enter" && handleSearch()}
								className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg text-sm
                           focus:ring-2 focus:ring-blue-500" />
						</div>
						<button onClick={handleSearch} disabled={loading}
							className="px-5 py-2.5 rounded-lg text-sm font-medium text-white
									bg-gradient-to-r from-blue-600 to-indigo-700
									hover:from-blue-700 hover:to-indigo-800 disabled:opacity-75 shadow-sm transition-all">
							{loading ? "Searching…" : "Search"}
						</button>
					</div>

					{listMsg && <div className="mb-4"><Banner msg={listMsg} onClose={() => setListMsg(null)} /></div>}

					<div className="overflow-x-auto rounded-xl border border-gray-200">
						<table className="w-full">
							<thead className="bg-gradient-to-r from-gray-50 to-gray-100">
								<tr>
									<th className="py-3 px-5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider w-28">Code</th>
									<th className="py-3 px-5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Group Name</th>
									<th className="py-3 px-5 text-center text-xs font-semibold text-gray-500 uppercase tracking-wider w-52">Action</th>
								</tr>
							</thead>
							<tbody className="divide-y divide-gray-100">
								{groups.length === 0 && !loading ? (
									<tr><td colSpan={3} className="py-12 text-center text-gray-400">
										<div className="flex flex-col items-center gap-2">
											<svg className="w-12 h-12 text-gray-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
													d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
											</svg>
											<p className="font-medium">No group records found</p>
											<p className="text-sm">Try adjusting your search</p>
										</div>
									</td></tr>
								) : (
									<>
										{groups.map((row, idx) => (
											<tr key={row.GrpCode}
												className={`hover:bg-blue-50 transition-colors ${idx % 2 === 0 ? "bg-white" : "bg-gray-50"}`}>
												<td className="py-3 px-5 text-sm font-mono font-semibold text-gray-800">{row.GrpCode}</td>
												<td className="py-3 px-5 text-sm text-gray-700">{row.GrpName}</td>
												<td className="py-3 px-5">
													<div className="flex justify-center gap-2 flex-wrap">
														<button onClick={() => navigate(`/group-member?grpcode=${row.GrpCode}`)}
															className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs
																font-semibold bg-indigo-600 hover:bg-indigo-700 text-white
																shadow-sm transition-all">
															<svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
																<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
																	d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
															</svg>
															Member
														</button>

														{akses === "9" && (
															<>
																<button onClick={() => openEdit(row.GrpCode)}
																	className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs
																		font-semibold bg-blue-600 hover:bg-blue-700 text-white
																		shadow-sm transition-all">
																	<svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
																		<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
																			d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
																	</svg>
																	Edit
																</button>
																<button onClick={() => handleDelete(row)}
																	className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs
																		font-semibold bg-red-50 hover:bg-red-100 text-red-600
																		border border-red-200 hover:border-red-300 shadow-sm transition-all">
																	<svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
																		<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
																			d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
																	</svg>
																	Delete
																</button>
															</>
														)}
													</div>
												</td>
											</tr>
										))}
										{loading && (
											<tr><td colSpan={3} className="py-4 text-center">
												<div className="flex justify-center">
													<svg className="animate-spin h-5 w-5 text-blue-500" fill="none" viewBox="0 0 24 24">
														<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
														<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
													</svg>
												</div>
											</td></tr>
										)}
									</>
								)}
							</tbody>
						</table>
					</div>

					{!loading && total > 0 && (
						<Pagination page={page} totalPages={totalPages} onPageChange={setPage}
							totalItems={total} itemsPerPage={limit} className="mt-5" />
					)}
				</div>
			</div>

			{editOpen && (
				<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
					onClick={e => e.target === e.currentTarget && setEditOpen(false)}>
					<div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg animate-in slide-in-from-top-4">
						<div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
							<h2 className="font-semibold text-gray-800">Edit Group</h2>
							<button onClick={() => setEditOpen(false)}
								className="text-gray-400 hover:text-gray-600 text-2xl leading-none">×</button>
						</div>
						<div className="px-6 py-5 space-y-4">
							<div>
								<label className="block text-xs font-medium text-gray-500 mb-1">Group Code</label>
								<input readOnly value={editCode}
									className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm bg-gray-100 font-mono" />
							</div>
							<div className="grid grid-cols-2 gap-3">
								<div>
									<label className="block text-xs font-medium text-gray-500 mb-1">Group SIPP</label>
									<select value={editSipp} onChange={e => setEditSipp(e.target.value)}
										className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500">
										<option value="">Select…</option>
										{sippOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
									</select>
								</div>
								<div>
									<label className="block text-xs font-medium text-gray-500 mb-1">Group SLIK</label>
									<select value={editSlik} onChange={e => setEditSlik(e.target.value)}
										className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500">
										<option value="">Select…</option>
										{slikOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
									</select>
								</div>
							</div>
							<div>
								<label className="block text-xs font-medium text-gray-500 mb-1">Group Name *</label>
								<input maxLength={100} autoFocus value={editName} onChange={e => setEditName(e.target.value)}
									className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500" />
							</div>
							<div>
								<label className="block text-xs font-medium text-gray-500 mb-1">Group Description *</label>
								<input value={editDesc} onChange={e => setEditDesc(e.target.value)}
									className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500" />
							</div>
							<div>
								<label className="block text-xs font-medium text-gray-500 mb-1">Group Type *</label>
								<select value={editType} onChange={e => setEditType(e.target.value)}
									className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500">
									<option value="">Select…</option>
									{GROUP_TYPES.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
								</select>
							</div>
							{editMsg && <Banner msg={editMsg} onClose={() => setEditMsg(null)} />}
						</div>
						<div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
							<button onClick={() => setEditOpen(false)}
								className="px-4 py-2 text-sm border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">
								Cancel
							</button>
							<button onClick={handleUpdate} disabled={editSaving}
								className="px-4 py-2 text-sm rounded-lg font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-60">
								{editSaving ? "Saving…" : "Save"}
							</button>
						</div>
					</div>
				</div>
			)}
		</div>
	);
};

export default GroupPage;