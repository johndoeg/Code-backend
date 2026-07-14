import React, { useEffect, useState } from 'react';
import api from '../../../../api/axiosInstance';
import { isImageFile } from '../../../../constants/DefaultValue';
import type { CamCtx } from './CamViewTabs';

interface AddressBlock {
    address_line: string;
    contact_line: string;
}

interface EmergencyInfo {
    name: string;
    address: string;
    phone: string;
    relation: string;
}

interface SpouseInfo {
    name_id_card: string;
    name_without_title: string;
    mobile_phone: string;
    email: string;
    place_of_birth: string;
    date_of_birth: string;
    citizenship: string;
    nationality: string;
    id_card_no: string;
    id_card_validity: string;
    passport_no: string;
    marriage_agreement: string;
    total_dependent: string;
    relationship: string;
}

interface ReferenceRow {
    no: number;
    name: string;
    phone: string;
    remark: string;
}

interface DocumentFile {
    id: number;
    name: string;
    download_url: string | null;
}

interface DocumentRow {
    key: string;
    label: string;
    files: DocumentFile[];
}

interface DocumentGroup {
    header: string | null;
    rows: DocumentRow[];
}

interface CustomerDetail {
    lessee_nm: string;
    alias_nm: string;
    idcard_name: string;
    cust_type: string;
    id_card_address: AddressBlock | null;
    years_lived: number | null;
    mobile: string;
    email: string;
    npwp_formatted: string;
    correspondence: AddressBlock | null;
    npwp_address: string;
    additional1: AddressBlock | null;
    additional2: AddressBlock | null;
    group_name: string;
    mother_maiden_name: string;
    place_of_birth: string;
    date_of_birth: string;
    gender: string;
    marital_status: string;
    religion: string;
    id_card_no: string;
    id_card_validity: string;
    citizenship: string;
    nationality: string;
    passport_no: string;
    family_card_no: string;
    other_phone1: string;
    other_phone1_notes: string;
    other_phone2: string;
    other_phone2_notes: string;
    last_education: string;
    career_field: string;
    industrial_code: string;
    bi_customer_type: string;
    emergency: EmergencyInfo;
    spouse: SpouseInfo;
    references: ReferenceRow[];
    citizen: string;
    document_groups: DocumentGroup[];
    show_documents: boolean;
}

interface PreviewState {
    open: boolean;
    name: string;
    url: string;
}

const PREVIEW_CLOSED: PreviewState = {
    open: false,
    name: '',
    url: '',
};

const DocPreviewModal: React.FC<{
    state: PreviewState;
    onClose: () => void;
}> = ({ state, onClose }) => {
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
                        <img
                            src={state.url}
                            alt={state.name}
                            style={{ width: "100%", height: "100%", objectFit: "contain" }}
                            onError={() => setImgError(true)}
                        />
                    ) : isPdf ? (
                        <iframe title={state.name} src={state.url} width="100%" height="100%" />
                    ) : (
                        <div style={{ textAlign: "center", paddingTop: 40 }}>
                            <p style={{ marginBottom: 12, color: "#64748b" }}>
                                {imgError ? "Failed to load image." : "Preview not available for this file type."}
                            </p>
                            <a href={state.url} target="_blank" rel="noreferrer"
                                style={{ color: "#2563eb", textDecoration: "underline" }}>
                                Open / Download File
                            </a>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

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

function AddressField({ label, block }: { label: string; block: AddressBlock | null }) {
    return (
        <div className="border-b border-slate-100 py-2 last:border-0">
            <dt className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</dt>
            <dd className="mt-0.5 text-sm text-slate-700">
                {block ? (
                    <>
                        <div>{block.address_line}</div>
                        <div className="text-slate-500">{block.contact_line}</div>
                    </>
                ) : (
                    '-'
                )}
            </dd>
        </div>
    );
}

const DocChip: React.FC<{
    file: DocumentFile;
    onPreview: (file: DocumentFile) => void;
}> = ({ file, onPreview }) => {
    const [hovered, setHovered] = useState(false);

    if (!file.download_url) {
        return <span style={{ fontSize: 13, color: "#374151" }}>{file.name}</span>;
    }

    return (
        <div style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
            <button
                type="button"
                onClick={() => onPreview(file)}
                onMouseEnter={() => setHovered(true)}
                onMouseLeave={() => setHovered(false)}
                style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    border: `1px solid ${hovered ? "#ea580c" : "#f97316"}`,
                    background: hovered ? "#f97316" : "#fff7ed",
                    color: hovered ? "#fff" : "#c2410c",
                    borderRadius: 6,
                    padding: "5px 12px",
                    fontSize: 13,
                    fontWeight: 500,
                    cursor: "pointer",
                    transition: "background 0.15s, color 0.15s, border-color 0.15s",
                }}
            >
                <svg
                    width="15" height="15"
                    viewBox="0 0 24 24" fill="none"
                    stroke="currentColor" strokeWidth="2"
                    strokeLinecap="round" strokeLinejoin="round"
                    aria-hidden="true"
                >
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                    <circle cx="12" cy="12" r="3" />
                </svg>
                View
            </button>
            <span style={{ fontSize: 13, color: "#374151" }}>{file.name}</span>
        </div>
    );
};

