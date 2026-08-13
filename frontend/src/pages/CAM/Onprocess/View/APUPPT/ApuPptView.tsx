import React, { useEffect, useState } from 'react';
import api from '../../../../../api/axiosInstance';
import type { CamCtx } from '../CamViewTabs';

interface PartyDetail {
    name: string;
    type: string;
    occupation_business_type: string;
    apu_ppt_status: string;
    identification_verification: string;
}

interface EddQuestion {
    no: string;
    question: string;
    answer: string;
}

interface ApuPptData {
    no_data: boolean;
    customer: PartyDetail;
    show_edd_customer: boolean;
    edd_customer_questions: EddQuestion[];
    show_beneficial_owner: boolean;
    beneficial_owner: PartyDetail | null;
    show_edd_bo: boolean;
    edd_bo_questions: EddQuestion[];
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
    return (
        <div className="mb-4 overflow-hidden rounded-2xl bg-white shadow">
            <div className="border-b border-slate-100 bg-slate-50 px-5 py-3">
                <h2 className="text-sm font-semibold text-slate-700">{title}</h2>
            </div>
            <div className="p-5">{children}</div>
        </div>
    );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
    return (
        <div className="flex items-baseline justify-between gap-3 border-b border-slate-100 py-2 last:border-0">
            <dt className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</dt>
            <dd className="text-right text-sm text-slate-700">{value || '-'}</dd>
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

function PartyFields({ p }: { p: PartyDetail }) {
    return (
        <dl>
            <Field label="Customer Name" value={p.name} />
            <Field label="Customer Type" value={p.type} />
            <Field label="Occupation / Business Type" value={p.occupation_business_type} />
            <Field label="APU PPT Status" value={p.apu_ppt_status} />
            <Field label="Identification and Verification Process" value={p.identification_verification} />
        </dl>
    );
}

function EddQuestionnaire({ title, questions }: { title: string; questions: EddQuestion[] }) {
    return (
        <Card title={title}>
            <table className="w-full text-sm">
                <tbody>
                    {questions.map((q) => (
                        <tr key={q.no} className="border-b border-slate-100 last:border-0">
                            <td className="w-8 py-2 pr-3 text-center text-slate-400">{q.no}.</td>
                            <td className="py-2 pr-3">{q.question}</td>
                            <td className="w-20 py-2 text-right font-semibold">{q.answer}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </Card>
    );
}

export default function ApuPptView({ ctx }: { ctx: CamCtx }) {
    const [data, setData] = useState<ApuPptData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let active = true;
        setLoading(true);
        setError(null);
        api
            .get('/CAM/View/api/apu-ppt', { params: { applno: ctx.applno } })
            .then((res) => {
                if (active) setData(res.data);
            })
            .catch(() => {
                if (active) setError('Failed to load APU PPT data.');
            })
            .finally(() => {
                if (active) setLoading(false);
            });
        return () => {
            active = false;
        };
    }, [ctx.applno]);

    if (loading) {
        return (
            <div className="rounded-2xl bg-white p-8 text-center text-sm text-slate-500 shadow">
                Loading APU PPT…
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
        <div>
            <Card title="Customer">
                <PartyFields p={data.customer} />
            </Card>

            {data.show_edd_customer && (
                <EddQuestionnaire title="Enhanced Due Diligence (EDD) Customer Questionnaire" questions={data.edd_customer_questions} />
            )}

            {data.show_beneficial_owner && data.beneficial_owner && (
                <Card title="Beneficial Owner">
                    <PartyFields p={data.beneficial_owner} />
                </Card>
            )}

            {data.show_edd_bo && (
                <EddQuestionnaire title="Enhanced Due Diligence (EDD) Beneficial Owner Questionnaire" questions={data.edd_bo_questions} />
            )}
        </div>
    );
}