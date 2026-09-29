import React, { useEffect, useState, useCallback, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import api from "../../../api/axiosInstance";

type Tab = "company" | "prem" | "third" | "clause" | "driver" | "passenger" | "loading";

interface CompanyForm {
    ins_cd: string; ins_co: string; stamp_duty: string; stamp_dutyins: string;
    address: string; city: string; zipcode: string;
    phone: string; fax: string; contact: string;
}

interface PremiumRow {
    ID: number; insurance_area: string; area_name: string;
    model: string; model_nm: string; l_amount: string;
    tlo_ar: string; tlo_name: string;
    net_premi: string; net_rec_new: string; net_rec_used: string; premi: string;
}

interface PremForm {
    insurance_area: string; model: string; l_amount: string; tlo_ar: string;
    net_premi: string; net_rec_new: string; net_rec_used: string; premi: string;
}

interface ThirdPartyRow {
    ID_INSTPL: number; model: string; model_nm: string;
    tpl_amt: string; tpl_fee: string; tpl_fee2: string;
}

interface ThirdPartyForm { model: string; tpl_amt: string; tpl_fee: string; tpl_fee2: string; }
interface ClauseRow {
    insurance_area: string; area_name: string;
    clause: string; clause_name: string;
    tlo_ar: string; tlo_name: string;
    net_premi: string; net_rec_new: string; net_rec_used: string; premi: string;
}

interface ClauseAddForm {
    insurance_area: string; clause: string; tlo_ar: string;
    net_premi: string; net_rec_new: string; net_rec_used: string; premi: string;
}

interface ClauseEditForm { net_premi: string; net_rec_new: string; net_rec_used: string; premi: string; }
interface DriverRow { pa_amount: string; driver_fee_ins: string; driver_fee_cust: string; }
interface DriverAddForm { pa_amount: string; driver_fee_ins: string; driver_fee_cust: string; }
interface DriverEditForm { driver_fee_ins: string; driver_fee_cust: string; }
interface PassengerRow { seat_amount: string; seat: string; seat_fee_ins: string; seat_fee_cust: string; }
interface PassengerAddForm { seat_amount: string; seat: string; seat_fee_ins: string; seat_fee_cust: string; }
interface PassengerEditForm { seat_fee_ins: string; seat_fee_cust: string; }
interface LoadingRow { ID: number; model: string; model_nm: string; lr_age: string; lr_next: boolean; }
interface LoadingAddForm { model: string; lr_age: string; lr_next: boolean; }
interface LoadingEditForm { lr_age: string; lr_next: boolean; }

interface Opt { value: string; label: string; }
interface Msg { type: "success" | "error"; text: string; }
interface PremOpts { areas: Opt[]; models: Opt[]; coverages: Opt[]; clauses: Opt[]; }


const defCompany: CompanyForm = {
    ins_cd: "", ins_co: "", stamp_duty: "0", stamp_dutyins: "0",
    address: "", city: "", zipcode: "", phone: "", fax: "", contact: "",
};

const defPremForm: PremForm = { insurance_area: "", model: "", l_amount: "", tlo_ar: "", net_premi: "", net_rec_new: "", net_rec_used: "", premi: "" };
const defTpForm: ThirdPartyForm = { model: "", tpl_amt: "", tpl_fee: "", tpl_fee2: "" };
const defClForm: ClauseAddForm = { insurance_area: "", clause: "", tlo_ar: "", net_premi: "", net_rec_new: "", net_rec_used: "", premi: "" };
const defClEdit: ClauseEditForm = { net_premi: "", net_rec_new: "", net_rec_used: "", premi: "" };
const defDrForm: DriverAddForm = { pa_amount: "", driver_fee_ins: "", driver_fee_cust: "" };
const defDrEdit: DriverEditForm = { driver_fee_ins: "", driver_fee_cust: "" };
const defPsForm: PassengerAddForm = { seat_amount: "", seat: "", seat_fee_ins: "", seat_fee_cust: "" };
const defPsEdit: PassengerEditForm = { seat_fee_ins: "", seat_fee_cust: "" };
const defLrForm: LoadingAddForm = { model: "", lr_age: "", lr_next: false };
const defLrEdit: LoadingEditForm = { lr_age: "", lr_next: false };


const inp =
    "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm " +
    "focus:ring-2 focus:ring-blue-500 focus:border-blue-500 " +
    "disabled:bg-gray-100 disabled:cursor-not-allowed";
const sel = inp;

function Field({ label, children }: { label: string; children: React.ReactNode }) {
    return (
        <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-gray-500">{label}</label>
            {children}
        </div>
    );
}

function Banner({ msg, onClose }: { msg: Msg; onClose: () => void }) {
    return (
        <div className={`flex items-start gap-3 rounded-lg px-4 py-3 text-sm border mt-4 ${msg.type === "success" ? "bg-green-50 border-green-200 text-green-700" : "bg-red-50 border-red-200 text-red-700"
            }`}>
            <span className="flex-1">{msg.text}</span>
            <button onClick={onClose} className="text-lg leading-none opacity-60 hover:opacity-100">×</button>
        </div>
    );
}

function PctInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
    return (
        <div className="flex items-center gap-1">
            <input className={`${inp} text-right`} value={value}
                onChange={e => onChange(e.target.value)} />
            <span className="text-sm text-gray-500 shrink-0">%</span>
        </div>
    );
}

function AmtInput({ value, onChange, suffix }: { value: string; onChange: (v: string) => void; suffix?: string }) {
    return (
        <div className="flex items-center gap-1">
            <input className={`${inp} text-right`} value={value}
                onChange={e => onChange(e.target.value.replace(/[^0-9,]/g, ""))} />
            {suffix && <span className="text-sm text-gray-500 shrink-0">{suffix}</span>}
        </div>
    );
}

function StubTab({ title, desc }: { title: string; desc: string }) {
    return (
        <div className="py-16 text-center text-gray-400">
            <svg className="w-12 h-12 mx-auto mb-3 text-gray-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <p className="font-semibold text-gray-500">{title}</p>
            <p className="text-sm mt-1">{desc}</p>
        </div>
    );
}

