import api from './axiosInstance';
import type {
	CamEditPrData,
	CamEditPrSubmitPayload,
	DocumentFile,
	DocumentType,
	SubmitResponse,
} from '../types/prechecking';
import { unwrapApiError } from '../utils/prechecking/errorMessage';

const BASE = '/Prechecking/EditPR';

export async function fetchCamEditPrData(
	apless: string,
	precheckingId: string,
): Promise<CamEditPrData> {
	const res = await api.get(`${BASE}/get-data`, {
		params: { apless, prechecking_id: precheckingId },
	});
	return res.data;
}

export async function submitCamEditPr(
	payload: CamEditPrSubmitPayload,
): Promise<SubmitResponse> {
	return unwrapApiError(async () => {
		const res = await api.post(`${BASE}/submit`, payload);
		return res.data;
	});
}

export interface UploadResponse {
	success: boolean;
	document?: DocumentFile;
	message?: string;
}

export async function uploadCamDocument(
	apless: string,
	precheckingId: string,
	documentType: DocumentType,
	file: File,
): Promise<UploadResponse> {
	const form = new FormData();
	form.append('apless', apless);
	form.append('prechecking_id', precheckingId);
	form.append('document_type', documentType);
	form.append('file', file);

	return unwrapApiError(async () => {
		const res = await api.post(`${BASE}/upload-document`, form, {
			headers: { 'Content-Type': 'multipart/form-data' },
		});
		return res.data;
	});
}

export interface DeleteResponse {
	success: boolean;
	message?: string;
}

export async function deleteCamDocument(
	precheckingId: string,
	documentType: DocumentType,
	customerDocumentId?: number,
): Promise<DeleteResponse> {
	return unwrapApiError(async () => {
		const res = await api.post(`${BASE}/delete-document`, {
			prechecking_id: precheckingId,
			document_type: documentType,
			customer_document_id: customerDocumentId,
		});
		return res.data;
	});
}

export async function getDocumentDownloadUrl(
	awsKey: string,
	fileName: string,
): Promise<string> {
	const res = await api.get(`${BASE}/aws-download`, {
		params: { aws_key: awsKey, file_name: fileName },
	});
	return res.data.url;
}