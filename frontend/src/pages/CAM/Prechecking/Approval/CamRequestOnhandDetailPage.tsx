import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { decideOnhandDetail, fetchOnhandDetailData, getReviewDocumentDownloadUrl } from '../../../../api/onhandDetail';
import type { Decision, OnhandDetailData, SikRow } from '../../../../types/onhandDetail';
import type { DocumentFile } from '../../../../types/prechecking';
import { extractErrorMessage } from '../../../../utils/prechecking/errorMessage';
import PersonOcrTable from '../../../../components/PersonOcrTable';
import SimpleIdentityFields from '../../../../components/SimpleIdentityFields';
import SectionHeader from '../../../../components/SectionHeader';
import FieldRow from '../../../../components/FieldRow';
import DocChip from '../../../../components/DocChip';
import DocPreviewModal, { PREVIEW_CLOSED, type PreviewState } from '../../../../components/DocPreviewModal';
import ApprovalHistory from '../../../../components/ApprovalHistory';
import SikTable from '../../../../components/SikTable';

const DOCUMENT_TYPE_LABELS: Record<string, string> = {
	'cust-ktp': 'ID Card (KTP)',
	'cust-kitas': 'KITAS',
	'cust-spouse-ktp': "Spouse's ID Card (KTP)",
	'cust-spouse-kitas': "Spouse's KITAS",
	'cust-wna-spouse-ktp': "Spouse's ID Card (KTP)",
	'cust-kk': 'Family Card (KK)',
	'cust-npwp': 'Tax ID (NPWP)',
	'cust-marriage-or-death-statement': 'Akta Cerai / Akta Kematian',
	'guarantor-ktp': 'ID Card (KTP)',
	'guarantor-kitas': 'KITAS',
	'guarantor-spouse-ktp': "Spouse's ID Card (KTP)",
	'guarantor-spouse-kitas': "Spouse's KITAS",
	'guarantor-wna-spouse-ktp': "Spouse's ID Card (KTP)",
	'guarantor-kk': 'Family Card (KK)',
	'guarantor-npwp': 'Tax ID (NPWP)',
	'guarantor-marriage-or-death-statement': 'Akta Cerai / Akta Kematian',
};

