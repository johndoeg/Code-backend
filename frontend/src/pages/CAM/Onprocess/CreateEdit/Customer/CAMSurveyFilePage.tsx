import React, { useCallback, useEffect, useState } from "react";
import api from "../../../../../api/axiosInstance";
import CKEditorNotes from "../../../../../shared/CKEditorNotes";

interface SurveyFileItem {
	id: number;
	documentName: string;
	downloadUrl: string;
}

interface SurveySectionData {
	notes: string;
	files: SurveyFileItem[];
}

interface ContractSummary {
	status: string;
	brand: string;
	model: string;
	modelType: string;
	customerName: string;
	chassis: string;
	engine: string;
	bpkbName: string;
	bpkbAddress: string;
	year: string;
	condition: string;
	supplier: string;
	color: string;
	policeNo: string;
}

interface SurveyFileData {
	contract: ContractSummary;
	home: SurveySectionData;
	office: SurveySectionData;
	other: SurveySectionData;
}

export interface CAMSurveyFilePageProps {
	apless: string;
	applNo: string;
	status: string;
	onSaved: (result: { apless: string; applno: string }) => void;
}

const cellLabel =
	"border-b border-slate-100 bg-slate-50/70 px-4 py-2.5 align-top text-[11px] font-medium uppercase tracking-wide text-slate-400 whitespace-nowrap";
const cellValue = "border-b border-slate-100 px-4 py-2.5 align-top text-sm text-slate-700";

function SectionHeader({ children }: { children: React.ReactNode }) {
	return (
		<div className="border-b border-t border-slate-200 bg-slate-50 px-6 py-3 first:border-t-0">
			<h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">{children}</h2>
		</div>
	);
}

function Row({
	left,
	right,
}: {
	left: [string, React.ReactNode];
	right: [string, React.ReactNode];
}) {
	return (
		<tr>
			<td className={cellLabel}>{left[0]}</td>
			<td className={cellValue}>{left[1]}</td>
			<td className={cellLabel}>{right[0]}</td>
			<td className={cellValue}>{right[1]}</td>
		</tr>
	);
}

const fieldLabelCls = "text-[11px] font-medium uppercase tracking-wide text-slate-400 mb-1 block";

type SurveyType = "home" | "office" | "other";

const SURVEY_TYPE_CODES: Record<SurveyType, string> = {
	home: "home-survey",
	office: "office-survey",
	other: "other-survey",
};

const emptySection: SurveySectionData = { notes: "", files: [] };

