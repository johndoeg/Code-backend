import React, { useEffect, useState } from 'react';
import api from '../../../../../api/axiosInstance';
import type { CamCtx } from '../CamViewTabs';

interface DeviationRow {
    no: number;
    standard_desc: string;
    deviation_desc: string;
    reason: string;
    is_other: boolean;
}

interface DeviationData {
    no_data: boolean;
    rows: DeviationRow[];
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

function NoDataCard() {
    return (
        <div className="rounded-2xl bg-white p-12 text-center shadow">
            <p className="text-2xl font-bold text-red-600">NO DATA</p>
        </div>
    );
}

function NumberedList({ rows, field }: { rows: DeviationRow[]; field: 'standard_desc' | 'deviation_desc' | 'reason' }) {
    return (
        <ol className="space-y-1.5">
            {rows.map((r) => (
                <li key={r.no} className="flex gap-2 text-sm text-slate-700">
                    <span className="w-6 shrink-0 text-slate-400">{r.no}.</span>
                    <span className={r.is_other ? 'italic' : ''}>{r[field] || '-'}</span>
                </li>
            ))}
        </ol>
    );
}

export default function DeviationView({ ctx }: { ctx: CamCtx }) {
    const [data, setData] = useState<DeviationData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let active = true;
        setLoading(true);
        setError(null);
        api
            .get('/CAM/View/api/deviation', { params: { applno: ctx.applno } })
            .then((res) => {
                if (active) setData(res.data);
            })
            .catch(() => {
                if (active) setError('Failed to load deviation data.');
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
                Loading deviation data…
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
        <Card title="Deviation Form">
            <div className="space-y-6">
                <div>
                    <h3 className="mb-2 text-sm font-semibold text-slate-600">Standard Condition</h3>
                    <NumberedList rows={data.rows} field="standard_desc" />
                </div>
                <div>
                    <h3 className="mb-2 text-sm font-semibold text-slate-600">Deviation</h3>
                    <NumberedList rows={data.rows} field="deviation_desc" />
                </div>
                <div>
                    <h3 className="mb-2 text-sm font-semibold text-slate-600">Reason</h3>
                    <NumberedList rows={data.rows} field="reason" />
                </div>
            </div>
        </Card>
    );
}