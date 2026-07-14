import React, { useEffect, useState, useCallback } from "react";
import api from "../../api/axiosInstance";
interface MenuRight {
    menu_id: string;
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

const UserAccessPage: React.FC = () => {
    const [accessOptions, setAccessOptions] = useState<string[]>([]);
    const [accesscam, setAccesscam] = useState("");
    const [menuRights, setMenuRights] = useState<MenuRight[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [saveLoading, setSaveLoading] = useState(false);
    const [saveMessage, setSaveMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

    useEffect(() => {
        const fetchOptions = async () => {
            try {
                const res = await api.get('/SystemAdmin/api/uacc/access-options');
                setAccessOptions(res.data.data);
            } catch { }
        };
        fetchOptions();
    }, []);

    const fetchMenuRights = useCallback(async () => {
        if (!accesscam) { setMenuRights([]); return; }
        setLoading(true);
        setError(null);
        setSaveMessage(null);
        try {
            const res = await api.get('/SystemAdmin/api/uacc/menu-rights', { params: { accesscam } });
            setMenuRights(res.data.data);
        } catch {
            setError("Failed to load menu rights. Please try again.");
        } finally {
            setLoading(false);
        }
    }, [accesscam]);

    useEffect(() => { fetchMenuRights(); }, [fetchMenuRights]);

    const handleRightChange = (menu_id: string, value: number) => {
        setMenuRights(prev =>
            prev.map(r => r.menu_id === menu_id ? { ...r, userright: value } : r)
        );
    };

    const handleSave = async () => {
        if (!accesscam) {
            setSaveMessage({ type: "error", text: "Please select Access Level" });
            return;
        }
        setSaveLoading(true);
        setSaveMessage(null);
        try {
            await api.post('/SystemAdmin/api/uacc/save', {
                accesscam,
                rights: menuRights.map(r => ({ menu_id: r.menu_id, userright: r.userright })),
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
            <div className="max-w-5xl mx-auto">
                <div className="bg-white rounded-2xl shadow-lg p-6">

                    <div className="mb-6">
                        <h1 className="text-2xl md:text-3xl font-bold text-gray-800">User Access</h1>
                        <p className="text-gray-600 mt-1">Manage menu access rights per access level</p>
                    </div>

                    <div className="bg-gray-50 rounded-xl p-4 border border-gray-200 mb-6">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Access Level
                                </label>
                                <select
                                    value={accesscam}
                                    onChange={e => setAccesscam(e.target.value)}
                                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all bg-white"
                                >
                                    <option value="">Select</option>
                                    {accessOptions.map(opt => (
                                        <option key={opt} value={opt}>{opt}</option>
                                    ))}
                                </select>
                            </div>
                        </div>
                    </div>

                    {error && (
                        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 flex items-start gap-3">
                            <svg className="w-5 h-5 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <span>{error}</span>
                        </div>
                    )}

                    {accesscam && (
                        <>
                            <div className="overflow-x-auto rounded-lg border border-gray-200">
                                <table className="w-full text-sm">
                                    <thead className="bg-gradient-to-r from-gray-50 to-gray-100">
                                        <tr>
                                            <th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider border border-gray-300 bg-gray-100 w-36">
                                                Menu ID
                                            </th>
                                            <th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider border border-gray-300 bg-gray-100">
                                                Menu Description
                                            </th>
                                            <th className="py-3 px-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider border border-gray-300 bg-gray-100 w-44">
                                                User Right
                                            </th>
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
                                                    className={`hover:bg-blue-50 transition-colors ${idx % 2 === 0 ? "bg-white" : "bg-gray-50/50"}`}
                                                >
                                                    <td className="py-2.5 px-4 border border-gray-200 font-mono font-medium text-gray-900 text-sm">
                                                        <span style={{ paddingLeft: `${(row.menu_id.split('.').length - 1) * 12}px` }}>
                                                            {row.menu_id}
                                                        </span>
                                                    </td>
                                                    <td className="py-2.5 px-4 border border-gray-200 text-gray-800 text-sm">
                                                        {row.menu_desc}
                                                    </td>
                                                    <td className="py-2.5 px-4 border border-gray-200">
                                                        <select
                                                            value={row.userright}
                                                            onChange={e => handleRightChange(row.menu_id, Number(e.target.value))}
                                                            className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                                        >
                                                            {USER_RIGHT_OPTIONS.map(opt => (
                                                                <option key={opt.value} value={opt.value}>{opt.label}</option>
                                                            ))}
                                                        </select>
                                                    </td>
                                                </tr>
                                            ))
                                        )}
                                    </tbody>
                                </table>
                            </div>

                            {!loading && menuRights.length > 0 && (
                                <div className="mt-4 flex items-center gap-4">
                                    <button
                                        onClick={handleSave}
                                        disabled={saveLoading}
                                        className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                        {saveLoading ? (
                                            <>
                                                <svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                                </svg>
                                                Saving...
                                            </>
                                        ) : (
                                            <>
                                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
                                                </svg>
                                                Save
                                            </>
                                        )}
                                    </button>

                                    {saveMessage && (
                                        <span className={`text-sm font-medium ${saveMessage.type === "success" ? "text-green-600" : "text-red-600"}`}>
                                            {saveMessage.text}
                                        </span>
                                    )}
                                </div>
                            )}
                        </>
                    )}

                    {!accesscam && (
                        <div className="py-10 text-center text-gray-500">
                            <svg className="w-16 h-16 text-gray-300 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                            </svg>
                            <p className="text-lg">Select an access level to manage menu rights</p>
                        </div>
                    )}

                </div>
            </div>
        </div>
    );
};

export default UserAccessPage;