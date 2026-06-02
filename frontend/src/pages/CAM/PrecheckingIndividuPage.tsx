import React, { useState, useEffect, useRef, useCallback } from "react";
import axios from "axios";

const fontLink = document.createElement("link");
fontLink.rel = "stylesheet";
fontLink.href =
	"https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap";
document.head.appendChild(fontLink);

/* ─── Types ────────────────────────────────────────────────────────────── */
interface CustomerData {
	idCardNo: string; name: string; placeOfBirth: string; dateOfBirth: string;
	gender: string; bloodType: string; address: string; rt: string; rw: string;
	subdistrict: string; district: string; city: string; province: string;
	religion: string; job: string; citizen: string; photo: string; signature: string;
}
type ConfidenceMap = Partial<Record<keyof CustomerData, string>>;
type VerifiedMap = Partial<Record<keyof CustomerData, string>>;
interface MaritalOption { value: string; label: string; }
interface ModalState {
	open: boolean; type: "reject" | "inprogress" | "valid" | "expired" | "";
	message: string; apless: string; precheckingId: string;
}
interface UploadedDoc { id: number; name: string; type: string; key: string; }

const EMPTY_CUSTOMER = (): CustomerData => ({
	idCardNo: "", name: "", placeOfBirth: "", dateOfBirth: "",
	gender: "", bloodType: "", address: "", rt: "", rw: "",
	subdistrict: "", district: "", city: "", province: "",
	religion: "", job: "", citizen: "", photo: "", signature: "",
});

