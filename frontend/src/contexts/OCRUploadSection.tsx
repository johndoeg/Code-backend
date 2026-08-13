import React, { useState, useRef, useCallback, useEffect } from "react";
import api from '../api/axiosInstance';
export interface CustomerData {
	idCardNo: string;
	name: string;
	placeOfBirth: string;
	dateOfBirth: string;
	gender: string;
	bloodType: string;
	address: string;
	rt: string;
	rw: string;
	subdistrict: string;
	district: string;
	city: string;
	province: string;
	religion: string;
	job: string;
	citizen: string;
	photo: string;
	signature: string;
}

export type ConfidenceMap = Partial<Record<keyof CustomerData, string>>;
export type VerifiedMap = Partial<Record<keyof CustomerData, string>>;

export interface DukcapilVerification {
	checked: boolean;
	status: boolean | null;
	reason: string;
}
const DUKCAPIL_UNCHECKED: DukcapilVerification = { checked: false, status: null, reason: "" };

interface UploadedDoc {
	id: number;
	name: string;
	type: string;
	key: string;
	previewUrl?: string;
	view_url?: string | null;
}

export type OcrFor =
	| "customer" | "spouse" | "wna_spouse"
	| "guarantor" | "guarantor_spouse" | "guarantor_wna_spouse"
	| "corporate" | "corporate_guarantor";

interface Props {
	apless: string;
	precheckingId: string;
	ocrFor: OcrFor;
	docType: string;
	title: string;
	nationality?: "WNI" | "WNA";
	lesseeType?: string;
	maritalStatus?: string;
	onDataChange?: (data: CustomerData, conf: ConfidenceMap, verified: VerifiedMap, verification: DukcapilVerification) => void;
}

const EMPTY_DATA = (): CustomerData => ({
	idCardNo: "", name: "", placeOfBirth: "", dateOfBirth: "",
	gender: "", bloodType: "", address: "", rt: "", rw: "",
	subdistrict: "", district: "", city: "", province: "",
	religion: "", job: "", citizen: "", photo: "", signature: "",
});

const IMAGE_EXTS = new Set(["png", "jpg", "jpeg", "gif", "bmp", "heic", "heif", "tiff", "tif", "webp"]);

const _normCitizen = (value?: string): "WNI" | "WNA" => {
	const v = (value ?? "").trim().toUpperCase();
	if (v === "WNA" || v === "ASING" || v.startsWith("FOREIGN")) return "WNA";
	return "WNI";
};

const API_OCR = "/Prechecking/OCR/scanOCRCustomer";
const API_BASE = "/Prechecking/OCR";

const ROUTES: Record<OcrFor, {
	upload: string; list: string; del: string; view: string;
	custType: string; orgType: string; ocrForCode: string;
}> = {
	customer: { upload: "/upload-document", list: "/documents", del: "/delete-document", view: "/view-document", custType: "PR", orgType: "PR", ocrForCode: "C" },
	spouse: { upload: "/upload-document", list: "/documents", del: "/delete-document", view: "/view-document", custType: "PR", orgType: "PR", ocrForCode: "S" },
	wna_spouse: { upload: "/upload-document", list: "/documents", del: "/delete-document", view: "/view-document", custType: "PR", orgType: "PR", ocrForCode: "S" },
	guarantor: { upload: "/upload-document", list: "/documents", del: "/delete-document", view: "/view-document", custType: "PR", orgType: "GUARNPR", ocrForCode: "G" },
	guarantor_spouse: { upload: "/upload-document", list: "/documents", del: "/delete-document", view: "/view-document", custType: "PR", orgType: "GUARNPR", ocrForCode: "S" },
	guarantor_wna_spouse: { upload: "/upload-document", list: "/documents", del: "/delete-document", view: "/view-document", custType: "PR", orgType: "GUARNPR", ocrForCode: "S" },
	corporate: { upload: "/upload-document", list: "/documents", del: "/delete-document", view: "/view-document", custType: "PT", orgType: "PT", ocrForCode: "P" },
	corporate_guarantor: { upload: "/upload-document", list: "/documents", del: "/delete-document", view: "/view-document", custType: "PT", orgType: "GUARNPT", ocrForCode: "G" },
};

const Spinner: React.FC<{ dark?: boolean; size?: number }> = ({ dark, size = 16 }) => (
	<span
		style={{
			display: "inline-block",
			width: size, height: size,
			borderRadius: "50%",
			border: `2.5px solid ${dark ? "rgba(27,58,122,.15)" : "rgba(255,255,255,.3)"}`,
			borderTopColor: dark ? "#1B3A7A" : "#fff",
			animation: "ocr-spin .7s linear infinite",
			flexShrink: 0,
		}}
	/>
);

