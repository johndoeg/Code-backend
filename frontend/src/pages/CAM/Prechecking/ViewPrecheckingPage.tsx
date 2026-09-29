import React, { useEffect, useState, useCallback } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import api from "../../../api/axiosInstance";
import { isImageFile } from "../../../constants/DefaultValue";

interface OcrField {
	value: string;
	confidence: string;
	verified: string;
}

interface OcrData {
	citizen: string;
	idCardNo: OcrField;
	name: OcrField;
	pob: OcrField;
	dob: OcrField;
	gender: OcrField;
	bloodType: OcrField;
	address: OcrField;
	rt: OcrField;
	rw: OcrField;
	subdistrict: OcrField;
	district: OcrField;
	city: OcrField;
	province: OcrField;
	religion: OcrField;
	job: OcrField;
	photo: string;
	signature: string;
}

interface Document {
	id: number;
	name: string;
	type: string;
	viewUrl: string;
}

interface ViewData {
	prechecking_id: string;
	apless: string;
	check_for: string;
	customer_type: string;
	lessee_type: string;
	new_ro: string;
	nationality: string;
	marital: string;
	is_carro: string;
	note: string;
	last_checking_date: string;
	outstanding: number;
	customer?: OcrData;
	spouse?: OcrData;
	wna_name?: string;
	wna_idcard?: string;
	sik: { subject: string; credit_bureau: string; status: string; score: string; grade: string; }[];
	documents: Record<string, Document[]>;
}

interface PreviewState {
	open: boolean;
	name: string;
	url: string;
}

const PREVIEW_CLOSED: PreviewState = {
	open: false,
	name: "",
	url: "",
};