const API_BASE = (typeof import.meta !== "undefined" && (import.meta as any).env?.VITE_API_URL) ?? "/CAM/Prechecking";

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

  /* Header */
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

  /* Cards */
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
    width: 8px; height: 8px; border-radius: 50%; background: var(--blue);
    flex-shrink: 0;
  }
  .section-label hr { flex: 1; border: none; border-top: 1.5px solid var(--border); }

  /* Form Grid */
  .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px 28px; }
  @media (max-width: 700px) { .form-grid { grid-template-columns: 1fr; } }
  .form-field { display: flex; flex-direction: column; gap: 6px; }
  .form-field.full { grid-column: 1 / -1; }
  .form-label {
    font-size: .78rem; font-weight: 600; color: var(--ink); letter-spacing: .01em;
  }
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
  .form-input.readonly { background: #F8FAFF; color: var(--muted); cursor: not-allowed; }
  .form-textarea { resize: vertical; min-height: 72px; }
  .field-err { font-size: .72rem; color: var(--rose); margin-top: 2px; }

  /* Upload zone */
  .upload-zone {
    border: 2px dashed var(--border); border-radius: 12px;
    padding: 16px 20px; text-align: center; cursor: pointer;
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

  /* Doc chip */
  .doc-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
  .doc-chip {
    display: inline-flex; align-items: center; gap: 5px;
    background: var(--sky); border: 1px solid #C7D7F8;
    border-radius: 6px; padding: 3px 8px 3px 10px;
    font-size: .72rem; font-weight: 500; color: var(--navy);
  }
  .doc-chip-del {
    background: none; border: none; cursor: pointer;
    color: var(--muted); font-size: .9rem; line-height: 1; padding: 0;
    transition: color .15s;
  }
  .doc-chip-del:hover { color: var(--rose); }

  /* OCR Table wrapper */
  .ocr-card {
    border: 1.5px solid var(--border); border-radius: 16px; overflow: hidden;
    margin-bottom: 20px; box-shadow: 0 2px 12px rgba(15,29,60,.05);
  }
  .ocr-card-header {
    background: linear-gradient(135deg, var(--navy), #2D5BE3);
    padding: 14px 20px; display: flex; justify-content: space-between; align-items: center;
  }
  .ocr-card-title { color: #fff; font-size: .875rem; font-weight: 700; }
  .ocr-upload-inline {
    display: flex; align-items: center; gap: 8px;
  }
  .ocr-upload-btn {
    background: rgba(255,255,255,.15); border: 1px solid rgba(255,255,255,.3);
    border-radius: 8px; padding: 6px 14px; color: #fff;
    font-size: .78rem; font-weight: 600; font-family: var(--font);
    cursor: pointer; transition: background .2s; display: flex; align-items: center; gap: 6px;
  }
  .ocr-upload-btn:hover { background: rgba(255,255,255,.25); }

  /* OCR Table */
  .ocr-table { width: 100%; border-collapse: collapse; }
  .ocr-thead th {
    background: #F4F7FF; padding: 10px 14px; font-size: .72rem;
    font-weight: 700; text-transform: uppercase; letter-spacing: .06em;
    color: var(--muted); border-bottom: 1.5px solid var(--border); text-align: left;
  }
  .ocr-thead th.center { text-align: center; }
  .ocr-tr { border-bottom: 1px solid #F0F3FA; transition: background .15s; }
  .ocr-tr:hover { background: #F8FAFF; }
  .ocr-tr:last-child { border-bottom: none; }
  .ocr-td { padding: 10px 14px; vertical-align: middle; }
  .ocr-label { font-size: .8rem; font-weight: 600; color: var(--ink); }
  .ocr-label .req { color: var(--rose); }
  .ocr-input {
    width: 100%; padding: 7px 12px; font-size: .82rem; font-family: var(--font);
    border: 1.5px solid var(--border); border-radius: 8px; color: var(--ink);
    background: #fff; outline: none; transition: border-color .18s, box-shadow .18s;
  }
  .ocr-input:focus { border-color: var(--blue); box-shadow: 0 0 0 3px rgba(45,91,227,.1); }
  .ocr-input.err { border-color: var(--rose); }
  .ocr-textarea {
    width: 100%; padding: 7px 12px; font-size: .82rem; font-family: var(--font);
    border: 1.5px solid var(--border); border-radius: 8px; color: var(--ink);
    background: #fff; outline: none; transition: border-color .18s; resize: none; rows: 2;
  }
  .ocr-textarea:focus { border-color: var(--blue); box-shadow: 0 0 0 3px rgba(45,91,227,.1); }

  /* Confidence badge */
  .conf-badge {
    display: inline-block; padding: 4px 10px; border-radius: 20px;
    font-size: .72rem; font-weight: 700; font-family: var(--mono);
    text-align: center; width: 100%;
  }
  .conf-high   { background: #DCFCE7; color: #15803D; border: 1px solid #BBF7D0; }
  .conf-medium { background: #FEF9C3; color: #A16207; border: 1px solid #FDE68A; }
  .conf-low    { background: #FEE2E2; color: #B91C1C; border: 1px solid #FECACA; }
  .conf-empty  { background: #F1F5F9; color: #94A3B8; border: 1px solid #E2E8F0; }

  /* Verified badge */
  .ver-badge {
    display: inline-block; padding: 4px 10px; border-radius: 20px;
    font-size: .72rem; font-weight: 600; text-align: center; width: 100%;
    background: #ECFDF5; color: #065F46; border: 1px solid #A7F3D0;
  }
  .ver-empty {
    background: #F8FAFF; color: #94A3B8; border: 1px solid #E2E8F0;
  }

  /* Verify button (in table header) */
  .verify-btn {
    background: linear-gradient(135deg, #10B981, #059669);
    border: none; border-radius: 8px; padding: 6px 14px;
    color: #fff; font-size: .75rem; font-weight: 700; font-family: var(--font);
    cursor: pointer; transition: opacity .2s; display: flex; align-items: center; gap: 5px;
  }
  .verify-btn:hover { opacity: .88; }

  /* Buttons */
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

  /* Custom select wrapper with icon */
  .select-wrap { position: relative; }
  .select-wrap select { appearance: none; padding-right: 36px; }
  .select-wrap::after {
    content: ''; position: absolute; right: 12px; top: 50%; transform: translateY(-50%);
    width: 0; height: 0;
    border-left: 5px solid transparent; border-right: 5px solid transparent;
    border-top: 6px solid var(--muted); pointer-events: none;
  }
  .select-wrap:focus-within::after { border-top-color: var(--blue); }

  /* Photo / signature cells */
  .id-photo {
    height: 96px; width: 72px; object-fit: cover; border-radius: 8px;
    border: 2px solid var(--border); box-shadow: 0 2px 8px rgba(0,0,0,.1);
  }
  .id-photo-empty {
    height: 96px; width: 72px; background: #F4F7FF;
    border-radius: 8px; border: 2px dashed var(--border);
    display: flex; align-items: center; justify-content: center;
    color: var(--muted); font-size: .65rem; text-align: center; padding: 4px;
  }
  .id-sig { height: 44px; border-radius: 6px; border: 1.5px solid var(--border); background: #fff; }
  .id-sig-empty {
    height: 44px; width: 120px; background: #F8FAFF;
    border-radius: 6px; border: 2px dashed var(--border);
  }

  /* WNA info section */
  .sub-section {
    border-radius: 12px; padding: 20px; border: 1.5px solid;
  }
  .sub-section.blue   { border-color: #BFDBFE; background: #EFF6FF; }
  .sub-section.orange { border-color: #FED7AA; background: #FFF7ED; }
  .sub-section.purple { border-color: #DDD6FE; background: #F5F3FF; }
  .sub-section-title { font-size: .82rem; font-weight: 700; margin-bottom: 16px; }
  .sub-section.blue   .sub-section-title { color: #1E3A8A; }
  .sub-section.orange .sub-section-title { color: #9A3412; }
  .sub-section.purple .sub-section-title { color: #4C1D95; }

  /* RT/RW row */
  .rtrw-wrap { display: flex; align-items: center; gap: 8px; }
  .rtrw-wrap input { width: 72px; }
  .rtrw-sep { color: var(--muted); font-weight: 700; }

  /* Spinner */
  .spin {
    display: inline-block; width: 18px; height: 18px; border-radius: 50%;
    border: 3px solid rgba(255,255,255,.3); border-top-color: #fff;
    animation: spin .7s linear infinite; flex-shrink: 0;
  }
  .spin.dark { border-color: rgba(27,58,122,.15); border-top-color: var(--navy); }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* OCR overlay */
  .ocr-overlay {
    position: fixed; inset: 0; background: rgba(15,29,60,.6);
    display: flex; align-items: center; justify-content: center; z-index: 50;
    backdrop-filter: blur(4px);
  }
  .ocr-overlay-card {
    background: #fff; border-radius: 20px; padding: 40px 48px; text-align: center;
    box-shadow: 0 24px 80px rgba(15,29,60,.25);
  }
  .ocr-overlay-title { font-size: 1rem; font-weight: 700; color: var(--ink); margin-top: 16px; }
  .ocr-overlay-sub   { font-size: .82rem; color: var(--muted); margin-top: 4px; }

  /* Modal */
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

  /* Action bar */
  .action-bar {
    background: #fff; border-top: 1.5px solid var(--border);
    padding: 16px 28px; display: flex; justify-content: flex-end; gap: 12px;
    border-radius: 0 0 16px 16px; margin-top: 4px;
  }

  /* Top form stack (single column) */
  .top-form-stack {
    display: flex; flex-direction: column; gap: 14px; margin-bottom: 24px;
    max-width: 460px;
  }

  /* Nationality highlighted select */
  .form-select.nat-active {
    border-color: var(--blue); background: var(--sky); color: var(--navy); font-weight: 700;
  }
  /* Readonly input style */
  .form-input.is-readonly {
    background: #F4F7FF; color: var(--muted); cursor: default; border-color: #E8EEF8;
  }
  /* Disabled select style */
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

const ConfBadge: React.FC<{ value?: string }> = ({ value }) => {
	if (!value) return <span className="conf-badge conf-empty">—</span>;
	const n = parseInt(value.replace("%", ""), 10);
	const cls = n >= 90 ? "conf-high" : n >= 70 ? "conf-medium" : "conf-low";
	return <span className={`conf-badge ${cls}`}>{value}</span>;
};

const VerBadge: React.FC<{ value?: string }> = ({ value }) =>
	value ? (
		<span className="ver-badge">{value}</span>
	) : (
		<span className="ver-badge ver-empty">—</span>
	);

interface OcrRowProps {
	label: string; fieldKey: keyof CustomerData;
	value: string; confidence?: string; verified?: string;
	error?: string; required?: boolean; textarea?: boolean;
	numeric?: boolean; maxLen?: number;
	onChange: (v: string) => void;
}
const OcrRow: React.FC<OcrRowProps> = ({
	label, value, confidence, verified, error, required, textarea, numeric, maxLen, onChange,
}) => {
	const handleChange = (raw: string) => {
		if (numeric) {
			const digits = raw.replace(/\D/g, "");
			onChange(maxLen ? digits.slice(0, maxLen) : digits);
		} else {
			onChange((textarea ? raw : raw.toUpperCase()));
		}
	};
	return (
		<tr className="ocr-tr">
			<td className="ocr-td" style={{ width: "22%", whiteSpace: "nowrap" }}>
				<span className="ocr-label">{label}{required && <span className="req">*</span>}</span>
			</td>
			<td className="ocr-td" style={{ width: "38%" }}>
				{textarea ? (
					<textarea
						value={value} onChange={(e) => handleChange(e.target.value)}
						rows={2} maxLength={250}
						className={`ocr-textarea${error ? " err" : ""}`}
						style={{ textTransform: "uppercase" }}
					/>
				) : (
					<input
						type={numeric ? "text" : "text"}
						inputMode={numeric ? "numeric" : "text"}
						value={value} onChange={(e) => handleChange(e.target.value)}
						maxLength={maxLen}
						className={`ocr-input${error ? " err" : ""}`}
						style={!numeric ? { textTransform: "uppercase" } : undefined}
					/>
				)}
				{error && <p className="field-err">{error}</p>}
			</td>
			<td className="ocr-td" style={{ width: "20%", textAlign: "center" }}>
				<ConfBadge value={confidence} />
			</td>
			<td className="ocr-td" style={{ width: "20%", textAlign: "center" }}>
				<VerBadge value={verified} />
			</td>
		</tr>
	);
};

const DocList: React.FC<{ docs: UploadedDoc[]; onDelete: (id: number) => void }> = ({
	docs, onDelete,
}) =>
	docs.length ? (
		<div className="doc-chips">
			{docs.map((d) => (
				<span key={d.id} className="doc-chip">
					{d.name}
					<button className="doc-chip-del" onClick={() => onDelete(d.id)}>×</button>
				</span>
			))}
		</div>
	) : null;

const FileInput: React.FC<{ multiple?: boolean; onFileChange: (f: File) => void; label?: string }> = ({
	multiple, onFileChange, label = "Upload Document",
}) => {
	const ref = useRef<HTMLInputElement>(null);
	return (
		<label
			className="upload-zone"
			onClick={() => ref.current?.click()}
			style={{ cursor: "pointer" }}
		>
			<div className="upload-zone-icon">
				<svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
						d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
				</svg>
			</div>
			<div className="upload-zone-text">
				<div className="upload-zone-title">{label}</div>
				<div className="upload-zone-sub">PNG, JPG, PDF, TIFF · max 2 MB</div>
			</div>
			<input
				ref={ref} type="file" multiple={multiple}
				accept=".png,.jpg,.jpeg,.pdf,.tiff"
				style={{ display: "none" }}
				onChange={(e) => { const f = e.target.files?.[0]; if (f) onFileChange(f); }}
			/>
		</label>
	);
};

interface OCRSectionProps {
	title: string; fileInputRef: React.RefObject<HTMLInputElement>;
	onFileChange: (file: File) => void; showVerify: boolean; onVerify: () => void;
	data: CustomerData; setData: React.Dispatch<React.SetStateAction<CustomerData>>;
	conf: ConfidenceMap; ver: VerifiedMap; errors: Record<string, string>;
	prefix: string; docs: UploadedDoc[]; onDeleteDoc: (id: number) => void;
}
const OCRSection: React.FC<OCRSectionProps> = ({
	title, fileInputRef, onFileChange, showVerify, onVerify,
	data, setData, conf, ver, errors, prefix, docs, onDeleteDoc,
}) => {
	const upd = (field: keyof CustomerData) => (v: string) =>
		setData((prev) => ({ ...prev, [field]: v }));

	return (
		<div className="ocr-card">
			{/* Header */}
			<div className="ocr-card-header">
				<span className="ocr-card-title">{title}</span>
				<div className="ocr-upload-inline">
					<label className="ocr-upload-btn">
						<svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
								d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
						</svg>
						Upload KTP for OCR
						<input
							type="file" ref={fileInputRef} accept=".png,.jpg,.jpeg,.pdf,.tiff"
							style={{ display: "none" }}
							onChange={(e) => { const f = e.target.files?.[0]; if (f) onFileChange(f); }}
						/>
					</label>
				</div>
			</div>

			{/* Uploaded doc chips */}
			{docs.length > 0 && (
				<div style={{ padding: "10px 16px", borderBottom: "1px solid var(--border)", background: "#F8FAFF" }}>
					<DocList docs={docs} onDelete={onDeleteDoc} />
				</div>
			)}

			{/* Table */}
			<div style={{ overflowX: "auto" }}>
				<table className="ocr-table">
					<thead className="ocr-thead">
						<tr>
							<th>Field</th>
							<th>Value</th>
							<th className="center">Confidence Rate</th>
							<th className="center">
								{showVerify && (
									<button className="verify-btn" onClick={onVerify}>
										<svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5}
												d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
										</svg>
										Verify Dukcapil
									</button>
								)}
								{!showVerify && <span style={{ fontSize: ".72rem", color: "var(--muted)" }}>Verified (Dukcapil)</span>}
							</th>
						</tr>
					</thead>
					<tbody>
						<OcrRow label="NIK" fieldKey="idCardNo" value={data.idCardNo}
							confidence={conf.idCardNo} verified={ver.idCardNo}
							error={errors[`${prefix}_idCardNo`]} required numeric maxLen={16} onChange={upd("idCardNo")} />
						<OcrRow label="Nama" fieldKey="name" value={data.name}
							confidence={conf.name} verified={ver.name}
							error={errors[`${prefix}_name`]} required onChange={upd("name")} />
						<OcrRow label="Tempat Lahir" fieldKey="placeOfBirth" value={data.placeOfBirth}
							confidence={conf.placeOfBirth} verified={ver.placeOfBirth}
							error={errors[`${prefix}_pob`]} required onChange={upd("placeOfBirth")} />
						<OcrRow label="Tanggal Lahir" fieldKey="dateOfBirth" value={data.dateOfBirth}
							confidence={conf.dateOfBirth} verified={ver.dateOfBirth}
							error={errors[`${prefix}_dob`]} required onChange={upd("dateOfBirth")} />
						<OcrRow label="Jenis Kelamin" fieldKey="gender" value={data.gender}
							confidence={conf.gender} verified={ver.gender}
							error={errors[`${prefix}_gender`]} required onChange={upd("gender")} />
						<OcrRow label="Golongan Darah" fieldKey="bloodType" value={data.bloodType}
							confidence={conf.bloodType} onChange={upd("bloodType")} />
						<OcrRow label="Alamat" fieldKey="address" value={data.address}
							confidence={conf.address} verified={ver.address}
							error={errors[`${prefix}_address`]} required textarea onChange={upd("address")} />

						{/* RT / RW */}
						<tr className="ocr-tr">
							<td className="ocr-td">
								<span className="ocr-label">RT/RW <span className="req">*</span></span>
							</td>
							<td className="ocr-td">
								<div className="rtrw-wrap">
									<input
										value={data.rt}
										onChange={(e) => upd("rt")(e.target.value.replace(/\D/g, "").slice(0, 3))}
										inputMode="numeric" maxLength={3}
										className={`ocr-input${errors[`${prefix}_rt`] ? " err" : ""}`}
										placeholder="RT"
										style={{ width: 72 }}
									/>
									<span className="rtrw-sep">/</span>
									<input
										value={data.rw}
										onChange={(e) => upd("rw")(e.target.value.replace(/\D/g, "").slice(0, 3))}
										inputMode="numeric" maxLength={3}
										className="ocr-input" placeholder="RW" style={{ width: 72 }}
									/>
								</div>
								{errors[`${prefix}_rt`] && <p className="field-err">{errors[`${prefix}_rt`]}</p>}
							</td>
							<td className="ocr-td" style={{ textAlign: "center" }}>
								<ConfBadge value={conf.rt} />
							</td>
							<td className="ocr-td" style={{ textAlign: "center" }}>
								<VerBadge value={ver.rt} />
							</td>
						</tr>

						<OcrRow label="Kelurahan/Desa" fieldKey="subdistrict" value={data.subdistrict}
							confidence={conf.subdistrict} verified={ver.subdistrict}
							error={errors[`${prefix}_subdistrict`]} required onChange={upd("subdistrict")} />
						<OcrRow label="Kecamatan" fieldKey="district" value={data.district}
							confidence={conf.district} verified={ver.district}
							error={errors[`${prefix}_district`]} required onChange={upd("district")} />
						<OcrRow label="Kota/Kabupaten" fieldKey="city" value={data.city}
							confidence={conf.city} verified={ver.city}
							error={errors[`${prefix}_city`]} required onChange={upd("city")} />
						<OcrRow label="Provinsi" fieldKey="province" value={data.province}
							confidence={conf.province} verified={ver.province}
							error={errors[`${prefix}_province`]} required onChange={upd("province")} />
						<OcrRow label="Agama" fieldKey="religion" value={data.religion}
							confidence={conf.religion} verified={ver.religion}
							error={errors[`${prefix}_religion`]} required onChange={upd("religion")} />
						<OcrRow label="Pekerjaan" fieldKey="job" value={data.job}
							confidence={conf.job} verified={ver.job}
							error={errors[`${prefix}_job`]} required onChange={upd("job")} />

						{/* Photo */}
						<tr className="ocr-tr">
							<td className="ocr-td"><span className="ocr-label">Foto <span className="req">*</span></span></td>
							<td className="ocr-td" colSpan={3}>
								{data.photo ? (
									<img src={`data:image/jpeg;base64,${data.photo}`} alt="Photo" className="id-photo" />
								) : (
									<div className="id-photo-empty">No Photo</div>
								)}
							</td>
						</tr>

						{/* Signature */}
						<tr className="ocr-tr">
							<td className="ocr-td"><span className="ocr-label">Tanda Tangan <span className="req">*</span></span></td>
							<td className="ocr-td" colSpan={3}>
								{data.signature ? (
									<img src={`data:image/jpeg;base64,${data.signature}`} alt="Signature" className="id-sig" />
								) : (
									<div className="id-sig-empty" />
								)}
							</td>
						</tr>
					</tbody>
				</table>
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
							<button
								className="btn-modal-ghost"
								onClick={() => window.location.href = `/repeat-order?apless=${modal.apless}&prechecking_id=${modal.precheckingId}&types=P`}>
								Prechecking
							</button>
							<button
								className="btn-modal-primary"
								onClick={() => window.location.href = `/create-cam?apless=${modal.apless}&prechecking_id=${modal.precheckingId}&lessee_tp=PR`}>
								Create New CAM
							</button>
						</>
					)}
					{(modal.type === "inprogress" || modal.type === "expired") && (
						<button className="btn-modal-primary" onClick={() => {
							close();
							if (modal.type === "expired")
								window.location.href = `/repeat-order?apless=${modal.apless}&prechecking_id=${modal.precheckingId}&types=P`;
						}}>Close</button>
					)}
				</div>
			</div>
		</div>
	);
};

const PrecheckingIndividuPage: React.FC = () => {
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

	const [customer, setCustomer] = useState<CustomerData>(EMPTY_CUSTOMER());
	const [spouse, setSpouse] = useState<CustomerData>(EMPTY_CUSTOMER());
	const [wnaSpouse, setWnaSpouse] = useState<CustomerData>(EMPTY_CUSTOMER());
	const [wnaName, setWnaName] = useState("");
	const [wnaIdCard, setWnaIdCard] = useState("");
	const [wnaSpName, setWnaSpName] = useState("");
	const [wnaSpId, setWnaSpId] = useState("");

	const [custConf, setCustConf] = useState<ConfidenceMap>({});
	const [spouseConf, setSpouseConf] = useState<ConfidenceMap>({});
	const [wnaSpConf, setWnaSpConf] = useState<ConfidenceMap>({});
	const [custVer, setCustVer] = useState<VerifiedMap>({});
	const [spouseVer, setSpouseVer] = useState<VerifiedMap>({});
	const [wnaSpVer, setWnaSpVer] = useState<VerifiedMap>({});

	const [showVerifyCust, setShowVerifyCust] = useState(false);
	const [showVerifySpouse, setShowVerifySpouse] = useState(false);
	const [showVerifyWnaSp, setShowVerifyWnaSp] = useState(false);

	const [docs, setDocs] = useState<UploadedDoc[]>([]);
	const [loading, setLoading] = useState(false);
	const [ocrLoading, setOcrLoading] = useState(false);
	const [errors, setErrors] = useState<Record<string, string>>({});
	const [modal, setModal] = useState<ModalState>({
		open: false, type: "", message: "", apless: "", precheckingId: "",
	});

	const ktpRef = useRef<HTMLInputElement>(null);
	const spouseKtpRef = useRef<HTMLInputElement>(null);
	const wnaSpKtpRef = useRef<HTMLInputElement>(null);

	useEffect(() => {
		const init = async () => {
			setLoading(true);
			try {
				const [aplessR, pidR, maritalR] = await Promise.all([
					axios.post(`${API_BASE}/CAM/Prechecking/generate-apless`, { customer_type: "PR" }),
					axios.post(`${API_BASE}/CAM/Prechecking/generate-prechecking-id`, {}),
					axios.get(`${API_BASE}/CAM/Prechecking/marital-statuses`),
				]);
				setApless(aplessR.data);
				setPrecheckingId(pidR.data);
				setMaritalOptions(maritalR.data);
			} catch (e) { console.error("Init error", e); }
			finally { setLoading(false); }
		};
		init();
	}, []);

	const handleOCR = useCallback(async (file: File, ocrFor: "customer" | "spouse" | "wna_spouse") => {
		if (file.size > 2 * 1024 * 1024) { alert("File size exceeds 2 MB."); return; }
		setOcrLoading(true);
		try {
			const qFD = new FormData();
			qFD.append("image", file); qFD.append("param", "check_qualities");
			qFD.append("prechecking_id", precheckingId);
			const qRes = await axios.post("/CAM/OCR/scanOCRCustomer", qFD, { headers: { "Content-Type": "multipart/form-data" } });
			const qData = qRes.data;
			if (qData.status !== "SUCCESS" || qData.qualities?.blur?.value === true || qData.qualities?.document?.value !== "ktp") {
				alert(qData.reason || "Document quality check failed. Please use a clearer KTP image."); return;
			}
			const oFD = new FormData();
			oFD.append("image", file); oFD.append("param", "ocr_customer"); oFD.append("apless", apless);
			oFD.append("customer_type", "PR"); oFD.append("prechecking_id", precheckingId);
			oFD.append("check_for", "C"); oFD.append("repeat_order", "0");
			oFD.append("ocr_for", ocrFor === "customer" ? "C" : "S");
			const oRes = await axios.post("/CAM/OCR/scanOCRCustomer", oFD, { headers: { "Content-Type": "multipart/form-data" } });
			const r = oRes.data;
			if (r.status !== "SUCCESS" || !r.read) { alert(r.reason || "OCR failed."); return; }
			const read = r.read ?? {}; const images = r.images ?? {};
			const [rtVal, rwVal] = (read.rtRw?.value ?? "/").split("/");
			const mapped: CustomerData = {
				idCardNo: read.nik?.value ?? "", name: read.nama?.value ?? "",
				placeOfBirth: read.tempatLahir?.value ?? "", dateOfBirth: read.tanggalLahir?.value ?? "",
				gender: read.jenisKelamin?.value ?? "", bloodType: read.golonganDarah?.value ?? "",
				address: read.alamat?.value ?? "", rt: (rtVal ?? "").trim(), rw: (rwVal ?? "").trim(),
				subdistrict: read.kelurahanDesa?.value ?? "", district: read.kecamatan?.value ?? "",
				city: read.kotaKabupaten?.value ?? "", province: read.provinsi?.value ?? "",
				religion: read.agama?.value ?? "", job: read.pekerjaan?.value ?? "",
				citizen: read.kewarganegaraan?.value || "WNI", photo: images.photo ?? "", signature: images.sign ?? "",
			};
			const conf: ConfidenceMap = {
				idCardNo: read.nik?.confidence != null ? `${read.nik.confidence}%` : "",
				name: read.nama?.confidence != null ? `${read.nama.confidence}%` : "",
				placeOfBirth: read.tempatLahir?.confidence != null ? `${read.tempatLahir.confidence}%` : "",
				dateOfBirth: read.tanggalLahir?.confidence != null ? `${read.tanggalLahir.confidence}%` : "",
				gender: read.jenisKelamin?.confidence != null ? `${read.jenisKelamin.confidence}%` : "",
				bloodType: read.golonganDarah?.confidence != null ? `${read.golonganDarah.confidence}%` : "",
				address: read.alamat?.confidence != null ? `${read.alamat.confidence}%` : "",
				rt: read.rtRw?.confidence != null ? `${read.rtRw.confidence}%` : "",
				subdistrict: read.kelurahanDesa?.confidence != null ? `${read.kelurahanDesa.confidence}%` : "",
				district: read.kecamatan?.confidence != null ? `${read.kecamatan.confidence}%` : "",
				city: read.kotaKabupaten?.confidence != null ? `${read.kotaKabupaten.confidence}%` : "",
				province: read.provinsi?.confidence != null ? `${read.provinsi.confidence}%` : "",
				religion: read.agama?.confidence != null ? `${read.agama.confidence}%` : "",
				job: read.pekerjaan?.confidence != null ? `${read.pekerjaan.confidence}%` : "",
			};
			if (ocrFor === "customer") {
				setCustomer(mapped); setCustConf(conf); setShowVerifyCust(true);
				if (mapped.idCardNo && nationality === "WNI") {
					const histRes = await axios.post(`${API_BASE}/CAM/Prechecking/check-customer-history`, {
						idNo: mapped.idCardNo, prechecking_id: precheckingId, lesseeType: "PR", checking_for: "C",
					});
					const [msg, al, type, pid] = histRes.data;
					if (msg) {
						if (type === "expired") { window.location.href = `/repeat-order?apless=${al}&prechecking_id=${pid}&types=P`; }
						else { setModal({ open: true, type, message: msg, apless: al, precheckingId: pid }); }
					}
				}
			} else if (ocrFor === "spouse") {
				setSpouse(mapped); setSpouseConf(conf); setShowVerifySpouse(true);
			} else {
				setWnaSpouse(mapped); setWnaSpConf(conf); setShowVerifyWnaSp(true);
			}
			await _uploadDoc(file, ocrFor === "customer" ? "cust-ktp" : ocrFor === "spouse" ? "cust-spouse-ktp" : "cust-wna-spouse-ktp");
		} catch (e: any) {
			console.error("OCR error", e); alert(e.response?.data?.reason ?? "OCR processing failed.");
		} finally { setOcrLoading(false); }
	}, [apless, precheckingId, nationality]);

	const handleVerify = useCallback(async (type: "customer" | "spouse" | "wna_spouse") => {
		const src = type === "customer" ? customer : type === "spouse" ? spouse : wnaSpouse;
		setOcrLoading(true);
		try {
			const fd = new FormData();
			fd.append("param", "check_data_duckapil"); fd.append("prechecking_id", precheckingId);
			fd.append("nik", src.idCardNo); fd.append("name", src.name);
			fd.append("place_of_birth", src.placeOfBirth); fd.append("date_of_birth", src.dateOfBirth);
			fd.append("gender", src.gender); fd.append("address", src.address);
			fd.append("rt", src.rt); fd.append("rw", src.rw);
			fd.append("subdistrict", src.subdistrict); fd.append("district", src.district);
			fd.append("city", src.city); fd.append("province", src.province); fd.append("job_type", src.job);
			const res = await axios.post("/CAM/OCR/scanOCRCustomer", fd, { headers: { "Content-Type": "multipart/form-data" } });
			const result = res.data?.result ?? {};
			const mapped: VerifiedMap = {
				idCardNo: result.nik ?? "", name: result.name ?? "", placeOfBirth: result.place_of_birth ?? "",
				dateOfBirth: result.date_of_birth ?? "", gender: result.gender ?? "", address: result.address ?? "",
				rt: result.rt ?? "", rw: result.rw ?? "", subdistrict: result.subdistrict ?? "",
				district: result.district ?? "", city: result.city ?? "", province: result.province ?? "", job: result.job_type ?? "",
			};
			if (type === "customer") setCustVer(mapped);
			else if (type === "spouse") setSpouseVer(mapped);
			else setWnaSpVer(mapped);
		} catch (e) { console.error("Verify error", e); alert("Verification failed."); }
		finally { setOcrLoading(false); }
	}, [customer, spouse, wnaSpouse, precheckingId]);

	const _uploadDoc = async (file: File, docType: string) => {
		const fd = new FormData();
		fd.append("file", file); fd.append("apless", apless);
		fd.append("prechecking_id", precheckingId); fd.append("document_type", docType);
		fd.append("cust_type", "PR"); fd.append("organization_type", "PR");
		await axios.post(`${API_BASE}/CAM/Prechecking/upload-document`, fd, { headers: { "Content-Type": "multipart/form-data" } });
		await _refreshDocs();
	};

	const _refreshDocs = async () => {
		if (!apless || !precheckingId) return;
		const res = await axios.get(`${API_BASE}/CAM/Prechecking/documents`, { params: { apless, prechecking_id: precheckingId } });
		setDocs(res.data ?? []);
	};

	const handleDeleteDoc = async (docId: number) => {
		if (!window.confirm("Are you sure to delete this record?")) return;
		await axios.post(`${API_BASE}/CAM/Prechecking/delete-document`, { customer_document_id: docId, prechecking_id: precheckingId });
		await _refreshDocs();
	};

	const handleWnaIdBlur = async () => {
		if (wnaIdCard.length < 6) return;
		try {
			const res = await axios.post(`${API_BASE}/CAM/Prechecking/check-customer-history`, {
				idNo: wnaIdCard, prechecking_id: precheckingId, lesseeType: "PR", checking_for: "C",
			});
			const [msg, al, type, pid] = res.data;
			if (msg) setModal({ open: true, type, message: msg, apless: al, precheckingId: pid });
		} catch (e) { console.error(e); }
	};

	const handleCancel = async () => {
		try { await axios.post(`${API_BASE}/CAM/Prechecking/cancel`, { prechecking_id: precheckingId }); }
		finally { window.history.back(); }
	};

	const handleSubmit = async () => {
		const e: Record<string, string> = {};
		if (!customer.idCardNo) e.cust_idCardNo = "NIK is required";
		if (!customer.name) e.cust_name = "Nama is required";
		if (!customer.placeOfBirth) e.cust_pob = "Tempat Lahir is required";
		if (!customer.dateOfBirth) e.cust_dob = "Tanggal Lahir is required";
		if (!customer.gender) e.cust_gender = "Jenis Kelamin is required";
		if (!customer.address) e.cust_address = "Alamat is required";
		if (!customer.rt) e.cust_rt = "RT/RW is required";
		if (!customer.subdistrict) e.cust_subdistrict = "Kelurahan/Desa is required";
		if (!customer.district) e.cust_district = "Kecamatan is required";
		if (!customer.city) e.cust_city = "Kota/Kabupaten is required";
		if (!customer.province) e.cust_province = "Provinsi is required";
		if (!customer.religion) e.cust_religion = "Agama is required";
		if (!customer.job) e.cust_job = "Pekerjaan is required";
		if (!marital) e.marital = "Marital Status is required";
		setErrors(e);
		if (Object.keys(e).length) return;
		setLoading(true);
		try {
			const payload = {
				prechecking_id: precheckingId, apless, cust_type: "PR", lessee_type: "PR",
				check_for: "C", cust_new_ro: "New", cust_nationality_type: nationality,
				marital_status: marital, wna_marital_status: wnaMarital,
				is_carro_type: isCarro ? 1 : 0, note_prechecking_pr: notes,
				cust_id_card_no: customer.idCardNo, cust_name: customer.name,
				cust_pob: customer.placeOfBirth, cust_dob: customer.dateOfBirth,
				cust_gender: customer.gender, cust_blood_type: customer.bloodType,
				cust_address: customer.address, cust_rt: customer.rt, cust_rw: customer.rw,
				cust_subdistrict: customer.subdistrict, cust_district: customer.district,
				cust_city: customer.city, cust_province: customer.province,
				cust_religion: customer.religion, cust_job: customer.job,
				cust_citizen: customer.citizen, cust_photo_hidden: customer.photo,
				cust_signature_hidden: customer.signature,
				val_cust_id_card_no: custConf.idCardNo ?? "", val_cust_name: custConf.name ?? "",
				val_cust_pob: custConf.placeOfBirth ?? "", val_cust_dob: custConf.dateOfBirth ?? "",
				val_cust_gender: custConf.gender ?? "", val_cust_blood_type: custConf.bloodType ?? "",
				val_cust_address: custConf.address ?? "", val_cust_rt: custConf.rt ?? "",
				val_cust_subdistrict: custConf.subdistrict ?? "", val_cust_district: custConf.district ?? "",
				val_cust_city: custConf.city ?? "", val_cust_province: custConf.province ?? "",
				val_cust_religion: custConf.religion ?? "", val_cust_job: custConf.job ?? "",
				ver_cust_id_card_no: custVer.idCardNo ?? "", ver_cust_name: custVer.name ?? "",
				ver_cust_pob: custVer.placeOfBirth ?? "", ver_cust_dob: custVer.dateOfBirth ?? "",
				ver_cust_gender: custVer.gender ?? "", ver_cust_address: custVer.address ?? "",
				ver_cust_rt: custVer.rt ?? "", ver_cust_subdistrict: custVer.subdistrict ?? "",
				ver_cust_district: custVer.district ?? "", ver_cust_city: custVer.city ?? "",
				ver_cust_province: custVer.province ?? "", ver_cust_job: custVer.job ?? "",
				cust_spouse_id_card_no: spouse.idCardNo, cust_spouse_name: spouse.name,
				cust_spouse_pob: spouse.placeOfBirth, cust_spouse_dob: spouse.dateOfBirth,
				cust_spouse_gender: spouse.gender, cust_spouse_blood_type: spouse.bloodType,
				cust_spouse_address: spouse.address, cust_spouse_rt: spouse.rt,
				cust_spouse_rw: spouse.rw, cust_spouse_subdistrict: spouse.subdistrict,
				cust_spouse_district: spouse.district, cust_spouse_city: spouse.city,
				cust_spouse_province: spouse.province, cust_spouse_religion: spouse.religion,
				cust_spouse_job: spouse.job, cust_spouse_citizen: spouse.citizen,
				cust_spouse_photo_hidden: spouse.photo, cust_spouse_signature_hidden: spouse.signature,
				wna_name: wnaName, wna_idcard_no: wnaIdCard,
				wna_spouse_name: wnaSpName, wna_spouse_idcard_no: wnaSpId,
				cust_wna_spouse_id_card_no: wnaSpouse.idCardNo, cust_wna_spouse_name: wnaSpouse.name,
				cust_wna_spouse_pob: wnaSpouse.placeOfBirth, cust_wna_spouse_dob: wnaSpouse.dateOfBirth,
				cust_wna_spouse_gender: wnaSpouse.gender, cust_wna_spouse_blood_type: wnaSpouse.bloodType,
				cust_wna_spouse_address: wnaSpouse.address, cust_wna_spouse_rt: wnaSpouse.rt,
				cust_wna_spouse_rw: wnaSpouse.rw, cust_wna_spouse_subdistrict: wnaSpouse.subdistrict,
				cust_wna_spouse_district: wnaSpouse.district, cust_wna_spouse_city: wnaSpouse.city,
				cust_wna_spouse_province: wnaSpouse.province, cust_wna_spouse_religion: wnaSpouse.religion,
				cust_wna_spouse_job: wnaSpouse.job, cust_wna_spouse_citizen: wnaSpouse.citizen,
				cust_wna_spouse_photo_hidden: wnaSpouse.photo, cust_wna_spouse_signature_hidden: wnaSpouse.signature,
			};
			const res = await axios.post(`${API_BASE}/CAM/Prechecking/submit`, payload);
			if (res.data?.success) { alert("Prechecking submitted successfully!"); window.history.back(); }
			else alert(res.data?.message ?? "Submission failed");
		} catch (err: any) { alert(err.response?.data?.message ?? "Submission failed"); }
		finally { setLoading(false); }
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

			{/* OCR loading overlay */}
			{ocrLoading && (
				<div className="ocr-overlay">
					<div className="ocr-overlay-card">
						<Spinner size={44} />
						<p className="ocr-overlay-title">Processing Document…</p>
						<p className="ocr-overlay-sub">Running OCR analysis, please wait</p>
					</div>
				</div>
			)}

			{modal.open && <HistoryModal modal={modal} setModal={setModal} />}

			<div className="page-wrap">

				{/* ── Header ──────────────────────────────────────────────────── */}
				<div className="hdr">
					<div>
						<div className="hdr-title">Add Prechecking Data</div>
						<div className="hdr-sub">Individual Customer · KYC Verification</div>
					</div>
					<div className="hdr-badge">
						<span className="hdr-badge-label">Prechecking ID</span>
						<span className="hdr-badge-value">{precheckingId || "—"}</span>
					</div>
				</div>

				{/* ── Main card ───────────────────────────────────────────────── */}
				<div className="card">

					{/* ── Top meta fields ─────────────────────────────────────────── */}
					<div className="section-label"><span className="dot" />General Information<hr /></div>

					<div style={{ marginBottom: 24 }}>
						{/* Row 1: Checking For + Type */}
						<div className="form-grid" style={{ marginBottom: 14 }}>
							<div className="form-field">
								<label className="form-label">Checking For <span className="req">*</span></label>
								<div className="select-wrap">
									<select disabled value="C" className="form-select is-disabled">
										<option value="C">Customer</option>
									</select>
								</div>
							</div>
							<div className="form-field">
								<label className="form-label">Type <span className="req">*</span></label>
								<div className="select-wrap">
									<select disabled value="PR" className="form-select is-disabled">
										<option value="PR">Individu</option>
									</select>
								</div>
							</div>
						</div>

						{/* Row 2: New/Repeat Order + Temp Customer No */}
						<div className="form-grid" style={{ marginBottom: 14 }}>
							<div className="form-field">
								<label className="form-label">New / Repeat Order</label>
								<div className="select-wrap">
									<select disabled value="New" className="form-select is-disabled">
										<option value="New">New</option>
									</select>
								</div>
							</div>
							<div className="form-field">
								<label className="form-label">Temp. Customer No.</label>
								<input readOnly value={apless} className="form-input is-readonly" />
							</div>
						</div>

						{/* Row 3: Nationality alone (max-width matches one column) */}
						<div style={{ maxWidth: 460 }}>
							<div className="form-field">
								<label className="form-label">Nationality <span className="req">*</span></label>
								<div className="select-wrap">
									<select
										value={nationality}
										onChange={(e) => setNationality(e.target.value as "WNI" | "WNA")}
										className={`form-select${nationality ? " nat-active" : ""}`}
									>
										<option value="WNI">🇮🇩 WNI</option>
										<option value="WNA">🌐 WNA</option>
									</select>
								</div>
							</div>
						</div>
					</div>

					{/* ── WNI Customer OCR ──────────────────────────────────────── */}
					{nationality === "WNI" && (
						<>
							<div className="section-label"><span className="dot" />Customer KTP (OCR)<hr /></div>
							<OCRSection
								title="Customer · WNI"
								fileInputRef={ktpRef}
								onFileChange={(f) => handleOCR(f, "customer")}
								showVerify={showVerifyCust}
								onVerify={() => handleVerify("customer")}
								data={customer} setData={setCustomer}
								conf={custConf} ver={custVer}
								errors={errors} prefix="cust"
								docs={docsOf("cust-ktp")} onDeleteDoc={handleDeleteDoc}
							/>
						</>
					)}

					{/* ── WNA Customer ─────────────────────────────────────────── */}
					{showWnaSection && (
						<>
							<div className="section-label"><span className="dot" />Customer WNA Information<hr /></div>
							<div className="sub-section blue" style={{ marginBottom: 20 }}>
								<div className="sub-section-title">🌐 Customer WNA</div>
								<div className="form-grid">
									<div className="form-field">
										<label className="form-label">Nama <span className="req">*</span></label>
										<input value={wnaName} onChange={(e) => setWnaName(e.target.value.toUpperCase())} className="form-input" style={{ textTransform: "uppercase" }} />
									</div>
									<div className="form-field">
										<label className="form-label">ID Card No. <span className="req">*</span></label>
										<input value={wnaIdCard} onChange={(e) => setWnaIdCard(e.target.value)}
											onBlur={handleWnaIdBlur} className="form-input" />
									</div>
									<div className="form-field full">
										<label className="form-label">ID Card (KITAS/Passport)</label>
										<FileInput label="Upload KITAS / Passport" onFileChange={(f) => _uploadDoc(f, "cust-kitas")} />
										<DocList docs={docsOf("cust-kitas")} onDelete={handleDeleteDoc} />
									</div>
								</div>
							</div>
						</>
					)}

					{/* ── Marital Status (WNI) ──────────────────────────────────── */}
					{nationality === "WNI" && (
						<>
							<div className="section-label"><span className="dot" />Marital Status<hr /></div>
							<div className="form-grid" style={{ marginBottom: 20 }}>
								<div className="form-field">
									<label className="form-label">Marital Status <span className="req">*</span></label>
									<div className="select-wrap">
										<select value={marital} onChange={(e) => setMarital(e.target.value)}
											className={`form-select${errors.marital ? " err" : ""}`}>
											<option value="">— Select —</option>
											{maritalOptions.map((o) => (
												<option key={o.value} value={o.value}>{o.label}</option>
											))}
										</select>
									</div>
									{errors.marital && <p className="field-err">{errors.marital}</p>}
								</div>
								{showSpouseNat && (
									<div className="form-field">
										<label className="form-label">Spouse Nationality <span className="req">*</span></label>
										<div className="select-wrap">
											<select value={spouseNat} onChange={(e) => setSpouseNat(e.target.value as any)}
												className="form-select">
												<option value="">— Select —</option>
												<option value="WNI">WNI</option>
												<option value="WNA">WNA</option>
											</select>
										</div>
									</div>
								)}
							</div>
						</>
					)}

					{/* ── Marital Status (WNA) ──────────────────────────────────── */}
					{showWnaSection && (
						<>
							<div className="section-label"><span className="dot" />Marital Status (WNA)<hr /></div>
							<div className="form-grid" style={{ marginBottom: 20 }}>
								<div className="form-field">
									<label className="form-label">Marital Status <span className="req">*</span></label>
									<div className="select-wrap">
										<select value={wnaMarital} onChange={(e) => setWnaMarital(e.target.value)} className="form-select">
											<option value="">— Select —</option>
											{maritalOptions.map((o) => (
												<option key={o.value} value={o.value}>{o.label}</option>
											))}
										</select>
									</div>
								</div>
								{showWnaSpNat && (
									<div className="form-field">
										<label className="form-label">Spouse Nationality <span className="req">*</span></label>
										<div className="select-wrap">
											<select value={wnaSpouseNat} onChange={(e) => setWnaSpouseNat(e.target.value as any)} className="form-select">
												<option value="">— Select —</option>
												<option value="WNI">WNI</option>
												<option value="WNA">WNA</option>
											</select>
										</div>
									</div>
								)}
							</div>
						</>
					)}

					{/* ── WNI Spouse OCR ────────────────────────────────────────── */}
					{showSpouseOCR && (
						<>
							<div className="section-label"><span className="dot" />Spouse KTP (OCR)<hr /></div>
							<OCRSection
								title="Spouse · WNI"
								fileInputRef={spouseKtpRef}
								onFileChange={(f) => handleOCR(f, "spouse")}
								showVerify={showVerifySpouse}
								onVerify={() => handleVerify("spouse")}
								data={spouse} setData={setSpouse}
								conf={spouseConf} ver={spouseVer}
								errors={errors} prefix="spouse"
								docs={docsOf("cust-spouse-ktp")} onDeleteDoc={handleDeleteDoc}
							/>
						</>
					)}

					{/* ── WNA Spouse info ───────────────────────────────────────── */}
					{showWnaSpInfo && (
						<>
							<div className="section-label"><span className="dot" />Spouse (WNA)<hr /></div>
							<div className="sub-section orange" style={{ marginBottom: 20 }}>
								<div className="sub-section-title">Spouse — Foreign National</div>
								<div className="form-grid">
									<div className="form-field">
										<label className="form-label">Spouse Name <span className="req">*</span></label>
										<input value={wnaSpName} onChange={(e) => setWnaSpName(e.target.value.toUpperCase())} className="form-input" style={{ textTransform: "uppercase" }} />
									</div>
									<div className="form-field">
										<label className="form-label">Spouse ID Card No. <span className="req">*</span></label>
										<input value={wnaSpId} onChange={(e) => setWnaSpId(e.target.value)} className="form-input" />
									</div>
									<div className="form-field full">
										<label className="form-label">Spouse ID Card (KITAS)</label>
										<FileInput label="Upload Spouse KITAS" onFileChange={(f) => _uploadDoc(f, "cust-spouse-kitas")} />
										<DocList docs={docsOf("cust-spouse-kitas")} onDelete={handleDeleteDoc} />
									</div>
								</div>
							</div>
						</>
					)}

					{/* ── WNA Spouse with WNI OCR ───────────────────────────────── */}
					{showWnaSpOCR && (
						<>
							<div className="section-label"><span className="dot" />Spouse of WNA Customer (WNI KTP)<hr /></div>
							<OCRSection
								title="Spouse of WNA · WNI KTP"
								fileInputRef={wnaSpKtpRef}
								onFileChange={(f) => handleOCR(f, "wna_spouse")}
								showVerify={showVerifyWnaSp}
								onVerify={() => handleVerify("wna_spouse")}
								data={wnaSpouse} setData={setWnaSpouse}
								conf={wnaSpConf} ver={wnaSpVer}
								errors={errors} prefix="wna_spouse"
								docs={docsOf("cust-wna-spouse-ktp")} onDeleteDoc={handleDeleteDoc}
							/>
						</>
					)}

					{/* ── WNA Spouse (WNA) ─────────────────────────────────────── */}
					{showWnaSpWna && (
						<>
							<div className="section-label"><span className="dot" />Spouse of WNA (Foreign ID)<hr /></div>
							<div className="sub-section purple" style={{ marginBottom: 20 }}>
								<div className="sub-section-title">Spouse — Foreign National (KITAS)</div>
								<div className="form-grid">
									<div className="form-field">
										<label className="form-label">Spouse Name <span className="req">*</span></label>
										<input value={wnaSpName} onChange={(e) => setWnaSpName(e.target.value.toUpperCase())} className="form-input" style={{ textTransform: "uppercase" }} />
									</div>
									<div className="form-field">
										<label className="form-label">Spouse ID Card No. <span className="req">*</span></label>
										<input value={wnaSpId} onChange={(e) => setWnaSpId(e.target.value)} className="form-input" />
									</div>
									<div className="form-field full">
										<label className="form-label">Spouse KITAS</label>
										<FileInput label="Upload Spouse KITAS" onFileChange={(f) => _uploadDoc(f, "cust-spouse-kitas")} />
										<DocList docs={docsOf("cust-spouse-kitas")} onDelete={handleDeleteDoc} />
									</div>
								</div>
							</div>
						</>
					)}

					{/* ── Supporting Documents ──────────────────────────────────── */}
					<div className="section-label"><span className="dot" />Supporting Documents<hr /></div>
					<div className="form-grid" style={{ marginBottom: 24 }}>
						{[
							{ label: "KK (Kartu Keluarga)", type: "cust-kk" },
							{ label: "NPWP", type: "cust-npwp" },
							{ label: "Akta Cerai / Akta Kematian", type: "cust-marriage-or-death-statement" },
						].map((doc) => (
							<div className="form-field" key={doc.type}>
								<label className="form-label">{doc.label}</label>
								<FileInput multiple label={`Upload ${doc.label}`} onFileChange={(f) => _uploadDoc(f, doc.type)} />
								<DocList docs={docsOf(doc.type)} onDelete={handleDeleteDoc} />
							</div>
						))}
					</div>

					{/* ── Reference & Notes ─────────────────────────────────────── */}
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
							<textarea rows={4} value={notes} onChange={(e) => setNotes(e.target.value.toUpperCase())}
								className="form-textarea" placeholder="Optional notes…"
								style={{ textTransform: "uppercase" }} />
						</div>
					</div>
				</div>

				{/* ── Action bar ────────────────────────────────────────────────── */}
				<div style={{ display: "flex", justifyContent: "flex-end", gap: 12, marginTop: 4 }}>
					<button className="btn-ghost" onClick={handleCancel} disabled={loading}>
						Cancel
					</button>
					<button className="btn-primary" onClick={handleSubmit} disabled={loading}>
						{loading && <Spinner />}
						Submit Prechecking
					</button>
				</div>
			</div>
		</div>
	);
};

export default PrecheckingIndividuPage;