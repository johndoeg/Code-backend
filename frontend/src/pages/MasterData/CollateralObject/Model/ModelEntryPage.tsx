import React, { useEffect, useState, useCallback } from "react";
import api from "../../../../api/axiosInstance";
import Pagination from "../../../../helpers/Pagination";
import { DEFAULT_PAGE_LIMIT } from "../../../../constants/DefaultValue";

interface Model { MODEL: string; MODEL_NM: string; }

interface Msg { type: "success" | "error"; text: string; }

function Banner({ msg, onClose }: { msg: Msg; onClose: () => void }) {
	return (
		<div className={`flex items-start gap-3 rounded-lg px-4 py-3 text-sm border ${msg.type === "success"
			? "bg-green-50 border-green-200 text-green-700"
			: "bg-red-50   border-red-200   text-red-700"
			}`}>
			<span className="flex-1">{msg.text}</span>
			<button onClick={onClose} className="text-lg leading-none opacity-60 hover:opacity-100">
				×
			</button>
		</div>
	);
}

const ModelEntryPage: React.FC = () => {
	const [models, setModels] = useState<Model[]>([]);
	const [search, setSearch] = useState("");
	const [page, setPage] = useState(1);
	const [total, setTotal] = useState(0);
	const [loading, setLoading] = useState(false);
	const [listMsg, setListMsg] = useState<Msg | null>(null);
	const [akses, setAkses] = useState("0");
	const limit = DEFAULT_PAGE_LIMIT;

	const [newCode, setNewCode] = useState("");
	const [newName, setNewName] = useState("");
	const [saving, setSaving] = useState(false);
	const [addMsg, setAddMsg] = useState<Msg | null>(null);

	const [editRow, setEditRow] = useState<Model | null>(null);
	const [editName, setEditName] = useState("");
	const [editSaving, setEditSaving] = useState(false);
	const [editMsg, setEditMsg] = useState<Msg | null>(null);

	const fetchModels = useCallback(async () => {
		setLoading(true);
		setListMsg(null);
		try {
			const r = await api.get("/MasterData/api/model-entry", {
				params: { search_val: search, page, limit },
			});
			setModels(r.data.data || []);
			setTotal(r.data.total || 0);
			setAkses(r.data.akses || "0");
		} catch {
			setListMsg({ type: "error", text: "Failed to load model data. Please try again." });
		} finally {
			setLoading(false);
		}
	}, [search, page, limit]);

	useEffect(() => { fetchModels(); }, [fetchModels]);

	const fetchNextCode = useCallback(async () => {
		try {
			const r = await api.get("/MasterData/api/model/next-code");
			setNewCode(r.data.next_code || "");
		} catch {
			setNewCode("");
		}
	}, []);

	useEffect(() => {
		if (akses === "9") fetchNextCode();
	}, [akses, fetchNextCode]);

	const handleSave = async () => {
		if (!newName.trim()) {
			setAddMsg({ type: "error", text: "Model Name must not be empty." });
			return;
		}
		setSaving(true);
		setAddMsg(null);
		try {
			const r = await api.post("/MasterData/api/model", {
				model: newCode,
				model_nm: newName.trim(),
			});
			if (r.data.success) {
				setNewName("");
				setAddMsg({ type: "success", text: "Model saved successfully." });
				setPage(1);
				await fetchModels();
				await fetchNextCode();
			} else {
				setAddMsg({ type: "error", text: r.data.message || "Save failed." });
			}
		} catch {
			setAddMsg({ type: "error", text: "An error occurred. Please try again." });
		} finally {
			setSaving(false);
		}
	};

	const openEdit = (row: Model) => {
		setEditRow(row);
		setEditName(row.MODEL_NM);
		setEditMsg(null);
	};

	const handleUpdate = async () => {
		if (!editRow) return;
		if (!editName.trim()) {
			setEditMsg({ type: "error", text: "Model Name must not be empty." });
			return;
		}
		setEditSaving(true);
		setEditMsg(null);
		try {
			const r = await api.put(`/MasterData/api/model/${editRow.MODEL}`, {
				model_nm: editName.trim(),
			});
			if (r.data.success) {
				setEditMsg({ type: "success", text: "Model updated successfully." });
				await fetchModels();
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

	const handleDelete = async (model: Model) => {
		if (!window.confirm(
			`Delete model "${model.MODEL} – ${model.MODEL_NM}"?\n\nThis will also remove related Karoseri records.`
		)) return;

		try {
			const r = await api.delete(`/MasterData/api/model/${model.MODEL}`);
			if (r.data.success) {
				setListMsg({ type: "success", text: `Model ${model.MODEL} deleted.` });
				if (models.length === 1 && page > 1) setPage(p => p - 1);
				else fetchModels();
			} else {
				setListMsg({ type: "error", text: r.data.message || "Delete failed." });
			}
		} catch {
			setListMsg({ type: "error", text: "Delete failed. Please try again." });
		}
	};

	const totalPages = Math.ceil(total / limit);

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-6xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6">

					<div className="flex items-center justify-between mb-6">
						<div>
							<h1 className="text-2xl font-bold text-gray-800">Model</h1>
							<p className="text-gray-500 text-sm mt-0.5">
								View and manage vehicle model records
							</p>
						</div>
						<span className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full
                             text-sm font-medium">
							Total: {total}
						</span>
					</div>

					{akses === "9" && (
						<div className="mb-6 p-4 bg-gray-50 border border-gray-200 rounded-xl">
							<h2 className="text-sm font-semibold text-gray-600 uppercase
                             tracking-wide mb-3">
								Add New Model
							</h2>
							<div className="flex flex-col sm:flex-row gap-3">
								<div className="sm:w-36">
									<label className="block text-xs font-medium text-gray-500 mb-1">
										Model Code
									</label>
									<input
										type="text"
										readOnly
										value={newCode}
										className="w-full border border-gray-200 rounded-lg px-3 py-2.5
                               text-sm bg-gray-100 font-mono text-center"
									/>
								</div>

								<div className="flex-1">
									<label className="block text-xs font-medium text-gray-500 mb-1">
										Model Name <span className="text-red-500">*</span>
									</label>
									<input
										type="text"
										placeholder="Enter model name…"
										value={newName}
										onChange={e => setNewName(e.target.value)}
										onKeyDown={e => e.key === "Enter" && handleSave()}
										className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm
                               focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
									/>
								</div>

								<div className="sm:self-end">
									<button
										onClick={handleSave}
										disabled={saving}
										className="w-full sm:w-auto px-5 py-2.5 rounded-lg text-sm font-semibold
											bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white
											shadow-sm disabled:opacity-60 transition-colors"
									>
										{saving ? "Saving…" : "Save"}
									</button>
								</div>
							</div>

							{addMsg && (
								<div className="mt-3">
									<Banner msg={addMsg} onClose={() => setAddMsg(null)} />
								</div>
							)}
						</div>
					)}

					<div className="flex gap-3 mb-5">
						<div className="relative flex-1">
							<svg
								className="w-5 h-5 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2"
								fill="none" viewBox="0 0 24 24">
								<path fill="currentColor"
									d="M15.5 14H14.71L14.43 13.73C15.41 12.59 16 11.11 16 9.5
									C16 5.91 13.09 3 9.5 3C5.91 3 3 5.91 3 9.5C3 13.09 5.91
									16 9.5 16C11.11 16 12.59 15.41 13.73 14.43L14 14.71V15.5
									L19 20.49L20.49 19L15.5 14ZM9.5 14C7.01 14 5 11.99 5 9.5
									C5 7.01 7.01 5 9.5 5C11.99 5 14 7.01 14 9.5C14 11.99
									11.99 14 9.5 14Z" />
							</svg>
							<input
								type="text"
								placeholder="Search by code or name…"
								value={search}
								onChange={e => { setSearch(e.target.value); setPage(1); }}
								onKeyDown={e => e.key === "Enter" && fetchModels()}
								className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg
                           			text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
							/>
						</div>
						<button
							onClick={() => { setPage(1); fetchModels(); }}
							disabled={loading}
							className="px-5 py-2.5 rounded-lg text-sm font-medium text-white
								bg-gradient-to-r from-blue-600 to-indigo-700
								hover:from-blue-700 hover:to-indigo-800 shadow-sm
								disabled:opacity-75 transition-all"
						>
							{loading ? "Searching…" : "Search"}
						</button>
					</div>

					{listMsg && (
						<div className="mb-4">
							<Banner msg={listMsg} onClose={() => setListMsg(null)} />
						</div>
					)}

					<div className="overflow-x-auto rounded-xl border border-gray-200">
						<table className="w-full">
							<thead className="bg-gradient-to-r from-gray-50 to-gray-100">
								<tr>
									<th className="py-3 px-5 text-left text-xs font-semibold
                                 text-gray-500 uppercase tracking-wider">
										Model Code
									</th>
									<th className="py-3 px-5 text-left text-xs font-semibold
                                 text-gray-500 uppercase tracking-wider">
										Model Name
									</th>
									{akses === "9" && (
										<th className="py-3 px-5 text-left text-xs font-semibold
                                   text-gray-500 uppercase tracking-wider w-36">
											Action
										</th>
									)}
								</tr>
							</thead>
							<tbody className="divide-y divide-gray-100">
								{models.length === 0 && !loading ? (
									<tr>
										<td colSpan={akses === "9" ? 3 : 2}
											className="py-12 text-center text-gray-400">
											<div className="flex flex-col items-center gap-2">
												<svg className="w-12 h-12 text-gray-200" fill="none"
													stroke="currentColor" viewBox="0 0 24 24">
													<path strokeLinecap="round" strokeLinejoin="round"
														strokeWidth={2} d="M9.172 16.172a4 4 0 015.656
														0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9
														0 0118 0z" />
												</svg>
												<p className="font-medium">No model records found</p>
												<p className="text-sm">Try adjusting your search</p>
											</div>
										</td>
									</tr>
								) : (
									<>
										{models.map((m, idx) => (
											<tr key={m.MODEL}
												className={`hover:bg-blue-50 transition-colors ${idx % 2 === 0 ? "bg-white" : "bg-gray-50"
													}`}>
												<td className="py-3 px-5 text-sm font-mono font-semibold text-gray-800">
													{m.MODEL}
												</td>
												<td className="py-3 px-5 text-sm text-gray-700">
													{m.MODEL_NM}
												</td>
												{akses === "9" && (
													<td className="py-3 px-5">
														<div className="flex items-center gap-2">
															<button
																onClick={() => openEdit(m)}
																className="inline-flex items-center gap-1 px-3 py-1.5
																rounded-md text-xs font-semibold bg-blue-600
																hover:bg-blue-700 active:bg-blue-800 text-white
																shadow-sm transition-all"
															>
																<svg className="w-3 h-3" fill="none"
																	stroke="currentColor" viewBox="0 0 24 24">
																	<path strokeLinecap="round" strokeLinejoin="round"
																		strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2
																		2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2
																		2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
																</svg>
																Edit
															</button>

															<button
																onClick={() => handleDelete(m)}
																className="inline-flex items-center gap-1 px-3 py-1.5
																	rounded-md text-xs font-semibold bg-red-50
																	hover:bg-red-100 active:bg-red-200 text-red-600
																	border border-red-200 hover:border-red-300
																	shadow-sm transition-all"
															>
																<svg className="w-3 h-3" fill="none"
																	stroke="currentColor" viewBox="0 0 24 24">
																	<path strokeLinecap="round" strokeLinejoin="round"
																		strokeWidth={2} d="M19 7l-.867 12.142A2 2 0
																		0116.138 21H7.862a2 2 0 01-1.995-1.858L5
																		7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1
																		1 0 00-1 1v3M4 7h16" />
																</svg>
																Delete
															</button>
														</div>
													</td>
												)}
											</tr>
										))}
										
										{loading && (
											<tr>
												<td colSpan={akses === "9" ? 3 : 2}
													className="py-4 text-center">
													<div className="flex justify-center">
														<svg className="animate-spin h-5 w-5 text-blue-500"
															fill="none" viewBox="0 0 24 24">
															<circle className="opacity-25" cx="12" cy="12" r="10"
																stroke="currentColor" strokeWidth="4" />
															<path className="opacity-75" fill="currentColor"
																d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
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

					{!loading && total > 0 && (
						<Pagination
							page={page}
							totalPages={totalPages}
							onPageChange={setPage}
							totalItems={total}
							itemsPerPage={limit}
							className="mt-5"
						/>
					)}
				</div>
			</div>

			{editRow && (
				<div
					className="fixed inset-0 z-50 flex items-center justify-center
                     bg-black/40 p-4"
					onClick={e => e.target === e.currentTarget && setEditRow(null)}
				>
					<div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm
                          animate-in slide-in-from-top-4">
						<div className="flex items-center justify-between px-6 py-4
                            border-b border-gray-200">
							<h2 className="font-semibold text-gray-800">Edit Model</h2>
							<button
								onClick={() => setEditRow(null)}
								className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
							>
								×
							</button>
						</div>

						<div className="px-6 py-5 space-y-4">
							<div>
								<label className="block text-sm font-medium text-gray-600 mb-1">
									Model Code
								</label>
								<input
									type="text"
									readOnly
									value={editRow.MODEL}
									className="w-full border border-gray-200 rounded-lg px-3 py-2.5
                             text-sm bg-gray-100 font-mono"
								/>
							</div>

							<div>
								<label className="block text-sm font-medium text-gray-600 mb-1">
									Model Name <span className="text-red-500">*</span>
								</label>
								<input
									type="text"
									autoFocus
									value={editName}
									onChange={e => setEditName(e.target.value)}
									onKeyDown={e => e.key === "Enter" && handleUpdate()}
									className="w-full border border-gray-300 rounded-lg px-3 py-2.5
                             			text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
								/>
							</div>

							{editMsg && <Banner msg={editMsg} onClose={() => setEditMsg(null)} />}
						</div>

						<div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
							<button
								onClick={() => setEditRow(null)}
								className="px-4 py-2 text-sm border border-gray-300 rounded-lg
                           text-gray-700 hover:bg-gray-50 transition-colors"
							>
								Cancel
							</button>
							<button
								onClick={handleUpdate}
								disabled={editSaving}
								className="px-4 py-2 text-sm rounded-lg font-semibold text-white
                           bg-blue-600 hover:bg-blue-700 disabled:opacity-60
                           transition-colors"
							>
								{editSaving ? "Saving…" : "Save"}
							</button>
						</div>
					</div>
				</div>
			)}
		</div>
	);
};

export default ModelEntryPage;