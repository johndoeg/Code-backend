export type Citizen = 'WNI' | 'WNA' | '';
export type CheckFor = 'C' | 'G';
export type MaritalStatusCode = 'S' | 'M' | 'D' | 'O' | 'P' | '';
export type VerifiedFlag = 'True' | 'False' | '';

export interface OcrField {
	value: string;
	confidence: string;
	verified: VerifiedFlag;
}

export interface PersonOcr {
	citizen: Citizen;
	idCardNo: OcrField;
	name: OcrField;
	pob: OcrField;
	dob: OcrField;
	gender: OcrField;
	bloodType: OcrField;
	address: OcrField;
	rt: OcrField;
	rw: OcrField;
	subdistrict: OcrField;
	district: OcrField;
	city: OcrField;
	province: OcrField;
	religion: OcrField;
	job: OcrField;
	photo: string;
	signature: string;
}

export interface DocumentFile {
	id: number;
	name: string;
	awsKey: string;
}

export type DocumentType =
	| 'cust-ktp'
	| 'cust-spouse-ktp'
	| 'cust-kk'
	| 'cust-npwp'
	| 'cust-marriage-or-death-statement'
	| 'cust-kitas'
	| 'cust-spouse-kitas'
	| 'cust-wna-spouse-ktp'
	| 'guarantor-ktp'
	| 'guarantor-spouse-ktp'
	| 'guarantor-kk'
	| 'guarantor-npwp'
	| 'guarantor-marriage-or-death-statement'
	| 'guarantor-kitas'
	| 'guarantor-spouse-kitas'
	| 'guarantor-wna-spouse-ktp';

export interface SikRow {
	subject: string;
	creditBureau: string;
	status: string;
	score: string;
	grade: string;
}

export interface SpouseData {
	citizenType: Citizen;
	ocr: PersonOcr | null;
	wnaName: string;
	wnaIdCardNo: string;
}

export interface CamEditPrData {
	apless: string;
	prechecking_id: string;
	check_for: CheckFor;
	customer_type: 'PR';
	repeat_order: '0' | '1';
	is_carro: '0' | '1';
	note: string;
	last_checking_date: string;
	outstanding: number;
	maritalStatus: MaritalStatusCode;
	customer: PersonOcr;
	spouse: SpouseData | null;
	sik: SikRow[];
	documents: Partial<Record<DocumentType, DocumentFile[]>>;
}

export interface PersonOcrEditPayload {
	idCardNo: OcrField;
	name: OcrField;
	pob: OcrField;
	dob: OcrField;
	gender: OcrField;
	bloodType: OcrField;
	address: OcrField;
	rt: OcrField;
	rw: OcrField;
	subdistrict: OcrField;
	district: OcrField;
	city: OcrField;
	province: OcrField;
	religion: OcrField;
	job: OcrField;
}

export interface CamEditPrSubmitPayload {
	apless: string;
	prechecking_id: string;
	repeat_order: '0' | '1';
	is_carro: '0' | '1';
	note: string;
	marital_status: MaritalStatusCode;
	customer?: PersonOcrEditPayload;
	spouse: {
		citizenType: Citizen;
		ocr?: PersonOcrEditPayload;
		wnaName?: string;
		wnaIdCardNo?: string;
	} | null;
}

export interface FieldErrors {
	[fieldKey: string]: string;
}

export interface SubmitResponse {
	success: boolean;
	errors?: FieldErrors;
	message?: string;
}