import React, { useEffect, useState, useCallback, useRef } from 'react';
import api from '../../../../../api/axiosInstance';
import type { CamCtx } from '../CamViewTabs';

interface HistoryRow {
	date: string; full_name: string; status_label: string;
	comment: string; recommendation: string; not_recommend: boolean;
}

interface SelectOpt { value: string; label: string; }
interface Watchlist { category: string; created_by: string; created_date: string; }
interface ApprovalData {
	cam_no_display: string; lessee_nm: string; cmo_nm: string;
	access_level: string; username: string;
	can_act: boolean; in_progress_by: string | null;
	is_completed: boolean; already_sent_to_admin: boolean; sent_to_admin_date: string | null;
	warning: string; disabled: boolean;
	rejection_message: string; withdrawn_message: string; watchlist: Watchlist | null;
	approval_history: HistoryRow[];
	show_form: boolean; show_watchlist_option: boolean;
	show_credit_recommendation: boolean; show_survey_section: boolean;
	strength: string; weakness: string; tbo: string;
	survey_independent_value: string; result_independent_value: string;
	survey_options: SelectOpt[]; result_options: SelectOpt[];
	mat_in: boolean; mat_kau: boolean;
	next_approver_options: SelectOpt[];
	red_code_selected: boolean; gps_vendor: string; gps_vendors: SelectOpt[];
	purpoffinc: string; tot_net_finance_end: number;
	is_cmo: boolean; is_multiple: boolean; multiple_appl_nos: string;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
	return (
		<div className="mb-4 overflow-hidden rounded-2xl bg-white shadow">
			<div className="border-b border-slate-100 bg-slate-50 px-5 py-3">
				<h2 className="text-sm font-semibold text-slate-700">{title}</h2>
			</div>
			<div className="p-5">{children}</div>
		</div>
	);
}

function HistoryTable({ rows }: { rows: HistoryRow[] }) {
	if (!rows.length)
		return <p className="text-sm italic text-slate-400">No approval history yet.</p>;
	return (
		<div className="overflow-x-auto">
			<table className="w-full min-w-[760px] text-sm">
				<thead>
					<tr className="border-b border-slate-200 text-left text-slate-500 uppercase tracking-wide">
						<th className="pb-3 pr-4 w-36">Date</th>
						<th className="pb-3 pr-4">Approval By</th>
						<th className="pb-3 pr-4 w-44">CAM Status</th>
						<th className="pb-3 w-28">Recommendation</th>
					</tr>
				</thead>
				<tbody>
					{rows.map((r, i) => (
						<tr key={i} className={`border-b border-slate-100 ${r.not_recommend ? 'bg-pink-50' : i % 2 === 0 ? 'bg-slate-50' : 'bg-white'}`}>
							<td className="py-3 pr-4 align-top text-base font-medium">{r.date}</td>
							<td className="py-3 pr-4 align-top">
								<div className="text-base font-bold text-slate-900">{r.full_name}</div>
								{r.comment && (
									<div className="mt-1 border-l-4 border-slate-300 bg-slate-100/70 rounded-r-md pl-3 pr-3 py-1 leading-snug">
										<span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">Comment</span>
										<p className="text-sm text-slate-600 mt-0 line-clamp-2">{r.comment}</p>
									</div>
								)}
							</td>
							<td className="py-3 pr-4 align-top text-base font-medium">{r.status_label}</td>
							<td className="py-3 align-top text-base font-medium">{r.recommendation}</td>
						</tr>
					))}
				</tbody>
			</table>
		</div>
	);
}

interface FormState {
	approvalSts: string; nextAppr: string; comment: string;
	strength: string; weakness: string; tbo: string;
	isisurv: string; isiresult: string;
	redCode: boolean; gpsVendor: string; notRecommend: boolean;
	resultOptions: SelectOpt[];
}

