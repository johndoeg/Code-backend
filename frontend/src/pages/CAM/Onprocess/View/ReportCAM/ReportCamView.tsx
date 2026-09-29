import React, { useEffect, useState } from 'react';
import api from '../../../../../api/axiosInstance';
import type { CamCtx } from '../CamViewTabs';

interface BankAccount { bank_branch: string; account_no: string; account_name: string; amount: number; }
interface ApprovalRow { full_name: string; date: string; sent_to_admin: boolean; }
interface ReferenceRow { name: string; phone: string; remark: string; }
interface CommissionSale { label: string; amount: number; }
interface OutstandingRow { label: string; unit: number; amount: number; }
interface CreditScoringItem { description: string; result: string; score: number | string; }

interface JobHistoryRow {
	from: string;
	until: string;
	company: string;
	address: string;
	city: string;
	province: string;
	postal_code: string;
	employee_id?: string;
	position: string;
	phone: string;
}

interface SidCheckingFile {
	subject: string;
	credit_bureau: string;
	status: string;
	score: string;
	grade: string;
	file_label?: string;
	file_url?: string;
}

interface CustomerSurveyDetail {
	credit_history?: string;
	reference?: string;
	work_experience?: string;
	business_size?: string;
	company_status?: string;
	scale_of_business?: string;

	living?: string;
	living_status?: string;
	car_ownership?: string;
	business_location?: string;
	total_unit_owned?: string;
	unit_free_from_finance?: string;
	estimated_total_assets_as_of?: string;

	job_customer?: string;
	fixed_monthly_income?: number;
	income_source_note?: string;
	spouse_income?: number;
	other_income?: number;
	other_income_note?: string;
	total_income?: number;
	total_income_note?: string;
	average_income_per_year?: number;
	monthly_profit?: number;
	monthly_profit_note?: string;
	sales_per_month?: number;
	net_profit_ratio?: string;

	unit_type?: string;
	loan_to_value?: number;
	insurance_payment?: string;
	guarantor_available?: string;
	payment_method?: string;
	credit_period?: string;
	total_outstanding_bucket?: string;
	dealer_status?: string;
	usage_of_car?: string;
	job_history: JobHistoryRow[];
	sid_checking: SidCheckingFile[];
	sid_checking_notes?: string;
}

interface GuarantorDetail {
	entity_type: 'PR' | 'PT';
	name: string;
	name_without_title?: string;
	category?: string;
	id_card?: string;
	id_card_validity?: string;
	passport_no?: string;
	citizenship?: string;
	nationality?: string;
	date_of_birth?: string;
	place_of_birth?: string;
	gender?: string;
	marital_status?: string;
	address?: string;
	phone?: string;
	fax?: string;
	mobile?: string;
	email?: string;
	relationship_with_customer?: string;
	occupation?: string;
	bi_customer_type?: string;
	total_exposure?: number;
	npwp?: string;
	line_of_business?: string;
	contract_signer_name?: string;
	contract_signer_position?: string;
	contract_signer_id_card?: string;
	contract_signer_mobile?: string;
	contract_signer_email?: string;
	spouse_name?: string;
	spouse_id_card?: string;
	spouse_address?: string;
	spouse_status?: string;
	spouse_citizenship?: string;
	spouse_mobile?: string;
	spouse_email?: string;
}

interface BeneficialOwnerDetail {
	entity_type: 'PR' | 'PT';
	name: string;
	alias?: string;
	type_label?: string;
	address?: string;
	area?: string;
	province?: string;
	city?: string;
	kecamatan?: string;
	kelurahan?: string;
	rt_rw?: string;
	postal_code?: string;
	fax?: string;
	phone?: string;
	mobile?: string;
	email?: string;
	place_date_of_birth?: string;
	npwp?: string;
	siup_no?: string;
	line_of_business?: string;
	source_of_fund?: string;
	average_income?: number;
	contact_name?: string;
	contact_position?: string;
	contact_address?: string;
}

interface FinancialReviewLineItem { label: string; period1?: number; period2?: number; is_total?: boolean; }
interface AssetLineItem { description: string; amount: number; notes?: string; }
interface BankStatementPeriodRow {
	period: string;
	beginning_balance: number;
	debit: number;
	credit: number;
	ending_balance: number;
	notes?: string;
}
interface BankStatementAccount {
	bank_name: string;
	branch?: string;
	account_no: string;
	account_name: string;
	currency: string;
	notes?: string;
	rows: BankStatementPeriodRow[];
}
interface FinancialReview {
	currency?: string;
	period_label?: string;

	balance_sheet?: FinancialReviewLineItem[];
	profit_loss?: FinancialReviewLineItem[];

	liabilities?: AssetLineItem[];
	total_liabilities?: number;
	monthly_income?: AssetLineItem[];
	total_income?: number;
	net_saving?: number;
	assets?: AssetLineItem[];
	total_assets?: number;
	dscr?: number;
	bank_statements: BankStatementAccount[];
}

interface SignoffRole { code: string; label: string; }

interface ApuPptQuestion { no: string; question: string; answer: string; }
interface ApuPptParty {
	name: string;
	type: string;
	occupation_business_type: string;
	apu_ppt_status: string;
	identification_verification: string;
}
interface ApuPptData {
	customer: ApuPptParty;
	show_edd_customer: boolean;
	edd_customer_questions: ApuPptQuestion[];
	show_beneficial_owner: boolean;
	beneficial_owner: ApuPptParty;
	show_edd_bo: boolean;
	edd_bo_questions: ApuPptQuestion[];
}

interface ReportCamData {
	header: {
		cam_no: string; cont_type: string; contsts: string; bis_type: string;
		purpose_finc: string; fin_type: string; branch_name: string;
		create_date: string; cmo_name: string; cross_contract_numbers: string[];
	};
	customer: {
		name_in_id: string; address: string; city: string;
		phone1: string; phone2: string; phone3: string;
		mail_address: string; npwp: string; has_guarantor: boolean;
	};
	finance: {
		asset_value: number; dp_label: string; dp_percent: number; security: number;
		insurance_loan: number; bbn_loan: number; provision_loan: number; others_loan: number;
		net_finance: number; loan_to_value: number; type_of_finance: string;
		tenor: number; adv_arr_label: string; irr: number | null;
		selling_rate_flat: number; decl_rate: number; survey_fee_gross: number;
		notary_fee_gross: number; provision_fee: number; business_trip_fee: number; installment: number;
	};
	insurance: { name: string; type: string; gross_premium: number; net_premium: number; };
	notary: { vendor: string; fiducia_deed: number; fiducia_cert: number; };
	agency: { bbn_via: string; paid_by: string; agency_name: string; agency_fee_gross: number; bbn_fee: number; nett_agency_fee: number; };
	asset: { condition_model_year: string; brand_name: string; name_in_bpkb: string; bpkb_address: string; };
	dealer: { name: string; type: string; address: string; };
	disbursement: {
		paid_to_company: Record<string, number>;
		to_dealer: Record<string, number>;
		commission_sales: CommissionSale[];
		total_gross_commission: number;
		credit_protection: number;
		guaranteed_acceptance: string;
		advance_grace_period_months?: number;
		is_incentive_from_apm?: boolean;
		incentive_or_subsidy_from_apm?: number;
		signoff_roles?: SignoffRole[];
		related_survey_cam?: string | null;
	};
	outstanding: { process_date: string | null; rows: OutstandingRow[]; total_unit: number; total_amount: number; };
	bank_accounts: BankAccount[];
	approval_history: ApprovalRow[];
	references: ReferenceRow[];
	cam_notes: string;
	notes: string;
	revised_note?: string | null;
	pending_notes?: string;
	beneficial_owner_availability?: string;
	omitted_sections: string[];
	credit_scoring: { items: CreditScoringItem[]; total_score: number | string | null; recommendation?: string } | null;
	guarantor?: GuarantorDetail | null;
	beneficial_owner?: BeneficialOwnerDetail | null;
	customer_survey?: CustomerSurveyDetail | null;
	financial_review?: FinancialReview | null;
	apu_ppt?: ApuPptData | null;
}

