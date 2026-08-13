import React, { useEffect, useState } from "react";
import api from '../../../../api/axiosInstance';

interface CamRejectWatchlistPageProps {
	apless: string;
	applNo: string;
	onDone: () => void;
}

const CamRejectWatchlistPage: React.FC<CamRejectWatchlistPageProps> = ({ apless, applNo, onDone }) => {
	const [lesseeName, setLesseeName] = useState("");
	const [loading, setLoading] = useState(true);
	const [reason, setReason] = useState("");
	const [message, setMessage] = useState<string | null>(null);
	const [submitting, setSubmitting] = useState(false);

	useEffect(() => {
		let cancelled = false;

		const load = async () => {
			setLoading(true);
			try {
				const res = await api.get('/CAM/RejectWatchlist/api/init', {
					params: { apless, applno: applNo },
				});
				if (!cancelled) setLesseeName(res.data.lesseeName || "");
			} catch {
				if (!cancelled) setMessage("Failed to load customer data.");
			} finally {
				if (!cancelled) setLoading(false);
			}
		};

		load();
		return () => {
			cancelled = true;
		};
	}, [apless, applNo]);

	const handleSubmit = async () => {
		if (!reason.trim()) {
			setMessage("Reason must not empty");
			return;
		}
		setSubmitting(true);
		setMessage(null);
		try {
			const res = await api.post('/CAM/RejectWatchlist/api/submit', {
				apless,
				applno: applNo,
				reason,
			});
			if (res.data.success) {
				alert(res.data.message);
				onDone();
			} else {
				setMessage(res.data.message);
			}
		} catch {
			setMessage("Failed to reject to watchlist. Please try again.");
		} finally {
			setSubmitting(false);
		}
	};

	return (
		<div className="w-full max-w-lg rounded-2xl bg-white shadow-2xl">
			<div className="p-6">
				<h2 className="text-xl font-bold text-red-600 mb-4">Reject to Watchlist</h2>

				{loading ? (
					<div className="flex justify-center py-10">
						<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
					</div>
				) : (
					<div className="space-y-4">
						<div className="flex justify-between text-sm">
							<span className="text-slate-500">CAM No.</span>
							<span className="font-medium text-slate-800">{applNo}</span>
						</div>
						<div className="flex justify-between text-sm">
							<span className="text-slate-500">Customer Name</span>
							<span className="font-medium text-slate-800">{lesseeName}</span>
						</div>
						<div>
							<label className="block text-sm font-medium text-slate-700 mb-1">Reason</label>
							<textarea
								value={reason}
								onChange={e => setReason(e.target.value)}
								rows={4}
								autoFocus
								className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-400"
							/>
						</div>
						{message && (
							<p className="text-sm text-red-600">{message}</p>
						)}
					</div>
				)}
			</div>

			{!loading && (
				<div className="flex justify-end gap-3 border-t border-slate-200 p-4">
					<button
						onClick={onDone}
						className="px-4 py-2 border border-slate-300 rounded-lg text-slate-600 hover:bg-slate-50 text-sm"
					>
						Cancel
					</button>
					<button
						onClick={handleSubmit}
						disabled={submitting}
						className="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:bg-slate-300 text-white rounded-lg text-sm font-medium"
					>
						{submitting ? "Submitting…" : "Submit"}
					</button>
				</div>
			)}
		</div>
	);
};

export default CamRejectWatchlistPage;