import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import api from "../../../api/axiosInstance";
import Pagination from "../../../helpers/Pagination";
import { DEFAULT_PAGE_LIMIT } from "../../../constants/DefaultValue";

interface Insurance { INS_CD: string; INS_CO: string; }
interface Msg { type: "success" | "error"; text: string; }

type SearchBy = "1" | "2";

const InsurancePage: React.FC = () => {
	const navigate = useNavigate();

	const [insurances, setInsurances] = useState<Insurance[]>([]);
	const [total, setTotal] = useState(0);
	const [page, setPage] = useState(1);
	const [loading, setLoading] = useState(false);
	const [listMsg, setListMsg] = useState<Msg | null>(null);
	const [akses, setAkses] = useState("0");
	const limit = DEFAULT_PAGE_LIMIT;

	const [searchBy, setSearchBy] = useState<SearchBy>("1");
	const [searchVal, setSearchVal] = useState("");
	const [appliedSearchBy, setAppliedSearchBy] = useState<SearchBy>("1");
	const [appliedSearchVal, setAppliedSearchVal] = useState("");

	const [deleteTarget, setDeleteTarget] = useState<Insurance | null>(null);
	const [deleteLoading, setDeleteLoading] = useState(false);

	const fetchInsurance = useCallback(async () => {
		setLoading(true);
		setListMsg(null);
		try {
			const r = await api.get("/MasterData/api/insurance", {
				params: {
					search_by: appliedSearchBy, search_val: appliedSearchVal, page, limit,
				},
			});
			setInsurances(r.data.data || []);
			setTotal(r.data.total || 0);
			setAkses(r.data.akses || "0");
		} catch {
			setListMsg({ type: "error", text: "Failed to load insurance data." });
		} finally {
			setLoading(false);
		}
	}, [appliedSearchBy, appliedSearchVal, page, limit]);

	useEffect(() => { fetchInsurance(); }, [fetchInsurance]);

	const handleSearch = () => {
		setAppliedSearchBy(searchBy);
		setAppliedSearchVal(searchVal);
		setPage(1);
	};

	const handleDelete = async () => {
		if (!deleteTarget) return;
		setDeleteLoading(true);
		try {
			const r = await api.delete(`/MasterData/api/insurance/${deleteTarget.INS_CD}`);
			if (r.data.success) {
				setDeleteTarget(null);
				setListMsg({ type: "success", text: `Insurance ${deleteTarget.INS_CD} deleted.` });
				if (insurances.length === 1 && page > 1) setPage(p => p - 1);
				else fetchInsurance();
			} else {
				setListMsg({ type: "error", text: r.data.message || "Delete failed." });
				setDeleteTarget(null);
			}
		} catch {
			setListMsg({ type: "error", text: "Delete failed. Please try again." });
			setDeleteTarget(null);
		} finally {
			setDeleteLoading(false);
		}
	};

	const totalPages = Math.ceil(total / limit);

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-6xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6">

					<div className="flex items-center justify-between mb-6">
						<div>
							<h1 className="text-2xl font-bold text-gray-800">Insurance</h1>
							<p className="text-sm text-gray-500 mt-0.5">
								View and manage insurance records
							</p>
						</div>
						<div className="flex items-center gap-3">
							<span className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm font-medium">
								Total: {total}
							</span>
							{akses === "9" && (
								<button
									onClick={() => navigate(`/ins-company?id=Add&akses=${akses}`)}
									className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm
										font-semibold text-white bg-green-600 hover:bg-green-700
										active:bg-green-800 shadow-sm transition-all"
								>
									<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
									</svg>
									Add
								</button>
							)}
						</div>
					</div>

					<div className="flex gap-3 mb-5">
						<select value={searchBy} onChange={e => setSearchBy(e.target.value as SearchBy)}
							className="border border-gray-300 rounded-lg px-3 py-2.5 text-sm
                         focus:ring-2 focus:ring-blue-500 sm:w-48">
							<option value="1">Insurance Code</option>
							<option value="2">Insurance Company</option>
						</select>
						<div className="relative flex-1">
							<svg className="w-5 h-5 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2"
								fill="none" viewBox="0 0 24 24">
								<path fill="currentColor" d="M15.5 14H14.71L14.43 13.73C15.41 12.59 16 11.11 16
									9.5C16 5.91 13.09 3 9.5 3C5.91 3 3 5.91 3 9.5C3 13.09 5.91 16 9.5 16C11.11
									16 12.59 15.41 13.73 14.43L14 14.71V15.5L19 20.49L20.49 19L15.5 14ZM9.5
									14C7.01 14 5 11.99 5 9.5C5 7.01 7.01 5 9.5 5C11.99 5 14 7.01 14 9.5C14
									11.99 11.99 14 9.5 14Z" />
							</svg>
							<input type="text"
								placeholder={searchBy === "1" ? "Search by code…" : "Search by company…"}
								value={searchVal}
								onChange={e => setSearchVal(e.target.value)}
								onKeyDown={e => e.key === "Enter" && handleSearch()}
								className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg text-sm
                           focus:ring-2 focus:ring-blue-500" />
						</div>
						<button onClick={handleSearch} disabled={loading}
							className="px-5 py-2.5 rounded-lg text-sm font-medium text-white
									bg-gradient-to-r from-blue-600 to-indigo-700
									hover:from-blue-700 hover:to-indigo-800 disabled:opacity-75
									shadow-sm transition-all">
							{loading ? "Searching…" : "Search"}
						</button>
					</div>

					{listMsg && (
						<div className={`mb-4 flex items-center justify-between p-3 rounded-lg text-sm border ${listMsg.type === "success"
							? "bg-green-50 border-green-200 text-green-700"
							: "bg-red-50   border-red-200   text-red-700"
							}`}>
							<span>{listMsg.text}</span>
							<button onClick={() => setListMsg(null)}
								className="ml-4 opacity-60 hover:opacity-100 text-lg leading-none">×</button>
						</div>
					)}

					<div className="overflow-x-auto rounded-xl border border-gray-200">
						<table className="w-full">
							<thead className="bg-gradient-to-r from-gray-50 to-gray-100">
								<tr>
									<th className="py-3 px-5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider w-36">
										Insurance Code
									</th>
									<th className="py-3 px-5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
										Insurance Company
									</th>
									<th className="py-3 px-5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider w-48">
										Actions
									</th>
								</tr>
							</thead>
							<tbody className="divide-y divide-gray-100">
								{insurances.length === 0 && !loading ? (
									<tr>
										<td colSpan={3} className="py-12 text-center text-gray-400">
											<div className="flex flex-col items-center gap-2">
												<svg className="w-12 h-12 text-gray-200" fill="none"
													stroke="currentColor" viewBox="0 0 24 24">
													<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
														d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
												</svg>
												<p className="font-medium">No insurance records found</p>
												<p className="text-sm">Try adjusting your search</p>
											</div>
										</td>
									</tr>
								) : (
									<>
										{insurances.map((ins, idx) => (
											<tr key={ins.INS_CD}
												className={`hover:bg-blue-50 transition-colors ${idx % 2 === 0 ? "bg-white" : "bg-gray-50"}`}>
												<td className="py-3 px-5 text-sm font-mono font-semibold text-gray-800">
													{ins.INS_CD}
												</td>
												<td className="py-3 px-5 text-sm text-gray-700">{ins.INS_CO}</td>
												<td className="py-3 px-5">
													<div className="flex items-center gap-2">
														{akses === "9" ? (
															<>
																<button
																	onClick={() => navigate(`/ins-company?id=Edit&ins_cd=${ins.INS_CD}&akses=${akses}`)}
																	className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md
																		text-xs font-semibold bg-blue-600 hover:bg-blue-700
																		active:bg-blue-800 text-white shadow-sm transition-all">
																	<svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
																		<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
																			d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
																	</svg>
																	Edit
																</button>
																<button
																	onClick={() => setDeleteTarget(ins)}
																	className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md
																		text-xs font-semibold bg-red-50 hover:bg-red-100
																		active:bg-red-200 text-red-600 border border-red-200
																		hover:border-red-300 shadow-sm transition-all">
																	<svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
																		<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
																			d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
																	</svg>
																	Delete
																</button>
															</>
														) : (
															<button
																onClick={() => navigate(`/ins-company?id=View&ins_cd=${ins.INS_CD}&akses=${akses}`)}
																className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md
																	text-xs font-semibold bg-gray-100 hover:bg-gray-200
																	active:bg-gray-300 text-gray-700 shadow-sm transition-all">
																<svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
																	<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
																		d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
																	<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
																		d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
																</svg>
																View
															</button>
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

			{deleteTarget && (
				<div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
					<div className="bg-white rounded-2xl shadow-2xl p-6 max-w-sm w-full">
						<div className="flex items-center gap-3 mb-4">
							<div className="bg-red-100 p-2 rounded-full">
								<svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
										d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
								</svg>
							</div>
							<h2 className="text-lg font-semibold text-gray-800">Confirm Delete</h2>
						</div>
						<p className="text-gray-600 mb-6">
							Delete insurance{" "}
							<span className="font-semibold text-gray-800">{deleteTarget.INS_CD} – {deleteTarget.INS_CO}</span>?
							This will also remove all associated premium, clause, and liability records.
						</p>
						<div className="flex gap-3 justify-end">
							<button onClick={() => setDeleteTarget(null)} disabled={deleteLoading}
								className="px-4 py-2 rounded-lg border border-gray-300 text-gray-700
                           hover:bg-gray-50 text-sm font-medium transition-all">
								Cancel
							</button>
							<button onClick={handleDelete} disabled={deleteLoading}
								className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white
                           text-sm font-medium shadow transition-all disabled:opacity-75
                           flex items-center gap-2">
								{deleteLoading ? (
									<>
										<svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
											<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
											<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
										</svg>
										Deleting…
									</>
								) : "Delete"}
							</button>
						</div>
					</div>
				</div>
			)}
		</div>
	);
};

export default InsurancePage;