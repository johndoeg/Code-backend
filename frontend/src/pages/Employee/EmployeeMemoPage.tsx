import React, { useEffect, useState, useCallback } from "react";
import api from '../../api/axiosInstance';
import Pagination from '../../helpers/Pagination';
import { DEFAULT_PAGE_LIMIT } from '../../constants/DefaultValue';
import AsOfDatePicker from '../../components/AsOfDatePickerComponent';

type MemoType = "NW" | "RL" | "RS" | "";

interface Option { value: string; label: string }
interface Branch { branch_cd: string; branch_name: string }
interface Division { div_id: string; div_desc: string }
interface Position { position_id: string; position_desc: string }
interface Employee { employee_id: string; employee_fullname: string }

interface MemoRow {
	id: string;
	memo_type: MemoType;
	memo_type_desc: string;
	memo_date: string;
	employee_id: string;
	employee_fullname: string;
	branch_name: string;
	div_desc: string;
	position_desc: string;
	facility: string;
	email: string;
	new_branch: string;
	new_position: string;
	email_off: string;
	app_off: string;
	lewat: string;
	cancel: string;
}

interface MemoFormState {
	memo_id: string;
	memo_type: MemoType;
	employee_fullname: string;
	employee_id_old: string;
	employee_id: string;
	branch_cd: string;
	div_id: string;
	position_id: string;
	facility_laptop: boolean;
	facility_email: boolean;
	facility_app: boolean;
	reloc_branch: boolean;
	new_branch: string;
	reloc_position: boolean;
	new_position: string;
}

const EMPTY_FORM: MemoFormState = {
	memo_id: "0", memo_type: "",
	employee_fullname: "", employee_id_old: "", employee_id: "",
	branch_cd: "", div_id: "", position_id: "",
	facility_laptop: false, facility_email: false, facility_app: false,
	reloc_branch: false, new_branch: "", reloc_position: false, new_position: "",
};

const PAGE_SIZE = DEFAULT_PAGE_LIMIT;

const isoToDate = (iso: string): Date => {
	if (!iso) return new Date();
	const d = new Date(iso + "T00:00:00");
	return isNaN(d.getTime()) ? new Date() : d;
};

const ddmmToDate = (v: string): Date => {
	if (!v || v.length !== 10) return new Date();
	const parts = v.split("-");
	if (parts[0].length === 4) return isoToDate(v);
	const [d, m, y] = parts;
	return isoToDate(`${y}-${m}-${d}`);
};

const dateToDDMMYYYY = (d: Date): string => {
	const day = String(d.getDate()).padStart(2, "0");
	const month = String(d.getMonth() + 1).padStart(2, "0");
	return `${day}-${month}-${d.getFullYear()}`;
};

const MEMO_DATE_LABEL: Record<MemoType, string> = {
	NW: "Join Date *", RL: "Relocation Date *", RS: "Resign Date *", "": "Memo Date *",
};

const FormRow: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
	<div className="grid grid-cols-3 gap-2 items-start mb-3">
		<label className="col-span-1 text-sm font-medium text-slate-700 pt-2">{label}</label>
		<div className="col-span-2">{children}</div>
	</div>
);

const inputCls = "w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 disabled:bg-slate-100";
const selectCls = inputCls;

