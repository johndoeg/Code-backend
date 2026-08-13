import { useEffect, useState } from 'react';
import api from '../../../../../api/axiosInstance';
import type { CamCtx } from '../CamViewTabs';

interface NotesData {
    no_data: boolean;
    notes: string;
}

function NoDataCard() {
    return (
        <div className="rounded-2xl bg-white p-12 text-center shadow">
            <p className="text-2xl font-bold text-red-600">NO DATA</p>
        </div>
    );
}

function NotesCard({ title, endpoint, ctx }: { title: string; endpoint: string; ctx: CamCtx }) {
    const [data, setData] = useState<NotesData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let active = true;
        setLoading(true);
        setError(null);
        api
            .get(endpoint, { params: { applno: ctx.applno } })
            .then((res) => {
                if (active) setData(res.data);
            })
            .catch(() => {
                if (active) setError('Failed to load notes.');
            })
            .finally(() => {
                if (active) setLoading(false);
            });
        return () => {
            active = false;
        };
    }, [endpoint, ctx.applno]);

    if (loading) {
        return (
            <div className="rounded-2xl bg-white p-8 text-center text-sm text-slate-500 shadow">
                Loading notes…
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
                <h2 className="text-sm font-semibold text-slate-700">{title}</h2>
            </div>
            <div className="prose prose-sm max-w-none p-5 text-slate-700" dangerouslySetInnerHTML={{ __html: data.notes }} />
        </div>
    );
}

export function CamNotesView({ ctx }: { ctx: CamCtx }) {
    return <NotesCard title="CAM Notes" endpoint="/CAM/View/api/cam-notes" ctx={ctx} />;
}

export function OtherNotesView({ ctx }: { ctx: CamCtx }) {
    return <NotesCard title="Customer Notes" endpoint="/CAM/View/api/other-notes" ctx={ctx} />;
}