const fmt = (n: number | null | undefined) => (n ? n.toLocaleString('id-ID') : '0');

function LegacyStyle() {
	return (
		<style>{`
            .cam-report table { border-collapse: collapse; width: 100%; }
            .cam-report td, .cam-report th { background-color: #FFFFFF; font-size: 11px; padding: 2px; vertical-align: top; font-family: Arial, sans-serif; }
            .cam-report .bf { border-bottom: 1px solid #000; border-right: 1px solid #000; }
            .cam-report .bf1 { border-bottom: 1px solid #000; border-right: 1px solid #000; border-left: 1px solid #000; }
            .cam-report .bf2 { border-bottom: 1px solid #000; }
            .cam-report .bf3 { border: 1px solid #000; }
            .cam-report .bf4 { border-left: 1px solid #000; border-bottom: 1px solid #000; }
            .cam-report .head { background-color: #CCCCCC; }
            .cam-report .top { border-top: 1px solid #000; }
            .cam-report .thin-top { border-top: 1px solid #000; }
            .cam-report .right { text-align: right; }
            .cam-report .center { text-align: center; }
            .cam-report .bold { font-weight: bold; }
            .cam-report .italic { font-style: italic; color: #94a3b8; }
        `}</style>
	);
}

function SectionHead({ title, colSpan = 2 }: { title: string; colSpan?: number }) {
	return (
		<tr>
			<td colSpan={colSpan} className="bf1 head top"><strong>{title}</strong></td>
		</tr>
	);
}

function SubHead({ title, colSpan = 2 }: { title: string; colSpan?: number }) {
	return (
		<tr className="head">
			<td colSpan={colSpan} className="thin-top"><strong>{title}</strong></td>
		</tr>
	);
}

function LabelRow({ label, value, align, bold, widthLabel }: { label: React.ReactNode; value: React.ReactNode; align?: 'right' | 'left'; bold?: boolean; widthLabel?: string }) {
	return (
		<tr>
			<td className={`bf1 ${bold ? 'bold' : ''}`} width={widthLabel ?? '35%'}>{label}</td>
			<td className={`bf ${align === 'right' ? 'right' : ''} ${bold ? 'bold' : ''}`}>{value}</td>
		</tr>
	);
}

function OptionalLabelRow({ label, value, align, widthLabel }: { label: React.ReactNode; value?: React.ReactNode; align?: 'right' | 'left'; widthLabel?: string }) {
	if (value === undefined || value === null || value === '') return null;
	return <LabelRow label={label} value={value} align={align} widthLabel={widthLabel} />;
}

