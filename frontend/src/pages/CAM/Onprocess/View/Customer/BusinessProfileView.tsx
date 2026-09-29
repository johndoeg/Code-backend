import React, { useEffect, useState } from 'react';
import api from '../../../../../api/axiosInstance';
import { isImageFile } from '../../../../../constants/DefaultValue';
import type { CamCtx } from '../CamViewTabs';
import ViewContractInformation from './ViewContractInformation';

interface TableBlock {
    type: 'table';
    title: string | null;
    columns: string[];
    rows: string[][];
}

interface KeyValueBlock {
    type: 'key_value';
    title: string;
    rows: [string, string][];
}

interface TextBlock {
    type: 'text';
    title: string;
    content: string;
}

interface DetailParams {
    management_nm: string;
    share_status: string;
}

interface ManagementDetailRow {
    no: number;
    name: string;
    id_card: string;
    address: string;
    detail_params: DetailParams | null;
}

interface ManagementDetailBlock {
    type: 'management_detail';
    title: string;
    columns: string[];
    rows: ManagementDetailRow[];
}

interface DocumentFile {
    id: number;
    name: string;
    download_url: string | null;
}

interface DocumentsBlock {
    type: 'documents';
    title: string;
    rows: DocumentFile[];
}

type Block = TableBlock | KeyValueBlock | TextBlock | ManagementDetailBlock | DocumentsBlock;

interface BusinessProfile {
    lessee_cat: string;
    lessee_nm: string;
    period: string;
    blocks: Block[];
}

interface PreviewState {
    open: boolean;
    name: string;
    url: string;
}

const PREVIEW_CLOSED: PreviewState = { open: false, name: '', url: '' };

