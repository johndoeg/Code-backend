import React, { useCallback, useEffect, useState } from "react";
import api from "../../../../../api/axiosInstance";

interface FsItem {
	code: string;
	label: string;
	allowNegative: boolean;
}

interface FsGroup {
	section: "asset" | "liability_equity";
	header: string;
	items: FsItem[];
}

interface BalanceSheetData {
	currency: string;
	currencies: { value: string; label: string }[];
	periodOptions: string[];
	period1: string;
	period2: string;
	groups: FsGroup[];
	values: { period1: Record<string, string>; period2: Record<string, string> };
}

export interface CorporateBalanceSheetPageProps {
	apless: string;
	applNo: string;
	onSaved: (result: { apless: string; applno: string }) => void;
}

const cellLabel =
	"border-b border-slate-100 bg-slate-50/70 px-4 py-2.5 align-top text-[11px] font-medium uppercase tracking-wide text-slate-400 whitespace-nowrap";
const cellValue = "border-b border-slate-100 px-4 py-2.5 align-top text-sm text-slate-700";
const subheadCell =
	"border-b border-slate-100 bg-indigo-50/70 px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-indigo-600";

function SectionHeader({ children }: { children: React.ReactNode }) {
	return (
		<div className="border-b border-t border-slate-200 bg-slate-50 px-6 py-3 first:border-t-0">
			<h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">{children}</h2>
		</div>
	);
}

const inputCls =
	"border border-slate-300 rounded-lg px-2 py-1.5 text-sm w-full text-right focus:outline-none focus:ring-2 focus:ring-blue-400";
const selectCls = (editable: boolean) =>
	`border border-slate-300 rounded-lg px-2 py-1.5 text-sm w-full focus:outline-none focus:ring-2 focus:ring-blue-400 ${
		editable ? "bg-white" : "bg-slate-100 text-slate-400 cursor-not-allowed"
	}`;

const fieldLabelCls = "text-[11px] font-medium uppercase tracking-wide text-slate-400 mb-1 block";

const toNumber = (v: string) => {
	const n = parseFloat((v || "0").replace(/,/g, ""));
	return Number.isFinite(n) ? n : 0;
};
const fmt = (n: number) => n.toLocaleString("en-US", { maximumFractionDigits: 0 });

const numericKeyDown = (allowNegative: boolean) => (e: React.KeyboardEvent<HTMLInputElement>) => {
	const allowed = allowNegative ? /^[\d-]$/ : /^\d$/;
	if (!allowed.test(e.key) && !["Backspace", "Delete", "Tab", "ArrowLeft", "ArrowRight"].includes(e.key)) {
		e.preventDefault();
	}
};

const PeriodPicker: React.FC<{
	label: string;
	options: string[];
	mode: "existing" | "new";
	existingValue: string;
	newYear: string;
	onModeChange: (mode: "existing" | "new") => void;
	onExistingChange: (v: string) => void;
	onNewYearChange: (v: string) => void;
	onDelete: () => void;
	deleting: boolean;
}> = ({ label, options, mode, existingValue, newYear, onModeChange, onExistingChange, onNewYearChange, onDelete, deleting }) => (
	<div className="flex items-end gap-2">
		<div>
			<label className={fieldLabelCls}>{label}</label>
			<div className="flex gap-2">
				<select
					className={selectCls(true)}
					value={mode === "existing" ? existingValue : "__new__"}
					onChange={e => {
						if (e.target.value === "__new__") onModeChange("new");
						else { onModeChange("existing"); onExistingChange(e.target.value); }
					}}
				>
					<option value="__new__">New</option>
					{options.map(p => <option key={p} value={p}>{p}</option>)}
				</select>
				{mode === "new" && (
					<input
						className={selectCls + " w-24"}
						placeholder="yyyy"
						maxLength={4}
						value={newYear}
						onChange={e => onNewYearChange(e.target.value.replace(/\D/g, ""))}
					/>
				)}
			</div>
		</div>
		<button
			onClick={onDelete}
			disabled={deleting}
			className="px-3 py-2 bg-red-700 hover:bg-red-800 disabled:bg-slate-300 text-white rounded-lg text-sm font-medium"
		>
			{deleting ? "Deleting…" : "Delete"}
		</button>
	</div>
);

