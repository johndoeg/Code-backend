import { useCallback, useEffect, useState } from "react";
import api from "../../../../../api/axiosInstance";

export interface CAMRevisionNotesPageProps {
	apless: string;
	applNo: string;
	onSaved: (result: { apless: string; applno: string }) => void;
	onHome?: () => void;
}

const MAX_LENGTH = 255;

export default function CAMRevisionNotesPage({ apless, applNo, onSaved, onHome }: CAMRevisionNotesPageProps) {
	const [loading, setLoading] = useState(true);
	const [loadError, setLoadError] = useState("");
	const [notes, setNotes] = useState("");
	const [saving, setSaving] = useState(false);
	const [saveError, setSaveError] = useState("");
	const [advancing, setAdvancing] = useState(false);
	const [nextError, setNextError] = useState("");

	const isTooLong = notes.length > MAX_LENGTH;

	const load = useCallback(async () => {
		setLoading(true);
		setLoadError("");
		try {
			const res = await api.get("/CAM/EditIndex/revision-notes", { params: { apless, applno: applNo } });
			if (res.data.blocked) {
				setLoadError(res.data.message || "This application cannot be edited right now.");
			} else {
				setNotes(res.data.notes || "");
			}
		} catch {
			setLoadError("Failed to load Revision Notes. Please try again.");
		} finally {
			setLoading(false);
		}
	}, [apless, applNo]);

	useEffect(() => {
		load();
	}, [load]);

	const handleSave = async () => {
		if (isTooLong) {
			setSaveError(`Revision note must be ${MAX_LENGTH} characters or fewer.`);
			return;
		}
		setSaving(true);
		setSaveError("");
		try {
			const res = await api.post("/CAM/EditIndex/revision-notes/save", { apless, applno: applNo, notes });
			if (!res.data.success) {
				setSaveError(res.data.message || "Failed");
			}
		} catch (err: any) {
			setSaveError(err?.response?.data?.message || "Failed");
		} finally {
			setSaving(false);
		}
	};

	const handleNext = async () => {
		setAdvancing(true);
		setNextError("");
		try {
			const res = await api.post("/CAM/EditIndex/revision-notes/next", { apless, applno: applNo });
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
			<h2 className="text-base font-semibold text-slate-700">Revision Notes</h2>

			<div>
				<textarea
					value={notes}
					onChange={e => setNotes(e.target.value)}
					rows={6}
					className={`w-full rounded-lg border px-3 py-2 text-sm focus:outline-none ${isTooLong ? "border-red-400 focus:border-red-500" : "border-slate-300 focus:border-orange-500"
						}`}
				/>
				<div className="mt-1 flex items-center justify-between">
					{isTooLong ? (
						<p className="text-xs text-red-600">
							Revision note must be {MAX_LENGTH} characters or fewer — please shorten it before saving.
						</p>
					) : (
						<span />
					)}
					<p className={`text-right text-xs ${isTooLong ? "text-red-600" : "text-slate-400"}`}>
						{notes.length}/{MAX_LENGTH}
					</p>
				</div>
			</div>

			<div className="flex items-center gap-3">
				<button
					type="button"
					onClick={handleSave}
					disabled={saving || isTooLong}
					className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-green-700 disabled:opacity-50"
				>
					{saving ? "Saving…" : "Save"}
				</button>
				{saveError && <span className="text-sm text-red-600">{saveError}</span>}
			</div>

			<div className="flex justify-center border-t border-slate-100 pt-4">
				<button
					type="button"
					onClick={() => onHome?.()}
					className="rounded-lg bg-slate-700 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
				>
					Finish
				</button>
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