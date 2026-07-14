import React, { useEffect, useState, useCallback } from "react";
import api from "../../../api/axiosInstance";
import { DEFAULT_PAGE_LIMIT } from "../../../constants/DefaultValue"

interface ComboOption {
	value: string;
	desc_value: string;
}

interface ThresholdRow {
	id: number;
	ratio: string;
	ratio_desc: string;
	imp_date: string;
	remark: string;
	remark_desc: string;
	threshold1: string;
	threshold2: string;
	create_by: string;
	create_dt: string;
	update_by: string;
	update_dt: string;
}

interface FormState {
	id: number | null;
	ratio: string;
	imp_date: string;
	remark: string;
	threshold1: string;
	threshold2: string;
}

const EMPTY_FORM: FormState = {
	id: null, ratio: "1", imp_date: "", remark: "1",
	threshold1: "", threshold2: "",
};

type FieldType = "select" | "number_x" | "number_pct" | "select_range";

function getFieldConfig(ratio: string, remark: string): {
	type: FieldType;
	showRange: boolean;
	suffix1?: string;
	suffix2?: string;
} {
	const r = Number(ratio);
	const m = Number(remark);
	const showRange = m === 3;

	if (r === 1 || r === 5) return { type: "select", showRange };
	if (r === 2) return { type: "number_x", showRange, suffix1: "x", suffix2: "x" };
	if (r === 3 || r === 4) return { type: "number_pct", showRange, suffix1: "%", suffix2: "%" };
	return { type: "select", showRange };
}

const Spinner = ({ size = 6 }: { size?: number }) => (
	<svg className={`animate-spin h-${size} w-${size} text-blue-600`} fill="none" viewBox="0 0 24 24">
		<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
		<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
	</svg>
);

