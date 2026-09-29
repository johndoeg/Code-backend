import React, { useEffect, useState } from 'react';
import api from '../../../../../api/axiosInstance';
import type { CamCtx } from '../CamViewTabs';

interface CreditRecommendationData {
    has_data: boolean;
    strength?: string;
    weakness?: string;
    tbo?: string;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
    return (
        <div className="mb-4 overflow-hidden rounded-2xl bg-white shadow">
            <div className="border-b border-slate-100 bg-slate-50 px-5 py-3">
                <h2 className="text-sm font-semibold text-slate-700">{title}</h2>
            </div>
            <div className="p-5">{children}</div>
        </div>
    );
}

function RichText({ html }: { html: string }) {
    if (!html) return <p className="text-sm italic text-slate-400">—</p>;
    return (
        <div
            className="prose prose-sm max-w-none text-slate-700"
            dangerouslySetInnerHTML={{ __html: html }}
        />
    );
}

function NoDataCard() {
    return (
        <div className="rounded-2xl bg-white p-12 text-center shadow">
            <p className="text-2xl font-bold text-red-600">NO DATA</p>
        </div>
    );
}

export default function CreditRecommendationView({ ctx }: { ctx: CamCtx }) {
    const [data, setData] = useState<CreditRecommendationData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let active = true;
        setLoading(true);
        setError(null);
        api
            .get('/CAM/View/api/credit-recommendation', { params: { applno: ctx.applno } })
            .then((res) => {
                if (active) setData(res.data);
            })
            .catch(() => {
                if (active) setError('Failed to load credit recommendation.');
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
                Loading credit recommendation…
            </div>
        );
    }
    if (error) {
        return (
            <div className="rounded-2xl bg-white p-8 text-center text-sm text-red-500 shadow">
                {error}
            </div>
        );
    }

    if (!data || !data.has_data) {
        return <NoDataCard />;
    }

    return (
        <div>
            <Section title="Strength">
                <RichText html={data.strength || ''} />
            </Section>
            <Section title="Weakness">
                <RichText html={data.weakness || ''} />
            </Section>
            <Section title="TBO / TC">
                <RichText html={data.tbo || ''} />
            </Section>
        </div>
    );
}