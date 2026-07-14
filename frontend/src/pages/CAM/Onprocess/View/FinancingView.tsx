import React, { useEffect, useState } from 'react';
import api from '../../../../api/axiosInstance';
import type { CamCtx } from './CamViewTabs';

interface FinancingHeader {
	l_type_label: string;
	status: string;
	currency: string;
	contract_type: string;
	asset_value: number;
	disbursement_type: string;
	cross_note: string | null;
	dp_label: string;
	security_percent: number;
	security_amount: number;
	payment_method: string;
	net_finance: number;
	purpose_of_finance: string;
	insurance_loan: number;
	type_of_payment: string;
	bbn_loan: number;
	fix_float: string;
	provision_loan: number;
	tenor_label: string;
	other_loan: number;
	subsidy_from_dealer: number;
	total_net_finance: number;
	incentive_or_subsidy_label: string;
	incentive_or_subsidy_amount: number;
	survey_loan_2: number;
	refund_to_dealer: number;
	total_net_finance_plus_survey_loan2: number;
	bbn_via: string;
	flat_rate_selling: string;
	flat_rate_base: string;
	paid_by: string;
	effective_rate_selling: string;
	effective_rate_base: string;
	agency_name: string;
	rental_selling: number | null;
	rental_base: number | null;
	agency_fee_gross: number;
	bbn_fee: number;
	show_restructuring_change: boolean;
	restructuring_change: string;
	notary_fee_gross: number;
	business_trip_fee: number;
	nett_deed_fee: number;
	nett_certificate_fee: number;
	nett_agency_fee: number;
	guaranteed_acceptance: string;
	show_customer_flat_rate: boolean;
	customer_flat_rate: string;
}

interface StepRentalRow { step: number; month: number; rental: number; based: number; }

interface CalcRow {
	label: string;
	income: number | null;
	subsidy: number | null;
	total_income: number | null;
	base_rate: number | null;
	max_refund: number | null;
}

interface Calculator {
	rows: CalcRow[];
	subsidy_total: number;
	total_income_total: number;
	max_refund_total: number;
	max_incentive_percent: number;
	max_incentive_amount: number;
	marketing_fee: number;
	incentive_to_be_paid: number;
}

interface InsuranceYearRow {
	year: number;
	ins_amount: number;
	tpl_amount: number;
	tlo_ar: string;
	clause: string;
	premium_receive: number;
	premium_payment: number;
}

interface Insurance {
	ins_policy: string;
	ins_company: string;
	pay_method: string;
	model_nm: string;
	condition: string;
	total_seat: number;
	show_usage: boolean;
	usage_label: string;
	rows: InsuranceYearRow[];
}

interface InternalDisbRow { no: number; contract_no: string; amount: number; purpose: string; }
interface ExternalDisbRow { no: number; name: string; address: string; bank_branch: string; account_no: string; account_name: string; amount: number; }

interface Disbursement {
	left: {
		asset_value: number; dp_label: string; dp_or_security_amount: number; survey_fee_gross: number;
		notary_fee_gross: number; provision_fee: number; business_trip_fee: number; insurance: number;
		first_installment: number; agency_fee_gross: number; bbn_fee: number; refund_to_dealer: number;
		subsidy_from_dealer: number; disbursement_to_dealer: number; commission_to_dealer_gross: number;
		total_payment_to_dealer: number;
	};
	internal: InternalDisbRow[];
	internal_total: number;
	external: ExternalDisbRow[];
	external_total: number;
}

interface CommissionRow { no: number; code: string; name: string; address: string; fee: number; }

interface Outstanding {
	rows: Record<'disbursement' | 'undisbursement' | 'unapprove' | 'group' | 'guarantor', { unit: number; amount: number }>;
	total_unit: number;
	total_amount: number;
	calc_date: string;
	notes: string | null;
}

interface LoanRatioRow {
	no: number;
	label: string | null;
	brand_type: string;
	tahun: number | string | null;
	market_price: number;
	op: number;
	rental: number;
	term: number | string | null;
	tenor: number | string | null;
	payment_status: string | null;
	user_usage: string | null;
	loan_ratio: number | string | null;
	branch: string | null;
	remark?: string | null;
	cons_leas?: string | null;
}

