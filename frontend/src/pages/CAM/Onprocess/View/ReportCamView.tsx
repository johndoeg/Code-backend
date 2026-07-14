import React, { useEffect, useState } from 'react';
import api from '../../../../api/axiosInstance';
import type { CamCtx } from './CamViewTabs';

interface BankAccount { bank_branch: string; account_no: string; account_name: string; amount: number; }
interface ApprovalRow { full_name: string; date: string; sent_to_admin: boolean; }
interface ReferenceRow { name: string; phone: string; remark: string; }
interface CommissionSale { label: string; amount: number; }
interface OutstandingRow { label: string; unit: number; amount: number; }
interface CreditScoringItem { description: string; result: string; score: number | string; }

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
    };
    outstanding: { process_date: string | null; rows: OutstandingRow[]; total_unit: number; total_amount: number; };
    bank_accounts: BankAccount[];
    approval_history: ApprovalRow[];
    references: ReferenceRow[];
    cam_notes: string;
    notes: string;
    omitted_sections: string[];
    credit_scoring: { items: CreditScoringItem[]; total_score: number | string | null } | null;
}

const fmt = (n: number | null | undefined) => (n ? n.toLocaleString('id-ID') : '0');

function Section({ title, children }: { title: string; children: React.ReactNode }) {
    return (
        <div className="mb-3 border border-slate-800 text-xs">
            <div className="bg-slate-200 px-2 py-1 font-bold text-center border-b border-slate-800">{title}</div>
            <div className="p-2">{children}</div>
        </div>
    );
}

