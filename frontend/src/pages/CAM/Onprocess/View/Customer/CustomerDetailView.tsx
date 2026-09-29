import React, { useEffect, useState } from 'react';
import api from '../../../../../api/axiosInstance';
import { isImageFile } from '../../../../../constants/DefaultValue';
import type { CamCtx } from '../CamViewTabs';

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
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

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

const cellLabel =
    "border-b border-slate-100 bg-slate-50/70 px-4 py-2.5 align-top text-[11px] font-medium uppercase tracking-wide text-slate-400 whitespace-nowrap";
const cellValue =
    "border-b border-slate-100 px-4 py-2.5 align-top text-sm text-slate-700";
const cellEmpty = "border-b border-slate-100 px-4 py-2.5";
const subheadCell =
    "border-b border-slate-100 bg-indigo-50/70 px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-indigo-600";

function addressNode(block: AddressBlock | null): React.ReactNode {
    if (!block) return '-';
    return (
        <>
            <div>{block.address_line}</div>
            <div className="text-slate-500">{block.contact_line}</div>
        </>
    );
}

function Row({
    left,
    right,
    rightHeader,
}: {
    left?: [string, React.ReactNode];
    right?: [string, React.ReactNode];
    rightHeader?: string;
}) {
    return (
        <tr>
            {left ? (
                <>
                    <td className={cellLabel}>{left[0]}</td>
                    <td className={cellValue}>{left[1] || '-'}</td>
                </>
            ) : (
                <>
                    <td className={cellEmpty}></td>
                    <td className={cellEmpty}></td>
                </>
            )}
            {rightHeader ? (
                <td colSpan={2} className={subheadCell}>{rightHeader}</td>
            ) : right ? (
                <>
                    <td className={cellLabel}>{right[0]}</td>
                    <td className={cellValue}>{right[1] || '-'}</td>
                </>
            ) : (
                <>
                    <td className={cellEmpty}></td>
                    <td className={cellEmpty}></td>
                </>
            )}
        </tr>
    );
}