const EmployeeMemoPage: React.FC = () => {
	const [isHr, setIsHr] = useState(false);
	const [isIt, setIsIt] = useState(false);

	const [memoTypes, setMemoTypes] = useState<Option[]>([]);
	const [employees, setEmployees] = useState<Employee[]>([]);
	const [branches, setBranches] = useState<Branch[]>([]);
	const [divisions, setDivisions] = useState<Division[]>([]);
	const [positionsAll, setPositionsAll] = useState<Position[]>([]);
	const [formPositions, setFormPositions] = useState<Position[]>([]);

	const [memoFrom, setMemoFrom] = useState<Date>(new Date());
	const [memoTo, setMemoTo] = useState<Date>(new Date());

	const [rows, setRows] = useState<MemoRow[]>([]);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const [page, setPage] = useState(1);
	const totalPages = Math.ceil(rows.length / PAGE_SIZE);
	const pageRows = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
	const startIndex = (page - 1) * PAGE_SIZE + 1;

	const [memoModalOpen, setMemoModalOpen] = useState(false);
	const [cancelModalOpen, setCancelModalOpen] = useState(false);
	const [emailModalOpen, setEmailModalOpen] = useState(false);
	const [isEditMode, setIsEditMode] = useState(false);

	const [form, setForm] = useState<MemoFormState>(EMPTY_FORM);
	const [memoDt, setMemoDt] = useState<Date>(new Date());
	const [emailOffDate, setEmailOffDate] = useState<Date>(new Date());
	const [appOffDate, setAppOffDate] = useState<Date>(new Date());

	const [cancelId, setCancelId] = useState("");
	const [cancelReason, setCancelReason] = useState("");
	const [emailId, setEmailId] = useState("");
	const [emailVal, setEmailVal] = useState("");
	const [saving, setSaving] = useState(false);

	useEffect(() => {
		const load = async () => {
			try {
				const [role, types, emps, brs, divs, posAll] = await Promise.all([
					api.get('/EmployeeMemo/api/role'),
					api.get('/EmployeeMemo/api/memo-types'),
					api.get('/EmployeeMemo/api/employees'),
					api.get('/EmployeeMemo/api/branches'),
					api.get('/EmployeeMemo/api/divisions'),
					api.get('/EmployeeMemo/api/positions-all'),
				]);
				setIsHr(role.data.is_hr);
				setIsIt(role.data.is_it);
				setMemoTypes(types.data);
				setEmployees(emps.data);
				setBranches(brs.data);
				setDivisions(divs.data);
				setPositionsAll(posAll.data);
			} catch {
				setError("Failed to load page data.");
			}
		};
		load();
	}, []);

	const handleSearch = useCallback(async () => {
		setLoading(true);
		setError(null);
		setPage(1);
		try {
			const res = await api.get('/EmployeeMemo/api/search', {
				params: {
					memo_from: dateToDDMMYYYY(memoFrom),
					memo_to: dateToDDMMYYYY(memoTo),
				},
			});
			if (!res.data || res.data.length === 0) {
				setRows([]);
				alert("Data Not Found!");
				return;
			}
			setRows(res.data);
		} catch {
			setError("Search failed. Please try again.");
		} finally {
			setLoading(false);
		}
	}, [memoFrom, memoTo]);

	const setField = <K extends keyof MemoFormState>(key: K, val: MemoFormState[K]) =>
		setForm(f => ({ ...f, [key]: val }));

	const loadPositionsByDiv = async (div_id: string) => {
		if (!div_id) { setFormPositions([]); return; }
		const res = await api.get('/EmployeeMemo/api/positions', { params: { div_id } });
		setFormPositions(res.data);
	};

	const handleDivChange = async (div_id: string) => {
		setField("div_id", div_id);
		setField("position_id", "");
		await loadPositionsByDiv(div_id);
	};

	const handleEmployeeSelect = async (employee_id: string) => {
		setField("employee_id_old", employee_id);
		if (!employee_id) return;
		try {
			const res = await api.get(`/EmployeeMemo/api/employee/${employee_id}`);
			const d = res.data;
			setForm(f => ({
				...f,
				employee_id: d.employee_id,
				branch_cd: d.branch_cd,
				div_id: d.div_id,
				position_id: d.position_id,
				employee_id_old: employee_id,
			}));
			setFormPositions(d.positions);
		} catch {
			alert("Failed to load employee data.");
		}
	};

	const openAddModal = () => {
		setForm(EMPTY_FORM);
		setFormPositions([]);
		setMemoDt(new Date());
		setEmailOffDate(new Date());
		setAppOffDate(new Date());
		setIsEditMode(false);
		setMemoModalOpen(true);
	};

	const openEditModal = async (memo_id: string) => {
		try {
			const res = await api.get(`/EmployeeMemo/api/detail/${memo_id}`);
			const d = res.data;
			setFormPositions(d.positions);
			setMemoDt(ddmmToDate(d.memo_date));
			setEmailOffDate(d.email_offdate ? ddmmToDate(d.email_offdate) : new Date());
			setAppOffDate(d.app_offdate ? ddmmToDate(d.app_offdate) : new Date());
			setForm({
				memo_id,
				memo_type: d.memo_type as MemoType,
				employee_fullname: d.employee_fullname,
				employee_id_old: d.employee_id,
				employee_id: d.employee_id,
				branch_cd: d.branch_cd,
				div_id: d.div_id,
				position_id: d.position_id,
				facility_laptop: d.facility_laptop === "1",
				facility_email: d.facility_email === "1",
				facility_app: d.facility_app === "1",
				reloc_branch: !!d.new_branch,
				new_branch: d.new_branch,
				reloc_position: !!d.new_position,
				new_position: d.new_position,
			});
			setIsEditMode(true);
			setMemoModalOpen(true);
		} catch {
			alert("Failed to load memo details.");
		}
	};

	const handleSaveMemo = async () => {
		const { memo_type, employee_id, employee_fullname, branch_cd, div_id, position_id } = form;
		if (!memo_type || !memoDt || !position_id || !branch_cd || !div_id) {
			alert("Please fill all required fields.");
			return;
		}
		if (memo_type === "NW" && !employee_fullname) {
			alert("Please fill Employee Fullname.");
			return;
		}
		if ((memo_type === "RL" || memo_type === "RS") && !employee_id) {
			alert("Please select an employee.");
			return;
		}

		const fullname = memo_type === "NW"
			? form.employee_fullname
			: employees.find(e => e.employee_id === form.employee_id_old)?.employee_fullname ?? "";

		setSaving(true);
		try {
			const res = await api.post('/EmployeeMemo/api/save', {
				memo_id: form.memo_id,
				memo_type,
				memo_dt: dateToDDMMYYYY(memoDt),
				employee_id,
				employee_fullname: fullname,
				branch_cd,
				div_id,
				position_id,
				facility_laptop: form.facility_laptop ? 1 : 0,
				facility_email: form.facility_email ? 1 : 0,
				facility_app: form.facility_app ? 1 : 0,
				new_branch: form.reloc_branch ? form.new_branch : "",
				new_position: form.reloc_position ? form.new_position : "",
				email_off: dateToDDMMYYYY(emailOffDate),
				app_off: dateToDDMMYYYY(appOffDate),
			});
			alert(res.data.message);
			setMemoModalOpen(false);
			handleSearch();
		} catch {
			alert("Save failed. Please try again.");
		} finally {
			setSaving(false);
		}
	};

	const handleCancelMemo = async () => {
		if (!cancelReason.trim()) { alert("Please enter a cancel reason."); return; }
		try {
			const res = await api.post('/EmployeeMemo/api/cancel', {
				memo_id: cancelId, cancel_reason: cancelReason,
			});
			alert(res.data.message);
			setCancelModalOpen(false);
			setCancelReason("");
			handleSearch();
		} catch {
			alert("Cancel failed.");
		}
	};

	const handleEmailUpdate = async () => {
		if (!emailVal.trim()) { alert("Please enter an email."); return; }
		try {
			const res = await api.post('/EmployeeMemo/api/email', {
				memo_id: emailId, email: emailVal,
			});
			alert(res.data.message);
			setEmailModalOpen(false);
			setEmailVal("");
			handleSearch();
		} catch {
			alert("Update failed.");
		}
	};

	const memoType = form.memo_type;
	const isNW = memoType === "NW";
	const isRL = memoType === "RL";
	const isRS = memoType === "RS";
	const isOldEmp = isRL || isRS;
	const fieldLocked = isEditMode;

	const renderInfoCell = (row: MemoRow) => {
		if (row.memo_type === "NW") return <><strong>Facility:</strong> {row.facility}<br /><strong>Email:</strong> {row.email}</>;
		if (row.memo_type === "RL") return <><strong>New Branch:</strong> {row.new_branch}<br /><strong>New Position:</strong> {row.new_position}</>;
		if (row.memo_type === "RS") return <><strong>Email Off:</strong> {row.email_off}<br /><strong>App Off:</strong> {row.app_off}</>;
		return null;
	};

	const CloseIcon = () => (
		<svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
		</svg>
	);

	return (
		<div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 p-4 md:p-6">
			<div className="max-w-7xl mx-auto space-y-6">

				<div className="bg-white rounded-2xl shadow-lg p-6">
					<h1 className="text-2xl md:text-3xl font-bold text-slate-800 mb-6">Employee Memo</h1>

					{error && (
						<div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{error}</div>
					)}

					<div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
						<AsOfDatePicker
							label="Memo Date From"
							value={memoFrom}
							onChange={(date) => {
								if (!date) return;
								setMemoFrom(date);
								if (date > memoTo) setMemoTo(date);
							}}
							maxDate={memoTo}
							required
						/>
						<AsOfDatePicker
							label="Memo Date To"
							value={memoTo}
							onChange={(date) => { if (date) setMemoTo(date); }}
							minDate={memoFrom}
							required
						/>
					</div>

					<button
						onClick={handleSearch}
						disabled={loading}
						className="px-5 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white rounded-lg text-sm font-medium transition-colors"
					>
						{loading ? "Searching…" : "Search"}
					</button>
				</div>

				<div className="bg-white rounded-2xl shadow-lg p-6">
					<div className="overflow-x-auto rounded-xl border border-slate-200">
						<table className="w-full text-sm">
							<thead className="bg-gradient-to-r from-slate-100 to-slate-200">
								<tr>
									{["No.", "Memo Type", "Memo Date", "Employee Data", "Facility / Relocation / Resign Info"].map((h, i) => (
										<th key={i} className="py-3 px-4 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider border border-slate-300 whitespace-nowrap">
											{h}
										</th>
									))}
									<th className="py-3 px-4 border border-slate-300">
										{isHr && (
											<button onClick={openAddModal} className="px-3 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-xs font-medium">
												+ Add
											</button>
										)}
									</th>
								</tr>
							</thead>
							<tbody className="divide-y divide-slate-100">
								{loading ? (
									<tr>
										<td colSpan={6} className="py-14 text-center text-slate-400">
											<div className="flex justify-center">
												<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
											</div>
										</td>
									</tr>
								) : pageRows.length === 0 ? (
									<tr>
										<td colSpan={6} className="py-14 text-center text-slate-400">No records found</td>
									</tr>
								) : (
									pageRows.map((row, idx) => (
										<tr key={`${row.id}-${idx}`} className={idx % 2 === 0 ? "bg-white" : "bg-slate-50"}>
											<td className="py-2 px-4 text-center border-b border-slate-100">{startIndex + idx}</td>
											<td className="py-2 px-4 border-b border-slate-100">{row.memo_type_desc}</td>
											<td className="py-2 px-4 whitespace-nowrap border-b border-slate-100">{row.memo_date}</td>
											<td className="py-2 px-4 border-b border-slate-100 text-xs leading-5">
												<strong>ID:</strong> {row.employee_id}<br />
												<strong>Name:</strong> {row.employee_fullname}<br />
												<strong>Branch:</strong> {row.branch_name}<br />
												<strong>Division:</strong> {row.div_desc}<br />
												<strong>Position:</strong> {row.position_desc}
											</td>
											<td className="py-2 px-4 border-b border-slate-100 text-xs leading-5">
												{renderInfoCell(row)}
											</td>
											<td className="py-2 px-4 border-b border-slate-100">
												<div className="flex flex-col gap-1">
													{row.cancel === "1" ? (
														<span className="text-xs text-red-500 font-semibold">Cancelled</span>
													) : (
														<>
															{isHr && row.lewat === "0" && (
																<>
																	<button onClick={() => openEditModal(row.id)} className="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded text-xs font-medium">
																		Edit
																	</button>
																	<button onClick={() => { setCancelId(row.id); setCancelModalOpen(true); }} className="px-3 py-1 bg-red-600 hover:bg-red-700 text-white rounded text-xs font-medium">
																		Cancel
																	</button>
																</>
															)}
															{isIt && row.memo_type === "NW" && row.email === "" && (
																<button onClick={() => { setEmailId(row.id); setEmailModalOpen(true); }} className="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded text-xs font-medium">
																	Edit Email
																</button>
															)}
														</>
													)}
												</div>
											</td>
										</tr>
									))
								)}
							</tbody>
						</table>
					</div>

					{!loading && rows.length > PAGE_SIZE && (
						<Pagination page={page} totalPages={totalPages} onPageChange={setPage}
							totalItems={rows.length} itemsPerPage={PAGE_SIZE} className="mt-6" />
					)}
				</div>
			</div>

			{memoModalOpen && (
				<div className="fixed inset-0 bg-black/50 flex items-start justify-center z-50 p-4 overflow-y-auto">
					<div className="bg-white rounded-2xl shadow-2xl w-full max-w-xl my-8">
						<div className="flex justify-between items-center p-6 border-b">
							<h2 className="text-lg font-bold text-slate-800">{isEditMode ? "Edit Memo" : "Add Memo"}</h2>
							<button onClick={() => setMemoModalOpen(false)} className="text-slate-400 hover:text-slate-600"><CloseIcon /></button>
						</div>

						<div className="p-6 space-y-1">
							<FormRow label="Memo Type *">
								<select value={form.memo_type} disabled={fieldLocked}
									onChange={e => setField("memo_type", e.target.value as MemoType)}
									className={selectCls}>
									<option value="">Select</option>
									{memoTypes.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
								</select>
							</FormRow>

							<FormRow label={MEMO_DATE_LABEL[form.memo_type]}>
								<AsOfDatePicker label="" value={memoDt} onChange={(d) => { if (d) setMemoDt(d); }} required />
							</FormRow>

							<FormRow label="Employee Fullname *">
								{isNW ? (
									<input type="text" value={form.employee_fullname} readOnly={fieldLocked}
										onChange={e => setField("employee_fullname", e.target.value)} className={inputCls} />
								) : (
									<select value={form.employee_id_old} disabled={fieldLocked}
										onChange={e => handleEmployeeSelect(e.target.value)} className={selectCls}>
										<option value="">Select</option>
										{employees.map(e => <option key={e.employee_id} value={e.employee_id}>{e.employee_fullname}</option>)}
									</select>
								)}
							</FormRow>

							<FormRow label="Employee ID *">
								<input type="text" value={form.employee_id} readOnly={isOldEmp || fieldLocked}
									onChange={e => setField("employee_id", e.target.value)} className={inputCls} />
							</FormRow>

							<FormRow label="Branch *">
								<select value={form.branch_cd} disabled={isOldEmp || fieldLocked}
									onChange={e => setField("branch_cd", e.target.value)} className={selectCls}>
									<option value="">Select</option>
									{branches.map(b => <option key={b.branch_cd} value={b.branch_cd}>{b.branch_name}</option>)}
								</select>
							</FormRow>

							<FormRow label="Division *">
								<select value={form.div_id} disabled={isOldEmp || fieldLocked}
									onChange={e => handleDivChange(e.target.value)} className={selectCls}>
									<option value="">Select</option>
									{divisions.map(d => <option key={d.div_id} value={d.div_id}>{d.div_desc}</option>)}
								</select>
							</FormRow>

							<FormRow label="Position *">
								<select value={form.position_id} disabled={isOldEmp || fieldLocked}
									onChange={e => setField("position_id", e.target.value)} className={selectCls}>
									<option value="">Select</option>
									{formPositions.map(p => <option key={p.position_id} value={p.position_id}>{p.position_desc}</option>)}
								</select>
							</FormRow>

							{isNW && (
								<div className="border border-slate-200 rounded-lg p-4 space-y-2 bg-slate-50">
									<p className="text-xs font-semibold text-slate-600 uppercase tracking-wider mb-2">Facilities</p>
									{([
										{ key: "facility_laptop" as const, label: "Laptop" },
										{ key: "facility_email" as const, label: "Email" },
										{ key: "facility_app" as const, label: "Application" },
									] as const).map(f => (
										<label key={f.key} className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
											<input type="checkbox" checked={form[f.key] as boolean}
												onChange={e => setField(f.key, e.target.checked)}
												className="w-4 h-4 accent-blue-600" />
											{f.label}
										</label>
									))}
								</div>
							)}

							{isRL && (
								<div className="border border-slate-200 rounded-lg p-4 space-y-3 bg-slate-50">
									<p className="text-xs font-semibold text-slate-600 uppercase tracking-wider mb-2">Relocation</p>
									<div className="space-y-2">
										<label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
											<input type="checkbox" checked={form.reloc_branch}
												onChange={e => setField("reloc_branch", e.target.checked)}
												className="w-4 h-4 accent-blue-600" />
											New Branch
										</label>
										{form.reloc_branch && (
											<select value={form.new_branch} onChange={e => setField("new_branch", e.target.value)} className={selectCls}>
												<option value="">Select</option>
												{branches.map(b => <option key={b.branch_cd} value={b.branch_cd}>{b.branch_name}</option>)}
											</select>
										)}
									</div>
									<div className="space-y-2">
										<label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
											<input type="checkbox" checked={form.reloc_position}
												onChange={e => setField("reloc_position", e.target.checked)}
												className="w-4 h-4 accent-blue-600" />
											New Position
										</label>
										{form.reloc_position && (
											<select value={form.new_position} onChange={e => setField("new_position", e.target.value)} className={selectCls}>
												<option value="">Select</option>
												{positionsAll.map(p => <option key={p.position_id} value={p.position_id}>{p.position_desc}</option>)}
											</select>
										)}
									</div>
								</div>
							)}

							{isRS && (
								<div className="border border-slate-200 rounded-lg p-4 space-y-3 bg-slate-50">
									<p className="text-xs font-semibold text-slate-600 uppercase tracking-wider mb-2">Resign Details</p>
									<FormRow label="Email Off Date">
										<AsOfDatePicker label="" value={emailOffDate} onChange={(d) => { if (d) setEmailOffDate(d); }} />
									</FormRow>
									<FormRow label="Application Off Date">
										<AsOfDatePicker label="" value={appOffDate} onChange={(d) => { if (d) setAppOffDate(d); }} />
									</FormRow>
								</div>
							)}
						</div>

						<div className="flex justify-end gap-3 p-6 border-t">
							<button onClick={() => setMemoModalOpen(false)} className="px-4 py-2 border border-slate-300 rounded-lg text-slate-600 hover:bg-slate-50 text-sm">Close</button>
							<button onClick={handleSaveMemo} disabled={saving} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white rounded-lg text-sm font-medium">
								{saving ? "Saving…" : "Submit"}
							</button>
						</div>
					</div>
				</div>
			)}

			{cancelModalOpen && (
				<div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
					<div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
						<div className="flex justify-between items-center p-6 border-b">
							<h2 className="text-lg font-bold text-slate-800">Cancel Memo</h2>
							<button onClick={() => setCancelModalOpen(false)} className="text-slate-400 hover:text-slate-600"><CloseIcon /></button>
						</div>
						<div className="p-6">
							<FormRow label="Cancel Reason *">
								<input type="text" value={cancelReason} maxLength={200}
									onChange={e => setCancelReason(e.target.value)} className={inputCls} />
							</FormRow>
						</div>
						<div className="flex justify-end gap-3 p-6 border-t">
							<button onClick={() => setCancelModalOpen(false)} className="px-4 py-2 border border-slate-300 rounded-lg text-slate-600 hover:bg-slate-50 text-sm">Close</button>
							<button onClick={handleCancelMemo} className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium">Submit</button>
						</div>
					</div>
				</div>
			)}

			{emailModalOpen && (
				<div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
					<div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
						<div className="flex justify-between items-center p-6 border-b">
							<h2 className="text-lg font-bold text-slate-800">Update Email</h2>
							<button onClick={() => setEmailModalOpen(false)} className="text-slate-400 hover:text-slate-600"><CloseIcon /></button>
						</div>
						<div className="p-6">
							<FormRow label="Email *">
								<input type="text" value={emailVal} maxLength={200}
									onChange={e => setEmailVal(e.target.value)} className={inputCls} />
							</FormRow>
						</div>
						<div className="flex justify-end gap-3 p-6 border-t">
							<button onClick={() => setEmailModalOpen(false)} className="px-4 py-2 border border-slate-300 rounded-lg text-slate-600 hover:bg-slate-50 text-sm">Close</button>
							<button onClick={handleEmailUpdate} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium">Submit</button>
						</div>
					</div>
				</div>
			)}
		</div>
	);
};

export default EmployeeMemoPage;