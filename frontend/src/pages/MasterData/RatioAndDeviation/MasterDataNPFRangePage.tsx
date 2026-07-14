import React, { useEffect, useState, useCallback } from "react";
import api from "../../../api/axiosInstance";

interface ComboOption { value: string; desc_value: string; }

interface RangeRow {
    id: number;
    imp_date: string;
    imp_date_raw: string;
    actual: string;
    actual_desc: string;
    rangefrom: string;
    rangeto: string;
    multiguna: string;
    investasi: string;
    can_edit: boolean;
}

interface FormState {
    id: number | null;
    imp_date: string;
    threshold: string;
    rangefrom: string;
    rangeto: string;
    multi: string;
    inves: string;
}

const EMPTY_FORM: FormState = {
    id: null, imp_date: "", threshold: "",
    rangefrom: "", rangeto: "", multi: "", inves: "",
};

const allowAmountAndDot = (value: string) => /^\d*\.?\d{0,2}$/.test(value);

const blockNonNumericKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!/[0-9.]/.test(e.key) && e.key !== "Backspace" && e.key !== "Delete" && e.key !== "Tab" && !e.key.startsWith("Arrow")) {
        e.preventDefault();
    }
};

const MasterNpfRangePage: React.FC = () => {
    const [rows, setRows] = useState<RangeRow[]>([]);
    const [thresOpts, setThresOpts] = useState<ComboOption[]>([]);
    const [updateFullname, setUpdateFullname] = useState("");
    const [updateDate, setUpdateDate] = useState("");

    const [listLoading, setListLoading] = useState(true);
    const [listError, setListError] = useState<string | null>(null);

    const [modalOpen, setModalOpen] = useState(false);
    const [isEdit, setIsEdit] = useState(false);
    const [form, setForm] = useState<FormState>(EMPTY_FORM);
    const [loading, setLoading] = useState(false);
    const [saveMsg, setSaveMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

    const loadOptions = useCallback(() => {
        api.get("/MasterData/api/npf-range/options")
            .then(res => {
                setThresOpts(res.data.threshold || []);
            })
            .catch(err => {
                console.error("Options load error:", err);
            });
    }, []);

    const loadList = useCallback(() => {
        setListLoading(true);
        api.get("/MasterData/api/npf-range/list")
            .then(res => {
                const data = res.data;
                if (Array.isArray(data)) {
                    setRows(data);
                    setListError(null);
                } else {
                    setRows([]);
                    setListError(data?.error || "Unexpected response from server");
                }
            })
            .catch(err => {
                console.error("List load error:", err);
                setRows([]);
                setListError(err.response?.data?.error || err.message || "Failed to load data");
            })
            .finally(() => setListLoading(false));
    }, []);

    const loadLastUpdate = useCallback(() => {
        api.get("/MasterData/api/npf-range/last-update")
            .then(res => {
                setUpdateFullname(res.data.fullname || "");
                setUpdateDate(res.data.update_date || "");
            })
            .catch(err => {
                console.error("Last update load error:", err);
            });
    }, []);

    useEffect(() => {
        loadOptions();
        loadList();
        loadLastUpdate();
    }, [loadOptions, loadList, loadLastUpdate]);

    const handleOpenAdd = () => {
        setForm(EMPTY_FORM);
        setIsEdit(false);
        setSaveMsg(null);
        setModalOpen(true);
    };

    const handleOpenEdit = async (id: number) => {
        try {
            const res = await api.get(`/MasterData/api/npf-range/${id}`);
            const d = res.data;
            setForm({
                id: d.id,
                imp_date: d.imp_date,
                threshold: String(d.threshold),
                rangefrom: String(d.rangefrom),
                rangeto: String(d.rangeto),
                multi: String(d.multiguna),
                inves: String(d.investasi),
            });
            setIsEdit(true);
            setSaveMsg(null);
            setModalOpen(true);
        } catch (err) {
            console.error("Get record error:", err);
            alert("Failed to load record");
        }
    };

    const handleDelete = async (id: number) => {
        if (!window.confirm("Are you sure to delete this record?!")) return;
        try {
            await api.delete(`/MasterData/api/npf-range/${id}`);
            alert("Deleted sucess!");
            loadList();
            loadLastUpdate();
        } catch (err) {
            console.error("Delete error:", err);
            alert("Failed!");
        }
    };

    const handleSave = async () => {
        const { imp_date, threshold, rangefrom, rangeto, multi, inves } = form;
        if (!imp_date || !threshold || !rangefrom || !rangeto || !multi || !inves) {
            setSaveMsg({ type: "error", text: "Lengkapi data terlebih dahulu" });
            return;
        }

        setLoading(true);
        setSaveMsg(null);
        try {
            const payload = { imp_date, threshold, rangefrom, rangeto, multi, inves };
            if (isEdit && form.id) {
                await api.put(`/MasterData/api/npf-range/${form.id}`, payload);
                setSaveMsg({ type: "success", text: "Data berhasil di update" });
            } else {
                await api.post("/MasterData/api/npf-range", payload);
                setSaveMsg({ type: "success", text: "Data berhasil disimpan" });
            }
            loadList();
            loadLastUpdate();
            setTimeout(() => setModalOpen(false), 800);
        } catch (err: any) {
            console.error("Save error:", err);
            setSaveMsg({
                type: "error",
                text: err.response?.data?.error || (isEdit ? "Data gagal di update" : "Data gagal disimpan"),
            });
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
            <div className="max-w-4xl mx-auto">
                <div className="bg-white rounded-2xl shadow-lg p-6">

                    <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
                        <div>
                            <h1 className="text-2xl md:text-3xl font-bold text-gray-800">
                                Master NPF Range for Minimum DP <span className="text-gray-400 text-base font-normal">(Base on POJK)</span>
                            </h1>
                        </div>
                        <div className="text-right text-sm text-gray-500">
                            <p>Last Update: <span className="font-medium text-gray-700">{updateDate}</span></p>
                            <p>Update By: <span className="font-medium text-gray-700">{updateFullname}</span></p>
                        </div>
                    </div>

                    <button
                        onClick={handleOpenAdd}
                        className="mb-4 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center gap-2"
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
                        </svg>
                        Add
                    </button>

                    <div className="overflow-x-auto border border-gray-200 rounded-lg">
                        <table className="w-full text-sm">
                            <thead className="bg-blue-900 text-white">
                                <tr>
                                    <th rowSpan={2} className="border border-blue-800 px-3 py-2">Implementation Date</th>
                                    <th rowSpan={2} className="border border-blue-800 px-3 py-2">Tingkat Kesehatan Keuangan</th>
                                    <th rowSpan={2} className="border border-blue-800 px-3 py-2">NPF Range</th>
                                    <th colSpan={2} className="border border-blue-800 px-3 py-2">Minimum DP</th>
                                    <th rowSpan={2} className="border border-blue-800 px-3 py-2">&nbsp;</th>
                                </tr>
                                <tr>
                                    <th className="border border-blue-800 px-3 py-2">Multiguna</th>
                                    <th className="border border-blue-800 px-3 py-2">Investasi</th>
                                </tr>
                            </thead>
                            <tbody>
                                {listLoading ? (
                                    <tr><td colSpan={6} className="text-center py-6 text-gray-400">Loading...</td></tr>
                                ) : listError ? (
                                    <tr><td colSpan={6} className="text-center py-6 text-red-500">{listError}</td></tr>
                                ) : rows.length === 0 ? (
                                    <tr><td colSpan={6} className="text-center py-6 text-gray-400">No data</td></tr>
                                ) : rows.map(r => (
                                    <tr key={r.id} className="text-center hover:bg-gray-50">
                                        <td className="border border-gray-200 px-3 py-2">{r.imp_date}</td>
                                        <td className="border border-gray-200 px-3 py-2">{r.actual_desc}</td>
                                        <td className="border border-gray-200 px-3 py-2">{r.rangefrom} % s/d {r.rangeto} %</td>
                                        <td className="border border-gray-200 px-3 py-2">{r.multiguna} %</td>
                                        <td className="border border-gray-200 px-3 py-2">{r.investasi} %</td>
                                        <td className="border border-gray-200 px-3 py-2">
                                            {r.can_edit ? (
                                                <div className="flex justify-center gap-2">
                                                    <button onClick={() => handleOpenEdit(r.id)} className="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200">Edit</button>
                                                    <button onClick={() => handleDelete(r.id)} className="px-2 py-1 text-xs bg-red-100 text-red-700 rounded hover:bg-red-200">Delete</button>
                                                </div>
                                            ) : "-"}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                </div>
            </div>

            {modalOpen && (
                <div
                    className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
                    onClick={e => { if (e.target === e.currentTarget) setModalOpen(false); }}
                >
                    <div className="bg-white rounded-2xl shadow-2xl w-full max-w-xl mx-4 overflow-hidden">

                        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-gray-50">
                            <h2 className="text-lg font-bold text-gray-800">{isEdit ? "Edit" : "Add New"}</h2>
                            <button onClick={() => setModalOpen(false)} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">&times;</button>
                        </div>

                        <div className="px-6 py-5 space-y-4">

                            <div className="grid grid-cols-2 gap-6">
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Implementation Date</label>
                                    <input
                                        type="date"
                                        value={form.imp_date}
                                        onChange={e => setForm(f => ({ ...f, imp_date: e.target.value }))}
                                        className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500"
                                    />
                                </div>

                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Tingkat Kesehatan Keuangan</label>
                                    <select
                                        value={form.threshold}
                                        onChange={e => setForm(f => ({ ...f, threshold: e.target.value }))}
                                        className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 bg-white"
                                    >
                                        <option value="">Select</option>
                                        {thresOpts.map(o => <option key={o.value} value={o.value}>{o.desc_value}</option>)}
                                    </select>
                                </div>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">NPF Range</label>
                                <div className="flex items-center gap-2">
                                    <input
                                        type="text"
                                        value={form.rangefrom}
                                        onKeyDown={blockNonNumericKey}
                                        onChange={e => allowAmountAndDot(e.target.value) && setForm(f => ({ ...f, rangefrom: e.target.value }))}
                                        className="w-40 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500"
                                    />
                                    <span className="text-sm text-gray-500">% s/d</span>
                                    <input
                                        type="text"
                                        value={form.rangeto}
                                        onKeyDown={blockNonNumericKey}
                                        onChange={e => allowAmountAndDot(e.target.value) && setForm(f => ({ ...f, rangeto: e.target.value }))}
                                        className="w-40 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500"
                                    />
                                    <span className="text-sm text-gray-500">%</span>
                                </div>
                            </div>

                            <div className="border-t border-gray-100 pt-3">
                                <p className="text-sm font-bold text-gray-700 mb-2 text-center">Minimum DP</p>
                                <div className="grid grid-cols-2 gap-6">
                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 mb-1">Multiguna</label>
                                        <div className="flex items-center gap-1">
                                            <input
                                                type="text"
                                                value={form.multi}
                                                onKeyDown={blockNonNumericKey}
                                                onChange={e => allowAmountAndDot(e.target.value) && setForm(f => ({ ...f, multi: e.target.value }))}
                                                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500"
                                            />
                                            <span className="text-sm text-gray-500">%</span>
                                        </div>
                                    </div>
                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 mb-1">Investasi</label>
                                        <div className="flex items-center gap-1">
                                            <input
                                                type="text"
                                                value={form.inves}
                                                onKeyDown={blockNonNumericKey}
                                                onChange={e => allowAmountAndDot(e.target.value) && setForm(f => ({ ...f, inves: e.target.value }))}
                                                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500"
                                            />
                                            <span className="text-sm text-gray-500">%</span>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {saveMsg && (
                                <div className={`p-3 rounded-lg text-sm ${saveMsg.type === "success"
                                    ? "bg-green-50 border border-green-200 text-green-700"
                                    : "bg-red-50 border border-red-200 text-red-700"}`}>
                                    {saveMsg.text}
                                </div>
                            )}
                        </div>

                        <div className="px-6 py-4 border-t border-gray-200 bg-gray-50 flex justify-end gap-3">
                            <button onClick={() => setModalOpen(false)} className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-100 text-sm font-medium">
                                Close
                            </button>
                            <button onClick={handleSave} disabled={loading} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium disabled:opacity-50">
                                {loading ? "Saving…" : isEdit ? "Update" : "Save"}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default MasterNpfRangePage;