const MasterDataThresholdLevelPage: React.FC = () => {

	const [ratioOpts, setRatioOpts] = useState<ComboOption[]>([]);
	const [remarkOpts, setRemarkOpts] = useState<ComboOption[]>([]);
	const [thresOpts, setThresOpts] = useState<ComboOption[]>([]);

	const [ratioFilter, setRatioFilter] = useState("");
	const [rows, setRows] = useState<ThresholdRow[]>([]);
	const [total, setTotal] = useState(0);
	const [page, setPage] = useState(1);
	const LIMIT = DEFAULT_PAGE_LIMIT;
	const [listLoading, setListLoading] = useState(false);
	const [listError, setListError] = useState<string | null>(null);

	const [modalOpen, setModalOpen] = useState(false);
	const [isEdit, setIsEdit] = useState(false);
	const [form, setForm] = useState<FormState>(EMPTY_FORM);
	const [formLoading, setFormLoading] = useState(false);
	const [formError, setFormError] = useState<string | null>(null);
	const [formSuccess, setFormSuccess] = useState<string | null>(null);

	const [deleteId, setDeleteId] = useState<number | null>(null);
	const [deleteLoading, setDeleteLoading] = useState(false);

	useEffect(() => {
		api.get("/MasterData/api/ratio-threshold/options").then(res => {
			setRatioOpts(res.data.ratio || []);
			setRemarkOpts(res.data.remark || []);
			setThresOpts(res.data.threshold || []);
			if (res.data.ratio?.length) setForm(f => ({ ...f, ratio: res.data.ratio[0].value }));
			if (res.data.remark?.length) setForm(f => ({ ...f, remark: res.data.remark[0].value }));
		}).catch(() => { });
	}, []);

	const fetchList = useCallback(async (pg = page) => {
		setListLoading(true);
		setListError(null);
		try {
			const res = await api.get("/MasterData/api/ratio-threshold", {
				params: { ratio: ratioFilter, page: pg, limit: LIMIT },
			});
			setRows(res.data.data || []);
			setTotal(res.data.total || 0);
			setPage(pg);
		} catch {
			setListError("Failed to load data. Please try again.");
		} finally {
			setListLoading(false);
		}
	}, [ratioFilter, page]);

	const openAdd = () => {
		setForm({
			...EMPTY_FORM,
			ratio: ratioOpts[0]?.value || "1",
			remark: remarkOpts[0]?.value || "1",
		});
		setIsEdit(false);
		setFormError(null);
		setFormSuccess(null);
		setModalOpen(true);
	};

	const openEdit = async (id: number) => {
		setIsEdit(true);
		setFormError(null);
		setFormSuccess(null);
		setModalOpen(true);
		setFormLoading(true);
		try {
			const res = await api.get(`/MasterData/api/ratio-threshold/${id}`);
			const d = res.data;
			setForm({
				id: d.id,
				ratio: String(d.ratio),
				imp_date: d.imp_date,
				remark: String(d.remark),
				threshold1: d.threshold1,
				threshold2: d.threshold2,
			});
		} catch {
			setFormError("Failed to load record.");
		} finally {
			setFormLoading(false);
		}
	};

	const handleSubmit = async () => {
		setFormError(null);
		setFormSuccess(null);
		const { ratio, remark, imp_date, threshold1 } = form;
		if (!ratio || !remark || !imp_date) {
			setFormError("Lengkapi data terlebih dahulu.");
			return;
		}

		if (!threshold1) {
			setFormError("Lengkapi data Threshold dahulu.");
			return;
		}
		const cfg = getFieldConfig(ratio, remark);
		const payload = {
			ratio, remark, imp_date,
			threshold1: form.threshold1,
			threshold2: cfg.showRange ? form.threshold2 : "",
		};

		setFormLoading(true);
		try {
			if (isEdit && form.id) {
				await api.put(`/MasterData/api/ratio-threshold/${form.id}`, payload);
				setFormSuccess("Data berhasil di update");
			} else {
				await api.post("/MasterData/api/ratio-threshold", payload);
				setFormSuccess("Data berhasil disimpan");
			}
			fetchList(1);
		} catch (err: any) {
			setFormError(err.response?.data?.error || "Gagal menyimpan data.");
		} finally {
			setFormLoading(false);
		}
	};

	const confirmDelete = async () => {
		if (!deleteId) return;
		setDeleteLoading(true);
		try {
			await api.delete(`/MasterData/api/ratio-threshold/${deleteId}`);
			setDeleteId(null);
			fetchList(1);
		} catch {
			alert("Failed to delete record.");
		} finally {
			setDeleteLoading(false);
		}
	};

	const renderThresholdFields = () => {
		const cfg = getFieldConfig(form.ratio, form.remark);
		const inputCls = "border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 w-36";

		const fromField = cfg.type === "select" ? (
			<select
				value={form.threshold1}
				onChange={e => setForm(f => ({ ...f, threshold1: e.target.value }))}
				className={inputCls}
			>
				<option value="">Select</option>
				{thresOpts.map(o => (
					<option key={o.value} value={o.value}>{o.desc_value}</option>
				))}
			</select>
		) : (
			<div className="flex items-center gap-1">
				<input
					type="text"
					value={form.threshold1}
					onChange={e => {
						const v = e.target.value;
						if (/^[0-9]*\.?[0-9]{0,2}$/.test(v)) setForm(f => ({ ...f, threshold1: v }));
					}}
					className={inputCls}
					placeholder="0.00"
				/>
				{cfg.suffix1 && <span className="text-sm text-gray-500">{cfg.suffix1}</span>}
			</div>
		);

		const toField = cfg.type === "select" ? (
			<select
				value={form.threshold2}
				onChange={e => setForm(f => ({ ...f, threshold2: e.target.value }))}
				className={inputCls}
			>
				<option value="">Select</option>
				{thresOpts.map(o => (
					<option key={o.value} value={o.value}>{o.desc_value}</option>
				))}
			</select>
		) : (
			<div className="flex items-center gap-1">
				<input
					type="text"
					value={form.threshold2}
					onChange={e => {
						const v = e.target.value;
						if (/^[0-9]*\.?[0-9]{0,2}$/.test(v)) setForm(f => ({ ...f, threshold2: v }));
					}}
					className={inputCls}
					placeholder="0.00"
				/>
				{cfg.suffix2 && <span className="text-sm text-gray-500">{cfg.suffix2}</span>}
			</div>
		);

		return (
			<div className="flex items-center gap-2 flex-wrap">
				{fromField}
				{cfg.showRange && (
					<>
						<span className="text-sm text-gray-500 font-medium">s/d</span>
						{toField}
					</>
				)}
			</div>
		);
	};

	const totalPages = Math.ceil(total / LIMIT);

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-7xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6">

					<div className="mb-6">
						<h1 className="text-2xl md:text-3xl font-bold text-gray-800">Master Ratio Threshold Level</h1>
						<p className="text-gray-600 mt-1">Manage ratio threshold configuration</p>
					</div>

					<div className="bg-gray-50 rounded-xl p-4 border border-gray-200 mb-6">
						<div className="flex flex-wrap items-end gap-4">
							<div className="flex-1 min-w-[200px]">
								<label className="block text-sm font-medium text-gray-700 mb-1">Ratio</label>
								<select
									value={ratioFilter}
									onChange={e => setRatioFilter(e.target.value)}
									className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all bg-white"
								>
									<option value="">Select</option>
									{ratioOpts.map(o => (
										<option key={o.value} value={o.value}>{o.desc_value}</option>
									))}
								</select>
							</div>
							<div className="flex gap-3">
								<button
									onClick={() => fetchList(1)}
									disabled={listLoading}
									className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
								>
									{listLoading ? <Spinner size={4} /> : (
										<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-4.35-4.35M17 11A6 6 0 105 11a6 6 0 0012 0z" />
										</svg>
									)}
									Search
								</button>
								<button
									onClick={openAdd}
									className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center gap-2"
								>
									<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
									</svg>
									Add
								</button>
							</div>
						</div>
					</div>

					{listError && (
						<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 flex items-start gap-3">
							<svg className="w-5 h-5 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
							</svg>
							<span>{listError}</span>
						</div>
					)}

					<div className="overflow-x-auto rounded-lg border border-gray-200">
						<table className="w-full text-sm">
							<thead>
								<tr>
									{["Implementation Date", "Remark", "Threshold Level (OJK)", "Create By", "Create Date", "Update By", "Last Update", "Action"].map(h => (
										<th key={h} className="py-3 px-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider border border-gray-300 bg-gray-100">
											{h}
										</th>
									))}
								</tr>
							</thead>
							<tbody className="divide-y divide-gray-200">
								{listLoading ? (
									<tr>
										<td colSpan={8} className="py-10 text-center">
											<div className="flex justify-center"><Spinner size={8} /></div>
										</td>
									</tr>
								) : rows.length === 0 ? (
									<tr>
										<td colSpan={8} className="py-10 text-center text-gray-500">
											<svg className="w-16 h-16 text-gray-300 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
											</svg>
											<p>No data found. Click Search or Add to get started.</p>
										</td>
									</tr>
								) : (
									rows.map((row, idx) => {
										const thres = row.threshold2
											? `${row.threshold1} s/d ${row.threshold2}`
											: row.threshold1;
										return (
											<tr key={row.id} className={`hover:bg-blue-50 transition-colors ${idx % 2 === 0 ? "bg-white" : "bg-gray-50/50"}`}>
												<td className="py-2.5 px-4 border border-gray-200 text-center">{row.imp_date}</td>
												<td className="py-2.5 px-4 border border-gray-200 text-center">{row.remark_desc}</td>
												<td className="py-2.5 px-4 border border-gray-200 text-center font-mono">{thres}</td>
												<td className="py-2.5 px-4 border border-gray-200 text-center">{row.create_by}</td>
												<td className="py-2.5 px-4 border border-gray-200 text-center">{row.create_dt}</td>
												<td className="py-2.5 px-4 border border-gray-200 text-center">{row.update_by}</td>
												<td className="py-2.5 px-4 border border-gray-200 text-center">{row.update_dt}</td>
												<td className="py-2.5 px-4 border border-gray-200 text-center">
													<div className="flex items-center justify-center gap-2">
														<button
															onClick={() => openEdit(row.id)}
															className="px-3 py-1 bg-yellow-500 text-white rounded-lg hover:bg-yellow-600 transition-colors text-xs font-medium flex items-center gap-1"
														>
															<svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
																<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
															</svg>
															Edit
														</button>
														<button
															onClick={() => setDeleteId(row.id)}
															className="px-3 py-1 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors text-xs font-medium flex items-center gap-1"
														>
															<svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
																<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
															</svg>
															Delete
														</button>
													</div>
												</td>
											</tr>
										);
									})
								)}
							</tbody>
						</table>
					</div>

					{totalPages > 1 && (
						<div className="mt-4 flex items-center justify-between text-sm text-gray-600">
							<span>Showing {((page - 1) * LIMIT) + 1}–{Math.min(page * LIMIT, total)} of {total}</span>
							<div className="flex gap-2">
								<button
									onClick={() => fetchList(page - 1)}
									disabled={page === 1 || listLoading}
									className="px-3 py-1.5 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
								>← Prev</button>
								<button
									onClick={() => fetchList(page + 1)}
									disabled={page >= totalPages || listLoading}
									className="px-3 py-1.5 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
								>Next →</button>
							</div>
						</div>
					)}
				</div>
			</div>

			{modalOpen && (
				<div
					className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
					onClick={e => { if (e.target === e.currentTarget) setModalOpen(false); }}
				>
					<div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
						<div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-gray-50">
							<h2 className="text-lg font-bold text-gray-800">
								{isEdit ? "Edit Record" : "Add New Record"}
							</h2>
							<button
								onClick={() => setModalOpen(false)}
								className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
							>&times;</button>
						</div>

						<div className="px-6 py-5 space-y-4">
							{formLoading && (
								<div className="flex justify-center py-6"><Spinner size={8} /></div>
							)}

							{!formLoading && (
								<>
									<div className="grid grid-cols-3 items-center gap-3">
										<label className="text-sm font-medium text-gray-700 text-right">Ratio</label>
										<span className="text-sm text-gray-500">:</span>
										<select
											value={form.ratio}
											onChange={e => setForm(f => ({ ...f, ratio: e.target.value, threshold1: "", threshold2: "" }))}
											className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
										>
											{ratioOpts.map(o => (
												<option key={o.value} value={o.value}>{o.desc_value}</option>
											))}
										</select>
									</div>

									<div className="grid grid-cols-3 items-center gap-3">
										<label className="text-sm font-medium text-gray-700 text-right">Implementation Date</label>
										<span className="text-sm text-gray-500">:</span>
										<input
											type="date"
											value={form.imp_date}
											onChange={e => setForm(f => ({ ...f, imp_date: e.target.value }))}
											className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
										/>
									</div>

									<div className="grid grid-cols-3 items-center gap-3">
										<label className="text-sm font-medium text-gray-700 text-right">Remark</label>
										<span className="text-sm text-gray-500">:</span>
										<select
											value={form.remark}
											onChange={e => setForm(f => ({ ...f, remark: e.target.value, threshold1: "", threshold2: "" }))}
											className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
										>
											{remarkOpts.map(o => (
												<option key={o.value} value={o.value}>{o.desc_value}</option>
											))}
										</select>
									</div>

									<div className="grid grid-cols-3 items-center gap-3">
										<label className="text-sm font-medium text-gray-700 text-right">Threshold Level (OJK)</label>
										<span className="text-sm text-gray-500">:</span>
										{renderThresholdFields()}
									</div>
								</>
							)}

							{formError && (
								<div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm flex items-center gap-2">
									<svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
									</svg>
									{formError}
								</div>
							)}
							
							{formSuccess && (
								<div className="p-3 bg-green-50 border border-green-200 rounded-lg text-green-700 text-sm flex items-center gap-2">
									<svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
										<path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
									</svg>
									{formSuccess}
								</div>
							)}
						</div>

						<div className="px-6 py-4 border-t border-gray-200 bg-gray-50 flex justify-end gap-3">
							<button
								onClick={() => setModalOpen(false)}
								className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-100 transition-colors text-sm font-medium"
							>
								Close
							</button>
							{!formLoading && (
								<button
									onClick={handleSubmit}
									disabled={formLoading}
									className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
								>
									{formLoading ? <><Spinner size={4} /> Saving...</> : (
										<>
											<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
											</svg>
											{isEdit ? "Update" : "Save"}
										</>
									)}
								</button>
							)}
						</div>
					</div>
				</div>
			)}

			{deleteId !== null && (
				<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
					<div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm mx-4 p-6">
						<div className="flex items-center gap-3 mb-4">
							<div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center flex-shrink-0">
								<svg className="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
								</svg>
							</div>
							<div>
								<h3 className="font-bold text-gray-800">Delete Record</h3>
								<p className="text-sm text-gray-500 mt-0.5">Are you sure to delete this record?</p>
							</div>
						</div>
						<div className="flex justify-end gap-3">
							<button
								onClick={() => setDeleteId(null)}
								className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-100 text-sm font-medium"
							>
								Cancel
							</button>
							<button
								onClick={confirmDelete}
								disabled={deleteLoading}
								className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors text-sm font-medium flex items-center gap-2 disabled:opacity-50"
							>
								{deleteLoading ? <><Spinner size={4} /> Deleting...</> : "Delete"}
							</button>
						</div>
					</div>
				</div>
			)}
		</div>
	);
};

export default MasterDataThresholdLevelPage;