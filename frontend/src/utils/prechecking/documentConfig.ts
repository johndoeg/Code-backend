import type { CheckFor, Citizen, DocumentType, MaritalStatusCode } from '../../types/prechecking';

export interface DocumentSlot {
	type: DocumentType;
	label: string;
	required: boolean;
	multiple: boolean;
	group: 'identity' | 'marital';
}

export function getSpouseDocumentType(
	checkFor: CheckFor,
	customerCitizen: Citizen,
	spouseCitizen: Citizen,
): DocumentType {
	const prefix = checkFor === 'G' ? 'guarantor' : 'cust';
	if (spouseCitizen === 'WNA') {
		return `${prefix}-spouse-kitas` as DocumentType;
	}
	if (customerCitizen === 'WNA') {
		return `${prefix}-wna-spouse-ktp` as DocumentType;
	}
	return `${prefix}-spouse-ktp` as DocumentType;
}

export function buildDocumentConfig(
	checkFor: CheckFor,
	maritalStatus: MaritalStatusCode,
	customerCitizen: Citizen,
	spouseCitizen: Citizen | undefined,
): DocumentSlot[] {
	const prefix = checkFor === 'G' ? 'guarantor' : 'cust';
	const isMarried = maritalStatus === 'M' || maritalStatus === 'O';
	const needsMaritalCertificate = maritalStatus !== '' && maritalStatus !== 'S';

	const config: DocumentSlot[] = [
		{ type: `${prefix}-ktp` as DocumentType, label: 'ID Card (KTP)', required: false, multiple: false, group: 'identity' },
		{ type: `${prefix}-kk` as DocumentType, label: 'Family Card (KK)', required: false, multiple: true, group: 'identity' },
		{ type: `${prefix}-npwp` as DocumentType, label: 'Tax ID (NPWP)', required: false, multiple: true, group: 'identity' },
	];

	if (customerCitizen === 'WNA') {
		config.push({ type: `${prefix}-kitas` as DocumentType, label: 'KITAS', required: false, multiple: false, group: 'identity' });
	}

	if (needsMaritalCertificate) {
		config.push({
			type: `${prefix}-marriage-or-death-statement` as DocumentType,
			label: 'Akta Cerai / Akta Kematian',
			required: false,
			multiple: true,
			group: 'marital',
		});
	}

	if (isMarried && spouseCitizen) {
		const spouseDocType = getSpouseDocumentType(checkFor, customerCitizen, spouseCitizen);
		config.push({
			type: spouseDocType,
			label: spouseCitizen === 'WNA' ? "Spouse's KITAS" : "Spouse's ID Card (KTP)",
			required: true,
			multiple: false,
			group: 'marital',
		});
	}

	return config;
}