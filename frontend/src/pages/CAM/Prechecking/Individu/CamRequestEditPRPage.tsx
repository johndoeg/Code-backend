import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { fetchCamEditPrData, getDocumentDownloadUrl, submitCamEditPr } from '../../../../api/editPR';
import type {
	CamEditPrData,
	CamEditPrSubmitPayload,
	Citizen,
	DocumentFile,
	DocumentType,
	FieldErrors,
	MaritalStatusCode,
	OcrField,
	PersonOcr,
	SpouseData,
} from '../../../../types/prechecking';
import { buildDocumentConfig, getSpouseDocumentType } from '../../../../utils/prechecking/documentConfig';
import { extractErrorMessage } from '../../../../utils/prechecking/errorMessage';
import PersonOcrTable from '../../../../components/PersonOcrTable';
import type { OcrEditableKey } from '../../../../components/PersonOcrTable';
import DocumentUploadField from '../../../../components/DocumentUploadField';
import SimpleIdentityFields from '../../../../components/SimpleIdentityFields';
import DocPreviewModal, { PREVIEW_CLOSED, type PreviewState } from '../../../../components/DocPreviewModal';
import SectionHeader from '../../../../components/SectionHeader';
import FieldRow from '../../../../components/FieldRow';

const MARITAL_OPTIONS: { value: MaritalStatusCode; label: string }[] = [
	{ value: '', label: 'Select marital status' },
	{ value: 'S', label: 'Single' },
	{ value: 'M', label: 'Married' },
	{ value: 'D', label: 'Divorced' },
	{ value: 'O', label: 'Married (no certificate)' },
	{ value: 'P', label: 'Prenuptial agreement' },
];

const CITIZEN_OPTIONS: { value: Citizen; label: string }[] = [
	{ value: '', label: 'Select nationality' },
	{ value: 'WNI', label: 'Indonesian (WNI)' },
	{ value: 'WNA', label: 'Foreign national (WNA)' },
];

const emptyOcrField = (): OcrField => ({ value: '', confidence: '', verified: '' });

const emptyPersonOcr = (): PersonOcr => ({
	citizen: 'WNI',
	idCardNo: emptyOcrField(),
	name: emptyOcrField(),
	pob: emptyOcrField(),
	dob: emptyOcrField(),
	gender: emptyOcrField(),
	bloodType: emptyOcrField(),
	address: emptyOcrField(),
	rt: emptyOcrField(),
	rw: emptyOcrField(),
	subdistrict: emptyOcrField(),
	district: emptyOcrField(),
	city: emptyOcrField(),
	province: emptyOcrField(),
	religion: emptyOcrField(),
	job: emptyOcrField(),
	photo: '',
	signature: '',
});

const isMarriedStatus = (status: MaritalStatusCode) => status === 'M' || status === 'O';

