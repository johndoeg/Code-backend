import React, { useState, useEffect } from "react";
import api from "../../../../api/axiosInstance";
import OCRUploadSection from "../../../../contexts/OCRUploadSection";
import { MAX_FILE_LIMIT } from "../../../../constants/DefaultValue";
import { useNavigate } from "react-router-dom";

const fontLink = document.createElement("link");
fontLink.rel = "stylesheet";
fontLink.href =
	"https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap";
document.head.appendChild(fontLink);

interface CustomerData {
	idCardNo: string; name: string; placeOfBirth: string; dateOfBirth: string;
	gender: string; bloodType: string; address: string; rt: string; rw: string;
	subdistrict: string; district: string; city: string; province: string;
	religion: string; job: string; citizen: string; photo: string; signature: string;
}
type ConfidenceMap = Partial<Record<keyof CustomerData, string>>;
type VerifiedMap = Partial<Record<keyof CustomerData, string>>;
interface DukcapilVerification { checked: boolean; status: boolean | null; reason: string; }
const ver_UNCHECKED: DukcapilVerification = { checked: false, status: null, reason: "" };
interface MaritalOption { value: string; label: string; }
interface UploadedDoc { id: number; name: string; type: string; key: string; previewUrl?: string; view_url?: string | null; }

const EMPTY_CUSTOMER = (): CustomerData => ({
	idCardNo: "", name: "", placeOfBirth: "", dateOfBirth: "",
	gender: "", bloodType: "", address: "", rt: "", rw: "",
	subdistrict: "", district: "", city: "", province: "",
	religion: "", job: "", citizen: "", photo: "", signature: "",
});

const IMAGE_EXTS = new Set(["png", "jpg", "jpeg", "gif", "bmp", "heic", "heif", "tiff", "tif", "webp"]);

const OCR_DOC_TYPES = new Set(["cust-ktp", "cust-spouse-ktp", "cust-wna-spouse-ktp"]);