function Row({ label, value, bold }: { label: string; value: React.ReactNode; bold?: boolean }) {
    return (
        <div className={`flex justify-between border-b border-slate-200 py-1 last:border-0 ${bold ? 'font-bold' : ''}`}>
            <span className="text-slate-600">{label}</span>
            <span className="text-right">{value}</span>
        </div>
    );
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
            .get('/CAM/api/view/report-cam', { params: { applno: ctx.applno, apless: ctx.apless } })
            .then(res => { if (active) setData(res.data); })
            .catch(() => { if (active) setError('Failed to load Report CAM data.'); })
            .finally(() => { if (active) setLoading(false); });
        return () => { active = false; };
    }, [ctx.applno, ctx.apless]);

    if (loading) return <div className="p-8 text-center text-sm text-slate-500">Loading report…</div>;
    if (error || !data) return <div className="p-8 text-center text-sm text-red-500">{error || 'No data.'}</div>;

    const { header, customer, finance, insurance, notary, agency, asset, dealer,
        disbursement, outstanding, bank_accounts, approval_history, references,
        cam_notes, omitted_sections, credit_scoring } = data;

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

            {omitted_sections.length > 0 && (
                <div className="mb-4 rounded-xl border border-amber-300 bg-amber-50 p-3 text-xs text-amber-800 print:hidden">
                    <p className="font-semibold">Sections not yet included in this view:</p>
                    <ul className="ml-4 list-disc">
                        {omitted_sections.map(s => <li key={s}>{s}</li>)}
                    </ul>
                    <p className="mt-1">APU PPT and Deviation Form are already available as their own tabs above.</p>
                </div>
            )}

            <div className="bg-white p-4 shadow print:shadow-none">
                <div className="mb-2 text-center">
                    <div className="font-bold underline">CREDIT APPROVAL MEMORANDUM (CAM)</div>
                    <div className="text-xs">{header.bis_type} / {header.purpose_finc} / {header.fin_type} - {header.branch_name}</div>
                    <div className="text-xs text-slate-500">{header.create_date} — CMO: {header.cmo_name}</div>
                </div>
                <div className="mb-3 grid grid-cols-2 gap-2 border border-slate-800 p-2 text-xs">
                    <div>CAM No. {header.cam_no} — {header.cont_type}</div>
                    <div>Status: {header.contsts}</div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                    <div>
                        <Section title="CUSTOMER">
                            <Row label="Name" value={customer.name_in_id} />
                            <Row label="Address" value={`${customer.address}, ${customer.city}`} />
                            <Row label="Telephone" value={`(H) ${customer.phone2} (O) ${customer.phone1} (HP) ${customer.phone3}`} />
                            <Row label="Mail Address" value={customer.mail_address} />
                            <Row label="NPWP" value={customer.npwp} />
                            <Row label="Guarantor" value={customer.has_guarantor ? 'Available' : 'Not Available'} />
                        </Section>

                        <Section title="FINANCE INFORMATION">
                            <Row label="Asset Value" value={fmt(finance.asset_value)} />
                            <Row label={`${finance.dp_label} (${finance.dp_percent}%)`} value={fmt(finance.security)} />
                            <Row label="Insurance Loan" value={fmt(finance.insurance_loan)} />
                            <Row label="BBN Loan" value={fmt(finance.bbn_loan)} />
                            <Row label="Provision Loan" value={fmt(finance.provision_loan)} />
                            <Row label="Others Loan" value={fmt(finance.others_loan)} />
                            <Row label="Total Net Finance" value={fmt(finance.net_finance)} bold />
                            <Row label="Loan to Value" value={`${finance.loan_to_value}%`} />
                            <Row label="Type of Finance" value={finance.type_of_finance} />
                            <Row label={`Term ${finance.tenor} Months`} value={`(${finance.adv_arr_label}) 1 unit`} />
                            <Row label="IRR" value={finance.irr != null ? `${finance.irr}%` : '-'} />
                            <Row label="Selling Rate (Flat/Yr)" value={`${finance.selling_rate_flat}% / ${finance.decl_rate}%`} />
                            <Row label="Survey Fee Gross" value={fmt(finance.survey_fee_gross)} />
                            <Row label="Notary Fee Gross" value={fmt(finance.notary_fee_gross)} />
                            <Row label="Provision Fee" value={fmt(finance.provision_fee)} />
                            <Row label="Business Trip Fee" value={fmt(finance.business_trip_fee)} />
                            <Row label="Installment" value={fmt(finance.installment)} />
                        </Section>

                        <Section title="INSURANCE">
                            <Row label="Insurance Name" value={insurance.name} />
                            <Row label="Type" value={insurance.type} />
                            <Row label="Gross Premium" value={fmt(insurance.gross_premium)} />
                            <Row label="Net Premium" value={fmt(insurance.net_premium)} />
                        </Section>

                        <Section title="NOTARY / LEGITIMATE">
                            <Row label="Vendor Name" value={notary.vendor} />
                            <Row label="Fiducia/Cessie/Any Deed" value={fmt(notary.fiducia_deed)} />
                            <Row label="Fiducia/Cessie/Any Certificate" value={fmt(notary.fiducia_cert)} />
                        </Section>

                        <Section title="AGENCY">
                            <Row label="BBN Via" value={agency.bbn_via} />
                            <Row label="Paid By" value={agency.paid_by} />
                            <Row label="Agency Name" value={agency.agency_name} />
                            <Row label="Agency Fee Gross" value={fmt(agency.agency_fee_gross)} />
                            <Row label="BBN Fee" value={fmt(agency.bbn_fee)} />
                            <Row label="Nett Agency Fee" value={fmt(agency.nett_agency_fee)} />
                        </Section>
                    </div>

                    <div>
                        <Section title="ASSET INFORMATION">
                            <Row label="Condition/Model/Year" value={asset.condition_model_year} />
                            <Row label="Brand Name" value={asset.brand_name} />
                            <Row label="Name in BPKB" value={asset.name_in_bpkb} />
                            <Row label="Address" value={asset.bpkb_address} />
                        </Section>

                        <Section title="DEALER INFORMATION">
                            <Row label="Name" value={dealer.name} />
                            <Row label="Dealer Type" value={dealer.type} />
                            <Row label="Address" value={dealer.address} />
                        </Section>

                        <Section title="DISBURSEMENT">
                            <table className="w-full text-xs">
                                <thead>
                                    <tr className="border-b border-slate-800 text-left">
                                        <th className="py-1"></th>
                                        <th className="py-1 text-right">Paid to Company</th>
                                        <th className="py-1 text-right">Disbursement</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {[
                                        ['Asset Value', 'asset_value'],
                                        [disbursement.to_dealer ? finance.dp_label : 'DP', 'dp'],
                                        ['Survey Fee Gross', 'survey_fee_gross'],
                                        ['Notary Fee Gross', 'notary_fee_gross'],
                                        ['Provision Fee', 'provision_fee'],
                                        ['Business Trip Fee', 'business_trip_fee'],
                                        ['Insurance', 'insurance'],
                                        ['First Installment', 'first_installment'],
                                        ['Agency Fee Gross', 'agency_fee_gross'],
                                        ['BBN Fee', 'bbn_fee'],
                                    ].map(([label, key]) => (
                                        <tr key={key} className="border-b border-slate-100">
                                            <td className="py-0.5">{label}</td>
                                            <td className="py-0.5 text-right">({fmt(disbursement.paid_to_company[key] ?? 0)})</td>
                                            <td className="py-0.5 text-right">({fmt(disbursement.to_dealer[key] ?? 0)})</td>
                                        </tr>
                                    ))}
                                    <tr className="border-b border-slate-100">
                                        <td className="py-0.5">Subsidy From Dealer</td>
                                        <td className="py-0.5 text-right">(0)</td>
                                        <td className="py-0.5 text-right">({fmt(disbursement.to_dealer.subsidy_from_dealer)})</td>
                                    </tr>
                                    <tr className="border-b border-slate-100">
                                        <td className="py-0.5">Refund To Dealer</td>
                                        <td className="py-0.5 text-right">0</td>
                                        <td className="py-0.5 text-right">{fmt(disbursement.to_dealer.refund_to_dealer)}</td>
                                    </tr>
                                    <tr className="border-b border-slate-100 font-bold">
                                        <td className="py-0.5">Disbursement to Dealer</td>
                                        <td className="py-0.5 text-right">0</td>
                                        <td className="py-0.5 text-right">{fmt(disbursement.to_dealer.disbursement_to_dealer)}</td>
                                    </tr>
                                    <tr className="border-b border-slate-100">
                                        <td className="py-0.5">Commission to Dealer (Gross)</td>
                                        <td className="py-0.5 text-right">0</td>
                                        <td className="py-0.5 text-right">{fmt(disbursement.to_dealer.commission_to_dealer_gross)}</td>
                                    </tr>
                                    <tr className="font-bold">
                                        <td className="py-0.5">Total Payment to Dealer</td>
                                        <td className="py-0.5 text-right">0</td>
                                        <td className="py-0.5 text-right">{fmt(disbursement.to_dealer.total_payment_to_dealer)}</td>
                                    </tr>
                                </tbody>
                            </table>

                            <div className="mt-2 border-t border-slate-800 pt-2">
                                <p className="mb-1 font-bold">COMMISSION TO SALESMAN &amp; BROKER</p>
                                {disbursement.commission_sales.length === 0 ? (
                                    <p className="text-slate-400 italic">None</p>
                                ) : disbursement.commission_sales.map((s, i) => (
                                    <React.Fragment key={i}><Row label={s.label} value={fmt(s.amount)} /></React.Fragment>
                                ))}
                                <Row label="Total Gross Commission" value={fmt(disbursement.total_gross_commission)} bold />
                            </div>

                            <div className="mt-2 border-t border-slate-800 pt-2">
                                <p className="mb-1 font-bold">CREDIT PROTECTION</p>
                                <Row label="Credit Protection" value={fmt(disbursement.credit_protection)} />
                                <Row label="Guaranteed Acceptance" value={disbursement.guaranteed_acceptance} />
                            </div>
                        </Section>
                    </div>
                </div>

                <Section title="OUTSTANDING">
                    {outstanding.process_date && (
                        <p className="mb-1 text-slate-500">Process Date: {outstanding.process_date}</p>
                    )}
                    <table className="w-full text-xs">
                        <thead>
                            <tr className="border-b border-slate-800 text-center">
                                <th className="py-1 text-left">Category</th>
                                <th className="py-1">Unit</th>
                                <th className="py-1">Amount</th>
                            </tr>
                        </thead>
                        <tbody>
                            {outstanding.rows.map(r => (
                                <tr key={r.label} className="border-b border-slate-100">
                                    <td className="py-0.5">{r.label}</td>
                                    <td className="py-0.5 text-right">{r.unit}</td>
                                    <td className="py-0.5 text-right">{fmt(r.amount)}</td>
                                </tr>
                            ))}
                            <tr className="font-bold">
                                <td className="py-0.5">Total</td>
                                <td className="py-0.5 text-right">{outstanding.total_unit}</td>
                                <td className="py-0.5 text-right">{fmt(outstanding.total_amount)}</td>
                            </tr>
                        </tbody>
                    </table>
                </Section>

                {header.cross_contract_numbers.length > 1 && (
                    <Section title="CROSS CONTRACT">
                        <p>{header.cross_contract_numbers.join(' / ')}</p>
                    </Section>
                )}

                {bank_accounts.length > 0 && (
                    <Section title="Bank Account For DISBURSEMENT">
                        <table className="w-full text-xs">
                            <thead>
                                <tr className="border-b border-slate-800 text-left">
                                    <th className="py-1">Bank - Branch</th>
                                    <th className="py-1">Account No.</th>
                                    <th className="py-1">Name</th>
                                    <th className="py-1 text-right">Amount</th>
                                </tr>
                            </thead>
                            <tbody>
                                {bank_accounts.map((b, i) => (
                                    <tr key={i} className="border-b border-slate-100">
                                        <td className="py-0.5">{b.bank_branch}</td>
                                        <td className="py-0.5">{b.account_no}</td>
                                        <td className="py-0.5">{b.account_name}</td>
                                        <td className="py-0.5 text-right">{fmt(b.amount)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </Section>
                )}

                <Section title="CREDIT COMMITTEE APPROVAL">
                    {approval_history.length === 0 ? (
                        <p className="italic text-slate-400">No approvals yet.</p>
                    ) : (
                        <div className="grid auto-cols-fr grid-flow-col gap-2 text-center">
                            {approval_history.map((a, i) => (
                                <div key={i} className="border border-slate-300 p-2">
                                    <p className="font-bold text-red-600">
                                        {a.sent_to_admin ? 'APPROVED (Sent to Admin)' : 'APPROVED'}
                                    </p>
                                    <p>{a.full_name}</p>
                                    <p className="text-slate-500">{a.date}</p>
                                </div>
                            ))}
                        </div>
                    )}
                </Section>

                <Section title="CAM NOTES / COMMENTS">
                    <div dangerouslySetInnerHTML={{ __html: cam_notes || '<span class="italic text-slate-400">None</span>' }} />
                </Section>

                {references.length > 0 && (
                    <Section title="REFERENCES">
                        <table className="w-full text-xs">
                            <thead>
                                <tr className="border-b border-slate-800 text-left">
                                    <th className="py-1">Name</th>
                                    <th className="py-1">Phone</th>
                                    <th className="py-1">Remark</th>
                                </tr>
                            </thead>
                            <tbody>
                                {references.map((r, i) => (
                                    <tr key={i} className="border-b border-slate-100">
                                        <td className="py-0.5">{r.name}</td>
                                        <td className="py-0.5">{r.phone}</td>
                                        <td className="py-0.5">{r.remark}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </Section>
                )}

                {credit_scoring && (
                    <Section title="CREDIT SCORING">
                        {credit_scoring.items.map((s, i) => (
                            <React.Fragment key={i}><Row label={`${i + 1}. ${s.description}`} value={`${s.result} (${s.score})`} /></React.Fragment>
                        ))}
                        <Row label="Final Total Score" value={String(credit_scoring.total_score ?? '-')} bold />
                        <p className="mt-1 text-slate-400">Note: 5 (Good) ...... 1 (Poor)</p>
                    </Section>
                )}
            </div>
        </div>
    );
}