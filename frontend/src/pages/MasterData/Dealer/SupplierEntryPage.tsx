import React, { useEffect, useState, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import api from "../../../api/axiosInstance";
import { isImageFile } from "../../../constants/DefaultValue";

type Mode = "AddCF" | "Edit" | "View";
type Tab = "main" | "tax" | "bank" | "add" | "dev" | "doc" | "notes";

interface Opt { value: string; label: string; province?: string; }

interface FormOptions {
    dealer_types: Opt[];
    car_conditions: Opt[];
    branches: Opt[];
    showroom_cats: Opt[];
    npwp_details: Opt[];
    provinces: Opt[];
    cities: Opt[];
    tax_types: Opt[];
    banks: Opt[];
    beneficiary_types: Opt[];
    resident_statuses: Opt[];
    areas: Opt[];
    cmos: Opt[];
    brands: Opt[];
}

interface BankAccount {
    acc_no: string;
    acc_name: string;
    acc_bank: string;
    acc_bank_desc: string;
    acc_bank_branch: string;
    beneficiary_type: string;
    beneficiary_type_desc: string;
    resident_status: string;
    resident_status_desc: string;
    acc_type: string;
    is_default: boolean;
    last_update: string;
}

interface BankForm {
    acc_type: string;
    acc_name: string;
    acc_no: string;
    bank: string;
    bank_brch: string;
    beneficiary_type: string;
    resident_status: string;
    is_default: boolean;
}

interface AdditionalForm { bd_area: string; cmo: string; brand: string; }

interface DeviationItem { dev_cd: string; description: string; is_check: string; }
interface DeviationNotes {
    note1: string; note2: string; note3: string;
    note4: string; note5: string; janji: string;
}

interface DealerFile {
    id: number;
    aws_key: string;
    file_nm: string;
    file_ext: string;
    doc_type: string;
    ket: string;
    created_date: string;
    download_url: string;
}

interface DealerDocConfig { key: string; label: string; hasLainnya?: boolean; }

const DEALER_DOCS: DealerDocConfig[] = [
    { key: "dealer-ktp", label: "KTP Contact Person" },
    { key: "dealer-siup", label: "SIUP / NIB" },
    { key: "dealer-npwp", label: "NPWP" },
    { key: "dealer-akta", label: "Akta Pendirian" },
    { key: "dealer-bpkb", label: "Contoh BPKB" },
    { key: "dealer-bank", label: "Buku Tabungan / Rekening Koran" },
    { key: "dealer-other", label: "Lainnya", hasLainnya: true },
];

interface MainForm {
    supp: string;
    status: string;
    supp_type: string;
    car_condition: string;
    name: string;
    nickname: string;
    address: string;
    city: string;
    zipcode: string;
    phone: string;
    fax: string;
    contact: string;
    idcard: string;
    exp_date: string;
    certain_per: string;
    position: string;
    addr_con: string;
    city_con: string;
    zipcode1: string;
    phone_con: string;
    email_addr: string;
    adm_name: string;
    bpkbstaf: string;
    branch_mgr: string;
    remark: string;
    branch_cd: string;
    showroom_cat: string;
    create_by: string;
    create_date: string;
    update_by: string;
    ca_lastupd: string;
}

interface TaxForm {
    npwp_no: string;
    npwp_detail: string;
    npwp_nm: string;
    npwp_addr: string;
    province: string;
    city: string;
    ppnsts: string;
    ppnstartdate: string;
    taxfree: string;
    taxfree2: string;
    pph: string;
    rate: string;
    dpp: string;
    kores_address: string;
    update_by: string;
    lastupdate: string;
    is_saved: boolean;
}

const defMain: MainForm = {
    supp: "", status: "1", supp_type: "", car_condition: "",
    name: "", nickname: "", address: "", city: "", zipcode: "",
    phone: "", fax: "", contact: "", idcard: "", exp_date: "0", certain_per: "",
    position: "", addr_con: "", city_con: "", zipcode1: "", phone_con: "",
    email_addr: "", adm_name: "", bpkbstaf: "", branch_mgr: "",
    remark: "", branch_cd: "", showroom_cat: "0",
    create_by: "", create_date: "", update_by: "", ca_lastupd: "",
};

const defTax: TaxForm = {
    npwp_no: "", npwp_detail: "", npwp_nm: "", npwp_addr: "",
    province: "", city: "", ppnsts: "", ppnstartdate: "",
    taxfree: "", taxfree2: "", pph: "2", rate: "2", dpp: "100",
    kores_address: "", update_by: "", lastupdate: "", is_saved: false,
};

const defBankForm: BankForm = {
    acc_type: "", acc_name: "", acc_no: "", bank: "",
    bank_brch: "", beneficiary_type: "", resident_status: "", is_default: false,
};

const defAdditional: AdditionalForm = { bd_area: "", cmo: "", brand: "" };

const defDevNotes: DeviationNotes = {
    note1: "", note2: "", note3: "", note4: "", note5: "", janji: "",
};

const inp =
    "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm " +
    "focus:ring-2 focus:ring-blue-500 focus:border-blue-500 " +
    "disabled:bg-gray-100 disabled:cursor-not-allowed transition-colors";

const sel = inp;

const btnPrimary =
    "px-4 py-2 text-sm rounded-lg font-medium transition-colors " +
    "bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white shadow-sm disabled:opacity-60";

const btnSecondary =
    "px-4 py-2 text-sm rounded-lg font-medium transition-colors " +
    "border border-gray-300 bg-white hover:bg-gray-50 text-gray-700";

function Field({ label, children, required }: {
    label: string; children: React.ReactNode; required?: boolean;
}) {
    return (
        <div className="flex flex-col gap-1">
            <label className="block text-sm font-medium text-gray-700">
                {label}{required && <span className="text-red-500 ml-0.5">*</span>}
            </label>
            {children}
        </div>
    );
}

function StatusBanner({ msg }: { msg?: { type: "success" | "error"; text: string } }) {
    if (!msg) return null;
    return (
        <div className={`mt-4 p-3 rounded-lg text-sm border flex items-start gap-2 ${msg.type === "success"
            ? "bg-green-50 border-green-200 text-green-700"
            : "bg-red-50   border-red-200   text-red-700"
            }`}>
            <svg className="w-4 h-4 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24"
                stroke="currentColor">
                {msg.type === "success"
                    ? <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M5 13l4 4L19 7" />
                    : <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />}
            </svg>
            <span>{msg.text}</span>
        </div>
    );
}

interface FilePreviewState {
    open: boolean;
    name: string;
    url: string;
}

const FILE_PREVIEW_CLOSED: FilePreviewState = { open: false, name: "", url: "" };

function FilePreviewModal({ state, onClose }: { state: FilePreviewState; onClose: () => void }) {
    const [imgError, setImgError] = useState(false);

    useEffect(() => { setImgError(false); }, [state.url]);

    if (!state.open) return null;

    const cleanName = state.name.split("?")[0];
    const isImage = isImageFile(cleanName);
    const isPdf = cleanName.split(".").pop()?.toLowerCase() === "pdf";

    return (
        <div
            onClick={onClose}
            className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 p-4"
        >
            <div
                onClick={e => e.stopPropagation()}
                className="flex h-[88vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl"
            >
                <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
                    <span className="truncate text-sm font-semibold text-gray-800">{state.name}</span>
                    <div className="flex flex-shrink-0 items-center gap-3">
                        <a href={state.url} target="_blank" rel="noreferrer" title="Open in new tab"
                            className="text-gray-400 transition-colors hover:text-blue-600">
                            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                    d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                            </svg>
                        </a>
                        <button onClick={onClose} className="text-lg leading-none text-gray-400 hover:text-gray-600">
                            ✕
                        </button>
                    </div>
                </div>

                <div className="flex-1 overflow-hidden p-5">
                    {isImage && !imgError ? (
                        <img
                            src={state.url}
                            alt={state.name}
                            className="h-full w-full object-contain"
                            onError={() => setImgError(true)}
                        />
                    ) : isPdf ? (
                        <iframe title={state.name} src={state.url} className="h-full w-full border-0" />
                    ) : (
                        <div className="flex h-full flex-col items-center justify-center text-center">
                            <p className="mb-3 text-sm text-gray-500">
                                {imgError ? "Failed to load image." : "Preview not available for this file type."}
                            </p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

function ReadOnlyField({ label, value }: { label: string; value: string }) {
    if (!value) return null;
    return (
        <div className="flex flex-col gap-1">
            <label className="block text-xs font-medium text-gray-500">{label}</label>
            <p className="text-sm text-gray-800 bg-gray-50 border border-gray-200
                    rounded-lg px-3 py-2 min-h-[36px]">
                {value || "—"}
            </p>
        </div>
    );
}

function StubTab({ title, desc }: { title: string; desc: string }) {
    return (
        <div className="py-16 text-center text-gray-400">
            <svg className="w-12 h-12 mx-auto mb-3 text-gray-300" fill="none"
                stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2
             h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0
             01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <p className="font-semibold text-gray-500">{title}</p>
            <p className="text-sm mt-1">{desc}</p>
        </div>
    );
}

const SupplierEntryPage: React.FC = () => {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();

    const mode0 = (searchParams.get("id") || "View") as Mode;
    const supp0 = searchParams.get("supp") || "";
    const akses0 = searchParams.get("akses") || "0";

    const [mode, setMode] = useState<Mode>(mode0);
    const [currentSup, setCurrentSup] = useState(supp0);
    const [activeTab, setActiveTab] = useState<Tab>("main");
    const [options, setOptions] = useState<FormOptions | null>(null);
    const [loading, setLoading] = useState(false);

    const [main, setMain] = useState<MainForm>({ ...defMain });
    const [tax, setTax] = useState<TaxForm>(defTax);

    const [disbAccounts, setDisbAccounts] = useState<BankAccount[]>([]);
    const [commAccounts, setCommAccounts] = useState<BankAccount[]>([]);
    const [bankForm, setBankForm] = useState<BankForm>(defBankForm);
    const [bankEdit, setBankEdit] = useState<{ acc_no: string; acc_type: string } | null>(null);

    const [additional, setAdditional] = useState<AdditionalForm>(defAdditional);

    const [deviItems, setDeviItems] = useState<DeviationItem[]>([]);
    const [devNotes, setDevNotes] = useState<DeviationNotes>(defDevNotes);

    const [docFiles, setDocFiles] = useState<Record<string, DealerFile[]>>({});
    const [docLainnya, setDocLainnya] = useState("");
    const [uploading, setUploading] = useState<string | null>(null);
    const [filePreview, setFilePreview] = useState<FilePreviewState>(FILE_PREVIEW_CLOSED);

    const [notes, setNotes] = useState("");
    const [savingNotes, setSavingNotes] = useState(false);

    const [saving, setSaving] = useState<Partial<Record<Tab, boolean>>>({});
    const [msgs, setMsgs] = useState<
        Partial<Record<Tab, { type: "success" | "error"; text: string }>>
    >({});

    const canEdit = mode !== "View" && (mode === "AddCF" || akses0 === "9");
    const mainSaved = currentSup !== "";
    const showCarCondition = !["AC", "KR"].includes(main.supp_type);
    const taxLocked = tax.is_saved && tax.pph !== "";

    const citiesForProvince = (options?.cities ?? []).filter(
        c => !tax.province || c.province === tax.province
    );

    const tabs: { id: Tab; label: string; disabled: boolean }[] = [
        { id: "main", label: "Main", disabled: false },
        { id: "tax", label: "Tax", disabled: !mainSaved },
        { id: "bank", label: "Bank Account", disabled: !mainSaved },
        { id: "add", label: "Additional", disabled: !mainSaved },
        { id: "dev", label: "Deviation", disabled: !mainSaved },
        { id: "doc", label: "Document Dealer", disabled: !mainSaved },
        { id: "notes", label: "Additional Notes", disabled: !mainSaved },
    ];

    useEffect(() => {
        api.get("/MasterData/api/dealer/options")
            .then(r => setOptions(r.data))
            .catch(() => setMsg("main", {
                type: "error", text: "Failed to load form options.",
            }));
    }, []);

    useEffect(() => {
        if ((mode === "Edit" || mode === "View") && supp0) {
            setLoading(true);
            api.get(`/MasterData/api/dealer/${supp0}`)
                .then(r => setMain({ ...defMain, ...r.data }))
                .catch(() => setMsg("main", {
                    type: "error", text: "Failed to load dealer data.",
                }))
                .finally(() => setLoading(false));
        }
    }, [mode, supp0]);

    useEffect(() => {
        if (activeTab === "tax" && currentSup) {
            api.get(`/MasterData/api/dealer/${currentSup}/tax`)
                .then(r => setTax(t => ({ ...t, ...r.data })))
                .catch(() => setMsg("tax", {
                    type: "error", text: "Failed to load tax data.",
                }));
        }
    }, [activeTab, currentSup]);

    const loadBankAccounts = useCallback(async () => {
        if (!currentSup) return;
        try {
            const r = await api.get(`/MasterData/api/dealer/${currentSup}/bank-accounts`);
            setDisbAccounts(r.data.disbursement || []);
            setCommAccounts(r.data.commission || []);
        } catch {
            setMsg("bank", { type: "error", text: "Failed to load bank accounts." });
        }
    }, [currentSup]);

    const loadAdditional = useCallback(async () => {
        if (!currentSup) return;
        try {
            const r = await api.get(`/MasterData/api/dealer/${currentSup}/additional`);
            setAdditional(r.data);
        } catch {
            setMsg("add", { type: "error", text: "Failed to load additional info." });
        }
    }, [currentSup]);

    const loadDeviation = useCallback(async () => {
        if (!currentSup) return;
        try {
            const r = await api.get(`/MasterData/api/dealer/${currentSup}/deviation`);
            setDeviItems(r.data.items || []);
            setDevNotes({ ...defDevNotes, ...(r.data.notes || {}) });
        } catch {
            setMsg("dev", { type: "error", text: "Failed to load deviation data." });
        }
    }, [currentSup]);

    const loadDocFiles = useCallback(async () => {
        if (!currentSup) return;
        try {
            const r = await api.get(`/MasterData/api/dealer/${currentSup}/files`);
            setDocFiles(r.data.files || {});
            setDocLainnya(r.data.lainnya || "");
        } catch {
            setMsg("doc", { type: "error", text: "Failed to load documents." });
        }
    }, [currentSup]);

    const loadNotes = useCallback(async () => {
        if (!currentSup) return;
        try {
            const r = await api.get(`/MasterData/api/dealer/${currentSup}/notes`);
            setNotes(r.data.notes || "");
        } catch {
            setMsg("notes", { type: "error", text: "Failed to load notes." });
        }
    }, [currentSup]);

    useEffect(() => {
        if (activeTab === "bank" && currentSup) loadBankAccounts();
        if (activeTab === "add" && currentSup) loadAdditional();
        if (activeTab === "dev" && currentSup) loadDeviation();
        if (activeTab === "doc" && currentSup) loadDocFiles();
        if (activeTab === "notes" && currentSup) loadNotes();
    }, [activeTab, currentSup,
        loadBankAccounts, loadAdditional, loadDeviation, loadDocFiles, loadNotes]);

    const setMsg = (
        tab: Tab,
        msg: { type: "success" | "error"; text: string } | undefined,
    ) => setMsgs(m => ({ ...m, [tab]: msg }));

    const onMain = (field: keyof MainForm, val: string) =>
        setMain(f => {
            const next = { ...f, [field]: val };
            if (field === "supp_type" && ["AC", "KR"].includes(val)) {
                next.car_condition = "";
            }
            return next;
        });

    const handleSaveMain = async () => {
        if (!main.supp_type || !main.name || !main.nickname) {
            setMsg("main", {
                type: "error",
                text: "Dealer Type, Name, and Nick Name are required.",
            });
            return;
        }
        setSaving(s => ({ ...s, main: true }));
        setMsg("main", undefined);
        try {
            if (mode === "AddCF") {
                const r = await api.post("/MasterData/api/dealer", main);
                if (r.data.success) {
                    const newSupp = r.data.supp;
                    setCurrentSup(newSupp);
                    setMain(f => ({ ...f, supp: newSupp }));
                    setMode("Edit");
                    setMsg("main", {
                        type: "success",
                        text: `Dealer created successfully. Dealer ID: ${newSupp}`,
                    });
                    navigate(
                        `/dealer-entry?id=Edit&supp=${newSupp}&akses=${akses0}`,
                        { replace: true },
                    );
                } else {
                    setMsg("main", {
                        type: "error",
                        text: r.data.message || "Save failed.",
                    });
                }
            } else {
                const r = await api.put(
                    `/MasterData/api/dealer/${currentSup}`, main,
                );
                setMsg("main", r.data.success
                    ? { type: "success", text: "Dealer updated successfully." }
                    : { type: "error", text: r.data.message || "Update failed." });
            }
        } catch {
            setMsg("main", { type: "error", text: "An error occurred." });
        } finally {
            setSaving(s => ({ ...s, main: false }));
        }
    };

    const handleSaveTax = async () => {
        setSaving(s => ({ ...s, tax: true }));
        setMsg("tax", undefined);
        try {
            const r = await api.post(
                `/MasterData/api/dealer/${currentSup}/tax`, tax,
            );
            if (r.data.success) {
                const rg = await api.get(
                    `/MasterData/api/dealer/${currentSup}/tax`,
                );
                setTax(t => ({ ...t, ...rg.data }));
                setMsg("tax", { type: "success", text: "Tax information saved." });
            } else {
                setMsg("tax", {
                    type: "error",
                    text: r.data.message || "Save failed.",
                });
            }
        } catch {
            setMsg("tax", { type: "error", text: "An error occurred." });
        } finally {
            setSaving(s => ({ ...s, tax: false }));
        }
    };

    const onPpnSts = (val: string) => {
        if (val === "1") {
            const now = new Date();
            const date = `${String(now.getDate()).padStart(2, "0")}-` +
                `${String(now.getMonth() + 1).padStart(2, "0")}-` +
                `${now.getFullYear()}`;
            setTax(t => ({ ...t, ppnsts: val, ppnstartdate: date }));
        } else {
            setTax(t => ({ ...t, ppnsts: val, ppnstartdate: "" }));
        }
    };

    const onTaxProvince = (val: string) =>
        setTax(t => ({ ...t, province: val, city: "" }));

    const handleBankSave = async () => {
        const required: (keyof BankForm)[] = [
            "acc_type", "acc_name", "bank", "bank_brch", "beneficiary_type", "resident_status",
        ];
        for (const f of required) {
            if (!bankForm[f]) {
                setMsg("bank", { type: "error", text: `${f.replace(/_/g, " ")} is required.` });
                return;
            }
        }
        setSaving(s => ({ ...s, bank: true }));
        setMsg("bank", undefined);
        try {
            if (bankEdit) {
                await api.put(
                    `/MasterData/api/dealer/${currentSup}/bank-accounts/${bankEdit.acc_type}/${bankEdit.acc_no}`,
                    bankForm,
                );
            } else {
                await api.post(`/MasterData/api/dealer/${currentSup}/bank-accounts`, bankForm);
            }
            setBankForm(defBankForm);
            setBankEdit(null);
            await loadBankAccounts();
            setMsg("bank", {
                type: "success",
                text: bankEdit ? "Account updated." : "Account added.",
            });
        } catch {
            setMsg("bank", { type: "error", text: "Operation failed." });
        } finally {
            setSaving(s => ({ ...s, bank: false }));
        }
    };

    const handleBankEdit = (row: BankAccount) => {
        setBankEdit({ acc_no: row.acc_no, acc_type: row.acc_type });
        setBankForm({
            acc_type: row.acc_type,
            acc_name: row.acc_name,
            acc_no: row.acc_no,
            bank: row.acc_bank,
            bank_brch: row.acc_bank_branch,
            beneficiary_type: row.beneficiary_type,
            resident_status: row.resident_status,
            is_default: row.is_default,
        });
        setMsg("bank", undefined);
    };

    const handleBankDelete = async (row: BankAccount) => {
        if (!window.confirm(`Delete account ${row.acc_no} (${row.acc_name})?`)) return;
        try {
            await api.delete(
                `/MasterData/api/dealer/${currentSup}/bank-accounts/${row.acc_type}/${row.acc_no}`,
            );
            await loadBankAccounts();
            setMsg("bank", { type: "success", text: "Account deleted." });
        } catch {
            setMsg("bank", { type: "error", text: "Delete failed." });
        }
    };

    const handleSaveAdditional = async () => {
        setSaving(s => ({ ...s, add: true }));
        setMsg("add", undefined);
        try {
            const r = await api.post(
                `/MasterData/api/dealer/${currentSup}/additional`, additional,
            );
            setMsg("add", r.data.success
                ? { type: "success", text: "Additional info saved." }
                : { type: "error", text: r.data.message || "Save failed." });
        } catch {
            setMsg("add", { type: "error", text: "An error occurred." });
        } finally {
            setSaving(s => ({ ...s, add: false }));
        }
    };

    const handleToggleDevi = async (dev_cd: string, checked: boolean) => {
        setDeviItems(items =>
            items.map(i => i.dev_cd === dev_cd ? { ...i, is_check: checked ? "1" : "0" } : i)
        );
        try {
            await api.put(
                `/MasterData/api/dealer/${currentSup}/deviation/${dev_cd}`,
                { is_check: checked },
            );
        } catch {
            setDeviItems(items =>
                items.map(i => i.dev_cd === dev_cd ? { ...i, is_check: checked ? "0" : "1" } : i)
            );
        }
    };

    const handleSaveDevNotes = async () => {
        setSaving(s => ({ ...s, dev: true }));
        setMsg("dev", undefined);
        try {
            const r = await api.post(
                `/MasterData/api/dealer/${currentSup}/deviation/notes`, devNotes,
            );
            setMsg("dev", r.data.success
                ? { type: "success", text: "Notes saved." }
                : { type: "error", text: r.data.message || "Save failed." });
        } catch {
            setMsg("dev", { type: "error", text: "An error occurred." });
        } finally {
            setSaving(s => ({ ...s, dev: false }));
        }
    };

    const handleFileUpload = async (docType: string, fileList: FileList) => {
        if (!fileList.length) return;
        setUploading(docType);
        setMsg("doc", undefined);
        const fd = new FormData();
        Array.from(fileList).forEach(f => fd.append("file", f));
        if (docType === "dealer-other" && docLainnya)
            fd.append("lainnya", docLainnya);
        try {
            const r = await api.post(
                `/MasterData/api/dealer/${currentSup}/files/${docType}`,
                fd,
                { headers: { "Content-Type": "multipart/form-data" } },
            );
            if (r.data.success) {
                await loadDocFiles();
                setMsg("doc", {
                    type: "success",
                    text: `${r.data.uploaded?.length ?? 1} file(s) uploaded.`,
                });
            } else {
                setMsg("doc", { type: "error", text: r.data.message || "Upload failed." });
            }
        } catch {
            setMsg("doc", { type: "error", text: "Upload failed. Please try again." });
        } finally {
            setUploading(null);
        }
    };

    const handleFileDelete = async (fileId: number) => {
        if (!window.confirm("Delete this file?")) return;
        try {
            await api.delete(`/MasterData/api/dealer/${currentSup}/files/${fileId}`);
            await loadDocFiles();
            setMsg("doc", { type: "success", text: "File deleted." });
        } catch {
            setMsg("doc", { type: "error", text: "Delete failed." });
        }
    };

    const handleFilePreview = async (f: DealerFile) => {
        try {
            const r = await api.get(f.download_url);
            setFilePreview({
                open: true,
                name: r.data.file_name || `${f.file_nm}${f.file_ext ? `.${f.file_ext}` : ""}`,
                url: r.data.url,
            });
        } catch {
            setMsg("doc", { type: "error", text: "Failed to get preview link." });
        }
    };

    const handleSaveNotes = async () => {
        setSavingNotes(true);
        setMsg("notes", undefined);
        try {
            const r = await api.post(
                `/MasterData/api/dealer/${currentSup}/notes`, { notes },
            );
            setMsg("notes", r.data.success
                ? { type: "success", text: "Notes saved successfully." }
                : { type: "error", text: r.data.message || "Save failed." });
        } catch {
            setMsg("notes", { type: "error", text: "An error occurred." });
        } finally {
            setSavingNotes(false);
        }
    };

    if (!options || loading) {
        return (
            <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100
                      flex items-center justify-center">
                <div className="flex items-center gap-3 text-gray-500">
                    <svg className="animate-spin w-5 h-5 text-blue-500" fill="none"
                        viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10"
                            stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor"
                            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Loading…
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
            <FilePreviewModal state={filePreview} onClose={() => setFilePreview(FILE_PREVIEW_CLOSED)} />
            <div className="mx-auto max-w-6xl">

                <div className="mb-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                    <div>
                        <h1 className="text-xl font-bold text-gray-800">
                            {mode === "AddCF"
                                ? "Add New Dealer"
                                : `Dealer — ${currentSup}`}
                        </h1>
                        <p className="text-sm text-gray-500 mt-0.5">
                            {mode === "AddCF"
                                ? "Create a new dealer record"
                                : mode === "View"
                                    ? "View only — no changes will be saved"
                                    : canEdit
                                        ? "Edit mode"
                                        : "Read-only (insufficient permissions)"}
                        </p>
                    </div>
                    <button
                        onClick={() => navigate("/supplier")}
                        className={btnSecondary}
                    >
                        ← Back to List
                    </button>
                </div>

                <div className="rounded-2xl bg-white shadow-lg overflow-hidden">

                    <div className="flex border-b border-gray-200 bg-gray-50 overflow-x-auto">
                        {tabs.map(t => (
                            <button
                                key={t.id}
                                disabled={t.disabled}
                                onClick={() => !t.disabled && setActiveTab(t.id)}
                                className={[
                                    "px-4 py-3 text-sm font-medium whitespace-nowrap transition-colors",
                                    activeTab === t.id
                                        ? "border-b-2 border-blue-600 text-blue-700 bg-white"
                                        : t.disabled
                                            ? "text-gray-300 cursor-not-allowed"
                                            : "text-gray-500 hover:text-gray-700 hover:bg-white",
                                ].join(" ")}
                            >
                                {t.label}
                            </button>
                        ))}
                    </div>

                    <div className="p-6">

                        {activeTab === "main" && (
                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-x-10 gap-y-0">

                                <div className="space-y-4">
                                    <p className="text-xs font-semibold text-gray-400 uppercase
                                tracking-widest pb-2 border-b border-gray-100">
                                        Dealer Information
                                    </p>

                                    <Field label="Dealer ID">
                                        <input className={inp} readOnly
                                            value={main.supp || "(auto-generated on save)"}
                                            style={{ fontFamily: "monospace", letterSpacing: "0.05em" }} />
                                    </Field>

                                    <Field label="Status" required>
                                        <select className={sel} disabled={!canEdit}
                                            value={main.status}
                                            onChange={e => onMain("status", e.target.value)}>
                                            <option value="">Select…</option>
                                            <option value="0">Inactive</option>
                                            <option value="1">Active</option>
                                        </select>
                                    </Field>

                                    <Field label="Dealer Type" required>
                                        <select className={sel} disabled={!canEdit}
                                            value={main.supp_type}
                                            onChange={e => onMain("supp_type", e.target.value)}>
                                            <option value="">Select…</option>
                                            {options.dealer_types.map(o => (
                                                <option key={o.value} value={o.value}>{o.label}</option>
                                            ))}
                                        </select>
                                    </Field>

                                    {showCarCondition && (
                                        <Field label="Car Condition">
                                            <select className={sel} disabled={!canEdit}
                                                value={main.car_condition}
                                                onChange={e => onMain("car_condition", e.target.value)}>
                                                <option value="">Select…</option>
                                                {options.car_conditions.map(o => (
                                                    <option key={o.value} value={o.value}>{o.label}</option>
                                                ))}
                                            </select>
                                        </Field>
                                    )}

                                    <Field label="Name" required>
                                        <input className={inp} disabled={!canEdit}
                                            value={main.name}
                                            onChange={e => onMain("name", e.target.value)} />
                                    </Field>

                                    <Field label="Nick Name" required>
                                        <input className={inp} disabled={!canEdit}
                                            value={main.nickname}
                                            onChange={e => onMain("nickname", e.target.value)} />
                                    </Field>

                                    <Field label="Address" required>
                                        <textarea className={`${inp} resize-none`} rows={3}
                                            disabled={!canEdit}
                                            value={main.address}
                                            onChange={e => onMain("address", e.target.value)} />
                                    </Field>

                                    <div className="grid grid-cols-2 gap-3">
                                        <Field label="City">
                                            <input className={inp} disabled={!canEdit}
                                                value={main.city}
                                                onChange={e => onMain("city", e.target.value)} />
                                        </Field>
                                        <Field label="Post Code">
                                            <input className={inp} disabled={!canEdit}
                                                maxLength={5}
                                                value={main.zipcode}
                                                onChange={e => onMain("zipcode", e.target.value.replace(/\D/g, ""))} />
                                        </Field>
                                    </div>

                                    <div className="grid grid-cols-2 gap-3">
                                        <Field label="Phone">
                                            <input className={inp} disabled={!canEdit}
                                                value={main.phone}
                                                onChange={e => onMain("phone", e.target.value)} />
                                        </Field>
                                        <Field label="Fax">
                                            <input className={inp} disabled={!canEdit}
                                                value={main.fax}
                                                onChange={e => onMain("fax", e.target.value)} />
                                        </Field>
                                    </div>

                                    <Field label="Contact Person">
                                        <input className={inp} disabled={!canEdit}
                                            value={main.contact}
                                            onChange={e => onMain("contact", e.target.value)} />
                                    </Field>

                                    <Field label="ID Card">
                                        <input className={inp} disabled={!canEdit}
                                            value={main.idcard}
                                            onChange={e => onMain("idcard", e.target.value)} />
                                    </Field>

                                    <Field label="ID Valid Date">
                                        <div className="flex items-center gap-5 py-1">
                                            {[
                                                { val: "0", label: "No Expire Date" },
                                                { val: "1", label: "Certain Period" },
                                            ].map(opt => (
                                                <label key={opt.val}
                                                    className="flex items-center gap-1.5 text-sm text-gray-700 cursor-pointer">
                                                    <input type="radio" name="exp_date"
                                                        disabled={!canEdit}
                                                        checked={main.exp_date === opt.val}
                                                        onChange={() => onMain("exp_date", opt.val)} />
                                                    {opt.label}
                                                </label>
                                            ))}
                                        </div>
                                        {main.exp_date === "1" && (
                                            <input className={`${inp} mt-1`} disabled={!canEdit}
                                                placeholder="dd-mm-yyyy"
                                                value={main.certain_per}
                                                onChange={e => onMain("certain_per", e.target.value)} />
                                        )}
                                    </Field>

                                    <Field label="Occupation">
                                        <input className={inp} disabled={!canEdit}
                                            value={main.position}
                                            onChange={e => onMain("position", e.target.value)} />
                                    </Field>

                                    <Field label="Address (Contact Person)">
                                        <textarea className={`${inp} resize-none`} rows={2}
                                            disabled={!canEdit}
                                            value={main.addr_con}
                                            onChange={e => onMain("addr_con", e.target.value)} />
                                    </Field>

                                    <div className="grid grid-cols-2 gap-3">
                                        <Field label="City">
                                            <input className={inp} disabled={!canEdit}
                                                value={main.city_con}
                                                onChange={e => onMain("city_con", e.target.value)} />
                                        </Field>
                                        <Field label="Post Code">
                                            <input className={inp} disabled={!canEdit}
                                                maxLength={5}
                                                value={main.zipcode1}
                                                onChange={e => onMain("zipcode1", e.target.value.replace(/\D/g, ""))} />
                                        </Field>
                                    </div>

                                    <Field label="Contact Person Phone">
                                        <input className={inp} disabled={!canEdit}
                                            value={main.phone_con}
                                            onChange={e => onMain("phone_con", e.target.value)} />
                                    </Field>

                                    <Field label="Email Address">
                                        <input className={inp} type="email" disabled={!canEdit}
                                            value={main.email_addr}
                                            onChange={e => onMain("email_addr", e.target.value)} />
                                    </Field>

                                    <Field label="Adm. Name">
                                        <input className={inp} disabled={!canEdit}
                                            value={main.adm_name}
                                            onChange={e => onMain("adm_name", e.target.value)} />
                                    </Field>

                                    <Field label="BPKB Staff">
                                        <input className={inp} disabled={!canEdit}
                                            value={main.bpkbstaf}
                                            onChange={e => onMain("bpkbstaf", e.target.value)} />
                                    </Field>

                                    <Field label="Branch Manager">
                                        <input className={inp} disabled={!canEdit}
                                            value={main.branch_mgr}
                                            onChange={e => onMain("branch_mgr", e.target.value)} />
                                    </Field>

                                    <div className="pt-4 flex flex-wrap gap-3">
                                        {canEdit && (
                                            <button
                                                onClick={handleSaveMain}
                                                disabled={saving.main}
                                                className={btnPrimary}
                                            >
                                                {saving.main
                                                    ? "Saving…"
                                                    : mode === "AddCF" ? "Save" : "Update"}
                                            </button>
                                        )}
                                        <button
                                            onClick={() => navigate("/supplier")}
                                            className={btnSecondary}
                                        >
                                            {canEdit ? "Cancel" : "Back"}
                                        </button>
                                    </div>

                                    <StatusBanner msg={msgs.main} />
                                </div>

                                <div className="space-y-4 mt-8 lg:mt-0">
                                    <p className="text-xs font-semibold text-gray-400 uppercase tracking-widest pb-2 border-b border-gray-100">
                                        Configuration
                                    </p>

                                    <Field label="Remark">
                                        <input className={inp} disabled={!canEdit}
                                            value={main.remark}
                                            onChange={e => onMain("remark", e.target.value)} />
                                    </Field>

                                    <Field label="Branch Name">
                                        <select className={sel} disabled={!canEdit}
                                            value={main.branch_cd}
                                            onChange={e => onMain("branch_cd", e.target.value)}>
                                            <option value="">Select…</option>
                                            {options.branches.map(o => (
                                                <option key={o.value} value={o.value}>{o.label}</option>
                                            ))}
                                        </select>
                                    </Field>

                                    <Field label="Showroom Category">
                                        <select className={sel} disabled={!canEdit}
                                            value={main.showroom_cat}
                                            onChange={e => onMain("showroom_cat", e.target.value)}>
                                            {options.showroom_cats.map(o => (
                                                <option key={o.value} value={o.value}>{o.label}</option>
                                            ))}
                                        </select>
                                    </Field>

                                    <div className="pt-2 space-y-3 border-t border-gray-100">
                                        <p className="text-xs font-semibold text-gray-400 uppercase tracking-widest pt-2">
                                            Audit
                                        </p>
                                        <ReadOnlyField label="Create By" value={main.create_by} />
                                        <ReadOnlyField label="Create Date" value={main.create_date} />
                                        {main.ca_lastupd && (
                                            <>
                                                <ReadOnlyField label="Update By" value={main.update_by} />
                                                <ReadOnlyField label="Last Update" value={main.ca_lastupd} />
                                            </>
                                        )}
                                    </div>
                                </div>
                            </div>
                        )}

                        {activeTab === "tax" && (
                            <div className="max-w-xl space-y-4">

                                <div className="flex items-center gap-3 pb-2 border-b border-gray-100">
                                    <h2 className="text-sm font-semibold text-gray-700">
                                        Tax Information
                                    </h2>
                                    {taxLocked && (
                                        <span className="text-xs bg-amber-100 text-amber-700 border
                                     border-amber-200 px-2 py-0.5 rounded-full font-medium">
                                            Locked — Tax Type set
                                        </span>
                                    )}
                                    {!canEdit && !taxLocked && (
                                        <span className="text-xs bg-gray-100 text-gray-500 border
                                     border-gray-200 px-2 py-0.5 rounded-full">
                                            View only
                                        </span>
                                    )}
                                </div>

                                <Field label="NPWP Type">
                                    <input className={inp} readOnly
                                        value="PT — Corporate" />
                                </Field>

                                <Field label="NPWP No.">
                                    <div className="flex items-center gap-1 text-sm">
                                        {[
                                            { len: 2, sep: "." },
                                            { len: 3, sep: "." },
                                            { len: 3, sep: "." },
                                            { len: 1, sep: "-" },
                                            { len: 3, sep: "." },
                                            { len: 4, sep: "" },
                                        ].reduce<React.ReactNode[]>((acc, seg, i, arr) => {
                                            const start = arr.slice(0, i).reduce((s, x) => s + x.len, 0);
                                            acc.push(
                                                <input
                                                    key={i}
                                                    className={`${inp} text-center`}
                                                    style={{ width: `${seg.len * 14 + 24}px` }}
                                                    maxLength={seg.len}
                                                    disabled={!canEdit || taxLocked}
                                                    value={tax.npwp_no.slice(start, start + seg.len)}
                                                    onChange={e => {
                                                        const v = e.target.value.replace(/\D/g, "").slice(0, seg.len);
                                                        const full = tax.npwp_no.padEnd(15, " ");
                                                        const next = (full.slice(0, start) + v).padEnd(
                                                            start + seg.len, " "
                                                        ) + full.slice(start + seg.len);
                                                        setTax(t => ({ ...t, npwp_no: next.trimEnd() }));
                                                    }}
                                                />
                                            );
                                            if (seg.sep)
                                                acc.push(<span key={`s${i}`} className="text-gray-400 select-none">{seg.sep}</span>);
                                            return acc;
                                        }, [])}
                                    </div>
                                </Field>

                                <Field label="NPWP Detail">
                                    <select className={sel} disabled value={tax.npwp_detail}>
                                        <option value="">Select…</option>
                                        {options.npwp_details.map(o => (
                                            <option key={o.value} value={o.value}>{o.label}</option>
                                        ))}
                                    </select>
                                </Field>

                                <Field label="NPWP Name">
                                    <input className={inp} disabled={!canEdit || taxLocked}
                                        value={tax.npwp_nm}
                                        onChange={e => setTax(t => ({ ...t, npwp_nm: e.target.value }))} />
                                </Field>

                                <Field label="NPWP Address">
                                    <textarea className={`${inp} resize-none`} rows={2}
                                        disabled={!canEdit || taxLocked}
                                        value={tax.npwp_addr}
                                        onChange={e => setTax(t => ({ ...t, npwp_addr: e.target.value }))} />
                                </Field>

                                <Field label="NPWP Province">
                                    <select className={sel} disabled={!canEdit || taxLocked}
                                        value={tax.province} onChange={e => onTaxProvince(e.target.value)}>
                                        <option value="">Select…</option>
                                        {options.provinces.map(o => (
                                            <option key={o.value} value={o.value}>{o.label}</option>
                                        ))}
                                    </select>
                                </Field>

                                <Field label="NPWP City">
                                    <select className={sel} disabled={!canEdit || taxLocked}
                                        value={tax.city}
                                        onChange={e => setTax(t => ({ ...t, city: e.target.value }))}>
                                        <option value="">Select…</option>
                                        {citiesForProvince.map(o => (
                                            <option key={o.value} value={o.value}>{o.label}</option>
                                        ))}
                                    </select>
                                </Field>

                                <Field label="NPWP Start">
                                    <input className={inp} readOnly value="0" />
                                </Field>

                                <Field label="PPN Status">
                                    <select className={sel} disabled={!canEdit || taxLocked}
                                        value={tax.ppnsts} onChange={e => onPpnSts(e.target.value)}>
                                        <option value="">Select…</option>
                                        <option value="1">PPN</option>
                                        <option value="0">Non PPN</option>
                                    </select>
                                </Field>

                                <Field label="PPN Start Date">
                                    <input className={inp} readOnly value={tax.ppnstartdate}
                                        placeholder="Auto-filled when PPN selected" />
                                </Field>

                                <Field label="Tax Free (From → To)">
                                    <div className="flex items-center gap-2">
                                        <input className={inp} disabled={!canEdit || taxLocked}
                                            placeholder="dd-mm-yyyy"
                                            value={tax.taxfree}
                                            onChange={e => setTax(t => ({
                                                ...t, taxfree: e.target.value, taxfree2: "",
                                            }))} />
                                        <span className="text-sm text-gray-400 shrink-0">to</span>
                                        <input className={inp}
                                            disabled={!canEdit || taxLocked || !tax.taxfree}
                                            placeholder="dd-mm-yyyy"
                                            value={tax.taxfree2}
                                            onChange={e => setTax(t => ({ ...t, taxfree2: e.target.value }))} />
                                    </div>
                                </Field>

                                <Field label="Tax Type">
                                    <select className={sel} disabled value={tax.pph}>
                                        <option value="">—</option>
                                        {options.tax_types.map(o => (
                                            <option key={o.value} value={o.value}>{o.label}</option>
                                        ))}
                                    </select>
                                </Field>

                                <Field label="Tax Rate">
                                    <div className="flex items-center gap-2">
                                        <select className={`${sel} flex-1`} disabled value={tax.rate}>
                                            <option value="1">Progressive</option>
                                            <option value="2">Flat</option>
                                        </select>
                                        <input className={`${inp} w-16 text-center`} readOnly value="2" />
                                        <span className="text-sm text-gray-500 shrink-0">%</span>
                                    </div>
                                </Field>

                                <Field label="DPP">
                                    <div className="flex items-center gap-2">
                                        <input className={`${inp} w-16 text-center`} readOnly value={tax.dpp} />
                                        <span className="text-sm text-gray-500">% × Bruto</span>
                                    </div>
                                </Field>

                                <Field label="Correspondence Address for Withholding Tax Certificate Delivery">
                                    <textarea className={`${inp} resize-none`} rows={3}
                                        disabled={!canEdit}
                                        value={tax.kores_address}
                                        onChange={e => setTax(t => ({
                                            ...t, kores_address: e.target.value,
                                        }))} />
                                </Field>

                                {tax.update_by && (
                                    <div className="pt-2 space-y-3 border-t border-gray-100">
                                        <ReadOnlyField label="Update By" value={tax.update_by} />
                                        <ReadOnlyField label="Update Date" value={tax.lastupdate} />
                                    </div>
                                )}

                                <div className="pt-4 flex flex-wrap gap-3">
                                    {!taxLocked && canEdit && (
                                        <button
                                            onClick={handleSaveTax}
                                            disabled={saving.tax}
                                            className={btnPrimary}
                                        >
                                            {saving.tax
                                                ? "Saving…"
                                                : tax.is_saved ? "Update" : "Save"}
                                        </button>
                                    )}
                                    <button
                                        onClick={() => navigate("/dealer")}
                                        className={btnSecondary}
                                    >
                                        {taxLocked || !canEdit ? "Back" : "Cancel"}
                                    </button>
                                </div>

                                <StatusBanner msg={msgs.tax} />
                            </div>
                        )}

                        {activeTab === "bank" && (() => {
                            const isEditing = bankEdit !== null;

                            const BankTable = ({ rows, title }: { rows: BankAccount[]; title: string }) => (
                                <div className="mb-6">
                                    <h3 className="text-sm font-semibold text-gray-600 mb-2">{title}</h3>
                                    <div className="overflow-x-auto rounded-lg border border-gray-200">
                                        <table className="w-full text-xs">
                                            <thead className="bg-gray-50">
                                                <tr>
                                                    {canEdit && <th className="py-2 px-3 text-left font-medium text-gray-500 w-20">Action</th>}
                                                    <th className="py-2 px-3 text-left font-medium text-gray-500">Acc Name</th>
                                                    <th className="py-2 px-3 text-left font-medium text-gray-500">Acc No</th>
                                                    <th className="py-2 px-3 text-left font-medium text-gray-500">Bank</th>
                                                    <th className="py-2 px-3 text-left font-medium text-gray-500">Branch</th>
                                                    <th className="py-2 px-3 text-left font-medium text-gray-500">Benef. Type</th>
                                                    <th className="py-2 px-3 text-left font-medium text-gray-500">Resident</th>
                                                    <th className="py-2 px-3 text-left font-medium text-gray-500">Updated</th>
                                                    <th className="py-2 px-3 text-center font-medium text-gray-500">Default</th>
                                                </tr>
                                            </thead>
                                            <tbody className="divide-y divide-gray-100">
                                                {rows.length === 0 ? (
                                                    <tr><td colSpan={canEdit ? 9 : 8}
                                                        className="py-6 text-center text-gray-400">No records</td></tr>
                                                ) : rows.map(r => (
                                                    <tr key={r.acc_no} className="hover:bg-gray-50">
                                                        {canEdit && (
                                                            <td className="py-2 px-3">
                                                                <div className="flex gap-1">
                                                                    <button onClick={() => handleBankEdit(r)}
                                                                        className="px-2 py-1 bg-blue-50 hover:bg-blue-100 text-blue-700 rounded text-xs font-medium transition-colors">
                                                                        Edit
                                                                    </button>
                                                                    <button onClick={() => handleBankDelete(r)}
                                                                        className="px-2 py-1 bg-red-50 hover:bg-red-100 text-red-600 rounded text-xs font-medium transition-colors">
                                                                        Del
                                                                    </button>
                                                                </div>
                                                            </td>
                                                        )}
                                                        <td className="py-2 px-3 text-gray-800 font-medium">{r.acc_name}</td>
                                                        <td className="py-2 px-3 font-mono text-gray-700">{r.acc_no}</td>
                                                        <td className="py-2 px-3 text-gray-600">{r.acc_bank_desc || r.acc_bank}</td>
                                                        <td className="py-2 px-3 text-gray-600">{r.acc_bank_branch}</td>
                                                        <td className="py-2 px-3 text-gray-600">{r.beneficiary_type_desc || r.beneficiary_type}</td>
                                                        <td className="py-2 px-3 text-gray-600">{r.resident_status_desc || r.resident_status}</td>
                                                        <td className="py-2 px-3 text-gray-500">{r.last_update}</td>
                                                        <td className="py-2 px-3 text-center">
                                                            {r.is_default
                                                                ? <span className="text-green-600 font-bold text-base">✔</span>
                                                                : <span className="text-gray-300">–</span>}
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            );

                            return (
                                <div>
                                    {canEdit && (
                                        <div className="mb-6 p-4 border border-gray-200 rounded-xl bg-gray-50">
                                            <h3 className="text-sm font-semibold text-gray-700 mb-4">
                                                {isEditing ? `Edit Account — ${bankEdit!.acc_no}` : "Add New Account"}
                                            </h3>
                                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                                                <Field label="Account Type" required>
                                                    <select className={sel} disabled={isEditing}
                                                        value={bankForm.acc_type}
                                                        onChange={e => setBankForm(f => ({ ...f, acc_type: e.target.value }))}>
                                                        <option value="">Select…</option>
                                                        <option value="D">Disbursement</option>
                                                        <option value="C">Commission</option>
                                                    </select>
                                                </Field>
                                                <Field label="Account Name" required>
                                                    <input className={inp}
                                                        value={bankForm.acc_name}
                                                        onChange={e => setBankForm(f => ({ ...f, acc_name: e.target.value }))} />
                                                </Field>
                                                <Field label="Account No">
                                                    <input className={inp}
                                                        readOnly={isEditing}
                                                        placeholder={isEditing ? "Cannot change Acc No" : ""}
                                                        value={bankForm.acc_no}
                                                        onChange={e => setBankForm(f => ({ ...f, acc_no: e.target.value }))} />
                                                </Field>
                                                <Field label="Bank" required>
                                                    <select className={sel}
                                                        value={bankForm.bank}
                                                        onChange={e => setBankForm(f => ({ ...f, bank: e.target.value }))}>
                                                        <option value="">Select…</option>
                                                        {(options.banks ?? []).map(o => (
                                                            <option key={o.value} value={o.value}>{o.label}</option>
                                                        ))}
                                                    </select>
                                                </Field>
                                                <Field label="Bank Branch Name" required>
                                                    <input className={inp}
                                                        value={bankForm.bank_brch}
                                                        onChange={e => setBankForm(f => ({ ...f, bank_brch: e.target.value }))} />
                                                </Field>
                                                <Field label="Beneficiary Type (BI)" required>
                                                    <select className={sel}
                                                        value={bankForm.beneficiary_type}
                                                        onChange={e => setBankForm(f => ({ ...f, beneficiary_type: e.target.value }))}>
                                                        <option value="">Select…</option>
                                                        {(options.beneficiary_types ?? []).map(o => (
                                                            <option key={o.value} value={o.value}>{o.label}</option>
                                                        ))}
                                                    </select>
                                                </Field>
                                                <Field label="Resident Status" required>
                                                    <select className={sel}
                                                        value={bankForm.resident_status}
                                                        onChange={e => setBankForm(f => ({ ...f, resident_status: e.target.value }))}>
                                                        <option value="">Select…</option>
                                                        {(options.resident_statuses ?? []).map(o => (
                                                            <option key={o.value} value={o.value}>{o.label}</option>
                                                        ))}
                                                    </select>
                                                </Field>
                                                <Field label="Default">
                                                    <label className="flex items-center gap-2 pt-2 cursor-pointer">
                                                        <input type="checkbox"
                                                            checked={bankForm.is_default}
                                                            onChange={e => setBankForm(f => ({ ...f, is_default: e.target.checked }))} />
                                                        <span className="text-sm text-gray-700">Set as Default</span>
                                                    </label>
                                                </Field>
                                            </div>
                                            <div className="mt-4 flex gap-3">
                                                <button onClick={handleBankSave} disabled={saving.bank}
                                                    className={btnPrimary}>
                                                    {saving.bank ? "Saving…" : isEditing ? "Update" : "Save"}
                                                </button>
                                                <button className={btnSecondary}
                                                    onClick={() => { setBankForm(defBankForm); setBankEdit(null); setMsg("bank", undefined); }}>
                                                    Cancel
                                                </button>
                                            </div>
                                        </div>
                                    )}

                                    <BankTable rows={disbAccounts} title="Disbursement Accounts (D)" />
                                    <BankTable rows={commAccounts} title="Commission Accounts (C)" />
                                    <StatusBanner msg={msgs.bank} />
                                </div>
                            );
                        })()}

                        {activeTab === "add" && (
                            <div className="max-w-sm space-y-4">
                                <h2 className="text-sm font-semibold text-gray-600 pb-2 border-b border-gray-100">
                                    Additional
                                </h2>
                                <Field label="Area">
                                    <select className={sel} disabled={!canEdit}
                                        value={additional.bd_area}
                                        onChange={e => setAdditional(a => ({ ...a, bd_area: e.target.value }))}>
                                        <option value="">Select…</option>
                                        {(options.areas ?? []).map(o => (
                                            <option key={o.value} value={o.value}>{o.label}</option>
                                        ))}
                                    </select>
                                </Field>
                                <Field label="CMO">
                                    <select className={sel} disabled={!canEdit}
                                        value={additional.cmo}
                                        onChange={e => setAdditional(a => ({ ...a, cmo: e.target.value }))}>
                                        <option value="">Select…</option>
                                        {(options.cmos ?? []).map(o => (
                                            <option key={o.value} value={o.value}>{o.label}</option>
                                        ))}
                                    </select>
                                </Field>
                                <Field label="Brand">
                                    <select className={sel} disabled={!canEdit}
                                        value={additional.brand}
                                        onChange={e => setAdditional(a => ({ ...a, brand: e.target.value }))}>
                                        <option value="">Select…</option>
                                        {(options.brands ?? []).map(o => (
                                            <option key={o.value} value={o.value}>{o.label}</option>
                                        ))}
                                    </select>
                                </Field>
                                {canEdit && (
                                    <div className="pt-2 flex gap-3">
                                        <button onClick={handleSaveAdditional} disabled={saving.add}
                                            className={btnPrimary}>
                                            {saving.add ? "Saving…" : "Save"}
                                        </button>
                                        <button onClick={() => navigate("/dealer")}
                                            className={btnSecondary}>Cancel</button>
                                    </div>
                                )}
                                <StatusBanner msg={msgs.add} />
                            </div>
                        )}

                        {activeTab === "dev" && (
                            <div className="space-y-6">
                                <div>
                                    <h2 className="text-sm font-semibold text-gray-600 pb-2 border-b border-gray-100 mb-3">
                                        Document Checklist
                                    </h2>
                                    <div className="overflow-x-auto rounded-lg border border-gray-200">
                                        <table className="w-full text-sm border-collapse">
                                            <thead className="bg-gray-50">
                                                <tr>
                                                    <th className="py-2 px-4 text-center font-medium text-gray-600 border-b border-gray-200 w-28">
                                                        Received
                                                    </th>
                                                    <th className="py-2 px-4 text-center font-medium text-gray-600 border-b border-gray-200 w-28">
                                                        Not Received
                                                    </th>
                                                    <th className="py-2 px-4 text-left font-medium text-gray-600 border-b border-gray-200">
                                                        Document
                                                    </th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {deviItems.length === 0 ? (
                                                    <tr><td colSpan={3} className="py-8 text-center text-gray-400">
                                                        No checklist items
                                                    </td></tr>
                                                ) : deviItems.map((item, idx) => (
                                                    <tr key={item.dev_cd}
                                                        className={idx % 2 === 0 ? "bg-white" : "bg-gray-50"}>
                                                        <td className="py-2 px-4 text-center border-b border-gray-100">
                                                            <input type="radio"
                                                                name={`dev_${item.dev_cd}`}
                                                                disabled={!canEdit}
                                                                checked={item.is_check === "1"}
                                                                onChange={() => handleToggleDevi(item.dev_cd, true)}
                                                                className="w-4 h-4 accent-green-600" />
                                                        </td>
                                                        <td className="py-2 px-4 text-center border-b border-gray-100">
                                                            <input type="radio"
                                                                name={`dev_${item.dev_cd}`}
                                                                disabled={!canEdit}
                                                                checked={item.is_check !== "1"}
                                                                onChange={() => handleToggleDevi(item.dev_cd, false)}
                                                                className="w-4 h-4 accent-red-500" />
                                                        </td>
                                                        <td className="py-2 px-4 text-gray-700 border-b border-gray-100">
                                                            {item.description}
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                    <p className="mt-2 text-xs text-gray-500 italic">
                                        Copy KTP yang harus diterima oleh Genie adalah copy KTP yang nama pejabatnya
                                        tertulis di Kartu Identitas Dealer.
                                    </p>
                                </div>

                                <div>
                                    <h2 className="text-sm font-semibold text-gray-600 pb-2 border-b border-gray-100 mb-3">
                                        Pertimbangan (Considerations)
                                    </h2>
                                    <div className="space-y-2">
                                        {(["note1", "note2", "note3", "note4", "note5"] as const).map((k, i) => (
                                            <textarea key={k} rows={1}
                                                className={`${inp} resize-none`}
                                                disabled={!canEdit}
                                                placeholder={`Note ${i + 1}`}
                                                value={devNotes[k]}
                                                onChange={e => setDevNotes(n => ({ ...n, [k]: e.target.value }))} />
                                        ))}
                                    </div>
                                </div>

                                <div>
                                    <h2 className="text-sm font-semibold text-gray-600 pb-2 border-b border-gray-100 mb-3">
                                        Janji CMO (CMO Promise)
                                    </h2>
                                    <textarea className={`${inp} resize-none`} rows={4}
                                        disabled={!canEdit}
                                        value={devNotes.janji}
                                        onChange={e => setDevNotes(n => ({ ...n, janji: e.target.value }))} />
                                </div>

                                {canEdit && (
                                    <div className="flex gap-3">
                                        <button onClick={handleSaveDevNotes} disabled={saving.dev}
                                            className={btnPrimary}>
                                            {saving.dev ? "Saving…" : "Update"}
                                        </button>
                                        <button onClick={() => navigate("/dealer")}
                                            className={btnSecondary}>Cancel</button>
                                    </div>
                                )}
                                <StatusBanner msg={msgs.dev} />
                            </div>
                        )}

                        {activeTab === "doc" && (
                            <div>
                                <h2 className="text-sm font-semibold text-gray-600 pb-2
                               border-b border-gray-100 mb-5">
                                    Upload Dealer Documents
                                </h2>

                                <div className="space-y-3">
                                    {DEALER_DOCS.map(doc => {
                                        const existing = docFiles[doc.key] || [];
                                        const isUpl = uploading === doc.key;

                                        return (
                                            <div key={doc.key}
                                                className="rounded-xl border border-gray-200 bg-white p-4 transition-colors hover:border-gray-300">
                                                <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
                                                    <div className="flex-shrink-0 sm:w-52">
                                                        <p className="text-sm font-medium text-gray-700">{doc.label}</p>
                                                        {doc.hasLainnya && (
                                                            <input
                                                                className={`${inp} mt-1.5`}
                                                                placeholder="Keterangan…"
                                                                disabled={!canEdit}
                                                                value={docLainnya}
                                                                onChange={e => setDocLainnya(e.target.value)} />
                                                        )}
                                                    </div>

                                                    <div className="min-w-0 flex-1">
                                                        {canEdit && (
                                                            <label className={[
                                                                "inline-flex items-center gap-1.5 cursor-pointer rounded-lg",
                                                                "border border-dashed border-blue-300 bg-blue-50 hover:bg-blue-100",
                                                                "px-3 py-1.5 text-xs text-blue-700 transition-colors",
                                                                isUpl ? "opacity-60 cursor-not-allowed" : "",
                                                            ].join(" ")}>
                                                                <svg className={`w-4 h-4 ${isUpl ? "animate-spin" : ""}`}
                                                                    fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                                    {isUpl
                                                                        ? <path strokeLinecap="round" strokeLinejoin="round"
                                                                            strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001
                                                                                8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003
                                                                                8.003 0 01-15.357-2m15.357 2H15" />
                                                                        : <path strokeLinecap="round" strokeLinejoin="round"
                                                                            strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />}
                                                                </svg>
                                                                {isUpl ? "Uploading…" : "Choose File(s)"}
                                                                <input type="file" multiple className="hidden"
                                                                    disabled={isUpl}
                                                                    onChange={e => {
                                                                        if (e.target.files?.length) {
                                                                            handleFileUpload(doc.key, e.target.files);
                                                                            e.target.value = "";
                                                                        }
                                                                    }} />
                                                            </label>
                                                        )}

                                                        {existing.length > 0 ? (
                                                            <div className={`flex flex-wrap gap-2 ${canEdit ? "mt-2.5" : ""}`}>
                                                                {existing.map(f => {
                                                                    const fullName = `${f.file_nm}${f.file_ext ? `.${f.file_ext}` : ""}`;
                                                                    return (
                                                                        <div key={f.id}
                                                                            className="flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-2.5 py-1.5">
                                                                            <button
                                                                                onClick={() => handleFilePreview(f)}
                                                                                className="inline-flex items-center gap-1.5 rounded-md border border-blue-300
                                                                                    bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700 transition-colors
                                                                                    hover:border-blue-400 hover:bg-blue-100"
                                                                            >
                                                                                <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                                                                        d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                                                                        d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                                                                                </svg>
                                                                                View
                                                                            </button>
                                                                            <span className="max-w-[180px] truncate text-xs text-gray-700" title={fullName}>
                                                                                {fullName}
                                                                            </span>
                                                                            {f.created_date && (
                                                                                <span className="whitespace-nowrap text-[11px] text-gray-400">{f.created_date}</span>
                                                                            )}
                                                                            {canEdit && (
                                                                                <button
                                                                                    onClick={() => handleFileDelete(f.id)}
                                                                                    title="Delete"
                                                                                    className="text-gray-300 transition-colors hover:text-red-500"
                                                                                >
                                                                                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                                                                    </svg>
                                                                                </button>
                                                                            )}
                                                                        </div>
                                                                    );
                                                                })}
                                                            </div>
                                                        ) : !canEdit ? (
                                                            <span className="text-xs italic text-gray-400">No file uploaded</span>
                                                        ) : null}
                                                    </div>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>

                                <StatusBanner msg={msgs.doc} />
                            </div>
                        )}

                        {activeTab === "notes" && (
                            <div className="max-w-2xl">
                                <h2 className="text-sm font-semibold text-gray-600 pb-2 border-b border-gray-100 mb-4">
                                    Additional Notes
                                </h2>
                                <textarea
                                    value={notes}
                                    disabled={!canEdit}
                                    onChange={e => setNotes(e.target.value)}
                                    rows={10}
                                    className={`${inp} resize-none font-sans`}
                                    placeholder={canEdit ? "Enter additional notes…" : ""}
                                />
                                {canEdit && (
                                    <div className="mt-4 flex gap-3">
                                        <button
                                            onClick={handleSaveNotes}
                                            disabled={savingNotes}
                                            className={btnPrimary}
                                        >
                                            {savingNotes ? "Saving…" : notes ? "Update" : "Save"}
                                        </button>
                                        <button
                                            onClick={() => navigate("/dealer")}
                                            className={btnSecondary}
                                        >
                                            Cancel
                                        </button>
                                    </div>
                                )}
                                <StatusBanner msg={msgs.notes} />
                            </div>
                        )}

                    </div>
                </div>
            </div>
        </div>
    );
};

export default SupplierEntryPage;