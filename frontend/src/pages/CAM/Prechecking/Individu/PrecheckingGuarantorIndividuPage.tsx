import React, { useState, useEffect } from "react";
import api from "../../../api/axiosInstance";
import OCRUploadSection from "../../../contexts/OCRUploadSection";
import { MAX_FILE_LIMIT } from "../../../constants/DefaultValue";

const fontLink = document.createElement("link");
fontLink.rel = "stylesheet";
fontLink.href =
	"https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap";
document.head.appendChild(fontLink);

interface GuarantorData {
	idCardNo: string; name: string; placeOfBirth: string; dateOfBirth: string;
	gender: string; bloodType: string; address: string; rt: string; rw: string;
	subdistrict: string; district: string; city: string; province: string;
	religion: string; job: string; citizen: string; photo: string; signature: string;
}
type ConfidenceMap = Partial<Record<keyof GuarantorData, string>>;
interface MaritalOption { value: string; label: string; }
interface ModalState {
	open: boolean; type: "reject" | "inprogress" | "valid" | "expired" | "";
	message: string; apless: string; precheckingId: string;
}
interface UploadedDoc { id: number; name: string; type: string; key: string; previewUrl?: string; view_url?: string | null; }

const EMPTY_GUARANTOR = (): GuarantorData => ({
	idCardNo: "", name: "", placeOfBirth: "", dateOfBirth: "",
	gender: "", bloodType: "", address: "", rt: "", rw: "",
	subdistrict: "", district: "", city: "", province: "",
	religion: "", job: "", citizen: "", photo: "", signature: "",
});

const IMAGE_EXTS = new Set(["png", "jpg", "jpeg", "gif", "bmp", "heic", "heif", "tiff", "tif", "webp"]);

const OCR_DOC_TYPES = new Set(["guarantor-ktp", "guarantor-spouse-ktp", "guarantor-wna-spouse-ktp"]);

