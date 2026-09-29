import React, { useEffect, useState } from 'react';
import api from '../../../../../api/axiosInstance';
import type { CamCtx } from '../CamViewTabs';

interface Character {
	credit_history_label: string;
	reference: string;
	work_experience: string;
	note: string;
	company_status: string | null;
	scale_of_business: string | null;
}

interface Capital {
	living_label: string | null;
	living_status_label: string | null;
	car_ownership: string | null;
	note: string;
	business_location: string | null;
	office_status: string | null;
	total_unit_owned: string | null;
	unit_free_from_finance: string | null;
	estimated_total_assets_label: string | null;
	estimated_total_assets_asof: string | null;
}

interface Capacity {
	job_occupation_customer: string | null;
	fixed_monthly_income: number | null;
	fixed_income_source_label: string | null;
	job_occupation_spouse: string | null;
	spouse_income_per_month: number | null;
	total_other_income: number | null;
	total_other_income_status: string | null;
	total_other_income_source_label: string | null;
	total_income_per_month: number | null;
	total_income_status: string | null;
	average_income_per_year: number | null;
	note: string;
	monthly_profit: number | null;
	monthly_profit_status: string | null;
	monthly_profit_source_label: string | null;
	sales_per_month: number | null;
	net_profit_to_sales: string | null;
}

interface Collateral {
	unit_type: string;
	insurance: string;
	payment_method: string;
	note: string;
	loan_to_value: number;
	guarantor: string;
}

interface Condition {
	total_outstanding_label: string;
	dealer_status: string;
	usage_of_car: string;
	credit_period: string;
}

interface SidRow {
	subject: string;
	show_related_party: boolean;
	related_party: string;
	show_keterangan_text: boolean;
	keterangan_text: string;
	show_type: boolean;
	type_label: string;
	credit_bureau: string;
	status: string;
	score: string | number;
	grade: string;
	pefindo_download_url: string | null;
}

interface SurveyData {
	no_data: boolean;
	ind_cor: string;
	character: Character;
	capital: Capital;
	capacity: Capacity;
	collateral: Collateral;
	condition: Condition;
	sid_checking: { note: string; rows: SidRow[] };
}

function fmt(n: number | null | undefined): string {
	if (n === null || n === undefined) return '-';
	return Math.round(n).toLocaleString('en-US');
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
	return (
		<div className="mb-4 overflow-hidden rounded-2xl bg-white shadow">
			<div className="border-b border-slate-100 bg-slate-50 px-5 py-3">
				<h2 className="text-sm font-semibold text-slate-700">{title}</h2>
			</div>
			<div className="grid grid-cols-1 gap-4 p-5 lg:grid-cols-[3fr_2fr]">{children}</div>
		</div>
	);
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
	return (
		<div className="flex items-baseline justify-between gap-3 border-b border-slate-100 py-2 last:border-0">
			<dt className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</dt>
			<dd className="text-right text-sm text-slate-700">{value === '' || value === null || value === undefined ? '-' : value}</dd>
		</div>
	);
}

