import React, { useCallback, useRef, useState } from 'react';
import type { DocumentFile, DocumentType } from '../types/prechecking';
import { deleteCamDocument, uploadCamDocument } from '../api/editPR';
import { extractErrorMessage } from '../utils/prechecking/errorMessage';
import DocChip from './DocChip';

interface DocumentUploadFieldProps {
	label: string;
	apless: string;
	precheckingId: string;
	documentType: DocumentType;
	files: DocumentFile[];
	required?: boolean;
	multiple?: boolean;
	accept?: string;
	error?: string;
	onChanged: (files: DocumentFile[]) => void;
	onPreview: (doc: DocumentFile) => void;
}

const DEFAULT_ACCEPT = '.jpg,.jpeg,.png,.gif,.bmp,.heic,.heif,.pdf,.xlsx,.docx';

const UploadCloudIcon: React.FC = () => (
	<svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
		<path
			strokeLinecap="round"
			strokeLinejoin="round"
			strokeWidth={1.5}
			d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M12 12v9m0-9l-3.5 3.5M12 12l3.5 3.5"
		/>
	</svg>
);

const CheckBadgeIcon: React.FC = () => (
	<svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
		<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
	</svg>
);

const AlertIcon: React.FC = () => (
	<svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
		<path
			strokeLinecap="round"
			strokeLinejoin="round"
			strokeWidth={2.5}
			d="M12 9v3.75m0 3.75h.007M4.318 18.849A2 2 0 006.096 20h11.808a2 2 0 001.778-2.972l-5.904-10.86a2 2 0 00-3.556 0L4.318 17.03a2 2 0 000 1.819z"
		/>
	</svg>
);

const DocumentUploadField: React.FC<DocumentUploadFieldProps> = ({
	label,
	apless,
	precheckingId,
	documentType,
	files,
	required = false,
	multiple = false,
	accept = DEFAULT_ACCEPT,
	error,
	onChanged,
	onPreview,
}) => {
	const inputRef = useRef<HTMLInputElement>(null);
	const [uploading, setUploading] = useState(false);
	const [deletingId, setDeletingId] = useState<number | null>(null);
	const [localError, setLocalError] = useState<string | null>(null);
	const [dragActive, setDragActive] = useState(false);

	const uploadFile = useCallback(
		async (file: File) => {
			setUploading(true);
			setLocalError(null);
			try {
				const res = await uploadCamDocument(apless, precheckingId, documentType, file);
				if (res.success && res.document) {
					onChanged(multiple ? [...files, res.document] : [res.document]);
				} else {
					setLocalError(res.message || 'Upload failed');
				}
			} catch (err) {
				setLocalError(extractErrorMessage(err, 'Upload failed. Please try again.'));
			} finally {
				setUploading(false);
			}
		},
		[apless, precheckingId, documentType, files, multiple, onChanged],
	);

	const handleFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
		const file = e.target.files?.[0];
		if (file) await uploadFile(file);
		if (inputRef.current) inputRef.current.value = '';
	};

	const handleDrop = async (e: React.DragEvent<HTMLLabelElement>) => {
		e.preventDefault();
		setDragActive(false);
		if (uploading) return;
		const file = e.dataTransfer.files?.[0];
		if (file) await uploadFile(file);
	};

	const handleDelete = async (doc: DocumentFile) => {
		if (!window.confirm('Are you sure to delete this record?')) return;
		setDeletingId(doc.id);
		setLocalError(null);
		try {
			const res = await deleteCamDocument(precheckingId, documentType, doc.id);
			if (res.success) {
				onChanged(files.filter((f) => f.id !== doc.id));
			} else {
				setLocalError(res.message || 'Delete failed');
			}
		} catch (err) {
			setLocalError(extractErrorMessage(err, 'Delete failed. Please try again.'));
		} finally {
			setDeletingId(null);
		}
	};

	const canAddMore = files.length === 0;
	const isComplete = files.length > 0;
	const isMissingRequired = required && !isComplete;

	const cardBorderCls = isMissingRequired
		? 'border-red-200 bg-red-50/40'
		: isComplete
			? 'border-green-200 bg-green-50/30'
			: 'border-gray-200 bg-white';

	return (
		<div className={`rounded-xl border p-4 transition-colors ${cardBorderCls}`}>
			<div className="flex items-center justify-between gap-2 mb-3">
				<span className="text-sm font-medium text-gray-800">{label}</span>
				{isComplete ? (
					<span className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wide text-green-700 bg-green-100 px-2 py-0.5 rounded-full flex-shrink-0">
						<CheckBadgeIcon /> Uploaded
					</span>
				) : required ? (
					<span className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wide text-red-700 bg-red-100 px-2 py-0.5 rounded-full flex-shrink-0">
						<AlertIcon /> Required
					</span>
				) : (
					<span className="text-[11px] font-medium uppercase tracking-wide text-gray-400 flex-shrink-0">Optional</span>
				)}
			</div>

			{files.length > 0 && (
				<div className="flex flex-wrap gap-2 mb-3">
					{files.map((doc) => (
						<DocChip
							key={doc.id}
							name={doc.name}
							onPreview={() => onPreview(doc)}
							onDelete={() => handleDelete(doc)}
							deleting={deletingId === doc.id}
						/>
					))}
				</div>
			)}

			{canAddMore && (
				<label
					onDragOver={(e) => {
						e.preventDefault();
						setDragActive(true);
					}}
					onDragLeave={() => setDragActive(false)}
					onDrop={handleDrop}
					className={`flex items-center justify-center gap-2 border-2 border-dashed rounded-lg py-3 px-3 cursor-pointer transition-colors text-center ${dragActive ? 'border-blue-400 bg-blue-50' : 'border-gray-200 hover:border-blue-300 hover:bg-gray-50'
						} ${uploading ? 'opacity-60 pointer-events-none' : ''}`}
				>
					<span className="text-gray-400">
						<UploadCloudIcon />
					</span>
					<span className="text-xs text-gray-500">
						{uploading ? 'Uploading…' : 'Click to upload or drag & drop'}
					</span>
					<input
						ref={inputRef}
						type="file"
						accept={accept}
						disabled={uploading}
						onChange={handleFileSelected}
						className="hidden"
					/>
				</label>
			)}

			{(localError || error) && <p className="text-xs text-red-600 mt-2">{localError || error}</p>}
		</div>
	);
};

export default DocumentUploadField;