const CSS = `
  :root {
    --navy:   #1B3A7A;
    --blue:   #2D5BE3;
    --sky:    #EBF1FF;
    --mint:   #10B981;
    --amber:  #F59E0B;
    --rose:   #EF4444;
    --ink:    #0F1D3C;
    --muted:  #64748B;
    --border: #DDE3F0;
    --card:   #FFFFFF;
    --bg:     #F2F5FB;
    --font:   'Plus Jakarta Sans', sans-serif;
    --mono:   'JetBrains Mono', monospace;
  }
  * { box-sizing: border-box; }
  body { font-family: var(--font); background: var(--bg); }

  .page-wrap { margin: 0 auto; padding: 10px; }

  .hdr {
    background: linear-gradient(135deg, #0F1D3C 0%, #1B3A7A 55%, #2D5BE3 100%);
    border-radius: 16px; padding: 20px 28px;
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 24px; box-shadow: 0 8px 32px rgba(27,58,122,.35);
    position: relative; overflow: hidden;
  }
  .hdr::after {
    content: ''; position: absolute; right: -40px; top: -40px;
    width: 160px; height: 160px; border-radius: 50%;
    background: rgba(255,255,255,.06); pointer-events: none;
  }
  .hdr-title { color: #fff; font-size: 1.125rem; font-weight: 800; letter-spacing: -.01em; }
  .hdr-sub { color: rgba(255,255,255,.65); font-size: .75rem; margin-top: 2px; }
  .hdr-badge {
    background: rgba(255,255,255,.12); border: 1px solid rgba(255,255,255,.2);
    border-radius: 10px; padding: 8px 16px; display: flex; flex-direction: column; align-items: flex-end;
  }
  .hdr-badge-label { color: rgba(255,255,255,.6); font-size: .7rem; text-transform: uppercase; letter-spacing: .08em; }
  .hdr-badge-value { color: #fff; font-size: .875rem; font-family: var(--mono); font-weight: 500; }

  .card {
    background: var(--card); border-radius: 16px;
    border: 1px solid var(--border); padding: 28px;
    box-shadow: 0 2px 12px rgba(15,29,60,.06); margin-bottom: 20px;
  }
  .section-label {
    display: flex; align-items: center; gap: 10px;
    font-size: .8rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: .1em; color: var(--navy); margin-bottom: 20px;
  }
  .section-label span.dot {
    width: 8px; height: 8px; border-radius: 50%; background: var(--blue); flex-shrink: 0;
  }
  .section-label hr { flex: 1; border: none; border-top: 1.5px solid var(--border); }

  .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px 28px; }
  @media (max-width: 700px) { .form-grid { grid-template-columns: 1fr; } }
  .form-field { display: flex; flex-direction: column; gap: 6px; }
  .form-field.full { grid-column: 1 / -1; }
  .form-label { font-size: .78rem; font-weight: 600; color: var(--ink); letter-spacing: .01em; }
  .form-label .req { color: var(--rose); margin-left: 2px; }
  .form-input, .form-select, .form-textarea {
    width: 100%; padding: 9px 14px; font-size: .875rem; font-family: var(--font);
    border: 1.5px solid var(--border); border-radius: 10px; color: var(--ink);
    background: #fff; transition: border-color .18s, box-shadow .18s; outline: none;
  }
  .form-input:focus, .form-select:focus, .form-textarea:focus {
    border-color: var(--blue); box-shadow: 0 0 0 3px rgba(45,91,227,.1);
  }
  .form-input.err, .form-select.err { border-color: var(--rose); }
  .form-textarea { resize: vertical; min-height: 72px; }
  .field-err { font-size: .72rem; color: var(--rose); margin-top: 2px; }

  .upload-zone {
    border: 2px dashed var(--border); border-radius: 12px;
    padding: 16px 20px; cursor: pointer;
    transition: border-color .2s, background .2s; background: #F8FAFF;
    display: flex; align-items: center; gap: 12px;
  }
  .upload-zone:hover { border-color: var(--blue); background: var(--sky); }
  .upload-zone-icon {
    width: 38px; height: 38px; border-radius: 10px;
    background: var(--sky); border: 1.5px solid var(--border);
    display: flex; align-items: center; justify-content: center; flex-shrink: 0;
    color: var(--blue);
  }
  .upload-zone-text { text-align: left; }
  .upload-zone-title { font-size: .82rem; font-weight: 600; color: var(--navy); }
  .upload-zone-sub { font-size: .72rem; color: var(--muted); margin-top: 1px; }

  .doc-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
  .doc-chip {
    display: inline-flex; align-items: center; gap: 4px;
    background: var(--sky); border: 1px solid #C7D7F8;
    border-radius: 6px; padding: 3px 8px;
    font-size: .72rem; font-weight: 500; color: var(--navy);
  }
  .doc-chip-btn {
    background: none; border: none; cursor: pointer; padding: 0 1px;
    color: var(--muted); display: flex; align-items: center; transition: color .15s; line-height: 1;
  }
  .doc-chip-btn:hover { color: var(--blue); }
  .doc-chip-del {
    background: none; border: none; cursor: pointer;
    color: var(--muted); font-size: .9rem; line-height: 1; padding: 0 1px; transition: color .15s;
  }
  .doc-chip-del:hover { color: var(--rose); }

  .sub-section { border-radius: 12px; padding: 20px; border: 1.5px solid; }
  .sub-section.blue   { border-color: #BFDBFE; background: #EFF6FF; }
  .sub-section.orange { border-color: #FED7AA; background: #FFF7ED; }
  .sub-section.purple { border-color: #DDD6FE; background: #F5F3FF; }
  .sub-section-title { font-size: .82rem; font-weight: 700; margin-bottom: 16px; }
  .sub-section.blue   .sub-section-title { color: #1E3A8A; }
  .sub-section.orange .sub-section-title { color: #9A3412; }
  .sub-section.purple .sub-section-title { color: #4C1D95; }

  .spin {
    display: inline-block; width: 18px; height: 18px; border-radius: 50%;
    border: 3px solid rgba(255,255,255,.3); border-top-color: #fff;
    animation: spin .7s linear infinite; flex-shrink: 0;
  }
  .spin.dark { border-color: rgba(27,58,122,.15); border-top-color: var(--navy); }
  @keyframes spin { to { transform: rotate(360deg); } }

  .modal-overlay {
    position: fixed; inset: 0; background: rgba(15,29,60,.5);
    display: flex; align-items: center; justify-content: center; z-index: 50;
    padding: 16px; backdrop-filter: blur(3px);
  }
  .modal-card {
    background: #fff; border-radius: 20px; width: 100%; max-width: 480px;
    overflow: hidden; box-shadow: 0 24px 80px rgba(15,29,60,.25);
    animation: modal-in .22s ease;
  }
  @keyframes modal-in { from { opacity:0; transform: scale(.94) translateY(8px); } }
  .modal-hdr {
    background: linear-gradient(135deg, #0F1D3C, #2D5BE3);
    padding: 18px 24px; display: flex; align-items: center; gap: 10px;
  }
  .modal-icon {
    width: 32px; height: 32px; border-radius: 50%;
    background: rgba(255,255,255,.15); display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
  }
  .modal-title { color: #fff; font-size: .95rem; font-weight: 700; }
  .modal-body { padding: 24px; font-size: .875rem; color: #334155; line-height: 1.6; }
  .modal-footer {
    padding: 16px 24px; border-top: 1px solid var(--border);
    display: flex; justify-content: flex-end; gap: 10px;
  }
  .btn-modal-primary {
    background: var(--navy); color: #fff; border: none; border-radius: 10px;
    padding: 9px 20px; font-size: .82rem; font-weight: 700; font-family: var(--font);
    cursor: pointer; transition: opacity .2s;
  }
  .btn-modal-primary:hover { opacity: .85; }
  .btn-modal-ghost {
    background: none; border: 1.5px solid var(--border); border-radius: 10px;
    padding: 9px 20px; font-size: .82rem; font-weight: 600; font-family: var(--font);
    cursor: pointer; color: var(--ink); transition: background .2s;
  }
  .btn-modal-ghost:hover { background: #F4F7FF; }

  .btn-primary {
    background: linear-gradient(135deg, var(--navy), var(--blue));
    color: #fff; border: none; border-radius: 12px;
    padding: 11px 28px; font-size: .875rem; font-weight: 700;
    font-family: var(--font); cursor: pointer;
    transition: opacity .2s, transform .15s;
    display: inline-flex; align-items: center; gap: 8px;
    box-shadow: 0 4px 16px rgba(45,91,227,.3);
  }
  .btn-primary:hover { opacity: .9; transform: translateY(-1px); }
  .btn-primary:disabled { opacity: .55; cursor: not-allowed; transform: none; }
  .btn-ghost {
    background: #fff; color: var(--ink); border: 1.5px solid var(--border);
    border-radius: 12px; padding: 11px 24px; font-size: .875rem; font-weight: 600;
    font-family: var(--font); cursor: pointer; transition: background .2s;
  }
  .btn-ghost:hover { background: #F4F7FF; }

  .select-wrap { position: relative; }
  .select-wrap select { appearance: none; padding-right: 36px; }
  .select-wrap::after {
    content: ''; position: absolute; right: 12px; top: 50%; transform: translateY(-50%);
    width: 0; height: 0;
    border-left: 5px solid transparent; border-right: 5px solid transparent;
    border-top: 6px solid var(--muted); pointer-events: none;
  }
  .select-wrap:focus-within::after { border-top-color: var(--blue); }

  .form-select.nat-active {
    border-color: var(--blue); background: var(--sky); color: var(--navy); font-weight: 700;
  }
  .form-input.is-readonly {
    background: #F4F7FF; color: var(--muted); cursor: default; border-color: #E8EEF8;
  }
  .form-select.is-disabled {
    background: #F4F7FF; color: var(--muted); cursor: default; border-color: #E8EEF8;
  }
`;

const styleTag = document.createElement("style");
styleTag.textContent = CSS;
document.head.appendChild(styleTag);

const Spinner: React.FC<{ dark?: boolean; size?: number }> = ({ dark, size = 18 }) => (
	<span className={`spin${dark ? " dark" : ""}`} style={{ width: size, height: size }} />
);

const FileInput: React.FC<{
	multiple?: boolean; onFileChange: (f: File) => void;
	label?: string; uploading?: boolean;
}> = ({ multiple, onFileChange, label = "Upload Document", uploading = false }) => {
	const ref = React.useRef<HTMLInputElement>(null);
	return (
		<label
			className="upload-zone"
			onClick={() => !uploading && ref.current?.click()}
			style={{ cursor: uploading ? "not-allowed" : "pointer", opacity: uploading ? 0.7 : 1 }}
		>
			<div className="upload-zone-icon">
				{uploading
					? <span className="spin dark" style={{ width: 18, height: 18 }} />
					: (
						<svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
								d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
						</svg>
					)
				}
			</div>
			<div className="upload-zone-text">
				<div className="upload-zone-title">{uploading ? "Mengupload…" : label}</div>
				<div className="upload-zone-sub">
					{uploading ? "Sedang upload ke server, harap tunggu" : "PNG, JPG, PDF, TIFF · max 2 MB"}
				</div>
			</div>
			<input
				ref={ref} type="file" multiple={multiple}
				accept=".png,.jpg,.jpeg,.pdf,.tiff"
				style={{ display: "none" }}
				disabled={uploading}
				onChange={(e) => {
					const f = e.target.files?.[0];
					if (f) { onFileChange(f); e.target.value = ""; }
				}}
			/>
		</label>
	);
};