export default function CustomerDetailView({ ctx }: { ctx: CamCtx }) {
    const [data, setData] = useState<CustomerDetail | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [preview, setPreview] = useState<PreviewState>(PREVIEW_CLOSED);

    useEffect(() => {
        let active = true;
        setLoading(true);
        setError(null);
        api
            .get('/CAM/api/view/customer-detail', { params: { apless: ctx.apless, applno: ctx.applno } })
            .then((res) => {
                if (active) setData(res.data);
            })
            .catch(() => {
                if (active) setError('Failed to load customer detail.');
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
            <div className="rounded-2xl bg-white p-8 text-center text-sm text-slate-500 shadow">
                Loading customer detail…
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

    return (
        <div>
            <DocPreviewModal state={preview} onClose={() => setPreview(PREVIEW_CLOSED)} />

            <Card title="Customer Detail Review">
                <dl className="grid grid-cols-1 gap-x-8 sm:grid-cols-2">
                    <Field label="Name in ID Card" value={data.lessee_nm} />
                    <Field label="Alias Name" value={data.alias_nm} />
                    <Field label="Customer Name Without Title" value={data.idcard_name} />
                    <Field label="Type" value={data.cust_type} />
                </dl>
            </Card>

            <Card title="Address & Contact">
                <dl className="grid grid-cols-1 gap-x-8 sm:grid-cols-2">
                    <div>
                        <AddressField label="Address in ID Card" block={data.id_card_address} />
                        {data.years_lived !== null && (
                            <p className="mt-1 text-xs text-slate-400">Live here for {data.years_lived} year(s)</p>
                        )}
                    </div>
                    <Field label="Mobile" value={data.mobile} />
                    <Field label="Email" value={data.email} />
                    <Field label="NPWP" value={data.npwp_formatted} />
                    <AddressField label="Correspondence" block={data.correspondence} />
                    <Field label="Address in NPWP" value={data.npwp_address} />
                    <AddressField label="Additional 1" block={data.additional1} />
                    <AddressField label="Additional 2" block={data.additional2} />
                </dl>
            </Card>

            <Card title="Personal Information">
                <dl className="grid grid-cols-1 gap-x-8 sm:grid-cols-2">
                    <Field label="Group" value={data.group_name} />
                    <Field label="Mother's Maiden Name" value={data.mother_maiden_name} />
                    <Field label="Place / Date of Birth" value={`${data.place_of_birth} / ${data.date_of_birth}`} />
                    <Field label="Gender" value={data.gender} />
                    <Field label="Marital Status" value={data.marital_status} />
                    <Field label="Religion" value={data.religion} />
                    <Field label="ID Card No." value={data.id_card_no} />
                    <Field label="Validity ID Card" value={data.id_card_validity} />
                    <Field label="Citizenship" value={`${data.citizenship} / ${data.nationality}`} />
                    <Field label="Passport No." value={data.passport_no} />
                    <Field label="Family Card No." value={data.family_card_no} />
                    <Field label="Other Phone 1" value={data.other_phone1} />
                    <Field label="Other Phone Notes 1" value={data.other_phone1_notes} />
                    <Field label="Other Phone 2" value={data.other_phone2} />
                    <Field label="Other Phone Notes 2" value={data.other_phone2_notes} />
                    <Field label="Last Education" value={data.last_education} />
                    <Field label="Career Field" value={data.career_field} />
                    <Field label="Industrial Code" value={data.industrial_code} />
                    <Field label="BI Customer Type" value={data.bi_customer_type} />
                </dl>
            </Card>

            <Card title="Spouse Information">
                <dl className="grid grid-cols-1 gap-x-8 sm:grid-cols-2">
                    <Field label="Spouse Name in ID Card" value={data.spouse.name_id_card} />
                    <Field label="Spouse Name Without Title" value={data.spouse.name_without_title} />
                    <Field label="Spouse Mobile Phone No." value={data.spouse.mobile_phone} />
                    <Field label="Spouse Email" value={data.spouse.email} />
                    <Field
                        label="Place / Date of Birth"
                        value={`${data.spouse.place_of_birth || '-'} / ${data.spouse.date_of_birth || '-'}`}
                    />
                    <Field
                        label="Citizenship"
                        value={`${data.spouse.citizenship || '-'} / ${data.spouse.nationality || '-'}`}
                    />
                    <Field label="ID Card No." value={data.spouse.id_card_no} />
                    <Field label="Validity ID Card" value={data.spouse.id_card_validity} />
                    <Field label="Passport No." value={data.spouse.passport_no} />
                    <Field label="Marriage Agreement" value={data.spouse.marriage_agreement} />
                    <Field label="Total of Dependent" value={data.spouse.total_dependent} />
                    <Field label="Relationship with Genie" value={data.spouse.relationship} />
                </dl>
            </Card>

            <Card title="Emergency Contact">
                <dl className="grid grid-cols-1 gap-x-8 sm:grid-cols-2">
                    <Field label="Emergency Name" value={data.emergency.name} />
                    <Field label="Emergency Address" value={data.emergency.address} />
                    <Field label="Emergency Phone" value={data.emergency.phone} />
                    <Field label="Emergency Relation" value={data.emergency.relation} />
                </dl>
            </Card>

            {data.references.length > 0 && (
                <Card title="References">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-400">
                                <th className="py-2 pr-4">No.</th>
                                <th className="py-2 pr-4">Name</th>
                                <th className="py-2 pr-4">Telephone Number</th>
                                <th className="py-2">Remark / Notes</th>
                            </tr>
                        </thead>
                        <tbody>
                            {data.references.map((r) => (
                                <tr key={r.no} className="border-b border-slate-100 last:border-0">
                                    <td className="py-2 pr-4 text-slate-500">{r.no}</td>
                                    <td className="py-2 pr-4 text-slate-700">{r.name}</td>
                                    <td className="py-2 pr-4 text-slate-700">{r.phone}</td>
                                    <td className="py-2 text-slate-700">{r.remark}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </Card>
            )}

            {data.show_documents && (
                <Card title="Documents">
                    <div className="space-y-5">
                        {data.document_groups.map((group, gi) => (
                            <div key={gi}>
                                {group.header && <h3 className="mb-2 text-sm font-semibold text-slate-600">{group.header}</h3>}
                                <div className="space-y-3">
                                    {group.rows.map((row) => (
                                        <div key={row.key} className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_2fr]">
                                            <div className="text-sm text-slate-600">{row.label}</div>
                                            <div>
                                                {row.files.length === 0 ? (
                                                    <span className="text-sm text-slate-400">No file uploaded</span>
                                                ) : (
                                                    <ul className="space-y-1">
                                                        {row.files.map((f) => (
                                                            <li key={f.id}>
                                                                <DocChip file={f} onPreview={handlePreview} />
                                                            </li>
                                                        ))}
                                                    </ul>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                </Card>
            )}
        </div>
    );
}