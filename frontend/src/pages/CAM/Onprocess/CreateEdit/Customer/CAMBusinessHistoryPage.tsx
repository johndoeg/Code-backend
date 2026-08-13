import React, { useCallback, useEffect, useState } from "react";
import api from "../../../../../api/axiosInstance";

interface Option {
	value: string;
	label: string;
}

interface BusinessHistoryRow {
	id: number;
	fromMonth: string;
	fromYear: string;
	untilMonth: string;
	untilYear: string;
	company: string;
	companyAddress: string;
	position: string;
	positionLabel: string;
	positionOther: string;
	employeeId: string;
	areaCd: string;
	province: string;
	city: string;
	postcode: string;
	phone: string;
}

interface BusinessHistoryData {
	lesseeCat: string;
	positions: Option[];
	rows: BusinessHistoryRow[];
}

export interface CAMBusinessHistoryPageProps {
	apless: string;
	applNo: string;
	onSaved: (result: { apless: string; applno: string }) => void;
}

const cellLabel =
	"border-b border-slate-100 bg-slate-50/70 px-4 py-2.5 align-top text-[11px] font-medium uppercase tracking-wide text-slate-400 whitespace-nowrap";
const cellValue = "border-b border-slate-100 px-4 py-2.5 align-top text-sm text-slate-700";
const cellEmpty = "border-b border-slate-100 px-4 py-2.5";

function SectionHeader({ children }: { children: React.ReactNode }) {
	return (
		<div className="border-b border-t border-slate-200 bg-slate-50 px-6 py-3 first:border-t-0">
			<h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">{children}</h2>
		</div>
	);
}

