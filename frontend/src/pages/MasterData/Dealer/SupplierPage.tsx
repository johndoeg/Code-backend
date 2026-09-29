import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import api from "../../../api/axiosInstance";
import Pagination from "../../../helpers/Pagination";
import { DEFAULT_PAGE_LIMIT } from "../../../constants/DefaultValue";
interface Dealer {
	SUPP: string;
	NAME: string;
	NICKNAME: string;
	ADDRESS: string;
}
interface DeleteState {
	supp: string;
	reason: string;
	saving: boolean;
	error: string;
}

const Spinner: React.FC<{ small?: boolean }> = ({ small }) => (
	<svg
		className={`animate-spin ${small ? "h-4 w-4" : "h-6 w-6"} text-blue-600`}
		fill="none" viewBox="0 0 24 24"
	>
		<circle className="opacity-25" cx="12" cy="12" r="10"
			stroke="currentColor" strokeWidth="4" />
		<path className="opacity-75" fill="currentColor"
			d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
	</svg>
);

const SupplierPage: React.FC = () => {
	const navigate = useNavigate();

	const [dealers, setDealers] = useState<Dealer[]>([]);
	const [search, setSearch] = useState("");
	const [searchBy, setSearchBy] = useState("");
	const [page, setPage] = useState(1);
	const [total, setTotal] = useState(0);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [akses, setAkses] = useState("0");
	const [username, setUsername] = useState("");

	const [del, setDel] = useState<DeleteState | null>(null);
	const [delSuccess, setDelSuccess] = useState<string | null>(null);

	const limit = DEFAULT_PAGE_LIMIT;

	const fetchDealers = useCallback(async () => {
		setLoading(true);
		setError(null);
		setDelSuccess(null);
		try {
			const r = await api.get("/MasterData/api/dealer", {
				params: { search_val: search, search_by: searchBy, page, limit },
			});
			setDealers(r.data.data || []);
			setTotal(r.data.total || 0);
			setAkses(r.data.akses || "0");
			setUsername(r.data.username || "");
		} catch {
			setError("Failed to load dealer data. Please try again.");
		} finally {
			setLoading(false);
		}
	}, [search, searchBy, page, limit]);

	useEffect(() => { fetchDealers(); }, [fetchDealers]);

	const openDelete = (supp: string) =>
		setDel({ supp, reason: "", saving: false, error: "" });

	const closeDelete = () => setDel(null);

	const confirmDelete = async () => {
		if (!del) return;
		if (!del.reason.trim()) {
			setDel(d => d ? { ...d, error: "Please fill in the reason for deletion." } : d);
			return;
		}
		setDel(d => d ? { ...d, saving: true, error: "" } : d);
		try {
			const r = await api.delete(`/MasterData/api/dealer/${del.supp}`, {
				data: { reason: del.reason },
			});
			if (r.data.success) {
				setDel(null);
				setDelSuccess(`Dealer ${del.supp} deleted successfully.`);
				fetchDealers();
			} else {
				setDel(d => d ? { ...d, saving: false, error: r.data.message || "Delete failed." } : d);
			}
		} catch {
			setDel(d => d ? { ...d, saving: false, error: "An error occurred. Please try again." } : d);
		}
	};

	const totalPages = Math.ceil(total / limit);

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-7xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6 mb-6">

					<div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
						<div>
							<h1 className="text-2xl md:text-3xl font-bold text-gray-800">Dealer</h1>
							<p className="text-gray-600 mt-1">View and manage dealer records</p>
						</div>
						<div className="flex items-center gap-3">
							<span className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm font-medium">
								Total: {total}
							</span>
							{akses === "9" && (
								<button
									onClick={() => navigate(`/supplier-entry?id=AddCF&akses=${akses}`)}
									className="bg-gradient-to-r from-green-600 to-emerald-700 hover:from-green-700
										hover:to-emerald-800 text-white px-5 py-2.5 rounded-lg font-medium
										shadow-md hover:shadow-lg transition-all text-sm"
								>
									+ Add New
								</button>
							)}
						</div>
					</div>

					<div className="flex flex-col md:flex-row gap-3 mb-6">
						<select
							value={searchBy}
							onChange={e => { setSearchBy(e.target.value); setPage(1); }}
							className="border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 md:w-40"
						>
							<option value="">All Fields</option>
							<option value="1">Dealer ID</option>
							<option value="2">Name</option>
							<option value="3">Nickname</option>
						</select>

						<div className="relative flex-1">
							<input
								type="text"
								placeholder="Search dealer…"
								value={search}
								onChange={e => { setSearch(e.target.value); setPage(1); }}
								onKeyDown={e => e.key === "Enter" && fetchDealers()}
								className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg
                           				focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all text-sm"
							/>
							<svg className="w-5 h-5 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2"
								fill="none" viewBox="0 0 24 24">
								<path d="M15.5 14H14.71L14.43 13.73C15.41 12.59 16 11.11 16 9.5C16 5.91 13.09 3 9.5 3C5.91 3 3 5.91 3 9.5C3 13.09 5.91 16 9.5 16C11.11 16 12.59 15.41 13.73 14.43L14 14.71V15.5L19 20.49L20.49 19L15.5 14ZM9.5 14C7.01 14 5 11.99 5 9.5C5 7.01 7.01 5 9.5 5C11.99 5 14 7.01 14 9.5C14 11.99 11.99 14 9.5 14Z"
									fill="currentColor" />
							</svg>
						</div>

						<button
							onClick={() => { setPage(1); fetchDealers(); }}
							disabled={loading}
							className="bg-gradient-to-r from-blue-600 to-indigo-700 hover:from-blue-700
								hover:to-indigo-800 text-white px-5 py-2.5 rounded-lg font-medium
								shadow-md hover:shadow-lg transition-all flex items-center gap-2
								text-sm disabled:opacity-75 disabled:cursor-not-allowed"
						>
							{loading ? <><Spinner small /> Searching…</> : "Search"}
						</button>
					</div>

					{error && (
						<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
							{error}
							<button onClick={fetchDealers} className="ml-4 font-medium underline">Retry</button>
						</div>
					)}
					{delSuccess && (
						<div className="mb-4 p-4 bg-green-50 border border-green-200 rounded-lg text-green-700 text-sm">
							{delSuccess}
						</div>
					)}

					<div className="overflow-x-auto rounded-lg border border-gray-200">
						<table className="w-full">
							<thead className="bg-gradient-to-r from-gray-50 to-gray-100">
								<tr>
									{["Dealer ID", "Name", "Nickname", "Address", "Actions"].map(h => (
										<th key={h}
											className="py-3 px-5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
											{h}
										</th>
									))}
								</tr>
							</thead>
							<tbody className="divide-y divide-gray-100">
								{dealers.length === 0 && !loading ? (
									<tr>
										<td colSpan={5} className="py-10 px-6 text-center text-gray-500">
											<div className="flex flex-col items-center gap-2">
												<svg className="w-12 h-12 text-gray-300" fill="none"
													stroke="currentColor" viewBox="0 0 24 24">
													<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
														d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
												</svg>
												<p>No dealer records found</p>
												<p className="text-sm text-gray-400">Try adjusting your search</p>
											</div>
										</td>
									</tr>
								) : (
									<>
										{dealers.map((d, idx) => (
											<tr key={d.SUPP}
												className={`hover:bg-blue-50 transition-colors ${idx % 2 === 0 ? "bg-white" : "bg-gray-50"}`}>
												<td className="py-3 px-5 text-sm font-mono font-medium text-gray-900">
													{d.SUPP}
												</td>
												<td className="py-3 px-5 text-sm font-medium text-gray-800">{d.NAME}</td>
												<td className="py-3 px-5 text-sm text-gray-600">{d.NICKNAME}</td>
												<td className="py-3 px-5 text-sm text-gray-500 max-w-xs truncate">{d.ADDRESS}</td>
												<td className="py-3 px-5 whitespace-nowrap">
													<div className="flex items-center gap-2">
														{akses === "9" ? (
															<>
																<button
																	onClick={() => navigate(`/supplier-entry?id=Edit&supp=${d.SUPP}&akses=${akses}`)}
																	className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-semibold
																		bg-blue-600 hover:bg-blue-700 active:bg-blue-800
																		text-white shadow-sm hover:shadow transition-all"
																>
																	<svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
																		<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
																			d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
																	</svg>
																	Edit
																</button>
																<button
																	onClick={() => navigate(`/supplier-entry?id=View&supp=${d.SUPP}&akses=${akses}`)}
																	className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-semibold
																		bg-gray-100 hover:bg-gray-200 active:bg-gray-300
																		text-gray-700 shadow-sm hover:shadow transition-all"
																>
																	<svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
																		<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
																			d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
																		<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
																			d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
																	</svg>
																	View
																</button>
																<button
																	onClick={() => openDelete(d.SUPP)}
																	className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-semibold
																		bg-red-50 hover:bg-red-100 active:bg-red-200
																		text-red-600 hover:text-red-700 border border-red-200
																		hover:border-red-300 shadow-sm transition-all"
																>
																	<svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
																		<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
																			d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
																	</svg>
																	Delete
																</button>
															</>
														) : (
															<button
																onClick={() => navigate(`/supplier-entry?id=View&supp=${d.SUPP}&akses=${akses}`)}
																className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-semibold
																		bg-gray-100 hover:bg-gray-200 active:bg-gray-300
																		text-gray-700 shadow-sm hover:shadow transition-all"
															>
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
											<tr>
												<td colSpan={5} className="py-4 text-center">
													<div className="flex justify-center"><Spinner /></div>
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
							page={page} totalPages={totalPages}
							onPageChange={setPage}
							totalItems={total} itemsPerPage={limit}
							className="mt-6"
						/>
					)}
				</div>
			</div>

			{del && (
				<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
					onClick={e => e.target === e.currentTarget && closeDelete()}>
					<div className="bg-white rounded-2xl shadow-2xl w-full max-w-md animate-in slide-in-from-top-4">
						<div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
							<h2 className="font-semibold text-gray-800">Delete Dealer</h2>
							<button onClick={closeDelete}
								className="text-gray-400 hover:text-gray-600 text-2xl leading-none">&times;</button>
						</div>
						<div className="px-6 py-5 space-y-4">
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">
									Dealer ID
								</label>
								<input type="text" readOnly value={del.supp}
									className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-gray-50 font-mono" />
							</div>
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">
									Reason for Delete <span className="text-red-500">*</span>
								</label>
								<textarea
									rows={4}
									value={del.reason}
									onChange={e => setDel(d => d ? { ...d, reason: e.target.value, error: "" } : d)}
									className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-red-400 focus:border-red-400 resize-none"
									placeholder="Enter reason…"
								/>
							</div>
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Delete By</label>
								<input type="text" readOnly value={username}
									className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-gray-50" />
							</div>
							{del.error && (
								<p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
									{del.error}
								</p>
							)}
						</div>
						<div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
							<button onClick={closeDelete}
								className="px-4 py-2 text-sm border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors">
								Cancel
							</button>
							<button
								onClick={confirmDelete}
								disabled={del.saving}
								className="px-4 py-2 text-sm bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium transition-colors disabled:opacity-60 flex items-center gap-2"
							>
								{del.saving ? <><Spinner small /> Deleting…</> : "Delete"}
							</button>
						</div>
					</div>
				</div>
			)}
		</div>
	);
};

export default SupplierPage;