const DocChip: React.FC<{
	doc: UploadedDoc;
	onPreview: (doc: UploadedDoc) => void;
	onDelete: (id: number) => void;
	isDeleting: boolean;
	isPreviewLoading: boolean;
	canPreview: boolean;
}> = ({ doc, onPreview, onDelete, isDeleting, isPreviewLoading, canPreview }) => {
	const [hovered, setHovered] = useState(false);

	return (
		<div style={{ display: "inline-flex", alignItems: "center", gap: 8, opacity: isDeleting ? 0.6 : 1 }}>
			{canPreview && (
				<button
					onClick={() => onPreview(doc)}
					onMouseEnter={() => setHovered(true)}
					onMouseLeave={() => setHovered(false)}
					disabled={isPreviewLoading}
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
						cursor: isPreviewLoading ? "not-allowed" : "pointer",
						transition: "background 0.15s, color 0.15s, border-color 0.15s",
					}}
				>
					{isPreviewLoading ? (
						<span style={{ width: 13, height: 13, display: "inline-block", borderRadius: "50%", border: "2px solid rgba(194,65,12,.3)", borderTopColor: "#c2410c", animation: "spin .7s linear infinite" }} />
					) : (
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
					)}
					View
				</button>
			)}
			<span style={{ fontSize: 13, color: "#374151" }}>{doc.name}</span>
			{isDeleting
				? <span className="spin dark" style={{ width: 12, height: 12 }} />
				: <button className="doc-chip-del" title="Hapus" onClick={() => onDelete(doc.id)}>×</button>
			}
		</div>
	);
};

const DocList: React.FC<{
	docs: UploadedDoc[];
	onDelete: (id: number) => void;
	deletingDocs?: Set<number>;
	onPreview: (doc: UploadedDoc) => void;
	previewLoadingId?: number | null;
}> = ({ docs, onDelete, deletingDocs = new Set(), onPreview, previewLoadingId = null }) =>
		docs.length ? (
			<div className="doc-chips" style={{ flexDirection: "column", alignItems: "flex-start", gap: 8 }}>
				{docs.map((d) => {
					const ext = d.name.split(".").pop()?.toLowerCase() ?? "";
					const canPreview = IMAGE_EXTS.has(ext) || ext === "pdf";
					return (
						<DocChip
							key={d.id}
							doc={d}
							onPreview={onPreview}
							onDelete={onDelete}
							isDeleting={deletingDocs.has(d.id)}
							isPreviewLoading={previewLoadingId === d.id}
							canPreview={canPreview}
						/>
					);
				})}
			</div>
		) : null;

interface PreviewState { open: boolean; name: string; previewUrl?: string; }
const PREVIEW_CLOSED: PreviewState = { open: false, name: "", previewUrl: undefined };

