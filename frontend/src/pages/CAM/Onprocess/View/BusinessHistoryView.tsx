import { useEffect, useState } from 'react';
import api from '../../../../api/axiosInstance';
import type { CamCtx } from './CamViewTabs';

interface HistoryRow {
	from: string;
	until: string;
	company: string;
	company_address: string;
	kabupaten: string;
	propinsi: string;
	postcode: string;
	employee_id: string;
	position: string;
	phone: string;
}

interface BusinessHistoryData {
	lessee_cat: string;
	show_employee_id: boolean;
	history: HistoryRow[];
	no_data: boolean;
}

function NoDataCard() {
	return (
		<div className="rounded-2xl bg-white p-12 text-center shadow">
			<p className="text-2xl font-bold text-red-600">NO DATA</p>
		</div>
	);
}

export default function BusinessHistoryView({ ctx }: { ctx: CamCtx }) {
	const [data, setData] = useState<BusinessHistoryData | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		let active = true;
		setLoading(true);
		setError(null);
		api
			.get('/CAM/api/view/business-history', { params: { apless: ctx.apless } })
			.then((res) => {
				if (active) setData(res.data);
			})
			.catch(() => {
				if (active) setError('Failed to load business history.');
			})
			.finally(() => {
				if (active) setLoading(false);
			});
		return () => {
			active = false;
		};
	}, [ctx.apless]);

	if (loading) {
		return (
			<div className="rounded-2xl bg-white p-8 text-center text-sm text-slate-500 shadow">
				Loading business history…
			</div>
		);
	}
	if (error || !data) {
		return (
			<div className="rounded-2xl bg-white p-8 text-center text-sm text-red-500 shadow">
				{error || 'No data found.'}
			</div>
		);
	}
	if (data.no_data) {
		return <NoDataCard />;
	}

	return (
		<div className="overflow-hidden rounded-2xl bg-white shadow">
			<div className="border-b border-slate-100 bg-slate-50 px-5 py-3">
				<h2 className="text-sm font-semibold text-slate-700">Business / Job History</h2>
			</div>
			<div className="overflow-x-auto p-5">
				<table className="w-full min-w-[900px] text-sm">
					<thead>
						<tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-400">
							<th className="py-2 pr-3">No.</th>
							<th className="py-2 pr-3">From</th>
							<th className="py-2 pr-3">Until</th>
							<th className="py-2 pr-3">Company Name</th>
							<th className="py-2 pr-3">Company Address</th>
							<th className="py-2 pr-3">District / City</th>
							<th className="py-2 pr-3">Province</th>
							<th className="py-2 pr-3">Post Code</th>
							{data.show_employee_id && <th className="py-2 pr-3">Employee ID No.</th>}
							<th className="py-2 pr-3">Position</th>
							<th className="py-2">Phone</th>
						</tr>
					</thead>
					<tbody>
						{data.history.map((row, i) => (
							<tr key={i} className="border-b border-slate-100 last:border-0">
								<td className="py-2 pr-3 text-slate-500">{i + 1}</td>
								<td className="py-2 pr-3">{row.from}</td>
								<td className="py-2 pr-3">{row.until}</td>
								<td className="py-2 pr-3">{row.company}</td>
								<td className="py-2 pr-3">{row.company_address}</td>
								<td className="py-2 pr-3">{row.kabupaten}</td>
								<td className="py-2 pr-3">{row.propinsi}</td>
								<td className="py-2 pr-3">{row.postcode}</td>
								{data.show_employee_id && <td className="py-2 pr-3">{row.employee_id}</td>}
								<td className="py-2 pr-3">{row.position}</td>
								<td className="py-2">{row.phone}</td>
							</tr>
						))}
					</tbody>
				</table>
			</div>
		</div>
	);
}