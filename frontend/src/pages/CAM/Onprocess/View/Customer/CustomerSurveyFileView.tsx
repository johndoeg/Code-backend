import React, { useEffect, useState } from 'react';
import api from '../../../../../api/axiosInstance';
import { isImageFile } from '../../../../../constants/DefaultValue';
import type { CamCtx } from '../CamViewTabs';

interface SurveySummary {
	contract_status: string;
	customer_name: string;
	brand: string;
	model: string;
	type: string;
	chassis: string;
	bpkb_name: string;
	bpkb_age_suffix: string;
	engine: string;
	bpkb_address: string;
	year: string;
	condition: string;
	supplier: string;
	color: string;
	police_no: string;
}

interface SurveyFile {
	id: number;
	name: string;
	download_url: string | null;
}

interface SurveySection {
	files: SurveyFile[];
	notes: string;
}

interface SurveyFileData {
	no_data: boolean;
	summary: SurveySummary;
	sections: {
		home: SurveySection;
		office: SurveySection;
		other: SurveySection;
	};
}

interface PreviewState {
	open: boolean;
	name: string;
	url: string;
}

const PREVIEW_CLOSED: PreviewState = { open: false, name: '', url: '' };

const DocPreviewModal: React.FC<{ state: PreviewState; onClose: () => void }> = ({ state, onClose }) => {
	const [imgError, setImgError] = useState(false);

	useEffect(() => {
		setImgError(false);
	}, [state.url]);

	if (!state.open) return null;

	const cleanName = state.name.split("?")[0];
	const isImage = isImageFile(cleanName);
	const isPdf = cleanName.split(".").pop()?.toLowerCase() === "pdf";

	return (
		<div
			onClick={onClose}
			style={{
				position: "fixed", inset: 0,
				background: "rgba(0,0,0,.7)",
				zIndex: 9999, display: "flex",
				justifyContent: "center", alignItems: "center",
			}}
		>
			<div
				onClick={(e) => e.stopPropagation()}
				style={{
					width: "90%", height: "90%",
					background: "#fff", borderRadius: 10,
					overflow: "hidden", display: "flex",
					flexDirection: "column",
				}}
			>
				<div style={{
					padding: "12px 16px",
					borderBottom: "1px solid #e5e7eb",
					display: "flex", justifyContent: "space-between", alignItems: "center",
				}}>
					<span style={{ fontWeight: 600, fontSize: ".9rem" }}>{state.name}</span>
					<button type="button" onClick={onClose} style={{ cursor: "pointer", background: "none", border: "none", fontSize: "1.2rem" }}>✕</button>
				</div>
				<div style={{ flex: 1, overflow: "hidden", padding: 20 }}>
					{isImage && !imgError ? (
						<img src={state.url} alt={state.name} style={{ width: "100%", height: "100%", objectFit: "contain" }} onError={() => setImgError(true)} />
					) : isPdf ? (
						<iframe title={state.name} src={state.url} width="100%" height="100%" />
					) : (
						<div style={{ textAlign: "center", paddingTop: 40 }}>
							<p style={{ marginBottom: 12, color: "#64748b" }}>
								{imgError ? "Failed to load image." : "Preview not available for this file type."}
							</p>
						</div>
					)}
				</div>
			</div>
		</div>
	);
};

const DocActionButton: React.FC<{ file: SurveyFile; onPreview: (file: SurveyFile) => void }> = ({ file, onPreview }) => {
	const [hovered, setHovered] = useState(false);

	if (!file.download_url) {
		return <span className="text-xs text-slate-300">Unavailable</span>;
	}

	return (
		<button
			type="button"
			onClick={() => onPreview(file)}
			onMouseEnter={() => setHovered(true)}
			onMouseLeave={() => setHovered(false)}
			style={{
				display: "inline-flex", alignItems: "center", gap: 6,
				border: `1px solid ${hovered ? "#ea580c" : "#f97316"}`,
				background: hovered ? "#f97316" : "#fff7ed",
				color: hovered ? "#fff" : "#c2410c",
				borderRadius: 6, padding: "5px 12px", fontSize: 13, fontWeight: 500,
				cursor: "pointer", transition: "background 0.15s, color 0.15s, border-color 0.15s",
			}}
		>
			<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
				<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
				<circle cx="12" cy="12" r="3" />
			</svg>
			View
		</button>
	);
};

function Card({ title, children }: { title: string; children: React.ReactNode }) {
	return (
		<div className="mb-4 overflow-hidden rounded-2xl bg-white shadow">
			<div className="border-b border-slate-100 bg-slate-50 px-5 py-3">
				<h2 className="text-sm font-bold text-slate-700">{title}</h2>
			</div>
			<div className="p-5">{children}</div>
		</div>
	);
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
	return (
		<div className="border-b border-slate-100 py-2 last:border-0">
			<dt className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</dt>
			<dd className="mt-0.5 text-sm text-slate-700">{value || '-'}</dd>
		</div>
	);
}