function SectionHeader({ children }: { children: React.ReactNode }) {
    return (
        <div className="border-b border-t border-slate-200 bg-slate-50 px-6 py-3 first:border-t-0">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">{children}</h2>
        </div>
    );
}

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
            .get('/CAM/View/api/customer-detail', { params: { apless: ctx.apless, applno: ctx.applno } })
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
            <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500 shadow-sm">
                Loading customer detail…
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

            <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                <SectionHeader>Customer Detail Review</SectionHeader>

                <div className="overflow-x-auto">
                    <table className="w-full min-w-[820px] border-collapse text-sm">
                        <tbody>
                            <tr>
                                <td colSpan={2} className={cellValue}>
                                    <span className="mr-1 font-medium text-slate-400">Name in ID Card:</span>
                                    {data.lessee_nm || '-'}
                                </td>
                                <td colSpan={2} className={cellValue}>
                                    <span className="mr-1 font-medium text-slate-400">Alias Name:</span>
                                    {data.alias_nm || '-'}
                                </td>
                            </tr>
                            <tr>
                                <td colSpan={2} className={cellValue}>
                                    <span className="mr-1 font-medium text-slate-400">Customer Name Without Title:</span>
                                    {data.idcard_name || '-'}
                                </td>
                                <td className={cellLabel}>Type</td>
                                <td className={cellValue}>{data.cust_type || '-'}</td>
                            </tr>
                            <tr>
                                <td rowSpan={4} className={cellLabel}>Address in ID Card</td>
                                <td rowSpan={4} className={cellValue}>
                                    {data.id_card_address ? (
                                        <>
                                            <div>{data.id_card_address.address_line}</div>
                                            <div className="text-slate-500">{data.id_card_address.contact_line}</div>
                                            {data.years_lived !== null && (
                                                <div className="mt-2 text-xs text-slate-400">
                                                    Live here for {data.years_lived} year(s)
                                                </div>
                                            )}
                                        </>
                                    ) : '-'}
                                </td>
                                <td className={cellLabel}>Whatsapp No.</td>
                                <td className={cellValue}>{data.mobile}</td>
                            </tr>
                            <Row right={['Mobile', data.mobile]} />
                            <Row right={['Email', data.email]} />
                            <Row right={['NPWP', data.npwp_formatted]} />

                            <Row
                                left={['Correspondence', addressNode(data.correspondence)]}
                                right={['Address in NPWP', data.npwp_address]}
                            />
                            <tr>
                                <td rowSpan={3} className={cellLabel}>Additional 1</td>
                                <td rowSpan={3} className={cellValue}>{addressNode(data.additional1)}</td>
                                <td className={cellLabel}>Group</td>
                                <td className={cellValue}>{data.group_name || '-'}</td>
                            </tr>
                            <Row right={["Mother's Maiden Name", data.mother_maiden_name]} />
                            <Row right={['Place/Date of Birth', `${data.place_of_birth || '-'} / ${data.date_of_birth || '-'}`]} />

                            <tr>
                                <td rowSpan={3} className={cellLabel}>Additional 2</td>
                                <td rowSpan={3} className={cellValue}>{addressNode(data.additional2)}</td>
                                <td className={cellLabel}>Gender</td>
                                <td className={cellValue}>{data.gender || '-'}</td>
                            </tr>
                            <Row right={['Marital Status', data.marital_status]} />
                            <Row right={['Religion', data.religion]} />

                            <Row
                                left={['ID Card No.', data.id_card_no]}
                                right={['Citizenship', `${data.citizenship || '-'} / ${data.nationality || '-'}`]}
                            />
                            <Row left={['Validity ID Card', data.id_card_validity]} rightHeader="Spouse Information" />
                            <Row left={['Passport No.', data.passport_no]} right={['Spouse Name in ID Card', data.spouse.name_id_card]} />
                            <Row left={['Family Card No.', data.family_card_no]} right={['Spouse Name Without Title', data.spouse.name_without_title]} />
                            <Row left={['Other Phone 1', data.other_phone1]} right={['Spouse Mobile Phone No.', data.spouse.mobile_phone]} />
                            <Row left={['Other Phone Notes 1', data.other_phone1_notes]} right={['Spouse Email', data.spouse.email]} />
                            <Row
                                left={['Other Phone 2', data.other_phone2]}
                                right={['Place/Date of Birth', `${data.spouse.place_of_birth || '-'} / ${data.spouse.date_of_birth || '-'}`]}
                            />
                            <Row
                                left={['Other Phone Notes 2', data.other_phone2_notes]}
                                right={['Citizenship', `${data.spouse.citizenship || '-'} / ${data.spouse.nationality || '-'}`]}
                            />
                            <Row left={['Last Education', data.last_education]} right={['ID Card No.', data.spouse.id_card_no]} />
                            <Row left={['Career Field', data.career_field]} right={['Validity ID Card', data.spouse.id_card_validity]} />
                            <Row right={['Passport No.', data.spouse.passport_no]} />
                            <Row right={['Marriage Agreement', data.spouse.marriage_agreement]} />
                            <Row right={['Total of Dependent', data.spouse.total_dependent]} />
                            <Row right={['Relationship with Genie', data.spouse.relationship]} />
                            <Row right={['Industrial Code', data.industrial_code]} />
                            <Row right={['BI Customer Type', data.bi_customer_type]} />
                            <Row rightHeader="Emergency Contact" />
                            <Row right={['Emergency Name', data.emergency.name]} />
                            <Row right={['Emergency Address', data.emergency.address]} />
                            <Row right={['Emergency Phone', data.emergency.phone]} />
                            <Row right={['Emergency Relation', data.emergency.relation]} />
                        </tbody>
                    </table>
                </div>

                {data.references.length > 0 && (
                    <>
                        <SectionHeader>References</SectionHeader>
                        <div className="overflow-x-auto">
                            <table className="w-full min-w-[600px] border-collapse text-sm">
                                <thead>
                                    <tr>
                                        <th className="w-16 border-b border-slate-200 bg-slate-50/70 px-4 py-2 text-left text-[11px] font-medium uppercase tracking-wide text-slate-400">No.</th>
                                        <th className="border-b border-slate-200 bg-slate-50/70 px-4 py-2 text-left text-[11px] font-medium uppercase tracking-wide text-slate-400">Name</th>
                                        <th className="border-b border-slate-200 bg-slate-50/70 px-4 py-2 text-left text-[11px] font-medium uppercase tracking-wide text-slate-400">Telephone Number</th>
                                        <th className="border-b border-slate-200 bg-slate-50/70 px-4 py-2 text-left text-[11px] font-medium uppercase tracking-wide text-slate-400">Remark / Notes</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {data.references.map((r) => (
                                        <tr key={r.no}>
                                            <td className="border-b border-slate-100 px-4 py-2.5 text-slate-500">{r.no}</td>
                                            <td className="border-b border-slate-100 px-4 py-2.5 text-slate-700">{r.name || '-'}</td>
                                            <td className="border-b border-slate-100 px-4 py-2.5 text-slate-700">{r.phone || '-'}</td>
                                            <td className="border-b border-slate-100 px-4 py-2.5 text-slate-700">{r.remark || '-'}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </>
                )}

                {data.show_documents && (
                    <>
                        <SectionHeader>Documents</SectionHeader>
                        <div className="space-y-6 px-6 py-5">
                            {data.document_groups.map((group, gi) => (
                                <div key={gi}>
                                    {group.header && (
                                        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                                            {group.header}
                                        </h3>
                                    )}
                                    <div className="divide-y divide-slate-100 rounded-lg border border-slate-100">
                                        {group.rows.map((row) => (
                                            <div
                                                key={row.key}
                                                className="grid grid-cols-1 gap-2 px-4 py-2.5 sm:grid-cols-[220px_1fr]"
                                            >
                                                <div className="text-sm text-slate-500">{row.label}</div>
                                                <div>
                                                    {row.files.length === 0 ? (
                                                        <span className="text-sm text-slate-400">No file uploaded</span>
                                                    ) : (
                                                        <ul className="space-y-1.5">
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
                    </>
                )}
            </div>
        </div>
    );
}