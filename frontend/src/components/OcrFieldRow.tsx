import React from 'react';
import type { VerifiedFlag } from '../types/prechecking';

interface OcrFieldRowProps {
	label: string;
	value: string;
	confidence: string;
	verified: VerifiedFlag;
	readOnly?: boolean;
	valueDisabled?: boolean;
	locked?: boolean;
	lockedReason?: string;
	required?: boolean;
	error?: string;
	multiline?: boolean;
	onValueChange?: (v: string) => void;
}

const inputCls =
	'w-full border border-gray-300 rounded-md px-2 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:text-gray-600';

const LockIcon: React.FC = () => (
	<svg className="w-3 h-3 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
		<path
			strokeLinecap="round"
			strokeLinejoin="round"
			strokeWidth={2}
			d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
		/>
	</svg>
);

const OcrFieldRow: React.FC<OcrFieldRowProps> = ({
	label,
	value,
	confidence,
	verified,
	readOnly = false,
	valueDisabled,
	locked = false,
	lockedReason,
	required = false,
	error,
	multiline = false,
	onValueChange,
}) => {
	const isValueDisabled = valueDisabled ?? readOnly;

	return (
		<tr className="border-b border-gray-100">
			<td className="py-2 px-3 text-sm text-gray-700 whitespace-nowrap align-top">
				<span className="inline-flex items-center gap-1">
					{label} {required && <span className="text-red-500">*</span>}
					{locked && (
						<span title={lockedReason || 'This field cannot be edited'}>
							<LockIcon />
						</span>
					)}
				</span>
			</td>
			<td className="py-2 px-3 align-top">
				{multiline ? (
					<textarea
						className={inputCls}
						value={value}
						disabled={isValueDisabled}
						rows={2}
						onChange={(e) => onValueChange?.(e.target.value)}
					/>
				) : (
					<input
						type="text"
						className={inputCls}
						value={value}
						disabled={isValueDisabled}
						onChange={(e) => onValueChange?.(e.target.value)}
					/>
				)}
				{error && <p className="text-xs text-red-600 mt-1">{error}</p>}
			</td>
			<td className="py-2 px-3 align-top w-28">
				<input type="text" className={inputCls} value={confidence} disabled placeholder="e.g. 95%" readOnly />
			</td>
			<td className="py-2 px-3 align-top w-32">
				<select className={inputCls} value={verified} disabled>
					<option value="">-</option>
					<option value="True">Verified</option>
					<option value="False">Not verified</option>
				</select>
			</td>
		</tr>
	);
};

export default OcrFieldRow;