const ConfBadge: React.FC<{ value?: string }> = ({ value }) => {
	if (!value) return (
		<span style={badge("#F1F5F9", "#94A3B8", "#E2E8F0")}>—</span>
	);
	const n = parseInt(value.replace("%", ""), 10);
	const [bg, color, border] =
		n >= 90 ? ["#DCFCE7", "#15803D", "#BBF7D0"] :
			n >= 70 ? ["#FEF9C3", "#A16207", "#FDE68A"] :
				["#FEE2E2", "#B91C1C", "#FECACA"];
	return <span style={badge(bg, color, border)}>{value}</span>;
};

const VerBadge: React.FC<{ value?: string }> = ({ value }) => {
	if (!value) return <span style={badge("#F8FAFF", "#94A3B8", "#E2E8F0")}>—</span>;
	if (value === "NOT MATCH") return <span style={badge("#FEE2E2", "#B91C1C", "#FECACA")}>NOT MATCH</span>;
	return <span style={badge("#ECFDF5", "#065F46", "#A7F3D0")}>{value}</span>;
};

function badge(bg: string, color: string, border: string): React.CSSProperties {
	return {
		display: "inline-block", padding: "4px 10px", borderRadius: 20,
		fontSize: ".72rem", fontWeight: 700, fontFamily: "var(--mono, monospace)",
		background: bg, color, border: `1px solid ${border}`,
		textAlign: "center", width: "100%",
	};
}

interface RowProps {
	label: string;
	value: string;
	confidence?: string;
	verified?: string;
	required?: boolean;
	textarea?: boolean;
	numeric?: boolean;
	maxLen?: number;
	onChange: (v: string) => void;
}

const OcrRow: React.FC<RowProps> = ({
	label, value, confidence, verified, required,
	textarea, numeric, maxLen, onChange,
}) => {
	const handle = (raw: string) => {
		if (numeric) {
			const d = raw.replace(/\D/g, "");
			onChange(maxLen ? d.slice(0, maxLen) : d);
		} else {
			onChange(textarea ? raw : raw.toUpperCase());
		}
	};

	const inputStyle: React.CSSProperties = {
		width: "100%", padding: "7px 12px", fontSize: ".82rem",
		fontFamily: "var(--font, 'Plus Jakarta Sans', sans-serif)",
		border: "1.5px solid var(--border, #DDE3F0)", borderRadius: 8,
		color: "var(--ink, #0F1D3C)", background: "#fff", outline: "none",
		transition: "border-color .18s",
		textTransform: numeric ? "none" : "uppercase",
		resize: textarea ? "vertical" : undefined,
	};

	return (
		<tr style={{ borderBottom: "1px solid #F0F3FA" }}>
			<td style={{ padding: "10px 14px", whiteSpace: "nowrap", width: "22%", verticalAlign: "middle" }}>
				<span style={{ fontSize: ".8rem", fontWeight: 600, color: "var(--ink, #0F1D3C)" }}>
					{label}{required && <span style={{ color: "#EF4444", marginLeft: 2 }}>*</span>}
				</span>
			</td>
			<td style={{ padding: "10px 14px", width: "38%", verticalAlign: "middle" }}>
				{textarea ? (
					<textarea
						value={value}
						onChange={(e) => handle(e.target.value)}
						rows={2} maxLength={250}
						style={{ ...inputStyle, minHeight: 56 }}
					/>
				) : (
					<input
						type="text"
						inputMode={numeric ? "numeric" : "text"}
						value={value}
						onChange={(e) => handle(e.target.value)}
						maxLength={maxLen}
						style={inputStyle}
					/>
				)}
			</td>
			<td style={{ padding: "10px 14px", width: "20%", textAlign: "center", verticalAlign: "middle" }}>
				<ConfBadge value={confidence} />
			</td>
			<td style={{ padding: "10px 14px", width: "20%", textAlign: "center", verticalAlign: "middle" }}>
				<VerBadge value={verified} />
			</td>
		</tr>
	);
};