interface LoanRatioSection { rows: LoanRatioRow[]; sub_total: { market: number; op: number; rental: number; ratio: number | null }; }

interface LoanRatio {
	disbursement: LoanRatioSection;
	cross_collateral_breakdown: {
		cross: { market: number; op: number; rental: number; ratio: number | null };
		non_cross: { market: number; op: number; rental: number; ratio: number | null };
		total_exposure: { market: number; op: number; rental: number; ratio: number | null };
		by_finance_type: Record<'leasing' | 'consumer_finance' | 'installment_financing' | 'finance_lease' | 'sale_leaseback', { op: number; units: number }>;
	};
	undisbursement: LoanRatioSection | null;
	unapprove: LoanRatioSection | null;
	grand_total_dis_undis_unapp: { market: number; op: number; rental: number; ratio: number | null };
	group: LoanRatioSection | null;
	guarantor: LoanRatioSection | null;
	grand_total_all: { market: number; op: number; rental: number; ratio: number | null } | null;
}

interface FinancingData {
	no_data: boolean;
	header: FinancingHeader;
	step_rental: StepRentalRow[] | null;
	calculator: Calculator;
	insurance: Insurance | null;
	disbursement: Disbursement;
	commission: CommissionRow[] | null;
	outstanding: Outstanding | null;
	loan_ratio: LoanRatio | null;
}

function fmt(n: number | null | undefined): string {
	if (n === null || n === undefined) return '-';
	return Math.round(n).toLocaleString('en-US');
}