const DocPreviewModal: React.FC<{ state: PreviewState; onClose: () => void }> = ({ state, onClose }) => {
    const [imgError, setImgError] = useState(false);

    useEffect(() => {
        setImgError(false);
    }, [state.url]);

    if (!state.open) return null;

    const cleanName = state.name.split("?")[0];
    const isImage = isImageFile(cleanName);
    const isPdf = cleanName.split(".").pop()?.toLowerCase() === "pdf";

    return (
        <div
            onClick={onClose}
            style={{
                position: "fixed", inset: 0,
                background: "rgba(0,0,0,.7)",
                zIndex: 9999, display: "flex",
                justifyContent: "center", alignItems: "center",
            }}
        >
            <div
                onClick={(e) => e.stopPropagation()}
                style={{
                    width: "90%", height: "90%",
                    background: "#fff", borderRadius: 10,
                    overflow: "hidden", display: "flex",
                    flexDirection: "column",
                }}
            >
                <div style={{
                    padding: "12px 16px",
                    borderBottom: "1px solid #e5e7eb",
                    display: "flex", justifyContent: "space-between", alignItems: "center",
                }}>
                    <span style={{ fontWeight: 600, fontSize: ".9rem" }}>{state.name}</span>
                    <button type="button" onClick={onClose} style={{ cursor: "pointer", background: "none", border: "none", fontSize: "1.2rem" }}>✕</button>
                </div>
                <div style={{ flex: 1, overflow: "hidden", padding: 20 }}>
                    {isImage && !imgError ? (
                        <img src={state.url} alt={state.name} style={{ width: "100%", height: "100%", objectFit: "contain" }} onError={() => setImgError(true)} />
                    ) : isPdf ? (
                        <iframe title={state.name} src={state.url} width="100%" height="100%" />
                    ) : (
                        <div style={{ textAlign: "center", paddingTop: 40 }}>
                            <p style={{ marginBottom: 12, color: "#64748b" }}>
                                {imgError ? "Failed to load image." : "Preview not available for this file type."}
                            </p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

const DocActionButton: React.FC<{ file: DocumentFile; onPreview: (file: DocumentFile) => void }> = ({ file, onPreview }) => {
    const [hovered, setHovered] = useState(false);

    if (!file.download_url) {
        return <span className="text-xs text-slate-300">Unavailable</span>;
    }

    return (
        <button
            type="button"
            onClick={() => onPreview(file)}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
            style={{
                display: "inline-flex", alignItems: "center", gap: 6,
                border: `1px solid ${hovered ? "#ea580c" : "#f97316"}`,
                background: hovered ? "#f97316" : "#fff7ed",
                color: hovered ? "#fff" : "#c2410c",
                borderRadius: 6, padding: "5px 12px", fontSize: 13, fontWeight: 500,
                cursor: "pointer", transition: "background 0.15s, color 0.15s, border-color 0.15s",
            }}
        >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                <circle cx="12" cy="12" r="3" />
            </svg>
            View
        </button>
    );
};

function SectionHeader({ children }: { children: React.ReactNode }) {
    return (
        <div className="border-b border-t border-slate-200 bg-slate-50 px-6 py-3 first:border-t-0">
            <h2 className="text-xs font-bold uppercase tracking-wide text-slate-500">{children}</h2>
        </div>
    );
}

const thCell = "border border-slate-300 bg-slate-100 px-4 py-2 text-left text-[11px] font-bold uppercase tracking-wide text-slate-600";
const tdCell = "border border-slate-200 px-4 py-2.5 text-sm text-slate-700";

function TableBlockView({ block }: { block: TableBlock }) {
    return (
        <div className="overflow-x-auto">
            <table className="w-full min-w-[600px] border border-slate-300 border-collapse text-sm">
                <thead>
                    <tr>
                        {block.columns.map((col) => (
                            <th key={col} className={thCell}>{col}</th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {block.rows.length === 0 ? (
                        <tr><td className={tdCell} colSpan={block.columns.length}>No data.</td></tr>
                    ) : (
                        block.rows.map((row, ri) => (
                            <tr key={ri}>
                                {row.map((cell, ci) => (
                                    <td key={ci} className={tdCell}>{cell}</td>
                                ))}
                            </tr>
                        ))
                    )}
                </tbody>
            </table>
        </div>
    );
}

function KeyValueBlockView({ block }: { block: KeyValueBlock }) {
    return (
        <div className="px-6 py-4">
            <table className="w-full max-w-md border-collapse text-sm">
                <tbody>
                    {block.rows.map(([label, value]) => (
                        <tr key={label} className="border-b border-slate-100 last:border-0">
                            <td className="py-2 pr-4 text-slate-500">{label}</td>
                            <td className="py-2 text-right font-medium text-slate-800">{value}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

function TextBlockView({ block }: { block: TextBlock }) {
    return (
        <div className="px-6 py-4 text-sm text-slate-700">{block.content}</div>
    );
}

function ManagementDetailBlockView({
    block,
    onOpenDetail,
}: {
    block: ManagementDetailBlock;
    onOpenDetail: (params: DetailParams) => void;
}) {
    return (
        <div className="overflow-x-auto">
            <table className="w-full min-w-[700px] border border-slate-300 border-collapse text-sm">
                <thead>
                    <tr>
                        {block.columns.map((col) => (
                            <th key={col} className={thCell}>{col}</th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {block.rows.length === 0 ? (
                        <tr><td className={tdCell} colSpan={block.columns.length}>No data.</td></tr>
                    ) : (
                        block.rows.map((row) => (
                            <tr key={row.no}>
                                <td className={tdCell}>{row.no}</td>
                                <td className={tdCell}>{row.name}</td>
                                <td className={tdCell}>{row.id_card}</td>
                                <td className={tdCell}>{row.address}</td>
                                <td className={tdCell}>
                                    {row.detail_params ? (
                                        <button
                                            type="button"
                                            onClick={() => onOpenDetail(row.detail_params!)}
                                            className="rounded-md border border-slate-300 bg-white px-3 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50"
                                        >
                                            Detail
                                        </button>
                                    ) : (
                                        <span className="text-slate-300">—</span>
                                    )}
                                </td>
                            </tr>
                        ))
                    )}
                </tbody>
            </table>
        </div>
    );
}

function DocumentsBlockView({ block, onPreview }: { block: DocumentsBlock; onPreview: (file: DocumentFile) => void }) {
    return (
        <div className="overflow-x-auto">
            <table className="w-full min-w-[500px] border border-slate-300 border-collapse text-sm">
                <thead>
                    <tr>
                        <th className={thCell} style={{ width: 60 }}>No.</th>
                        <th className={thCell}>File Name</th>
                        <th className={thCell} style={{ width: 140 }}>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {block.rows.length === 0 ? (
                        <tr><td className={tdCell} colSpan={3}>No files uploaded.</td></tr>
                    ) : (
                        block.rows.map((f, idx) => (
                            <tr key={f.id}>
                                <td className={tdCell}>{idx + 1}</td>
                                <td className={tdCell}>{f.name}</td>
                                <td className={tdCell}>
                                    <DocActionButton file={f} onPreview={onPreview} />
                                </td>
                            </tr>
                        ))
                    )}
                </tbody>
            </table>
        </div>
    );
}

export default function BusinessProfileView({ ctx }: { ctx: CamCtx }) {
    const [data, setData] = useState<BusinessProfile | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [preview, setPreview] = useState<PreviewState>(PREVIEW_CLOSED);
    const [detailParams, setDetailParams] = useState<DetailParams | null>(null);

    useEffect(() => {
        let active = true;
        setLoading(true);
        setError(null);
        api
            .get('/CAM/View/api/business-profile', { params: { apless: ctx.apless, applno: ctx.applno } })
            .then((res) => {
                if (active) setData(res.data);
            })
            .catch((err) => {
                if (active) setError(err?.response?.data?.error || 'Failed to load business profile.');
            })
            .finally(() => {
                if (active) setLoading(false);
            });
        return () => {
            active = false;
        };
    }, [ctx.apless, ctx.applno]);

    const handlePreview = (file: DocumentFile) => {
        if (!file.download_url) return;
        setPreview({ open: true, name: file.name, url: file.download_url });
    };

    if (loading) {
        return (
            <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500 shadow-sm">
                Loading business profile…
            </div>
        );
    }
    if (error || !data) {
        return (
            <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-sm text-red-500 shadow-sm">
                {error || 'No data found.'}
            </div>
        );
    }

    return (
        <div>
            <DocPreviewModal state={preview} onClose={() => setPreview(PREVIEW_CLOSED)} />
            {detailParams && (
                <ViewContractInformation
                    apless={ctx.apless}
                    period={data.period}
                    managementNm={detailParams.management_nm}
                    shareStatus={detailParams.share_status}
                    onClose={() => setDetailParams(null)}
                />
            )}

            <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                <SectionHeader>Organization Structure — {data.lessee_nm}</SectionHeader>

                {data.blocks.map((block, i) => (
                    <React.Fragment key={i}>
                        {block.title && <SectionHeader>{block.title}</SectionHeader>}
                        {block.type === 'table' && <TableBlockView block={block} />}
                        {block.type === 'key_value' && <KeyValueBlockView block={block} />}
                        {block.type === 'text' && <TextBlockView block={block} />}
                        {block.type === 'management_detail' && (
                            <ManagementDetailBlockView block={block} onOpenDetail={setDetailParams} />
                        )}
                        {block.type === 'documents' && (
                            <DocumentsBlockView block={block} onPreview={handlePreview} />
                        )}
                    </React.Fragment>
                ))}
            </div>
        </div>
    );
}