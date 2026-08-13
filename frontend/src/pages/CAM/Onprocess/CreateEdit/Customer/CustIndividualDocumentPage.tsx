import React, { useCallback, useEffect, useState } from "react";
import api from "../../../../../api/axiosInstance";

interface DocumentFileItem {
	id: number;
	documentName: string;
	downloadUrl: string;
}

interface IndividualDocumentData {
	citizen: string;
	spouseCitizen: string;
	files: Record<string, DocumentFileItem[]>;
}

export interface CustIndividualDocumentPageProps {
	apless: string;
	applNo: string;
	onSaved: (result: { apless: string; applno: string }) => void;
}

const cellLabel =
	"border-b border-slate-100 bg-slate-50/70 px-4 py-2.5 align-top text-[11px] font-medium uppercase tracking-wide text-slate-400 whitespace-nowrap";
const cellValue = "border-b border-slate-100 px-4 py-2.5 align-top text-sm text-slate-700";
const subheadCell =
	"border-b border-slate-100 bg-indigo-50/70 px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-indigo-600";

function SectionHeader({ children }: { children: React.ReactNode }) {
	return (
		<div className="border-b border-t border-slate-200 bg-slate-50 px-6 py-3 first:border-t-0">
			<h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">{children}</h2>
		</div>
	);
}

function SubheadRow({ children }: { children: React.ReactNode }) {
	return (
		<tr>
			<td colSpan={2} className={subheadCell}>{children}</td>
		</tr>
	);
}

function DocumentUploadRow({
	label,
	files,
	uploading,
	uploadError,
	deletingFileId,
	onUpload,
	onDelete,
}: {
	label: string;
	files: DocumentFileItem[];
	uploading: boolean;
	uploadError: string | null;
	deletingFileId: number | null;
	onUpload: (fileList: FileList | null) => void;
	onDelete: (id: number) => void;
}) {
	return (
		<tr>
			<td className={cellLabel}>{label}</td>
			<td className={cellValue}>
				<input
					type="file"
					multiple
					disabled={uploading}
					onChange={e => {
						onUpload(e.target.files);
						e.target.value = "";
					}}
					className="text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-blue-600 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white file:cursor-pointer hover:file:bg-blue-700 disabled:opacity-50"
				/>
				{uploading && <p className="text-xs text-slate-500 mt-1">Uploading…</p>}
				{uploadError && <p className="text-xs text-red-600 mt-1">{uploadError}</p>}

				{files.length > 0 && (
					<div className="mt-2 overflow-hidden rounded-lg border border-slate-200">
						<table className="w-full border-collapse text-sm">
							<tbody>
								{files.map(f => (
									<tr key={f.id}>
										<td className={cellValue}>{f.documentName}</td>
										<td className={cellValue + " w-40"}>
											<div className="flex gap-3">
												<a
													href={f.downloadUrl}
													target="_blank"
													rel="noreferrer"
													className="text-xs font-medium text-blue-600 hover:underline"
												>
													Download
												</a>
												<button
													onClick={() => onDelete(f.id)}
													disabled={deletingFileId === f.id}
													className="text-xs font-medium text-red-600 hover:underline disabled:text-slate-400"
												>
													{deletingFileId === f.id ? "Deleting…" : "Delete"}
												</button>
											</div>
										</td>
									</tr>
								))}
							</tbody>
						</table>
					</div>
				)}
			</td>
		</tr>
	);
}

