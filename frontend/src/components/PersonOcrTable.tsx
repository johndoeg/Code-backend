import React from 'react';
import OcrFieldRow from './OcrFieldRow';
import type { OcrField, PersonOcr } from '../types/prechecking';

export type OcrEditableKey = keyof Omit<PersonOcr, 'citizen' | 'photo' | 'signature'>;

const FIELD_DEFS: { key: OcrEditableKey; label: string; multiline?: boolean }[] = [
	{ key: 'idCardNo', label: 'NIK' },
	{ key: 'name', label: 'Nama' },
	{ key: 'pob', label: 'Tempat Lahir' },
	{ key: 'dob', label: 'Tanggal Lahir' },
	{ key: 'gender', label: 'Jenis Kelamin' },
	{ key: 'bloodType', label: 'Golongan Darah' },
	{ key: 'address', label: 'Alamat', multiline: true },
	{ key: 'rt', label: 'RT' },
	{ key: 'rw', label: 'RW' },
	{ key: 'subdistrict', label: 'Kelurahan/Desa' },
	{ key: 'district', label: 'Kecamatan' },
	{ key: 'city', label: 'Kota/Kabupaten' },
	{ key: 'province', label: 'Provinsi' },
	{ key: 'religion', label: 'Agama' },
	{ key: 'job', label: 'Pekerjaan' },
];

const NO_VERIFICATION: OcrEditableKey[] = ['bloodType', 'religion'];
const VALUE_LOCKED: OcrEditableKey[] = ['idCardNo'];

interface PersonOcrTableProps {
	data: PersonOcr;
	readOnly?: boolean;
	errors?: Partial<Record<OcrEditableKey, string>>;
	onFieldChange?: (key: OcrEditableKey, field: OcrField) => void;
}

const PersonOcrTable: React.FC<PersonOcrTableProps> = ({ data, readOnly = false, errors, onFieldChange }) => {
	return (
		<div className="overflow-x-auto rounded-lg border border-gray-200">
			<table className="w-full">
				<thead className="bg-gray-50">
					<tr>
						<th className="py-2 px-3 text-left text-xs font-medium text-gray-500 uppercase">Field</th>
						<th className="py-2 px-3 text-left text-xs font-medium text-gray-500 uppercase">Value</th>
						<th className="py-2 px-3 text-left text-xs font-medium text-gray-500 uppercase">Confidence</th>
						<th className="py-2 px-3 text-left text-xs font-medium text-gray-500 uppercase">Dukcapil</th>
					</tr>
				</thead>
				<tbody>
					{FIELD_DEFS.map(({ key, label, multiline }) => {
						const field = data[key] as OcrField;
						const verifiable = !NO_VERIFICATION.includes(key);
						const valueLocked = VALUE_LOCKED.includes(key);
						return (
							<OcrFieldRow
								key={key}
								label={label}
								value={field.value}
								confidence={field.confidence}
								verified={verifiable ? field.verified : ''}
								readOnly={readOnly}
								valueDisabled={readOnly || valueLocked}
								locked={!readOnly && valueLocked}
								lockedReason="NIK can't be edited here — it's a fixed identifier from the scanned document."
								multiline={multiline}
								error={errors?.[key]}
								onValueChange={(v) => onFieldChange?.(key, { ...field, value: v })}
							/>
						);
					})}
				</tbody>
			</table>
		</div>
	);
};

export default PersonOcrTable;