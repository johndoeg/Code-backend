import type { CheckFor, DocumentFile, DocumentType, PersonOcr } from './prechecking';

export interface ComboOption {
	value: string;
	label: string;
}

export interface Lookups {
	subjects: ComboOption[];
	relatedParties: ComboOption[];
	types: ComboOption[];
	boardTypes: ComboOption[];
	creditBureaus: ComboOption[];
	statuses: ComboOption[];
	slikScores: ComboOption[];
	appiScores: ComboOption[];
}

export interface SikRow {
	id: number | null;
	subject: string;
	relatedParty: string;
	keterangan: string;
	type: string;
	creditBureau: string;
	status: string;
	score: string;
	grade: string;
}

export const emptySikRow = (): SikRow => ({
	id: null,
	subject: '',
	relatedParty: '',
	keterangan: '',
	type: '',
	creditBureau: '',
	status: '',
	score: '',
	grade: '',
});

export interface OnhandDetailData {
	apless: string;
	prechecking_id: string;
	check_for: CheckFor;
	customer_type: 'PR';
	repeat_order: '0' | '1';
	is_carro: '0' | '1';
	note: string;
	last_checking_date: string;
	outstanding: number;
	maritalStatus: string;
	maritalStatusLabel: string;
	customer: PersonOcr;
	spouse: PersonOcr | null;
	documents: Partial<Record<DocumentType, DocumentFile[]>>;
	sik: SikRow[];
	canEdit: boolean;
	accessLevel: string;
	currentApprover: string;
	lookups: Lookups;
}

export type Decision = 'approve' | 'reject';

export interface DecidePayload {
	apless: string;
	prechecking_id: string;
	decision: Decision;
	comment: string;
	sik: SikRow[];
}

export interface DecideResponse {
	success: boolean;
	errors?: Record<string, string>;
	message?: string;
}