function Row({
	left,
	right,
}: {
	left?: [string, React.ReactNode];
	right?: [string, React.ReactNode];
}) {
	return (
		<tr>
			{left ? (
				<>
					<td className={cellLabel}>{left[0]}</td>
					<td className={cellValue}>{left[1]}</td>
				</>
			) : (
				<>
					<td className={cellEmpty}></td>
					<td className={cellEmpty}></td>
				</>
			)}
			{right ? (
				<>
					<td className={cellLabel}>{right[0]}</td>
					<td className={cellValue}>{right[1]}</td>
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

function FullRow({ label, children }: { label: string; children: React.ReactNode }) {
	return (
		<tr>
			<td className={cellLabel}>{label}</td>
			<td colSpan={3} className={cellValue}>{children}</td>
		</tr>
	);
}

const inputCls =
	"border border-slate-300 rounded-lg px-2 py-1.5 text-sm w-full focus:outline-none focus:ring-2 focus:ring-blue-400";

const MONTHS = Array.from({ length: 12 }, (_, i) => String(i + 1).padStart(2, "0"));
const CURRENT_YEAR = new Date().getFullYear();
const YEARS = Array.from({ length: 101 }, (_, i) => String(CURRENT_YEAR - i));

const formatPeriod = (month: string, year: string) => (month === "00" ? "Present" : `${month}-${year}`);

const emptyForm = {
	fromMonth: "", fromYear: "", untilMonth: "", untilYear: "",
	company: "", companyAddress: "", position: "", positionOther: "",
	employeeId: "", areaCd: "", province: "", city: "", postcode: "", phone: "",
};

const CAMBusinessHistoryPage: React.FC<CAMBusinessHistoryPageProps> = ({ apless, applNo, onSaved }) => {
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [savingRow, setSavingRow] = useState(false);
	const [deletingId, setDeletingId] = useState<number | null>(null);
	const [data, setData] = useState<BusinessHistoryData | null>(null);
	const [areas, setAreas] = useState<Option[]>([]);

	const [editingId, setEditingId] = useState<number | null>(null);
	const [form, setForm] = useState(emptyForm);

	const setField = (key: keyof typeof emptyForm, value: string) => setForm(prev => ({ ...prev, [key]: value }));

	const load = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			const [historyRes, areasRes] = await Promise.all([
				api.get("/CAM/EditIndex/business-history", { params: { apless, applno: applNo } }),
				api.get("/CAM/Combo/provinces-and-cities"),
			]);
			setData(historyRes.data);
			setAreas(areasRes.data);
		} catch {
			setError("Failed to load business history. Please try again.");
		} finally {
			setLoading(false);
		}
	}, [apless, applNo]);

	useEffect(() => {
		load();
	}, [load]);

	const resetForm = () => {
		setEditingId(null);
		setForm(emptyForm);
	};

	const startEdit = (row: BusinessHistoryRow) => {
		setEditingId(row.id);
		setForm({
			fromMonth: row.fromMonth,
			fromYear: row.fromYear,
			untilMonth: row.untilMonth === "00" ? "13" : row.untilMonth,
			untilYear: row.untilYear,
			company: row.company,
			companyAddress: row.companyAddress,
			position: row.position,
			positionOther: row.positionOther,
			employeeId: row.employeeId,
			areaCd: row.areaCd,
			province: row.province,
			city: row.city,
			postcode: row.postcode,
			phone: row.phone,
		});
	};

	const handleAreaChange = (value: string) => {
		setField("areaCd", value);
		const area = areas.find(a => a.value === value);
		if (area) {
			const [prov, city] = area.label.split(" - ");
			setField("province", prov || "");
			setField("city", city || "");
		} else {
			setField("province", "");
			setField("city", "");
		}
	};

	const handleUntilMonthChange = (value: string) => {
		setField("untilMonth", value);
		if (value === "13") setField("untilYear", String(CURRENT_YEAR));
	};

	const handleSaveRow = async () => {
		const errs: string[] = [];
		if (!form.fromMonth) errs.push("Month (From) must not be empty.");
		if (!form.fromYear) errs.push("Year (From) must not be empty.");
		if (!form.untilMonth) errs.push("Month (Until) must not be empty.");
		if (form.untilMonth !== "13" && !form.untilYear) errs.push("Year (Until) must not be empty.");
		if (form.untilMonth !== "13" && form.fromYear > form.untilYear) errs.push("Year (From) must not exceed Year (Until).");
		if (!form.company.trim()) errs.push("Company must not be empty.");
		if (!form.position) errs.push("Position must not be empty.");
		if (!form.positionOther.trim()) errs.push("Position Other must not be empty.");
		if (!form.areaCd) errs.push("Area must not be empty.");
		if (!form.postcode.trim()) errs.push("Post Code must not be empty.");
		if (errs.length > 0) {
			alert(errs.join("\n"));
			return;
		}

		setSavingRow(true);
		try {
			const res = await api.post("/CAM/EditIndex/business-history", {
				apless,
				applno: applNo,
				id: editingId || 0,
				fromMonth: form.fromMonth,
				fromYear: form.fromYear,
				untilMonth: form.untilMonth === "13" ? "00" : form.untilMonth,
				untilYear: form.untilMonth === "13" ? "0000" : form.untilYear,
				company: form.company,
				companyAddress: form.companyAddress,
				position: form.position,
				positionOther: form.positionOther,
				employeeId: form.employeeId,
				areaCd: form.areaCd,
				postcode: form.postcode,
				phone: form.phone,
			});
			if (res.data.success) {
				resetForm();
				await load();
			} else {
				alert(res.data.message || "Save failed.");
			}
		} catch {
			alert("Save failed. Please try again.");
		} finally {
			setSavingRow(false);
		}
	};

	const handleDeleteRow = async (id: number) => {
		if (!window.confirm("Are you sure you want to delete this entry?")) return;
		setDeletingId(id);
		try {
			await api.delete("/CAM/EditIndex/business-history", { params: { apless, id } });
			if (editingId === id) resetForm();
			await load();
		} catch {
			alert("Delete failed. Please try again.");
		} finally {
			setDeletingId(null);
		}
	};

	const handleNext = () => {
		if (!data || data.rows.length === 0) {
			alert("Please fill in Business/ Job History.");
			return;
		}
		onSaved({ apless, applno: applNo });
	};

	if (loading || !data) {
		return (
			<div className="flex justify-center py-16">
				<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
			</div>
		);
	}
	if (error) {
		return (
			<div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm flex items-center justify-between">
				{error}
				<button onClick={load} className="underline ml-4">Retry</button>
			</div>
		);
	}

	const showEmployeeId = data.lesseeCat === "EM";

	return (
		<div>
			<h2 className="text-xl font-bold text-slate-800 mb-1">Business / Job History</h2>
			<p className="text-sm text-slate-500 mb-4">Customer No. {apless || "(new)"}</p>

			<div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
				<SectionHeader>{editingId ? "Edit Entry" : "Add Entry"}</SectionHeader>
				<div className="overflow-x-auto">
					<table className="w-full min-w-[820px] border-collapse text-sm">
						<tbody>
							<FullRow label="Period (From - Until) *">
								<div className="flex flex-wrap items-center gap-2">
									<select className={inputCls} style={{ width: "80px" }} value={form.fromMonth} onChange={e => setField("fromMonth", e.target.value)}>
										<option value="">Month</option>
										{MONTHS.map(m => <option key={m} value={m}>{m}</option>)}
									</select>
									<select className={inputCls} style={{ width: "90px" }} value={form.fromYear} onChange={e => setField("fromYear", e.target.value)}>
										<option value="">Year</option>
										{YEARS.map(y => <option key={y} value={y}>{y}</option>)}
									</select>
									<span className="text-sm text-slate-500">to</span>
									<select className={inputCls} style={{ width: "110px" }} value={form.untilMonth} onChange={e => handleUntilMonthChange(e.target.value)}>
										<option value="">Month</option>
										<option value="13">Present</option>
										{MONTHS.map(m => <option key={m} value={m}>{m}</option>)}
									</select>
									<select
										className={inputCls}
										style={{ width: "90px" }}
										value={form.untilYear}
										disabled={form.untilMonth === "13"}
										onChange={e => setField("untilYear", e.target.value)}
									>
										<option value="">Year</option>
										{YEARS.map(y => <option key={y} value={y}>{y}</option>)}
									</select>
								</div>
							</FullRow>

							{showEmployeeId && (
								<Row left={["Employee ID No.", (
									<input className={inputCls} value={form.employeeId} onChange={e => setField("employeeId", e.target.value)} maxLength={25} />
								)]} />
							)}

							<Row
								left={["Position *", (
									<div className="flex flex-col gap-2">
										<select className={inputCls} value={form.position} onChange={e => setField("position", e.target.value)}>
											<option value="">Select</option>
											{data.positions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
										</select>
										<input
											className={inputCls}
											placeholder="Position Other"
											value={form.positionOther}
											onChange={e => setField("positionOther", e.target.value)}
											maxLength={100}
										/>
									</div>
								)]}
								right={["Company Name *", (
									<input className={inputCls} value={form.company} onChange={e => setField("company", e.target.value)} maxLength={100} />
								)]}
							/>

							<FullRow label="Company Address">
								<textarea className={inputCls} value={form.companyAddress} onChange={e => setField("companyAddress", e.target.value)} maxLength={500} />
							</FullRow>

							<Row
								left={["Area *", (
									<select className={inputCls} value={form.areaCd} onChange={e => handleAreaChange(e.target.value)}>
										<option value="">Select</option>
										{areas.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
									</select>
								)]}
								right={["Province", (
									<input className={inputCls} value={form.province} readOnly />
								)]}
							/>
							<Row
								left={["District / City *", (
									<input className={inputCls} value={form.city} readOnly />
								)]}
								right={["Post Code *", (
									<input
										className={inputCls}
										value={form.postcode}
										maxLength={5}
										onChange={e => setField("postcode", e.target.value.replace(/\D/g, ""))}
									/>
								)]}
							/>
							<Row left={["Phone", (
								<input className={inputCls} value={form.phone} onChange={e => setField("phone", e.target.value)} maxLength={100} />
							)]} />
						</tbody>
					</table>
				</div>

				<div className="flex justify-end gap-3 px-6 py-4">
					{editingId && (
						<button
							onClick={resetForm}
							className="px-6 py-2 border border-slate-300 text-slate-600 hover:bg-slate-50 rounded-lg text-sm font-medium"
						>
							Cancel
						</button>
					)}
					<button
						onClick={handleSaveRow}
						disabled={savingRow}
						className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white rounded-lg text-sm font-medium"
					>
						{savingRow ? "Saving…" : editingId ? "Update Entry" : "Add Entry"}
					</button>
				</div>

				<SectionHeader>Existing Entries</SectionHeader>
				<div className="overflow-x-auto">
					<table className="w-full min-w-[960px] border-collapse text-sm">
						<tbody>
							<tr>
								<td className={cellLabel}>No.</td>
								<td className={cellLabel}>From</td>
								<td className={cellLabel}>Until</td>
								<td className={cellLabel}>Company Name</td>
								<td className={cellLabel}>District / City</td>
								<td className={cellLabel}>Post Code</td>
								{showEmployeeId && <td className={cellLabel}>Employee ID No.</td>}
								<td className={cellLabel}>Position</td>
								<td className={cellLabel}>Phone</td>
								<td className={cellLabel}>Actions</td>
							</tr>
							{data.rows.map((row, idx) => (
								<tr key={row.id}>
									<td className={cellValue}>{idx + 1}</td>
									<td className={cellValue}>{formatPeriod(row.fromMonth, row.fromYear)}</td>
									<td className={cellValue}>{formatPeriod(row.untilMonth, row.untilYear)}</td>
									<td className={cellValue}>{row.company}</td>
									<td className={cellValue}>{row.city}</td>
									<td className={cellValue}>{row.postcode}</td>
									{showEmployeeId && <td className={cellValue}>{row.employeeId}</td>}
									<td className={cellValue}>{row.positionLabel} ({row.positionOther})</td>
									<td className={cellValue}>{row.phone}</td>
									<td className={cellValue}>
										<div className="flex gap-3">
											<button onClick={() => startEdit(row)} className="text-xs font-medium text-blue-600 hover:underline">
												Edit
											</button>
											<button
												onClick={() => handleDeleteRow(row.id)}
												disabled={deletingId === row.id}
												className="text-xs font-medium text-red-600 hover:underline disabled:text-slate-400"
											>
												{deletingId === row.id ? "Deleting…" : "Delete"}
											</button>
										</div>
									</td>
								</tr>
							))}
							{data.rows.length === 0 && (
								<tr>
									<td colSpan={showEmployeeId ? 10 : 9} className={cellValue + " text-center text-slate-400"}>
										No entries yet.
									</td>
								</tr>
							)}
						</tbody>
					</table>
				</div>
			</div>

			<div className="flex justify-end gap-3 mt-6">
				<button
					onClick={handleNext}
					className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium"
				>
					Next
				</button>
			</div>
		</div>
	);
};

export default CAMBusinessHistoryPage;