import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import api from "../../../../api/axiosInstance";
import Pagination from "../../../../helpers/Pagination";
import { DEFAULT_PAGE_LIMIT } from "../../../../constants/DefaultValue";

interface Brand { BRAND: string; BRAND_NM: string; BRAND_COUNTRY: string; }
interface Msg { type: "success" | "error"; text: string; }

function Banner({ msg, onClose }: { msg: Msg; onClose: () => void }) {
	return (
		<div className={`flex items-start gap-3 rounded-lg px-4 py-3 text-sm border ${msg.type === "success"
			? "bg-green-50 border-green-200 text-green-700"
			: "bg-red-50   border-red-200   text-red-700"
			}`}>
			<span className="flex-1">{msg.text}</span>
			<button onClick={onClose}
				className="text-lg leading-none opacity-60 hover:opacity-100">×</button>
		</div>
	);
}

const BrandPage: React.FC = () => {
	const navigate = useNavigate();

	const [brands, setBrands] = useState<Brand[]>([]);
	const [total, setTotal] = useState(0);
	const [page, setPage] = useState(1);
	const [loading, setLoading] = useState(false);
	const [listMsg, setListMsg] = useState<Msg | null>(null);
	const [akses, setAkses] = useState("0");
	const limit = DEFAULT_PAGE_LIMIT;

	const [searchBy, setSearchBy] = useState("1");
	const [searchVal, setSearchVal] = useState("");
	const [appliedSearchBy, setAppliedSearchBy] = useState("1");
	const [appliedSearchVal, setAppliedSearchVal] = useState("");

	const [formBrand, setFormBrand] = useState("");
	const [formBrandNm, setFormBrandNm] = useState("");
	const [formCountry, setFormCountry] = useState("");
	const [saving, setSaving] = useState(false);
	const [addMsg, setAddMsg] = useState<Msg | null>(null);

	const [editRow, setEditRow] = useState<Brand | null>(null);
	const [editBrandNm, setEditBrandNm] = useState("");
	const [editCountry, setEditCountry] = useState("");
	const [editSaving, setEditSaving] = useState(false);
	const [editMsg, setEditMsg] = useState<Msg | null>(null);

	const fetchBrands = useCallback(async () => {
		setLoading(true);
		setListMsg(null);
		try {
			const r = await api.get("/MasterData/api/brand", {
				params: { search_val: appliedSearchVal, search_by: appliedSearchBy, page, limit },
			});
			setBrands(r.data.data || []);
			setTotal(r.data.total || 0);
			setAkses(r.data.akses || "0");
		} catch {
			setListMsg({ type: "error", text: "Failed to load brand data." });
		} finally {
			setLoading(false);
		}
	}, [appliedSearchVal, appliedSearchBy, page, limit]);

	useEffect(() => { fetchBrands(); }, [fetchBrands]);

	const handleSearch = () => {
		setAppliedSearchBy(searchBy);
		setAppliedSearchVal(searchVal);
		setPage(1);
	};

	const handleSave = async () => {
		setSaving(true);
		setAddMsg(null);
		try {
			const r = await api.post("/MasterData/api/brand", {
				brand: formBrand, brand_nm: formBrandNm, brand_country: formCountry,
			});
			if (r.data.success) {
				setAddMsg({ type: "success", text: "Brand saved successfully." });
				setFormBrand(""); setFormBrandNm(""); setFormCountry("");
				setPage(1);
				fetchBrands();
			} else {
				setAddMsg({ type: "error", text: r.data.message || "Save failed." });
			}
		} catch (err: any) {
			const msg = err.response?.data?.message;
			setAddMsg({
				type: "error",
				text: Array.isArray(msg) ? msg.join(", ") : "Save failed."
			});
		} finally {
			setSaving(false);
		}
	};

	const openEdit = (row: Brand) => {
		setEditRow(row);
		setEditBrandNm(row.BRAND_NM);
		setEditCountry(row.BRAND_COUNTRY);
		setEditMsg(null);
	};

	const handleUpdate = async () => {
		if (!editRow) return;
		if (!editBrandNm.trim() || !editCountry.trim()) {
			setEditMsg({ type: "error", text: "Brand Name and Country are required." });
			return;
		}
		setEditSaving(true);
		setEditMsg(null);
		try {
			const r = await api.put(`/MasterData/api/brand/${editRow.BRAND}`, {
				brand_nm: editBrandNm.trim(), brand_country: editCountry.trim(),
			});
			if (r.data.success) {
				setEditMsg({ type: "success", text: "Brand updated successfully." });
				fetchBrands();
				setTimeout(() => setEditRow(null), 800);
			} else {
				setEditMsg({ type: "error", text: r.data.message || "Update failed." });
			}
		} catch {
			setEditMsg({ type: "error", text: "An error occurred." });
		} finally {
			setEditSaving(false);
		}
	};

	const handleDelete = async (row: Brand) => {
		if (!window.confirm(
			`Delete brand "${row.BRAND} – ${row.BRAND_NM}"?\n\nThis will also remove all Vehicle Types.`
		)) return;
		try {
			const r = await api.delete(`/MasterData/api/brand/${row.BRAND}`);
			if (r.data.success) {
				setListMsg({ type: "success", text: `Brand ${row.BRAND} deleted.` });
				if (brands.length === 1 && page > 1) setPage(p => p - 1);
				else fetchBrands();
			} else {
				setListMsg({ type: "error", text: r.data.message || "Delete failed." });
			}
		} catch {
			setListMsg({ type: "error", text: "Delete failed." });
		}
	};

	const totalPages = Math.ceil(total / limit);

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-6xl mx-auto space-y-5">

				{akses === "9" && (
					<div className="bg-white rounded-2xl shadow-lg p-6">
						<h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-4">
							Add Brand
						</h2>
						<div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
							<div>
								<label className="block text-xs font-medium text-gray-500 mb-1">
									Brand Code <span className="text-red-500">*</span>
								</label>
								<input value={formBrand}
									onChange={e => setFormBrand(e.target.value)}
									placeholder="Code…"
									className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm
                             focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
							</div>
							<div>
								<label className="block text-xs font-medium text-gray-500 mb-1">
									Brand Name <span className="text-red-500">*</span>
								</label>
								<input value={formBrandNm}
									onChange={e => setFormBrandNm(e.target.value)}
									placeholder="Name…"
									className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm
                             focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
							</div>
							<div>
								<label className="block text-xs font-medium text-gray-500 mb-1">
									Brand Country <span className="text-red-500">*</span>
								</label>
								<input value={formCountry}
									onChange={e => setFormCountry(e.target.value)}
									onKeyDown={e => e.key === "Enter" && handleSave()}
									placeholder="Country…"
									className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm
                             focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
							</div>
						</div>
						<div className="mt-4">
							<button onClick={handleSave} disabled={saving}
								className="px-5 py-2.5 rounded-lg text-sm font-semibold text-white
                           bg-blue-600 hover:bg-blue-700 disabled:opacity-60 transition-colors shadow-sm">
								{saving ? "Saving…" : "Save"}
							</button>
						</div>
						{addMsg && <div className="mt-3"><Banner msg={addMsg} onClose={() => setAddMsg(null)} /></div>}
					</div>
				)}

				<div className="bg-white rounded-2xl shadow-lg p-6">
					<div className="flex items-center justify-between mb-5">
						<div>
							<h1 className="text-2xl font-bold text-gray-800">Brand</h1>
							<p className="text-sm text-gray-500 mt-0.5">View and manage brand records</p>
						</div>
						<span className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm font-medium">
							Total: {total}
						</span>
					</div>

					<div className="flex gap-3 mb-5">
						<select value={searchBy} onChange={e => setSearchBy(e.target.value)}
							className="border border-gray-300 rounded-lg px-3 py-2.5 text-sm
                         focus:ring-2 focus:ring-blue-500 sm:w-44">
							<option value="1">Brand Code</option>
							<option value="2">Brand Name</option>
						</select>
						<div className="relative flex-1">
							<svg className="w-5 h-5 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2"
								fill="none" viewBox="0 0 24 24">
								<path fill="currentColor" d="M15.5 14H14.71L14.43 13.73C15.41 12.59 16 11.11 16
									9.5C16 5.91 13.09 3 9.5 3C5.91 3 3 5.91 3 9.5C3 13.09 5.91 16 9.5
									16C11.11 16 12.59 15.41 13.73 14.43L14 14.71V15.5L19 20.49L20.49 19L15.5
									14ZM9.5 14C7.01 14 5 11.99 5 9.5C5 7.01 7.01 5 9.5 5C11.99 5 14 7.01 14
									9.5C14 11.99 11.99 14 9.5 14Z" />
							</svg>
							<input type="text" placeholder="Search…" value={searchVal}
								onChange={e => setSearchVal(e.target.value)}
								onKeyDown={e => e.key === "Enter" && handleSearch()}
								className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg text-sm
                           focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
						</div>
						<button onClick={handleSearch} disabled={loading}
							className="px-5 py-2.5 rounded-lg text-sm font-medium text-white
                         bg-gradient-to-r from-blue-600 to-indigo-700
                         hover:from-blue-700 hover:to-indigo-800 disabled:opacity-75 transition-all shadow-sm">
							{loading ? "Searching…" : "Search"}
						</button>
					</div>

					{listMsg && <div className="mb-4"><Banner msg={listMsg} onClose={() => setListMsg(null)} /></div>}

					<div className="overflow-x-auto rounded-xl border border-gray-200">
						<table className="w-full">
							<thead className="bg-gradient-to-r from-gray-50 to-gray-100">
								<tr>
									{["Brand Code", "Brand Name", "Country"].map(h => (
										<th key={h}
											className="py-3 px-5 text-left text-xs font-semibold
                                 text-gray-500 uppercase tracking-wider">{h}</th>
									))}
									<th className="py-3 px-5 text-center text-xs font-semibold
                                 text-gray-500 uppercase tracking-wider w-60">
										Action
									</th>
								</tr>
							</thead>
							<tbody className="divide-y divide-gray-100">
								{brands.length === 0 && !loading ? (
									<tr>
										<td colSpan={4} className="py-12 text-center text-gray-400">
											<div className="flex flex-col items-center gap-2">
												<svg className="w-12 h-12 text-gray-200" fill="none"
													stroke="currentColor" viewBox="0 0 24 24">
													<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
														d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
												</svg>
												<p className="font-medium">No brand records found</p>
												<p className="text-sm">Try adjusting your search</p>
											</div>
										</td>
									</tr>
								) : (
									<>
										{brands.map((row, idx) => (
											<tr key={row.BRAND}
												className={`hover:bg-blue-50 transition-colors ${idx % 2 === 0 ? "bg-white" : "bg-gray-50"}`}>
												<td className="py-3 px-5 text-sm font-semibold text-gray-800">{row.BRAND}</td>
												<td className="py-3 px-5 text-sm text-gray-700">{row.BRAND_NM}</td>
												<td className="py-3 px-5 text-sm text-gray-600">{row.BRAND_COUNTRY}</td>
												<td className="py-3 px-5">
													<div className="flex justify-center gap-2 flex-wrap">
														<button
															onClick={() => navigate(`/brand-vehicle?brand=${row.BRAND}`)}
															className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md
																text-xs font-semibold bg-indigo-600 hover:bg-indigo-700
																active:bg-indigo-800 text-white shadow-sm transition-all">
															<svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
																<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
																	d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
															</svg>
															Vehicle Type
														</button>

														{akses === "9" && (
															<>
																<button onClick={() => openEdit(row)}
																	className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md
																		text-xs font-semibold bg-blue-600 hover:bg-blue-700
																		active:bg-blue-800 text-white shadow-sm transition-all">
																	<svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
																		<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
																			d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
																	</svg>
																	Edit
																</button>
																<button onClick={() => handleDelete(row)}
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
														)}
													</div>
												</td>
											</tr>
										))}
										{loading && (
											<tr><td colSpan={4} className="py-4 text-center">
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

			{editRow && (
				<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
					onClick={e => e.target === e.currentTarget && setEditRow(null)}>
					<div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm animate-in slide-in-from-top-4">
						<div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
							<h2 className="font-semibold text-gray-800">Edit Brand</h2>
							<button onClick={() => setEditRow(null)}
								className="text-gray-400 hover:text-gray-600 text-2xl leading-none">×</button>
						</div>
						<div className="px-6 py-5 space-y-4">
							<div>
								<label className="block text-xs font-medium text-gray-500 mb-1">Brand Code</label>
								<input readOnly value={editRow.BRAND}
									className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm bg-gray-100 font-semibold" />
							</div>
							<div>
								<label className="block text-xs font-medium text-gray-500 mb-1">
									Brand Name <span className="text-red-500">*</span>
								</label>
								<input autoFocus value={editBrandNm} onChange={e => setEditBrandNm(e.target.value)}
									className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm
                             focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
							</div>
							<div>
								<label className="block text-xs font-medium text-gray-500 mb-1">
									Brand Country <span className="text-red-500">*</span>
								</label>
								<input value={editCountry} onChange={e => setEditCountry(e.target.value)}
									onKeyDown={e => e.key === "Enter" && handleUpdate()}
									className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm
                             focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
							</div>
							{editMsg && <Banner msg={editMsg} onClose={() => setEditMsg(null)} />}
						</div>
						<div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
							<button onClick={() => setEditRow(null)}
								className="px-4 py-2 text-sm border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">
								Cancel
							</button>
							<button onClick={handleUpdate} disabled={editSaving}
								className="px-4 py-2 text-sm rounded-lg font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-60 transition-colors">
								{editSaving ? "Saving…" : "Save"}
							</button>
						</div>
					</div>
				</div>
			)}
		</div>
	);
};

export default BrandPage;