function pct(n: number | string | null | undefined): string {
	if (n === null || n === undefined || n === '') return '-';
	return `${n}%`;
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
		<div className="flex items-baseline justify-between gap-3 border-b border-slate-100 py-2 last:border-0">
			<dt className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</dt>
			<dd className="text-right text-sm text-slate-700">{value === '' || value === null || value === undefined ? '-' : value}</dd>
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

function SubTotalRow({ st }: { st: { market: number; op: number; rental: number; ratio: number | null } }) {
	return (
		<tr className="border-t border-slate-200 font-semibold">
			<td className="py-2 pr-3" colSpan={4}>Sub Total</td>
			<td className="py-2 pr-3 text-right">{fmt(st.market)}</td>
			<td className="py-2 pr-3 text-right">{fmt(st.op)}</td>
			<td className="py-2 pr-3 text-right">{fmt(st.rental)}</td>
			<td className="py-2 pr-3" />
			<td className="py-2 pr-3" />
			<td className="py-2 pr-3 text-right">{st.ratio ?? '-'}{st.ratio !== null && '%'}</td>
			<td className="py-2" />
		</tr>
	);
}

function LoanRatioTable({ rows, subTotal, showPaymentStatus, showRemark, showConsLeas }: {
	rows: LoanRatioRow[];
	subTotal: { market: number; op: number; rental: number; ratio: number | null };
	showPaymentStatus: boolean;
	showRemark: boolean;
	showConsLeas: boolean;
}) {
	return (
		<table className="w-full min-w-[1000px] text-sm">
			<thead>
				<tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-400">
					<th className="py-2 pr-3">No.</th>
					<th className="py-2 pr-3">Contract No</th>
					<th className="py-2 pr-3">Brand/Type</th>
					<th className="py-2 pr-3">Car Year</th>
					<th className="py-2 pr-3 text-right">Market Price</th>
					<th className="py-2 pr-3 text-right">Outstanding Principal</th>
					<th className="py-2 pr-3 text-right">Installment/Month</th>
					<th className="py-2 pr-3">Terms</th>
					{showPaymentStatus && <th className="py-2 pr-3">Payment Status</th>}
					<th className="py-2 pr-3">User of Car</th>
					<th className="py-2 pr-3 text-right">Loan Ratio (%)</th>
					<th className="py-2 pr-3">Branch</th>
					{showRemark && <th className="py-2 pr-3">Remark</th>}
					{showConsLeas && <th className="py-2">Finance Type</th>}
				</tr>
			</thead>
			<tbody>
				{rows.map((r) => (
					<tr key={r.no} className="border-b border-slate-100 last:border-0">
						<td className="py-2 pr-3">{r.no}</td>
						<td className="py-2 pr-3">{r.label || '-'}</td>
						<td className="py-2 pr-3">{r.brand_type}</td>
						<td className="py-2 pr-3">{r.tahun ?? '-'}</td>
						<td className="py-2 pr-3 text-right">{fmt(r.market_price)}</td>
						<td className="py-2 pr-3 text-right">{fmt(r.op)}</td>
						<td className="py-2 pr-3 text-right">{fmt(r.rental)}</td>
						<td className="py-2 pr-3">{r.term} of {r.tenor}</td>
						{showPaymentStatus && <td className="py-2 pr-3">{r.payment_status}</td>}
						<td className="py-2 pr-3">{r.user_usage}</td>
						<td className="py-2 pr-3 text-right">{r.loan_ratio ?? '-'}</td>
						<td className="py-2 pr-3">{r.branch}</td>
						{showRemark && <td className="py-2 pr-3">{r.remark}</td>}
						{showConsLeas && <td className="py-2">{r.cons_leas}</td>}
					</tr>
				))}
				<SubTotalRow st={subTotal} />
			</tbody>
		</table>
	);
}

function BreakdownTable({ b }: { b: LoanRatio['cross_collateral_breakdown'] }) {
	const row = (label: string, v: { market?: number; op: number; rental: number | string; ratio: number | null }) => (
		<tr className="border-b border-slate-100 last:border-0">
			<td className="py-2 pr-3">{label}</td>
			<td className="py-2 pr-3 text-right">{v.market !== undefined ? fmt(v.market) : ''}</td>
			<td className="py-2 pr-3 text-right">{fmt(v.op)}</td>
			<td className="py-2 pr-3 text-right">{typeof v.rental === 'number' ? fmt(v.rental) : v.rental}</td>
			<td className="py-2 text-right">{v.ratio !== null && v.ratio !== undefined ? `${v.ratio}%` : ''}</td>
		</tr>
	);
	return (
		<table className="w-full text-sm">
			<thead>
				<tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-400">
					<th className="py-2 pr-3" />
					<th className="py-2 pr-3 text-right">Market Price</th>
					<th className="py-2 pr-3 text-right">Outstanding Principal</th>
					<th className="py-2 pr-3 text-right">Installment/Month</th>
					<th className="py-2 text-right">Loan Ratio</th>
				</tr>
			</thead>
			<tbody>
				{row('Total Cross Collateral Customer', b.cross)}
				{row('Total non Cross Collateral Customer', b.non_cross)}
				{row('Total Exposure Customer', b.total_exposure)}
				{row('Leasing', { op: b.by_finance_type.leasing.op, rental: `${b.by_finance_type.leasing.units} Unit`, ratio: null })}
				{row('Consumer Finance', { op: b.by_finance_type.consumer_finance.op, rental: `${b.by_finance_type.consumer_finance.units} Unit`, ratio: null })}
				{row('Installment Financing', { op: b.by_finance_type.installment_financing.op, rental: `${b.by_finance_type.installment_financing.units} Unit`, ratio: null })}
				{row('Finance Lease', { op: b.by_finance_type.finance_lease.op, rental: `${b.by_finance_type.finance_lease.units} Unit`, ratio: null })}
				{row('Sale & Leaseback', { op: b.by_finance_type.sale_leaseback.op, rental: `${b.by_finance_type.sale_leaseback.units} Unit`, ratio: null })}
			</tbody>
		</table>
	);
}

function GrandTotalTable({ title, gt }: { title: string; gt: { market: number; op: number; rental: number; ratio: number | null } }) {
	return (
		<table className="w-full max-w-xl text-sm">
			<thead>
				<tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-400">
					<th className="py-2 pr-3" />
					<th className="py-2 pr-3 text-right">Market Price</th>
					<th className="py-2 pr-3 text-right">Outstanding Principal</th>
					<th className="py-2 pr-3 text-right">Installment/Month</th>
					<th className="py-2 text-right">Loan Ratio</th>
				</tr>
			</thead>
			<tbody>
				<tr>
					<td className="py-2 pr-3 font-semibold">{title}</td>
					<td className="py-2 pr-3 text-right">{fmt(gt.market)}</td>
					<td className="py-2 pr-3 text-right">{fmt(gt.op)}</td>
					<td className="py-2 pr-3 text-right">{fmt(gt.rental)}</td>
					<td className="py-2 text-right">{gt.ratio !== null ? `${gt.ratio}%` : '-'}</td>
				</tr>
			</tbody>
		</table>
	);
}

export default function FinancingView({ ctx }: { ctx: CamCtx }) {
	const [data, setData] = useState<FinancingData | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		let active = true;
		setLoading(true);
		setError(null);
		api
			.get('/CAM/api/view/financing', {
				params: { apless: ctx.apless, applno: ctx.applno, fin_type: ctx.finType, ind_cor: ctx.indCor },
			})
			.then((res) => {
				if (active) setData(res.data);
			})
			.catch(() => {
				if (active) setError('Failed to load financing detail.');
			})
			.finally(() => {
				if (active) setLoading(false);
			});
		return () => {
			active = false;
		};
	}, [ctx.apless, ctx.applno, ctx.finType, ctx.indCor]);

	if (loading) {
		return (
			<div className="rounded-2xl bg-white p-8 text-center text-sm text-slate-500 shadow">
				Loading financing detail…
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

	const h = data.header;
	const c = data.calculator;
	const d = data.disbursement;
	const lr = data.loan_ratio;

	return (
		<div>
			<Card title={`Financing Detail Review - ${h.l_type_label}`}>
				<dl className="grid grid-cols-1 gap-x-8 sm:grid-cols-2">
					<Field label="Status" value={h.status} />
					<Field label="Currency" value={h.currency} />
					<Field label="Contract Type" value={h.contract_type} />
					<Field label="Asset Value" value={fmt(h.asset_value)} />
					<Field label="Disbursement Type" value={`${h.disbursement_type}${h.cross_note ? ` | ${h.cross_note}` : ''}`} />
					<Field label={h.dp_label} value={`${pct(h.security_percent)} / ${fmt(h.security_amount)}`} />
					<Field label="Payment Method" value={h.payment_method} />
					<Field label="Net Finance" value={fmt(h.net_finance)} />
					<Field label="Purpose of Finance" value={h.purpose_of_finance} />
					<Field label="Insurance Loan" value={fmt(h.insurance_loan)} />
					<Field label="Type of Payment" value={h.type_of_payment} />
					<Field label="BBN Loan" value={fmt(h.bbn_loan)} />
					<Field label="Fix/Float" value={h.fix_float} />
					<Field label="Provision Loan" value={fmt(h.provision_loan)} />
					<Field label="Tenor/Payment Cycle" value={h.tenor_label} />
					<Field label="Other Loan" value={fmt(h.other_loan)} />
					<Field label="Subsidy from Dealer" value={fmt(h.subsidy_from_dealer)} />
					<Field label="Total Net Finance" value={fmt(h.total_net_finance)} />
					<Field label={h.incentive_or_subsidy_label} value={fmt(h.incentive_or_subsidy_amount)} />
					<Field label="Survey Loan 2" value={fmt(h.survey_loan_2)} />
					<Field label="Refund to Dealer" value={fmt(h.refund_to_dealer)} />
					<Field label="Total Net Finance + Survey Loan 2" value={fmt(h.total_net_finance_plus_survey_loan2)} />
					<Field label="BBN Via" value={h.bbn_via} />
					<Field label="Flat Rate (Selling / Base)" value={`${h.flat_rate_selling}% / ${h.flat_rate_base}%`} />
					<Field label="Paid By" value={h.paid_by} />
					<Field label="Effective Rate (Selling / Base)" value={`${h.effective_rate_selling}% / ${h.effective_rate_base}%`} />
					<Field label="Agency Name" value={h.agency_name} />
					<Field
						label="Rental (Selling / Base)"
						value={h.rental_selling === null ? '-' : `${fmt(h.rental_selling)} / ${fmt(h.rental_base)}`}
					/>
					<Field label="Agency Fee Gross" value={fmt(h.agency_fee_gross)} />
					<Field label="BBN Fee" value={fmt(h.bbn_fee)} />
					{h.show_restructuring_change && <Field label="Changes from Restructuring" value={h.restructuring_change} />}
					<Field label="Notary Fee Gross" value={fmt(h.notary_fee_gross)} />
					<Field label="Business Trip Fee" value={fmt(h.business_trip_fee)} />
					<Field label="Nett Deed Fee" value={fmt(h.nett_deed_fee)} />
					<Field label="Nett Certificate Fee" value={fmt(h.nett_certificate_fee)} />
					<Field label="Nett Agency Fee" value={fmt(h.nett_agency_fee)} />
					<Field label="Guaranteed Acceptance" value={h.guaranteed_acceptance} />
					{h.show_customer_flat_rate && <Field label="Customer Flat Rate" value={`${h.customer_flat_rate}%`} />}
				</dl>
			</Card>

			<Card title="Income / Subsidy / Provision Calculator">
				<table className="w-full min-w-[800px] text-sm">
					<thead>
						<tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-400">
							<th className="py-2 pr-3">Item</th>
							<th className="py-2 pr-3 text-right">Income</th>
							<th className="py-2 pr-3 text-right">Subsidy</th>
							<th className="py-2 pr-3 text-right">Total Income (incl. Subsidy)</th>
							<th className="py-2 pr-3 text-right">Base Rate</th>
							<th className="py-2 text-right">Max Refund</th>
						</tr>
					</thead>
					<tbody>
						{c.rows.map((r) => (
							<tr key={r.label} className="border-b border-slate-100 last:border-0">
								<td className="py-2 pr-3">{r.label}</td>
								<td className="py-2 pr-3 text-right">{r.income !== null ? fmt(r.income) : ''}</td>
								<td className="py-2 pr-3 text-right">{r.subsidy !== null ? fmt(r.subsidy) : ''}</td>
								<td className="py-2 pr-3 text-right">{r.total_income !== null ? fmt(r.total_income) : ''}</td>
								<td className="py-2 pr-3 text-right">{r.base_rate !== null ? fmt(r.base_rate) : ''}</td>
								<td className="py-2 text-right">{r.max_refund !== null ? fmt(r.max_refund) : ''}</td>
							</tr>
						))}
						<tr className="border-t border-slate-200 font-semibold">
							<td className="py-2 pr-3">Total</td>
							<td className="py-2 pr-3" />
							<td className="py-2 pr-3 text-right">{fmt(c.subsidy_total)}</td>
							<td className="py-2 pr-3 text-right">{fmt(c.total_income_total)}</td>
							<td className="py-2 pr-3" />
							<td className="py-2 text-right">{fmt(c.max_refund_total)}</td>
						</tr>
					</tbody>
				</table>
				<div className="mt-4 space-y-1 text-sm">
					<div className="flex justify-between border-b border-slate-100 py-1">
						<span>Max Incentive to 3rd Party ({c.max_incentive_percent}%)</span>
						<span className="font-semibold">{fmt(c.max_incentive_amount)}</span>
					</div>
					<div className="flex justify-between border-b border-slate-100 py-1">
						<span>Marketing Fee</span>
						<span className="font-semibold">{fmt(c.marketing_fee)}</span>
					</div>
					<div className="flex justify-between py-1">
						<span>Incentive To Be Paid</span>
						<span className="font-semibold">{fmt(c.incentive_to_be_paid)}</span>
					</div>
				</div>
			</Card>

			{data.step_rental && data.step_rental.length > 0 && (
				<Card title="Step Rental">
					<table className="w-full text-sm">
						<thead>
							<tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-400">
								<th className="py-2 pr-3">Step</th>
								<th className="py-2 pr-3">Month</th>
								<th className="py-2 pr-3 text-right">Rental</th>
								<th className="py-2 text-right">Based</th>
							</tr>
						</thead>
						<tbody>
							{data.step_rental.map((s) => (
								<tr key={s.step} className="border-b border-slate-100 last:border-0">
									<td className="py-2 pr-3">{s.step}</td>
									<td className="py-2 pr-3">{s.month}</td>
									<td className="py-2 pr-3 text-right">{fmt(s.rental)}</td>
									<td className="py-2 text-right">{fmt(s.based)}</td>
								</tr>
							))}
						</tbody>
					</table>
				</Card>
			)}

			{data.insurance && (
				<Card title="Insurance">
					<dl className="mb-4 grid grid-cols-1 gap-x-8 sm:grid-cols-2">
						<Field label="Ins. Policy" value={data.insurance.ins_policy} />
						<Field label="Model" value={data.insurance.model_nm} />
						<Field label="Ins. Company" value={data.insurance.ins_company} />
						<Field label="Condition" value={data.insurance.condition} />
						<Field label="Pay Method" value={data.insurance.pay_method} />
						<Field label="Seat" value={data.insurance.total_seat} />
						{data.insurance.show_usage && <Field label="Usage" value={data.insurance.usage_label} />}
					</dl>
					<table className="w-full text-sm">
						<thead>
							<tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-400">
								<th className="py-2 pr-3">Year</th>
								<th className="py-2 pr-3 text-right">Insurance Amount</th>
								<th className="py-2 pr-3 text-right">TPL Amount</th>
								<th className="py-2 pr-3">TLO CP</th>
								<th className="py-2 pr-3">Clause</th>
								<th className="py-2 pr-3 text-right">Premium Receive</th>
								<th className="py-2 text-right">Premium Payment</th>
							</tr>
						</thead>
						<tbody>
							{data.insurance.rows.map((r) => (
								<tr key={r.year} className="border-b border-slate-100 last:border-0">
									<td className="py-2 pr-3">{r.year}</td>
									<td className="py-2 pr-3 text-right">{fmt(r.ins_amount)}</td>
									<td className="py-2 pr-3 text-right">{fmt(r.tpl_amount)}</td>
									<td className="py-2 pr-3">{r.tlo_ar}</td>
									<td className="py-2 pr-3">{r.clause}</td>
									<td className="py-2 pr-3 text-right">{fmt(r.premium_receive)}</td>
									<td className="py-2 text-right">{fmt(r.premium_payment)}</td>
								</tr>
							))}
						</tbody>
					</table>
				</Card>
			)}

			<Card title="Disbursement">
				<div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
					<dl>
						<Field label="Asset Value" value={fmt(d.left.asset_value)} />
						<Field label={d.left.dp_label} value={fmt(d.left.dp_or_security_amount)} />
						<Field label="Survey Fee Gross" value={fmt(d.left.survey_fee_gross)} />
						<Field label="Notary Fee Gross" value={fmt(d.left.notary_fee_gross)} />
						<Field label="Provision Fee" value={fmt(d.left.provision_fee)} />
						<Field label="Business Trip Fee" value={fmt(d.left.business_trip_fee)} />
						<Field label="Insurance" value={fmt(d.left.insurance)} />
						<Field label="First Installment" value={fmt(d.left.first_installment)} />
						<Field label="Agency Fee Gross" value={fmt(d.left.agency_fee_gross)} />
						<Field label="BBN Fee" value={fmt(d.left.bbn_fee)} />
						<Field label="Refund To Dealer" value={fmt(d.left.refund_to_dealer)} />
						<Field label="Subsidy From Dealer" value={fmt(d.left.subsidy_from_dealer)} />
						<Field label="Disbursement to Dealer" value={fmt(d.left.disbursement_to_dealer)} />
						<Field label="Commission to Dealer (Gross)" value={fmt(d.left.commission_to_dealer_gross)} />
						<Field label="Total Payment to Dealer" value={fmt(d.left.total_payment_to_dealer)} />
					</dl>
					<div>
						<h3 className="mb-2 text-center text-sm font-semibold text-slate-600">Internal Disbursement</h3>
						<table className="mb-6 w-full text-sm">
							<thead>
								<tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-400">
									<th className="py-2 pr-3">No</th>
									<th className="py-2 pr-3">Contract Number</th>
									<th className="py-2 pr-3 text-right">Amount</th>
									<th className="py-2">Purpose</th>
								</tr>
							</thead>
							<tbody>
								{d.internal.length === 0 ? (
									<tr><td colSpan={4} className="py-2 text-slate-400">No Data</td></tr>
								) : (
									d.internal.map((r) => (
										<tr key={r.no} className="border-b border-slate-100 last:border-0">
											<td className="py-2 pr-3">{r.no}</td>
											<td className="py-2 pr-3">{r.contract_no}</td>
											<td className="py-2 pr-3 text-right">{fmt(r.amount)}</td>
											<td className="py-2">{r.purpose}</td>
										</tr>
									))
								)}
								<tr className="border-t border-slate-200 font-semibold">
									<td className="py-2 pr-3" />
									<td className="py-2 pr-3">Total</td>
									<td className="py-2 pr-3 text-right">{fmt(d.internal_total)}</td>
									<td className="py-2" />
								</tr>
							</tbody>
						</table>

						<h3 className="mb-2 text-center text-sm font-semibold text-slate-600">External Disbursement</h3>
						<table className="w-full text-sm">
							<thead>
								<tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-400">
									<th className="py-2 pr-3">No</th>
									<th className="py-2 pr-3">Name</th>
									<th className="py-2 pr-3">Bank-Branch</th>
									<th className="py-2 pr-3">Account No.</th>
									<th className="py-2 pr-3">Beneficiary Name</th>
									<th className="py-2 text-right">Amount</th>
								</tr>
							</thead>
							<tbody>
								{d.external.length === 0 ? (
									<tr><td colSpan={6} className="py-2 text-slate-400">No Data</td></tr>
								) : (
									d.external.map((r) => (
										<tr key={r.no} className="border-b border-slate-100 last:border-0">
											<td className="py-2 pr-3">{r.no}</td>
											<td className="py-2 pr-3">{r.name}</td>
											<td className="py-2 pr-3">{r.bank_branch}</td>
											<td className="py-2 pr-3">{r.account_no}</td>
											<td className="py-2 pr-3">{r.account_name}</td>
											<td className="py-2 text-right">{fmt(r.amount)}</td>
										</tr>
									))
								)}
								<tr className="border-t border-slate-200 font-semibold">
									<td className="py-2 pr-3" colSpan={5}>Total</td>
									<td className="py-2 text-right">{fmt(d.external_total)}</td>
								</tr>
							</tbody>
						</table>
					</div>
				</div>
			</Card>

			{data.commission && (
				<Card title="Commission">
					<table className="w-full text-sm">
						<thead>
							<tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-400">
								<th className="py-2 pr-3">No.</th>
								<th className="py-2 pr-3">Code</th>
								<th className="py-2 pr-3">Name</th>
								<th className="py-2 pr-3">Address</th>
								<th className="py-2 text-right">Fee</th>
							</tr>
						</thead>
						<tbody>
							{data.commission.map((r) => (
								<tr key={r.no} className="border-b border-slate-100 last:border-0">
									<td className="py-2 pr-3">{r.no}</td>
									<td className="py-2 pr-3" dangerouslySetInnerHTML={{ __html: r.code }} />
									<td className="py-2 pr-3">{r.name}</td>
									<td className="py-2 pr-3">{r.address}</td>
									<td className="py-2 text-right">{fmt(r.fee)}</td>
								</tr>
							))}
						</tbody>
					</table>
				</Card>
			)}

			{data.outstanding && (
				<Card title="Outstanding">
					<table className="w-full max-w-lg text-sm">
						<thead>
							<tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-400">
								<th className="py-2 pr-3">Outstanding</th>
								<th className="py-2 pr-3 text-right">Unit</th>
								<th className="py-2 text-right">Amount</th>
							</tr>
						</thead>
						<tbody>
							<tr className="border-b border-slate-100"><td className="py-2 pr-3">Disbursement</td><td className="py-2 pr-3 text-right">{fmt(data.outstanding.rows.disbursement.unit)}</td><td className="py-2 text-right">{fmt(data.outstanding.rows.disbursement.amount)}</td></tr>
							<tr className="border-b border-slate-100"><td className="py-2 pr-3">Undisbursement</td><td className="py-2 pr-3 text-right">{fmt(data.outstanding.rows.undisbursement.unit)}</td><td className="py-2 text-right">{fmt(data.outstanding.rows.undisbursement.amount)}</td></tr>
							<tr className="border-b border-slate-100"><td className="py-2 pr-3">Unapprove</td><td className="py-2 pr-3 text-right">{fmt(data.outstanding.rows.unapprove.unit)}</td><td className="py-2 text-right">{fmt(data.outstanding.rows.unapprove.amount)}</td></tr>
							<tr className="border-b border-slate-100"><td className="py-2 pr-3">Group</td><td className="py-2 pr-3 text-right">{fmt(data.outstanding.rows.group.unit)}</td><td className="py-2 text-right">{fmt(data.outstanding.rows.group.amount)}</td></tr>
							<tr className="border-b border-slate-100"><td className="py-2 pr-3">Guarantor</td><td className="py-2 pr-3 text-right">{fmt(data.outstanding.rows.guarantor.unit)}</td><td className="py-2 text-right">{fmt(data.outstanding.rows.guarantor.amount)}</td></tr>
							<tr className="border-t border-slate-200 font-semibold"><td className="py-2 pr-3">Total</td><td className="py-2 pr-3 text-right">{fmt(data.outstanding.total_unit)}</td><td className="py-2 text-right">{fmt(data.outstanding.total_amount)}</td></tr>
						</tbody>
					</table>
					<p className="mt-3 text-sm text-slate-500">Calculation Date: {data.outstanding.calc_date}</p>
					{data.outstanding.notes && (
						<div className="mt-3 rounded-lg border border-slate-100 bg-slate-50 p-3 text-sm text-slate-700">
							{data.outstanding.notes}
						</div>
					)}
				</Card>
			)}

			{lr && (
				<Card title="Loan Ratio">
					<div className="space-y-8">
						<div>
							<h3 className="mb-2 text-sm font-semibold text-slate-600">Disbursement</h3>
							<LoanRatioTable rows={lr.disbursement.rows} subTotal={lr.disbursement.sub_total} showPaymentStatus showRemark={false} showConsLeas={false} />
						</div>

						<BreakdownTable b={lr.cross_collateral_breakdown} />

						{lr.undisbursement && (
							<div>
								<h3 className="mb-2 text-sm font-semibold text-slate-600">Undisbursement</h3>
								<LoanRatioTable rows={lr.undisbursement.rows} subTotal={lr.undisbursement.sub_total} showPaymentStatus showRemark={false} showConsLeas={false} />
							</div>
						)}

						{lr.unapprove && (
							<div>
								<h3 className="mb-2 text-sm font-semibold text-slate-600">Unapprove</h3>
								<LoanRatioTable rows={lr.unapprove.rows} subTotal={lr.unapprove.sub_total} showPaymentStatus={false} showRemark={false} showConsLeas />
							</div>
						)}

						<GrandTotalTable title="Grand Total" gt={lr.grand_total_dis_undis_unapp} />

						{lr.group && (
							<div>
								<h3 className="mb-2 text-sm font-semibold text-slate-600">Group</h3>
								<LoanRatioTable rows={lr.group.rows} subTotal={lr.group.sub_total} showPaymentStatus showRemark={false} showConsLeas={false} />
							</div>
						)}

						{lr.guarantor && (
							<div>
								<h3 className="mb-2 text-sm font-semibold text-slate-600">Guarantor</h3>
								<LoanRatioTable rows={lr.guarantor.rows} subTotal={lr.guarantor.sub_total} showPaymentStatus showRemark={false} showConsLeas={false} />
							</div>
						)}

						{lr.grand_total_all && <GrandTotalTable title="Grand Total (incl. Group/Guarantor)" gt={lr.grand_total_all} />}

						<p className="text-xs text-slate-400">
							Finance Type: F = Finance Lease (FL), I = Installment Financing (IF), S = Sale &amp; Leaseback (SL)
						</p>
					</div>
				</Card>
			)}
		</div>
	);
}