const CamRequestOnhandDetailPage: React.FC = () => {
	const [searchParams] = useSearchParams();
	const navigate = useNavigate();
	const apless = searchParams.get('apless') || '';
	const precheckingId = searchParams.get('prechecking_id') || '';

	const [data, setData] = useState<OnhandDetailData | null>(null);
	const [loading, setLoading] = useState(true);
	const [loadError, setLoadError] = useState<string | null>(null);

	const [sikRows, setSikRows] = useState<SikRow[]>([]);
	const [comment, setComment] = useState('');
	const [errors, setErrors] = useState<Record<string, string>>({});
	const [deciding, setDeciding] = useState<Decision | null>(null);
	const [message, setMessage] = useState<string | null>(null);

	const [preview, setPreview] = useState<PreviewState>(PREVIEW_CLOSED);
	const handlePreview = async (doc: DocumentFile) => {
		try {
			const url = await getReviewDocumentDownloadUrl(doc.awsKey, doc.name);
			setPreview({ open: true, name: doc.name, url });
		} catch (err) {
			setMessage(extractErrorMessage(err, 'Could not open that file. Please try again.'));
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
			const result = await fetchOnhandDetailData(apless, precheckingId);
			setData(result);
			setSikRows(result.sik);
		} catch (err) {
			setLoadError(extractErrorMessage(err, 'Failed to load prechecking data. Please try again.'));
		} finally {
			setLoading(false);
		}
	}, [apless, precheckingId]);

	useEffect(() => {
		load();
	}, [load]);

	const handleDecide = async (decision: Decision) => {
		if (!data) return;
		setDeciding(decision);
		setMessage(null);
		setErrors({});
		try {
			const res = await decideOnhandDetail({
				apless,
				prechecking_id: precheckingId,
				decision,
				comment,
				sik: sikRows,
			});
			if (res.success) {
				navigate('/cam-request-onhand');
			} else {
				setErrors(res.errors || {});
				setMessage(res.message || 'Please fix the highlighted fields.');
			}
		} catch (err) {
			setMessage(extractErrorMessage(err, 'Failed to save. Please try again.'));
		} finally {
			setDeciding(null);
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

	const documentEntries = Object.entries(data.documents) as [string, DocumentFile[] | undefined][];

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<DocPreviewModal state={preview} onClose={() => setPreview(PREVIEW_CLOSED)} />

			<div className="max-w-7xl mx-auto space-y-6">
				<div className="bg-gradient-to-r from-blue-900 via-blue-800 to-blue-600 rounded-2xl p-6 shadow-lg flex flex-col md:flex-row md:items-center md:justify-between gap-4">
					<div>
						<h1 className="text-white text-xl md:text-2xl font-bold">Review Prechecking Data</h1>
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
					{message && (
						<div
							className={`mb-4 p-3 rounded-lg text-sm border ${Object.keys(errors).length
								? 'bg-red-50 text-red-700 border-red-200'
								: 'bg-green-50 text-green-700 border-green-200'
								}`}
						>
							{message}
						</div>
					)}

					<section className="mb-8">
						<SectionHeader title="General Information" />
						<div className="grid md:grid-cols-2 gap-x-12">
							<div>
								<FieldRow label="Checking For" value={data.check_for === 'G' ? 'Guarantor' : 'Customer'} />
								<FieldRow label="Type" value="Individu" />
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
						{data.customer.citizen === 'WNA' ? (
							<SimpleIdentityFields
								name={data.customer.name.value}
								idCardNo={data.customer.idCardNo.value}
								nameLabel="Name"
								idLabel="Passport No."
								readOnly
							/>
						) : (
							<PersonOcrTable data={data.customer} readOnly />
						)}
					</section>

					<section className="mb-8 max-w-xs">
						<FieldRow label="Marital Status" value={data.maritalStatusLabel || '—'} />
					</section>

					{data.spouse && (
						<section className="mb-8">
							<SectionHeader title="Spouse" />
							{data.spouse.citizen === 'WNA' ? (
								<SimpleIdentityFields
									name={data.spouse.name.value}
									idCardNo={data.spouse.idCardNo.value}
									nameLabel="Spouse Name"
									idLabel="Spouse ID/Passport No."
									readOnly
								/>
							) : (
								<PersonOcrTable data={data.spouse} readOnly />
							)}
						</section>
					)}

					<section className="mb-8">
						<SectionHeader title="Documents" />
						<div className="space-y-3">
							{documentEntries.length === 0 && (
								<p className="text-sm text-gray-400 italic">No documents uploaded.</p>
							)}
							{documentEntries.map(([docType, files]) => (
								<div key={docType} className="flex items-start gap-4">
									<span className="text-sm text-gray-500 w-48 flex-shrink-0 pt-1">
										{DOCUMENT_TYPE_LABELS[docType] || docType}
									</span>
									<div className="flex flex-wrap gap-2">
										{(files || []).map((doc) => (
											<DocChip key={doc.id} name={doc.name} onPreview={() => handlePreview(doc)} />
										))}
									</div>
								</div>
							))}
						</div>
					</section>

					<section className="mb-8">
						<SectionHeader title="Reference" />
						<p className="text-sm text-gray-800">{data.is_carro === '1' ? 'Carro' : 'Non Carro'}</p>
					</section>

					<section className="mb-8">
						<SectionHeader title="Notes" />
						<p className="text-sm text-gray-800 whitespace-pre-wrap">{data.note || '—'}</p>
					</section>

					<section className="mb-8">
						<SectionHeader title="SIK Checking Data" />
						<SikTable rows={sikRows} lookups={data.lookups} canEdit={data.canEdit} errors={errors} onChange={setSikRows} />
					</section>

					<section className="mb-8">
						<SectionHeader title="Approval History" />
						<ApprovalHistory apless={apless} precheckingId={precheckingId} />
					</section>

					{data.canEdit && (
						<section className="mb-8">
							<SectionHeader title="Approval" />
							<label className="block text-sm font-medium text-gray-700 mb-1">Comment</label>
							<textarea
								className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
								rows={3}
								value={comment}
								onChange={(e) => setComment(e.target.value)}
							/>
							{errors.comment && <p className="text-xs text-red-600 mt-1">{errors.comment}</p>}
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
						{data.canEdit && (
							<>
								<button
									type="button"
									onClick={() => handleDecide('reject')}
									disabled={deciding !== null}
									className={`px-6 py-2 rounded-lg font-medium shadow-md transition-all bg-red-600 hover:bg-red-700 text-white ${deciding ? 'opacity-75 cursor-not-allowed' : ''
										}`}
								>
									{deciding === 'reject' ? 'Rejecting...' : 'Reject'}
								</button>
								<button
									type="button"
									onClick={() => handleDecide('approve')}
									disabled={deciding !== null}
									className={`bg-gradient-to-r from-blue-600 to-indigo-700 hover:from-blue-700 hover:to-indigo-800 text-white px-6 py-2 rounded-lg font-medium shadow-md transition-all ${deciding ? 'opacity-75 cursor-not-allowed' : ''
										}`}
								>
									{deciding === 'approve' ? 'Approving...' : 'Approve'}
								</button>
							</>
						)}
					</div>
				</div>
			</div>
		</div>
	);
};

export default CamRequestOnhandDetailPage;
