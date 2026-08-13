import React, { useCallback, useEffect, useState } from "react";
import api from "../../../../../api/axiosInstance";

export interface CAMReferencesPageProps {
	apless: string;
	applNo: string;
	onSaved: (result: { apless: string; applno: string }) => void;
}

interface ReferenceRow {
	id: number;
	refName: string;
	refPhone: string;
	remark: string;
}

const EMPTY_FORM = { refName: "", refPhone: "", remark: "" };

export default function CAMReferencesPage({ apless, applNo, onSaved }: CAMReferencesPageProps) {
	const [rows, setRows] = useState<ReferenceRow[]>([]);
	const [loading, setLoading] = useState(true);
	const [saving, setSaving] = useState(false);
	const [error, setError] = useState("");
	const [editingId, setEditingId] = useState<number | null>(null);
	const [form, setForm] = useState(EMPTY_FORM);

	const loadRows = useCallback(async () => {
		setLoading(true);
		setError("");
		try {
			const res = await api.get("/CAM/EditIndex/references", {
				params: { apless, applno: applNo },
			});
			setRows(res.data.rows || []);
		} catch {
			setError("Failed to load references.");
		} finally {
			setLoading(false);
		}
	}, [apless, applNo]);

	useEffect(() => {
		loadRows();
	}, [loadRows]);

	const resetForm = () => {
		setForm(EMPTY_FORM);
		setEditingId(null);
	};

	const handleEdit = (row: ReferenceRow) => {
		setEditingId(row.id);
		setForm({ refName: row.refName, refPhone: row.refPhone, remark: row.remark });
	};

	const handleDelete = async (id: number) => {
		if (!window.confirm("Delete this reference?")) return;
		setError("");
		try {
			const res = await api.delete("/CAM/EditIndex/references", {
				params: { apless, id },
			});
			if (!res.data.success) {
				setError(res.data.message || "Delete failed.");
				return;
			}
			if (editingId === id) resetForm();
			loadRows();
		} catch {
			setError("Delete failed.");
		}
	};

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		setSaving(true);
		setError("");
		try {
			const res = await api.post("/CAM/EditIndex/references", {
				apless,
				applno: applNo,
				id: editingId || undefined,
				refName: form.refName,
				refPhone: form.refPhone,
				remark: form.remark,
			});
			if (!res.data.success) {
				setError(res.data.message || "Save failed.");
				return;
			}
			resetForm();
			loadRows();
		} catch {
			setError("Save failed.");
		} finally {
			setSaving(false);
		}
	};

	return (
		<div className="rounded-2xl bg-white p-6 shadow">
			<h2 className="mb-4 text-base font-semibold text-slate-700">References</h2>

			<form onSubmit={handleSubmit} className="mb-6 space-y-3">
				<div>
					<label className="mb-1 block text-sm text-slate-600">Name *</label>
					<input
						type="text"
						maxLength={100}
						value={form.refName}
						onChange={e => setForm(f => ({ ...f, refName: e.target.value }))}
						className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-orange-500 focus:outline-none"
					/>
				</div>
				<div>
					<label className="mb-1 block text-sm text-slate-600">Telephone Number *</label>
					<input
						type="text"
						maxLength={60}
						value={form.refPhone}
						onChange={e => setForm(f => ({ ...f, refPhone: e.target.value }))}
						className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-orange-500 focus:outline-none"
					/>
				</div>
				<div>
					<label className="mb-1 block text-sm text-slate-600">Remark / Notes *</label>
					<textarea
						maxLength={250}
						rows={3}
						value={form.remark}
						onChange={e => setForm(f => ({ ...f, remark: e.target.value }))}
						className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-orange-500 focus:outline-none"
					/>
				</div>

				{error && <p className="text-sm text-red-600">{error}</p>}

				<div className="flex gap-2">
					<button
						type="submit"
						disabled={saving}
						className="rounded-lg bg-orange-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-orange-600 disabled:opacity-50"
					>
						{editingId ? "Update" : "Save"}
					</button>
					{editingId && (
						<button
							type="button"
							onClick={resetForm}
							className="rounded-lg bg-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-300"
						>
							Cancel
						</button>
					)}
				</div>
			</form>

			<table className="w-full text-left text-sm">
				<thead>
					<tr className="border-b border-slate-200 text-slate-500">
						<th className="py-2 pr-2">No.</th>
						<th className="py-2 pr-2">Name</th>
						<th className="py-2 pr-2">Telephone Number</th>
						<th className="py-2 pr-2">Remark / Notes</th>
						<th className="py-2"></th>
					</tr>
				</thead>
				<tbody>
					{loading ? (
						<tr>
							<td colSpan={5} className="py-4 text-center text-slate-400">Loading…</td>
						</tr>
					) : rows.length === 0 ? (
						<tr>
							<td colSpan={5} className="py-4 text-center text-slate-400">No references yet.</td>
						</tr>
					) : (
						rows.map((row, idx) => (
							<tr key={row.id} className="border-b border-slate-100">
								<td className="py-2 pr-2">{idx + 1}</td>
								<td className="py-2 pr-2">{row.refName}</td>
								<td className="py-2 pr-2">{row.refPhone}</td>
								<td className="py-2 pr-2">{row.remark}</td>
								<td className="py-2">
									<div className="flex gap-2">
										<button
											type="button"
											onClick={() => handleEdit(row)}
											className="rounded-lg px-2 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50"
										>
											Edit
										</button>
										<button
											type="button"
											onClick={() => handleDelete(row.id)}
											className="rounded-lg px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50"
										>
											Delete
										</button>
									</div>
								</td>
							</tr>
						))
					)}
				</tbody>
			</table>

			<div className="mt-6 flex justify-end">
				<button
					type="button"
					onClick={() => onSaved({ apless, applno: applNo })}
					className="rounded-lg bg-orange-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-orange-600"
				>
					Next
				</button>
			</div>
		</div>
	);
}