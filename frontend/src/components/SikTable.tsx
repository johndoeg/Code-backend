import React from 'react';
import type { Lookups, SikRow } from '../types/onhandDetail';
import { emptySikRow } from '../types/onhandDetail';
import { computeGrade } from '../utils/prechecking/grade';

interface SikTableProps {
	rows: SikRow[];
	lookups: Lookups;
	canEdit: boolean;
	errors?: Record<string, string>;
	onChange: (rows: SikRow[]) => void;
}

const controlCls =
	'w-full bg-white border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:text-gray-500';

const SikTable: React.FC<SikTableProps> = ({ rows, lookups, canEdit, errors, onChange }) => {
	const applyPatch = (index: number, patch: Partial<SikRow>) => {
		const merged: SikRow = { ...rows[index], ...patch };

		if (merged.status === '' || merged.status === 'N/A') {
			merged.score = '';
			merged.grade = '';
		} else {
			const { grade } = computeGrade(merged.creditBureau, merged.score, merged.subject, merged.type);
			merged.grade = grade;
		}

		const next = rows.map((r, i) => (i === index ? merged : r));
		onChange(next);
	};

	const addRow = () => onChange([...rows, emptySikRow()]);
	const removeRow = (index: number) => onChange(rows.filter((_, i) => i !== index));

	const scoreDisabled = (row: SikRow) => !canEdit || row.status === '' || row.status === 'N/A';

	const renderScoreControl = (row: SikRow, index: number) => {
		if (row.creditBureau === 'SLIK') {
			return (
				<select
					className={controlCls}
					value={row.score}
					disabled={scoreDisabled(row)}
					onChange={(e) => applyPatch(index, { score: e.target.value })}
				>
					<option value="">Select</option>
					{lookups.slikScores.map((o) => (
						<option key={o.value} value={o.value}>{o.label}</option>
					))}
				</select>
			);
		}
		if (row.creditBureau === 'APPI') {
			return (
				<select
					className={controlCls}
					value={row.score}
					disabled={scoreDisabled(row)}
					onChange={(e) => applyPatch(index, { score: e.target.value })}
				>
					<option value="">Select</option>
					{lookups.appiScores.map((o) => (
						<option key={o.value} value={o.value}>{o.label}</option>
					))}
				</select>
			);
		}
		return (
			<input
				type="text"
				inputMode="numeric"
				className={controlCls}
				value={row.score}
				disabled={scoreDisabled(row)}
				onChange={(e) => applyPatch(index, { score: e.target.value.replace(/\D/g, '') })}
			/>
		);
	};

	return (
		<div className="space-y-4">
			{rows.length === 0 && <p className="text-sm text-gray-400 italic">No SIK checking data yet.</p>}

			{rows.map((row, index) => {
				const typeOptions =
					row.relatedParty === 'Director' || row.relatedParty === 'Commissioner'
						? lookups.boardTypes
						: lookups.types;
				const { scoreError } = computeGrade(row.creditBureau, row.score, row.subject, row.type);

				return (
					<div key={row.id ?? `new-${index}`} className="rounded-xl border border-gray-200 p-4">
						<div className="flex justify-between items-start mb-3">
							<span className="text-xs font-semibold uppercase tracking-wide text-gray-400">Record {index + 1}</span>
							{canEdit && (
								<button type="button" onClick={() => removeRow(index)} className="text-xs text-red-600 hover:underline">
									Delete
								</button>
							)}
						</div>

						<div className="grid grid-cols-1 md:grid-cols-3 gap-3">
							<div>
								<label className="block text-xs text-gray-500 mb-1">Subject</label>
								<select
									className={controlCls}
									value={row.subject}
									disabled={!canEdit}
									onChange={(e) => applyPatch(index, { subject: e.target.value, relatedParty: '', keterangan: '', type: '' })}
								>
									<option value="">Select</option>
									{lookups.subjects.map((o) => (
										<option key={o.value} value={o.value}>{o.label}</option>
									))}
								</select>
								{errors?.[`sik.${index}.subject`] && (
									<p className="text-xs text-red-600 mt-1">{errors[`sik.${index}.subject`]}</p>
								)}
							</div>

							{row.subject === 'RP' && (
								<div>
									<label className="block text-xs text-gray-500 mb-1">Related Party</label>
									<select
										className={controlCls}
										value={row.relatedParty}
										disabled={!canEdit}
										onChange={(e) => applyPatch(index, { relatedParty: e.target.value, keterangan: '', type: '' })}
									>
										<option value="">Select</option>
										{lookups.relatedParties.map((o) => (
											<option key={o.value} value={o.value}>{o.label}</option>
										))}
									</select>
								</div>
							)}

							{row.relatedParty === 'Other' && (
								<div>
									<label className="block text-xs text-gray-500 mb-1">Description</label>
									<input
										type="text"
										className={controlCls}
										value={row.keterangan}
										disabled={!canEdit}
										onChange={(e) => applyPatch(index, { keterangan: e.target.value })}
									/>
								</div>
							)}

							{row.relatedParty !== '' && (
								<div>
									<label className="block text-xs text-gray-500 mb-1">Type</label>
									<select
										className={controlCls}
										value={row.type}
										disabled={!canEdit}
										onChange={(e) => applyPatch(index, { type: e.target.value })}
									>
										<option value="">Select</option>
										{typeOptions.map((o) => (
											<option key={o.value} value={o.value}>{o.label}</option>
										))}
									</select>
									{errors?.[`sik.${index}.type`] && (
										<p className="text-xs text-red-600 mt-1">{errors[`sik.${index}.type`]}</p>
									)}
								</div>
							)}

							<div>
								<label className="block text-xs text-gray-500 mb-1">Credit Bureau</label>
								<select
									className={controlCls}
									value={row.creditBureau}
									disabled={!canEdit}
									onChange={(e) => applyPatch(index, { creditBureau: e.target.value, score: '' })}
								>
									<option value="">Select</option>
									{lookups.creditBureaus.map((o) => (
										<option key={o.value} value={o.value}>{o.label}</option>
									))}
								</select>
								{errors?.[`sik.${index}.creditBureau`] && (
									<p className="text-xs text-red-600 mt-1">{errors[`sik.${index}.creditBureau`]}</p>
								)}
							</div>

							<div>
								<label className="block text-xs text-gray-500 mb-1">Status</label>
								<select
									className={controlCls}
									value={row.status}
									disabled={!canEdit}
									onChange={(e) => applyPatch(index, { status: e.target.value })}
								>
									<option value="">Select</option>
									{lookups.statuses.map((o) => (
										<option key={o.value} value={o.value}>{o.label}</option>
									))}
								</select>
								{errors?.[`sik.${index}.status`] && (
									<p className="text-xs text-red-600 mt-1">{errors[`sik.${index}.status`]}</p>
								)}
							</div>

							<div>
								<label className="block text-xs text-gray-500 mb-1">Score</label>
								{renderScoreControl(row, index)}
								{scoreError && <p className="text-xs text-red-600 mt-1">{scoreError}</p>}
							</div>

							<div>
								<label className="block text-xs text-gray-500 mb-1">Grade</label>
								<input type="text" className={controlCls} value={row.grade} disabled readOnly />
							</div>
						</div>
					</div>
				);
			})}

			{canEdit && (
				<button
					type="button"
					onClick={addRow}
					className="text-sm font-medium text-blue-600 hover:text-blue-800 flex items-center gap-1"
				>
					+ Add SIK Record
				</button>
			)}
		</div>
	);
};

export default SikTable;