const matchToBit = (value?: string): number => (value === "MATCH" ? 1 : 0);

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

  .dukcapil-gate {
    border-radius: 12px; padding: 12px 16px; margin-bottom: 4px;
    font-size: .8rem; font-weight: 600; display: flex; align-items: center; gap: 8px;
  }
  .dukcapil-gate.pending { background: #FEF2F2; color: #B91C1C; border: 1.5px solid #FECACA; }
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

const PrecheckingIndividuPage: React.FC = () => {
	const navigate = useNavigate();

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
	const [custDukcapil, setCustDukcapil] = useState<DukcapilVerification>(ver_UNCHECKED);
	const [spouseDukcapil, setSpouseDukcapil] = useState<DukcapilVerification>(ver_UNCHECKED);
	const [wnaSpDukcapil, setWnaSpDukcapil] = useState<DukcapilVerification>(ver_UNCHECKED);

	const [docs, setDocs] = useState<UploadedDoc[]>([]);
	const [uploadingDocs, setUploadingDocs] = useState<Set<string>>(new Set());
	const [deletingDocs, setDeletingDocs] = useState<Set<number>>(new Set());
	const [preview, setPreview] = useState<PreviewState>(PREVIEW_CLOSED);
	const [previewLoadingId, setPreviewLoadingId] = useState<number | null>(null);

	const [loading, setLoading] = useState(false);
	const [errors, setErrors] = useState<Record<string, string>>({});

	useEffect(() => {
		const init = async () => {
			setLoading(true);
			try {
				const [aplessR, pidR, maritalR] = await Promise.all([
					api.post('/CAM/Prechecking/generate-apless', { customer_type: "PR" }),
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
			fd.append("organization_type", "PR");

			const res = await api.post('/CAM/Prechecking/upload-document', fd);

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
			const res = await api.get('/CAM/Prechecking/documents', {
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
		if (docType === "cust-ktp") return customer.idCardNo;
		if (docType === "cust-spouse-ktp") return spouse.idCardNo;
		if (docType === "cust-wna-spouse-ktp") return wnaSpouse.idCardNo;

		return "";
	};

	const _clearDataForDocType = (docType: string) => {
		if (docType === "cust-ktp") {
			setCustomer(EMPTY_CUSTOMER());
			setCustConf({});
			setCustVer({});
			setCustDukcapil(ver_UNCHECKED);
		} else if (docType === "cust-spouse-ktp") {
			setSpouse(EMPTY_CUSTOMER());
			setSpouseConf({});
			setSpouseVer({});
			setSpouseDukcapil(ver_UNCHECKED);
		} else if (docType === "cust-wna-spouse-ktp") {
			setWnaSpouse(EMPTY_CUSTOMER());
			setWnaSpConf({});
			setWnaSpVer({});
			setWnaSpDukcapil(ver_UNCHECKED);
		}
	};

	const handleDeleteDoc = async (docId: number) => {
		if (!window.confirm("Apakah Anda yakin ingin menghapus dokumen ini?")) return;
		setDeletingDocs((prev) => new Set(prev).add(docId));
		try {
			const doc = docs.find((d) => d.id === docId);
			if (doc?.previewUrl?.startsWith("blob:")) URL.revokeObjectURL(doc.previewUrl);

			const nik = doc ? _nikForDocType(doc.type) : "";

			const res = await api.post('/CAM/Prechecking/delete-document', {
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
			const res = await api.get('/CAM/Prechecking/view-document', {
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

	const handleCancel = async () => {
		try { await api.post('/CAM/Prechecking/cancel', { prechecking_id: precheckingId }); }
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

	const custDukcapilRequired = nationality === "WNI";
	const spouseDukcapilRequired = showSpouseOCR;
	const wnaSpDukcapilRequired = showWnaSpOCR;

	const dukcapilPending =
		(custDukcapilRequired && !custDukcapil.checked) ||
		(spouseDukcapilRequired && !spouseDukcapil.checked) ||
		(wnaSpDukcapilRequired && !wnaSpDukcapil.checked);

	const handleSubmit = async () => {
		const e: Record<string, string> = {};

		if (nationality === "WNI") {
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

		if (custDukcapilRequired && !custDukcapil.checked) {
			e.cust_dukcapil = "Please verify the Customer's KTP data with Dukcapil before submitting";
		}
		if (spouseDukcapilRequired && !spouseDukcapil.checked) {
			e.spouse_dukcapil = "Please verify the Spouse's KTP data with Dukcapil before submitting";
		}
		if (wnaSpDukcapilRequired && !wnaSpDukcapil.checked) {
			e.wna_spouse_dukcapil = "Please verify the WNA's Spouse KTP data with Dukcapil before submitting";
		}

		setErrors(e);
		if (Object.keys(e).length) {
			const dukcapilMsgs = [e.cust_dukcapil, e.spouse_dukcapil, e.wna_spouse_dukcapil].filter(Boolean) as string[];
			if (dukcapilMsgs.length) {
				alert(dukcapilMsgs.join("\n"));
			}
			return;
		}

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
				val_cust_rw: custConf.rt ?? "",
				val_cust_subdistrict: custConf.subdistrict ?? "", val_cust_district: custConf.district ?? "",
				val_cust_city: custConf.city ?? "", val_cust_province: custConf.province ?? "",
				val_cust_religion: custConf.religion ?? "", val_cust_job: custConf.job ?? "",

				cust_ver_verified: custDukcapil.checked ? 1 : 0,
				cust_ver_status: custDukcapil.status === null ? "" : (custDukcapil.status ? 1 : 0),
				cust_ver_reason: custDukcapil.reason ?? "",
				ver_cust_id_card_no: matchToBit(custVer.idCardNo), ver_cust_name: matchToBit(custVer.name),
				ver_cust_pob: matchToBit(custVer.placeOfBirth), ver_cust_dob: matchToBit(custVer.dateOfBirth),
				ver_cust_gender: matchToBit(custVer.gender), ver_cust_address: matchToBit(custVer.address),
				ver_cust_rt: matchToBit(custVer.rt), ver_cust_rw: matchToBit(custVer.rw),
				ver_cust_subdistrict: matchToBit(custVer.subdistrict), ver_cust_district: matchToBit(custVer.district),
				ver_cust_city: matchToBit(custVer.city), ver_cust_province: matchToBit(custVer.province),
				ver_cust_job: matchToBit(custVer.job),
				
				cust_spouse_id_card_no: spouse.idCardNo, cust_spouse_name: spouse.name,
				cust_spouse_pob: spouse.placeOfBirth, cust_spouse_dob: spouse.dateOfBirth,
				cust_spouse_gender: spouse.gender, cust_spouse_blood_type: spouse.bloodType,
				cust_spouse_address: spouse.address, cust_spouse_rt: spouse.rt,
				cust_spouse_rw: spouse.rw, cust_spouse_subdistrict: spouse.subdistrict,
				cust_spouse_district: spouse.district, cust_spouse_city: spouse.city,
				cust_spouse_province: spouse.province, cust_spouse_religion: spouse.religion,
				cust_spouse_job: spouse.job, cust_spouse_citizen: spouse.citizen,
				cust_spouse_photo_hidden: spouse.photo, cust_spouse_signature_hidden: spouse.signature,
				
				val_cust_spouse_id_card_no: spouseConf.idCardNo ?? "", val_cust_spouse_name: spouseConf.name ?? "",
				val_cust_spouse_pob: spouseConf.placeOfBirth ?? "", val_cust_spouse_dob: spouseConf.dateOfBirth ?? "",
				val_cust_spouse_gender: spouseConf.gender ?? "", val_cust_spouse_address: spouseConf.address ?? "",
				val_cust_spouse_rt: spouseConf.rt ?? "", val_cust_spouse_rw: spouseConf.rt ?? "",
				val_cust_spouse_subdistrict: spouseConf.subdistrict ?? "",
				val_cust_spouse_district: spouseConf.district ?? "", val_cust_spouse_city: spouseConf.city ?? "",
				val_cust_spouse_province: spouseConf.province ?? "", val_cust_spouse_job: spouseConf.job ?? "",

				cust_spouse_ver_verified: spouseDukcapil.checked ? 1 : 0,
				cust_spouse_ver_status: spouseDukcapil.status === null ? "" : (spouseDukcapil.status ? 1 : 0),
				cust_spouse_ver_reason: spouseDukcapil.reason ?? "",
				ver_cust_spouse_id_card_no: matchToBit(spouseVer.idCardNo), ver_cust_spouse_name: matchToBit(spouseVer.name),
				ver_cust_spouse_pob: matchToBit(spouseVer.placeOfBirth), ver_cust_spouse_dob: matchToBit(spouseVer.dateOfBirth),
				ver_cust_spouse_gender: matchToBit(spouseVer.gender), ver_cust_spouse_address: matchToBit(spouseVer.address),
				ver_cust_spouse_rt: matchToBit(spouseVer.rt), ver_cust_spouse_rw: matchToBit(spouseVer.rw),
				ver_cust_spouse_subdistrict: matchToBit(spouseVer.subdistrict), ver_cust_spouse_district: matchToBit(spouseVer.district),
				ver_cust_spouse_city: matchToBit(spouseVer.city), ver_cust_spouse_province: matchToBit(spouseVer.province),
				ver_cust_spouse_job: matchToBit(spouseVer.job),
				
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
				
				val_cust_wna_spouse_id_card_no: wnaSpConf.idCardNo ?? "", val_cust_wna_spouse_name: wnaSpConf.name ?? "",
				val_cust_wna_spouse_pob: wnaSpConf.placeOfBirth ?? "", val_cust_wna_spouse_dob: wnaSpConf.dateOfBirth ?? "",
				val_cust_wna_spouse_gender: wnaSpConf.gender ?? "", val_cust_wna_spouse_address: wnaSpConf.address ?? "",
				val_cust_wna_spouse_rt: wnaSpConf.rt ?? "", val_cust_wna_spouse_rw: wnaSpConf.rt ?? "",
				val_cust_wna_spouse_subdistrict: wnaSpConf.subdistrict ?? "",
				val_cust_wna_spouse_district: wnaSpConf.district ?? "", val_cust_wna_spouse_city: wnaSpConf.city ?? "",
				val_cust_wna_spouse_province: wnaSpConf.province ?? "", val_cust_wna_spouse_job: wnaSpConf.job ?? "",

				cust_wna_spouse_ver_verified: wnaSpDukcapil.checked ? 1 : 0,
				cust_wna_spouse_ver_status: wnaSpDukcapil.status === null ? "" : (wnaSpDukcapil.status ? 1 : 0),
				cust_wna_spouse_ver_reason: wnaSpDukcapil.reason ?? "",
				ver_cust_wna_spouse_id_card_no: matchToBit(wnaSpVer.idCardNo), ver_cust_wna_spouse_name: matchToBit(wnaSpVer.name),
				ver_cust_wna_spouse_pob: matchToBit(wnaSpVer.placeOfBirth), ver_cust_wna_spouse_dob: matchToBit(wnaSpVer.dateOfBirth),
				ver_cust_wna_spouse_gender: matchToBit(wnaSpVer.gender), ver_cust_wna_spouse_address: matchToBit(wnaSpVer.address),
				ver_cust_wna_spouse_rt: matchToBit(wnaSpVer.rt), ver_cust_wna_spouse_rw: matchToBit(wnaSpVer.rw),
				ver_cust_wna_spouse_subdistrict: matchToBit(wnaSpVer.subdistrict), ver_cust_wna_spouse_district: matchToBit(wnaSpVer.district),
				ver_cust_wna_spouse_city: matchToBit(wnaSpVer.city), ver_cust_wna_spouse_province: matchToBit(wnaSpVer.province),
				ver_cust_wna_spouse_job: matchToBit(wnaSpVer.job),
			};

			const res = await api.post('/CAM/Prechecking/submit', payload);
			if (res.data?.success) {
				alert("Prechecking submitted successfully!");
				navigate("/CAM/Prechecking/Onhand");
			} else {
				alert(res.data?.message ?? "Submission failed");
			}
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

			<div className="page-wrap">
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

				<div className="card">
					<div className="section-label"><span className="dot" />General Information<hr /></div>
					<div style={{ marginBottom: 24 }}>
						<div className="form-grid" style={{ marginBottom: 14 }}>
							<div className="form-field">
								<label className="form-label">Checking For <span className="req">*</span></label>
								<div className="select-wrap"><select disabled value="C" className="form-select is-disabled"><option value="C">Customer</option></select></div>
							</div>
							<div className="form-field">
								<label className="form-label">Type <span className="req">*</span></label>
								<div className="select-wrap"><select disabled value="PR" className="form-select is-disabled"><option value="PR">Individu</option></select></div>
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
							<div className="section-label"><span className="dot" />Customer KTP (OCR)<hr /></div>
							<OCRUploadSection
								apless={apless}
								precheckingId={precheckingId}
								ocrFor="customer"
								docType="cust-ktp"
								title="Customer · WNI"
								nationality="WNI"
								maritalStatus={maritalOptions.find((o) => o.value === marital)?.label}
								onDataChange={(data, conf, verified, verification) => {
									setCustomer(data); setCustConf(conf);
									setCustVer(verified); setCustDukcapil(verification);
								}}
							/>
						</>
					)}

					{showWnaSection && (
						<>
							<div className="section-label"><span className="dot" />Customer WNA Information<hr /></div>
							<div className="sub-section blue" style={{ marginBottom: 20 }}>
								<div className="sub-section-title">🌐 Customer WNA</div>
								<div className="form-grid">
									<div className="form-field">
										<label className="form-label">Nama <span className="req">*</span></label>
										<input value={wnaName} onChange={(e) => setWnaName(e.target.value.toUpperCase())} className={`form-input${errors.wna_name ? " err" : ""}`} style={{ textTransform: "uppercase" }} />
										{errors.wna_name && <p className="field-err">{errors.wna_name}</p>}
									</div>
									<div className="form-field">
										<label className="form-label">ID Card No. <span className="req">*</span></label>
										<input value={wnaIdCard} onChange={(e) => setWnaIdCard(e.target.value)} className={`form-input${errors.wna_idcard ? " err" : ""}`} />
										{errors.wna_idcard && <p className="field-err">{errors.wna_idcard}</p>}
									</div>
									<div className="form-field full">
										<label className="form-label">ID Card (KITAS/Passport)</label>
										<FileInput label="Upload KITAS / Passport" onFileChange={(f) => _uploadDoc(f, "cust-kitas")} uploading={uploadingDocs.has("cust-kitas")} />
										<DocList docs={docsOf("cust-kitas")} onDelete={handleDeleteDoc} deletingDocs={deletingDocs} onPreview={handlePreview} previewLoadingId={previewLoadingId} />
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
								ocrFor="spouse"
								docType="cust-spouse-ktp"
								title="Spouse · WNI"
								onDataChange={(data, conf, verified, verification) => {
									setSpouse(data); setSpouseConf(conf);
									setSpouseVer(verified); setSpouseDukcapil(verification);
								}}
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
										<FileInput label="Upload Spouse KITAS" onFileChange={(f) => _uploadDoc(f, "cust-spouse-kitas")} uploading={uploadingDocs.has("cust-spouse-kitas")} />
										<DocList docs={docsOf("cust-spouse-kitas")} onDelete={handleDeleteDoc} deletingDocs={deletingDocs} onPreview={handlePreview} previewLoadingId={previewLoadingId} />
									</div>
								</div>
							</div>
						</>
					)}

					{showWnaSpOCR && (
						<>
							<div className="section-label"><span className="dot" />Spouse of WNA Customer (WNI KTP)<hr /></div>
							<OCRUploadSection
								apless={apless}
								precheckingId={precheckingId}
								ocrFor="wna_spouse"
								docType="cust-wna-spouse-ktp"
								title="Spouse of WNA · WNI KTP"
								onDataChange={(data, conf, verified, verification) => {
									setWnaSpouse(data); setWnaSpConf(conf);
									setWnaSpVer(verified); setWnaSpDukcapil(verification);
								}}
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
										<FileInput label="Upload Spouse KITAS" onFileChange={(f) => _uploadDoc(f, "cust-spouse-kitas")} uploading={uploadingDocs.has("cust-spouse-kitas")} />
										<DocList docs={docsOf("cust-spouse-kitas")} onDelete={handleDeleteDoc} deletingDocs={deletingDocs} onPreview={handlePreview} previewLoadingId={previewLoadingId} />
									</div>
								</div>
							</div>
						</>
					)}

					<div className="section-label"><span className="dot" />Supporting Documents<hr /></div>
					<div className="form-grid" style={{ marginBottom: 24 }}>
						{[
							{ label: "KK (Kartu Keluarga)", type: "cust-kk" },
							{ label: "NPWP", type: "cust-npwp" },
							{ label: "Akta Cerai / Akta Kematian", type: "cust-marriage-or-death-statement" },
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

				{dukcapilPending && (
					<div className="dukcapil-gate pending">
						<svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 9v4m0 4h.01M10.29 3.86l-8.18 14.18A2 2 0 004.02 21h15.96a2 2 0 001.91-2.96L13.71 3.86a2 2 0 00-3.42 0z" />
						</svg>
						Submit is locked until every KTP shown above has been checked with "Verify Dukcapil" and a result is displayed.
					</div>
				)}

				<div style={{ display: "flex", justifyContent: "flex-end", gap: 12, marginTop: 4 }}>
					<button className="btn-ghost" onClick={handleCancel} disabled={loading}>Cancel</button>
					<button className="btn-primary" onClick={handleSubmit} disabled={loading || dukcapilPending} title={dukcapilPending ? "Complete Dukcapil verification for all KTP sections first" : undefined}>
						{loading && <Spinner />}
						Submit Prechecking
					</button>
				</div>

			</div>
		</div>
	);
};

export default PrecheckingIndividuPage;