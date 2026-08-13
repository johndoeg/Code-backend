import React, { useEffect, useState } from 'react';
import api from '../../../../../api/axiosInstance';
import type { CamCtx } from '../CamViewTabs';

interface SurveySummary {
    contract_status: string;
    customer_name: string;
    brand: string;
    model: string;
    type: string;
    chassis: string;
    bpkb_name: string;
    bpkb_age_suffix: string;
    engine: string;
    bpkb_address: string;
    year: string;
    condition: string;
    supplier: string;
    color: string;
    police_no: string;
}

interface SurveyFile {
    id: number;
    name: string;
    download_url: string | null;
}

interface EquipmentSurveyFileData {
    no_data: boolean;
    summary: SurveySummary;
    notes: string;
    files: {
        vehicle_photo_front: SurveyFile[];
        vehicle_photo: SurveyFile[];
        vehicle_data_bpkb: SurveyFile[];
        vehicle_data: SurveyFile[];
    };
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

function FileList({ files }: { files: SurveyFile[] }) {
    if (files.length === 0) {
        return <span className="text-sm text-slate-400">No file uploaded</span>;
    }
    return (
        <ul className="space-y-1">
            {files.map((f) => (
                <li key={f.id}>
                    {f.download_url ? (
                        <a href={f.download_url} className="text-sm text-blue-600 underline hover:text-blue-700">
                            {f.name}
                        </a>
                    ) : (
                        <span className="text-sm text-slate-700">{f.name}</span>
                    )}
                </li>
            ))}
        </ul>
    );
}

function PhotoBox({ title, files }: { title: string; files: SurveyFile[] }) {
    return (
        <div className="rounded-xl border border-slate-100 p-4">
            <h3 className="mb-2 text-sm font-semibold text-slate-600">{title}</h3>
            <FileList files={files} />
        </div>
    );
}

export default function EquipmentSurveyFileView({ ctx }: { ctx: CamCtx }) {
    const [data, setData] = useState<EquipmentSurveyFileData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let active = true;
        setLoading(true);
        setError(null);
        api
            .get('/CAM/View/api/equipment-survey-file', { params: { apless: ctx.apless, applno: ctx.applno } })
            .then((res) => {
                if (active) setData(res.data);
            })
            .catch(() => {
                if (active) setError('Failed to load survey file.');
            })
            .finally(() => {
                if (active) setLoading(false);
            });
        return () => {
            active = false;
        };
    }, [ctx.apless, ctx.applno]);

    if (loading) {
        return (
            <div className="rounded-2xl bg-white p-8 text-center text-sm text-slate-500 shadow">
                Loading survey file…
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

    const s = data.summary;

    return (
        <div>
            <Card title="Vehicle Survey Report Form">
                <dl className="grid grid-cols-1 gap-x-8 sm:grid-cols-2">
                    <Field label="Contract Status" value={s.contract_status} />
                    <Field label="Brand / Model / Type" value={`${s.brand}/${s.model}/${s.type}`} />
                    <Field label="Customer Name" value={s.customer_name} />
                    <Field label="Chassis" value={s.chassis} />
                    <Field label="BPKB Name" value={`${s.bpkb_name}${s.bpkb_age_suffix}`} />
                    <Field label="Engine" value={s.engine} />
                    <Field label="BPKB Address" value={s.bpkb_address} />
                    <Field label="Year / Condition" value={`${s.year}/${s.condition}`} />
                    <Field label="Supplier" value={s.supplier} />
                    <Field label="Color / Police No." value={`${s.color}/${s.police_no}`} />
                </dl>
            </Card>

            <Card title="Vehicle Photo">
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <PhotoBox title="Front only" files={data.files.vehicle_photo_front} />
                    <PhotoBox title="Vehicle Photo" files={data.files.vehicle_photo} />
                </div>
            </Card>

            <Card title="Vehicle Data">
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <PhotoBox
                        title="BPKB, Faktur, Sertifikat NIK (if any) and/or Form A (if any)"
                        files={data.files.vehicle_data_bpkb}
                    />
                    <PhotoBox title="STNK" files={data.files.vehicle_data} />
                </div>
            </Card>

            <Card title="Notes">
                <div className="min-h-[120px] rounded-lg border border-slate-100 bg-slate-50 p-4 text-base text-slate-700 whitespace-pre-wrap">
                    {data.notes || <span className="text-sm text-slate-400">No notes.</span>}
                </div>
            </Card>
        </div>
    );
}