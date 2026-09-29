import React, { useEffect, useState } from 'react';
import api from '../api/axiosInstance';

interface ApprovalHistoryRow {
	date: string;
	action: string;
	by: string;
	remarks: string;
}

interface ApprovalHistoryProps {
	apless: string;
	precheckingId: string;
}

const ApprovalHistory: React.FC<ApprovalHistoryProps> = ({ apless, precheckingId }) => {
	const [rows, setRows] = useState<ApprovalHistoryRow[]>([]);
	const [loading, setLoading] = useState(true);

	useEffect(() => {
		api
			.get('/Prechecking/View/approval-history', { params: { apless, prechecking_id: precheckingId } })
			.then((r) => setRows(r.data))
			.catch(() => setRows([]))
			.finally(() => setLoading(false));
	}, [apless, precheckingId]);

	if (loading) {
		return (
			<div className="flex justify-center py-12">
				<svg className="animate-spin h-8 w-8 text-blue-600" fill="none" viewBox="0 0 24 24">
					<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
					<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
				</svg>
			</div>
		);
	}

	if (!rows.length) {
		return (
			<div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-12 text-center text-gray-400">
				No approval history found.
			</div>
		);
	}

	return (
		<div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
			<table className="w-full text-sm">
				<thead className="bg-gray-50">
					<tr>
						{['Date', 'Action', 'By', 'Remarks'].map((h) => (
							<th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
								{h}
							</th>
						))}
					</tr>
				</thead>
				<tbody className="divide-y divide-gray-100">
					{rows.map((row, i) => {
						const actionColor =
							row.action === 'approve' ? 'bg-green-100 text-green-700' :
								row.action === 'reject' ? 'bg-red-100 text-red-700' :
									row.action === 'submit' ? 'bg-blue-100 text-blue-700' :
										'bg-gray-100 text-gray-600';
						return (
							<tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
								<td className="px-4 py-3 whitespace-nowrap text-gray-500">{row.date}</td>
								<td className="px-4 py-3">
									<span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${actionColor}`}>
										{row.action}
									</span>
								</td>
								<td className="px-4 py-3 text-gray-700">{row.by}</td>
								<td className="px-4 py-3 text-gray-600">{row.remarks}</td>
							</tr>
						);
					})}
				</tbody>
			</table>
		</div>
	);
};

export default ApprovalHistory;
