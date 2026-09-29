import React, { useState, useEffect } from "react";
import api from "../../../../api/axiosInstance";
import OCRUploadSection from "../../../../contexts/OCRUploadSection";
import { MAX_FILE_LIMIT } from "../../../../constants/DefaultValue";

const fontLink = document.createElement("link");
fontLink.rel = "stylesheet";
fontLink.href =
	"https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap";
document.head.appendChild(fontLink);

interface DirectorData {
	idCardNo: string; name: string; placeOfBirth: string; dateOfBirth: string;
	gender: string; bloodType: string; address: string; rt: string; rw: string;
	subdistrict: string; district: string; city: string; province: string;
	religion: string; job: string; maritalStatus: string; citizen: string;
	photo: string; signature: string;
}
type ConfidenceMap = Partial<Record<keyof DirectorData, string>>;

interface DirectorEntry {
	uid: string;
	data: DirectorData;
	conf: ConfidenceMap;
}

interface WnaBoardMember { uid: string; name: string; idCardNo: string; }

interface LesseeTypeOption { value: string; label: string; }
interface ModalState {
	open: boolean; type: "reject" | "inprogress" | "valid" | "expired" | "";
	message: string; apless: string; precheckingId: string;
}
interface UploadedDoc { id: number; name: string; type: string; key: string; previewUrl?: string; view_url?: string | null; }

const EMPTY_DIRECTOR = (): DirectorData => ({
	idCardNo: "", name: "", placeOfBirth: "", dateOfBirth: "",
	gender: "", bloodType: "", address: "", rt: "", rw: "",
	subdistrict: "", district: "", city: "", province: "",
	religion: "", job: "", maritalStatus: "", citizen: "",
	photo: "", signature: "",
});

const REQUIRED_DIRECTOR_FIELDS: [keyof DirectorData, string][] = [
	["idCardNo", "NIK"], ["name", "Nama"], ["placeOfBirth", "Tempat Lahir"],
	["dateOfBirth", "Tanggal Lahir"], ["gender", "Jenis Kelamin"],
	["address", "Alamat"], ["rt", "RT"], ["rw", "RW"],
	["subdistrict", "Kelurahan/Desa"], ["district", "Kecamatan"],
	["city", "Kota/Kabupaten"], ["province", "Provinsi"],
	["job", "Pekerjaan"], ["maritalStatus", "Status Perkawinan"],
];

const directorLabel = (entry: DirectorEntry, all: DirectorEntry[]) =>
	`#${all.findIndex((d) => d.uid === entry.uid) + 1}`;

const directorIsComplete = (entry: DirectorEntry) =>
	REQUIRED_DIRECTOR_FIELDS.every(([key]) => !!entry.data[key]);

const directorHasError = (entry: DirectorEntry, errors: Record<string, string>) =>
	Object.keys(errors).some((k) => k.startsWith(`director_${entry.uid}_`));


const IMAGE_EXTS = new Set(["png", "jpg", "jpeg", "gif", "bmp", "heic", "heif", "tiff", "tif", "webp"]);

