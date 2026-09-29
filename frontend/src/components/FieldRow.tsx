import React from 'react';

const FieldRow: React.FC<{ label: string; value?: React.ReactNode }> = ({ label, value }) => (
	<div className="flex gap-4 py-2 border-b border-gray-50 last:border-0">
		<span className="text-gray-500 text-sm w-48 flex-shrink-0">{label}</span>
		<span className="text-gray-800 text-sm font-medium">{value ?? '—'}</span>
	</div>
);

export default FieldRow;