export default function ReportCamView({ ctx }: { ctx: CamCtx }) {
	const [data, setData] = useState<ReportCamData | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		let active = true;
		setLoading(true);
		setError(null);
		api
			.get('/CAM/View/api/report-cam', { params: { applno: ctx.applno, apless: ctx.apless } })
			.then(res => { if (active) setData(res.data); })
			.catch(() => { if (active) setError('Failed to load Report CAM data.'); })
			.finally(() => { if (active) setLoading(false); });
		return () => { active = false; };
	}, [ctx.applno, ctx.apless]);

	if (loading) return <div className="p-8 text-center text-sm text-slate-500">Loading report…</div>;
	if (error || !data) return <div className="p-8 text-center text-sm text-red-500">{error || 'No data.'}</div>;

	const { header, customer, finance, insurance, notary, agency, asset, dealer,
		disbursement, outstanding, bank_accounts, approval_history, references,
		cam_notes, omitted_sections, credit_scoring, guarantor, beneficial_owner,
		customer_survey, financial_review, revised_note, pending_notes,
		beneficial_owner_availability, apu_ppt } = data;

	const disbursementRows: [string, string][] = [
		['Asset Value', 'asset_value'],
		[finance.dp_label, 'dp'],
		['Survey Fee Gross', 'survey_fee_gross'],
		['Notary Fee Gross', 'notary_fee_gross'],
		['Provision Fee', 'provision_fee'],
		['Business Trip Fee', 'business_trip_fee'],
		['Insurance', 'insurance'],
		['First Installment', 'first_installment'],
		['Agency Fee Gross', 'agency_fee_gross'],
		['BBN Fee', 'bbn_fee'],
	];

	return (
		<div>
			<div className="mb-3 flex items-center justify-between rounded-xl bg-white px-4 py-2 shadow print:hidden">
				<span className="text-sm font-semibold text-slate-700">Report CAM — {header.cam_no}</span>
				<button
					onClick={() => window.print()}
					className="rounded-lg bg-blue-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
				>
					Print
				</button>
			</div>

			{/* {omitted_sections.length > 0 && (
				<div className="mb-4 rounded-xl border border-amber-300 bg-amber-50 p-3 text-xs text-amber-800 print:hidden">
					<p className="font-semibold">Sections not yet included in this view:</p>
					<ul className="ml-4 list-disc">
						{omitted_sections.map(s => <li key={s}>{s}</li>)}
					</ul>
					<p className="mt-1">APU PPT and Deviation Form are already available as their own tabs above.</p>
				</div>
			)} */}

			<LegacyStyle />

			<div className="cam-report bg-white p-4 shadow print:shadow-none">
				<table cellPadding={2} cellSpacing={0} style={{ backgroundColor: '#FFFFFF' }}>
					<tbody>
						<tr>
							<td className="center" style={{ paddingLeft: 90 }}><strong><u>CREDIT APPROVAL MEMORANDUM (CAM)</u></strong></td>
							<td className="right"><i>{header.cmo_name}</i></td>
						</tr>
						<tr>
							<td className="center" style={{ paddingLeft: 90 }}><strong>{header.bis_type} / {header.purpose_finc} / {header.fin_type} - {header.branch_name}</strong></td>
							<td className="right"><i>{header.create_date}</i></td>
						</tr>
					</tbody>
				</table>

				<table cellPadding={2} cellSpacing={0}>
					<tbody>
						<tr>
							<td className="bf1 top" width="30%">CAM No. {header.cam_no} — {header.cont_type}</td>
							<td className="bf top" width="20%">Status</td>
							<td className="bf top" width="20%">{header.contsts}</td>
							<td className="bf top">Cross Disbursement No</td>
						</tr>
					</tbody>
				</table>

				<div style={{ height: 10 }} />

				<table cellPadding={0} cellSpacing={2}>
					<tbody>
						<tr>
							<td width="50%" style={{ border: 0 }}>
								<table cellPadding={2} cellSpacing={0}>
									<tbody>
										<SectionHead title="CUSTOMER" />
										<LabelRow label="Name" value={customer.name_in_id} />
										<LabelRow label="Address" value={`${customer.address}, ${customer.city}`} />
										<LabelRow label="Telephone" value={`(H) ${customer.phone2} (O) ${customer.phone1} (HP) ${customer.phone3}`} />
										<LabelRow label="Mail Address" value={customer.mail_address} />
										<LabelRow label="NPWP" value={customer.npwp} />
										<LabelRow label="Guarantor" value={customer.has_guarantor ? 'Available' : 'Not Available'} />
									</tbody>
								</table>

								<table cellPadding={2} cellSpacing={0}>
									<tbody>
										<SectionHead title="FINANCE INFORMATION" />
										<LabelRow label="Asset Value" value={fmt(finance.asset_value)} align="right" />
										<LabelRow label={`${finance.dp_label} (${finance.dp_percent}%)`} value={fmt(finance.security)} align="right" />
										<LabelRow label="Insurance Loan" value={fmt(finance.insurance_loan)} align="right" />
										<LabelRow label="BBN Loan" value={fmt(finance.bbn_loan)} align="right" />
										<LabelRow label="Provision Loan" value={fmt(finance.provision_loan)} align="right" />
										<LabelRow label="Others Loan" value={fmt(finance.others_loan)} align="right" />
										<LabelRow label="Total Net Finance" value={fmt(finance.net_finance)} align="right" bold />
										<LabelRow label="Loan to Value" value={`${finance.loan_to_value}%`} align="right" />
										<LabelRow label="Type of Finance" value={finance.type_of_finance} align="right" />
										<LabelRow label={`Term ${finance.tenor} Months`} value={`(${finance.adv_arr_label}) 1 unit`} align="right" />
										<LabelRow label="IRR" value={finance.irr != null ? `${finance.irr}%` : '-'} align="right" />
										<LabelRow label="Selling Rate (Flat/ Yr)" value={`${finance.selling_rate_flat}% / ${finance.decl_rate}%`} align="right" />
										<LabelRow label="Survey Fee Gross" value={fmt(finance.survey_fee_gross)} align="right" />
										<LabelRow label="Notary Fee Gross" value={fmt(finance.notary_fee_gross)} align="right" />
										<LabelRow label="Provision Fee" value={fmt(finance.provision_fee)} align="right" />
										<LabelRow label="Business Trip Fee" value={fmt(finance.business_trip_fee)} align="right" />
										<LabelRow label="Installment" value={fmt(finance.installment)} align="right" />
									</tbody>
								</table>

								<table cellPadding={2} cellSpacing={0}>
									<tbody>
										<SectionHead title="INSURANCE" />
										<LabelRow label="Insurance Name" value={insurance.name} />
										<LabelRow label="Type" value={insurance.type} />
										<LabelRow label="Gross Premium" value={fmt(insurance.gross_premium)} align="right" />
										<LabelRow label="Net Premium" value={fmt(insurance.net_premium)} align="right" />
										<SectionHead title="NOTARY / LEGITIMATE" />
										<LabelRow label="Vendor Name" value={notary.vendor} />
										<LabelRow label="Fiducia/ Cessie/ Any Deed" value={fmt(notary.fiducia_deed)} align="right" />
										<LabelRow label="Fiducia/ Cessie/ Any Certificate" value={fmt(notary.fiducia_cert)} align="right" />
									</tbody>
								</table>

								<table cellPadding={2} cellSpacing={0}>
									<tbody>
										<SectionHead title="AGENCY" />
										<LabelRow label="BBN Via" value={agency.bbn_via} align="right" />
										<LabelRow label="Paid By" value={agency.paid_by} align="right" />
										<LabelRow label="Agency Name" value={agency.agency_name} align="right" />
										<LabelRow label="Agency Fee Gross" value={fmt(agency.agency_fee_gross)} align="right" />
										<LabelRow label="BBN Fee" value={fmt(agency.bbn_fee)} align="right" />
										<LabelRow label="Nett Agency Fee" value={fmt(agency.nett_agency_fee)} align="right" />
									</tbody>
								</table>
							</td>

							<td width="50%" style={{ border: 0 }}>
								<table cellPadding={2} cellSpacing={0}>
									<tbody>
										<SectionHead title="ASSET INFORMATION" />
										<LabelRow label="Condition/ Model/ Year" value={asset.condition_model_year} widthLabel="41%" />
										<LabelRow label="Brand Name" value={asset.brand_name} widthLabel="41%" />
										<LabelRow label="Name in BPKB" value={asset.name_in_bpkb} widthLabel="41%" />
										<LabelRow label="Address" value={asset.bpkb_address} widthLabel="41%" />
										<SectionHead title="DEALER INFORMATION" />
										<LabelRow label="Name" value={dealer.name} widthLabel="41%" />
										<LabelRow label="Dealer Type" value={dealer.type} widthLabel="41%" />
										<LabelRow label="Address" value={dealer.address} widthLabel="41%" />
									</tbody>
								</table>

								<table cellPadding={2} cellSpacing={0}>
									<tbody>
										<tr>
											<td className="bf3 head"><strong>DISBURSEMENT</strong></td>
											<td className="bf3 head center"><strong>PAID TO COMPANY</strong></td>
											<td className="bf3 head">&nbsp;</td>
										</tr>
										{disbursementRows.map(([label, key]) => (
											<tr key={key}>
												<td className="bf1" width="41%">{label}</td>
												<td className="bf right" width="29%">({fmt(disbursement.paid_to_company[key] ?? 0)})</td>
												<td className="bf right">({fmt(disbursement.to_dealer[key] ?? 0)})</td>
											</tr>
										))}
										{disbursement.advance_grace_period_months != null && (
											<tr>
												<td className="bf1">Advance Grace Period<span style={{ float: 'right' }}>{disbursement.advance_grace_period_months} Month(s)</span></td>
												<td className="bf right">(0)</td>
												<td className="bf right">({fmt(disbursement.to_dealer.advance_grace_period ?? 0)})</td>
											</tr>
										)}
										<tr>
											<td className="bf1">Subsidy From Dealer</td>
											<td className="bf right">(0)</td>
											<td className="bf right">({fmt(disbursement.to_dealer.subsidy_from_dealer)})</td>
										</tr>
										<tr>
											<td className="bf1">Refund To Dealer</td>
											<td className="bf right">0</td>
											<td className="bf right">{fmt(disbursement.to_dealer.refund_to_dealer)}</td>
										</tr>
										<tr>
											<td className="bf1">Disbursement to Dealer</td>
											<td className="bf right">0</td>
											<td className="bf right">{fmt(disbursement.to_dealer.disbursement_to_dealer)}</td>
										</tr>
										<tr>
											<td className="bf1">Commission to Dealer (Gross)</td>
											<td className="bf right">0</td>
											<td className="bf right">{fmt(disbursement.to_dealer.commission_to_dealer_gross)}</td>
										</tr>
										<tr>
											<td className="bf1 bold">Total Payment to Dealer</td>
											<td className="bf right">0</td>
											<td className="bf right bold">{fmt(disbursement.to_dealer.total_payment_to_dealer)}</td>
										</tr>
										{disbursement.incentive_or_subsidy_from_apm != null && (
											<tr>
												<td className="bf1">{disbursement.is_incentive_from_apm ? 'Incentive from APM' : 'Subsidy from APM'}</td>
												<td className="bf right">0</td>
												<td className="bf right">{fmt(disbursement.incentive_or_subsidy_from_apm)}</td>
											</tr>
										)}
										<tr>
											<td colSpan={3} className="bf1 head top"><strong>COMMISSION TO SALESMAN &amp; BROKER</strong></td>
										</tr>
										{disbursement.commission_sales.length === 0 ? (
											<tr><td colSpan={3} className="bf italic">None</td></tr>
										) : disbursement.commission_sales.map((s, i) => (
											<tr key={i}>
												<td className="bf1">{s.label}</td>
												<td className="bf right" colSpan={2}>{fmt(s.amount)}</td>
											</tr>
										))}
										<tr>
											<td className="bf1 bold">Total Gross Commission</td>
											<td className="bf right bold" colSpan={2}>{fmt(disbursement.total_gross_commission)}</td>
										</tr>
										<tr>
											<td colSpan={3} className="bf1 head top"><strong>CREDIT PROTECTION</strong></td>
										</tr>
										<LabelRow label="Credit Protection" value={fmt(disbursement.credit_protection)} align="right" widthLabel="41%" />
										<LabelRow label="Guaranteed Acceptance" value={disbursement.guaranteed_acceptance} align="right" widthLabel="41%" />
									</tbody>
								</table>
							</td>
						</tr>
					</tbody>
				</table>

				{disbursement.signoff_roles && disbursement.signoff_roles.length > 0 && (
					<table cellPadding={2} cellSpacing={0}>
						<tbody>
							<tr>
								<td className="bf1 head top">&nbsp;</td>
								<td className="bf head" colSpan={disbursement.signoff_roles.length - 1}>&nbsp;</td>
								<td className="bf head">
									<strong>Related Survey CAM</strong>
								</td>
							</tr>
							<tr>
								{disbursement.signoff_roles.map((role, i) => (
									<td key={role.code} className={i === 0 ? 'bf1' : 'bf'}>{role.label}</td>
								))}
								<td className="bf">{disbursement.related_survey_cam || <span className="italic">None</span>}</td>
							</tr>
							<tr>
								{disbursement.signoff_roles.map((role, i) => (
									<td key={role.code} className={i === 0 ? 'bf1' : 'bf'}>DATE :</td>
								))}
								<td className="bf">&nbsp;</td>
							</tr>
						</tbody>
					</table>
				)}

				<table cellPadding={2} cellSpacing={0}>
					<tbody>
						<tr>
							<td colSpan={3} className="bf1 head top center"><strong>OUTSTANDING</strong></td>
						</tr>
						<tr>
							<td className="bf4 top" width="30%"><strong>OUTSTANDING</strong></td>
							<td colSpan={2} className="bf3">
								<strong><i>Process Date: {outstanding.process_date ?? ''}</i></strong>
							</td>
						</tr>
						<tr className="center">
							<td rowSpan={2} className="bf4">&nbsp;</td>
							<td colSpan={2} className="bf1">OUTSTANDING EXPOSURE</td>
						</tr>
						<tr className="center">
							<td className="bf1" width="15%">Unit</td>
							<td className="bf">Amount</td>
						</tr>
						{outstanding.rows.map(r => (
							<tr key={r.label}>
								<td className="bf4">{r.label}</td>
								<td className="bf1 right">{r.unit}</td>
								<td className="bf right">{fmt(r.amount)}</td>
							</tr>
						))}
						<tr>
							<td className="bf4 bold">Total</td>
							<td className="bf1 right bold">{outstanding.total_unit}</td>
							<td className="bf right bold">{fmt(outstanding.total_amount)}</td>
						</tr>
					</tbody>
				</table>

				{header.cross_contract_numbers.length > 0 && (
					<table cellPadding={2} cellSpacing={1}>
						<tbody>
							<SectionHead title="CROSS CONTRACT" colSpan={1} />
							<tr><td className="bf1">{header.cross_contract_numbers.join(' / ')}</td></tr>
						</tbody>
					</table>
				)}

				{bank_accounts.length > 0 && (
					<table cellPadding={2} cellSpacing={0} style={{ marginTop: 10 }}>
						<tbody>
							<tr>
								<td colSpan={4} className="bf3 head center"><strong>Bank Account For DISBURSEMENT</strong></td>
							</tr>
							<tr className="center">
								<td className="bf1" width="34%"><strong>Bank - Branch</strong></td>
								<td className="bf" width="29%"><strong>Account No.</strong></td>
								<td className="bf" width="16%"><strong>Name</strong></td>
								<td className="bf" width="21%"><strong>Amount</strong></td>
							</tr>
							{bank_accounts.map((b, i) => (
								<tr key={i}>
									<td className="bf1">{b.bank_branch}</td>
									<td className="bf">{b.account_no}</td>
									<td className="bf">{b.account_name}</td>
									<td className="bf right">{fmt(b.amount)}</td>
								</tr>
							))}
						</tbody>
					</table>
				)}

				<table cellPadding={2} cellSpacing={0} style={{ marginTop: 10 }}>
					<tbody>
						<tr>
							<td colSpan={Math.max(approval_history.length, 1)} className="bf1 head top center">
								<strong>CREDIT COMMITTEE APPROVAL</strong>
							</td>
						</tr>
						<tr className="center">
							{approval_history.length === 0 ? (
								<td className="bf italic">No approvals yet.</td>
							) : approval_history.map((a, i) => (
								<td key={i} className="bf" style={{ height: 50 }}>
									<span style={{ color: 'red' }}>
										<strong>{a.sent_to_admin ? <em><u>APPROVED</u></em> : 'APPROVED'}</strong>
									</span>
									<br />{a.full_name}
								</td>
							))}
						</tr>
						{approval_history.length > 0 && (
							<tr className="center">
								{approval_history.map((a, i) => (
									<td key={i} className="bf">{a.date}</td>
								))}
							</tr>
						)}
					</tbody>
				</table>

				{customer_survey && (
					<table cellPadding={2} cellSpacing={1} style={{ marginTop: 10 }}>
						<tbody>
							<tr>
								<td colSpan={2} className="bf3 head center"><strong>CUSTOMER SURVEY REPORT</strong></td>
							</tr>
							<tr>
								<td colSpan={2} className="bf2"><strong>CUSTOMER SURVEY DETAIL</strong></td>
							</tr>

							<SubHead title="Character" />
							<OptionalLabelRow label="Credit History" value={customer_survey.credit_history} />
							<OptionalLabelRow label="Reference" value={customer_survey.reference} />
							<OptionalLabelRow label="Working/ Business Experience" value={customer_survey.work_experience} />
							<OptionalLabelRow label="Business Size" value={customer_survey.business_size} />
							<OptionalLabelRow label="Company Status" value={customer_survey.company_status} />
							<OptionalLabelRow label="Scale of Business" value={customer_survey.scale_of_business} />

							<SubHead title="Capital" />
							<OptionalLabelRow label="Living" value={customer_survey.living} />
							<OptionalLabelRow label={`${customer_survey.living ?? 'Living'} Status`} value={customer_survey.living_status} />
							<OptionalLabelRow label="Car Ownership" value={customer_survey.car_ownership} />
							<OptionalLabelRow label="Business Location" value={customer_survey.business_location} />
							<OptionalLabelRow label="Total Unit Owned (Vehicle)" value={customer_survey.total_unit_owned} />
							<OptionalLabelRow label="Unit Free from Finance" value={customer_survey.unit_free_from_finance} />
							<OptionalLabelRow label="Estimated Total Assets" value={customer_survey.estimated_total_assets_as_of} />

							<SubHead title="Capacity" />
							<OptionalLabelRow label="Job/ Occupation" value={customer_survey.job_customer} />
							<OptionalLabelRow
								label="Fixed Monthly Income (Rp.)"
								value={customer_survey.fixed_monthly_income != null
									? `${fmt(customer_survey.fixed_monthly_income)}${customer_survey.income_source_note ? ' / ' + customer_survey.income_source_note : ''}`
									: undefined}
							/>
							<OptionalLabelRow label="Spouse Income (Rp.)" value={customer_survey.spouse_income != null ? fmt(customer_survey.spouse_income) : undefined} />
							<OptionalLabelRow
								label="Total Other Income per Month (Rp.)"
								value={customer_survey.other_income != null
									? `${fmt(customer_survey.other_income)} ${customer_survey.other_income_note ?? ''}`
									: undefined}
							/>
							<OptionalLabelRow
								label="Total Income per Month (Rp.)"
								value={customer_survey.total_income != null
									? `${fmt(customer_survey.total_income)} ${customer_survey.total_income_note ?? ''}`
									: undefined}
							/>
							<OptionalLabelRow label="Average Income per Year (Rp.)" value={customer_survey.average_income_per_year != null ? fmt(customer_survey.average_income_per_year) : undefined} />
							<OptionalLabelRow
								label="Monthly Profit (Rp.)"
								value={customer_survey.monthly_profit != null
									? `${fmt(customer_survey.monthly_profit)} ${customer_survey.monthly_profit_note ?? ''}`
									: undefined}
							/>
							<OptionalLabelRow label="Sales/ Month (Rp.)" value={customer_survey.sales_per_month != null ? fmt(customer_survey.sales_per_month) : undefined} />
							<OptionalLabelRow label="Net Profit : Sales" value={customer_survey.net_profit_ratio} />

							<SubHead title="Collateral" />
							<OptionalLabelRow label="Unit Type" value={customer_survey.unit_type} />
							<OptionalLabelRow label="Loan to Value" value={customer_survey.loan_to_value != null ? `${customer_survey.loan_to_value}%` : undefined} />
							<OptionalLabelRow label="Insurance" value={customer_survey.insurance_payment} />
							<OptionalLabelRow label="Guarantor" value={customer_survey.guarantor_available} />
							<OptionalLabelRow label="Payment Method" value={customer_survey.payment_method} />

							<SubHead title="Condition" />
							<OptionalLabelRow label="Credit Period" value={customer_survey.credit_period} />
							<OptionalLabelRow label="Total Outstanding" value={customer_survey.total_outstanding_bucket} />
							<OptionalLabelRow label="Dealer Status" value={customer_survey.dealer_status} />
							<OptionalLabelRow label="Usage of Car" value={customer_survey.usage_of_car} />

							<tr>
								<td colSpan={2} className="bf2"><strong>CUSTOMER JOB HISTORY</strong></td>
							</tr>
							<tr>
								<td colSpan={2} style={{ padding: 0 }}>
									<table cellPadding={1} cellSpacing={0}>
										<tbody>
											<tr className="center">
												<td className="bf1 top" width="5%"><strong>No.</strong></td>
												<td className="bf top" width="8%"><strong>From</strong></td>
												<td className="bf top" width="8%"><strong>Until</strong></td>
												<td className="bf top" width="15%"><strong>Company Name</strong></td>
												<td className="bf top" width="20%"><strong>Company Address</strong></td>
												<td className="bf top" width="10%"><strong>District/ City</strong></td>
												<td className="bf top" width="10%"><strong>Province</strong></td>
												<td className="bf top" width="10%"><strong>Post Code</strong></td>
												<td className="bf top" width="15%"><strong>Position</strong></td>
												<td className="bf top" width="10%"><strong>Phone</strong></td>
											</tr>
											{customer_survey.job_history.length === 0 ? (
												<tr><td className="bf1 italic center" colSpan={10}>No job history</td></tr>
											) : customer_survey.job_history.map((j, i) => (
												<tr key={i}>
													<td className="bf1 center">{i + 1}</td>
													<td className="bf">{j.from}</td>
													<td className="bf">{j.until}</td>
													<td className="bf">{j.company}</td>
													<td className="bf">{j.address}</td>
													<td className="bf">{j.city}</td>
													<td className="bf">{j.province}</td>
													<td className="bf">{j.postal_code}</td>
													<td className="bf">{j.position}</td>
													<td className="bf">{j.phone}</td>
												</tr>
											))}
										</tbody>
									</table>
								</td>
							</tr>

							{customer_survey.sid_checking.length > 0 && (
								<>
									<SubHead title="File SID Checking" />
									<tr>
										<td colSpan={2} className="bf2" style={{ padding: 0 }}>
											{customer_survey.sid_checking.map((s, i) => (
												<table key={i} cellPadding={2} cellSpacing={0} style={{ marginBottom: 8 }}>
													<tbody>
														<LabelRow label="Subject" value={s.subject} />
														<LabelRow label="Credit Bureau" value={s.credit_bureau} />
														<LabelRow label="Status" value={s.status} />
														<LabelRow label="Score" value={s.score} />
														<LabelRow label="Grade" value={s.grade} />
														{s.file_url && (
															<LabelRow
																label="File"
																value={
																	<a href={s.file_url} target="_blank" rel="noopener noreferrer" style={{ color: '#2563eb', textDecoration: 'underline' }}>
																		{s.file_label ?? 'Download'}
																	</a>
																}
															/>
														)}
													</tbody>
												</table>
											))}
											{customer_survey.sid_checking_notes && (
												<table cellPadding={2} cellSpacing={0}>
													<tbody>
														<LabelRow label="Notes" value={customer_survey.sid_checking_notes} />
													</tbody>
												</table>
											)}
										</td>
									</tr>
								</>
							)}
						</tbody>
					</table>
				)}

				{apu_ppt && (
					<table cellPadding={2} cellSpacing={1} style={{ marginTop: 10 }}>
						<tbody>
							<tr>
								<td colSpan={2} className="bf3 head center"><strong>APU PPT</strong></td>
							</tr>
							<tr>
								<td colSpan={2} className="bf2"><strong>CUSTOMER'S DATA</strong></td>
							</tr>
							<LabelRow label="Customer Name" value={apu_ppt.customer.name} />
							<LabelRow label="Customer Type" value={apu_ppt.customer.type} />
							<LabelRow label="Occupation/ Business Type" value={apu_ppt.customer.occupation_business_type} />
							<LabelRow label="APU PPT Status" value={apu_ppt.customer.apu_ppt_status} />
							<LabelRow label="Identification and Verification Process" value={apu_ppt.customer.identification_verification} />

							{apu_ppt.show_edd_customer && (
								<>
									<tr><td colSpan={2}><strong>Enhanced Due Diligence (EDD) Customer Questionnaire</strong></td></tr>
									{apu_ppt.edd_customer_questions.map(q => (
										<tr key={q.no}>
											<td className="bf1">{q.no}. {q.question}</td>
											<td className="bf right bold">{q.answer}</td>
										</tr>
									))}
								</>
							)}

							<tr>
								<td colSpan={2} className="bf2"><strong>BENEFICIAL OWNER'S DATA</strong></td>
							</tr>
							<LabelRow label="Beneficial Owner Name" value={apu_ppt.beneficial_owner.name} />
							<LabelRow label="Beneficial Owner Type" value={apu_ppt.beneficial_owner.type} />
							<LabelRow label="Occupation/ Business Type" value={apu_ppt.beneficial_owner.occupation_business_type} />
							<LabelRow label="APU PPT Status" value={apu_ppt.beneficial_owner.apu_ppt_status} />
							<LabelRow label="Identification and Verification Process" value={apu_ppt.beneficial_owner.identification_verification} />

							{apu_ppt.show_edd_bo && (
								<>
									<tr><td colSpan={2}><strong>Enhanced Due Diligence (EDD) Beneficial Owner Questionnaire</strong></td></tr>
									{apu_ppt.edd_bo_questions.map(q => (
										<tr key={q.no}>
											<td className="bf1">{q.no}. {q.question}</td>
											<td className="bf right bold">{q.answer}</td>
										</tr>
									))}
								</>
							)}
						</tbody>
					</table>
				)}

				{guarantor && (
					<table cellPadding={2} cellSpacing={0} style={{ marginTop: 10 }}>
						<tbody>
							<tr>
								<td colSpan={2} className="bf3 head center"><strong>GUARANTOR DETAIL REVIEW</strong></td>
							</tr>
							<LabelRow label="Guarantor Name" value={guarantor.name} />
							<OptionalLabelRow
								label={guarantor.entity_type === 'PR' ? 'Name Without Title' : 'Type'}
								value={guarantor.name_without_title ? `${guarantor.name_without_title}${guarantor.category ? ' - ' + guarantor.category : ''}` : guarantor.category}
							/>
							<OptionalLabelRow label="Gender" value={guarantor.gender} />
							<OptionalLabelRow label={guarantor.entity_type === 'PR' ? 'Date of Birth' : 'Establishment Date'} value={guarantor.date_of_birth} />
							<OptionalLabelRow label="Place of Birth" value={guarantor.place_of_birth} />
							<OptionalLabelRow label="Address" value={guarantor.address} />
							<OptionalLabelRow label="Mobile Phone No. / Fax" value={[guarantor.phone, guarantor.fax].filter(Boolean).join(' - ') || undefined} />
							<OptionalLabelRow label="Email" value={guarantor.email} />
							<OptionalLabelRow label="Relationship with Customer" value={guarantor.relationship_with_customer} />
							<OptionalLabelRow label="BI Customer Type" value={guarantor.bi_customer_type} />
							<OptionalLabelRow label="Occupation" value={guarantor.occupation} />
							<OptionalLabelRow label="Total Exposure (Rp)" value={guarantor.total_exposure != null ? fmt(guarantor.total_exposure) : undefined} />
							<OptionalLabelRow label="NPWP" value={guarantor.npwp} />
							<OptionalLabelRow label="Citizenship" value={[guarantor.citizenship, guarantor.nationality].filter(Boolean).join(' / ') || undefined} />
							<OptionalLabelRow label="ID Card No./ Validity" value={guarantor.id_card ? `${guarantor.id_card} / ${guarantor.id_card_validity ?? 'No Expire date'}` : undefined} />
							<OptionalLabelRow label="Passport No." value={guarantor.passport_no} />
							<OptionalLabelRow label="Marital Status" value={guarantor.marital_status} />
							<OptionalLabelRow label="Line of Business" value={guarantor.line_of_business} />
							{(guarantor.spouse_name || guarantor.contract_signer_name) && (
								<>
									<tr><td colSpan={2} className="bf2"><strong>{guarantor.entity_type === 'PR' ? 'SPOUSE' : 'CONTRACT SIGNER'}</strong></td></tr>
									<OptionalLabelRow label="Name" value={guarantor.spouse_name ?? guarantor.contract_signer_name} />
									<OptionalLabelRow label="Position" value={guarantor.contract_signer_position} />
									<OptionalLabelRow label="ID Card No." value={guarantor.spouse_id_card ?? guarantor.contract_signer_id_card} />
									<OptionalLabelRow label="Address" value={guarantor.spouse_address} />
									<OptionalLabelRow label="Status" value={guarantor.spouse_status} />
									<OptionalLabelRow label="Citizenship" value={guarantor.spouse_citizenship} />
									<OptionalLabelRow label="Mobile" value={guarantor.spouse_mobile ?? guarantor.contract_signer_mobile} />
									<OptionalLabelRow label="Email" value={guarantor.spouse_email ?? guarantor.contract_signer_email} />
								</>
							)}
						</tbody>
					</table>
				)}

				{beneficial_owner && (
					<table cellPadding={2} cellSpacing={0} style={{ marginTop: 10 }}>
						<tbody>
							<tr>
								<td colSpan={2} className="bf3 head center"><strong>BENEFICIAL OWNER DETAIL REVIEW</strong></td>
							</tr>
							<LabelRow label="Beneficial Owner Name" value={beneficial_owner.name} />
							<OptionalLabelRow label="Alias Name" value={beneficial_owner.alias} />
							<OptionalLabelRow label="Beneficial Owner Type" value={beneficial_owner.type_label} />
							<OptionalLabelRow label={beneficial_owner.entity_type === 'PR' ? 'ID Address' : 'Address'} value={beneficial_owner.address} />
							<OptionalLabelRow label="Area" value={beneficial_owner.area} />
							<OptionalLabelRow label="Province" value={beneficial_owner.province} />
							<OptionalLabelRow label="District/ City" value={beneficial_owner.city} />
							<OptionalLabelRow label="Kecamatan" value={beneficial_owner.kecamatan} />
							<OptionalLabelRow label="Kelurahan" value={beneficial_owner.kelurahan} />
							<OptionalLabelRow label="RT/ RW" value={beneficial_owner.rt_rw} />
							<OptionalLabelRow label="Post Code" value={beneficial_owner.postal_code} />
							<OptionalLabelRow label="Fax" value={beneficial_owner.fax} />
							<OptionalLabelRow label="Phone" value={beneficial_owner.phone} />
							<OptionalLabelRow label="Mobile" value={beneficial_owner.mobile} />
							<OptionalLabelRow label="Email" value={beneficial_owner.email} />
							<OptionalLabelRow label={beneficial_owner.entity_type === 'PR' ? 'Place/ Date of Birth' : 'Establishment Place/ Date'} value={beneficial_owner.place_date_of_birth} />
							<OptionalLabelRow label="NPWP" value={beneficial_owner.npwp} />
							<OptionalLabelRow label="SIUP No" value={beneficial_owner.siup_no} />
							<OptionalLabelRow label="Line of Business" value={beneficial_owner.line_of_business} />
							<OptionalLabelRow label="Source of Fund" value={beneficial_owner.source_of_fund} />
							<OptionalLabelRow label="Average Income per Year" value={beneficial_owner.average_income != null ? fmt(beneficial_owner.average_income) : undefined} />
							{beneficial_owner.contact_name && (
								<>
									<tr><td colSpan={2} className="bf2"><strong>CONTACT PERSON</strong></td></tr>
									<LabelRow label="Name" value={beneficial_owner.contact_name} />
									<OptionalLabelRow label="Position" value={beneficial_owner.contact_position} />
									<OptionalLabelRow label="Address" value={beneficial_owner.contact_address} />
								</>
							)}
						</tbody>
					</table>
				)}

				{financial_review && (
					<table cellPadding={2} cellSpacing={0} style={{ marginTop: 10 }}>
						<tbody>
							<tr>
								<td className="bf1 head top center"><strong>FINANCIAL INFORMATION REVIEW</strong></td>
							</tr>
							<tr>
								<td style={{ padding: 0 }}>
									{financial_review.period_label && (
										<div style={{ padding: 2 }}>{financial_review.period_label}</div>
									)}

									{financial_review.balance_sheet !== undefined && (
										<table cellPadding={2} cellSpacing={0} style={{ width: '70%', margin: '0 auto' }}>
											<tbody>
												<tr><td colSpan={3} className="bf1 top"><strong>Balance Sheet</strong></td></tr>
												{financial_review.balance_sheet.length === 0 ? (
													<tr><td colSpan={3} className="bf italic">No data</td></tr>
												) : financial_review.balance_sheet.map((r, i) => (
													<tr key={i}>
														<td className={`bf1 ${r.is_total ? 'bold' : ''}`} width="60%">{r.label}</td>
														<td className={`bf right ${r.is_total ? 'bold' : ''}`} width="20%">{fmt(r.period1)}</td>
														<td className={`bf right ${r.is_total ? 'bold' : ''}`} width="20%">{fmt(r.period2)}</td>
													</tr>
												))}
											</tbody>
										</table>
									)}

									{financial_review.profit_loss !== undefined && (
										<table cellPadding={2} cellSpacing={0} style={{ width: '70%', margin: '0 auto' }}>
											<tbody>
												<tr><td colSpan={2} className="bf1 top"><strong>Profit / Loss</strong></td></tr>
												{financial_review.profit_loss.length === 0 ? (
													<tr><td colSpan={2} className="bf italic">No data</td></tr>
												) : financial_review.profit_loss.map((r, i) => (
													<tr key={i}>
														<td className={`bf1 ${r.is_total ? 'bold' : ''}`} width="60%">{r.label}</td>
														<td className={`bf right ${r.is_total ? 'bold' : ''}`}>Rp. {fmt(r.period1)}</td>
													</tr>
												))}
											</tbody>
										</table>
									)}

									{financial_review.liabilities !== undefined && (
										<table cellPadding={2} cellSpacing={0} style={{ width: '70%', margin: '0 auto' }}>
											<tbody>
												<tr><td colSpan={3} className="bf1 top"><strong>Liabilities</strong></td></tr>
												{financial_review.liabilities.map((r, i) => (
													<tr key={i}>
														<td className="bf1" width="30%">{r.notes}</td>
														<td className="bf" width="45%">{r.description}</td>
														<td className="bf right" width="25%">{fmt(r.amount)}</td>
													</tr>
												))}
												<tr>
													<td colSpan={2} className="bf1 right bold">Total</td>
													<td className="bf right bold">{fmt(financial_review.total_liabilities)}</td>
												</tr>
											</tbody>
										</table>
									)}

									{financial_review.monthly_income !== undefined && (
										<table cellPadding={2} cellSpacing={0} style={{ width: '70%', margin: '0 auto' }}>
											<tbody>
												<tr><td colSpan={2} className="bf1 top"><strong>Estimated Monthly Income</strong></td></tr>
												{financial_review.monthly_income.map((r, i) => (
													<tr key={i}>
														<td className="bf1">{r.description}</td>
														<td className="bf right">{fmt(r.amount)}</td>
													</tr>
												))}
												<tr>
													<td className="bf1 right bold">Total Income</td>
													<td className="bf right bold">{fmt(financial_review.total_income)}</td>
												</tr>
												<tr>
													<td className="bf1">Liabilities</td>
													<td className="bf right">{fmt(financial_review.total_liabilities)}</td>
												</tr>
												<tr>
													<td className="bf1 right bold">Net saving</td>
													<td className="bf right bold">{fmt(financial_review.net_saving)}</td>
												</tr>
											</tbody>
										</table>
									)}

									{financial_review.dscr != null && (
										<table cellPadding={2} cellSpacing={0} style={{ width: '70%', margin: '0 auto' }}>
											<tbody>
												<tr>
													<td className="bf1 top">DSCR</td>
													<td className="bf right top">{financial_review.dscr}</td>
												</tr>
											</tbody>
										</table>
									)}

									{financial_review.assets !== undefined && (
										<table cellPadding={2} cellSpacing={0} style={{ width: '70%', margin: '0 auto' }}>
											<tbody>
												<tr><td colSpan={3} className="bf3"><strong>Customer Asset Ownership</strong></td></tr>
												<tr className="center">
													<td className="bf1" width="30%"><strong>Descriptions</strong></td>
													<td className="bf" width="25%"><strong>Amount Estimated</strong></td>
													<td className="bf" width="45%"><strong>Notes</strong></td>
												</tr>
												{financial_review.assets.map((r, i) => (
													<tr key={i}>
														<td className="bf1">{r.description}</td>
														<td className="bf right">{fmt(r.amount)}</td>
														<td className="bf">{r.notes}</td>
													</tr>
												))}
												<tr>
													<td className="bf1 right bold">Total Assets</td>
													<td className="bf right bold">{fmt(financial_review.total_assets)}</td>
													<td className="bf">&nbsp;</td>
												</tr>
											</tbody>
										</table>
									)}

									{financial_review.bank_statements.length > 0 && financial_review.bank_statements.map((acc, i) => (
										<table key={i} cellPadding={2} cellSpacing={0} style={{ width: '70%', margin: '10px auto' }}>
											<tbody>
												<LabelRow label="Bank" value={`${acc.bank_name}${acc.branch ? ' / ' + acc.branch : ''}`} />
												<LabelRow label="Account Number" value={acc.account_no} />
												<LabelRow label="Account name" value={acc.account_name} />
												<LabelRow label="Currency" value={acc.currency} />
												{acc.notes && <LabelRow label="Notes" value={acc.notes} />}
												<tr><td colSpan={6} className="bf3 head center"><strong>BANK SUMMARY</strong></td></tr>
												<tr className="center">
													<td className="bf1" width="11%"><strong>Month - Year</strong></td>
													<td className="bf" width="13%"><strong>Beginning Balance</strong></td>
													<td className="bf" width="11%"><strong>Debet</strong></td>
													<td className="bf" width="11%"><strong>Credit</strong></td>
													<td className="bf" width="11%"><strong>Ending Balance</strong></td>
													<td className="bf" width="25%"><strong>Notes</strong></td>
												</tr>
												{acc.rows.map((r, j) => (
													<tr key={j}>
														<td className="bf1">{r.period}</td>
														<td className="bf right">{fmt(r.beginning_balance)}</td>
														<td className="bf right">{fmt(r.debit)}</td>
														<td className="bf right">{fmt(r.credit)}</td>
														<td className="bf right">{fmt(r.ending_balance)}</td>
														<td className="bf center">{r.notes}</td>
													</tr>
												))}
											</tbody>
										</table>
									))}
								</td>
							</tr>
						</tbody>
					</table>
				)}

				<table cellPadding={2} cellSpacing={0} style={{ marginTop: 10 }}>
					<tbody>
						<tr>
							<td className="bf1 head top center"><strong>CAM NOTES / COMMENTS</strong></td>
						</tr>
						<tr>
							<td className="bf1" style={{ minHeight: 50 }}>
								<div dangerouslySetInnerHTML={{ __html: cam_notes || '<span class="italic">None</span>' }} />
								{revised_note && (
									<p style={{ marginTop: 8 }}><i><strong>Revised Note</strong></i> : {revised_note}</p>
								)}
							</td>
						</tr>
					</tbody>
				</table>

				{pending_notes && (
					<table cellPadding={2} cellSpacing={0} style={{ marginTop: 10 }}>
						<tbody>
							<tr>
								<td className="bf3 head center"><strong>PENDING DOCUMENT NOTES</strong></td>
							</tr>
							<tr>
								<td className="bf1" style={{ minHeight: 50 }}>
									<div dangerouslySetInnerHTML={{ __html: pending_notes }} />
								</td>
							</tr>
						</tbody>
					</table>
				)}

				{references.length > 0 && (
					<table cellPadding={2} cellSpacing={0} style={{ marginTop: 10 }}>
						<tbody>
							<tr>
								<td colSpan={4} className="bf1 head top center"><strong>REFERENCES</strong></td>
							</tr>
							<tr className="center">
								<td className="bf1"><strong>No.</strong></td>
								<td className="bf"><strong>Name</strong></td>
								<td className="bf"><strong>Telephone Number</strong></td>
								<td className="bf"><strong>Remark / Notes</strong></td>
							</tr>
							{references.map((r, i) => (
								<tr key={i} className="center">
									<td className="bf1">{i + 1}</td>
									<td className="bf">{r.name}</td>
									<td className="bf">{r.phone}</td>
									<td className="bf">{r.remark}</td>
								</tr>
							))}
						</tbody>
					</table>
				)}

				{credit_scoring && (
					<table cellPadding={2} cellSpacing={0} style={{ marginTop: 10 }}>
						<tbody>
							<tr>
								<td colSpan={3} className="bf3 head center"><strong>CREDIT SCORING</strong></td>
							</tr>
							<tr><td colSpan={3}>Credit Scoring Result</td></tr>
							{credit_scoring.items.map((s, i) => (
								<tr key={i}>
									<td width="10%">{i + 1}. {s.description}</td>
									<td width="5%">: {s.result}</td>
									<td width="85%">({s.score})</td>
								</tr>
							))}
							<tr><td colSpan={3}>Note : 5 (Good) ...... 1 (Poor)</td></tr>
							<tr>
								<td width="15%"><strong>Final Result</strong></td>
								<td width="15%"><strong>: <u>{credit_scoring.recommendation ?? ''}</u></strong></td>
								<td width="70%"><strong>({credit_scoring.total_score ?? '-'})</strong></td>
							</tr>
						</tbody>
					</table>
				)}

				{beneficial_owner_availability && (
					<table cellPadding={2} cellSpacing={0} style={{ marginTop: 10 }}>
						<tbody>
							<tr>
								<td style={{ fontSize: 12 }}>Beneficial Owner : {beneficial_owner_availability}</td>
							</tr>
						</tbody>
					</table>
				)}
			</div>
		</div>
	);
}