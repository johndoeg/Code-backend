import React, { useEffect, useState, useCallback, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import api from "../../../api/axiosInstance";
import Pagination from "../../../helpers/Pagination";
import { DEFAULT_PAGE_LIMIT } from "../../../constants/DefaultValue";

interface GroupInfo {
	grpcode: string; grpname: string;
	sipp_code: string; sipp_desc: string;
	slik_code: string; slik_desc: string;
}
interface Member { APLESS: string; LESSEE_NM: string; address: string; }
interface Customer { APLESS: string; LESSEE_NM: string; address: string; GrpCode: string; }
interface Msg { type: "success" | "error"; text: string; }

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

const GroupMemberPage: React.FC = () => {
	const navigate = useNavigate();
	const [searchParams] = useSearchParams();
	const grpcode = searchParams.get("grpcode") || "";

	const [info, setInfo] = useState<GroupInfo | null>(null);
	const [akses, setAkses] = useState("0");

	const [members, setMembers] = useState<Member[]>([]);
	const [total, setTotal] = useState(0);
	const [page, setPage] = useState(1);
	const [loading, setLoading] = useState(false);
	const [listMsg, setListMsg] = useState<Msg | null>(null);
	const limit = DEFAULT_PAGE_LIMIT;

	const [searchName, setSearchName] = useState("");
	const [appliedSearchName, setAppliedSearchName] = useState("");

	const [custSearch, setCustSearch] = useState("");
	const [custResults, setCustResults] = useState<Customer[]>([]);
	const [custSearching, setCustSearching] = useState(false);
	const [selectedCust, setSelectedCust] = useState<Customer | null>(null);
	const [addSaving, setAddSaving] = useState(false);
	const [addMsg, setAddMsg] = useState<Msg | null>(null);
	const searchDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);

	useEffect(() => {
		if (!grpcode) return;
		api.get(`/MasterData/api/group/${grpcode}`)
			.then(r => setInfo(r.data))
			.catch(() => setListMsg({ type: "error", text: "Failed to load group info." }));
	}, [grpcode]);

	const fetchMembers = useCallback(async () => {
		if (!grpcode) return;
		setLoading(true); setListMsg(null);
		try {
			const r = await api.get(`/MasterData/api/group/${grpcode}/members`, {
				params: { lessee_nm: appliedSearchName, page, limit },
			});
			setMembers(r.data.data || []);
			setTotal(r.data.total || 0);
			setAkses(r.data.akses || "0");
		} catch { setListMsg({ type: "error", text: "Failed to load member data." }); }
		finally { setLoading(false); }
	}, [grpcode, appliedSearchName, page, limit]);

	useEffect(() => { fetchMembers(); }, [fetchMembers]);

	const handleSearch = () => { setAppliedSearchName(searchName); setPage(1); };

	const handleCustSearchChange = (val: string) => {
		setCustSearch(val);
		setSelectedCust(null);
		setCustResults([]);
		if (searchDebounce.current) clearTimeout(searchDebounce.current);
		if (val.length < 2) return;
		searchDebounce.current = setTimeout(async () => {
			setCustSearching(true);
			try {
				const r = await api.get("/MasterData/api/group/customer-search", { params: { q: val } });
				setCustResults(r.data.data || []);
			} catch {}
			finally { setCustSearching(false); }
		}, 400);
	};

	const selectCustomer = (c: Customer) => {
		setSelectedCust(c);
		setCustSearch(c.LESSEE_NM);
		setCustResults([]);
	};

	const handleAddMember = async () => {
		if (!selectedCust) {
			setAddMsg({ type: "error", text: "Please select a customer first." });
			return;
		}
		setAddSaving(true); setAddMsg(null);
		try {
			const r = await api.post(`/MasterData/api/group/${grpcode}/members`,
				{ apless: selectedCust.APLESS });
			if (r.data.success) {
				setAddMsg({ type: "success", text: `${selectedCust.LESSEE_NM} added to group.` });
				setSelectedCust(null); setCustSearch("");
				setPage(1); fetchMembers();
			} else {
				setAddMsg({ type: "error", text: r.data.message || "Add failed." });
			}
		} catch { setAddMsg({ type: "error", text: "An error occurred." }); }
		finally { setAddSaving(false); }
	};

	const handleRemoveMember = async (m: Member) => {
		if (!window.confirm(
			`Remove "${m.LESSEE_NM}" (${m.APLESS}) from this group?`
		)) return;
		try {
			const r = await api.delete(`/MasterData/api/group/${grpcode}/members/${m.APLESS}`);
			if (r.data.success) {
				setListMsg({ type: "success", text: `${m.LESSEE_NM} removed from group.` });
				if (members.length === 1 && page > 1) setPage(p => p - 1); else fetchMembers();
			} else {
				setListMsg({ type: "error", text: r.data.message || "Remove failed." });
			}
		} catch { setListMsg({ type: "error", text: "Remove failed." }); }
	};

	const totalPages = Math.ceil(total / limit);

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-6xl mx-auto space-y-5">

				<div className="flex items-center justify-between">
					<div>
						<h1 className="text-xl font-bold text-gray-800">
							Group Member — <span className="text-blue-700">{info?.grpname || grpcode}</span>
						</h1>
						<p className="text-sm text-gray-500 mt-0.5">Manage members of this group</p>
					</div>
					<button onClick={() => navigate("/group-entry")}
						className="px-4 py-2 text-sm border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">
						← Back to Group
					</button>
				</div>

				{info && (
					<div className="bg-white rounded-2xl shadow-lg p-5">
						<h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">
							Group Information
						</h2>
						<div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
							<div>
								<p className="text-xs font-medium text-gray-500 mb-1">Group Name</p>
								<p className="text-sm font-medium text-gray-800 bg-gray-50 border
                              border-gray-200 rounded-lg px-3 py-2.5">
									{info.grpname}
								</p>
							</div>
							<div>
								<p className="text-xs font-medium text-gray-500 mb-1">Group SIPP</p>
								<p className="text-sm text-gray-700 bg-gray-50 border
                              border-gray-200 rounded-lg px-3 py-2.5 truncate"
									title={info.sipp_desc || info.sipp_code}>
									{info.sipp_desc || info.sipp_code || "—"}
								</p>
							</div>
							<div>
								<p className="text-xs font-medium text-gray-500 mb-1">Group SLIK</p>
								<p className="text-sm text-gray-700 bg-gray-50 border
                              border-gray-200 rounded-lg px-3 py-2.5 truncate"
									title={info.slik_desc || info.slik_code}>
									{info.slik_desc || info.slik_code || "—"}
								</p>
							</div>
						</div>
					</div>
				)}

				{akses === "9" && (
					<div className="bg-white rounded-2xl shadow-lg p-6">
						<h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-4">
							Add Member
						</h2>
						<p className="text-xs text-gray-500 mb-3">
							Type at least 2 characters to search customers
						</p>
						<div className="relative">
							<input
								type="text"
								placeholder="Search customer by name…"
								value={custSearch}
								onChange={e => handleCustSearchChange(e.target.value)}
								className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 pr-8"
							/>
							{custSearching && (
								<svg className="animate-spin w-4 h-4 text-blue-500 absolute right-3 top-3"
									fill="none" viewBox="0 0 24 24">
									<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
									<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
								</svg>
							)}

							{custResults.length > 0 && (
								<div className="absolute z-20 w-full top-full mt-1 bg-white rounded-xl
                                shadow-lg border border-gray-200 max-h-60 overflow-y-auto">
									{custResults.map(c => (
										<button key={c.APLESS} onClick={() => selectCustomer(c)}
											className={`w-full text-left px-4 py-3 hover:bg-blue-50 transition-colors
                                  				border-b border-gray-100 last:border-0 ${c.GrpCode ? "opacity-60" : ""}`}>
											<div className="flex items-center justify-between">
												<div>
													<p className="text-sm font-medium text-gray-800">{c.LESSEE_NM}</p>
													<p className="text-xs text-gray-500 mt-0.5">{c.APLESS} · {c.address}</p>
												</div>
												{c.GrpCode && (
													<span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full shrink-0 ml-2">
														Group {c.GrpCode}
													</span>
												)}
											</div>
										</button>
									))}
								</div>
							)}
						</div>

						{selectedCust && (
							<div className="mt-3 p-3 bg-blue-50 border border-blue-200 rounded-lg flex
                              items-center justify-between">
								<div>
									<p className="text-sm font-medium text-blue-800">{selectedCust.LESSEE_NM}</p>
									<p className="text-xs text-blue-600 mt-0.5">{selectedCust.APLESS}</p>
								</div>
								<button onClick={() => { setSelectedCust(null); setCustSearch(""); }}
									className="text-blue-400 hover:text-blue-600 text-lg leading-none">×</button>
							</div>
						)}

						<div className="mt-3 flex items-center gap-3">
							<button onClick={handleAddMember} disabled={addSaving || !selectedCust}
								className="px-5 py-2 text-sm rounded-lg font-semibold text-white bg-blue-600
                           			hover:bg-blue-700 disabled:opacity-50 transition-colors shadow-sm">
								{addSaving ? "Saving…" : "Save"}
							</button>
							<button onClick={() => navigate("/group-entry")}
								className="px-4 py-2 text-sm border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">
								Cancel
							</button>
						</div>
						{addMsg && <div className="mt-3"><Banner msg={addMsg} onClose={() => setAddMsg(null)} /></div>}
					</div>
				)}

				<div className="bg-white rounded-2xl shadow-lg p-6">
					<div className="flex items-center justify-between mb-5">
						<h2 className="text-lg font-bold text-gray-800">Members</h2>
						<span className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm font-medium">
							Total: {total}
						</span>
					</div>

					<div className="flex gap-3 mb-5">
						<div className="relative flex-1">
							<svg className="w-5 h-5 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2"
								fill="none" viewBox="0 0 24 24">
								<path fill="currentColor" d="M15.5 14H14.71L14.43 13.73C15.41 12.59 16 11.11 16
									9.5C16 5.91 13.09 3 9.5 3C5.91 3 3 5.91 3 9.5C3 13.09 5.91 16 9.5 16C11.11
									16 12.59 15.41 13.73 14.43L14 14.71V15.5L19 20.49L20.49 19L15.5 14ZM9.5 14C
									7.01 14 5 11.99 5 9.5C5 7.01 7.01 5 9.5 5C11.99 5 14 7.01 14 9.5C14 11.99
									11.99 14 9.5 14Z"/>
							</svg>
							<input type="text" placeholder="Customer Name…" value={searchName}
								onChange={e => setSearchName(e.target.value)}
								onKeyDown={e => e.key === "Enter" && handleSearch()}
								className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg text-sm
                           focus:ring-2 focus:ring-blue-500"/>
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
									<th className="py-3 px-5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider w-36">Customer No.</th>
									<th className="py-3 px-5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Customer Name</th>
									<th className="py-3 px-5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Address</th>
									{akses === "9" && (
										<th className="py-3 px-5 text-center text-xs font-semibold text-gray-500 uppercase tracking-wider w-24">Action</th>
									)}
								</tr>
							</thead>
							<tbody className="divide-y divide-gray-100">
								{members.length === 0 && !loading ? (
									<tr><td colSpan={akses === "9" ? 4 : 3} className="py-12 text-center text-gray-400">
										<div className="flex flex-col items-center gap-2">
											<svg className="w-12 h-12 text-gray-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
													d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
											</svg>
											<p className="font-medium">No members found</p>
											<p className="text-sm">Try adjusting your search</p>
										</div>
									</td></tr>
								) : (
									<>
										{members.map((m, idx) => (
											<tr key={m.APLESS}
												className={`hover:bg-blue-50 transition-colors ${idx % 2 === 0 ? "bg-white" : "bg-gray-50"}`}>
												<td className="py-3 px-5 text-sm font-mono font-medium text-gray-800">{m.APLESS}</td>
												<td className="py-3 px-5 text-sm text-gray-700">{m.LESSEE_NM}</td>
												<td className="py-3 px-5 text-sm text-gray-600">{m.address}</td>
												{akses === "9" && (
													<td className="py-3 px-5 text-center">
														<button onClick={() => handleRemoveMember(m)}
															className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs
																font-semibold bg-red-50 hover:bg-red-100 text-red-600
																border border-red-200 hover:border-red-300 shadow-sm transition-all">
															<svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
																<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
																	d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
															</svg>
															Delete
														</button>
													</td>
												)}
											</tr>
										))}
										{loading && (
											<tr><td colSpan={akses === "9" ? 4 : 3} className="py-4 text-center">
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
		</div>
	);
};

export default GroupMemberPage;