function NoDataCard() {
	return (
		<div className="rounded-2xl bg-white p-12 text-center shadow">
			<p className="text-2xl font-bold text-red-600">NO DATA</p>
		</div>
	);
}

const thCell = "border border-slate-300 bg-slate-100 px-4 py-2 text-left text-[11px] font-bold uppercase tracking-wide text-slate-600";
const tdCell = "border border-slate-200 px-4 py-2.5 text-sm text-slate-700";

function SurveyFileTable({ files, onPreview }: { files: SurveyFile[]; onPreview: (file: SurveyFile) => void }) {
	return (
		<div className="overflow-x-auto">
			<table className="w-full min-w-[500px] border border-slate-300 border-collapse text-sm">
				<thead>
					<tr>
						<th className={thCell} style={{ width: 60 }}>No.</th>
						<th className={thCell}>File Name</th>
						<th className={thCell} style={{ width: 140 }}>Actions</th>
					</tr>
				</thead>
				<tbody>
					{files.length === 0 ? (
						<tr><td className={tdCell} colSpan={3}>No file uploaded</td></tr>
					) : (
						files.map((f, idx) => (
							<tr key={f.id}>
								<td className={tdCell}>{idx + 1}</td>
								<td className={tdCell}>{f.name}</td>
								<td className={tdCell}>
									<DocActionButton file={f} onPreview={onPreview} />
								</td>
							</tr>
						))
					)}
				</tbody>
			</table>
		</div>
	);
}

function SurveyReportSection({
	title,
	section,
	onPreview,
}: {
	title: string;
	section: SurveySection;
	onPreview: (file: SurveyFile) => void;
}) {
	return (
		<Card title={title}>
			<div className="mb-4">
				<SurveyFileTable files={section.files} onPreview={onPreview} />
			</div>
			<h3 className="mb-2 text-sm font-semibold text-slate-600">Notes</h3>
			<div className="min-h-[120px] rounded-lg border border-slate-100 bg-slate-50 p-4 text-base text-slate-700 whitespace-pre-wrap">
				{section.notes || <span className="text-sm text-slate-400">No notes.</span>}
			</div>
		</Card>
	);
}

export default function CustomerSurveyFileView({ ctx }: { ctx: CamCtx }) {
	const [data, setData] = useState<SurveyFileData | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [preview, setPreview] = useState<PreviewState>(PREVIEW_CLOSED);

	useEffect(() => {
		let active = true;
		setLoading(true);
		setError(null);
		api
			.get('/CAM/View/api/customer-survey-file', { params: { apless: ctx.apless, applno: ctx.applno } })
			.then((res) => {
				if (active) setData(res.data);
			})
			.catch(() => {
				if (active) setError('Failed to load survey file.');
			})
			.finally(() => {
				if (active) setLoading(false);
			});
		return () => {
			active = false;
		};
	}, [ctx.apless, ctx.applno]);

	const handlePreview = (file: SurveyFile) => {
		if (!file.download_url) return;
		setPreview({ open: true, name: file.name, url: file.download_url });
	};

	if (loading) {
		return (
			<div className="rounded-2xl bg-white p-8 text-center text-sm text-slate-500 shadow">
				Loading survey file…
			</div>
		);
	}
	if (error || !data) {
		return (
			<div className="rounded-2xl bg-white p-8 text-center text-sm text-red-500 shadow">
				{error || 'No data found.'}
			</div>
		);
	}
	if (data.no_data) {
		return <NoDataCard />;
	}

	const s = data.summary;

	return (
		<div>
			<DocPreviewModal state={preview} onClose={() => setPreview(PREVIEW_CLOSED)} />

			<Card title="Survey Information">
				<dl className="grid grid-cols-1 gap-x-8 sm:grid-cols-2">
					<Field label="Contract Status" value={s.contract_status} />
					<Field label="Brand / Model / Type" value={`${s.brand}/${s.model}/${s.type}`} />
					<Field label="Customer Name" value={s.customer_name} />
					<Field label="Chassis" value={s.chassis} />
					<Field label="BPKB Name" value={`${s.bpkb_name}${s.bpkb_age_suffix}`} />
					<Field label="Engine" value={s.engine} />
					<Field label="BPKB Address" value={s.bpkb_address} />
					<Field label="Year / Condition" value={`${s.year}/${s.condition}`} />
					<Field label="Supplier" value={s.supplier} />
					<Field label="Color / Police No." value={`${s.color}/${s.police_no}`} />
				</dl>
			</Card>

			<SurveyReportSection title="Home Survey Report Form" section={data.sections.home} onPreview={handlePreview} />
			<SurveyReportSection title="Office Survey Report Form" section={data.sections.office} onPreview={handlePreview} />
			<SurveyReportSection title="Other Survey Report Form" section={data.sections.other} onPreview={handlePreview} />
		</div>
	);
}