const DocPreviewModal: React.FC<{ state: PreviewState; onClose: () => void }> = ({ state, onClose }) => {
	if (!state.open) return null;
	const ext = state.name.split(".").pop()?.toLowerCase() ?? "";
	const isImage = IMAGE_EXTS.has(ext);
	const isPdf = ext === "pdf";

	React.useEffect(() => {
		const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
		window.addEventListener("keydown", handler);
		return () => window.removeEventListener("keydown", handler);
	}, [onClose]);

	return (
		<div className="preview-overlay" onClick={onClose}
			style={{ position: "fixed", inset: 0, background: "rgba(10,18,40,.8)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 200, padding: 24, backdropFilter: "blur(6px)" }}>
			<div onClick={(e) => e.stopPropagation()}
				style={{ background: "#fff", borderRadius: 20, overflow: "hidden", boxShadow: "0 32px 96px rgba(10,18,40,.4)", display: "flex", flexDirection: "column", width: "min(90vw,800px)", maxHeight: "90vh" }}>
				<div style={{ background: "linear-gradient(135deg,#0F1D3C,#2D5BE3)", padding: "14px 20px", display: "flex", alignItems: "center", gap: 10 }}>
					<span style={{ color: "#fff", fontSize: ".875rem", fontWeight: 700, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{state.name}</span>
					<button onClick={onClose} style={{ background: "rgba(255,255,255,.15)", border: "1px solid rgba(255,255,255,.25)", borderRadius: 8, width: 32, height: 32, cursor: "pointer", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "1.2rem" }}>×</button>
				</div>
				<div style={{ overflow: "auto", display: "flex", alignItems: "center", justifyContent: "center", padding: 24, background: "#F2F5FB", flex: 1, minHeight: 0 }}>
					{isImage && state.previewUrl
						? <img src={state.previewUrl} alt={state.name} style={{ maxWidth: "100%", maxHeight: "65vh", objectFit: "contain", borderRadius: 10, boxShadow: "0 4px 24px rgba(10,18,40,.18)" }} />
						: isPdf && state.previewUrl
							? <iframe src={state.previewUrl} title={state.name} style={{ width: "100%", height: "60vh", border: "none", borderRadius: 10 }} />
							: <p style={{ color: "#64748B" }}>Preview tidak tersedia untuk tipe file ini</p>
					}
				</div>
				<div style={{ padding: "12px 20px", borderTop: "1px solid #DDE3F0", display: "flex", justifyContent: "flex-end", background: "#fff" }}>
					<button onClick={onClose} className="btn-modal-ghost">Tutup</button>
				</div>
			</div>
		</div>
	);
};

const HistoryModal: React.FC<{
	modal: ModalState; setModal: React.Dispatch<React.SetStateAction<ModalState>>;
}> = ({ modal, setModal }) => {
	const close = () => setModal((m) => ({ ...m, open: false }));
	return (
		<div className="modal-overlay">
			<div className="modal-card">
				<div className="modal-hdr">
					<div className="modal-icon">
						<svg width="16" height="16" fill="none" stroke="#fff" viewBox="0 0 24 24">
							<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
								d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
						</svg>
					</div>
					<span className="modal-title">Notification</span>
				</div>
				<div className="modal-body">{modal.message}</div>
				<div className="modal-footer">
					{modal.type === "reject" && (
						<>
							<button className="btn-modal-ghost" onClick={() => window.history.back()}>NO</button>
							<button className="btn-modal-primary" onClick={close}>YES – Continue</button>
						</>
					)}
					{modal.type === "valid" && (
						<>
							<button className="btn-modal-ghost" onClick={() => window.location.href = `/repeat-order-guarantor?apless=${modal.apless}&prechecking_id=${modal.precheckingId}&types=G`}>Prechecking</button>
							<button className="btn-modal-primary" onClick={() => window.location.href = `/create-cam?apless=${modal.apless}&prechecking_id=${modal.precheckingId}&lessee_tp=PR`}>Create New CAM</button>
						</>
					)}
					{(modal.type === "inprogress" || modal.type === "expired") && (
						<button className="btn-modal-primary" onClick={() => {
							close();
							if (modal.type === "expired") window.location.href = `/repeat-order-guarantor?apless=${modal.apless}&prechecking_id=${modal.precheckingId}&types=G`;
						}}>Close</button>
					)}
				</div>
			</div>
		</div>
	);
};

const PrecheckingGuarantorIndividuPage: React.FC = () => {
	const [precheckingId, setPrecheckingId] = useState("");
	const [apless, setApless] = useState("");
	const [nationality, setNationality] = useState<"WNI" | "WNA">("WNI");
	const [marital, setMarital] = useState("");
	const [spouseNat, setSpouseNat] = useState<"WNI" | "WNA" | "">("");
	const [wnaMarital, setWnaMarital] = useState("");
	const [wnaSpouseNat, setWnaSpouseNat] = useState<"WNI" | "WNA" | "">("");
	const [isCarro, setIsCarro] = useState(true);
	const [notes, setNotes] = useState("");
	const [maritalOptions, setMaritalOptions] = useState<MaritalOption[]>([]);

	const [guarantor, setGuarantor] = useState<GuarantorData>(EMPTY_GUARANTOR());
	const [spouse, setSpouse] = useState<GuarantorData>(EMPTY_GUARANTOR());
	const [wnaSpouse, setWnaSpouse] = useState<GuarantorData>(EMPTY_GUARANTOR());
	const [wnaName, setWnaName] = useState("");
	const [wnaIdCard, setWnaIdCard] = useState("");
	const [wnaSpName, setWnaSpName] = useState("");
	const [wnaSpId, setWnaSpId] = useState("");

	const [guarantorConf, setGuarantorConf] = useState<ConfidenceMap>({});
	const [spouseConf, setSpouseConf] = useState<ConfidenceMap>({});
	const [wnaSpConf, setWnaSpConf] = useState<ConfidenceMap>({});

	const [docs, setDocs] = useState<UploadedDoc[]>([]);
	const [uploadingDocs, setUploadingDocs] = useState<Set<string>>(new Set());
	const [deletingDocs, setDeletingDocs] = useState<Set<number>>(new Set());
	const [preview, setPreview] = useState<PreviewState>(PREVIEW_CLOSED);
	const [previewLoadingId, setPreviewLoadingId] = useState<number | null>(null);

	const [loading, setLoading] = useState(false);
	const [errors, setErrors] = useState<Record<string, string>>({});
	const [modal, setModal] = useState<ModalState>({ open: false, type: "", message: "", apless: "", precheckingId: "" });

	useEffect(() => {
		const init = async () => {
			setLoading(true);
			try {
				const [aplessR, pidR, maritalR] = await Promise.all([
					api.post('/CAM/Prechecking/generate-apless', { customer_type: "G" }),
					api.post('/CAM/Prechecking/generate-prechecking-id', {}),
					api.get('/CAM/Prechecking/marital-statuses'),
				]);
				setApless(aplessR.data);
				setPrecheckingId(pidR.data);
				setMaritalOptions(maritalR.data);
			} catch (e) { console.error("Init error", e); }
			finally { setLoading(false); }
		};
		init();
	}, []);

	const _uploadDoc = async (file: File, docType: string) => {
		const MAX_MB = MAX_FILE_LIMIT;
		const ALLOWED_EXTS = [".png", ".jpg", ".jpeg", ".pdf", ".tiff", ".tif", ".bmp", ".gif", ".heic", ".heif", ".xlsx", ".docx"];
		const ext = "." + file.name.split(".").pop()!.toLowerCase();

		if (!ALLOWED_EXTS.includes(ext)) {
			alert("Format file tidak didukung.\nFormat yang diizinkan: PNG, JPG, PDF, TIFF, BMP, GIF, HEIC, XLSX, DOCX");
			return;
		}

		if (ext !== ".pdf" && file.size > MAX_MB * 1024 * 1024) {
			alert(`Ukuran file melebihi batas maksimal (${MAX_MB} MB).`);
			return;
		}

		let localPreviewUrl: string | undefined;
		const extClean = ext.replace(".", "");
		if (IMAGE_EXTS.has(extClean) || ext === ".pdf") {
			localPreviewUrl = URL.createObjectURL(file);
		}

		setUploadingDocs((prev) => new Set(prev).add(docType));
		try {
			const fd = new FormData();
			fd.append("file", file);
			fd.append("apless", apless);
			fd.append("prechecking_id", precheckingId);
			fd.append("document_type", docType);
			fd.append("cust_type", "PR");
			fd.append("organization_type", "GUARNPR");

			const res = await api.post(
				'/CAM/Prechecking/upload-document-guarantor',
				fd,
				{ headers: { "Content-Type": "multipart/form-data" } },
			);

			if (!res.data?.success) {
				alert(res.data?.message ?? "Upload gagal. Silakan coba lagi.");
				if (localPreviewUrl) URL.revokeObjectURL(localPreviewUrl);
				return;
			}

			await _refreshDocs(localPreviewUrl, res.data.document_name);
		} catch (e: any) {
			if (localPreviewUrl) URL.revokeObjectURL(localPreviewUrl);
			alert(e.response?.data?.message ?? "Upload gagal. Periksa koneksi dan coba lagi.");
		} finally {
			setUploadingDocs((prev) => {
				const next = new Set(prev);
				next.delete(docType);
				return next;
			});
		}
	};

	const _refreshDocs = async (newPreviewUrl?: string, newDocName?: string) => {
		if (!apless || !precheckingId) return;
		try {
			const res = await api.get('/CAM/Prechecking/documents-guarantor', {
				params: { apless, prechecking_id: precheckingId },
			});
			const fetched: UploadedDoc[] = res.data ?? [];
			setDocs((prev) => {
				const previewMap = new Map(prev.map((d) => [d.id, d.previewUrl]));
				return fetched.map((d) => ({
					...d,
					previewUrl:
						(newDocName && d.name === newDocName)
							? newPreviewUrl
							: previewMap.get(d.id),
				}));
			});
		} catch (e) {
			console.error("Failed to refresh docs", e);
		}
	};

	const _nikForDocType = (docType: string): string => {
		if (docType === "guarantor-ktp") return guarantor.idCardNo;
		if (docType === "guarantor-spouse-ktp") return spouse.idCardNo;
		if (docType === "guarantor-wna-spouse-ktp") return wnaSpouse.idCardNo;

		return "";
	};

	const _clearDataForDocType = (docType: string) => {
		if (docType === "guarantor-ktp") {
			setGuarantor(EMPTY_GUARANTOR());
			setGuarantorConf({});
		} else if (docType === "guarantor-spouse-ktp") {
			setSpouse(EMPTY_GUARANTOR());
			setSpouseConf({});
		} else if (docType === "guarantor-wna-spouse-ktp") {
			setWnaSpouse(EMPTY_GUARANTOR());
			setWnaSpConf({});
		}
	};

	const handleDeleteDoc = async (docId: number) => {
		if (!window.confirm("Apakah Anda yakin ingin menghapus dokumen ini?")) return;
		setDeletingDocs((prev) => new Set(prev).add(docId));
		try {
			const doc = docs.find((d) => d.id === docId);
			if (doc?.previewUrl?.startsWith("blob:")) URL.revokeObjectURL(doc.previewUrl);

			const nik = doc ? _nikForDocType(doc.type) : "";

			const res = await api.post('/CAM/Prechecking/delete-document-guarantor', {
				customer_document_id: docId,
				prechecking_id: precheckingId,
				nik,
			});
			if (!res.data?.success) {
				alert(res.data?.message ?? "Hapus dokumen gagal. Silakan coba lagi.");
				return;
			}

			if (doc && OCR_DOC_TYPES.has(doc.type)) {
				_clearDataForDocType(doc.type);
			}

			await _refreshDocs();
		} catch (e: any) {
			alert(e.response?.data?.message ?? "Hapus dokumen gagal. Periksa koneksi dan coba lagi.");
		} finally {
			setDeletingDocs((prev) => {
				const next = new Set(prev);
				next.delete(docId);
				return next;
			});
		}
	};

	const handlePreview = async (doc: UploadedDoc) => {
		if (doc.previewUrl) {
			setPreview({ open: true, name: doc.name, previewUrl: doc.previewUrl });
			return;
		}

		if (doc.view_url) {
			setPreview({ open: true, name: doc.name, previewUrl: doc.view_url });
			return;
		}
		setPreviewLoadingId(doc.id);
		try {
			const res = await api.get('/CAM/Prechecking/view-document-guarantor', {
				params: { customer_document_id: doc.id },
			});

			if (res.data?.success && res.data?.view_url) {
				setPreview({ open: true, name: doc.name, previewUrl: res.data.view_url });
			} else {
				alert(res.data?.message ?? "Dokumen tidak dapat ditampilkan.");
			}
		} catch (e: any) {
			alert(e.response?.data?.message ?? "Gagal memuat pratinjau dokumen.");
		} finally {
			setPreviewLoadingId(null);
		}
	};

	const handleWnaIdBlur = async () => {
		if (wnaIdCard.length < 6) return;
		try {
			const res = await api.post('/CAM/Prechecking/check-customer-history', {
				idNo: wnaIdCard, prechecking_id: precheckingId, lesseeType: "PR", checking_for: "G",
			});
			const [msg, al, type, pid] = res.data;

			if (msg) setModal({ open: true, type, message: msg, apless: al, precheckingId: pid });
		} catch (e) { console.error(e); }
	};

	const handleCancel = async () => {
		try { await api.post('/CAM/Prechecking/cancel-guarantor', { prechecking_id: precheckingId }); }
		finally { window.history.back(); }
	};

	const isMarried = ["M", "O"].includes(marital);
	const showSpouseNat = nationality === "WNI" && isMarried;
	const showSpouseOCR = showSpouseNat && spouseNat === "WNI";
	const showWnaSpInfo = showSpouseNat && spouseNat === "WNA";
	const showWnaSection = nationality === "WNA";
	const isWnaMarried = ["M", "O"].includes(wnaMarital);
	const showWnaSpNat = showWnaSection && isWnaMarried;
	const showWnaSpOCR = showWnaSpNat && wnaSpouseNat === "WNI";
	const showWnaSpWna = showWnaSpNat && wnaSpouseNat === "WNA";

	const handleSubmit = async () => {
		const e: Record<string, string> = {};

		if (nationality === "WNI") {
			if (!guarantor.idCardNo) e.guarantor_idCardNo = "NIK is required";
			if (!guarantor.name) e.guarantor_name = "Nama is required";
			if (!guarantor.placeOfBirth) e.guarantor_pob = "Tempat Lahir is required";
			if (!guarantor.dateOfBirth) e.guarantor_dob = "Tanggal Lahir is required";
			if (!guarantor.gender) e.guarantor_gender = "Jenis Kelamin is required";
			if (!guarantor.address) e.guarantor_address = "Alamat is required";
			if (!guarantor.rt) e.guarantor_rt = "RT/RW is required";
			if (!guarantor.subdistrict) e.guarantor_subdistrict = "Kelurahan/Desa is required";
			if (!guarantor.district) e.guarantor_district = "Kecamatan is required";
			if (!guarantor.city) e.guarantor_city = "Kota/Kabupaten is required";
			if (!guarantor.province) e.guarantor_province = "Provinsi is required";
			if (!guarantor.religion) e.guarantor_religion = "Agama is required";
			if (!guarantor.job) e.guarantor_job = "Pekerjaan is required";
			if (!marital) e.marital = "Marital Status is required";
		} else {
			if (!wnaName) e.wna_name = "Nama is required";
			if (!wnaIdCard) e.wna_idcard = "ID Card No. is required";
			if (!wnaMarital) e.wna_marital = "Marital Status is required";
		}

		if (showSpouseNat) {
			if (!spouseNat) {
				e.spouse_nat = "Spouse Nationality is required";
			} else if (spouseNat === "WNI") {
				if (!spouse.idCardNo) e.spouse_idCardNo = "Spouse NIK is required";
				if (!spouse.name) e.spouse_name = "Spouse Nama is required";
				if (!spouse.placeOfBirth) e.spouse_pob = "Spouse Tempat Lahir is required";
				if (!spouse.dateOfBirth) e.spouse_dob = "Spouse Tanggal Lahir is required";
				if (!spouse.gender) e.spouse_gender = "Spouse Jenis Kelamin is required";
				if (!spouse.address) e.spouse_address = "Spouse Alamat is required";
			} else if (spouseNat === "WNA") {
				if (!wnaSpName) e.wna_spouse_name = "Spouse Name is required";
				if (!wnaSpId) e.wna_spouse_idcard = "Spouse ID Card No. is required";
			}
		}

		if (showWnaSpNat) {
			if (!wnaSpouseNat) {
				e.wna_spouse_nat = "Spouse Nationality is required";
			} else if (wnaSpouseNat === "WNI") {
				if (!wnaSpouse.idCardNo) e.wna_spouse_ktp_idCardNo = "Spouse NIK is required";
				if (!wnaSpouse.name) e.wna_spouse_ktp_name = "Spouse Nama is required";
			} else if (wnaSpouseNat === "WNA") {
				if (!wnaSpName) e.wna_spouse_name = "Spouse Name is required";
				if (!wnaSpId) e.wna_spouse_idcard = "Spouse ID Card No. is required";
			}
		}

		setErrors(e);
		if (Object.keys(e).length) return;

		setLoading(true);
		try {
			const payload = {
				prechecking_id: precheckingId, apless, cust_type: "PR", lessee_type: "PR",
				check_for: "G", cust_new_ro: "New", guarantor_nationality_type: nationality,
				marital_status: marital, wna_marital_status: wnaMarital,
				is_carro_type: isCarro ? 1 : 0, note_prechecking_pr: notes,

				guarantor_id_card_no: guarantor.idCardNo, guarantor_name: guarantor.name,
				guarantor_pob: guarantor.placeOfBirth, guarantor_dob: guarantor.dateOfBirth,
				guarantor_gender: guarantor.gender, guarantor_blood_type: guarantor.bloodType,
				guarantor_address: guarantor.address, guarantor_rt: guarantor.rt, guarantor_rw: guarantor.rw,
				guarantor_subdistrict: guarantor.subdistrict, guarantor_district: guarantor.district,
				guarantor_city: guarantor.city, guarantor_province: guarantor.province,
				guarantor_religion: guarantor.religion, guarantor_job: guarantor.job,
				guarantor_citizen: guarantor.citizen, guarantor_photo_hidden: guarantor.photo,
				guarantor_signature_hidden: guarantor.signature,

				val_guarantor_id_card_no: guarantorConf.idCardNo ?? "", val_guarantor_name: guarantorConf.name ?? "",
				val_guarantor_pob: guarantorConf.placeOfBirth ?? "", val_guarantor_dob: guarantorConf.dateOfBirth ?? "",
				val_guarantor_gender: guarantorConf.gender ?? "", val_guarantor_blood_type: guarantorConf.bloodType ?? "",
				val_guarantor_address: guarantorConf.address ?? "", val_guarantor_rt: guarantorConf.rt ?? "",
				val_guarantor_subdistrict: guarantorConf.subdistrict ?? "", val_guarantor_district: guarantorConf.district ?? "",
				val_guarantor_city: guarantorConf.city ?? "", val_guarantor_province: guarantorConf.province ?? "",
				val_guarantor_religion: guarantorConf.religion ?? "", val_guarantor_job: guarantorConf.job ?? "",

				guarantor_spouse_id_card_no: spouse.idCardNo, guarantor_spouse_name: spouse.name,
				guarantor_spouse_pob: spouse.placeOfBirth, guarantor_spouse_dob: spouse.dateOfBirth,
				guarantor_spouse_gender: spouse.gender, guarantor_spouse_blood_type: spouse.bloodType,
				guarantor_spouse_address: spouse.address, guarantor_spouse_rt: spouse.rt,
				guarantor_spouse_rw: spouse.rw, guarantor_spouse_subdistrict: spouse.subdistrict,
				guarantor_spouse_district: spouse.district, guarantor_spouse_city: spouse.city,
				guarantor_spouse_province: spouse.province, guarantor_spouse_religion: spouse.religion,
				guarantor_spouse_job: spouse.job, guarantor_spouse_citizen: spouse.citizen,
				guarantor_spouse_photo_hidden: spouse.photo, guarantor_spouse_signature_hidden: spouse.signature,

				val_guarantor_spouse_id_card_no: spouseConf.idCardNo ?? "", val_guarantor_spouse_name: spouseConf.name ?? "",
				val_guarantor_spouse_pob: spouseConf.placeOfBirth ?? "", val_guarantor_spouse_dob: spouseConf.dateOfBirth ?? "",
				val_guarantor_spouse_gender: spouseConf.gender ?? "", val_guarantor_spouse_address: spouseConf.address ?? "",
				val_guarantor_spouse_rt: spouseConf.rt ?? "", val_guarantor_spouse_subdistrict: spouseConf.subdistrict ?? "",
				val_guarantor_spouse_district: spouseConf.district ?? "", val_guarantor_spouse_city: spouseConf.city ?? "",
				val_guarantor_spouse_province: spouseConf.province ?? "", val_guarantor_spouse_job: spouseConf.job ?? "",

				guarantor_wna_name: wnaName, guarantor_wna_idcard_no: wnaIdCard,
				guarantor_spouse_wna_name: wnaSpName, guarantor_spouse_wna_id_card_no: wnaSpId,

				guarantor_wna_spouse_id_card_no: wnaSpouse.idCardNo, guarantor_wna_spouse_name: wnaSpouse.name,
				guarantor_wna_spouse_pob: wnaSpouse.placeOfBirth, guarantor_wna_spouse_dob: wnaSpouse.dateOfBirth,
				guarantor_wna_spouse_gender: wnaSpouse.gender, guarantor_wna_spouse_blood_type: wnaSpouse.bloodType,
				guarantor_wna_spouse_address: wnaSpouse.address, guarantor_wna_spouse_rt: wnaSpouse.rt,
				guarantor_wna_spouse_rw: wnaSpouse.rw, guarantor_wna_spouse_subdistrict: wnaSpouse.subdistrict,
				guarantor_wna_spouse_district: wnaSpouse.district, guarantor_wna_spouse_city: wnaSpouse.city,
				guarantor_wna_spouse_province: wnaSpouse.province, guarantor_wna_spouse_religion: wnaSpouse.religion,
				guarantor_wna_spouse_job: wnaSpouse.job, guarantor_wna_spouse_citizen: wnaSpouse.citizen,
				guarantor_wna_spouse_photo_hidden: wnaSpouse.photo, guarantor_wna_spouse_signature_hidden: wnaSpouse.signature,

				val_guarantor_wna_spouse_id_card_no: wnaSpConf.idCardNo ?? "", val_guarantor_wna_spouse_name: wnaSpConf.name ?? "",
				val_guarantor_wna_spouse_pob: wnaSpConf.placeOfBirth ?? "", val_guarantor_wna_spouse_dob: wnaSpConf.dateOfBirth ?? "",
				val_guarantor_wna_spouse_gender: wnaSpConf.gender ?? "", val_guarantor_wna_spouse_address: wnaSpConf.address ?? "",
				val_guarantor_wna_spouse_rt: wnaSpConf.rt ?? "", val_guarantor_wna_spouse_subdistrict: wnaSpConf.subdistrict ?? "",
				val_guarantor_wna_spouse_district: wnaSpConf.district ?? "", val_guarantor_wna_spouse_city: wnaSpConf.city ?? "",
				val_guarantor_wna_spouse_province: wnaSpConf.province ?? "", val_guarantor_wna_spouse_job: wnaSpConf.job ?? "",
			};
			const res = await api.post('/CAM/Prechecking/submit-guarantor', payload);
			if (res.data?.success) { alert("Guarantor prechecking submitted successfully!"); window.history.back(); }
			else alert(res.data?.message ?? "Submission failed");
		} catch (err: any) { alert(err.response?.data?.message ?? "Submission failed"); }
		finally { setLoading(false); }
	};

	const docsOf = (type: string) => docs.filter((d) => d.type === type);

	if (loading && !precheckingId) {
		return (
			<div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "var(--bg)" }}>
				<Spinner dark size={40} />
			</div>
		);
	}

	return (
		<div style={{ minHeight: "100vh", background: "var(--bg)", fontFamily: "var(--font)" }}>

			<DocPreviewModal state={preview} onClose={() => setPreview(PREVIEW_CLOSED)} />

			{modal.open && <HistoryModal modal={modal} setModal={setModal} />}

			<div className="page-wrap">
				<div className="hdr">
					<div>
						<div className="hdr-title">Add Guarantor Data</div>
						<div className="hdr-sub">Individual Guarantor · KYC Verification</div>
					</div>
					<div className="hdr-badge">
						<span className="hdr-badge-label">Prechecking ID</span>
						<span className="hdr-badge-value">{precheckingId || "—"}</span>
					</div>
				</div>

				<div className="card">

					<div className="section-label"><span className="dot" />General Information<hr /></div>
					<div style={{ marginBottom: 24 }}>
						<div className="form-grid" style={{ marginBottom: 14 }}>
							<div className="form-field">
								<label className="form-label">Checking For <span className="req">*</span></label>
								<div className="select-wrap"><select disabled value="G" className="form-select is-disabled"><option value="G">Guarantor</option></select></div>
							</div>
							<div className="form-field">
								<label className="form-label">Type <span className="req">*</span></label>
								<div className="select-wrap"><select disabled value="G" className="form-select is-disabled"><option value="G">Individu</option></select></div>
							</div>
						</div>
						<div className="form-grid" style={{ marginBottom: 14 }}>
							<div className="form-field">
								<label className="form-label">New / Repeat Order</label>
								<div className="select-wrap"><select disabled value="New" className="form-select is-disabled"><option value="New">New</option></select></div>
							</div>
							<div className="form-field">
								<label className="form-label">Temp. Customer No.</label>
								<input readOnly value={apless} className="form-input is-readonly" />
							</div>
						</div>
						<div style={{ maxWidth: 460 }}>
							<div className="form-field">
								<label className="form-label">Nationality <span className="req">*</span></label>
								<div className="select-wrap">
									<select value={nationality} onChange={(e) => setNationality(e.target.value as "WNI" | "WNA")} className={`form-select${nationality ? " nat-active" : ""}`}>
										<option value="WNI">🇮🇩 WNI</option>
										<option value="WNA">🌐 WNA</option>
									</select>
								</div>
							</div>
						</div>
					</div>

					{nationality === "WNI" && (
						<>
							<div className="section-label"><span className="dot" />Guarantor KTP (OCR)<hr /></div>
							<OCRUploadSection
								apless={apless}
								precheckingId={precheckingId}
								ocrFor="guarantor"
								docType="guarantor-ktp"
								title="Guarantor · WNI"
								nationality="WNI"
								onDataChange={(data, conf) => { setGuarantor(data); setGuarantorConf(conf); }}
								onHistoryModal={(msg, al, type, pid) =>
									setModal({ open: true, type: type as any, message: msg, apless: al, precheckingId: pid })
								}
							/>
						</>
					)}

					{showWnaSection && (
						<>
							<div className="section-label"><span className="dot" />Guarantor WNA Information<hr /></div>
							<div className="sub-section blue" style={{ marginBottom: 20 }}>
								<div className="sub-section-title">🌐 Guarantor WNA</div>
								<div className="form-grid">
									<div className="form-field">
										<label className="form-label">Nama <span className="req">*</span></label>
										<input value={wnaName} onChange={(e) => setWnaName(e.target.value.toUpperCase())} className={`form-input${errors.wna_name ? " err" : ""}`} style={{ textTransform: "uppercase" }} />
										{errors.wna_name && <p className="field-err">{errors.wna_name}</p>}
									</div>
									<div className="form-field">
										<label className="form-label">ID Card No. <span className="req">*</span></label>
										<input value={wnaIdCard} onChange={(e) => setWnaIdCard(e.target.value)} onBlur={handleWnaIdBlur} className={`form-input${errors.wna_idcard ? " err" : ""}`} />
										{errors.wna_idcard && <p className="field-err">{errors.wna_idcard}</p>}
									</div>
									<div className="form-field full">
										<label className="form-label">ID Card (KITAS/Passport)</label>
										<FileInput label="Upload KITAS / Passport" onFileChange={(f) => _uploadDoc(f, "guarantor-kitas")} uploading={uploadingDocs.has("guarantor-kitas")} />
										<DocList docs={docsOf("guarantor-kitas")} onDelete={handleDeleteDoc} deletingDocs={deletingDocs} onPreview={handlePreview} previewLoadingId={previewLoadingId} />
									</div>
								</div>
							</div>
						</>
					)}

					{nationality === "WNI" && (
						<>
							<div className="section-label"><span className="dot" />Marital Status<hr /></div>
							<div className="form-grid" style={{ marginBottom: 20 }}>
								<div className="form-field">
									<label className="form-label">Marital Status <span className="req">*</span></label>
									<div className="select-wrap">
										<select value={marital} onChange={(e) => setMarital(e.target.value)} className={`form-select${errors.marital ? " err" : ""}`}>
											<option value="">— Select —</option>
											{maritalOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
										</select>
									</div>
									{errors.marital && <p className="field-err">{errors.marital}</p>}
								</div>
								{showSpouseNat && (
									<div className="form-field">
										<label className="form-label">Spouse Nationality <span className="req">*</span></label>
										<div className="select-wrap">
											<select value={spouseNat} onChange={(e) => setSpouseNat(e.target.value as any)} className={`form-select${errors.spouse_nat ? " err" : ""}`}>
												<option value="">— Select —</option>
												<option value="WNI">WNI</option>
												<option value="WNA">WNA</option>
											</select>
										</div>
										{errors.spouse_nat && <p className="field-err">{errors.spouse_nat}</p>}
									</div>
								)}
							</div>
						</>
					)}

					{showWnaSection && (
						<>
							<div className="section-label"><span className="dot" />Marital Status (WNA)<hr /></div>
							<div className="form-grid" style={{ marginBottom: 20 }}>
								<div className="form-field">
									<label className="form-label">Marital Status <span className="req">*</span></label>
									<div className="select-wrap">
										<select value={wnaMarital} onChange={(e) => setWnaMarital(e.target.value)} className={`form-select${errors.wna_marital ? " err" : ""}`}>
											<option value="">— Select —</option>
											{maritalOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
										</select>
									</div>
									{errors.wna_marital && <p className="field-err">{errors.wna_marital}</p>}
								</div>
								{showWnaSpNat && (
									<div className="form-field">
										<label className="form-label">Spouse Nationality <span className="req">*</span></label>
										<div className="select-wrap">
											<select value={wnaSpouseNat} onChange={(e) => setWnaSpouseNat(e.target.value as any)} className={`form-select${errors.wna_spouse_nat ? " err" : ""}`}>
												<option value="">— Select —</option>
												<option value="WNI">WNI</option>
												<option value="WNA">WNA</option>
											</select>
										</div>
										{errors.wna_spouse_nat && <p className="field-err">{errors.wna_spouse_nat}</p>}
									</div>
								)}
							</div>
						</>
					)}

					{showSpouseOCR && (
						<>
							<div className="section-label"><span className="dot" />Spouse KTP (OCR)<hr /></div>
							<OCRUploadSection
								apless={apless}
								precheckingId={precheckingId}
								ocrFor="guarantor_spouse"
								docType="guarantor-spouse-ktp"
								title="Spouse · WNI"
								onDataChange={(data, conf) => { setSpouse(data); setSpouseConf(conf); }}
							/>
						</>
					)}

					{showWnaSpInfo && (
						<>
							<div className="section-label"><span className="dot" />Spouse (WNA)<hr /></div>
							<div className="sub-section orange" style={{ marginBottom: 20 }}>
								<div className="sub-section-title">Spouse — Foreign National</div>
								<div className="form-grid">
									<div className="form-field">
										<label className="form-label">Spouse Name <span className="req">*</span></label>
										<input value={wnaSpName} onChange={(e) => setWnaSpName(e.target.value.toUpperCase())} className={`form-input${errors.wna_spouse_name ? " err" : ""}`} style={{ textTransform: "uppercase" }} />
										{errors.wna_spouse_name && <p className="field-err">{errors.wna_spouse_name}</p>}
									</div>
									<div className="form-field">
										<label className="form-label">Spouse ID Card No. <span className="req">*</span></label>
										<input value={wnaSpId} onChange={(e) => setWnaSpId(e.target.value)} className={`form-input${errors.wna_spouse_idcard ? " err" : ""}`} />
										{errors.wna_spouse_idcard && <p className="field-err">{errors.wna_spouse_idcard}</p>}
									</div>
									<div className="form-field full">
										<label className="form-label">Spouse ID Card (KITAS)</label>
										<FileInput label="Upload Spouse KITAS" onFileChange={(f) => _uploadDoc(f, "guarantor-spouse-kitas")} uploading={uploadingDocs.has("guarantor-spouse-kitas")} />
										<DocList docs={docsOf("guarantor-spouse-kitas")} onDelete={handleDeleteDoc} deletingDocs={deletingDocs} onPreview={handlePreview} previewLoadingId={previewLoadingId} />
									</div>
								</div>
							</div>
						</>
					)}

					{showWnaSpOCR && (
						<>
							<div className="section-label"><span className="dot" />Spouse of WNA Guarantor (WNI KTP)<hr /></div>
							<OCRUploadSection
								apless={apless}
								precheckingId={precheckingId}
								ocrFor="guarantor_wna_spouse"
								docType="guarantor-wna-spouse-ktp"
								title="Spouse of WNA · WNI KTP"
								onDataChange={(data, conf) => { setWnaSpouse(data); setWnaSpConf(conf); }}
							/>
						</>
					)}

					{showWnaSpWna && (
						<>
							<div className="section-label"><span className="dot" />Spouse of WNA (Foreign ID)<hr /></div>
							<div className="sub-section purple" style={{ marginBottom: 20 }}>
								<div className="sub-section-title">Spouse — Foreign National (KITAS)</div>
								<div className="form-grid">
									<div className="form-field">
										<label className="form-label">Spouse Name <span className="req">*</span></label>
										<input value={wnaSpName} onChange={(e) => setWnaSpName(e.target.value.toUpperCase())} className={`form-input${errors.wna_spouse_name ? " err" : ""}`} style={{ textTransform: "uppercase" }} />
										{errors.wna_spouse_name && <p className="field-err">{errors.wna_spouse_name}</p>}
									</div>
									<div className="form-field">
										<label className="form-label">Spouse ID Card No. <span className="req">*</span></label>
										<input value={wnaSpId} onChange={(e) => setWnaSpId(e.target.value)} className={`form-input${errors.wna_spouse_idcard ? " err" : ""}`} />
										{errors.wna_spouse_idcard && <p className="field-err">{errors.wna_spouse_idcard}</p>}
									</div>
									<div className="form-field full">
										<label className="form-label">Spouse KITAS</label>
										<FileInput label="Upload Spouse KITAS" onFileChange={(f) => _uploadDoc(f, "guarantor-spouse-kitas")} uploading={uploadingDocs.has("guarantor-spouse-kitas")} />
										<DocList docs={docsOf("guarantor-spouse-kitas")} onDelete={handleDeleteDoc} deletingDocs={deletingDocs} onPreview={handlePreview} previewLoadingId={previewLoadingId} />
									</div>
								</div>
							</div>
						</>
					)}

					<div className="section-label"><span className="dot" />Supporting Documents<hr /></div>
					<div className="form-grid" style={{ marginBottom: 24 }}>
						{[
							{ label: "KK (Kartu Keluarga)", type: "guarantor-kk" },
							{ label: "NPWP", type: "guarantor-npwp" },
							{ label: "Akta Cerai / Akta Kematian", type: "guarantor-marriage-or-death-statement" },
						].map((doc) => (
							<div className="form-field" key={doc.type}>
								<label className="form-label">{doc.label}</label>
								<FileInput multiple label={`Upload ${doc.label}`} onFileChange={(f) => _uploadDoc(f, doc.type)} uploading={uploadingDocs.has(doc.type)} />
								<DocList docs={docsOf(doc.type)} onDelete={handleDeleteDoc} deletingDocs={deletingDocs} onPreview={handlePreview} previewLoadingId={previewLoadingId} />
							</div>
						))}
					</div>

					<div className="section-label"><span className="dot" />Reference &amp; Notes<hr /></div>
					<div style={{ display: "flex", flexDirection: "column", gap: 14, maxWidth: 460, marginBottom: 8 }}>
						<div className="form-field">
							<label className="form-label">Reference</label>
							<div className="select-wrap">
								<select value={isCarro ? "1" : "0"} onChange={(e) => setIsCarro(e.target.value === "1")} className="form-select">
									<option value="1">Carro</option>
									<option value="0">Non Carro</option>
								</select>
							</div>
						</div>
						<div className="form-field">
							<label className="form-label">Note for Prechecking</label>
							<textarea rows={4} value={notes} onChange={(e) => setNotes(e.target.value.toUpperCase())} className="form-textarea" placeholder="Optional notes…" style={{ textTransform: "uppercase" }} />
						</div>
					</div>

				</div>

				<div style={{ display: "flex", justifyContent: "flex-end", gap: 12, marginTop: 4 }}>
					<button className="btn-ghost" onClick={handleCancel} disabled={loading}>Cancel</button>
					<button className="btn-primary" onClick={handleSubmit} disabled={loading}>
						{loading && <Spinner />}
						Submit Guarantor Prechecking
					</button>
				</div>

			</div>
		</div>
	);
};

export default PrecheckingGuarantorIndividuPage;