const uid = () => Math.random().toString(36).slice(2, 10);

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
  .doc-chip-del {
    background: none; border: none; cursor: pointer;
    color: var(--muted); font-size: .9rem; line-height: 1; padding: 0 1px; transition: color .15s;
  }
  .doc-chip-del:hover { color: var(--rose); }

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

  .btn-soft {
    background: var(--sky); color: var(--navy); border: 1.5px dashed #C7D7F8;
    border-radius: 12px; padding: 10px 18px; font-size: .82rem; font-weight: 700;
    font-family: var(--font); cursor: pointer; transition: background .2s, border-color .2s;
    display: inline-flex; align-items: center; gap: 8px;
  }
  .btn-soft:hover { background: #DCEAFF; border-color: var(--blue); }
  .btn-remove {
    background: none; border: 1.5px solid var(--border); color: var(--rose);
    border-radius: 10px; padding: 7px 14px; font-size: .78rem; font-weight: 700;
    font-family: var(--font); cursor: pointer; transition: background .2s, border-color .2s;
  }
  .btn-remove:hover { background: #FEF2F2; border-color: var(--rose); }

  .select-wrap { position: relative; }
  .select-wrap select { appearance: none; padding-right: 36px; }
  .select-wrap::after {
    content: ''; position: absolute; right: 12px; top: 50%; transform: translateY(-50%);
    width: 0; height: 0;
    border-left: 5px solid transparent; border-right: 5px solid transparent;
    border-top: 6px solid var(--muted); pointer-events: none;
  }
  .select-wrap:focus-within::after { border-top-color: var(--blue); }

  .form-input.is-readonly {
    background: #F4F7FF; color: var(--muted); cursor: default; border-color: #E8EEF8;
  }
  .form-select.is-disabled {
    background: #F4F7FF; color: var(--muted); cursor: default; border-color: #E8EEF8;
  }

  .director-tabs-wrap {
    border: 1.5px solid var(--border); border-radius: 14px;
    background: #FAFCFF; overflow: hidden; margin-bottom: 18px;
  }
  .director-tabbar {
    display: flex; align-items: stretch; gap: 0; overflow-x: auto;
    background: #F4F7FF; border-bottom: 1.5px solid var(--border);
    scrollbar-width: thin;
  }
  .director-tab {
    display: flex; align-items: center; gap: 8px;
    padding: 12px 18px; border: none; background: none; cursor: pointer;
    font-family: var(--font); font-size: .8rem; font-weight: 700; color: var(--muted);
    white-space: nowrap; position: relative; transition: color .15s, background .15s;
    border-right: 1px solid var(--border);
  }
  .director-tab:hover { background: #EAF0FF; color: var(--navy); }
  .director-tab.active {
    color: var(--navy); background: #fff;
  }
  .director-tab.active::after {
    content: ''; position: absolute; left: 0; right: 0; bottom: -1.5px;
    height: 2.5px; background: var(--blue);
  }
  .director-tab-dot {
    width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
    background: var(--border);
  }
  .director-tab-dot.complete { background: var(--mint); }
  .director-tab-dot.error { background: var(--rose); }
  .director-tab-close {
    border: none; background: none; cursor: pointer; color: var(--muted);
    font-size: .95rem; line-height: 1; padding: 0 0 0 2px; transition: color .15s;
  }
  .director-tab-close:hover { color: var(--rose); }
  .director-tab-add {
    display: flex; align-items: center; gap: 6px;
    padding: 12px 16px; border: none; background: none; cursor: pointer;
    font-family: var(--font); font-size: .8rem; font-weight: 700; color: var(--blue);
    white-space: nowrap; transition: background .15s;
  }
  .director-tab-add:hover { background: #EAF0FF; }
  .director-tabpanel { padding: 22px; }

  .wna-board-table { width: 100%; border-collapse: separate; border-spacing: 0 10px; }
  .wna-board-table th {
    text-align: left; font-size: .72rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: .06em; color: var(--muted); padding: 0 10px 4px;
  }
  .wna-board-table td { padding: 0 10px; vertical-align: top; }
  .wna-board-row-actions { display: flex; align-items: flex-start; padding-top: 9px; }
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
							<button className="btn-modal-ghost" onClick={() => window.location.href = `/repeat-order-guarantor-pt?apless=${modal.apless}&prechecking_id=${modal.precheckingId}&types=G`}>Prechecking</button>
							<button className="btn-modal-primary" onClick={() => window.location.href = `/create-cam?apless=${modal.apless}&prechecking_id=${modal.precheckingId}&lessee_tp=PT`}>Create New CAM</button>
						</>
					)}
					{(modal.type === "inprogress" || modal.type === "expired") && (
						<button className="btn-modal-primary" onClick={() => {
							close();
							if (modal.type === "expired") window.location.href = `/repeat-order-guarantor-pt?apless=${modal.apless}&prechecking_id=${modal.precheckingId}&types=G`;
						}}>Close</button>
					)}
				</div>
			</div>
		</div>
	);
};