const OCRUploadSection: React.FC<Props> = ({
	apless,
	precheckingId,
	ocrFor,
	docType,
	title,
	nationality = "WNI",
	lesseeType,
	maritalStatus,
	onDataChange,
}) => {
	const route = ROUTES[ocrFor];

	const [data, setData] = useState<CustomerData>(EMPTY_DATA());
	const [conf, setConf] = useState<ConfidenceMap>({});
	const [ver, setVer] = useState<VerifiedMap>({});
	const [docs, setDocs] = useState<UploadedDoc[]>([]);
	const [scanning, setScanning] = useState(false);
	const [verifying, setVerifying] = useState(false);
	const [uploading, setUploading] = useState(false);
	const [deleting, setDeleting] = useState<Set<number>>(new Set());
	const [showVerify, setShowVerify] = useState(false);
	
	const [dukcapilResult, setDukcapilResult] = useState<DukcapilVerification>(DUKCAPIL_UNCHECKED);
	const [previewDoc, setPreviewDoc] = useState<UploadedDoc | null>(null);
	const [previewLoadingId, setPreviewLoadingId] = useState<number | null>(null);

	const fileRef = useRef<HTMLInputElement>(null);

	useEffect(() => {
		onDataChange?.(data, conf, ver, dukcapilResult);
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [data, conf, ver, dukcapilResult]);

	const refreshDocs = useCallback(async (newPreviewUrl?: string, newDocName?: string) => {
		if (!apless || !precheckingId) return;
		try {
			const res = await api.get(`${API_BASE}${route.list}`, {
				params: { apless, prechecking_id: precheckingId },
			});
			const fetched: UploadedDoc[] = (res.data ?? []).filter((d: UploadedDoc) => d.type === docType);
			setDocs((prev) => {
				const previewMap = new Map(prev.map((d) => [d.id, d.previewUrl]));
				return fetched.map((d) => ({
					...d,
					previewUrl:
						newDocName && d.name === newDocName
							? newPreviewUrl
							: previewMap.get(d.id),
				}));
			});
		} catch (e) {
			console.error("refreshDocs error", e);
		}
	}, [apless, precheckingId, route.list, docType]);

	const uploadDoc = useCallback(async (file: File, type: string): Promise<string | undefined> => {
		const ALLOWED = [".png", ".jpg", ".jpeg", ".pdf", ".tiff", ".tif", ".bmp", ".gif", ".heic", ".heif", ".xlsx", ".docx"];
		const ext = "." + file.name.split(".").pop()!.toLowerCase();
		if (!ALLOWED.includes(ext)) { alert("Format file tidak didukung."); return; }
		if (ext !== ".pdf" && file.size > 2 * 1024 * 1024) { alert("Ukuran file melebihi 2 MB."); return; }

		let localPreview: string | undefined;
		const extClean = ext.replace(".", "");
		if (IMAGE_EXTS.has(extClean) || ext === ".pdf") {
			localPreview = URL.createObjectURL(file);
		}

		setUploading(true);
		try {
			const fd = new FormData();
			fd.append("file", file);
			fd.append("apless", apless);
			fd.append("prechecking_id", precheckingId);
			fd.append("document_type", type);
			fd.append("cust_type", route.custType);
			fd.append("organization_type", route.orgType);
			if (ocrFor === "corporate" || ocrFor === "corporate_guarantor") {
				fd.append("lessee_type", lesseeType ?? "");
			}

			const res = await api.post(`${API_BASE}${route.upload}`, fd);

			if (!res.data?.success) {
				alert(res.data?.message ?? "Upload gagal.");
				if (localPreview) URL.revokeObjectURL(localPreview);
				return;
			}

			await refreshDocs(localPreview, res.data.document_name);
			return res.data.document_name;
		} catch (e: any) {
			if (localPreview) URL.revokeObjectURL(localPreview);
			alert(e.response?.data?.message ?? "Upload gagal.");
		} finally {
			setUploading(false);
		}
	}, [apless, precheckingId, refreshDocs, route, ocrFor, lesseeType]);

	const handleFileChange = useCallback(async (file: File) => {
		if (file.size > 2 * 1024 * 1024) { alert("File size exceeds 2 MB."); return; }
		setScanning(true);
		try {

			const qFD = new FormData();
			qFD.append("image", file);
			qFD.append("param", "check_qualities");
			qFD.append("prechecking_id", precheckingId);

			const qRes = await api.post(API_OCR, qFD);
			const qData = qRes.data;
			if (
				qData.status !== "SUCCESS" ||
				qData.qualities?.blur?.value === true ||
				qData.qualities?.document?.value !== "ktp"
			) {
				alert(qData.reason || "Kualitas dokumen tidak memadai. Gunakan foto KTP yang lebih jelas.");
				return;
			}

			const oFD = new FormData();
			oFD.append("image", file);
			oFD.append("param", "ocr_customer");
			oFD.append("apless", apless);
			oFD.append("customer_type", route.custType);
			oFD.append("prechecking_id", precheckingId);
			oFD.append("check_for", "C");
			oFD.append("repeat_order", "0");
			oFD.append("ocr_for", route.ocrForCode);

			const oRes = await api.post(API_OCR, oFD);
			const r = oRes.data;
			if (r.status !== "SUCCESS" || !r.read) { alert(r.reason || "OCR gagal."); return; }

			const read = r.read ?? {};
			const images = r.images ?? {};
			const [rtVal, rwVal] = (read.rtRw?.value ?? "/").split("/");

			const mapped: CustomerData = {
				idCardNo: read.nik?.value ?? "",
				name: read.nama?.value ?? "",
				placeOfBirth: read.tempatLahir?.value ?? "",
				dateOfBirth: read.tanggalLahir?.value ?? "",
				gender: read.jenisKelamin?.value ?? "",
				bloodType: read.golonganDarah?.value ?? "",
				address: read.alamat?.value ?? "",
				rt: (rtVal ?? "").trim(),
				rw: (rwVal ?? "").trim(),
				subdistrict: read.kelurahanDesa?.value ?? "",
				district: read.kecamatan?.value ?? "",
				city: read.kotaKabupaten?.value ?? "",
				province: read.provinsi?.value ?? "",
				religion: read.agama?.value ?? "",
				job: read.pekerjaan?.value ?? "",
				citizen: _normCitizen(read.kewarganegaraan?.value),
				photo: images.photo ?? "",
				signature: images.sign ?? "",
			};

			const newConf: ConfidenceMap = {};
			const confFields: [keyof ConfidenceMap, string][] = [
				["idCardNo", "nik"], ["name", "nama"], ["placeOfBirth", "tempatLahir"],
				["dateOfBirth", "tanggalLahir"], ["gender", "jenisKelamin"],
				["bloodType", "golonganDarah"], ["address", "alamat"], ["rt", "rtRw"],
				["subdistrict", "kelurahanDesa"], ["district", "kecamatan"],
				["city", "kotaKabupaten"], ["province", "provinsi"],
				["religion", "agama"], ["job", "pekerjaan"],
			];
			for (const [k, src] of confFields) {
				if (read[src]?.confidence != null) newConf[k] = `${read[src].confidence}%`;
			}

			setData(mapped);
			setConf(newConf);
			setVer({});
			setDukcapilResult(DUKCAPIL_UNCHECKED);
			setShowVerify(true);

			await uploadDoc(file, docType);

		} catch (e: any) {
			console.error("OCR error", e);
			alert(e.response?.data?.reason ?? "OCR processing failed.");
		} finally {
			setScanning(false);
		}
	}, [apless, precheckingId, ocrFor, docType, nationality, uploadDoc, route.custType, route.ocrForCode]);

	const handleVerify = useCallback(async () => {
		setVerifying(true);
		try {
			const fd = new FormData();
			const fields: [string, string][] = [
				["param", "check_data_duckapil"], ["prechecking_id", precheckingId],
				["nik", data.idCardNo], ["name", data.name],
				["place_of_birth", data.placeOfBirth], ["date_of_birth", data.dateOfBirth],
				["gender", data.gender], ["address", data.address],
				["rt", data.rt], ["rw", data.rw],
				["subdistrict", data.subdistrict], ["district", data.district],
				["city", data.city], ["province", data.province], ["job_type", data.job],
			];
			if (maritalStatus) fields.push(["marital_status", maritalStatus]);
			for (const [k, v] of fields) fd.append(k, v);

			const res = await api.post(API_OCR, fd);
			const body = res.data ?? {};
			const result = body.result ?? {};
			const toLabel = (v: unknown): string =>
				v === true ? "MATCH" : v === false ? "NOT MATCH" : "";

			setVer({
				idCardNo: toLabel(result.nik),
				name: toLabel(result.name),
				placeOfBirth: toLabel(result.place_of_birth),
				dateOfBirth: toLabel(result.date_of_birth),
				gender: toLabel(result.gender),
				address: toLabel(result.address),
				rt: toLabel(result.rt),
				rw: toLabel(result.rw),
				subdistrict: toLabel(result.subdistrict),
				district: toLabel(result.district),
				city: toLabel(result.city),
				province: toLabel(result.province),
				job: toLabel(result.job_type),
			});

			setDukcapilResult({
				checked: true,
				status: typeof body.verification_status === "boolean" ? body.verification_status : false,
				reason: body.reason ?? "",
			});
		} catch {
			alert("Verification failed. Please try again.");
			setDukcapilResult(DUKCAPIL_UNCHECKED);
		}
		finally { setVerifying(false); }
	}, [data, precheckingId, maritalStatus]);

	const handlePreviewClick = useCallback(async (doc: UploadedDoc) => {
		if (doc.previewUrl) { setPreviewDoc(doc); return; }
		if (doc.view_url) { setPreviewDoc({ ...doc, previewUrl: doc.view_url }); return; }
		setPreviewLoadingId(doc.id);
		try {
			const res = await api.get(`${API_BASE}${route.view}`, {
				params: { customer_document_id: doc.id },
			});
			if (res.data?.success && res.data?.view_url) {
				setPreviewDoc({ ...doc, previewUrl: res.data.view_url });
			} else {
				alert(res.data?.message ?? "Dokumen tidak dapat ditampilkan.");
			}
		} catch (e: any) {
			alert(e.response?.data?.message ?? "Gagal memuat pratinjau dokumen.");
		} finally {
			setPreviewLoadingId(null);
		}
	}, [route.view]);

	const handleDeleteDoc = useCallback(async (docId: number) => {
		if (!window.confirm("Hapus dokumen ini?")) return;
		setDeleting((prev) => new Set(prev).add(docId));
		try {
			const doc = docs.find((d) => d.id === docId);
			if (doc?.previewUrl?.startsWith("blob:")) URL.revokeObjectURL(doc.previewUrl);

			const res = await api.post(`${API_BASE}${route.del}`, {
				customer_document_id: docId,
				prechecking_id: precheckingId,
				nik: data.idCardNo,
			});
			if (!res.data?.success) { alert(res.data?.message ?? "Hapus gagal."); return; }
			await refreshDocs();
		} catch { alert("Hapus gagal."); }
		finally {
			setDeleting((prev) => { const n = new Set(prev); n.delete(docId); return n; });
		}
	}, [docs, precheckingId, refreshDocs, route.del, data.idCardNo]);

	const upd = (field: keyof CustomerData) => (v: string) => {
		setData((prev) => ({ ...prev, [field]: v }));
		setDukcapilResult(DUKCAPIL_UNCHECKED);
	};

	return (
		<>
			<style>{`@keyframes ocr-spin { to { transform: rotate(360deg); } }`}</style>

			{(scanning || verifying) && (
				<div style={{
					position: "fixed", inset: 0, background: "rgba(15,29,60,.55)",
					display: "flex", alignItems: "center", justifyContent: "center",
					zIndex: 999, backdropFilter: "blur(4px)",
				}}>
					<div style={{
						background: "#fff", borderRadius: 20, padding: "40px 48px",
						textAlign: "center", boxShadow: "0 24px 80px rgba(15,29,60,.25)",
					}}>
						<Spinner size={44} />
						<p style={{ fontSize: "1rem", fontWeight: 700, color: "#0F1D3C", marginTop: 16 }}>
							{scanning ? "Processing Document…" : "Verifying with Dukcapil…"}
						</p>
						<p style={{ fontSize: ".82rem", color: "#64748B", marginTop: 4 }}>
							{scanning ? "Running OCR analysis, please wait" : "Checking identity data, please wait"}
						</p>
					</div>
				</div>
			)}

			{previewDoc && (
				<div
					style={{
						position: "fixed", inset: 0, background: "rgba(10,18,40,.8)",
						display: "flex", alignItems: "center", justifyContent: "center",
						zIndex: 300, padding: 24, backdropFilter: "blur(6px)",
					}}
					onClick={() => setPreviewDoc(null)}
				>
					<div
						style={{
							background: "#fff", borderRadius: 20, overflow: "hidden",
							boxShadow: "0 32px 96px rgba(10,18,40,.4)",
							display: "flex", flexDirection: "column",
							width: "min(90vw,800px)", maxHeight: "90vh",
						}}
						onClick={(e) => e.stopPropagation()}
					>
						<div style={{
							background: "linear-gradient(135deg,#0F1D3C,#2D5BE3)",
							padding: "14px 20px", display: "flex", alignItems: "center", gap: 10,
						}}>
							<span style={{
								color: "#fff", fontSize: ".875rem", fontWeight: 700, flex: 1,
								overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
							}}>{previewDoc.name}</span>
							<button
								onClick={() => setPreviewDoc(null)}
								style={{
									background: "rgba(255,255,255,.15)", border: "1px solid rgba(255,255,255,.25)",
									borderRadius: 8, width: 32, height: 32, color: "#fff",
									cursor: "pointer", fontSize: "1.2rem", display: "flex",
									alignItems: "center", justifyContent: "center",
								}}
							>×</button>
						</div>
						<div style={{
							overflow: "auto", display: "flex", alignItems: "center",
							justifyContent: "center", padding: 24, background: "#F2F5FB",
							flex: 1, minHeight: 0,
						}}>
							{previewDoc.previewUrl && IMAGE_EXTS.has(previewDoc.name.split(".").pop()?.toLowerCase() ?? "") ? (
								<img
									src={previewDoc.previewUrl} alt={previewDoc.name}
									style={{
										maxWidth: "100%", maxHeight: "65vh", objectFit: "contain",
										borderRadius: 10, boxShadow: "0 4px 24px rgba(10,18,40,.18)",
									}}
								/>
							) : previewDoc.previewUrl && previewDoc.name.toLowerCase().endsWith(".pdf") ? (
								<iframe
									src={previewDoc.previewUrl} title={previewDoc.name}
									style={{ width: "100%", height: "60vh", border: "none", borderRadius: 10 }}
								/>
							) : (
								<p style={{ color: "#64748B" }}>Preview tidak tersedia</p>
							)}
						</div>
						<div style={{
							padding: "12px 20px", borderTop: "1px solid #DDE3F0",
							display: "flex", justifyContent: "flex-end", background: "#fff",
						}}>
							<button
								onClick={() => setPreviewDoc(null)}
								style={{
									background: "none", border: "1.5px solid #DDE3F0", borderRadius: 10,
									padding: "9px 20px", fontSize: ".82rem", fontWeight: 600,
									cursor: "pointer", color: "#0F1D3C",
								}}
							>Tutup</button>
						</div>
					</div>
				</div>
			)}

			<div style={{
				border: "1.5px solid #DDE3F0", borderRadius: 16, overflow: "hidden",
				marginBottom: 20, boxShadow: "0 2px 12px rgba(15,29,60,.05)",
			}}>
				<div style={{
					background: "linear-gradient(135deg, #1B3A7A, #2D5BE3)",
					padding: "14px 20px", display: "flex", justifyContent: "space-between", alignItems: "center",
				}}>
					<span style={{ color: "#fff", fontSize: ".875rem", fontWeight: 700 }}>{title}</span>
					<div style={{ display: "flex", alignItems: "center", gap: 8 }}>
						<label style={{
							background: "rgba(255,255,255,.15)", border: "1px solid rgba(255,255,255,.3)",
							borderRadius: 8, padding: "6px 14px", color: "#fff",
							fontSize: ".78rem", fontWeight: 600, fontFamily: "inherit",
							cursor: scanning || uploading ? "not-allowed" : "pointer",
							display: "flex", alignItems: "center", gap: 6,
							opacity: scanning || uploading ? 0.6 : 1,
						}}>
							{scanning || uploading
								? <Spinner size={14} />
								: (
									<svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
											d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
									</svg>
								)
							}
							{scanning ? "Scanning…" : uploading ? "Uploading…" : "Upload KTP for OCR"}
							<input
								ref={fileRef}
								type="file"
								accept=".png,.jpg,.jpeg,.pdf,.tiff"
								style={{ display: "none" }}
								disabled={scanning || uploading}
								onChange={(e) => {
									const f = e.target.files?.[0];
									if (f) { handleFileChange(f); e.target.value = ""; }
								}}
							/>
						</label>
					</div>
				</div>

				{showVerify && (
					<div style={{
						padding: "9px 20px",
						fontSize: ".76rem",
						fontWeight: 700,
						display: "flex",
						alignItems: "center",
						gap: 7,
						background: !dukcapilResult.checked ? "#FEF2F2" : dukcapilResult.status ? "#ECFDF5" : "#FFFBEB",
						color: !dukcapilResult.checked ? "#B91C1C" : dukcapilResult.status ? "#065F46" : "#92400E",
						borderBottom: "1px solid #DDE3F0",
					}}>
						{!dukcapilResult.checked ? (
							<>
								<svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 9v4m0 4h.01M10.29 3.86l-8.18 14.18A2 2 0 004.02 21h15.96a2 2 0 001.91-2.96L13.71 3.86a2 2 0 00-3.42 0z" />
								</svg>
								Click "Verify Dukcapil" below — required before this form can be submitted
							</>
						) : dukcapilResult.status ? (
							<>
								<svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
								</svg>
								Verified — data matches Dukcapil{dukcapilResult.reason ? ` (${dukcapilResult.reason})` : ""}
							</>
						) : (
							<>
								<svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 8v4m0 4h.01M12 3l9 16H3l9-16z" />
								</svg>
								Verified — Dukcapil returned a false result{dukcapilResult.reason ? `: ${dukcapilResult.reason}` : ""}. Please review the data below before submitting.
							</>
						)}
					</div>
				)}

				{docs.length > 0 && (
					<div style={{
						padding: "10px 16px", borderBottom: "1px solid #DDE3F0",
						background: "#F8FAFF", display: "flex", flexDirection: "column", gap: 8,
					}}>
						{docs.map((d) => {
							const ext = d.name.split(".").pop()?.toLowerCase() ?? "";
							const canPrev = IMAGE_EXTS.has(ext) || ext === "pdf";
							const isDel = deleting.has(d.id);
							const isPrevLoading = previewLoadingId === d.id;
							return (
								<div key={d.id} style={{
									display: "inline-flex", alignItems: "center", gap: 8,
									opacity: isDel ? 0.6 : 1,
								}}>
									{canPrev && (
										<button
											onClick={() => handlePreviewClick(d)}
											disabled={isPrevLoading}
											style={{
												display: "inline-flex", alignItems: "center", gap: 6,
												border: "1px solid #f97316", background: "#fff7ed",
												color: "#c2410c", borderRadius: 6, padding: "5px 12px",
												fontSize: 13, fontWeight: 500,
												cursor: isPrevLoading ? "not-allowed" : "pointer",
												transition: "background 0.15s, color 0.15s, border-color 0.15s",
											}}
											onMouseEnter={(e) => {
												e.currentTarget.style.background = "#f97316";
												e.currentTarget.style.color = "#fff";
												e.currentTarget.style.borderColor = "#ea580c";
											}}
											onMouseLeave={(e) => {
												e.currentTarget.style.background = "#fff7ed";
												e.currentTarget.style.color = "#c2410c";
												e.currentTarget.style.borderColor = "#f97316";
											}}
										>
											{isPrevLoading ? (
												<span style={{ width: 13, height: 13, display: "inline-block", borderRadius: "50%", border: "2px solid rgba(194,65,12,.3)", borderTopColor: "#c2410c", animation: "ocr-spin .7s linear infinite" }} />
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
									<span style={{ fontSize: 13, color: "#374151" }}>{d.name}</span>
									{isDel
										? <span style={{ width: 12, height: 12, display: "inline-block", borderRadius: "50%", border: "2px solid #1B3A7A33", borderTopColor: "#1B3A7A", animation: "ocr-spin .7s linear infinite" }} />
										: (
											<button
												title="Hapus"
												onClick={() => handleDeleteDoc(d.id)}
												style={{ background: "none", border: "none", cursor: "pointer", color: "#94A3B8", fontSize: ".9rem", padding: "0 1px" }}
											>×</button>
										)
									}
								</div>
							);
						})}
					</div>
				)}

				<div style={{ overflowX: "auto" }}>
					<table style={{ width: "100%", borderCollapse: "collapse" }}>
						<thead>
							<tr>
								{[
									{ label: "Field", align: "left" },
									{ label: "Value", align: "left" },
									{ label: "Confidence Rate", align: "center" },
									{ label: null, align: "center" },
								].map((col, i) => (
									<th key={i} style={{
										background: "#F4F7FF", padding: "10px 14px",
										fontSize: ".72rem", fontWeight: 700, textTransform: "uppercase",
										letterSpacing: ".06em", color: "#64748B",
										borderBottom: "1.5px solid #DDE3F0",
										textAlign: col.align as any,
									}}>
										{i === 3 ? (
											showVerify ? (
												<button
													onClick={handleVerify}
													disabled={verifying}
													style={{
														background: dukcapilResult.checked
															? "linear-gradient(135deg,#64748B,#475569)"
															: "linear-gradient(135deg,#10B981,#059669)",
														border: "none", borderRadius: 8, padding: "6px 14px",
														color: "#fff", fontSize: ".75rem", fontWeight: 700,
														fontFamily: "inherit", cursor: "pointer",
														display: "inline-flex", alignItems: "center", gap: 5,
														opacity: verifying ? 0.6 : 1,
													}}
												>
													{verifying ? <Spinner size={12} /> : (
														<svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
															<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5}
																d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
														</svg>
													)}
													{dukcapilResult.checked ? "Re-verify Dukcapil" : "Verify Dukcapil"}
												</button>
											) : (
												<span style={{ fontSize: ".72rem", color: "#64748B" }}>Verified (Dukcapil)</span>
											)
										) : col.label}
									</th>
								))}
							</tr>
						</thead>
						<tbody>
							<OcrRow label="NIK" value={data.idCardNo} confidence={conf.idCardNo} verified={ver.idCardNo} required numeric maxLen={16} onChange={upd("idCardNo")} />
							<OcrRow label="Nama" value={data.name} confidence={conf.name} verified={ver.name} required onChange={upd("name")} />
							<OcrRow label="Tempat Lahir" value={data.placeOfBirth} confidence={conf.placeOfBirth} verified={ver.placeOfBirth} required onChange={upd("placeOfBirth")} />
							<OcrRow label="Tanggal Lahir" value={data.dateOfBirth} confidence={conf.dateOfBirth} verified={ver.dateOfBirth} required onChange={upd("dateOfBirth")} />
							<OcrRow label="Jenis Kelamin" value={data.gender} confidence={conf.gender} verified={ver.gender} required onChange={upd("gender")} />
							<OcrRow label="Golongan Darah" value={data.bloodType} confidence={conf.bloodType} onChange={upd("bloodType")} />
							<OcrRow label="Alamat" value={data.address} confidence={conf.address} verified={ver.address} required textarea onChange={upd("address")} />

							<tr style={{ borderBottom: "1px solid #F0F3FA" }}>
								<td style={{ padding: "10px 14px", whiteSpace: "nowrap", verticalAlign: "middle" }}>
									<span style={{ fontSize: ".8rem", fontWeight: 600, color: "#0F1D3C" }}>
										RT/RW <span style={{ color: "#EF4444" }}>*</span>
									</span>
								</td>
								<td style={{ padding: "10px 14px", verticalAlign: "middle" }}>
									<div style={{ display: "flex", alignItems: "center", gap: 8 }}>
										<input
											value={data.rt} inputMode="numeric" maxLength={3} placeholder="RT"
											onChange={(e) => upd("rt")(e.target.value.replace(/\D/g, "").slice(0, 3))}
											style={{
												width: 72, padding: "7px 12px", fontSize: ".82rem",
												border: "1.5px solid #DDE3F0", borderRadius: 8,
												color: "#0F1D3C", background: "#fff", outline: "none",
											}}
										/>
										<span style={{ color: "#64748B", fontWeight: 700 }}>/</span>
										<input
											value={data.rw} inputMode="numeric" maxLength={3} placeholder="RW"
											onChange={(e) => upd("rw")(e.target.value.replace(/\D/g, "").slice(0, 3))}
											style={{
												width: 72, padding: "7px 12px", fontSize: ".82rem",
												border: "1.5px solid #DDE3F0", borderRadius: 8,
												color: "#0F1D3C", background: "#fff", outline: "none",
											}}
										/>
									</div>
								</td>
								<td style={{ padding: "10px 14px", textAlign: "center", verticalAlign: "middle" }}>
									<ConfBadge value={conf.rt} />
								</td>
								<td style={{ padding: "10px 14px", textAlign: "center", verticalAlign: "middle" }}>
									<VerBadge value={ver.rt} />
								</td>
							</tr>

							<OcrRow label="Kelurahan/Desa" value={data.subdistrict} confidence={conf.subdistrict} verified={ver.subdistrict} required onChange={upd("subdistrict")} />
							<OcrRow label="Kecamatan" value={data.district} confidence={conf.district} verified={ver.district} required onChange={upd("district")} />
							<OcrRow label="Kota/Kabupaten" value={data.city} confidence={conf.city} verified={ver.city} required onChange={upd("city")} />
							<OcrRow label="Provinsi" value={data.province} confidence={conf.province} verified={ver.province} required onChange={upd("province")} />
							<OcrRow label="Agama" value={data.religion} confidence={conf.religion} verified={ver.religion} required onChange={upd("religion")} />
							<OcrRow label="Pekerjaan" value={data.job} confidence={conf.job} verified={ver.job} required onChange={upd("job")} />

							<tr style={{ borderBottom: "1px solid #F0F3FA" }}>
								<td style={{ padding: "10px 14px", verticalAlign: "middle" }}>
									<span style={{ fontSize: ".8rem", fontWeight: 600, color: "#0F1D3C" }}>Foto</span>
								</td>
								<td colSpan={3} style={{ padding: "10px 14px", verticalAlign: "middle" }}>
									{data.photo
										? <img src={`data:image/jpeg;base64,${data.photo}`} alt="Photo" style={{ height: 96, width: 72, objectFit: "cover", borderRadius: 8, border: "2px solid #DDE3F0" }} />
										: <div style={{ background: "#F4F7FF", borderRadius: 8, border: "2px dashed #DDE3F0", display: "flex", alignItems: "center", justifyContent: "center", fontSize: ".65rem", color: "#94A3B8", textAlign: "center" }}>No Photo</div>
									}
								</td>
							</tr>

							<tr>
								<td style={{ padding: "10px 14px", verticalAlign: "middle" }}>
									<span style={{ fontSize: ".8rem", fontWeight: 600, color: "#0F1D3C" }}>Tanda Tangan</span>
								</td>
								<td colSpan={3} style={{ padding: "10px 14px", verticalAlign: "middle" }}>
									{data.signature
										? <img src={`data:image/jpeg;base64,${data.signature}`} alt="Signature" style={{ height: 44, borderRadius: 6, border: "1.5px solid #DDE3F0" }} />
										: <div style={{ background: "#F8FAFF", borderRadius: 6, border: "2px dashed #DDE3F0" }} />
									}
								</td>
							</tr>
						</tbody>
					</table>
				</div>
			</div>
		</>
	);
};

export default OCRUploadSection;