function SubTable({ headers, rows, loading }: {
    headers: string[];
    rows: React.ReactNode[][];
    loading?: boolean;
}) {
    const span = headers.length;
    return (
        <div className="overflow-x-auto rounded-xl border border-gray-200">
            <table className="w-full text-xs">
                <thead className="bg-gradient-to-r from-gray-50 to-gray-100">
                    <tr>
                        {headers.map(h => (
                            <th key={h} className="py-2.5 px-3 text-left font-semibold text-gray-500 uppercase tracking-wide">
                                {h}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                    {loading ? (
                        <tr><td colSpan={span} className="py-4 text-center">
                            <div className="flex justify-center">
                                <svg className="animate-spin h-5 w-5 text-blue-500" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                </svg>
                            </div>
                        </td></tr>
                    ) : rows.length === 0 ? (
                        <tr><td colSpan={span} className="py-10 text-center text-gray-400">No records</td></tr>
                    ) : rows.map((cells, idx) => (
                        <tr key={idx} className={`hover:bg-blue-50 transition-colors ${idx % 2 === 0 ? "bg-white" : "bg-gray-50"}`}>
                            {cells.map((c, ci) => (
                                <td key={ci} className="py-2 px-3 text-gray-700">{c}</td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

function EditBtn({ onClick }: { onClick: () => void }) {
    return (
        <button onClick={onClick}
            className="px-2.5 py-1 bg-blue-600 hover:bg-blue-700 text-white text-xs rounded font-medium mr-1.5">
            Edit
        </button>
    );
}
function DelBtn({ onClick }: { onClick: () => void }) {
    return (
        <button onClick={onClick}
            className="px-2.5 py-1 bg-red-50 hover:bg-red-100 text-red-600 border border-red-200 text-xs rounded font-medium">
            Del
        </button>
    );
}

function Modal({ title, onClose, onSave, saving, children, msg, onMsgClose }: {
    title: string; onClose: () => void; onSave: () => void; saving: boolean;
    children: React.ReactNode; msg: Msg | null; onMsgClose: () => void;
}) {
    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
            onClick={e => e.target === e.currentTarget && onClose()}>
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md animate-in slide-in-from-top-4">
                <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
                    <h2 className="font-semibold text-gray-800">{title}</h2>
                    <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">×</button>
                </div>
                <div className="px-6 py-5 space-y-3">
                    {children}
                    {msg && <Banner msg={msg} onClose={onMsgClose} />}
                </div>
                <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
                    <button onClick={onClose}
                        className="px-4 py-2 text-sm border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">
                        Cancel
                    </button>
                    <button onClick={onSave} disabled={saving}
                        className="px-4 py-2 text-sm rounded-lg font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-60">
                        {saving ? "Saving…" : "Save"}
                    </button>
                </div>
            </div>
        </div>
    );
}

const InsuranceEntryPage: React.FC = () => {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const id0 = searchParams.get("id") || "View";
    const insCd0 = searchParams.get("ins_cd") || "";
    const akses0 = searchParams.get("akses") || "0";

    const [mode, setMode] = useState(id0);
    const [currentCd, setCurrentCd] = useState(insCd0);
    const [activeTab, setActiveTab] = useState<Tab>("company");
    const [loading, setLoading] = useState(false);

    const canEdit = mode !== "View" && (mode === "Add" || akses0 === "9");
    const mainSaved = currentCd !== "";

    const [company, setCompany] = useState<CompanyForm>({ ...defCompany });
    const [compSaving, setCompSaving] = useState(false);
    const [compMsg, setCompMsg] = useState<Msg | null>(null);

    const optLoadedRef = useRef(false);
    const [opts, setOpts] = useState<PremOpts>({ areas: [], models: [], coverages: [], clauses: [] });

    const [premiums, setPremiums] = useState<PremiumRow[]>([]);
    const [premForm, setPremForm] = useState<PremForm>(defPremForm);
    const [premSaving, setPremSaving] = useState(false);
    const [premMsg, setPremMsg] = useState<Msg | null>(null);
    const [editPrem, setEditPrem] = useState<PremiumRow | null>(null);
    const [editPremForm, setEditPremForm] = useState<Partial<PremForm>>({});
    const [editPremSaving, setEditPremSaving] = useState(false);
    const [editPremMsg, setEditPremMsg] = useState<Msg | null>(null);

    const [thirdParty, setThirdParty] = useState<ThirdPartyRow[]>([]);
    const [tpForm, setTpForm] = useState<ThirdPartyForm>(defTpForm);
    const [tpSaving, setTpSaving] = useState(false);
    const [tpMsg, setTpMsg] = useState<Msg | null>(null);
    const [editTp, setEditTp] = useState<ThirdPartyRow | null>(null);
    const [editTpForm, setEditTpForm] = useState<Partial<ThirdPartyForm>>({});
    const [editTpSaving, setEditTpSaving] = useState(false);
    const [editTpMsg, setEditTpMsg] = useState<Msg | null>(null);

    const [clauses, setClauses] = useState<ClauseRow[]>([]);
    const [clForm, setClForm] = useState<ClauseAddForm>(defClForm);
    const [clSaving, setClSaving] = useState(false);
    const [clMsg, setClMsg] = useState<Msg | null>(null);
    const [editCl, setEditCl] = useState<ClauseRow | null>(null);
    const [editClForm, setEditClForm] = useState<ClauseEditForm>(defClEdit);
    const [editClSaving, setEditClSaving] = useState(false);
    const [editClMsg, setEditClMsg] = useState<Msg | null>(null);

    const [drivers, setDrivers] = useState<DriverRow[]>([]);
    const [drForm, setDrForm] = useState<DriverAddForm>(defDrForm);
    const [drSaving, setDrSaving] = useState(false);
    const [drMsg, setDrMsg] = useState<Msg | null>(null);
    const [editDr, setEditDr] = useState<DriverRow | null>(null);
    const [editDrForm, setEditDrForm] = useState<DriverEditForm>(defDrEdit);
    const [editDrSaving, setEditDrSaving] = useState(false);
    const [editDrMsg, setEditDrMsg] = useState<Msg | null>(null);

    const [passengers, setPassengers] = useState<PassengerRow[]>([]);
    const [psForm, setPsForm] = useState<PassengerAddForm>(defPsForm);
    const [psSaving, setPsSaving] = useState(false);
    const [psMsg, setPsMsg] = useState<Msg | null>(null);
    const [editPs, setEditPs] = useState<PassengerRow | null>(null);
    const [editPsForm, setEditPsForm] = useState<PassengerEditForm>(defPsEdit);
    const [editPsSaving, setEditPsSaving] = useState(false);
    const [editPsMsg, setEditPsMsg] = useState<Msg | null>(null);

    const [loadings, setLoadings] = useState<LoadingRow[]>([]);
    const [lrForm, setLrForm] = useState<LoadingAddForm>(defLrForm);
    const [lrSaving, setLrSaving] = useState(false);
    const [lrMsg, setLrMsg] = useState<Msg | null>(null);
    const [editLr, setEditLr] = useState<LoadingRow | null>(null);
    const [editLrForm, setEditLrForm] = useState<LoadingEditForm>(defLrEdit);
    const [editLrSaving, setEditLrSaving] = useState(false);
    const [editLrMsg, setEditLrMsg] = useState<Msg | null>(null);

    const TABS: { id: Tab; label: string }[] = [
        { id: "company", label: "Insurance Company" },
        { id: "prem", label: "Premium Table" },
        { id: "third", label: "3rd Party Liabilities" },
        { id: "clause", label: "Clause" },
        { id: "driver", label: "P.A. - Driver" },
        { id: "passenger", label: "P.A. - Passenger" },
        { id: "loading", label: "Loading Rate" },
    ];

    useEffect(() => {
        if ((mode === "Edit" || mode === "View") && insCd0) {
            setLoading(true);
            api.get(`/MasterData/api/insurance/${insCd0}`)
                .then(r => setCompany({ ...defCompany, ...r.data }))
                .catch(() => setCompMsg({ type: "error", text: "Failed to load insurance data." }))
                .finally(() => setLoading(false));
        }
    }, [mode, insCd0]);

    useEffect(() => {
        if (mode === "Add") {
            api.get("/MasterData/api/insurance/next-code")
                .then(r => setCompany(c => ({ ...c, ins_cd: r.data.next_code || "" })))
                .catch(() => { });
        }
    }, [mode]);

    const loadOpts = useCallback(async () => {
        if (optLoadedRef.current) return;
        optLoadedRef.current = true;
        try {
            const r = await api.get("/MasterData/api/insurance/prem-options");
            setOpts({
                areas: r.data.areas || [],
                models: r.data.models || [],
                coverages: r.data.coverages || [],
                clauses: r.data.clauses || [],
            });
        } catch { optLoadedRef.current = false; }
    }, []);

    const loadPremiums = useCallback(async () => {
        if (!currentCd) return;
        try {
            const r = await api.get(`/MasterData/api/insurance/${currentCd}/premiums`);
            setPremiums(r.data.data || []);
        }
        catch { setPremMsg({ type: "error", text: "Failed to load premium data." }); }
    }, [currentCd]);

    const loadThirdParty = useCallback(async () => {
        if (!currentCd) return;
        try {
            const r = await api.get(`/MasterData/api/insurance/${currentCd}/third-party`);
            setThirdParty(r.data.data || []);
        }
        catch { setTpMsg({ type: "error", text: "Failed to load 3rd party data." }); }
    }, [currentCd]);

    const loadClauses = useCallback(async () => {
        if (!currentCd) return;
        try {
            const r = await api.get(`/MasterData/api/insurance/${currentCd}/clauses`);
            setClauses(r.data.data || []);
        }
        catch { setClMsg({ type: "error", text: "Failed to load clause data." }); }
    }, [currentCd]);

    const loadDrivers = useCallback(async () => {
        if (!currentCd) return;
        try {
            const r = await api.get(`/MasterData/api/insurance/${currentCd}/driver`);
            setDrivers(r.data.data || []);
        }
        catch { setDrMsg({ type: "error", text: "Failed to load driver data." }); }
    }, [currentCd]);

    const loadPassengers = useCallback(async () => {
        if (!currentCd) return;
        try {
            const r = await api.get(`/MasterData/api/insurance/${currentCd}/passenger`);
            setPassengers(r.data.data || []);
        }
        catch { setPsMsg({ type: "error", text: "Failed to load passenger data." }); }
    }, [currentCd]);

    const loadLoading = useCallback(async () => {
        if (!currentCd) return;
        try {
            const r = await api.get(`/MasterData/api/insurance/${currentCd}/loading`);
            setLoadings(r.data.data || []);
        }
        catch { setLrMsg({ type: "error", text: "Failed to load loading rate data." }); }
    }, [currentCd]);

    useEffect(() => {
        if (!currentCd) return;
        if (["prem", "third", "clause", "loading"].includes(activeTab)) loadOpts();
        if (activeTab === "prem") loadPremiums();
        if (activeTab === "third") loadThirdParty();
        if (activeTab === "clause") loadClauses();
        if (activeTab === "driver") loadDrivers();
        if (activeTab === "passenger") loadPassengers();
        if (activeTab === "loading") loadLoading();
    }, [activeTab, currentCd, loadOpts, loadPremiums, loadThirdParty, loadClauses, loadDrivers, loadPassengers, loadLoading]);

    const handleSaveCompany = async () => {
        setCompSaving(true); setCompMsg(null);
        try {
            if (mode === "Add") {
                const r = await api.post("/MasterData/api/insurance", company);
                if (r.data.success) {
                    setMode("Edit"); setCurrentCd(company.ins_cd);
                    setCompMsg({ type: "success", text: "Insurance saved successfully." });
                    navigate(`/insurance-entry?id=Edit&ins_cd=${company.ins_cd}&akses=${akses0}`, { replace: true });
                } else { setCompMsg({ type: "error", text: r.data.message || "Save failed." }); }
            } else {
                const r = await api.put(`/MasterData/api/insurance/${currentCd}`, company);
                setCompMsg(r.data.success
                    ? { type: "success", text: "Insurance updated successfully." }
                    : { type: "error", text: r.data.message || "Update failed." });
            }
        } catch (e: any) { setCompMsg({ type: "error", text: e.response?.data?.message || "An error occurred." }); }
        finally { setCompSaving(false); }
    };

    const handleAddPremium = async () => {
        setPremSaving(true); setPremMsg(null);
        try {
            const r = await api.post(`/MasterData/api/insurance/${currentCd}/premiums`, premForm);
            if (r.data.success) { setPremMsg({ type: "success", text: "Premium record added." }); setPremForm(defPremForm); loadPremiums(); }
            else { setPremMsg({ type: "error", text: r.data.message || "Save failed." }); }
        } catch { setPremMsg({ type: "error", text: "An error occurred." }); }
        finally { setPremSaving(false); }
    };

    const openEditPrem = (row: PremiumRow) => {
        setEditPrem(row);
        setEditPremForm({
            l_amount: row.l_amount, tlo_ar: row.tlo_ar, net_premi: row.net_premi,
            net_rec_new: row.net_rec_new, net_rec_used: row.net_rec_used, premi: row.premi
        });
        setEditPremMsg(null);
    };

    const handleUpdatePrem = async () => {
        if (!editPrem) return;
        setEditPremSaving(true); setEditPremMsg(null);
        try {
            const r = await api.put(`/MasterData/api/insurance/${currentCd}/premiums/${editPrem.ID}`, editPremForm);
            if (r.data.success) { setEditPremMsg({ type: "success", text: "Updated." }); loadPremiums(); setTimeout(() => setEditPrem(null), 700); }
            else { setEditPremMsg({ type: "error", text: r.data.message || "Update failed." }); }
        } catch { setEditPremMsg({ type: "error", text: "An error occurred." }); }
        finally { setEditPremSaving(false); }
    };

    const handleDeletePrem = async (row: PremiumRow) => {
        if (!window.confirm(`Delete premium for ${row.area_name} / ${row.model_nm}?`)) return;
        try { await api.delete(`/MasterData/api/insurance/${currentCd}/premiums/${row.ID}`); loadPremiums(); }
        catch { setPremMsg({ type: "error", text: "Delete failed." }); }
    };

    const handleAddTp = async () => {
        setTpSaving(true); setTpMsg(null);
        try {
            const r = await api.post(`/MasterData/api/insurance/${currentCd}/third-party`, tpForm);
            if (r.data.success) { setTpMsg({ type: "success", text: "Record added." }); setTpForm(defTpForm); loadThirdParty(); }
            else { setTpMsg({ type: "error", text: r.data.message || "Save failed." }); }
        } catch { setTpMsg({ type: "error", text: "An error occurred." }); }
        finally { setTpSaving(false); }
    };

    const openEditTp = (row: ThirdPartyRow) => {
        setEditTp(row);
        setEditTpForm({ tpl_amt: row.tpl_amt, tpl_fee: row.tpl_fee, tpl_fee2: row.tpl_fee2 });
        setEditTpMsg(null);
    };

    const handleUpdateTp = async () => {
        if (!editTp) return;
        setEditTpSaving(true); setEditTpMsg(null);
        try {
            const r = await api.put(`/MasterData/api/insurance/${currentCd}/third-party/${editTp.ID_INSTPL}`, editTpForm);
            if (r.data.success) { setEditTpMsg({ type: "success", text: "Updated." }); loadThirdParty(); setTimeout(() => setEditTp(null), 700); }
            else { setEditTpMsg({ type: "error", text: r.data.message || "Update failed." }); }
        } catch { setEditTpMsg({ type: "error", text: "An error occurred." }); }
        finally { setEditTpSaving(false); }
    };

    const handleDeleteTp = async (row: ThirdPartyRow) => {
        if (!window.confirm(`Delete 3rd party record for ${row.model_nm}?`)) return;
        try { await api.delete(`/MasterData/api/insurance/${currentCd}/third-party/${row.ID_INSTPL}`); loadThirdParty(); }
        catch { setTpMsg({ type: "error", text: "Delete failed." }); }
    };

    const handleAddClause = async () => {
        setClSaving(true); setClMsg(null);
        try {
            const r = await api.post(`/MasterData/api/insurance/${currentCd}/clauses`, clForm);
            if (r.data.success) { setClMsg({ type: "success", text: "Clause record added." }); setClForm(defClForm); loadClauses(); }
            else { setClMsg({ type: "error", text: r.data.message || "Save failed." }); }
        } catch { setClMsg({ type: "error", text: "An error occurred." }); }
        finally { setClSaving(false); }
    };

    const openEditCl = (row: ClauseRow) => {
        setEditCl(row);
        setEditClForm({
            net_premi: row.net_premi, net_rec_new: row.net_rec_new,
            net_rec_used: row.net_rec_used, premi: row.premi
        });
        setEditClMsg(null);
    };

    const handleUpdateCl = async () => {
        if (!editCl) return;
        setEditClSaving(true); setEditClMsg(null);
        try {
            const area = encodeURIComponent(editCl.insurance_area);
            const clause = encodeURIComponent(editCl.clause);
            const tlo = encodeURIComponent(editCl.tlo_ar);
            const r = await api.put(
                `/MasterData/api/insurance/${currentCd}/clauses/${area}/${clause}/${tlo}`,
                editClForm,
            );
            if (r.data.success) { setEditClMsg({ type: "success", text: "Updated." }); loadClauses(); setTimeout(() => setEditCl(null), 700); }
            else { setEditClMsg({ type: "error", text: r.data.message || "Update failed." }); }
        } catch { setEditClMsg({ type: "error", text: "An error occurred." }); }
        finally { setEditClSaving(false); }
    };

    const handleDeleteCl = async (row: ClauseRow) => {
        if (!window.confirm(`Delete clause ${row.clause_name} / ${row.tlo_name}?`)) return;
        try {
            const area = encodeURIComponent(row.insurance_area);
            const clause = encodeURIComponent(row.clause);
            const tlo = encodeURIComponent(row.tlo_ar);
            await api.delete(`/MasterData/api/insurance/${currentCd}/clauses/${area}/${clause}/${tlo}`);
            loadClauses();
        } catch { setClMsg({ type: "error", text: "Delete failed." }); }
    };

    const handleAddDr = async () => {
        setDrSaving(true); setDrMsg(null);
        try {
            const r = await api.post(`/MasterData/api/insurance/${currentCd}/driver`, drForm);
            if (r.data.success) { setDrMsg({ type: "success", text: "Record added." }); setDrForm(defDrForm); loadDrivers(); }
            else { setDrMsg({ type: "error", text: r.data.message || "Save failed." }); }
        } catch { setDrMsg({ type: "error", text: "An error occurred." }); }
        finally { setDrSaving(false); }
    };

    const openEditDr = (row: DriverRow) => {
        setEditDr(row);
        setEditDrForm({ driver_fee_ins: row.driver_fee_ins, driver_fee_cust: row.driver_fee_cust });
        setEditDrMsg(null);
    };

    const handleUpdateDr = async () => {
        if (!editDr) return;
        setEditDrSaving(true); setEditDrMsg(null);
        try {
            const pa = encodeURIComponent(editDr.pa_amount);
            const r = await api.put(`/MasterData/api/insurance/${currentCd}/driver/${pa}`, editDrForm);
            if (r.data.success) { setEditDrMsg({ type: "success", text: "Updated." }); loadDrivers(); setTimeout(() => setEditDr(null), 700); }
            else { setEditDrMsg({ type: "error", text: r.data.message || "Update failed." }); }
        } catch { setEditDrMsg({ type: "error", text: "An error occurred." }); }
        finally { setEditDrSaving(false); }
    };

    const handleDeleteDr = async (row: DriverRow) => {
        if (!window.confirm(`Delete PA driver record for amount ${parseInt(row.pa_amount).toLocaleString()}?`)) return;
        try {
            const pa = encodeURIComponent(row.pa_amount);
            await api.delete(`/MasterData/api/insurance/${currentCd}/driver/${pa}`);
            loadDrivers();
        } catch { setDrMsg({ type: "error", text: "Delete failed." }); }
    };

    const handleAddPs = async () => {
        setPsSaving(true); setPsMsg(null);
        try {
            const r = await api.post(`/MasterData/api/insurance/${currentCd}/passenger`, psForm);
            if (r.data.success) { setPsMsg({ type: "success", text: "Record added." }); setPsForm(defPsForm); loadPassengers(); }
            else { setPsMsg({ type: "error", text: r.data.message || "Save failed." }); }
        } catch { setPsMsg({ type: "error", text: "An error occurred." }); }
        finally { setPsSaving(false); }
    };

    const openEditPs = (row: PassengerRow) => {
        setEditPs(row);
        setEditPsForm({ seat_fee_ins: row.seat_fee_ins, seat_fee_cust: row.seat_fee_cust });
        setEditPsMsg(null);
    };
    
    const handleUpdatePs = async () => {
        if (!editPs) return;
        setEditPsSaving(true); setEditPsMsg(null);
        try {
            const sa = encodeURIComponent(editPs.seat_amount);
            const seat = encodeURIComponent(editPs.seat);
            const r = await api.put(
                `/MasterData/api/insurance/${currentCd}/passenger/${sa}/${seat}`, editPsForm);
            if (r.data.success) { setEditPsMsg({ type: "success", text: "Updated." }); loadPassengers(); setTimeout(() => setEditPs(null), 700); }
            else { setEditPsMsg({ type: "error", text: r.data.message || "Update failed." }); }
        } catch { setEditPsMsg({ type: "error", text: "An error occurred." }); }
        finally { setEditPsSaving(false); }
    };

    const handleDeletePs = async (row: PassengerRow) => {
        if (!window.confirm(`Delete PA passenger record: amount ${parseInt(row.seat_amount).toLocaleString()}, seat ${row.seat}?`)) return;
        try {
            const sa = encodeURIComponent(row.seat_amount);
            const seat = encodeURIComponent(row.seat);
            await api.delete(`/MasterData/api/insurance/${currentCd}/passenger/${sa}/${seat}`);
            loadPassengers();
        } catch { setPsMsg({ type: "error", text: "Delete failed." }); }
    };

    const handleAddLr = async () => {
        setLrSaving(true); setLrMsg(null);
        try {
            const r = await api.post(`/MasterData/api/insurance/${currentCd}/loading`, lrForm);
            if (r.data.success) { setLrMsg({ type: "success", text: "Record added." }); setLrForm(defLrForm); loadLoading(); }
            else { setLrMsg({ type: "error", text: r.data.message || "Save failed." }); }
        } catch { setLrMsg({ type: "error", text: "An error occurred." }); }
        finally { setLrSaving(false); }
    };

    const openEditLr = (row: LoadingRow) => {
        setEditLr(row);
        setEditLrForm({ lr_age: row.lr_age, lr_next: row.lr_next });
        setEditLrMsg(null);
    };

    const handleUpdateLr = async () => {
        if (!editLr) return;
        setEditLrSaving(true); setEditLrMsg(null);
        try {
            const r = await api.put(`/MasterData/api/insurance/${currentCd}/loading/${editLr.ID}`, editLrForm);
            if (r.data.success) { setEditLrMsg({ type: "success", text: "Updated." }); loadLoading(); setTimeout(() => setEditLr(null), 700); }
            else { setEditLrMsg({ type: "error", text: r.data.message || "Update failed." }); }
        } catch { setEditLrMsg({ type: "error", text: "An error occurred." }); }
        finally { setEditLrSaving(false); }
    };

    const handleDeleteLr = async (row: LoadingRow) => {
        if (!window.confirm(`Delete loading rate record for ${row.model_nm}?`)) return;
        try { await api.delete(`/MasterData/api/insurance/${currentCd}/loading/${row.ID}`); loadLoading(); }
        catch { setLrMsg({ type: "error", text: "Delete failed." }); }
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center">
                <div className="flex items-center gap-3 text-gray-500">
                    <svg className="animate-spin w-5 h-5 text-blue-500" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Loading…
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
            <div className="max-w-5xl mx-auto">
                <div className="flex items-center justify-between mb-4">
                    <div>
                        <h1 className="text-xl font-bold text-gray-800">
                            {mode === "Add" ? "Add Insurance" : `Insurance — ${currentCd}`}
                        </h1>
                        <p className="text-sm text-gray-500 mt-0.5">
                            {mode === "Add" ? "Create a new insurance record" : mode === "View" ? "View only" : canEdit ? "Edit mode" : "Read-only"}
                        </p>
                    </div>
                    <button onClick={() => navigate("/insurance")}
                        className="px-4 py-2 text-sm border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">
                        ← Back to List
                    </button>
                </div>

                <div className="rounded-2xl bg-white shadow-lg overflow-hidden">
                    <div className="flex border-b border-gray-200 bg-gray-50 overflow-x-auto">
                        {TABS.map(t => {
                            const disabled = t.id !== "company" && !mainSaved;
                            return (
                                <button key={t.id} disabled={disabled}
                                    onClick={() => !disabled && setActiveTab(t.id)}
                                    className={[
                                        "px-4 py-3 text-sm font-medium whitespace-nowrap transition-colors",
                                        activeTab === t.id
                                            ? "border-b-2 border-blue-600 text-blue-700 bg-white"
                                            : disabled
                                                ? "text-gray-300 cursor-not-allowed"
                                                : "text-gray-500 hover:text-gray-700 hover:bg-white",
                                    ].join(" ")}>
                                    {t.label}
                                </button>
                            );
                        })}
                    </div>

                    <div className="p-6">

                        {activeTab === "company" && (
                            <div className="max-w-xl space-y-4">
                                <h2 className="text-sm font-semibold text-gray-600 pb-2 border-b border-gray-100">Insurance Company</h2>
                                <Field label="Insurance Code">
                                    <input className={inp} readOnly value={company.ins_cd} style={{ fontFamily: "monospace" }} />
                                </Field>
                                <Field label="Insurance Company">
                                    <input className={inp} disabled={!canEdit} value={company.ins_co}
                                        onChange={e => setCompany(c => ({ ...c, ins_co: e.target.value }))} />
                                </Field>
                                <div className="grid grid-cols-2 gap-3">
                                    <Field label="Stamp Duty">
                                        <AmtInput value={company.stamp_duty} onChange={v => setCompany(c => ({ ...c, stamp_duty: v }))} />
                                    </Field>
                                    <Field label="Stamp Duty from Insurance">
                                        <AmtInput value={company.stamp_dutyins} onChange={v => setCompany(c => ({ ...c, stamp_dutyins: v }))} />
                                    </Field>
                                </div>
                                <Field label="Address">
                                    <input className={inp} disabled={!canEdit} value={company.address}
                                        onChange={e => setCompany(c => ({ ...c, address: e.target.value }))} />
                                </Field>
                                <div className="grid grid-cols-2 gap-3">
                                    <Field label="City">
                                        <input className={inp} disabled={!canEdit} value={company.city}
                                            onChange={e => setCompany(c => ({ ...c, city: e.target.value }))} />
                                    </Field>
                                    <Field label="Post Code">
                                        <input className={inp} disabled={!canEdit} maxLength={5} value={company.zipcode}
                                            onChange={e => setCompany(c => ({ ...c, zipcode: e.target.value.replace(/\D/g, "") }))} />
                                    </Field>
                                </div>
                                <div className="grid grid-cols-2 gap-3">
                                    <Field label="Telephone">
                                        <input className={inp} disabled={!canEdit} value={company.phone}
                                            onChange={e => setCompany(c => ({ ...c, phone: e.target.value }))} />
                                    </Field>
                                    <Field label="Fax">
                                        <input className={inp} disabled={!canEdit} value={company.fax}
                                            onChange={e => setCompany(c => ({ ...c, fax: e.target.value }))} />
                                    </Field>
                                </div>
                                <Field label="Contact">
                                    <input className={inp} disabled={!canEdit} value={company.contact}
                                        onChange={e => setCompany(c => ({ ...c, contact: e.target.value }))} />
                                </Field>
                                <div className="pt-2 flex gap-3">
                                    {canEdit && (
                                        <button onClick={handleSaveCompany} disabled={compSaving}
                                            className="px-5 py-2 text-sm rounded-lg font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-60 shadow-sm">
                                            {compSaving ? "Saving…" : mode === "Add" ? "Save" : "Update"}
                                        </button>
                                    )}
                                    <button onClick={() => navigate("/insurance")}
                                        className="px-4 py-2 text-sm border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">
                                        {canEdit ? "Cancel" : "Back"}
                                    </button>
                                </div>
                                {compMsg && <Banner msg={compMsg} onClose={() => setCompMsg(null)} />}
                            </div>
                        )}

                        {activeTab === "prem" && (
                            <div>
                                {canEdit && (
                                    <div className="mb-6 p-4 bg-gray-50 border border-gray-200 rounded-xl">
                                        <h3 className="text-sm font-semibold text-gray-600 mb-4">Add Premium Record</h3>
                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                            <Field label="Insurance Area *">
                                                <select className={sel} value={premForm.insurance_area}
                                                    onChange={e => setPremForm(f => ({ ...f, insurance_area: e.target.value }))}>
                                                    <option value="">Select…</option>
                                                    {opts.areas.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                                                </select>
                                            </Field>
                                            <Field label="Model *">
                                                <select className={sel} value={premForm.model}
                                                    onChange={e => setPremForm(f => ({ ...f, model: e.target.value }))}>
                                                    <option value="">Select…</option>
                                                    {opts.models.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                                                </select>
                                            </Field>
                                            <Field label="OTR">
                                                <AmtInput value={premForm.l_amount} onChange={v => setPremForm(f => ({ ...f, l_amount: v }))} />
                                            </Field>
                                            <Field label="Coverage Type *">
                                                <select className={sel} value={premForm.tlo_ar}
                                                    onChange={e => setPremForm(f => ({ ...f, tlo_ar: e.target.value }))}>
                                                    <option value="">Select…</option>
                                                    {opts.coverages.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                                                </select>
                                            </Field>
                                            <Field label="Net Premi (%)"><PctInput value={premForm.net_premi} onChange={v => setPremForm(f => ({ ...f, net_premi: v }))} /></Field>
                                            <Field label="Net Rec New (%)"><PctInput value={premForm.net_rec_new} onChange={v => setPremForm(f => ({ ...f, net_rec_new: v }))} /></Field>
                                            <Field label="Net Rec Used (%)"><PctInput value={premForm.net_rec_used} onChange={v => setPremForm(f => ({ ...f, net_rec_used: v }))} /></Field>
                                            <Field label="Premi (%)"><PctInput value={premForm.premi} onChange={v => setPremForm(f => ({ ...f, premi: v }))} /></Field>
                                        </div>
                                        <button onClick={handleAddPremium} disabled={premSaving}
                                            className="mt-4 px-5 py-2 text-sm rounded-lg font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-60 shadow-sm">
                                            {premSaving ? "Saving…" : "Save"}
                                        </button>
                                        {premMsg && <Banner msg={premMsg} onClose={() => setPremMsg(null)} />}
                                    </div>
                                )}
                                <SubTable
                                    headers={["Area", "Model", "OTR", "Coverage", "Net Premi", "Net Rec New", "Net Rec Used", "Premi", ...(canEdit ? ["Action"] : [])]}
                                    rows={premiums.map(r => [
                                        r.area_name, r.model_nm,
                                        <span className="tabular-nums">{parseInt(r.l_amount || "0").toLocaleString()}</span>,
                                        r.tlo_name, `${r.net_premi}%`, `${r.net_rec_new}%`, `${r.net_rec_used}%`, `${r.premi}%`,
                                        ...(canEdit ? [<><EditBtn onClick={() => openEditPrem(r)} /><DelBtn onClick={() => handleDeletePrem(r)} /></>] : [] as React.ReactNode[]),
                                    ])} />
                            </div>
                        )}

                        {activeTab === "third" && (
                            <div>
                                {canEdit && (
                                    <div className="mb-6 p-4 bg-gray-50 border border-gray-200 rounded-xl">
                                        <h3 className="text-sm font-semibold text-gray-600 mb-4">Add 3rd Party Record</h3>
                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                            <Field label="Model Name">
                                                <select className={sel} value={tpForm.model}
                                                    onChange={e => setTpForm(f => ({ ...f, model: e.target.value }))}>
                                                    <option value="">Select…</option>
                                                    {opts.models.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                                                </select>
                                            </Field>
                                            <Field label="TPL Amount">
                                                <AmtInput value={tpForm.tpl_amt} onChange={v => setTpForm(f => ({ ...f, tpl_amt: v }))} />
                                            </Field>
                                            <Field label="TPL Fee">
                                                <AmtInput value={tpForm.tpl_fee} onChange={v => setTpForm(f => ({ ...f, tpl_fee: v }))} suffix="/ Year" />
                                            </Field>
                                            <Field label="TPL Fee 2">
                                                <AmtInput value={tpForm.tpl_fee2} onChange={v => setTpForm(f => ({ ...f, tpl_fee2: v }))} suffix="/ Year" />
                                            </Field>
                                        </div>
                                        <button onClick={handleAddTp} disabled={tpSaving}
                                            className="mt-4 px-5 py-2 text-sm rounded-lg font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-60 shadow-sm">
                                            {tpSaving ? "Saving…" : "Save"}
                                        </button>
                                        {tpMsg && <Banner msg={tpMsg} onClose={() => setTpMsg(null)} />}
                                    </div>
                                )}
                                <SubTable
                                    headers={["Model", "TPL Amount", "TPL Fee", "TPL Fee 2", ...(canEdit ? ["Action"] : [])]}
                                    rows={thirdParty.map(r => [
                                        r.model_nm,
                                        <span className="tabular-nums">{parseInt(r.tpl_amt || "0").toLocaleString()}</span>,
                                        <span className="tabular-nums">{parseInt(r.tpl_fee || "0").toLocaleString()}</span>,
                                        <span className="tabular-nums">{parseInt(r.tpl_fee2 || "0").toLocaleString()}</span>,
                                        ...(canEdit ? [<><EditBtn onClick={() => openEditTp(r)} /><DelBtn onClick={() => handleDeleteTp(r)} /></>] : [] as React.ReactNode[]),
                                    ])} />
                            </div>
                        )}

                        {activeTab === "clause" && (
                            <div>
                                {canEdit && (
                                    <div className="mb-6 p-4 bg-gray-50 border border-gray-200 rounded-xl">
                                        <h3 className="text-sm font-semibold text-gray-600 mb-4">Add Clause Record</h3>
                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                            <Field label="Insurance Area">
                                                <select className={sel} value={clForm.insurance_area}
                                                    onChange={e => setClForm(f => ({ ...f, insurance_area: e.target.value }))}>
                                                    <option value="">Select…</option>
                                                    {opts.areas.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                                                </select>
                                            </Field>
                                            <Field label="Clause">
                                                <select className={sel} value={clForm.clause}
                                                    onChange={e => setClForm(f => ({ ...f, clause: e.target.value }))}>
                                                    <option value="">Select…</option>
                                                    {opts.clauses.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                                                </select>
                                            </Field>
                                            <Field label="Coverage Type">
                                                <select className={sel} value={clForm.tlo_ar}
                                                    onChange={e => setClForm(f => ({ ...f, tlo_ar: e.target.value }))}>
                                                    <option value="">Select…</option>
                                                    {opts.coverages.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                                                </select>
                                            </Field>
                                            <Field label="Net Premi (%)"><PctInput value={clForm.net_premi} onChange={v => setClForm(f => ({ ...f, net_premi: v }))} /></Field>
                                            <Field label="Net Rec New (%)"><PctInput value={clForm.net_rec_new} onChange={v => setClForm(f => ({ ...f, net_rec_new: v }))} /></Field>
                                            <Field label="Net Rec Used (%)"><PctInput value={clForm.net_rec_used} onChange={v => setClForm(f => ({ ...f, net_rec_used: v }))} /></Field>
                                            <Field label="Premi (%)"><PctInput value={clForm.premi} onChange={v => setClForm(f => ({ ...f, premi: v }))} /></Field>
                                        </div>
                                        <button onClick={handleAddClause} disabled={clSaving}
                                            className="mt-4 px-5 py-2 text-sm rounded-lg font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-60 shadow-sm">
                                            {clSaving ? "Saving…" : "Save"}
                                        </button>
                                        {clMsg && <Banner msg={clMsg} onClose={() => setClMsg(null)} />}
                                    </div>
                                )}
                                <SubTable
                                    headers={["Area", "Clause", "Coverage", "Net Premi", "Net Rec New", "Net Rec Used", "Premi", ...(canEdit ? ["Action"] : [])]}
                                    rows={clauses.map(r => [
                                        r.area_name, r.clause_name, r.tlo_name,
                                        `${r.net_premi}%`, `${r.net_rec_new}%`, `${r.net_rec_used}%`, `${r.premi}%`,
                                        ...(canEdit ? [<><EditBtn onClick={() => openEditCl(r)} /><DelBtn onClick={() => handleDeleteCl(r)} /></>] : [] as React.ReactNode[]),
                                    ])} />
                            </div>
                        )}

                        {activeTab === "driver" && (
                            <div>
                                {canEdit && (
                                    <div className="mb-6 p-4 bg-gray-50 border border-gray-200 rounded-xl">
                                        <h3 className="text-sm font-semibold text-gray-600 mb-4">Add P.A. Driver Record</h3>
                                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                                            <Field label="PA Amount">
                                                <AmtInput value={drForm.pa_amount} onChange={v => setDrForm(f => ({ ...f, pa_amount: v }))} />
                                            </Field>
                                            <Field label="Driver Fee from Insurance">
                                                <AmtInput value={drForm.driver_fee_ins} onChange={v => setDrForm(f => ({ ...f, driver_fee_ins: v }))} />
                                            </Field>
                                            <Field label="Driver Fee for Customer">
                                                <AmtInput value={drForm.driver_fee_cust} onChange={v => setDrForm(f => ({ ...f, driver_fee_cust: v }))} />
                                            </Field>
                                        </div>
                                        <button onClick={handleAddDr} disabled={drSaving}
                                            className="mt-4 px-5 py-2 text-sm rounded-lg font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-60 shadow-sm">
                                            {drSaving ? "Saving…" : "Save"}
                                        </button>
                                        {drMsg && <Banner msg={drMsg} onClose={() => setDrMsg(null)} />}
                                    </div>
                                )}
                                <SubTable
                                    headers={["PA Amount", "Driver Fee from Insurance", "Driver Fee for Customer", ...(canEdit ? ["Action"] : [])]}
                                    rows={drivers.map(r => [
                                        <span className="tabular-nums">{parseInt(r.pa_amount || "0").toLocaleString()}</span>,
                                        <span className="tabular-nums">{parseInt(r.driver_fee_ins || "0").toLocaleString()}</span>,
                                        <span className="tabular-nums">{parseInt(r.driver_fee_cust || "0").toLocaleString()}</span>,
                                        ...(canEdit ? [<><EditBtn onClick={() => openEditDr(r)} /><DelBtn onClick={() => handleDeleteDr(r)} /></>] : [] as React.ReactNode[]),
                                    ])} />
                            </div>
                        )}

                        {activeTab === "passenger" && (
                            <div>
                                {canEdit && (
                                    <div className="mb-6 p-4 bg-gray-50 border border-gray-200 rounded-xl">
                                        <h3 className="text-sm font-semibold text-gray-600 mb-4">Add P.A. Passenger Record</h3>
                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                            <Field label="Seat Amount">
                                                <AmtInput value={psForm.seat_amount} onChange={v => setPsForm(f => ({ ...f, seat_amount: v }))} />
                                            </Field>
                                            <Field label="Seat">
                                                <input className={inp} value={psForm.seat}
                                                    onChange={e => setPsForm(f => ({ ...f, seat: e.target.value.replace(/\D/g, "") }))}
                                                    style={{ textAlign: "right" }} />
                                            </Field>
                                            <Field label="Fee from Insurance">
                                                <AmtInput value={psForm.seat_fee_ins} onChange={v => setPsForm(f => ({ ...f, seat_fee_ins: v }))} />
                                            </Field>
                                            <Field label="Fee for Customer">
                                                <AmtInput value={psForm.seat_fee_cust} onChange={v => setPsForm(f => ({ ...f, seat_fee_cust: v }))} />
                                            </Field>
                                        </div>
                                        <button onClick={handleAddPs} disabled={psSaving}
                                            className="mt-4 px-5 py-2 text-sm rounded-lg font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-60 shadow-sm">
                                            {psSaving ? "Saving…" : "Save"}
                                        </button>
                                        {psMsg && <Banner msg={psMsg} onClose={() => setPsMsg(null)} />}
                                    </div>
                                )}
                                <SubTable
                                    headers={["Seat Amount", "Seat", "Fee from Insurance", "Fee for Customer", ...(canEdit ? ["Action"] : [])]}
                                    rows={passengers.map(r => [
                                        <span className="tabular-nums">{parseInt(r.seat_amount || "0").toLocaleString()}</span>,
                                        <span className="tabular-nums">{r.seat}</span>,
                                        <span className="tabular-nums">{parseInt(r.seat_fee_ins || "0").toLocaleString()}</span>,
                                        <span className="tabular-nums">{parseInt(r.seat_fee_cust || "0").toLocaleString()}</span>,
                                        ...(canEdit ? [<><EditBtn onClick={() => openEditPs(r)} /><DelBtn onClick={() => handleDeletePs(r)} /></>] : [] as React.ReactNode[]),
                                    ])} />
                            </div>
                        )}

                        {activeTab === "loading" && (
                            <div>
                                {canEdit && (
                                    <div className="mb-6 p-4 bg-gray-50 border border-gray-200 rounded-xl">
                                        <h3 className="text-sm font-semibold text-gray-600 mb-4">Add Loading Rate Record</h3>
                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                            <Field label="Model Name">
                                                <select className={sel} value={lrForm.model}
                                                    onChange={e => setLrForm(f => ({ ...f, model: e.target.value }))}>
                                                    <option value="">Select…</option>
                                                    {opts.models.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                                                </select>
                                            </Field>
                                            <Field label="Loading Rate Age">
                                                <input className={`${inp} text-right`} value={lrForm.lr_age}
                                                    onChange={e => setLrForm(f => ({ ...f, lr_age: e.target.value.replace(/\D/g, "") }))} />
                                            </Field>
                                        </div>
                                        <label className="flex items-center gap-2 mt-3 cursor-pointer">
                                            <input type="checkbox" checked={lrForm.lr_next}
                                                onChange={e => setLrForm(f => ({ ...f, lr_next: e.target.checked }))}
                                                className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
                                            <span className="text-sm text-gray-700">Next Year</span>
                                        </label>
                                        <button onClick={handleAddLr} disabled={lrSaving}
                                            className="mt-4 px-5 py-2 text-sm rounded-lg font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-60 shadow-sm">
                                            {lrSaving ? "Saving…" : "Save"}
                                        </button>
                                        {lrMsg && <Banner msg={lrMsg} onClose={() => setLrMsg(null)} />}
                                    </div>
                                )}
                                <SubTable
                                    headers={["Model Name", "Loading Rate Age", "Next Year", ...(canEdit ? ["Action"] : [])]}
                                    rows={loadings.map(r => [
                                        r.model_nm,
                                        <span className="tabular-nums text-right block">{r.lr_age}</span>,
                                        <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-semibold ${r.lr_next ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                                            {r.lr_next ? "Yes" : "No"}
                                        </span>,
                                        ...(canEdit ? [<><EditBtn onClick={() => openEditLr(r)} /><DelBtn onClick={() => handleDeleteLr(r)} /></>] : [] as React.ReactNode[]),
                                    ])} />
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {editPrem && (
                <Modal title="Edit Premium Record" onClose={() => setEditPrem(null)}
                    onSave={handleUpdatePrem} saving={editPremSaving}
                    msg={editPremMsg} onMsgClose={() => setEditPremMsg(null)}>
                    <div className="grid grid-cols-2 gap-3">
                        <Field label="Insurance Area"><input className={inp} readOnly value={editPrem.area_name} /></Field>
                        <Field label="Model"><input className={inp} readOnly value={editPrem.model_nm} /></Field>
                    </div>
                    <Field label="OTR">
                        <AmtInput value={editPremForm.l_amount || ""} onChange={v => setEditPremForm(f => ({ ...f, l_amount: v }))} />
                    </Field>
                    <Field label="Coverage Type">
                        <select className={sel} value={editPremForm.tlo_ar || ""}
                            onChange={e => setEditPremForm(f => ({ ...f, tlo_ar: e.target.value }))}>
                            <option value="">Select…</option>
                            {opts.coverages.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                        </select>
                    </Field>
                    <Field label="Net Premi (%)"><PctInput value={editPremForm.net_premi || ""} onChange={v => setEditPremForm(f => ({ ...f, net_premi: v }))} /></Field>
                    <Field label="Net Rec New (%)"><PctInput value={editPremForm.net_rec_new || ""} onChange={v => setEditPremForm(f => ({ ...f, net_rec_new: v }))} /></Field>
                    <Field label="Net Rec Used (%)"><PctInput value={editPremForm.net_rec_used || ""} onChange={v => setEditPremForm(f => ({ ...f, net_rec_used: v }))} /></Field>
                    <Field label="Premi (%)"><PctInput value={editPremForm.premi || ""} onChange={v => setEditPremForm(f => ({ ...f, premi: v }))} /></Field>
                </Modal>
            )}

            {editTp && (
                <Modal title="Edit 3rd Party Record" onClose={() => setEditTp(null)}
                    onSave={handleUpdateTp} saving={editTpSaving}
                    msg={editTpMsg} onMsgClose={() => setEditTpMsg(null)}>
                    <Field label="Model Name"><input className={inp} readOnly value={editTp.model_nm} /></Field>
                    <Field label="TPL Amount">
                        <AmtInput value={editTpForm.tpl_amt || ""} onChange={v => setEditTpForm(f => ({ ...f, tpl_amt: v }))} />
                    </Field>
                    <Field label="TPL Fee">
                        <AmtInput value={editTpForm.tpl_fee || ""} onChange={v => setEditTpForm(f => ({ ...f, tpl_fee: v }))} suffix="/ Year" />
                    </Field>
                    <Field label="TPL Fee 2">
                        <AmtInput value={editTpForm.tpl_fee2 || ""} onChange={v => setEditTpForm(f => ({ ...f, tpl_fee2: v }))} suffix="/ Year" />
                    </Field>
                </Modal>
            )}

            {editCl && (
                <Modal title="Edit Clause Record" onClose={() => setEditCl(null)}
                    onSave={handleUpdateCl} saving={editClSaving}
                    msg={editClMsg} onMsgClose={() => setEditClMsg(null)}>
                    <div className="grid grid-cols-2 gap-3">
                        <Field label="Insurance Area"><input className={inp} readOnly value={editCl.area_name} /></Field>
                        <Field label="Clause"><input className={inp} readOnly value={editCl.clause_name} /></Field>
                    </div>
                    <Field label="Coverage Type"><input className={inp} readOnly value={editCl.tlo_name} /></Field>
                    <Field label="Net Premi (%)"><PctInput value={editClForm.net_premi} onChange={v => setEditClForm(f => ({ ...f, net_premi: v }))} /></Field>
                    <Field label="Net Rec New (%)"><PctInput value={editClForm.net_rec_new} onChange={v => setEditClForm(f => ({ ...f, net_rec_new: v }))} /></Field>
                    <Field label="Net Rec Used (%)"><PctInput value={editClForm.net_rec_used} onChange={v => setEditClForm(f => ({ ...f, net_rec_used: v }))} /></Field>
                    <Field label="Premi (%)"><PctInput value={editClForm.premi} onChange={v => setEditClForm(f => ({ ...f, premi: v }))} /></Field>
                </Modal>
            )}

            {editDr && (
                <Modal title="Edit P.A. Driver Record" onClose={() => setEditDr(null)}
                    onSave={handleUpdateDr} saving={editDrSaving}
                    msg={editDrMsg} onMsgClose={() => setEditDrMsg(null)}>
                    <Field label="PA Amount">
                        <input className={inp} readOnly
                            value={parseInt(editDr.pa_amount || "0").toLocaleString()}
                            style={{ textAlign: "right" }} />
                    </Field>
                    <Field label="Driver Fee from Insurance">
                        <AmtInput value={editDrForm.driver_fee_ins}
                            onChange={v => setEditDrForm(f => ({ ...f, driver_fee_ins: v }))} />
                    </Field>
                    <Field label="Driver Fee for Customer">
                        <AmtInput value={editDrForm.driver_fee_cust}
                            onChange={v => setEditDrForm(f => ({ ...f, driver_fee_cust: v }))} />
                    </Field>
                </Modal>
            )}

            {editPs && (
                <Modal title="Edit P.A. Passenger Record" onClose={() => setEditPs(null)}
                    onSave={handleUpdatePs} saving={editPsSaving}
                    msg={editPsMsg} onMsgClose={() => setEditPsMsg(null)}>
                    <div className="grid grid-cols-2 gap-3">
                        <Field label="Seat Amount">
                            <input className={inp} readOnly
                                value={parseInt(editPs.seat_amount || "0").toLocaleString()}
                                style={{ textAlign: "right" }} />
                        </Field>
                        <Field label="Seat">
                            <input className={inp} readOnly value={editPs.seat} style={{ textAlign: "right" }} />
                        </Field>
                    </div>
                    <Field label="Fee from Insurance">
                        <AmtInput value={editPsForm.seat_fee_ins}
                            onChange={v => setEditPsForm(f => ({ ...f, seat_fee_ins: v }))} />
                    </Field>
                    <Field label="Fee for Customer">
                        <AmtInput value={editPsForm.seat_fee_cust}
                            onChange={v => setEditPsForm(f => ({ ...f, seat_fee_cust: v }))} />
                    </Field>
                </Modal>
            )}

            {editLr && (
                <Modal title="Edit Loading Rate Record" onClose={() => setEditLr(null)}
                    onSave={handleUpdateLr} saving={editLrSaving}
                    msg={editLrMsg} onMsgClose={() => setEditLrMsg(null)}>
                    <Field label="Model Name">
                        <input className={inp} readOnly value={editLr.model_nm} />
                    </Field>
                    <Field label="Loading Rate Age">
                        <input className={`${inp} text-right`} value={editLrForm.lr_age}
                            onChange={e => setEditLrForm(f => ({ ...f, lr_age: e.target.value.replace(/\D/g, "") }))} />
                    </Field>
                    <label className="flex items-center gap-2 cursor-pointer">
                        <input type="checkbox" checked={editLrForm.lr_next}
                            onChange={e => setEditLrForm(f => ({ ...f, lr_next: e.target.checked }))}
                            className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
                        <span className="text-sm text-gray-700">Next Year</span>
                    </label>
                </Modal>
            )}
        </div>
    );
};

export default InsuranceEntryPage;