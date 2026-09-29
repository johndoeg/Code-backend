import React, { useRef, useState } from 'react';
import { DocumentFile, DocumentType } from '../../../types/prechecking';
import { deleteCamDocument, getDocumentDownloadUrl, uploadCamDocument } from '../../../api/prechecking/editPr';

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
}

const DEFAULT_ACCEPT = '.png,.jpg,.jpeg,.pdf,.tiff';

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
}) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const handleFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setBusy(true);
    setLocalError(null);
    try {
      const res = await uploadCamDocument(apless, precheckingId, documentType, file);
      if (res.success && res.document) {
        onChanged(multiple ? [...files, res.document] : [res.document]);
      } else {
        setLocalError(res.message || 'Upload failed');
      }
    } catch {
      setLocalError('Upload failed. Please try again.');
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = '';
    }
  };

  const handleView = async (doc: DocumentFile) => {
    try {
      const url = await getDocumentDownloadUrl(doc.awsKey, doc.name);
      window.open(url, '_blank', 'noopener,noreferrer');
    } catch {
      setLocalError('Could not open file.');
    }
  };

  const handleDelete = async (doc: DocumentFile) => {
    if (!window.confirm('Are you sure to delete this record?')) return;
    setBusy(true);
    setLocalError(null);
    try {
      const res = await deleteCamDocument(precheckingId, documentType, doc.id);
      if (res.success) {
        onChanged(files.filter((f) => f.id !== doc.id));
      } else {
        setLocalError(res.message || 'Delete failed');
      }
    } catch {
      setLocalError('Delete failed. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  const canAddMore = multiple || files.length === 0;

  return (
    <div className="mb-4">
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {label} {required && <span className="text-red-500">*</span>}
      </label>

      {canAddMore && (
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          disabled={busy}
          onChange={handleFileSelected}
          className="block w-full text-sm text-gray-600 border border-gray-300 rounded-lg cursor-pointer file:mr-3 file:py-1.5 file:px-3 file:border-0 file:bg-blue-50 file:text-blue-700 file:rounded-lg"
        />
      )}

      {(localError || error) && <p className="text-xs text-red-600 mt-1">{localError || error}</p>}

      {files.length > 0 && (
        <ul className="mt-2 space-y-1">
          {files.map((doc) => (
            <li key={doc.id} className="flex items-center gap-3 text-sm">
              <span className="text-gray-700 truncate max-w-xs">{doc.name}</span>
              <button type="button" onClick={() => handleView(doc)} className="text-blue-600 hover:underline text-xs">
                View
              </button>
              <button
                type="button"
                onClick={() => handleDelete(doc)}
                disabled={busy}
                className="text-red-600 hover:underline text-xs disabled:opacity-50"
              >
                Delete
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default DocumentUploadField;