const CustIndividualDocumentPage: React.FC<CustIndividualDocumentPageProps> = ({ apless, applNo, onSaved }) => {
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [savingNext, setSavingNext] = useState(false);

	const [citizen, setCitizen] = useState("WNI");
	const [spouseCitizen, setSpouseCitizen] = useState("WNI");
	const [files, setFiles] = useState<Record<string, DocumentFileItem[]>>({});
	const [uploadingType, setUploadingType] = useState<string | null>(null);
	const [uploadErrors, setUploadErrors] = useState<Record<string, string | null>>({});
	const [deletingFileId, setDeletingFileId] = useState<number | null>(null);

	const load = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			const res = await api.get("/CAM/EditIndex/document/individual", { params: { apless, applno: applNo } });
			const d: IndividualDocumentData = res.data;
			setCitizen(d.citizen);
			setSpouseCitizen(d.spouseCitizen);
			setFiles(d.files || {});
		} catch {
			setError("Failed to load customer documents. Please try again.");
		} finally {
			setLoading(false);
		}
	}, [apless, applNo]);

	useEffect(() => {
		load();
	}, [load]);

	const filesFor = (docType: string) => files[docType] || [];

	const handleUpload = async (docType: string, fileList: FileList | null) => {
		if (!fileList || fileList.length === 0) return;
		setUploadingType(docType);
		setUploadErrors(prev => ({ ...prev, [docType]: null }));
		try {
			const formData = new FormData();
			formData.append("apless", apless);
			formData.append("applno", applNo);
			formData.append("documentType", docType);
			Array.from(fileList).forEach(f => formData.append("files", f));

			const res = await api.post("/CAM/EditIndex/document/individual/upload", formData, {
				headers: { "Content-Type": "multipart/form-data" },
			});
			if (res.data.success) {
				setFiles(prev => ({ ...prev, [docType]: res.data.files }));
			} else {
				setUploadErrors(prev => ({ ...prev, [docType]: res.data.message || "Upload failed." }));
			}
		} catch {
			setUploadErrors(prev => ({ ...prev, [docType]: "Upload failed. Please try again." }));
		} finally {
			setUploadingType(null);
		}
	};

	const handleDeleteFile = async (docType: string, id: number) => {
		if (!window.confirm("Are you sure to delete this record?")) return;
		setDeletingFileId(id);
		try {
			await api.delete("/CAM/EditIndex/document/individual", { params: { apless, applno: applNo, id } });
			setFiles(prev => ({ ...prev, [docType]: (prev[docType] || []).filter(f => f.id !== id) }));
		} catch {
			alert("Delete failed. Please try again.");
		} finally {
			setDeletingFileId(null);
		}
	};

	const handleNext = async () => {
		setSavingNext(true);
		try {
			const res = await api.post("/CAM/EditIndex/document/individual/next", { apless, applno: applNo });
			if (res.data.success) {
				onSaved({ apless, applno: applNo });
			} else {
				alert(res.data.message || "Please upload Customer's Document.");
			}
		} catch {
			alert("Save failed. Please try again.");
		} finally {
			setSavingNext(false);
		}
	};

	if (loading) {
		return (
			<div className="flex justify-center py-16">
				<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
			</div>
		);
	}
	if (error) {
		return (
			<div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm flex items-center justify-between">
				{error}
				<button onClick={load} className="underline ml-4">Retry</button>
			</div>
		);
	}

	const row = (docType: string, label: string) => (
		<DocumentUploadRow
			key={docType}
			label={label}
			files={filesFor(docType)}
			uploading={uploadingType === docType}
			uploadError={uploadErrors[docType] || null}
			deletingFileId={deletingFileId}
			onUpload={fl => handleUpload(docType, fl)}
			onDelete={id => handleDeleteFile(docType, id)}
		/>
	);

	return (
		<div>
			<h2 className="text-xl font-bold text-slate-800 mb-1">Customer's Document</h2>
			<p className="text-sm text-slate-500 mb-4">Customer No. {apless || "(new)"}</p>

			<div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
				<SectionHeader>Documents</SectionHeader>
				<div className="overflow-x-auto">
					<table className="w-full min-w-[720px] border-collapse text-sm">
						<tbody>
							{citizen === "WNI" && (
								<>
									<SubheadRow>WNI</SubheadRow>
									{row("cust-spouse-kk", "Customer's Spouse Family Card")}
								</>
							)}
							{citizen === "WNA" && (
								<>
									<SubheadRow>WNA</SubheadRow>
									{row("cust-kitas", "KITAS/KITAP a/n Pelanggan")}
									{spouseCitizen === "WNI"
										? row("cust-wna-spouse-ktp", "KITAS/KITAP a/n Suami/Istri Pelanggan")
										: row("cust-spouse-kitas", "KITAS/KITAP a/n Suami/Istri Pelanggan")}
									{row("cust-family-tree", "SK. Susunan Keluarga Pendatang (SKSP) WNA")}
									{row("cust-reference", "Surat Referensi Kerja dari Perusahaan WNA Bekerja")}
								</>
							)}

							<SubheadRow>Additional Document</SubheadRow>
							{row("cust-salary-receipt", "Salary Receipt")}

							<SubheadRow>BPKB Document</SubheadRow>
							{row("cust-ktp-bpkb", "BPKB ID")}
							{row("cust-kk-bpkb", "BPKB Family Card")}
							{row("cust-other", "Other")}

							<SubheadRow>Individual Document</SubheadRow>
							{row("cust-ktp", "ID Card")}
							{citizen === "WNI" &&
								(spouseCitizen === "WNI"
									? row("cust-spouse-ktp", "Spouse ID Card")
									: row("cust-spouse-kitas", "Spouse ID Card"))}
							{row("cust-kk", "KK")}
							{row("cust-npwp", "NPWP")}
							{row("cust-spk", "SPK")}
							{row("cust-marriage-or-death-statement", "Marriage/ Death/ Divorce/ Prenuptial Statement")}
						</tbody>
					</table>
				</div>
			</div>

			<div className="flex justify-end gap-3 mt-6">
				<button
					onClick={handleNext}
					disabled={savingNext}
					className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white rounded-lg text-sm font-medium"
				>
					{savingNext ? "Saving…" : "Next"}
				</button>
			</div>
		</div>
	);
};

export default CustIndividualDocumentPage;