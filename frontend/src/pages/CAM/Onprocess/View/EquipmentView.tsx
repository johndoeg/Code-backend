import React, { useEffect, useState } from 'react';
import api from '../../../../api/axiosInstance';
import type { CamCtx } from './CamViewTabs';

interface EquipmentDetail {
	brand: string;
	show_stnk_valid_date: boolean;
	stnk_valid_date: string;
	type: string;
	chassis: string;
	model_karoseri: string;
	engine: string;
	wheels: string;
	police_no: string;
	year_condition: string;
	color: string;
	type_of_equipment: string;
	user_usage: string;
	dealer_name: string;
	vehicle_purpose: string;
	show_financing_purpose: boolean;
	financing_purpose: string;
	dealer_address: string;
	parking_address: string;
	red_code_gps: string;
	zip_code: string;
	karoseri_name: string | null;
	karoseri_address: string | null;
	accessories_name: string | null;
	accessories_address: string | null;
	other_name: string | null;
	other_address: string | null;
	bpkb_no: string;
	bpkb_name_type: string;
	show_family_status: boolean;
	family_status: string;
	relation: string;
	bpkb_address: string;
	area: string;
	notary_name: string;
	fdc_area: string;
}

interface FinancingHistoryRow {
	lease_no: string;
	lessee_no: string;
	lessee_nm: string;
	otr: number;
	net_finance: number;
	disburse_date: string;
	finish_date: string;
}

interface EquipmentData {
	no_data: boolean;
	title: string;
	detail: EquipmentDetail;
	financing_history: FinancingHistoryRow[];
}

function fmt(n: number): string {
	return Math.round(n).toLocaleString('en-US');
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
	return (
		<div className="mb-4 overflow-hidden rounded-2xl bg-white shadow">
			<div className="border-b border-slate-100 bg-slate-50 px-5 py-3">
				<h2 className="text-sm font-semibold text-slate-700">{title}</h2>
			</div>
			<div className="overflow-x-auto p-5">{children}</div>
		</div>
	);
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
	return (
		<div className="border-b border-slate-100 py-2 last:border-0">
			<dt className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</dt>
			<dd className="mt-0.5 text-sm text-slate-700">{value || '-'}</dd>
		</div>
	);
}

function NoDataCard() {
	return (
		<div className="rounded-2xl bg-white p-12 text-center shadow">
			<p className="text-2xl font-bold text-red-600">NO DATA</p>
		</div>
	);
}

export default function EquipmentView({ ctx }: { ctx: CamCtx }) {
	const [data, setData] = useState<EquipmentData | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		let active = true;
		setLoading(true);
		setError(null);
		api
			.get('/CAM/api/view/equipment', { params: { applno: ctx.applno, fin_type: ctx.finType } })
			.then((res) => {
				if (active) setData(res.data);
			})
			.catch(() => {
				if (active) setError('Failed to load equipment detail.');
			})
			.finally(() => {
				if (active) setLoading(false);
			});
		return () => {
			active = false;
		};
	}, [ctx.applno, ctx.finType]);

	if (loading) {
		return (
			<div className="rounded-2xl bg-white p-8 text-center text-sm text-slate-500 shadow">
				Loading equipment detail…
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

	const d = data.detail;

	return (
		<div>
			<Card title={data.title}>
				<dl className="grid grid-cols-1 gap-x-8 sm:grid-cols-2">
					<Field label="Brand" value={d.brand} />
					{d.show_stnk_valid_date && <Field label="STNK Valid Date" value={d.stnk_valid_date} />}
					<Field label="Type" value={d.type} />
					<Field label="Chasis No." value={d.chassis} />
					<Field label="Model / Karoseri" value={d.model_karoseri} />
					<Field label="Engine No." value={d.engine} />
					<Field label="Wheels" value={d.wheels} />
					<Field label="Police No." value={d.police_no} />
					<Field label="Year / Condition" value={d.year_condition} />
					<Field label="Color" value={d.color} />
					<Field label="Type of Equipment" value={d.type_of_equipment} />
					<Field label="User Usage" value={d.user_usage} />
					<Field label="Dealer Name" value={d.dealer_name} />
					<Field label="Vehicle Purpose" value={d.vehicle_purpose} />
					{d.show_financing_purpose && <Field label="Financing Purpose" value={d.financing_purpose} />}
					<Field label="Dealer Address" value={d.dealer_address} />
					<Field label="Parking Address" value={d.parking_address} />
					<Field label="Red Code (GPS Vendor)" value={d.red_code_gps} />
					<Field label="Zip Code" value={d.zip_code} />
					{d.karoseri_name !== null && <Field label="Karoseri Name" value={d.karoseri_name} />}
					{d.karoseri_address !== null && <Field label="Karoseri Address" value={d.karoseri_address} />}
					{d.accessories_name !== null && <Field label="Accessories Name" value={d.accessories_name} />}
					{d.accessories_address !== null && <Field label="Accessories Address" value={d.accessories_address} />}
					{d.other_name !== null && <Field label="Others Name" value={d.other_name} />}
					{d.other_address !== null && <Field label="Others Address" value={d.other_address} />}
				</dl>
			</Card>

			<Card title="Equipment Financing History">
				{data.financing_history.length === 0 ? (
					<p className="text-sm text-slate-400">No Data</p>
				) : (
					<table className="w-full text-sm">
						<thead>
							<tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-400">
								<th className="py-2 pr-3">Contract No.</th>
								<th className="py-2 pr-3">Customer Name</th>
								<th className="py-2 pr-3 text-right">OTR Amount</th>
								<th className="py-2 pr-3 text-right">Total Net Finance</th>
								<th className="py-2 pr-3">Disbursement Date</th>
								<th className="py-2">Finish Date</th>
							</tr>
						</thead>
						<tbody>
							{data.financing_history.map((row, i) => (
								<tr key={i} className="border-b border-slate-100 last:border-0">
									<td className="py-2 pr-3">
										<a
											href={`/rpt_print_his_pmt.php?lessee_no=${row.lessee_no}&lease_no=${row.lease_no}`}
											target="_blank"
											rel="noreferrer"
											className="text-blue-600 underline hover:text-blue-700"
										>
											{row.lease_no}
										</a>
									</td>
									<td className="py-2 pr-3">{row.lessee_nm}</td>
									<td className="py-2 pr-3 text-right">{fmt(row.otr)}</td>
									<td className="py-2 pr-3 text-right">{fmt(row.net_finance)}</td>
									<td className="py-2 pr-3">{row.disburse_date}</td>
									<td className="py-2">{row.finish_date}</td>
								</tr>
							))}
						</tbody>
					</table>
				)}
			</Card>

			<Card title="BPKB">
				<dl className="grid grid-cols-1 gap-x-8 sm:grid-cols-2">
					<Field label="BPKB No." value={d.bpkb_no} />
					<Field label="BPKB Name / Type" value={d.bpkb_name_type} />
					{d.show_family_status && <Field label="Family Status" value={d.family_status} />}
					<Field label="Relationship with Customer" value={d.relation} />
					<Field label="BPKB Address" value={d.bpkb_address} />
					<Field label="Area" value={d.area} />
					<Field label="Notary Name" value={d.notary_name} />
					<Field label="Fiducia/Cessie/Any Legitimate Area" value={d.fdc_area} />
				</dl>
			</Card>
		</div>
	);
}