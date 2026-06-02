import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";

interface MenuRight {
    menu_id:   string;
    menu_desc: string;
    userright: number;
}

const USER_RIGHT_OPTIONS = [
    { value: 0, label: "None" },
    { value: 1, label: "View" },
    { value: 3, label: "Add & Edit" },
    { value: 7, label: "Delete" },
    { value: 9, label: "Full" },
];

const RIGHT_BADGE: Record<number, string> = {
    0: "bg-gray-100 text-gray-500",
    1: "bg-blue-100 text-blue-700",
    3: "bg-yellow-100 text-yellow-700",
    7: "bg-orange-100 text-orange-700",
    9: "bg-green-100 text-green-700",
};

const API_URL = import.meta.env.VITE_API_URL;

const UserAccessPage: React.FC = () => {
    // --- dropdown ---
    const [accessOptions, setAccessOptions] = useState<string[]>([]);
    const [accesscam, setAccesscam]         = useState("");

    // --- table ---
    const [menuRights, setMenuRights] = useState<MenuRight[]>([]);
    const [akses, setAkses]           = useState("");
    const [loading, setLoading]       = useState(false);
    const [error, setError]           = useState<string | null>(null);

    // --- save ---
    const [saveLoading, setSaveLoading] = useState(false);
    const [saveMessage, setSaveMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

    // --- fetch access level dropdown ---
    useEffect(() => {
        const fetchOptions = async () => {
            try {
                const res = await axios.get(`${API_URL}/SystemAdmin/api/uacc/access-options`);
                setAccessOptions(res.data.data);
            } catch {
                // non-critical
            }
        };
        fetchOptions();
    }, []);

    // --- fetch menu rights when accesscam changes ---
    const fetchMenuRights = useCallback(async () => {
        if (!accesscam) { setMenuRights([]); return; }
        setLoading(true);
        setError(null);
        setSaveMessage(null);
        try {
            const res = await axios.get(`${API_URL}/SystemAdmin/api/uacc/menu-rights`, {
                params: { accesscam },
                timeout: 10000,
            });
            setMenuRights(res.data.data);
            setAkses(res.data.akses);
        } catch {
            setError("Failed to load menu rights. Please try again.");
        } finally {
            setLoading(false);
        }
    }, [accesscam]);

    useEffect(() => { fetchMenuRights(); }, [fetchMenuRights]);

    // --- update a single row's userright locally ---
    const handleRightChange = (menu_id: string, value: number) => {
        setMenuRights((prev) =>
            prev.map((r) => r.menu_id === menu_id ? { ...r, userright: value } : r)
        );
    };

    // --- save all ---
    const handleSave = async () => {
        if (!accesscam) {
            setSaveMessage({ type: "error", text: "Please select Access Level" });
            return;
        }
        setSaveLoading(true);
        setSaveMessage(null);
        try {
            await axios.post(`${API_URL}/SystemAdmin/api/uacc/save`, {
                accesscam,
                rights: menuRights.map((r) => ({
                    menu_id:   r.menu_id,
                    userright: r.userright,
                })),
            });
            setSaveMessage({ type: "success", text: "Successful" });
        } catch (err: any) {
            const msgs = err.response?.data?.message;
            setSaveMessage({
                type: "error",
                text: Array.isArray(msgs) ? msgs.join(", ") : "Failed",
            });
        } finally {
            setSaveLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
            <div className="max-w-5xl mx-auto space-y-6">

                {/* ── Header ── */}
                <div className="bg-white rounded-2xl shadow-lg p-6">
                    <h1 className="text-2xl md:text-3xl font-bold text-gray-800 mb-6">User Access</h1>

                    {/* Access Level selector */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Access Level</label>
                        <select
                            value={accesscam}
                            onChange={(e) => setAccesscam(e.target.value)}
                            className="w-full md:w-72 border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        >
                            <option value="">Select</option>
                            {accessOptions.map((opt) => (
                                <option key={opt} value={opt}>{opt}</option>
                            ))}
                        </select>
                    </div>
                </div>

                {/* ── Rights Table ── */}
                {accesscam && (
                    <div className="bg-white rounded-2xl shadow-lg p-6">

                        {error && (
                            <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
                                {error}
                                <button onClick={fetchMenuRights} className="ml-4 underline text-red-900">Retry</button>
                            </div>
                        )}

                        <div className="overflow-x-auto rounded-lg border border-gray-200">
                            <table className="w-full">
                                <thead className="bg-gradient-to-r from-gray-50 to-gray-100">
                                    <tr>
                                        <th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-32">Menu ID</th>
                                        <th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Menu Description</th>
                                        <th className="py-4 px-6 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-48">User Right</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-200">
                                    {loading ? (
                                        <tr>
                                            <td colSpan={3} className="py-10 text-center">
                                                <div className="flex justify-center">
                                                    <svg className="animate-spin h-6 w-6 text-blue-600" fill="none" viewBox="0 0 24 24">
                                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                                    </svg>
                                                </div>
                                            </td>
                                        </tr>
                                    ) : menuRights.length === 0 ? (
                                        <tr>
                                            <td colSpan={3} className="py-10 px-6 text-center text-gray-500">
                                                No menu entries found.
                                            </td>
                                        </tr>
                                    ) : (
                                        menuRights.map((row, idx) => (
                                            <tr
                                                key={row.menu_id}
                                                className={`transition-colors ${idx % 2 === 0 ? "bg-white" : "bg-gray-50"}`}
                                            >
                                                <td className="py-3 px-6 text-sm font-mono font-medium text-gray-900">
                                                    <span style={{ paddingLeft: `${(row.menu_id.split('.').length - 1) * 12}px` }}>
                                                        {row.menu_id}
                                                    </span>
                                                </td>
                                                <td className="py-3 px-6 text-sm text-gray-800">{row.menu_desc}</td>
                                                <td className="py-3 px-6">
                                                    {akses === "9" ? (
                                                        /* Admin: editable dropdown */
                                                        <select
                                                            value={row.userright}
                                                            onChange={(e) => handleRightChange(row.menu_id, Number(e.target.value))}
                                                            className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                                        >
                                                            {USER_RIGHT_OPTIONS.map((opt) => (
                                                                <option key={opt.value} value={opt.value}>{opt.label}</option>
                                                            ))}
                                                        </select>
                                                    ) : (
                                                        /* Read-only: badge */
                                                        <span className={`inline-flex px-2 py-1 rounded-full text-xs font-semibold ${RIGHT_BADGE[row.userright] ?? RIGHT_BADGE[0]}`}>
                                                            {USER_RIGHT_OPTIONS.find((o) => o.value === row.userright)?.label ?? "None"}
                                                        </span>
                                                    )}
                                                </td>
                                            </tr>
                                        ))
                                    )}
                                </tbody>
                            </table>
                        </div>

                        {/* Save button — admin only */}
                        {akses === "9" && !loading && menuRights.length > 0 && (
                            <div className="mt-4 flex items-center gap-4">
                                <button
                                    onClick={handleSave}
                                    disabled={saveLoading}
                                    className={`bg-gradient-to-r from-blue-600 to-indigo-700 hover:from-blue-700 hover:to-indigo-800 text-white px-6 py-2 rounded-lg font-medium shadow-md transition-all ${saveLoading ? "opacity-75 cursor-not-allowed" : ""}`}
                                >
                                    {saveLoading ? "Saving..." : "Save"}
                                </button>

                                {saveMessage && (
                                    <span className={`text-sm font-medium ${saveMessage.type === "success" ? "text-green-600" : "text-red-600"}`}>
                                        {saveMessage.text}
                                    </span>
                                )}
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};

export default UserAccessPage;