function SurveySection({
	title,
	section,
	uploading,
	uploadError,
	deletingFileId,
	onNotesChange,
	onUpload,
	onDelete,
}: {
	title: string;
	section: SurveySectionData;
	uploading: boolean;
	uploadError: string | null;
	deletingFileId: number | null;
	onNotesChange: (value: string) => void;
	onUpload: (fileList: FileList | null) => void;
	onDelete: (id: number) => void;
}) {
	return (
		<>
			<SectionHeader>{title}</SectionHeader>
			<div className="px-6 py-4 space-y-4">
				<div>
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
				</div>

				{section.files.length > 0 && (
					<div className="overflow-hidden rounded-lg border border-slate-200">
						<table className="w-full border-collapse text-sm">
							<tbody>
								{section.files.map(f => (
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

				<div>
					<label className={fieldLabelCls}>Notes</label>
					<CKEditorNotes value={section.notes} onChange={onNotesChange} minHeight={250} />
				</div>
			</div>
		</>
	);
}

const CAMSurveyFilePage: React.FC<CAMSurveyFilePageProps> = ({ apless, applNo, status, onSaved }) => {
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [savingNext, setSavingNext] = useState(false);

	const [contract, setContract] = useState<ContractSummary | null>(null);
	const [sections, setSections] = useState<Record<SurveyType, SurveySectionData>>({
		home: emptySection, office: emptySection, other: emptySection,
	});
	const [uploadingType, setUploadingType] = useState<SurveyType | null>(null);
	const [uploadErrors, setUploadErrors] = useState<Record<SurveyType, string | null>>({
		home: null, office: null, other: null,
	});
	const [deletingFileId, setDeletingFileId] = useState<number | null>(null);

	const load = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			const res = await api.get("/CAM/EditIndex/survey-file", { params: { apless, applno: applNo, status } });
			const d: SurveyFileData = res.data;
			setContract(d.contract);
			setSections({ home: d.home, office: d.office, other: d.other });
		} catch {
			setError("Failed to load survey files. Please try again.");
		} finally {
			setLoading(false);
		}
	}, [apless, applNo, status]);

	useEffect(() => {
		load();
	}, [load]);

	const setNotes = (type: SurveyType, value: string) =>
		setSections(prev => ({ ...prev, [type]: { ...prev[type], notes: value } }));

	const handleUpload = async (type: SurveyType, fileList: FileList | null) => {
		if (!fileList || fileList.length === 0) return;
		setUploadingType(type);
		setUploadErrors(prev => ({ ...prev, [type]: null }));
		try {
			const formData = new FormData();
			formData.append("apless", apless);
			formData.append("applno", applNo);
			formData.append("surveyType", SURVEY_TYPE_CODES[type]);
			Array.from(fileList).forEach(f => formData.append("files", f));

			const res = await api.post("/CAM/EditIndex/survey-file/upload", formData, {
				headers: { "Content-Type": "multipart/form-data" },
			});
			if (res.data.success) {
				setSections(prev => ({ ...prev, [type]: { ...prev[type], files: res.data.files } }));
			} else {
				setUploadErrors(prev => ({ ...prev, [type]: res.data.message || "Upload failed." }));
			}
		} catch {
			setUploadErrors(prev => ({ ...prev, [type]: "Upload failed. Please try again." }));
		} finally {
			setUploadingType(null);
		}
	};

	const handleDeleteFile = async (type: SurveyType, id: number) => {
		if (!window.confirm("Are you sure to delete this record?")) return;
		setDeletingFileId(id);
		try {
			await api.delete("/CAM/EditIndex/survey-file", { params: { apless, applno: applNo, id } });
			setSections(prev => ({ ...prev, [type]: { ...prev[type], files: prev[type].files.filter(f => f.id !== id) } }));
		} catch {
			alert("Delete failed. Please try again.");
		} finally {
			setDeletingFileId(null);
		}
	};

	const handleNext = async () => {
		setSavingNext(true);
		try {
			const res = await api.post("/CAM/EditIndex/survey-file/next", {
				apless,
				applno: applNo,
				notesHome: sections.home.notes,
				notesOffice: sections.office.notes,
				notesOther: sections.other.notes,
			});
			if (res.data.success) {
				onSaved({ apless, applno: applNo });
			} else {
				alert(res.data.message || "Please upload Survey File.");
			}
		} catch {
			alert("Save failed. Please try again.");
		} finally {
			setSavingNext(false);
		}
	};

	if (loading || !contract) {
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

	return (
		<div>
			<h2 className="text-xl font-bold text-slate-800 mb-1">Survey Files</h2>
			<p className="text-sm text-slate-500 mb-4">Customer No. {apless || "(new)"}</p>

			<div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
				<SectionHeader>Contract Summary</SectionHeader>
				<div className="overflow-x-auto">
					<table className="w-full min-w-[820px] border-collapse text-sm">
						<tbody>
							<Row
								left={["Contract Status", contract.status]}
								right={["Brand / Model / Type", `${contract.brand}/${contract.model}/${contract.modelType}`]}
							/>
							<Row left={["Customer Name", contract.customerName]} right={["Chassis", contract.chassis]} />
							<Row left={["BPKB Name", contract.bpkbName]} right={["Engine", contract.engine]} />
							<Row
								left={["BPKB Address", contract.bpkbAddress]}
								right={["Year / Condition", `${contract.year}/${contract.condition}`]}
							/>
							<Row
								left={["Supplier", contract.supplier]}
								right={["Color / Police No.", `${contract.color}/${contract.policeNo}`]}
							/>
						</tbody>
					</table>
				</div>

				<SurveySection
					title="Home Survey Report"
					section={sections.home}
					uploading={uploadingType === "home"}
					uploadError={uploadErrors.home}
					deletingFileId={deletingFileId}
					onNotesChange={v => setNotes("home", v)}
					onUpload={fl => handleUpload("home", fl)}
					onDelete={id => handleDeleteFile("home", id)}
				/>
				<SurveySection
					title="Office Survey Report"
					section={sections.office}
					uploading={uploadingType === "office"}
					uploadError={uploadErrors.office}
					deletingFileId={deletingFileId}
					onNotesChange={v => setNotes("office", v)}
					onUpload={fl => handleUpload("office", fl)}
					onDelete={id => handleDeleteFile("office", id)}
				/>
				<SurveySection
					title="Other Survey Report"
					section={sections.other}
					uploading={uploadingType === "other"}
					uploadError={uploadErrors.other}
					deletingFileId={deletingFileId}
					onNotesChange={v => setNotes("other", v)}
					onUpload={fl => handleUpload("other", fl)}
					onDelete={id => handleDeleteFile("other", id)}
				/>
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

export default CAMSurveyFilePage;