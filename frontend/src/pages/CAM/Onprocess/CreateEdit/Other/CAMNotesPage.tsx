import { useCallback, useEffect, useState } from "react";
import api from "../../../../../api/axiosInstance";

export interface CAMNotesPageProps {
	apless: string;
	applNo: string;
	onSaved: (result: { apless: string; applno: string }) => void;
	onHome?: () => void;
}

export default function CAMNotesPage({ apless, applNo, onSaved, onHome }: CAMNotesPageProps) {
	const [loading, setLoading] = useState(true);
	const [loadError, setLoadError] = useState("");
	const [notes, setNotes] = useState("");
	const [saving, setSaving] = useState(false);
	const [saveMessage, setSaveMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
	const [advancing, setAdvancing] = useState(false);
	const [nextError, setNextError] = useState("");

	const load = useCallback(async () => {
		setLoading(true);
		setLoadError("");
		try {
			const res = await api.get("/CAM/EditIndex/cam-notes", { params: { apless, applno: applNo } });
			if (res.data.blocked) {
				setLoadError(res.data.message || "This application cannot be edited right now.");
			} else {
				setNotes(res.data.notes || "");
			}
		} catch {
			setLoadError("Failed to load CAM Notes. Please try again.");
		} finally {
			setLoading(false);
		}
	}, [apless, applNo]);

	useEffect(() => {
		load();
	}, [load]);

	const handleSave = async () => {
		setSaving(true);
		setSaveMessage(null);
		try {
			const res = await api.post("/CAM/EditIndex/cam-notes/save", { apless, applno: applNo, notes });
			if (res.data.success) {
				setSaveMessage({ type: "success", text: "Successful" });
			} else {
				setSaveMessage({ type: "error", text: res.data.message || "Failed" });
			}
		} catch (err: any) {
			setSaveMessage({ type: "error", text: err?.response?.data?.message || "Failed" });
		} finally {
			setSaving(false);
		}
	};

	const handleNext = async () => {
		setAdvancing(true);
		setNextError("");
		try {
			const res = await api.post("/CAM/EditIndex/cam-notes/next", { apless, applno: applNo });
			if (res.data.success) {
				onSaved({ apless, applno: applNo });
			} else {
				setNextError(res.data.message || "Please try again.");
			}
		} catch (err: any) {
			setNextError(err?.response?.data?.message || "Please try again.");
		} finally {
			setAdvancing(false);
		}
	};

	if (loading) {
		return (
			<div className="rounded-2xl bg-white p-8 text-center shadow">
				<p className="text-sm text-slate-400">Loading…</p>
			</div>
		);
	}
	if (loadError) {
		return (
			<div className="rounded-2xl bg-white p-8 text-center shadow">
				<p className="text-sm text-red-600">{loadError}</p>
			</div>
		);
	}

	return (
		<div className="space-y-4 rounded-2xl bg-white p-6 shadow">
			<h2 className="text-base font-semibold text-slate-700">CAM Notes</h2>

			<textarea
				value={notes}
				onChange={e => setNotes(e.target.value)}
				rows={8}
				className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-orange-500 focus:outline-none"
			/>

			<div className="flex items-center gap-3">
				<button
					type="button"
					onClick={handleSave}
					disabled={saving}
					className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-green-700 disabled:opacity-50"
				>
					{saving ? "Saving…" : "Save"}
				</button>

				{saveMessage && (
					<span className={`text-sm ${saveMessage.type === "success" ? "text-green-600" : "text-red-600"}`}>
						{saveMessage.text}
					</span>
				)}

				{saveMessage?.type === "success" && (
					<button
						type="button"
						onClick={() => onHome?.()}
						className="rounded-lg bg-slate-700 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
					>
						Finish
					</button>
				)}
			</div>

			{nextError && <p className="text-sm text-red-600">{nextError}</p>}

			<div className="flex justify-end pt-2">
				<button
					type="button"
					onClick={handleNext}
					disabled={advancing}
					className="rounded-lg bg-orange-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-orange-600 disabled:opacity-50"
				>
					{advancing ? "Please wait…" : "Next"}
				</button>
			</div>
		</div>
	);
}