const PrecheckingGuarantorCorporatePage: React.FC = () => {
	const [precheckingId, setPrecheckingId] = useState("");
	const [apless, setApless] = useState("");
	const [lesseeType, setLesseeType] = useState("");
	const [lesseeTypeOptions, setLesseeTypeOptions] = useState<LesseeTypeOption[]>([]);

	const [corpName, setCorpName] = useState("");
	const [corpAddress, setCorpAddress] = useState("");
	const [corpNpwpNo, setCorpNpwpNo] = useState("");

	const [isCarro, setIsCarro] = useState(true);
	const [notes, setNotes] = useState("");

	const [directors, setDirectors] = useState<DirectorEntry[]>(() => [
		{ uid: uid(), data: EMPTY_DIRECTOR(), conf: {} },
	]);
	const [activeDirectorTab, setActiveDirectorTab] = useState<string>(() => directors[0].uid);
	const [wnaBoard, setWnaBoard] = useState<WnaBoardMember[]>([]);

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
				const [aplessR, pidR, lesseeR] = await Promise.all([
					api.post('/CAM/Prechecking/generate-apless', { customer_type: "G" }),
					api.post('/CAM/Prechecking/generate-prechecking-id', {}),
					api.get('/CAM/Prechecking/lessee-types'),
				]);
				setApless(aplessR.data);
				setPrecheckingId(pidR.data);
				setLesseeTypeOptions(lesseeR.data);
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
			fd.append("cust_type", "PT");
			fd.append("lessee_type", lesseeType);

			const res = await api.post(
				'/CAM/Prechecking/upload-document-guarantor-corporate',
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
			const res = await api.get('/CAM/Prechecking/documents-guarantor-corporate', {
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
		const dirMatch = /^corp-guarantor-ocr-ktp_(.+)$/.exec(docType);
		if (dirMatch) {
			const d = directors.find((x) => x.uid === dirMatch[1]);
			return d?.data.idCardNo ?? "";
		}
		const wnaMatch = /^wna-corp-guarantor-board_(.+)$/.exec(docType);
		if (wnaMatch) {
			const w = wnaBoard.find((x) => x.uid === wnaMatch[1]);
			return w?.idCardNo ?? "";
		}
		return "";
	};

	const handleDeleteDoc = async (docId: number) => {
		if (!window.confirm("Apakah Anda yakin ingin menghapus dokumen ini?")) return;
		setDeletingDocs((prev) => new Set(prev).add(docId));
		try {
			const doc = docs.find((d) => d.id === docId);
			if (doc?.previewUrl?.startsWith("blob:")) URL.revokeObjectURL(doc.previewUrl);
			const nik = doc ? _nikForDocType(doc.type) : "";

			const res = await api.post('/CAM/Prechecking/delete-document-guarantor-corporate', {
				customer_document_id: docId,
				prechecking_id: precheckingId,
				nik,
			});
			if (!res.data?.success) {
				alert(res.data?.message ?? "Hapus dokumen gagal. Silakan coba lagi.");
				return;
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

	const _deleteDocsByType = async (docType: string, nik?: string) => {
		try {
			await api.post('/CAM/Prechecking/delete-documents-by-type-guarantor-corporate', {
				prechecking_id: precheckingId, document_type: docType, nik: nik ?? "",
			});
			setDocs((prev) => prev.filter((d) => d.type !== docType));
		} catch (e) {
			console.error("Failed to cascade-delete documents for", docType, e);
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
			const res = await api.get('/CAM/Prechecking/view-document-guarantor-corporate', {
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

	const handleNpwpBlur = async () => {
		if (corpNpwpNo.length < 15) {
			alert("No NPWP kurang panjang, minimal 15 karakter!");
			return;
		}
		
		try {
			const res = await api.post('/CAM/Prechecking/check-customer-history', {
				idNo: corpNpwpNo, prechecking_id: precheckingId, lesseeType: "PT", checking_for: "G",
			});
			const [msg, al, type, pid] = res.data;
			if (msg) setModal({ open: true, type, message: msg, apless: al, precheckingId: pid });
		} catch (e) { console.error(e); }
	};

	const handleCancel = async () => {
		try { await api.post('/CAM/Prechecking/cancel-guarantor', { prechecking_id: precheckingId }); }
		finally { window.history.back(); }
	};

	const docTypeForDirector = (entryUid: string) => `corp-guarantor-ocr-ktp_${entryUid}`;
	const docTypeForWnaBoard = (entryUid: string) => `wna-corp-guarantor-board_${entryUid}`;

	const addDirector = () => {
		const entry = { uid: uid(), data: EMPTY_DIRECTOR(), conf: {} };
		setDirectors((prev) => [...prev, entry]);
		setActiveDirectorTab(entry.uid);
	};

	const removeDirector = (entryUid: string) => {
		const removedNik = directors.find((d) => d.uid === entryUid)?.data.idCardNo ?? "";
		setDirectors((prev) => {
			if (prev.length <= 1) return prev;
			const next = prev.filter((d) => d.uid !== entryUid);
			setActiveDirectorTab((cur) => (cur === entryUid ? next[0].uid : cur));
			return next;
		});
		_deleteDocsByType(docTypeForDirector(entryUid), removedNik);
	};

	const updateDirector = (entryUid: string, data: DirectorData, conf: ConfidenceMap) => {
		setDirectors((prev) => prev.map((d) => (d.uid === entryUid ? { ...d, data, conf } : d)));
	};

	const addWnaBoard = () => {
		setWnaBoard((prev) => [...prev, { uid: uid(), name: "", idCardNo: "" }]);
	};

	const removeWnaBoard = (entryUid: string) => {
		const removedNik = wnaBoard.find((w) => w.uid === entryUid)?.idCardNo ?? "";
		setWnaBoard((prev) => prev.filter((w) => w.uid !== entryUid));
		_deleteDocsByType(docTypeForWnaBoard(entryUid), removedNik);
	};

	const updateWnaBoard = (entryUid: string, field: "name" | "idCardNo", value: string) => {
		setWnaBoard((prev) => prev.map((w) => (w.uid === entryUid ? { ...w, [field]: value } : w)));
	};

	const handleSubmit = async () => {
		const e: Record<string, string> = {};
		if (!lesseeType) e.lessee_type = "Company Type is required";
		if (!corpName) e.corp_name = "Nama is required";
		if (!corpAddress) e.corp_address = "Alamat is required";
		if (!corpNpwpNo) e.corp_npwp_no = "NPWP No is required";

		let firstInvalidTab: string | null = null;
		directors.forEach((d) => {
			let directorHasError = false;
			REQUIRED_DIRECTOR_FIELDS.forEach(([key, label]) => {
				if (!d.data[key]) {
					e[`director_${d.uid}_${key}`] = `${label} is required (Pengurus ${directorLabel(d, directors)})`;
					directorHasError = true;
				}
			});
			if (directorHasError && !firstInvalidTab) firstInvalidTab = d.uid;
		});

		setErrors(e);
		if (firstInvalidTab) setActiveDirectorTab(firstInvalidTab);
		if (Object.keys(e).length) return;

		setLoading(true);
		try {
			const payload = {
				prechecking_id: precheckingId, apless, cust_type: "PT", lessee_type: lesseeType,
				check_for: "G", corp_new_ro: "New",
				corp_guarantor_name: corpName, corp_guarantor_address: corpAddress, corp_guarantor_npwp_no: corpNpwpNo,
				is_carro_type: isCarro ? 1 : 0, note_prechecking_pt: notes,
				directors: directors.map((d) => ({
					id_card_no: d.data.idCardNo, name: d.data.name, pob: d.data.placeOfBirth,
					dob: d.data.dateOfBirth, gender: d.data.gender, blood_type: d.data.bloodType,
					address: d.data.address, rt: d.data.rt, rw: d.data.rw,
					subdistrict: d.data.subdistrict, district: d.data.district, city: d.data.city,
					province: d.data.province, religion: d.data.religion, job: d.data.job,
					marital_status: d.data.maritalStatus, citizen: d.data.citizen || "WNI",
					photo_hidden: d.data.photo, signature_hidden: d.data.signature,
					val_id_card_no: d.conf.idCardNo ?? "", val_name: d.conf.name ?? "",
					val_pob: d.conf.placeOfBirth ?? "", val_dob: d.conf.dateOfBirth ?? "",
					val_gender: d.conf.gender ?? "", val_blood_type: d.conf.bloodType ?? "",
					val_address: d.conf.address ?? "", val_rt: d.conf.rt ?? "", val_rw: d.conf.rw ?? "",
					val_subdistrict: d.conf.subdistrict ?? "", val_district: d.conf.district ?? "",
					val_city: d.conf.city ?? "", val_province: d.conf.province ?? "",
					val_religion: d.conf.religion ?? "", val_job: d.conf.job ?? "",
					val_marital_status: d.conf.maritalStatus ?? "", val_citizen: d.conf.citizen ?? "",
					ver_id_card_no: d.conf.idCardNo ? "True" : "", ver_name: d.conf.name ? "True" : "",
					ver_pob: d.conf.placeOfBirth ? "True" : "", ver_dob: d.conf.dateOfBirth ? "True" : "",
					ver_gender: d.conf.gender ? "True" : "", ver_address: d.conf.address ? "True" : "",
					ver_rt: d.conf.rt ? "True" : "", ver_rw: d.conf.rw ? "True" : "",
					ver_subdistrict: d.conf.subdistrict ? "True" : "", ver_district: d.conf.district ? "True" : "",
					ver_city: d.conf.city ? "True" : "", ver_province: d.conf.province ? "True" : "",
					ver_job: d.conf.job ? "True" : "", ver_marital_status: d.conf.maritalStatus ? "True" : "",
				})),
				wna_board: wnaBoard
					.filter((w) => w.idCardNo.trim())
					.map((w) => ({ name: w.name, id_card_no: w.idCardNo })),
			};

			const res = await api.post('/CAM/Prechecking/submit-guarantor-corporate', payload);
			if (res.data?.success) { alert("Corporate guarantor prechecking submitted successfully!"); window.history.back(); }
			else if (res.data?.errors) {
				setErrors(res.data.errors);
				alert("Please complete all required fields.");
			} else alert(res.data?.message ?? "Submission failed");
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
						<div className="hdr-title">Add Guarantor Prechecking Data</div>
						<div className="hdr-sub">Corporate Guarantor (PT) · KYC Verification</div>
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
								<div className="select-wrap"><select disabled value="G" className="form-select is-disabled"><option value="G">Corporate</option></select></div>
							</div>
						</div>
						<div className="form-grid" style={{ marginBottom: 14 }}>
							<div className="form-field">
								<label className="form-label">Company Type <span className="req">*</span></label>
								<div className="select-wrap">
									<select value={lesseeType} onChange={(e) => setLesseeType(e.target.value)} className={`form-select${errors.lessee_type ? " err" : ""}`}>
										<option value="">Select</option>
										{lesseeTypeOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
									</select>
								</div>
								{errors.lessee_type && <p className="field-err">{errors.lessee_type}</p>}
							</div>
							<div className="form-field">
								<label className="form-label">New / Repeat Order</label>
								<div className="select-wrap"><select disabled value="New" className="form-select is-disabled"><option value="New">New</option></select></div>
							</div>
						</div>
						<div className="form-grid">
							<div className="form-field">
								<label className="form-label">Temporary Customer No.</label>
								<input readOnly value={apless} className="form-input is-readonly" />
							</div>
						</div>
					</div>

					<div className="section-label"><span className="dot" />Company Information<hr /></div>
					<div className="form-grid" style={{ marginBottom: 24 }}>
						<div className="form-field full">
							<label className="form-label">Nama <span className="req">*</span></label>
							<input value={corpName} onChange={(e) => setCorpName(e.target.value.toUpperCase())} className={`form-input${errors.corp_name ? " err" : ""}`} style={{ textTransform: "uppercase" }} maxLength={100} />
							{errors.corp_name && <p className="field-err">{errors.corp_name}</p>}
						</div>
						<div className="form-field full">
							<label className="form-label">Alamat <span className="req">*</span></label>
							<input value={corpAddress} onChange={(e) => setCorpAddress(e.target.value.toUpperCase())} className={`form-input${errors.corp_address ? " err" : ""}`} style={{ textTransform: "uppercase" }} maxLength={100} />
							{errors.corp_address && <p className="field-err">{errors.corp_address}</p>}
						</div>
						<div className="form-field">
							<label className="form-label">NPWP No. <span className="req">*</span></label>
							<input
								value={corpNpwpNo}
								onChange={(e) => setCorpNpwpNo(e.target.value.replace(/\D/g, "").slice(0, 16))}
								onBlur={handleNpwpBlur}
								className={`form-input${errors.corp_npwp_no ? " err" : ""}`}
								maxLength={16}
							/>
							{errors.corp_npwp_no && <p className="field-err">{errors.corp_npwp_no}</p>}
						</div>
						<div className="form-field full">
							<label className="form-label">NPWP <span className="req">*</span></label>
							<FileInput multiple label="Upload NPWP" onFileChange={(f) => _uploadDoc(f, "corp-guarantor-npwp")} uploading={uploadingDocs.has("corp-guarantor-npwp")} />
							<DocList docs={docsOf("corp-guarantor-npwp")} onDelete={handleDeleteDoc} deletingDocs={deletingDocs} onPreview={handlePreview} previewLoadingId={previewLoadingId} />
						</div>
					</div>

					<div className="section-label"><span className="dot" />Data Pengurus (WNI)<hr /></div>
					<div className="director-tabs-wrap">
						<div className="director-tabbar" role="tablist">
							{directors.map((entry) => {
								const complete = directorIsComplete(entry);
								const hasErr = directorHasError(entry, errors);
								const dotClass = hasErr ? "error" : complete ? "complete" : "";
								return (
									<button
										key={entry.uid}
										type="button"
										role="tab"
										aria-selected={activeDirectorTab === entry.uid}
										className={`director-tab${activeDirectorTab === entry.uid ? " active" : ""}`}
										onClick={() => setActiveDirectorTab(entry.uid)}
									>
										<span className={`director-tab-dot${dotClass ? ` ${dotClass}` : ""}`} />
										Pengurus {directorLabel(entry, directors)}
										{entry.data.name && (
											<span style={{ color: "var(--muted)", fontWeight: 500 }}>
												· {entry.data.name.length > 16 ? entry.data.name.slice(0, 16) + "…" : entry.data.name}
											</span>
										)}
										{directors.length > 1 && (
											<span
												className="director-tab-close"
												role="button"
												aria-label={`Remove Pengurus ${directorLabel(entry, directors)}`}
												onClick={(ev) => {
													ev.stopPropagation();
													if (window.confirm(`Hapus Pengurus ${directorLabel(entry, directors)}? Dokumen yang sudah diupload untuk pengurus ini juga akan dihapus.`)) {
														removeDirector(entry.uid);
													}
												}}
											>×</span>
										)}
									</button>
								);
							})}
							<button type="button" className="director-tab-add" onClick={addDirector}>
								<svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 4v16m8-8H4" /></svg>
								Add Pengurus
							</button>
						</div>
						<div className="director-tabpanel">
							{directors.map((entry) => (
								<div key={entry.uid} style={{ display: activeDirectorTab === entry.uid ? "block" : "none" }}>
									<DirectorCard
										entry={entry}
										label={directorLabel(entry, directors)}
										apless={apless}
										precheckingId={precheckingId}
										lesseeType={lesseeType}
										docsOf={docsOf}
										uploadingDocs={uploadingDocs}
										deletingDocs={deletingDocs}
										onUploadDoc={_uploadDoc}
										onDeleteDoc={handleDeleteDoc}
										onPreview={handlePreview}
										onChange={(data, conf) => updateDirector(entry.uid, data, conf)}
										errors={errors}
										onHistoryModal={(msg, al, type, pid) =>
											setModal({ open: true, type: type as any, message: msg, apless: al, precheckingId: pid })
										}
									/>
								</div>
							))}
						</div>
					</div>

					<div className="section-label"><span className="dot" />Data Pengurus (WNA)<hr /></div>
					<div style={{ marginBottom: 12, overflowX: "auto" }}>
						{wnaBoard.length > 0 && (
							<table className="wna-board-table">
								<thead>
									<tr>
										<th style={{ width: "25%" }}>Name</th>
										<th style={{ width: "25%" }}>ID Card No.</th>
										<th style={{ width: "40%" }}>Upload ID Card File</th>
										<th style={{ width: "10%" }}></th>
									</tr>
								</thead>
								<tbody>
									{wnaBoard.map((w, idx) => {
										const boardDocType = docTypeForWnaBoard(w.uid);
										return (
											<tr key={w.uid}>
												<td>
													<input
														className="form-input"
														style={{ textTransform: "uppercase" }}
														value={w.name}
														onChange={(e) => updateWnaBoard(w.uid, "name", e.target.value.toUpperCase())}
													/>
												</td>
												<td>
													<input
														className="form-input"
														value={w.idCardNo}
														onChange={(e) => updateWnaBoard(w.uid, "idCardNo", e.target.value)}
													/>
												</td>
												<td>
													<FileInput
														label="Upload ID Card"
														onFileChange={(f) => _uploadDoc(f, boardDocType)}
														uploading={uploadingDocs.has(boardDocType)}
													/>
													<DocList docs={docsOf(boardDocType)} onDelete={handleDeleteDoc} deletingDocs={deletingDocs} onPreview={handlePreview} previewLoadingId={previewLoadingId} />
												</td>
												<td className="wna-board-row-actions">
													<button
														type="button"
														className="btn-remove"
														onClick={() => {
															if (window.confirm(`Hapus Pengurus WNA #${idx + 1}? Dokumen yang sudah diupload untuk pengurus ini juga akan dihapus.`)) {
																removeWnaBoard(w.uid);
															}
														}}
													>Remove</button>
												</td>
											</tr>
										);
									})}
								</tbody>
							</table>
						)}
					</div>
					<div style={{ marginBottom: 24 }}>
						<button type="button" className="btn-soft" onClick={addWnaBoard}>
							<svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 4v16m8-8H4" /></svg>
							Add Pengurus (WNA)
						</button>
					</div>

					<div className="section-label"><span className="dot" />Supporting Documents<hr /></div>
					<div className="form-grid" style={{ marginBottom: 24 }}>
						{[
							{ label: "Akta Pendirian", type: "corp-guarantor-akta" },
							{ label: "SK Kemenkumham Akta Pendirian", type: "corp-guarantor-sk-akta" },
							{ label: "Akta Perubahan Terakhir", type: "corp-guarantor-akta-terakhir" },
							{ label: "SK Kemenkumham atas Akta Perubahan Terakhir", type: "corp-guarantor-sk-akta-terakhir" },
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
						Submit Prechecking
					</button>
				</div>

			</div>
		</div>
	);
};

const DirectorCard: React.FC<{
	entry: DirectorEntry;
	label: string;
	apless: string;
	precheckingId: string;
	lesseeType: string;
	docsOf: (type: string) => UploadedDoc[];
	uploadingDocs: Set<string>;
	deletingDocs: Set<number>;
	onUploadDoc: (f: File, docType: string) => void;
	onDeleteDoc: (id: number) => void;
	onPreview: (doc: UploadedDoc) => void;
	onChange: (data: DirectorData, conf: ConfidenceMap) => void;
	errors: Record<string, string>;
	onHistoryModal: (msg: string, apless: string, type: string, pid: string) => void;
}> = ({
	entry, label, apless, precheckingId, lesseeType, docsOf, uploadingDocs, deletingDocs,
	onUploadDoc, onDeleteDoc, onPreview, onChange, errors,
	onHistoryModal,
}) => {

		const handleOcrChange = (data: any, conf: any) => {
			onChange(
				{ ...entry.data, ...data, maritalStatus: data.maritalStatus ?? entry.data.maritalStatus },
				{ ...entry.conf, ...conf },
			);
		};

		const setMaritalStatus = (val: string) => {
			onChange({ ...entry.data, maritalStatus: val }, entry.conf);
		};

		const docType = `corp-guarantor-ocr-ktp_${entry.uid}`;
		const errKey = `director_${entry.uid}_maritalStatus`;

		return (
			<div>
				<div style={{ marginBottom: 16 }}>
					<div className="form-field full">
						<label className="form-label">Upload ID Card Pengurus for OCR <span className="req">*</span></label>
					</div>
				</div>

				<OCRUploadSection
					apless={apless}
					precheckingId={precheckingId}
					ocrFor="corporate_guarantor"
					docType={docType}
					title={`Pengurus ${label} · WNI`}
					nationality="WNI"
					lesseeType={lesseeType}
					onDataChange={handleOcrChange}
					onHistoryModal={onHistoryModal}
				/>

				<div className="form-grid" style={{ marginTop: 16 }}>
					<div className="form-field">
						<label className="form-label">Status Perkawinan <span className="req">*</span></label>
						<input
							value={entry.data.maritalStatus}
							onChange={(e) => setMaritalStatus(e.target.value)}
							className={`form-input${errors[errKey] ? " err" : ""}`}
							maxLength={50}
						/>
						{errors[errKey] && <p className="field-err">{errors[errKey]}</p>}
					</div>
				</div>
			</div>
		);
	};

export default PrecheckingGuarantorCorporatePage;