function NotePanel({ note }: { note: string }) {
	return (
		<div className="rounded-lg border border-slate-100 bg-slate-50 p-3 text-sm text-slate-600">
			{note || <span className="text-slate-400">No note.</span>}
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

export default function SurveyView({ ctx }: { ctx: CamCtx }) {
	const [data, setData] = useState<SurveyData | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		let active = true;
		setLoading(true);
		setError(null);
		api
			.get('/CAM/View/api/survey', {
				params: { apless: ctx.apless, applno: ctx.applno, new_car: ctx.newCar, ind_cor: ctx.indCor },
			})
			.then((res) => {
				if (active) setData(res.data);
			})
			.catch(() => {
				if (active) setError('Failed to load survey data.');
			})
			.finally(() => {
				if (active) setLoading(false);
			});
		return () => {
			active = false;
		};
	}, [ctx.apless, ctx.applno, ctx.newCar, ctx.indCor]);

	if (loading) {
		return (
			<div className="rounded-2xl bg-white p-8 text-center text-sm text-slate-500 shadow">
				Loading survey…
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

	const isCorp = data.ind_cor === '2';
	const ch = data.character;
	const cap = data.capital;
	const cy = data.capacity;
	const co = data.collateral;
	const cn = data.condition;

	return (
		<div>
			<Card title="Character">
				<dl>
					<Field label="Credit History" value={ch.credit_history_label} />
					<Field label="Reference" value={ch.reference} />
					<Field label={isCorp ? 'Business Experience' : 'Working/ Business Experience'} value={ch.work_experience} />
					{isCorp && <Field label="Company Status" value={ch.company_status} />}
					{isCorp && <Field label="Scale of Business" value={ch.scale_of_business} />}
				</dl>
				<NotePanel note={ch.note} />
			</Card>

			<Card title="Capital">
				<dl>
					{!isCorp && (
						<>
							<Field label="Living" value={cap.living_label} />
							<Field label={`${cap.living_label || 'Living'} Status`} value={cap.living_status_label} />
							<Field label="Car Ownership" value={cap.car_ownership} />
						</>
					)}
					{isCorp && (
						<>
							<Field label="Business Location" value={cap.business_location} />
							<Field label="Office Status" value={cap.office_status} />
							<Field label="Total Unit Owned (Vehicle)" value={cap.total_unit_owned} />
							<Field label="Unit Free from Finance" value={cap.unit_free_from_finance} />
							<Field
								label={`Estimated Total Assets (as of ${cap.estimated_total_assets_asof || '-'})`}
								value={cap.estimated_total_assets_label}
							/>
						</>
					)}
				</dl>
				<NotePanel note={cap.note} />
			</Card>

			<Card title="Capacity">
				<dl>
					{!isCorp && (
						<>
							<Field label="Job / Occupation (Customer)" value={cy.job_occupation_customer} />
							<Field label="Fixed Monthly Income (Rp.) / Source Of Fund" value={`${fmt(cy.fixed_monthly_income)} / ${cy.fixed_income_source_label || '-'}`} />
							<Field label="Job/ Occupation (Spouse)" value={cy.job_occupation_spouse} />
							<Field label="Spouse Income Per Month (Rp.)" value={fmt(cy.spouse_income_per_month)} />
							<Field label="Total Other Income Per Month (Rp.) / Source Of Fund" value={`${fmt(cy.total_other_income)} ${cy.total_other_income_status} / ${cy.total_other_income_source_label || '-'}`} />
							<Field label="Total Income per Month (Rp.)" value={`${fmt(cy.total_income_per_month)} ${cy.total_income_status}`} />
							<Field label="Average Income per Year (Rp.)" value={fmt(cy.average_income_per_year)} />
						</>
					)}
					{isCorp && (
						<>
							<Field label="Monthly Profit (Rp.) / Source Of Fund" value={`${fmt(cy.monthly_profit)} ${cy.monthly_profit_status} / ${cy.monthly_profit_source_label || '-'}`} />
							<Field label="Sales/ Month (Rp.)" value={fmt(cy.sales_per_month)} />
							<Field label="Net Profit : Sales (Rp.)" value={cy.net_profit_to_sales} />
						</>
					)}
				</dl>
				<NotePanel note={cy.note} />
			</Card>

			<Card title="Collateral">
				<dl>
					<Field label="Unit Type" value={co.unit_type} />
					<Field label="Loan to Value" value={`${co.loan_to_value}%`} />
					<Field label="Insurance" value={co.insurance} />
					<Field label="Guarantor" value={co.guarantor} />
					<Field label="Payment Method" value={co.payment_method} />
				</dl>
				<NotePanel note={co.note} />
			</Card>

			<Card title="Condition">
				<dl>
					<Field label="Credit Period" value={cn.credit_period} />
					<Field label="Total Outstanding (Rp.)" value={cn.total_outstanding_label} />
					<Field label="Dealer Status" value={cn.dealer_status} />
					<Field label="Usage of Car" value={cn.usage_of_car} />
				</dl>
				<div />
			</Card>

			<div className="mb-4 overflow-hidden rounded-2xl bg-white shadow">
				<div className="border-b border-slate-100 bg-slate-50 px-5 py-3">
					<h2 className="text-sm font-semibold text-slate-700">File SID Checking</h2>
				</div>
				<div className="grid grid-cols-1 gap-4 p-5 lg:grid-cols-[3fr_2fr]">
					<div>
						{data.sid_checking.rows.length === 0 ? (
							<p className="text-sm text-slate-400">No SID checking records.</p>
						) : (
							<div className="space-y-4">
								{data.sid_checking.rows.map((r, i) => (
									<div key={i} className="rounded-lg border border-slate-100 p-3">
										<dl>
											<Field label="Subject" value={r.subject} />
											{r.show_related_party && <Field label="Related Party" value={r.related_party} />}
											{r.show_keterangan_text && <Field label="Keterangan" value={r.keterangan_text} />}
											{r.show_type && <Field label="Type" value={r.type_label} />}
											<Field label="Credit Bureau" value={r.credit_bureau} />
											<Field label="Status" value={r.status} />
											<Field label="Score" value={r.score} />
											<Field label="Grade" value={r.grade} />
										</dl>
										{r.pefindo_download_url && (
											<a href={r.pefindo_download_url} className="mt-2 inline-block text-sm text-blue-600 underline hover:text-blue-700">
												Download Pefindo File
											</a>
										)}
									</div>
								))}
							</div>
						)}
					</div>
					<NotePanel note={data.sid_checking.note} />
				</div>
			</div>
		</div>
	);
}