const CorporateBalanceSheetPage: React.FC<CorporateBalanceSheetPageProps> = ({ apless, applNo, onSaved }) => {
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [saving, setSaving] = useState(false);
	const [deleting1, setDeleting1] = useState(false);
	const [deleting2, setDeleting2] = useState(false);
	const [data, setData] = useState<BalanceSheetData | null>(null);

	const [currency, setCurrency] = useState("IDR");
	const [mode1, setMode1] = useState<"existing" | "new">("existing");
	const [mode2, setMode2] = useState<"existing" | "new">("existing");
	const [existing1, setExisting1] = useState("");
	const [existing2, setExisting2] = useState("");
	const [newYear1, setNewYear1] = useState("");
	const [newYear2, setNewYear2] = useState("");
	const [values1, setValues1] = useState<Record<string, string>>({});
	const [values2, setValues2] = useState<Record<string, string>>({});

	const load = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			const res = await api.get("/CAM/Customer/corporate", { params: { apless, applno: applNo } });
			const d: BalanceSheetData = res.data;
			setData(d);
			setCurrency(d.currency || "IDR");
			setValues1(d.values.period1 || {});
			setValues2(d.values.period2 || {});
			if (d.period1) { setMode1("existing"); setExisting1(d.period1); } else { setMode1("new"); setNewYear1(""); }
			if (d.period2) { setMode2("existing"); setExisting2(d.period2); } else { setMode2("new"); setNewYear2(""); }
		} catch {
			setError("Failed to load balance sheet data. Please try again.");
		} finally {
			setLoading(false);
		}
	}, [apless, applNo]);

	useEffect(() => {
		load();
	}, [load]);

	const setVal = (col: 1 | 2, code: string, value: string) => {
		const clean = value.replace(/[^\d.-]/g, "");
		if (col === 1) setValues1(prev => ({ ...prev, [code]: clean }));
		else setValues2(prev => ({ ...prev, [code]: clean }));
	};

	const groupSubtotal = (group: FsGroup, col: 1 | 2) =>
		group.items.reduce((sum, item) => sum + toNumber((col === 1 ? values1 : values2)[item.code] || "0"), 0);

	const sectionTotal = (section: "asset" | "liability_equity", col: 1 | 2) =>
		(data?.groups || [])
			.filter(g => g.section === section)
			.reduce((sum, g) => sum + groupSubtotal(g, col), 0);

	const handleDelete = async (which: 1 | 2) => {
		const period = which === 1 ? (mode1 === "new" ? newYear1 : existing1) : (mode2 === "new" ? newYear2 : existing2);
		if (!period) {
			alert("Choose the period first please.");
			return;
		}
		if (!window.confirm(`Are you want to delete this period: ${period}`)) return;

		const setDeletingFlag = which === 1 ? setDeleting1 : setDeleting2;
		setDeletingFlag(true);
		try {
			await api.delete("/CAM/Customer/corporate", { params: { apless, period } });
			await load();
		} catch {
			alert("Delete failed. Please try again.");
		} finally {
			setDeletingFlag(false);
		}
	};

	const validatePeriod = (mode: "existing" | "new", existing: string, newYear: string, label: string): string | null => {
		const period = mode === "new" ? newYear.trim() : existing;
		if (!period || period.length !== 4 || !/^\d{4}$/.test(period)) return `${label} not valid`;
		if (Number(period) > new Date().getFullYear()) return `${label} not valid`;
		return null;
	};

	const handleSave = async () => {
		const period1 = mode1 === "new" ? newYear1.trim() : existing1;
		const period2 = mode2 === "new" ? newYear2.trim() : existing2;

		const err1 = validatePeriod(mode1, existing1, newYear1, "Period 1 (Balance Sheet)");
		const err2 = validatePeriod(mode2, existing2, newYear2, "Period 2 (Balance Sheet)");
		if (err1) return alert(err1);
		if (err2) return alert(err2);
		if (period1 && period2 && period1 === period2) return alert("Data Period 1 and 2 must not be the same");

		setSaving(true);
		try {
			const res = await api.post("/CAM/Customer/corporate", {
				apless,
				applno: applNo,
				currency,
				period1: { period: period1, isNew: mode1 === "new", values: values1 },
				period2: { period: period2, isNew: mode2 === "new", values: values2 },
			});
			if (res.data.success) {
				onSaved({ apless: res.data.apless ?? apless, applno: res.data.applno ?? applNo });
			} else {
				alert(res.data.message || "Save failed — one or both periods may already exist.");
			}
		} catch {
			alert("Save failed. Please try again.");
		} finally {
			setSaving(false);
		}
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

	const assetGroups = data.groups.filter(g => g.section === "asset");
	const liabilityGroups = data.groups.filter(g => g.section === "liability_equity");

	const renderGroups = (groups: FsGroup[]) => (
		<>
			{groups.map(group => (
				<React.Fragment key={group.header}>
					<tr>
						<td colSpan={3} className={subheadCell}>{group.header}</td>
					</tr>
					{group.items.map(item => (
						<tr key={item.code}>
							<td className={cellValue}>{item.label}</td>
							<td className={cellValue}>
								<input
									className={inputCls}
									value={values1[item.code] || ""}
									onKeyDown={numericKeyDown(item.allowNegative)}
									onChange={e => setVal(1, item.code, e.target.value)}
								/>
							</td>
							<td className={cellValue}>
								<input
									className={inputCls}
									value={values2[item.code] || ""}
									onKeyDown={numericKeyDown(item.allowNegative)}
									onChange={e => setVal(2, item.code, e.target.value)}
								/>
							</td>
						</tr>
					))}
					<tr>
						<td className={cellValue + " font-semibold"}>TOTAL {group.header}</td>
						<td className={cellValue + " font-semibold text-right"}>{fmt(groupSubtotal(group, 1))}</td>
						<td className={cellValue + " font-semibold text-right"}>{fmt(groupSubtotal(group, 2))}</td>
					</tr>
				</React.Fragment>
			))}
		</>
	);

	const renderSectionTable = (groups: FsGroup[], totalLabel: string, section: "asset" | "liability_equity") => (
		<div className="overflow-x-auto">
			<table className="w-full min-w-[720px] border-collapse text-sm">
				<tbody>
					<tr>
						<td className={cellLabel}>Item</td>
						<td className={cellLabel + " text-right"}>Period 1</td>
						<td className={cellLabel + " text-right"}>Period 2</td>
					</tr>
					{renderGroups(groups)}
					<tr className="bg-slate-50">
						<td className="px-4 py-3 text-sm font-bold text-slate-800">{totalLabel}</td>
						<td className="px-4 py-3 text-sm font-bold text-slate-800 text-right">{fmt(sectionTotal(section, 1))}</td>
						<td className="px-4 py-3 text-sm font-bold text-slate-800 text-right">{fmt(sectionTotal(section, 2))}</td>
					</tr>
				</tbody>
			</table>
		</div>
	);

	return (
		<div>
			<h2 className="text-xl font-bold text-slate-800 mb-1">Neraca (Balance Sheet)</h2>
			<p className="text-sm text-slate-500 mb-4">Customer No. {apless || "(new)"}</p>

			<div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
				<SectionHeader>Currency & Period</SectionHeader>
				<div className="flex flex-wrap items-end gap-6 px-6 py-4">
					<div>
						<label className={fieldLabelCls}>Currency</label>
						<select className={selectCls(true)} value={currency} onChange={e => setCurrency(e.target.value)}>
							{data.currencies.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
						</select>
					</div>
					<PeriodPicker
						label="Period 1" options={data.periodOptions}
						mode={mode1} existingValue={existing1} newYear={newYear1}
						onModeChange={setMode1} onExistingChange={setExisting1} onNewYearChange={setNewYear1}
						onDelete={() => handleDelete(1)} deleting={deleting1}
					/>
					<PeriodPicker
						label="Period 2" options={data.periodOptions}
						mode={mode2} existingValue={existing2} newYear={newYear2}
						onModeChange={setMode2} onExistingChange={setExisting2} onNewYearChange={setNewYear2}
						onDelete={() => handleDelete(2)} deleting={deleting2}
					/>
				</div>

				<SectionHeader>Assets</SectionHeader>
				{renderSectionTable(assetGroups, "TOTAL ASSET", "asset")}

				<SectionHeader>Liabilities & Shareholder's Equity</SectionHeader>
				{renderSectionTable(liabilityGroups, "TOTAL LIABILITIES & SHAREHOLDER'S EQUITY", "liability_equity")}
			</div>

			<div className="flex justify-end gap-3 mt-6">
				<button
					onClick={handleSave}
					disabled={saving}
					className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white rounded-lg text-sm font-medium"
				>
					{saving ? "Saving…" : "Next"}
				</button>
			</div>
		</div>
	);
};

export default CorporateBalanceSheetPage;