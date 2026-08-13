import api from './axiosInstance';
import type { DecidePayload, DecideResponse, OnhandDetailData } from '../types/onhandDetail';
import { unwrapApiError } from '../utils/prechecking/errorMessage';

const BASE = '/Prechecking/OnhandDetail';

export async function fetchOnhandDetailData(
	apless: string,
	precheckingId: string,
): Promise<OnhandDetailData> {
	const res = await api.get(`${BASE}/get-data`, {
		params: { apless, prechecking_id: precheckingId },
	});
	return res.data;
}

export async function decideOnhandDetail(payload: DecidePayload): Promise<DecideResponse> {
	return unwrapApiError(async () => {
		const res = await api.post(`${BASE}/decide`, payload);
		return res.data;
	});
}

export async function getReviewDocumentDownloadUrl(
	awsKey: string,
	fileName: string,
): Promise<string> {
	const res = await api.get('/Prechecking/View/aws-download', {
		params: { aws_key: awsKey, file_name: fileName },
	});
	return res.data.url;
}
