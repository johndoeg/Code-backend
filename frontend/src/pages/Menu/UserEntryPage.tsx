import React, { useEffect, useState } from "react";
import api from "../../api/axiosInstance";
import AsOfDatePicker from "../../components/AsOfDatePickerComponent";

const toISO = (d: Date): string => d.toISOString().split('T')[0];

interface BranchOption {
	branch_cd: string;
	branch_name: string;
}

interface SuperiorOption {
	employee_id: string;
	fullname: string;
}

interface UserDetail {
	employee_id: string;
	username: string;
	fullname: string;
	branch_cd: string;
	accesscam: string;
	superior: string;
	resign_date: string;
	status: string;
}

type Mode = "Add" | "Edit" | "View";

const UserEntryPage: React.FC = () => {
	const params = new URLSearchParams(window.location.search);
	const mode = (params.get("id") as Mode) || "Add";
	const employeeIdParam = params.get("employee_id") || "";
	const isReadOnlyIdFields = mode !== "Add";
	const isViewOnly = mode === "View";

	const [loading, setLoading] = useState(mode !== "Add");
	const [loadError, setLoadError] = useState<string | null>(null);

	const [branchOptions, setBranchOptions] = useState<BranchOption[]>([]);
	const [accessGroupOptions, setAccessGroupOptions] = useState<string[]>([]);
	const [superiorOptions, setSuperiorOptions] = useState<SuperiorOption[]>([]);

	const [username, setUsername] = useState("");
	const [employeeId, setEmployeeId] = useState(employeeIdParam);
	const [fullname, setFullname] = useState("");
	const [branchCd, setBranchCd] = useState("");
	const [accesscam, setAccesscam] = useState("");
	const [superior, setSuperior] = useState("");
	const [status, setStatus] = useState("A");
	const [resignDate, setResignDate] = useState<Date | null>(null);

	const [saving, setSaving] = useState(false);
	const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

	useEffect(() => {
		const loadOptions = async () => {
			try {
				const [branchRes, accessRes, superiorRes] = await Promise.all([
					api.get('/SystemAdmin/api/users/branch-options'),
					api.get('/SystemAdmin/api/users/access-group-options'),
					api.get('/SystemAdmin/api/users/superior-options'),
				]);
				setBranchOptions(branchRes.data.data);
				setAccessGroupOptions(accessRes.data.data);
				setSuperiorOptions(superiorRes.data.data);
			} catch { }
		};
		loadOptions();
	}, []);

	useEffect(() => {
		if (mode === "Add") return;
		if (!employeeIdParam) {
			setLoadError("No employee_id was provided.");
			setLoading(false);
			return;
		}
		fetchUser();
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [mode, employeeIdParam]);

	const fetchUser = async () => {
		setLoading(true);
		setLoadError(null);
		try {
			const res = await api.get(`/SystemAdmin/api/users/${encodeURIComponent(employeeIdParam)}`);
			const data: UserDetail = res.data.data;
			setUsername(data.username);
			setEmployeeId(data.employee_id);
			setFullname(data.fullname);
			setBranchCd(data.branch_cd);
			setAccesscam(data.accesscam);
			setSuperior(data.superior);
			setStatus(data.status || "A");
			setResignDate(data.resign_date ? new Date(`${data.resign_date}T00:00:00`) : null);
		} catch {
			setLoadError("Failed to load user data. Please try again.");
		} finally {
			setLoading(false);
		}
	};

	const handleSave = async () => {
		const errors: string[] = [];
		if (mode === "Add") {
			if (!username.trim()) errors.push("Username must not be empty");
			if (!employeeId.trim()) errors.push("Employee ID must not be empty");
		}
		if (!fullname.trim()) errors.push("Fullname must not be empty");
		if (!branchCd) errors.push("Branch must not be empty");
		if (!accesscam) errors.push("Access Group must not be empty");

		if (errors.length > 0) {
			setMessage({ type: "error", text: errors.join(", ") });
			return;
		}

		setSaving(true);
		setMessage(null);
		try {
			if (mode === "Add") {
				await api.post('/SystemAdmin/api/users', {
					username,
					employee_id: employeeId,
					fullname,
					branch_cd: branchCd,
					accesscam,
					superior,
					status,
				});
			} else {
				await api.put(`/SystemAdmin/api/users/${encodeURIComponent(employeeId)}`, {
					fullname,
					branch_cd: branchCd,
					accesscam,
					superior,
					status,
					resign_date: resignDate ? toISO(resignDate) : '',
				});
			}
			setMessage({ type: "success", text: "Successful" });
			setTimeout(() => {
				window.location.href = "/users";
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
		window.location.href = "/users";
	};

	const titles: Record<Mode, string> = { Add: "Add User", Edit: "Edit User", View: "View User" };

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-2xl mx-auto space-y-6">
				<div className="bg-white rounded-2xl shadow-lg p-6">
					<h1 className="text-2xl md:text-3xl font-bold text-gray-800">{titles[mode]}</h1>
					<p className="text-gray-600 mt-1 mb-6">
						{mode === "Add" ? "Create a new user record" : mode === "Edit" ? "Update this user's details" : "Viewing user details (read-only)"}
					</p>

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
							<button onClick={fetchUser} className="ml-4 underline text-red-900">Retry</button>
						</div>
					) : (
						<div className="space-y-4">
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
								<input
									type="text"
									value={username}
									onChange={(e) => setUsername(e.target.value)}
									readOnly={isReadOnlyIdFields}
									className={`w-full border rounded-lg px-3 py-2 ${isReadOnlyIdFields ? "bg-gray-50 border-gray-200 text-gray-600" : "border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"}`}
								/>
							</div>

							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Fullname</label>
								<input
									type="text"
									value={fullname}
									onChange={(e) => setFullname(e.target.value)}
									readOnly={isViewOnly}
									className={`w-full border rounded-lg px-3 py-2 ${isViewOnly ? "bg-gray-50 border-gray-200 text-gray-600" : "border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"}`}
								/>
							</div>

							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Employee ID</label>
								<input
									type="text"
									value={employeeId}
									onChange={(e) => setEmployeeId(e.target.value)}
									readOnly={isReadOnlyIdFields}
									className={`w-full border rounded-lg px-3 py-2 ${isReadOnlyIdFields ? "bg-gray-50 border-gray-200 text-gray-600" : "border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"}`}
								/>
							</div>

							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Branch</label>
								<select
									value={branchCd}
									onChange={(e) => setBranchCd(e.target.value)}
									disabled={isViewOnly}
									className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:text-gray-600"
								>
									<option value="">Select</option>
									{branchOptions.map((b) => (
										<option key={b.branch_cd} value={b.branch_cd}>{b.branch_name}</option>
									))}
								</select>
							</div>

							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Access Group</label>
								<select
									value={accesscam}
									onChange={(e) => setAccesscam(e.target.value)}
									disabled={isViewOnly}
									className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:text-gray-600"
								>
									<option value="">Select</option>
									{accessGroupOptions.map((a) => (
										<option key={a} value={a}>{a}</option>
									))}
								</select>
							</div>

							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Superior</label>
								<select
									value={superior}
									onChange={(e) => setSuperior(e.target.value)}
									disabled={isViewOnly}
									className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:text-gray-600"
								>
									<option value="">No Superior</option>
									{superiorOptions.map((s) => (
										<option key={s.employee_id} value={s.employee_id}>{s.fullname}</option>
									))}
								</select>
							</div>

							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
								<select
									value={status}
									onChange={(e) => setStatus(e.target.value)}
									disabled={isViewOnly}
									className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:text-gray-600"
								>
									<option value="A">Active</option>
									<option value="D">Non Active</option>
								</select>
							</div>

							{mode === "Edit" && (
								<AsOfDatePicker
									label="Resign Date"
									value={resignDate}
									onChange={(date) => setResignDate(date)}
								/>
							)}

							<div className="flex items-center gap-4 pt-2">
								{mode !== "View" && (
									<button
										onClick={handleSave}
										disabled={saving}
										className={`bg-gradient-to-r from-blue-600 to-indigo-700 hover:from-blue-700 hover:to-indigo-800 text-white px-6 py-2 rounded-lg font-medium shadow-md transition-all ${saving ? "opacity-75 cursor-not-allowed" : ""}`}
									>
										{saving ? "Saving..." : "Save"}
									</button>
								)}

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

export default UserEntryPage;