const CamRequestEditPRPage: React.FC = () => {
	const [searchParams] = useSearchParams();
	const navigate = useNavigate();
	const apless = searchParams.get('apless') || '';
	const precheckingId = searchParams.get('prechecking_id') || '';

	const [data, setData] = useState<CamEditPrData | null>(null);
	const [loading, setLoading] = useState(true);
	const [loadError, setLoadError] = useState<string | null>(null);

	const [maritalStatus, setMaritalStatus] = useState<MaritalStatusCode>('');
	const [spouse, setSpouse] = useState<SpouseData | null>(null);
	const [customerOcr, setCustomerOcr] = useState<PersonOcr | null>(null);
	const [note, setNote] = useState('');
	const [isCarro, setIsCarro] = useState<'0' | '1'>('0');
	const [repeatOrder, setRepeatOrder] = useState<'0' | '1'>('0');
	const [documents, setDocuments] = useState<Partial<Record<DocumentType, DocumentFile[]>>>({});

	const [errors, setErrors] = useState<FieldErrors>({});
	const [saving, setSaving] = useState(false);
	const [saveMessage, setSaveMessage] = useState<string | null>(null);

	const [preview, setPreview] = useState<PreviewState>(PREVIEW_CLOSED);
	const handlePreviewDocument = async (doc: DocumentFile) => {
		try {
			const url = await getDocumentDownloadUrl(doc.awsKey, doc.name);
			setPreview({ open: true, name: doc.name, url });
		} catch (err) {
			setSaveMessage(extractErrorMessage(err, 'Could not open that file. Please try again.'));
		}
	};

	const load = useCallback(async () => {
		if (!apless || !precheckingId) {
			setLoadError('Missing apless or prechecking_id in the URL.');
			setLoading(false);
			return;
		}
		setLoading(true);
		setLoadError(null);
		try {
			const result = await fetchCamEditPrData(apless, precheckingId);
			setData(result);
			setMaritalStatus(result.maritalStatus);
			setSpouse(result.spouse);
			setCustomerOcr(result.customer);
			setNote(result.note);
			setIsCarro(result.is_carro);
			setRepeatOrder(result.repeat_order);
			setDocuments(result.documents);
		} catch (err) {
			setLoadError(extractErrorMessage(err, 'Failed to load prechecking data. Please try again.'));
		} finally {
			setLoading(false);
		}
	}, [apless, precheckingId]);

	useEffect(() => {
		load();
	}, [load]);

	const married = isMarriedStatus(maritalStatus);

	useEffect(() => {
		setSpouse((prev) => {
			if (married && !prev) {
				return { citizenType: '', ocr: null, wnaName: '', wnaIdCardNo: '' };
			}
			if (!married && prev) {
				return null;
			}
			return prev;
		});
	}, [married]);

	const documentConfig = useMemo(() => {
		if (!data) return [];
		return buildDocumentConfig(data.check_for, maritalStatus, data.customer.citizen, spouse?.citizenType || undefined);
	}, [data, maritalStatus, spouse?.citizenType]);

	const customerIdentityDocTypes = useMemo((): DocumentType[] => {
		if (!data) return [];
		const prefix = data.check_for === 'G' ? 'guarantor' : 'cust';
		const types: DocumentType[] = [`${prefix}-ktp` as DocumentType];
		if (data.customer.citizen === 'WNA') types.push(`${prefix}-kitas` as DocumentType);
		return types;
	}, [data]);
	const customerIdentitySlots = useMemo(
		() => documentConfig.filter((c) => customerIdentityDocTypes.includes(c.type)),
		[documentConfig, customerIdentityDocTypes],
	);

	const spouseDocType = useMemo((): DocumentType | undefined => {
		if (!data || !spouse?.citizenType) return undefined;
		return getSpouseDocumentType(data.check_for, data.customer.citizen, spouse.citizenType);
	}, [data, spouse?.citizenType]);
	const spouseDocSlot = useMemo(
		() => documentConfig.find((c) => c.type === spouseDocType),
		[documentConfig, spouseDocType],
	);

	const identityDocs = useMemo(
		() => documentConfig.filter((c) => c.group === 'identity' && !customerIdentityDocTypes.includes(c.type)),
		[documentConfig, customerIdentityDocTypes],
	);
	const maritalDocs = useMemo(
		() => documentConfig.filter((c) => c.group === 'marital' && c.type !== spouseDocSlot?.type),
		[documentConfig, spouseDocSlot],
	);
	const requiredTotal = useMemo(() => documentConfig.filter((c) => c.required).length, [documentConfig]);
	const requiredUploaded = useMemo(
		() => documentConfig.filter((c) => c.required && (documents[c.type]?.length || 0) > 0).length,
		[documentConfig, documents],
	);

	const handleSpouseOcrChange = (key: OcrEditableKey, field: OcrField) => {
		setSpouse((prev) => {
			if (!prev || !prev.ocr) return prev;
			return { ...prev, ocr: { ...prev.ocr, [key]: field } };
		});
	};

	const handleCustomerOcrChange = (key: OcrEditableKey, field: OcrField) => {
		setCustomerOcr((prev) => (prev ? { ...prev, [key]: field } : prev));
	};

	const handleSubmit = async () => {
		if (!data) return;
		setSaving(true);
		setSaveMessage(null);
		setErrors({});

		const payload: CamEditPrSubmitPayload = {
			apless,
			prechecking_id: precheckingId,
			repeat_order: repeatOrder,
			is_carro: isCarro,
			note,
			marital_status: maritalStatus,
			customer:
				data.customer.citizen === 'WNI' && customerOcr
					? {
						idCardNo: customerOcr.idCardNo,
						name: customerOcr.name,
						pob: customerOcr.pob,
						dob: customerOcr.dob,
						gender: customerOcr.gender,
						bloodType: customerOcr.bloodType,
						address: customerOcr.address,
						rt: customerOcr.rt,
						rw: customerOcr.rw,
						subdistrict: customerOcr.subdistrict,
						district: customerOcr.district,
						city: customerOcr.city,
						province: customerOcr.province,
						religion: customerOcr.religion,
						job: customerOcr.job,
					}
					: undefined,
			spouse:
				married && spouse
					? {
						citizenType: spouse.citizenType,
						ocr:
							spouse.citizenType === 'WNI' && spouse.ocr
								? {
									idCardNo: spouse.ocr.idCardNo,
									name: spouse.ocr.name,
									pob: spouse.ocr.pob,
									dob: spouse.ocr.dob,
									gender: spouse.ocr.gender,
									bloodType: spouse.ocr.bloodType,
									address: spouse.ocr.address,
									rt: spouse.ocr.rt,
									rw: spouse.ocr.rw,
									subdistrict: spouse.ocr.subdistrict,
									district: spouse.ocr.district,
									city: spouse.ocr.city,
									province: spouse.ocr.province,
									religion: spouse.ocr.religion,
									job: spouse.ocr.job,
								}
								: undefined,
						wnaName: spouse.citizenType === 'WNA' ? spouse.wnaName : undefined,
						wnaIdCardNo: spouse.citizenType === 'WNA' ? spouse.wnaIdCardNo : undefined,
					}
					: null,
		};

		try {
			const res = await submitCamEditPr(payload);
			if (res.success) {
				setSaveMessage('Saved successfully.');
				navigate('/cam-request-onhand')
			} else {
				setErrors(res.errors || {});
				setSaveMessage(res.message || 'Please fix the highlighted fields.');
			}
		} catch (err) {
			setSaveMessage(extractErrorMessage(err, 'Failed to save. Please try again.'));
		} finally {
			setSaving(false);
		}
	};

	if (loading) {
		return <div className="p-6 text-gray-500">Loading...</div>;
	}
	if (loadError) {
		return <div className="p-6 text-red-600">{loadError}</div>;
	}
	if (!data) {
		return null;
	}

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<DocPreviewModal state={preview} onClose={() => setPreview(PREVIEW_CLOSED)} />

			<div className="max-w-7xl mx-auto space-y-6">
				<div className="bg-gradient-to-r from-blue-900 via-blue-800 to-blue-600 rounded-2xl p-6 shadow-lg flex flex-col md:flex-row md:items-center md:justify-between gap-4">
					<div>
						<h1 className="text-white text-xl md:text-2xl font-bold">Edit Prechecking Data</h1>
						<p className="text-blue-200 text-sm mt-1">
							{data.check_for === 'G' ? 'Guarantor' : 'Customer'} &middot; <span className="font-mono">{data.apless}</span>
						</p>
					</div>
					<div className="flex items-center gap-4 self-start md:self-auto">
						<p className="text-white text-sm">
							<span className="font-bold mr-2">Prechecking ID :</span>
							<span className="font-mono font-semibold">{data.prechecking_id}</span>
						</p>
						<button
							onClick={() => navigate(-1)}
							className="bg-white/15 hover:bg-white/25 border border-white/30 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors flex items-center gap-2"
						>
							<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
							</svg>
							Back
						</button>
					</div>
				</div>

				<div className="bg-white rounded-2xl shadow-lg p-6">
					{saveMessage && (
						<div
							className={`mb-4 p-3 rounded-lg text-sm border ${Object.keys(errors).length
								? 'bg-red-50 text-red-700 border-red-200'
								: 'bg-green-50 text-green-700 border-green-200'
								}`}
						>
							{saveMessage}
						</div>
					)}

					<section className="mb-8">
						<SectionHeader title="General Information" />
						<div className="grid md:grid-cols-2 gap-x-12">
							<div>
								<FieldRow label="Checking For" value={data.check_for === 'G' ? 'Guarantor' : 'Customer'} />
								<FieldRow label="Type" value={data.customer_type === 'PR' ? 'Individu' : 'Corporate'} />
								<FieldRow label="New / Repeat Order" value={data.repeat_order === '1' ? 'Repeat Order' : 'New'} />
								<FieldRow label="Temp. Customer No." value={<span className="font-mono">{data.apless}</span>} />
								<FieldRow label="Nationality" value={data.customer.citizen || '—'} />
							</div>
							<div>
								<FieldRow label="Last Prechecking Date" value={data.last_checking_date || '—'} />
								<FieldRow label="Outstanding" value={`IDR ${data.outstanding.toLocaleString('id-ID')}`} />
							</div>
						</div>
					</section>

					<section className="mb-8">
						<SectionHeader title="Customer Data (OCR)" />
						<p className="text-xs text-gray-500 mb-3 -mt-2">
							{data.customer.citizen === 'WNA'
								? 'Captured at intake and read-only on this screen.'
								: "Editable — NIK's value stays locked; everything else, including its confidence and Dukcapil flag, can be corrected here."}
						</p>

						{customerIdentitySlots.length > 0 && (
							<div className="grid grid-cols-1 gap-3 mb-4">
								{customerIdentitySlots.map((cfg) => (
									<DocumentUploadField
										key={cfg.type}
										label={cfg.label}
										apless={apless}
										precheckingId={precheckingId}
										documentType={cfg.type}
										files={documents[cfg.type] || []}
										required={cfg.required}
										multiple={cfg.multiple}
										onChanged={(files) => setDocuments((prev) => ({ ...prev, [cfg.type]: files }))}
										onPreview={handlePreviewDocument}
									/>
								))}
							</div>
						)}

						{data.customer.citizen === 'WNA' ? (
							<SimpleIdentityFields
								name={data.customer.name.value}
								idCardNo={data.customer.idCardNo.value}
								nameLabel="Name"
								idLabel="Passport No."
								readOnly
							/>
						) : (
							customerOcr && <PersonOcrTable data={customerOcr} onFieldChange={handleCustomerOcrChange} />
						)}
					</section>

					<section className="mb-8 max-w-xs">
						<label className="block text-sm font-medium text-gray-700 mb-1">Marital Status</label>
						<select
							className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
							value={maritalStatus}
							onChange={(e) => setMaritalStatus(e.target.value as MaritalStatusCode)}
						>
							{MARITAL_OPTIONS.map((o) => (
								<option key={o.value} value={o.value}>
									{o.label}
								</option>
							))}
						</select>
						{errors.marital_status && <p className="text-xs text-red-600 mt-1">{errors.marital_status}</p>}
					</section>

					{married && spouse && (
						<section className="mb-8">
							<SectionHeader title="Spouse" />

							<div className="mb-3 max-w-xs">
								<label className="block text-sm font-medium text-gray-700 mb-1">Spouse Nationality</label>
								<select
									className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
									value={spouse.citizenType}
									onChange={(e) => {
										const citizenType = e.target.value as Citizen;
										setSpouse((prev) =>
											prev
												? {
													...prev,
													citizenType,
													ocr: citizenType === 'WNI' ? prev.ocr || emptyPersonOcr() : prev.ocr,
												}
												: prev,
										);
									}}
								>
									{CITIZEN_OPTIONS.map((o) => (
										<option key={o.value} value={o.value}>
											{o.label}
										</option>
									))}
								</select>
								{errors['spouse.citizenType'] && (
									<p className="text-xs text-red-600 mt-1">{errors['spouse.citizenType']}</p>
								)}
							</div>

							{spouse.citizenType === '' && (
								<p className="text-sm text-gray-500 italic">Select the spouse's nationality to continue.</p>
							)}

							{spouse.citizenType !== '' && spouseDocSlot && (
								<div className="mb-4">
									<DocumentUploadField
										label={spouseDocSlot.label}
										apless={apless}
										precheckingId={precheckingId}
										documentType={spouseDocSlot.type}
										files={documents[spouseDocSlot.type] || []}
										required={spouseDocSlot.required}
										multiple={spouseDocSlot.multiple}
										error={errors['spouse.document']}
										onChanged={(files) => setDocuments((prev) => ({ ...prev, [spouseDocSlot.type]: files }))}
										onPreview={handlePreviewDocument}
									/>
								</div>
							)}

							{spouse.citizenType === 'WNI' && spouse.ocr && (
								<PersonOcrTable data={spouse.ocr} onFieldChange={handleSpouseOcrChange} />
							)}

							{spouse.citizenType === 'WNA' && (
								<SimpleIdentityFields
									name={spouse.wnaName}
									idCardNo={spouse.wnaIdCardNo}
									nameLabel="Spouse Name"
									idLabel="Spouse ID/Passport No."
									nameError={errors['spouse.wnaName']}
									idCardNoError={errors['spouse.wnaIdCardNo']}
									onNameChange={(v) => setSpouse((prev) => (prev ? { ...prev, wnaName: v } : prev))}
									onIdCardNoChange={(v) => setSpouse((prev) => (prev ? { ...prev, wnaIdCardNo: v } : prev))}
								/>
							)}
						</section>
					)}

					<section className="mb-8">
						<SectionHeader
							title="Documents"
							right={
								requiredTotal > 0 ? (
									<span
										className={`text-xs font-medium px-2.5 py-1 rounded-full flex-shrink-0 ${requiredUploaded === requiredTotal
											? 'bg-green-100 text-green-700'
											: 'bg-amber-100 text-amber-700'
											}`}
									>
										{requiredUploaded}/{requiredTotal} required uploaded
									</span>
								) : null
							}
						/>

						{identityDocs.length > 0 && (
							<div className={maritalDocs.length > 0 ? 'mb-5' : ''}>
								<h3 className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">
									Identity Documents
								</h3>
								<div className="grid grid-cols-1 gap-3">
									{identityDocs.map((cfg) => (
										<DocumentUploadField
											key={cfg.type}
											label={cfg.label}
											apless={apless}
											precheckingId={precheckingId}
											documentType={cfg.type}
											files={documents[cfg.type] || []}
											required={cfg.required}
											multiple={cfg.multiple}
											onChanged={(files) => setDocuments((prev) => ({ ...prev, [cfg.type]: files }))}
											onPreview={handlePreviewDocument}
										/>
									))}
								</div>
							</div>
						)}

						{maritalDocs.length > 0 && (
							<div>
								<h3 className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">
									Marital Documents
								</h3>
								<div className="grid grid-cols-1 gap-3">
									{maritalDocs.map((cfg) => (
										<DocumentUploadField
											key={cfg.type}
											label={cfg.label}
											apless={apless}
											precheckingId={precheckingId}
											documentType={cfg.type}
											files={documents[cfg.type] || []}
											required={cfg.required}
											multiple={cfg.multiple}
											onChanged={(files) => setDocuments((prev) => ({ ...prev, [cfg.type]: files }))}
											onPreview={handlePreviewDocument}
										/>
									))}
								</div>
							</div>
						)}
					</section>

					<section className="mb-8 max-w-xs">
						<SectionHeader title="Reference" />
						<select
							className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
							value={isCarro}
							onChange={(e) => setIsCarro(e.target.value as '0' | '1')}
						>
							<option value="1">Carro</option>
							<option value="0">Non Carro</option>
						</select>
					</section>

					<section className="mb-8">
						<SectionHeader title="Notes" />
						<textarea
							className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
							rows={3}
							value={note}
							onChange={(e) => setNote(e.target.value)}
						/>
					</section>

					{data.sik.length > 0 && (
						<section className="mb-8">
							<SectionHeader title="Credit Bureau Checks" />
							<div className="overflow-x-auto rounded-lg border border-gray-200">
								<table className="w-full">
									<thead className="bg-gray-50">
										<tr>
											{['Subject', 'Bureau', 'Status', 'Score', 'Grade'].map((h) => (
												<th key={h} className="py-2 px-3 text-left text-xs font-medium text-gray-500 uppercase">
													{h}
												</th>
											))}
										</tr>
									</thead>
									<tbody className="divide-y divide-gray-200">
										{data.sik.map((s, i) => (
											<tr key={`${s.subject}-${i}`} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
												<td className="py-2 px-3 text-sm">{s.subject}</td>
												<td className="py-2 px-3 text-sm">{s.creditBureau}</td>
												<td className="py-2 px-3 text-sm">{s.status}</td>
												<td className="py-2 px-3 text-sm">{s.score}</td>
												<td className="py-2 px-3 text-sm">{s.grade}</td>
											</tr>
										))}
									</tbody>
								</table>
							</div>
						</section>
					)}

					<div className="flex justify-end gap-3">
						<button
							type="button"
							onClick={() => navigate(-1)}
							className="px-5 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50"
						>
							Cancel
						</button>
						<button
							type="button"
							onClick={handleSubmit}
							disabled={saving}
							className={`bg-gradient-to-r from-blue-600 to-indigo-700 hover:from-blue-700 hover:to-indigo-800 text-white px-6 py-2 rounded-lg font-medium shadow-md transition-all ${saving ? 'opacity-75 cursor-not-allowed' : ''
								}`}
						>
							{saving ? 'Saving...' : 'Save Changes'}
						</button>
					</div>
				</div>
			</div>
		</div>
	);
};

export default CamRequestEditPRPage;