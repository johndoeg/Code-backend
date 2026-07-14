import React, { useEffect, useState } from "react";
import api from '../../../../api/axiosInstance';

interface RevisiInit {
	blocked: boolean;
	message?: string;
	appl_no?: string;
	lessee_nm?: string;
	cons_leas_name?: string;
	next_revision?: string;
}

const CamRevisePage: React.FC = () => {
	const params = new URLSearchParams(window.location.search);
	const apless = params.get("apless") || "";
	const applno = params.get("applno") || "";

	const [init, setInit] = useState<RevisiInit | null>(null);
	const [loading, setLoading] = useState(true);
	const [note, setNote] = useState("");
	const [saving, setSaving] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [result, setResult] = useState<{ success: boolean; message: string } | null>(null);

	useEffect(() => {
		if (!apless || !applno) {
			setError("Missing apless/applno in the URL.");
			setLoading(false);
			return;
		}
		(async () => {
			try {
				const res = await api.get('/CAM/api/revisi/init', { params: { apless, applno } });
				setInit(res.data);
			} catch {
				setError("Failed to load CAM details.");
			} finally {
				setLoading(false);
			}
		})();
	}, [apless, applno]);

	const handleSave = async () => {
		if (!note.trim()) {
			setError("Note must not empty");
			return;
		}
		setError(null);
		setSaving(true);
		try {
			const res = await api.post('/CAM/api/revisi', { apless, applno, revisi_note: note });
			setResult({ success: res.data.success, message: res.data.message });
			if (res.data.success) {
				setTimeout(() => {
					window.parent.location.href = "/cam_onhand";
				}, 2500);
			}
		} catch {
			setResult({ success: false, message: "Save failed. Please try again." });
		} finally {
			setSaving(false);
		}
	};

	return (
		<div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 p-4 md:p-6">
			<div className="max-w-2xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6">
					<h1 className="text-2xl font-bold text-slate-800 mb-6">Revise CAM</h1>

					{loading ? (
						<div className="flex justify-center py-10">
							<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
						</div>
					) : error && !init ? (
						<div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
							{error}
						</div>
					) : init?.blocked ? (
						<div className="p-4 bg-amber-50 border border-amber-200 rounded-lg text-amber-800 text-sm">
							{init.message}
						</div>
					) : (
						<div className="space-y-4">
							<div className="grid grid-cols-3 gap-2 text-sm">
								<div className="text-slate-500">CAM No.</div>
								<div className="col-span-2 font-medium text-slate-800">{init?.appl_no}</div>
								<div className="text-slate-500">Customer Name</div>
								<div className="col-span-2 font-medium text-slate-800">{init?.lessee_nm}</div>
								<div className="text-slate-500">Finance Type</div>
								<div className="col-span-2 font-medium text-slate-800">{init?.cons_leas_name}</div>
								<div className="text-slate-500">Next Revision No.</div>
								<div className="col-span-2 font-medium text-slate-800">R{init?.next_revision}</div>
							</div>

							<div>
								<label className="block text-sm text-slate-600 mb-1">Note</label>
								<textarea
									value={note}
									onChange={e => setNote(e.target.value)}
									rows={4}
									className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
								/>
							</div>

							{error && (
								<div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
									{error}
								</div>
							)}

							{result && (
								<div className={`p-3 rounded-lg text-sm border ${result.success
									? "bg-green-50 border-green-200 text-green-700"
									: "bg-red-50 border-red-200 text-red-700"}`}>
									{result.message}
								</div>
							)}

							<div className="flex justify-center pt-2">
								<button
									onClick={handleSave}
									disabled={saving}
									className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white rounded-lg text-sm font-medium"
								>
									{saving ? "Saving…" : "Save"}
								</button>
							</div>
						</div>
					)}
				</div>
			</div>
		</div>
	);
};

export default CamRevisePage;