const DocPreviewModal: React.FC<{
	state: PreviewState;
	onClose: () => void;
}> = ({ state, onClose }) => {
	const [imgError, setImgError] = useState(false);

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
					<button onClick={onClose} style={{ cursor: "pointer", background: "none", border: "none", fontSize: "1.2rem" }}>✕</button>
				</div>

				<div style={{ flex: 1, overflow: "hidden", padding: 20 }}>
					{isImage && !imgError ? (
						<img
							src={state.url}
							alt={state.name}
							style={{ width: "100%", height: "100%", objectFit: "contain" }}
							onError={() => setImgError(true)}
						/>
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

const DocChip: React.FC<{
	doc: Document;
	onPreview: (doc: Document) => void;
}> = ({ doc, onPreview }) => {
	const [hovered, setHovered] = useState(false);

	return (
		<div style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
			<button
				onClick={() => onPreview(doc)}
				onMouseEnter={() => setHovered(true)}
				onMouseLeave={() => setHovered(false)}
				style={{
					display: "inline-flex",
					alignItems: "center",
					gap: 6,
					border: `1px solid ${hovered ? "#ea580c" : "#f97316"}`,
					background: hovered ? "#f97316" : "#fff7ed",
					color: hovered ? "#fff" : "#c2410c",
					borderRadius: 6,
					padding: "5px 12px",
					fontSize: 13,
					fontWeight: 500,
					cursor: "pointer",
					transition: "background 0.15s, color 0.15s, border-color 0.15s",
				}}
			>
				<svg
					width="15" height="15"
					viewBox="0 0 24 24" fill="none"
					stroke="currentColor" strokeWidth="2"
					strokeLinecap="round" strokeLinejoin="round"
					aria-hidden="true"
				>
					<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
					<circle cx="12" cy="12" r="3" />
				</svg>
				View
			</button>
			<span style={{ fontSize: 13, color: "#374151" }}>{doc.name}</span>
		</div>
	);
};

const DocSection: React.FC<{
	label: string;
	docs: Document[];
	onPreview: (doc: Document) => void;
	loadingId?: number;
}> = ({ label, docs, onPreview, loadingId }) => (
	<tr style={{ borderBottom: "1px solid #F0F3FA" }}>
		<td style={{
			padding: "10px 14px", color: "#64748B",
			width: 192, verticalAlign: "top", fontSize: ".875rem",
		}}>{label}</td>
		<td style={{ padding: "10px 14px" }}>
			{!docs || docs.length === 0 ? (
				<span style={{ color: "#334155", fontSize: ".875rem" }}>
					No file(s) uploaded.
				</span>
			) : (
				<div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
					{
						docs.map((doc) => (
							<DocChip
								key={doc.id}
								doc={doc}
								onPreview={onPreview}
							/>
						))
					}
				</div>
			)}
		</td>
	</tr>
);

const KtpFileChips: React.FC<{
	docs: Document[];
	onPreview: (doc: Document) => void;
	loadingId?: number;
}> = ({ docs, onPreview }) => {
	if (!docs || docs.length === 0) return null;
	return (
		<div style={{ marginBottom: 12, display: "flex", flexWrap: "wrap", gap: 6 }}>
			{docs.map((d) => (
				<DocChip
					key={d.id}
					doc={d}
					onPreview={onPreview}
				/>
			))}
		</div>
	);
};

const ConfBadge: React.FC<{ value: string }> = ({ value }) => {
	if (!value || value === "0") return <span className="text-gray-400">—</span>;
	const n = parseFloat(value);
	const color = n >= 90
		? "text-green-700 bg-green-50 border-green-200"
		: n >= 70
			? "text-yellow-700 bg-yellow-50 border-yellow-200"
			: "text-red-700 bg-red-50 border-red-200";
	return (
		<span className={`px-2 py-0.5 rounded-full text-xs font-mono font-semibold border ${color}`}>
			{value}%
		</span>
	);
};

const VerBadge: React.FC<{ value: string }> = ({ value }) => {
	if (!value) return <span className="text-gray-400">—</span>;
	const color = value === "True"
		? "text-green-700 bg-green-50 border-green-200"
		: value === "False"
			? "text-red-700 bg-red-50 border-red-200"
			: "text-gray-500 bg-gray-50 border-gray-200";
	return (
		<span className={`px-2 py-0.5 rounded-full text-xs font-semibold border ${color}`}>
			{value || "—"}
		</span>
	);
};

const OcrTable: React.FC<{ title: string; data: OcrData }> = ({ title, data }) => {
	const rows = [
		{ label: "NIK", field: data.idCardNo },
		{ label: "Nama", field: data.name },
		{ label: "Tempat Lahir", field: data.pob },
		{ label: "Tanggal Lahir", field: data.dob },
		{ label: "Jenis Kelamin", field: data.gender },
		{ label: "Golongan Darah", field: data.bloodType },
		{ label: "Alamat", field: data.address },
		{
			label: "RT/RW",
			field: {
				value: `${data.rt.value} / ${data.rw.value}`,
				confidence: data.rt.confidence,
				verified: data.rt.verified,
			},
		},
		{ label: "Kelurahan/Desa", field: data.subdistrict },
		{ label: "Kecamatan", field: data.district },
		{ label: "Kota/Kabupaten", field: data.city },
		{ label: "Provinsi", field: data.province },
		{ label: "Agama", field: data.religion },
		{ label: "Pekerjaan", field: data.job },
	];

	return (
		<div className="rounded-xl border border-gray-200 overflow-hidden shadow-sm mb-6">
			<div className="bg-gradient-to-r from-blue-900 to-blue-700 px-4 py-3">
				<h3 className="text-white font-semibold text-sm">{title}</h3>
			</div>
			<div className="overflow-x-auto">
				<table className="w-full text-sm">
					<thead className="bg-gray-50">
						<tr>
							{["Field", "Value", "Confidence Rate", "Verification (Dukcapil)"].map((h) => (
								<th
									key={h}
									className="px-4 py-2.5 text-left text-s font-bold text-gray-600 uppercase tracking-wider whitespace-nowrap"
								>{h}</th>
							))}
						</tr>
					</thead>
					<tbody className="divide-y divide-gray-100">
						{rows.map(({ label, field }) => (
							<tr key={label} className="hover:bg-blue-50 transition-colors">
								<td className="px-4 py-2.5 font-medium text-gray-700 whitespace-nowrap w-40">{label}</td>
								<td className="px-4 py-2.5 text-gray-800">{field?.value || "—"}</td>
								<td className="px-4 py-2.5 text-center">
									<ConfBadge value={field?.confidence ?? ""} />
								</td>
								<td className="px-4 py-2.5 text-center">
									<VerBadge value={field?.verified ?? ""} />
								</td>
							</tr>
						))}
						<tr className="hover:bg-blue-50">
							<td className="px-4 py-2.5 font-medium text-gray-700">Foto</td>
							<td className="px-4 py-2.5" colSpan={3}>
								{data.photo ? (
									<img
										src={`data:image/jpeg;base64,${data.photo}`}
										alt="Foto"
										className="object-cover rounded-lg border border-gray-200 shadow-sm"
									/>
								) : (
									<div
										className="bg-gray-100 rounded-lg border-2 border-dashed border-gray-300 flex items-center justify-center text-gray-400 text-xs"
									>
										No Photo
									</div>
								)}
							</td>
						</tr>
						<tr className="hover:bg-blue-50">
							<td className="px-4 py-2.5 font-medium text-gray-700">Tanda Tangan</td>
							<td className="px-4 py-2.5" colSpan={3}>
								{data.signature ? (
									<img
										src={`data:image/jpeg;base64,${data.signature}`}
										alt="Tanda Tangan"
										style={{ height: 44 }}
										className="rounded border border-gray-200"
									/>
								) : (
									<div
										style={{ height: 44, width: 120 }}
										className="bg-gray-100 rounded border-2 border-dashed border-gray-300"
									/>
								)}
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>
	);
};

const SectionHeader: React.FC<{ title: string }> = ({ title }) => (
	<div className="flex items-center gap-3 mb-4">
		<span className="w-2 h-2 rounded-full bg-blue-600 flex-shrink-0" />
		<span className="text-xs font-bold uppercase tracking-widest text-blue-900">{title}</span>
		<hr className="flex-1 border-t-2 border-gray-100" />
	</div>
);

const FieldRow: React.FC<{ label: string; value?: React.ReactNode }> = ({ label, value }) => (
	<div className="flex gap-4 py-2 border-b border-gray-50 last:border-0">
		<span className="text-gray-500 text-sm w-48 flex-shrink-0">{label}</span>
		<span className="text-gray-800 text-sm font-medium">{value ?? "—"}</span>
	</div>
);

const DocRow: React.FC<{
	label: string;
	docs: Document[];
	onPreview: (doc: Document) => void;
}> = ({ label, docs, onPreview }) => (
	<div className="flex gap-4 py-2 border-b border-gray-50 last:border-0 items-start">
		<span className="text-gray-500 text-sm w-48 flex-shrink-0 pt-0.5">{label}</span>
		<div>
			{!docs || docs.length === 0 ? (
				<span style={{ color: "#334155", fontSize: ".875rem" }}>No file(s) uploaded.</span>
			) : (
				<div className="flex flex-wrap gap-2">
					{docs.map((doc) => (
						<DocChip key={doc.id} doc={doc} onPreview={onPreview} />
					))}
				</div>
			)}
		</div>
	</div>
);

const DisabledSelect: React.FC<{ label: string; value: string }> = ({ label, value }) => (
	<div className="flex gap-4 py-2 border-b border-gray-50 last:border-0 items-center">
		<span className="text-gray-500 text-sm w-48 flex-shrink-0">{label}</span>
		<div className="relative w-full max-w-md">
			<select
				disabled
				value={value}
				className="w-full appearance-none bg-gray-100 border border-gray-200 text-gray-600 text-sm rounded-lg pl-3 pr-9 py-2 cursor-not-allowed"
			>
				<option>{value || "—"}</option>
			</select>
			<svg
				className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400"
				fill="none" stroke="currentColor" viewBox="0 0 24 24"
			>
				<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
			</svg>
		</div>
	</div>
);

const DisabledTextarea: React.FC<{ label: string; value: string }> = ({ label, value }) => (
	<div className="flex gap-4 py-2 border-b border-gray-50 last:border-0 items-start">
		<span className="text-gray-500 text-sm w-48 flex-shrink-0 pt-2">{label}</span>
		<textarea
			disabled
			readOnly
			value={value}
			rows={2}
			className="w-full max-w-md bg-gray-100 border border-gray-200 text-gray-600 text-sm rounded-lg px-3 py-2 cursor-not-allowed resize-y"
		/>
	</div>
);

const ApprovalHistory: React.FC<{ apless: string; precheckingId: string }> = ({
	apless,
	precheckingId,
}) => {
	const [rows, setRows] = useState<any[]>([]);
	const [loading, setLoading] = useState(true);

	useEffect(() => {
		api
			.get("/Prechecking/View/approval-history", { params: { apless, prechecking_id: precheckingId } })
			.then((r) => setRows(r.data))
			.catch(() => setRows([]))
			.finally(() => setLoading(false));
	}, [apless, precheckingId]);

	if (loading) return (
		<div className="flex justify-center py-12">
			<svg className="animate-spin h-8 w-8 text-blue-600" fill="none" viewBox="0 0 24 24">
				<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
				<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
			</svg>
		</div>
	);

	if (!rows.length) return (
		<div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-12 text-center text-gray-400">
			No approval history found.
		</div>
	);

	return (
		<div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
			<table className="w-full text-sm">
				<thead className="bg-gray-50">
					<tr>
						{["Date", "Action", "By", "Remarks"].map((h) => (
							<th
								key={h}
								className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider"
							>{h}</th>
						))}
					</tr>
				</thead>
				<tbody className="divide-y divide-gray-100">
					{rows.map((row, i) => {
						const actionColor =
							row.action === "approve" ? "bg-green-100 text-green-700" :
								row.action === "reject" ? "bg-red-100 text-red-700" :
									row.action === "submit" ? "bg-blue-100 text-blue-700" :
										"bg-gray-100 text-gray-600";
						return (
							<tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-gray-50"}>
								<td className="px-4 py-3 whitespace-nowrap text-gray-500">{row.date}</td>
								<td className="px-4 py-3">
									<span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${actionColor}`}>
										{row.action}
									</span>
								</td>
								<td className="px-4 py-3 text-gray-700">{row.by}</td>
								<td className="px-4 py-3 text-gray-600">{row.remarks}</td>
							</tr>
						);
					})}
				</tbody>
			</table>
		</div>
	);
};

const spouseKtpDocType = (isIndividu: boolean, mainCitizen?: string): string => {
	const isMainWna = mainCitizen === "WNA";
	if (isIndividu) return isMainWna ? "cust-wna-spouse-ktp" : "cust-spouse-ktp";
	return isMainWna ? "guarantor-wna-spouse-ktp" : "guarantor-spouse-ktp";
};

export interface ViewPrecheckingPageProps {
	apless?: string;
	precheckingId?: string;
	onClose?: () => void;
}

const ViewPrecheckingPage: React.FC<ViewPrecheckingPageProps> = ({
	apless: aplessProp,
	precheckingId: precheckingIdProp,
	onClose,
}) => {
	const [searchParams] = useSearchParams();
	const navigate = useNavigate();

	const embedded = precheckingIdProp !== undefined;
	const apless = aplessProp ?? searchParams.get("apless") ?? "";
	const prechecking_id = precheckingIdProp ?? searchParams.get("prechecking_id") ?? "";

	const [data, setData] = useState<ViewData | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [tab, setTab] = useState<"data" | "history">("data");

	const [fetchingId, setFetchingId] = useState<number | undefined>();

	useEffect(() => {
		if (!apless || !prechecking_id) return;
		setLoading(true);
		api
			.get("/Prechecking/View/get-data", { params: { apless, prechecking_id } })
			.then((res) => setData(res.data))
			.catch(() => setError("Failed to load prechecking data."))
			.finally(() => setLoading(false));
	}, [apless, prechecking_id]);

	const [preview, setPreview] =
		useState<PreviewState>(PREVIEW_CLOSED);

	const handlePreview = async (doc: Document) => {
		console.log('data', doc.viewUrl)
		try {
			const res = await api.get(doc.viewUrl);
			setPreview({
				open: true,
				name: res.data.file_name || doc.name,
				url: res.data.url,
			});
		} catch (e) {
			console.error("Failed to fetch presigned URL", e);
		}
	};

	const closePreview = useCallback(() => setPreview(PREVIEW_CLOSED), []);

	const goBack = () => {
		if (onClose) {
			onClose();
		} else {
			navigate(-1);
		}
	};

	if (loading) return (
		<div className={`bg-gray-50 flex items-center justify-center ${embedded ? '' : 'min-h-screen'}`}>
			<svg className="animate-spin h-10 w-10 text-blue-600" fill="none" viewBox="0 0 24 24">
				<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
				<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
			</svg>
		</div>
	);

	if (error) return (
		<div className={`bg-gray-50 flex items-center justify-center ${embedded ? '' : 'min-h-screen'}`}>
			<div className="bg-red-50 border border-red-200 rounded-xl p-8 text-center max-w-md">
				<p className="text-red-700 font-medium">{error}</p>
				<button
					onClick={goBack}
					className="mt-4 text-blue-600 hover:underline text-sm"
				>{embedded ? "✕ Close" : "← Go back"}</button>
			</div>
		</div>
	);

	if (!data) return null;

	const docs = data.documents ?? {};
	const isIndividu = data.check_for === "C" && data.customer_type === "PR";
	const isGuarnPR = data.check_for === "G" && data.customer_type === "PR";

	return (
		<div className={`bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6 ${embedded ? '' : 'min-h-screen'}`}>

			<DocPreviewModal
				state={preview}
				onClose={() => setPreview(PREVIEW_CLOSED)}
			/>

			<div className={embedded ? "w-full space-y-6" : "max-w-7xl mx-auto space-y-6"}>
				<div className="bg-gradient-to-r from-blue-900 via-blue-800 to-blue-600 rounded-2xl p-6 shadow-lg flex flex-col md:flex-row md:items-center md:justify-between gap-4">
					<div>
						<h1 className="text-white text-2xl font-bold">View Prechecking Data</h1>
						<p className="text-blue-200 text-sm mt-1">
							Prechecking ID:{" "}
							<span className="font-mono font-semibold text-white">{data.prechecking_id}</span>
						</p>
					</div>
					<button
						onClick={goBack}
						className="self-start md:self-auto bg-white/15 hover:bg-white/25 border border-white/30 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors flex items-center gap-2"
					>
						{embedded ? (
							<>
								<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
								</svg>
								Close
							</>
						) : (
							<>
								<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
										d="M10 19l-7-7m0 0l7-7m-7 7h18" />
								</svg>
								Back
							</>
						)}
					</button>
				</div>

				<div className="flex gap-1 bg-white rounded-xl p-1 shadow-sm border border-gray-100 w-fit">
					{(["data", "history"] as const).map((t) => (
						<button
							key={t}
							onClick={() => setTab(t)}
							className={`px-5 py-2 rounded-lg text-sm font-medium transition-all ${tab === t
								? "bg-blue-600 text-white shadow-sm"
								: "text-gray-600 hover:text-gray-800 hover:bg-gray-50"
								}`}
						>
							{t === "data" ? "Prechecking Data" : "Approval History"}
						</button>
					))}
				</div>

				{tab === "data" && (
					<div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 space-y-8">

						<section>
							<SectionHeader title="General Information" />
							<div className="grid md:grid-cols-2 gap-x-12">
								<div>
									<FieldRow label="Checking For"
										value={data.check_for === "C" ? "Customer" : "Guarantor"} />
									<FieldRow label="Type"
										value={data.customer_type === "PR" ? "Individu" : "Corporate"} />
									<FieldRow label="New / Repeat Order"
										value={data.new_ro === "1" ? "Repeat Order" : "New"} />
									<FieldRow label="Temp. Customer No."
										value={<span className="font-mono">{data.apless}</span>} />
								</div>
								<div>
									<FieldRow label="Nationality" value={data.nationality} />
									<FieldRow label="Last Prechecking Date"
										value={data.last_checking_date || "—"} />
									<FieldRow label="Outstanding"
										value={`IDR ${data.outstanding.toLocaleString("id-ID")}`} />
								</div>
							</div>
						</section>

						{(isIndividu || isGuarnPR) && data.customer && data.customer.citizen === "WNI" && (
							<section>
								<SectionHeader title={isIndividu ? "Customer KTP (OCR)" : "Guarantor KTP (OCR)"} />
								<KtpFileChips
									docs={docs[isIndividu ? "cust-ktp" : "guarantor-ktp"] ?? []}
									onPreview={handlePreview}
									loadingId={fetchingId}
								/>
								<OcrTable
									title={isIndividu ? "Customer · WNI" : "Guarantor · WNI"}
									data={data.customer}
								/>
							</section>
						)}

						{(isIndividu || isGuarnPR) && data.customer?.citizen === "WNA" && (
							<section>
								<SectionHeader title={isIndividu ? "Customer WNA" : "Guarantor WNA"} />
								<FieldRow label="Nama" value={data.wna_name} />
								<FieldRow label="ID Card No." value={data.wna_idcard} />
								<div className="mt-3 rounded-xl border border-gray-200 overflow-hidden">
									<table className="w-full text-sm">
										<tbody>
											<DocSection
												label="ID Card (KITAS/Passport)"
												docs={docs[isIndividu ? "cust-kitas" : "guarantor-kitas"] ?? []}
												onPreview={handlePreview}
												loadingId={fetchingId}
											/>
										</tbody>
									</table>
								</div>
							</section>
						)}

						{data.spouse && data.spouse.citizen === "WNI" && (
							<section>
								<SectionHeader title="Spouse KTP (OCR)" />
								<KtpFileChips
									docs={docs[spouseKtpDocType(isIndividu, data.customer?.citizen)] ?? []}
									onPreview={handlePreview}
									loadingId={fetchingId}
								/>
								<OcrTable title="Spouse · WNI" data={data.spouse} />
							</section>
						)}

						{data.spouse && data.spouse.citizen === "WNA" && (
							<section>
								<SectionHeader title="Spouse (WNA)" />
								<FieldRow label="Spouse Name" value={data.spouse.name?.value} />
								<FieldRow label="Spouse ID Card No." value={data.spouse.idCardNo?.value} />
								<div className="mt-3 rounded-xl border border-gray-200 overflow-hidden">
									<table className="w-full text-sm">
										<tbody>
											<DocSection
												label="Spouse KITAS"
												docs={docs[isIndividu ? "cust-spouse-kitas" : "guarantor-spouse-kitas"] ?? []}
												onPreview={handlePreview}
												loadingId={fetchingId}
											/>
										</tbody>
									</table>
								</div>
							</section>
						)}

						<section>
							<SectionHeader title="Marital Status, Documents &amp; Notes" />
							<div className="max-w-2xl">
								<DisabledSelect label="Marital Status" value={data.marital} />
								<DocRow
									label="KK (Kartu Keluarga)"
									docs={docs[isIndividu ? "cust-kk" : "guarantor-kk"] ?? []}
									onPreview={handlePreview}
								/>
								<DocRow
									label="NPWP"
									docs={docs[isIndividu ? "cust-npwp" : "guarantor-npwp"] ?? []}
									onPreview={handlePreview}
								/>
								<DocRow
									label="Akta Cerai / Akta Kematian"
									docs={docs[isIndividu ? "cust-marriage-or-death-statement" : "guarantor-marriage-or-death-statement"] ?? []}
									onPreview={handlePreview}
								/>
								<DisabledSelect label="Reference"
									value={data.is_carro === "1" ? "Carro" : "Non Carro"} />
								<DisabledTextarea label="Note for Prechecking" value={data.note} />
							</div>
						</section>

						{data.sik && data.sik.length > 0 && (
							<section>
								<SectionHeader title="SIK Checking Data" />
								<div className="rounded-xl border border-gray-200 overflow-hidden">
									<table className="w-full text-sm">
										<thead className="bg-gray-50">
											<tr>
												{["Subject", "Credit Bureau", "Status", "Score", "Grade"].map((h) => (
													<th
														key={h}
														className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider"
													>{h}</th>
												))}
											</tr>
										</thead>
										<tbody className="divide-y divide-gray-100">
											{data.sik.map((row, i) => (
												<tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-gray-50"}>
													<td className="px-4 py-2.5">{row.subject}</td>
													<td className="px-4 py-2.5">{row.credit_bureau}</td>
													<td className="px-4 py-2.5">{row.status}</td>
													<td className="px-4 py-2.5">{row.score}</td>
													<td className="px-4 py-2.5">{row.grade}</td>
												</tr>
											))}
										</tbody>
									</table>
								</div>
							</section>
						)}

					</div>
				)}

				{tab === "history" && (
					<ApprovalHistory apless={apless} precheckingId={prechecking_id} />
				)}

			</div>
		</div>
	);
};

export default ViewPrecheckingPage;