function ApprovalForm({
	data, ctx, onDone,
}: { data: ApprovalData; ctx: CamCtx; onDone: () => void }) {
	const [form, setForm] = useState<FormState>({
		approvalSts: 'A',
		nextAppr: data.next_approver_options[0]?.value ?? '',
		comment: '',
		strength: data.strength,
		weakness: data.weakness,
		tbo: data.tbo,
		isisurv: data.survey_independent_value,
		isiresult: data.result_independent_value,
		redCode: data.red_code_selected,
		gpsVendor: data.gps_vendor,
		notRecommend: false,
		resultOptions: data.result_options,
	});
	const [submitting, setSubmitting] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const set = (k: keyof FormState) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
		setForm(prev => ({ ...prev, [k]: e.target.value }));

	const handleSurveyChange = async (val: string) => {
		setForm(prev => ({ ...prev, isisurv: val, isiresult: '', resultOptions: [] }));
		if (val === '1') {
			try {
				const res = await api.get('/CAM/View/api/approval/result-options', { params: { isisurv: '1' } });
				setForm(prev => ({ ...prev, resultOptions: res.data }));
			} catch { }
		}
	};

	const handleSubmit = async () => {
		setError(null);
		if (form.approvalSts === 'A') {
			if (data.is_cmo && data.purpoffinc && ['3', '4'].includes(data.purpoffinc)
				&& data.tot_net_finance_end >= 3000000000) {
				const ok = window.confirm(
					`Total pembiayaan dari CAM ini ≥ Rp 3.000.000.000\n` +
					`sehingga cabang wajib melakukan Individual Assessment setiap tahun.\nLanjutkan?`
				);
				if (!ok) return;
			}
		} else if (form.approvalSts === 'RW') {
			const ok = window.confirm('Are you sure you want to Reject this CAM to Watchlist?');
			if (!ok) return;
		} else {
			const ok = window.confirm('Are you sure to reject this CAM?');
			if (!ok) return;
		}

		setSubmitting(true);
		try {
			const res = await api.post('/CAM/View/api/approval/confirm', {
				applno: ctx.applno,
				apless: ctx.apless,
				approval_sts: form.approvalSts,
				next_appr: form.nextAppr,
				comment: form.comment,
				strength: form.strength,
				weakness: form.weakness,
				tbo: form.tbo,
				isiresult: form.isiresult,
				resulti: data.result_independent_value,
				not_recommend: form.notRecommend ? 1 : 0,
				red_code: form.redCode ? '1' : '0',
				gps_vendor: form.gpsVendor,
				ind_cor: ctx.indCor,
				fin_type: ctx.finType,
				send_to_admin: 0,
			});
			if (res.data.redirect) {
				if (res.data.message) alert(res.data.message);
				onDone();
			}
		} catch (err: any) {
			setError(err.response?.data?.error || 'Submission failed. Please try again.');
		} finally {
			setSubmitting(false);
		}
	};

	const isReject = form.approvalSts !== 'A';
	return (
		<div className="space-y-4">
			{error && (
				<div className="rounded-lg bg-red-50 p-3 text-xs text-red-700 border border-red-200">{error}</div>
			)}

			<div className="flex items-center gap-4">
				<label className="flex items-center gap-2 text-sm text-slate-600">
					<input type="checkbox" checked={form.redCode}
						onChange={e => setForm(p => ({ ...p, redCode: e.target.checked }))}
						className="w-4 h-4 text-blue-600 rounded" />
					Red Code
				</label>
				{form.redCode && (
					<select value={form.gpsVendor} onChange={set('gpsVendor')}
						className="px-2 py-1.5 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500">
						<option value="">Select GPS Vendor</option>
						{data.gps_vendors.map(v => <option key={v.value} value={v.value}>{v.label}</option>)}
					</select>
				)}
			</div>

			{data.access_level !== 'CMO' && (
				<div className="flex items-center gap-4">
					<label className="text-sm text-slate-600 w-32 shrink-0">Approval Status</label>
					<select value={form.approvalSts} onChange={e => {
						const v = e.target.value;
						setForm(p => ({ ...p, approvalSts: v }));
					}}
						className="px-2 py-1.5 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500">
						<option value="A">Approve</option>
						<option value="R">Reject → Back to CMO</option>
						{data.show_watchlist_option && (
							<option value="RW" className="text-red-600">Reject → Added to Watchlist</option>
						)}
					</select>
					<label className="flex items-center gap-2 text-sm text-slate-600">
						<input type="checkbox" checked={form.notRecommend}
							onChange={e => setForm(p => ({ ...p, notRecommend: e.target.checked }))}
							className="w-4 h-4 text-blue-600 rounded" />
						Not Recommended
					</label>
				</div>
			)}

			<div className="flex items-center gap-4">
				<label className="text-sm text-slate-600 w-32 shrink-0">
					{data.is_cmo ? '1st Approval' : 'Next Approval'}
				</label>
				<select value={form.nextAppr}
					onChange={set('nextAppr')}
					disabled={isReject}
					className="flex-1 px-2 py-1.5 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 disabled:bg-slate-100 disabled:text-slate-400">
					{data.next_approver_options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
				</select>
			</div>

			<div className="flex gap-4">
				<label className="text-sm text-slate-600 w-32 shrink-0 pt-1">Comment</label>
				<textarea value={form.comment} onChange={set('comment')} rows={4}
					maxLength={5000}
					className="flex-1 px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500"
					placeholder={isReject ? 'Required for rejection' : 'Optional comment'} />
			</div>

			{data.show_survey_section && !data.is_cmo && (
				<div className="flex items-center gap-4">
					<label className="text-sm text-slate-600 w-32 shrink-0">Survey Independent</label>
					<select value={form.isisurv} onChange={e => handleSurveyChange(e.target.value)}
						disabled={data.mat_in}
						className="px-2 py-1.5 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 disabled:bg-slate-100">
						<option value="">Select</option>
						{data.survey_options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
					</select>
					<label className="text-sm text-slate-600 ml-4">Result</label>
					<select value={form.isiresult} onChange={set('isiresult')}
						disabled={data.mat_kau || form.isisurv !== '1'}
						className="px-2 py-1.5 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 disabled:bg-slate-100">
						<option value="">Select</option>
						{form.resultOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
					</select>
				</div>
			)}

			{data.show_credit_recommendation && (
				<div className="space-y-3">
					<p className="text-xs font-bold uppercase tracking-wide text-slate-600">Credit Recommendation</p>
					{(['strength', 'weakness', 'tbo'] as const).map(field => (
						<div key={field} className="flex gap-4">
							<label className="text-sm text-slate-600 w-32 shrink-0 pt-1 capitalize">
								{field === 'tbo' ? 'TBO/TC' : field}
							</label>
							<textarea
								value={form[field] as string}
								onChange={e => setForm(p => ({ ...p, [field]: e.target.value }))}
								rows={5}
								className="flex-1 px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-sans"
							/>
						</div>
					))}
				</div>
			)}

			<div className="flex gap-3 pt-2">
				<button onClick={handleSubmit} disabled={submitting || data.disabled}
					className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed">
					{submitting ? 'Processing…' : 'Confirm'}
				</button>
				<button onClick={onDone}
					className="px-5 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-medium rounded-lg transition">
					Cancel
				</button>
			</div>
		</div>
	);
}

export default function ApprovalView({ ctx }: { ctx: CamCtx }) {
	const [data, setData] = useState<ApprovalData | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const alertedWithdrawn = useRef(false);

	const load = useCallback(() => {
		setLoading(true);
		setError(null);
		api
			.get('/CAM/View/api/approval', {
				params: { apless: ctx.apless, applno: ctx.applno, fin_type: ctx.finType, ind_cor: ctx.indCor },
			})
			.then(res => setData(res.data))
			.catch(() => setError('Failed to load approval data.'))
			.finally(() => setLoading(false));
	}, [ctx.apless, ctx.applno, ctx.finType, ctx.indCor]);

	useEffect(() => { load(); }, [load]);

	useEffect(() => {
		if (data?.withdrawn_message && !alertedWithdrawn.current) {
			alertedWithdrawn.current = true;
			alert(data.withdrawn_message);
		}
	}, [data?.withdrawn_message]);

	if (loading) return <div className="p-8 text-center text-sm text-slate-500">Loading approval data…</div>;
	if (error || !data) return <div className="p-8 text-center text-sm text-red-500">{error || 'No data.'}</div>;

	return (
		<div>
			<Section title="Approval Review">
				<div className="space-y-1 text-sm">
					<div className="flex gap-2"><span className="w-32 text-slate-500">CAM No.</span><span className="font-medium">{data.cam_no_display}</span></div>
					<div className="flex gap-2"><span className="w-32 text-slate-500">Customer Name</span><span>{data.lessee_nm}</span></div>
					<div className="flex gap-2"><span className="w-32 text-slate-500">CMO Name</span><span>{data.cmo_nm}</span></div>
				</div>
			</Section>

			{data.withdrawn_message && (
				<div className="mb-4 rounded-xl bg-red-50 border border-red-300 p-4 text-sm text-red-700 font-medium">
					{data.withdrawn_message}
				</div>
			)}

			{data.warning && (
				<div className={`mb-4 rounded-xl p-4 text-sm ${data.disabled ? 'bg-red-50 border border-red-300 text-red-700' : 'bg-amber-50 border border-amber-300 text-amber-800'}`}>
					{data.warning}
				</div>
			)}
			{data.rejection_message && (
				<div className="mb-4 rounded-xl bg-amber-50 border border-amber-300 p-4 text-sm text-amber-800">
					{data.rejection_message}
				</div>
			)}
			{data.watchlist && (
				<div className="mb-4 rounded-xl bg-red-50 border border-red-300 p-4 text-sm text-red-700 space-y-1">
					<p className="font-semibold">⚠ Customer is on Watchlist</p>
					<p>Category: {data.watchlist.category}</p>
					<p className="text-xs text-red-500">By: {data.watchlist.created_by} on {data.watchlist.created_date}</p>
				</div>
			)}

			{data.is_completed && (
				<div className="mb-4 rounded-xl bg-green-50 border border-green-300 p-4 text-sm text-green-700 font-medium">
					This CAM has been completed.
				</div>
			)}
			{data.already_sent_to_admin && (
				<div className="mb-4 rounded-xl bg-blue-50 border border-blue-200 p-4 text-sm text-blue-700">
					This CAM has been sent to <strong>ADMIN</strong> at <strong>{data.sent_to_admin_date}</strong>.
				</div>
			)}
			{data.in_progress_by && data.in_progress_by.toUpperCase() !== data.username.toUpperCase() && (
				<div className="mb-4 rounded-xl bg-amber-50 border border-amber-300 p-4 text-sm text-amber-800">
					In Progress by: <strong>{data.in_progress_by}</strong>
				</div>
			)}

			<Section title="CAM Approval Status">
				<HistoryTable rows={data.approval_history} />
			</Section>

			{data.show_form && (
				<Section title="Approval Form">
					<ApprovalForm data={data} ctx={ctx} onDone={load} />
				</Section>
			)}
		</div>
	);
}