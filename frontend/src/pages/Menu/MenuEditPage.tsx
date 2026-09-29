import React, { useEffect, useState } from "react";
import api from "../../api/axiosInstance";

interface MenuEditData {
	menu_id: string;
	menu_desc: string;
	menu_parent: string;
	parent_label: string;
	url: string;
}

const MenuEditPage: React.FC = () => {
	const menuId = new URLSearchParams(window.location.search).get("menu_id") || "";

	const [loading, setLoading] = useState(true);
	const [loadError, setLoadError] = useState<string | null>(null);

	const [parentDisplay, setParentDisplay] = useState("");
	const [menuDesc, setMenuDesc] = useState("");
	const [url, setUrl] = useState("");

	const [saving, setSaving] = useState(false);
	const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

	const fetchMenu = async () => {
		setLoading(true);
		setLoadError(null);
		try {
			const res = await api.get(`/SystemAdmin/api/menu/${encodeURIComponent(menuId)}`);
			const data: MenuEditData = res.data.data;
			setMenuDesc(data.menu_desc);
			setUrl(data.url);
			setParentDisplay(
				data.menu_parent === "0" ? "Parent" : `${data.menu_parent} ${data.parent_label}`
			);
		} catch {
			setLoadError("Failed to load menu data. Please try again.");
		} finally {
			setLoading(false);
		}
	};

	useEffect(() => {
		if (!menuId) {
			setLoadError("No menu_id was provided.");
			setLoading(false);
			return;
		}
		fetchMenu();
	}, [menuId]);

	const handleSave = async () => {
		if (!menuDesc.trim()) {
			setMessage({ type: "error", text: "Menu Description must not be empty" });
			return;
		}
		setSaving(true);
		setMessage(null);
		try {
			await api.put(`/SystemAdmin/api/menu/${encodeURIComponent(menuId)}`, {
				menu_desc: menuDesc,
				url,
			});
			setMessage({ type: "success", text: "Successful" });
			setTimeout(() => {
				window.location.href = "/menu-entry";
			}, 500);
		} catch (err: any) {
			const msgs = err.response?.data?.message;
			setMessage({
				type: "error",
				text: Array.isArray(msgs) ? msgs.join(", ") : "Failed",
			});
		} finally {
			setSaving(false);
		}
	};

	const handleCancel = () => {
		window.location.href = "/menu-entry";
	};

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-2xl mx-auto space-y-6">
				<div className="bg-white rounded-2xl shadow-lg p-6">
					<h1 className="text-2xl md:text-3xl font-bold text-gray-800">Edit Menu</h1>
					<p className="text-gray-600 mt-1 mb-6">Update the description and URL for this menu entry</p>

					{loading ? (
						<div className="flex justify-center py-10">
							<svg className="animate-spin h-6 w-6 text-blue-600" fill="none" viewBox="0 0 24 24">
								<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
								<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
							</svg>
						</div>
					) : loadError ? (
						<div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
							{loadError}
							{menuId && (
								<button onClick={fetchMenu} className="ml-4 underline text-red-900">Retry</button>
							)}
						</div>
					) : (
						<div className="space-y-4">
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Menu Parent</label>
								<div className="w-full bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-gray-600">
									{parentDisplay}
								</div>
							</div>

							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Menu ID</label>
								<div className="w-full bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-gray-600 font-mono">
									{menuId}
								</div>
							</div>

							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Menu Description</label>
								<input
									type="text"
									value={menuDesc}
									onChange={(e) => setMenuDesc(e.target.value)}
									className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
								/>
							</div>

							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Menu URL</label>
								<input
									type="text"
									value={url}
									onChange={(e) => setUrl(e.target.value)}
									className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
								/>
							</div>

							<div className="flex items-center gap-4 pt-2">
								<button
									onClick={handleSave}
									disabled={saving}
									className={`bg-gradient-to-r from-blue-600 to-indigo-700 hover:from-blue-700 hover:to-indigo-800 text-white px-6 py-2 rounded-lg font-medium shadow-md transition-all ${saving ? "opacity-75 cursor-not-allowed" : ""}`}
								>
									{saving ? "Saving..." : "Save"}
								</button>

								<button
									onClick={handleCancel}
									className="bg-gray-200 hover:bg-gray-300 text-gray-700 px-6 py-2 rounded-lg font-medium transition-colors"
								>
									Cancel
								</button>

								{message && (
									<span className={`text-sm font-medium ${message.type === "success" ? "text-green-600" : "text-red-600"}`}>
										{message.text}
									</span>
								)}
							</div>
						</div>
					)}
				</div>
			</div>
		</div>
	);
};

export default MenuEditPage;