import React, { useCallback, useEffect, useMemo, useState } from "react";
import api from "../../../../../api/axiosInstance";

export interface CAMEquipmentBpkbPageProps {
	apless: string;
	applNo: string;
	finType: string;
	newCar: string;
	onSaved: (result: { apless: string; applno: string }) => void;
}

interface LookupOption {
	value: string;
	label: string;
}

interface NotaryOption extends LookupOption {
	npwpNo: string;
	npwpAddrs: string;
}

interface AttorneyRow {
	name: string;
	occupation: string;
	address: string;
}

interface BpkbFormState {
	bpkbNo: string;
	bpkbAnTp: string;
	bpkbAn: string;
	relation: string;
	bpkbAddr: string;
	areaCd: string;
	cityBpkb: string;
	idFam: string;
	placebirth: string;
	tglbirth: string;
	cancelOrder: boolean;
	addCollateral: boolean;
	notaryNo: string;
	npwpNo: string;
	npwpAddrs: string;
}

interface DetailState {
	maritalStatus: string;
	spouseName: string;
	spouseStatus: string;
	spouseAddress: string;
	attorneys: AttorneyRow[];
}

interface Lookups {
	bpkbNameTypes: LookupOption[];
	familyStatuses: LookupOption[];
	maritalStatuses: LookupOption[];
	spouseStatuses: LookupOption[];
	attorneyOccupations: LookupOption[];
	notaries: NotaryOption[];
}

const EMPTY_FORM: BpkbFormState = {
	bpkbNo: "",
	bpkbAnTp: "",
	bpkbAn: "",
	relation: "",
	bpkbAddr: "",
	areaCd: "",
	cityBpkb: "",
	idFam: "",
	placebirth: "",
	tglbirth: "",
	cancelOrder: false,
	addCollateral: false,
	notaryNo: "",
	npwpNo: "",
	npwpAddrs: "",
};

const EMPTY_DETAIL: DetailState = {
	maritalStatus: "-",
	spouseName: "",
	spouseStatus: "-",
	spouseAddress: "",
	attorneys: [{ name: "", occupation: "", address: "" }],
};

const EMPTY_LOOKUPS: Lookups = {
	bpkbNameTypes: [],
	familyStatuses: [],
	maritalStatuses: [],
	spouseStatuses: [],
	attorneyOccupations: [],
	notaries: [],
};

const NOT_FAMILY_CODES = new Set(["40", "50"]);
const LEASING_COMPANY_NORMALIZED = "MITSUILEASINGCAPITALINDONESIAPT";

function normalizeName(value: string): string {
	return (value || "").trim().toUpperCase();
}

function formatBpkbNo(raw: string): string {
	const stripped = raw.toUpperCase().replace(/-/g, "");
	const letters = (stripped.match(/^[A-Za-z]{0,2}/) || [""])[0];
	let formatted = letters;
	if (letters.length > 0) formatted += "-";
	const rest = stripped.slice(letters.length);
	const digits = (rest.match(/^\d{0,8}/) || [""])[0];
	if (formatted.includes("-")) formatted += digits;
	return formatted;
}

function computeIdFams(finType: string, bpkbAnTp: string, namesMatch: boolean, idFam: string): "" | "Family" | "Not Family" {
	if (finType === "F") return "Not Family";
	if (bpkbAnTp !== "PR") return "Not Family";
	if (namesMatch) return "Not Family";
	if (!idFam) return "";
	return NOT_FAMILY_CODES.has(idFam) ? "Not Family" : "Family";
}

const fieldClass =
	"w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-orange-500 focus:outline-none";
const readOnlyFieldClass =
	"w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500";
const labelClass = "mb-1 block text-sm text-slate-600";

const inputCls =
	"border border-slate-300 rounded-lg px-2 py-1.5 text-sm w-full focus:outline-none focus:ring-2 focus:ring-blue-400";
const selectCls = (editable: boolean) =>
	`border border-slate-300 rounded-lg px-2 py-1.5 text-sm w-full focus:outline-none focus:ring-2 focus:ring-blue-400 ${editable ? "bg-white" : "bg-slate-100 text-slate-400 cursor-not-allowed"
	}`;

export default function CAMEquipmentBpkbPage({ apless, applNo, finType, newCar, onSaved }: CAMEquipmentBpkbPageProps) {
	const [loading, setLoading] = useState(true);
	const [saving, setSaving] = useState(false);
	const [loadError, setLoadError] = useState("");
	const [errors, setErrors] = useState<string[]>([]);
	const [warning, setWarning] = useState("");
	const [lesseeName, setLesseeName] = useState("");
	const [carCondition, setCarCondition] = useState("");
	const [form, setForm] = useState<BpkbFormState>(EMPTY_FORM);
	const [detail, setDetail] = useState<DetailState>(EMPTY_DETAIL);
	const [showDetailPanel, setShowDetailPanel] = useState(false);
	const [lookups, setLookups] = useState<Lookups>(EMPTY_LOOKUPS);
	const [areas, setAreas] = useState<LookupOption[]>([]);

	const loadData = useCallback(async () => {
		setLoading(true);
		setLoadError("");
		try {
			const [bpkbRes, areasRes] = await Promise.all([
				api.get("/CAM/EditIndex/bpkb", { params: { apless, applno: applNo } }),
				api.get("/CAM/Combo/provinces-and-cities"),
			]);
			const d = bpkbRes.data || {};
			setLesseeName(d.lesseeName || "");
			setCarCondition(d.carCondition || "");
			setForm({
				bpkbNo: formatBpkbNo(d.bpkb?.bpkbNo || ""),
				bpkbAnTp: d.bpkb?.bpkbAnTp || "",
				bpkbAn: d.bpkb?.bpkbAn || "",
				relation: d.bpkb?.relation || "",
				bpkbAddr: d.bpkb?.bpkbAddr || "",
				areaCd: d.bpkb?.areaCd || "",
				cityBpkb: d.bpkb?.cityBpkb || "",
				idFam: d.bpkb?.idFam || "",
				placebirth: d.bpkb?.placebirth || "",
				tglbirth: d.bpkb?.tglbirth || "",
				cancelOrder: !!d.bpkb?.cancelOrder,
				addCollateral: !!d.bpkb?.addCollateral,
				notaryNo: d.notary?.notaryNo || "",
				npwpNo: d.notary?.npwpNo || "",
				npwpAddrs: d.notary?.npwpAddrs || "",
			});
			setDetail({
				maritalStatus: d.detail?.maritalStatus || "-",
				spouseName: d.detail?.spouseName || "",
				spouseStatus: d.detail?.spouseStatus || "-",
				spouseAddress: d.detail?.spouseAddress || "",
				attorneys: d.detail?.attorneys?.length ? d.detail.attorneys : [{ name: "", occupation: "", address: "" }],
			});
			setLookups({
				bpkbNameTypes: d.lookups?.bpkbNameTypes || [],
				familyStatuses: d.lookups?.familyStatuses || [],
				maritalStatuses: d.lookups?.maritalStatuses || [],
				spouseStatuses: d.lookups?.spouseStatuses || [],
				attorneyOccupations: d.lookups?.attorneyOccupations || [],
				notaries: d.lookups?.notaries || [],
			});
			setAreas(areasRes.data || []);
		} catch {
			setLoadError("Failed to load BPKB data.");
		} finally {
			setLoading(false);
		}
	}, [apless, applNo]);

	useEffect(() => {
		loadData();
	}, [loadData]);

	const isPR = form.bpkbAnTp === "PR";

	const namesMatch = useMemo(() => {
		const a = normalizeName(form.bpkbAn);
		const b = normalizeName(lesseeName);
		return a !== "" && a === b;
	}, [form.bpkbAn, lesseeName]);

	const isCompanyItself = useMemo(
		() => normalizeName(form.bpkbAn).replace(/ /g, "") === LEASING_COMPANY_NORMALIZED,
		[form.bpkbAn]
	);

	const idFams = useMemo(
		() => computeIdFams(finType, form.bpkbAnTp, namesMatch, form.idFam),
		[finType, form.bpkbAnTp, namesMatch, form.idFam]
	);

	const carIsNew = carCondition === "NEW";
	const showFamilyDropdown = isPR;
	const showCancelOrder = finType === "I" && carIsNew && idFams === "Not Family" && !namesMatch;
	const detailTriggerActive = form.bpkbAnTp !== "" && !namesMatch && newCar === "2" && idFams === "Not Family";
	const relationReadOnly = namesMatch;
	const relationRequired = !namesMatch && !isCompanyItself && finType !== "F";
	const showPlaceDob = isPR;
	const placeDobRequired = carCondition !== "USED";
	const notaryVisible = finType !== "F";
	const notaryRequired = notaryVisible && finType !== "S" && finType !== "W";
	const npwpEditable = finType !== "W";
	const nameTypeReadOnly = form.bpkbAnTp === "PT" && finType === "F";
	const areaRequired = finType !== "W";

	useEffect(() => {
		if (detailTriggerActive && (detail.spouseName.trim() !== "" || detail.attorneys.some(a => a.name.trim() !== ""))) {
			setShowDetailPanel(true);
		}
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [detailTriggerActive]);

	const handleAreaChange = async (areaCd: string) => {
		if (!areaCd) {
			setForm(f => ({ ...f, areaCd: "", cityBpkb: "" }));
			return;
		}
		setForm(f => ({ ...f, areaCd }));
		try {
			const res = await api.get("/CAM/Combo/province-city", { params: { areaCd } });
			setForm(f => ({ ...f, cityBpkb: res.data?.city || f.cityBpkb }));
		} catch { }
	};

	const handleNotaryChange = (notaryNo: string) => {
		const match = lookups.notaries.find(n => n.value === notaryNo);
		setForm(f => ({ ...f, notaryNo, npwpNo: match?.npwpNo || "", npwpAddrs: match?.npwpAddrs || "" }));
	};

	const handleResetName = async () => {
		if (!window.confirm("Reset BPKB name, address, and city?")) return;
		try {
			const res = await api.post("/CAM/EditIndex/bpkb/reset-name", { apless, applno: applNo });
			if (res.data?.success) {
				setForm(f => ({ ...f, bpkbAn: "", bpkbAddr: "", cityBpkb: "" }));
			} else {
				setLoadError(res.data?.message || "Failed to reset name.");
			}
		} catch (err: any) {
			setLoadError(err?.response?.data?.message || "Failed to reset name.");
		}
	};

	const addAttorney = () =>
		setDetail(d => ({ ...d, attorneys: [...d.attorneys, { name: "", occupation: "", address: "" }] }));

	const removeAttorney = (idx: number) =>
		setDetail(d => (d.attorneys.length > 1 ? { ...d, attorneys: d.attorneys.filter((_, i) => i !== idx) } : d));

	const updateAttorney = (idx: number, patch: Partial<AttorneyRow>) =>
		setDetail(d => ({ ...d, attorneys: d.attorneys.map((a, i) => (i === idx ? { ...a, ...patch } : a)) }));

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		setSaving(true);
		setErrors([]);
		setWarning("");
		setLoadError("");
		try {
			const res = await api.post("/CAM/EditIndex/bpkb", {
				apless,
				applno: applNo,
				newCar,
				bpkbNo: form.bpkbNo,
				bpkbAnTp: form.bpkbAnTp,
				bpkbAn: form.bpkbAn,
				relation: form.relation,
				bpkbAddr: form.bpkbAddr,
				areaCd: form.areaCd,
				cityBpkb: form.cityBpkb,
				idFam: form.idFam,
				placebirth: form.placebirth,
				tglbirth: form.tglbirth,
				cancelOrder: form.cancelOrder,
				addCollateral: form.addCollateral,
				notaryNo: form.notaryNo,
				detail: isPR
					? {
						maritalStatus: detail.maritalStatus,
						spouseName: detail.spouseName,
						spouseStatus: detail.spouseStatus,
						spouseAddress: detail.spouseAddress,
						attorneys: [],
					}
					: {
						maritalStatus: "-",
						spouseName: "",
						spouseStatus: "-",
						spouseAddress: "",
						attorneys: detail.attorneys,
					},
			});
			if (!res.data.success) {
				setErrors(res.data.errors?.length ? res.data.errors : [res.data.message || "Save failed."]);
				return;
			}
			if (res.data.warning) setWarning(res.data.warning);
			onSaved({ apless, applno: applNo });
		} catch (err: any) {
			setErrors([err?.response?.data?.message || "Save failed. Please try again."]);
		} finally {
			setSaving(false);
		}
	};

	if (loading) {
		return (
			<div className="rounded-2xl bg-white p-8 text-center shadow">
				<p className="text-sm text-slate-400">Loading…</p>
			</div>
		);
	}

	return (
		<form onSubmit={handleSubmit} className="space-y-4 rounded-2xl bg-white p-6 shadow">
			<h2 className="text-base font-semibold text-slate-700">BPKB</h2>

			{loadError && <p className="text-sm text-red-600">{loadError}</p>}

			<div>
				<label className={labelClass}>BPKB No</label>
				<input
					type="text"
					maxLength={50}
					value={form.bpkbNo}
					onChange={e => setForm(f => ({ ...f, bpkbNo: formatBpkbNo(e.target.value) }))}
					placeholder="AB-12345678"
					className={fieldClass}
				/>
			</div>

			<div>
				<label className={labelClass}>BPKB Name Type *</label>
				{nameTypeReadOnly ? (
					<input
						type="text"
						readOnly
						value={lookups.bpkbNameTypes.find(o => o.value === form.bpkbAnTp)?.label || form.bpkbAnTp}
						className={readOnlyFieldClass}
					/>
				) : (
					<select
						required
						value={form.bpkbAnTp}
						onChange={e => setForm(f => ({ ...f, bpkbAnTp: e.target.value }))}
						className={selectCls(true)}
					>
						<option value="">Select</option>
						{lookups.bpkbNameTypes.map(o => (
							<option key={o.value} value={o.value}>
								{o.label}
							</option>
						))}
					</select>
				)}
				{detailTriggerActive && (
					<button
						type="button"
						onClick={() => setShowDetailPanel(s => !s)}
						className="mt-2 text-sm font-medium text-blue-600 hover:underline"
					>
						{showDetailPanel ? "Hide BPKB name detail" : "BPKB name detail"}
					</button>
				)}
			</div>

			{showDetailPanel && detailTriggerActive && (
				<div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
					<h3 className="mb-3 text-sm font-semibold text-slate-700">BPKB Name Detail</h3>
					{isPR ? (
						<div className="space-y-3">
							<div>
								<label className={labelClass}>BPKB Name Marital Status *</label>
								<select
									required
									value={detail.maritalStatus}
									onChange={e => setDetail(d => ({ ...d, maritalStatus: e.target.value }))}
									className={fieldClass}
								>
									<option value="-">Select</option>
									{lookups.maritalStatuses.map(o => (
										<option key={o.value} value={o.value}>
											{o.label}
										</option>
									))}
								</select>
							</div>
							<div>
								<label className={labelClass}>Spouse BPKB Name {detail.maritalStatus === "M" && "*"}</label>
								<input
									type="text"
									readOnly={detail.maritalStatus !== "M"}
									value={detail.spouseName}
									onChange={e => setDetail(d => ({ ...d, spouseName: e.target.value }))}
									className={detail.maritalStatus !== "M" ? readOnlyFieldClass : fieldClass}
								/>
							</div>
							<div>
								<label className={labelClass}>Spouse BPKB Status {detail.maritalStatus === "M" && "*"}</label>
								<select
									required={detail.maritalStatus === "M"}
									value={detail.spouseStatus}
									onChange={e => setDetail(d => ({ ...d, spouseStatus: e.target.value }))}
									className={fieldClass}
								>
									<option value="-">Select</option>
									{lookups.spouseStatuses.map(o => (
										<option key={o.value} value={o.value}>
											{o.label}
										</option>
									))}
								</select>
							</div>
							<div>
								<label className={labelClass}>Spouse BPKB Address {detail.maritalStatus === "M" && "*"}</label>
								<textarea
									readOnly={detail.maritalStatus !== "M"}
									value={detail.spouseAddress}
									onChange={e => setDetail(d => ({ ...d, spouseAddress: e.target.value }))}
									className={detail.maritalStatus !== "M" ? readOnlyFieldClass : fieldClass}
								/>
							</div>
						</div>
					) : (
						<div className="space-y-3">
							<p className="text-sm text-slate-500">Signer(s) on Power of Attorney (POA)</p>
							{detail.attorneys.map((a, idx) => (
								<div key={idx} className="space-y-2 rounded-lg border border-slate-200 bg-white p-3">
									<div className="flex items-center justify-between">
										<span className="text-xs font-medium text-slate-500">Attorney {idx + 1}</span>
										{detail.attorneys.length > 1 && (
											<button
												type="button"
												onClick={() => removeAttorney(idx)}
												className="text-xs font-medium text-red-600 hover:underline"
											>
												Remove
											</button>
										)}
									</div>
									<input
										type="text"
										required
										placeholder="Name"
										value={a.name}
										onChange={e => updateAttorney(idx, { name: e.target.value })}
										className={fieldClass}
									/>
									<select
										required
										value={a.occupation}
										onChange={e => updateAttorney(idx, { occupation: e.target.value })}
										className={fieldClass}
									>
										<option value="">Occupation</option>
										{lookups.attorneyOccupations.map(o => (
											<option key={o.value} value={o.value}>
												{o.label}
											</option>
										))}
									</select>
									<textarea
										required
										placeholder="Address"
										value={a.address}
										onChange={e => updateAttorney(idx, { address: e.target.value })}
										className={fieldClass}
									/>
								</div>
							))}
							<button
								type="button"
								onClick={addAttorney}
								className="rounded-lg bg-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-300"
							>
								+ Add attorney
							</button>
						</div>
					)}
				</div>
			)}

			<div>
				<label className={labelClass}>BPKB Name *</label>
				<div className="flex gap-2">
					<input
						type="text"
						required
						value={form.bpkbAn}
						onChange={e => setForm(f => ({ ...f, bpkbAn: e.target.value }))}
						className={fieldClass}
					/>
					<button
						type="button"
						onClick={handleResetName}
						className="shrink-0 rounded-lg bg-slate-200 px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-300"
					>
						Reset Name
					</button>
				</div>
				{showCancelOrder && (
					<label className="mt-2 flex items-center gap-2 text-sm text-slate-600">
						<input
							type="checkbox"
							checked={form.cancelOrder}
							onChange={e => setForm(f => ({ ...f, cancelOrder: e.target.checked }))}
						/>
						Cancellation Order
					</label>
				)}
			</div>

			{showPlaceDob && (
				<div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
					<div>
						<label className={labelClass}>Place of Birth {placeDobRequired && "*"}</label>
						<input
							type="text"
							maxLength={30}
							required={placeDobRequired}
							value={form.placebirth}
							onChange={e => setForm(f => ({ ...f, placebirth: e.target.value }))}
							className={fieldClass}
						/>
					</div>
					<div>
						<label className={labelClass}>Date of Birth {placeDobRequired && "*"}</label>
						<input
							type="date"
							required={placeDobRequired}
							value={form.tglbirth}
							onChange={e => setForm(f => ({ ...f, tglbirth: e.target.value }))}
							className={fieldClass}
						/>
					</div>
				</div>
			)}

			{showFamilyDropdown &&
				(namesMatch ? (
					<div>
						<label className={labelClass}>Family Status</label>
						<p className={readOnlyFieldClass}>Not applicable — BPKB name matches the customer.</p>
					</div>
				) : (
					<div>
						<label className={labelClass}>Family Status *</label>
						<select
							required
							value={form.idFam}
							onChange={e => setForm(f => ({ ...f, idFam: e.target.value }))}
							className={fieldClass}
						>
							<option value="">Select</option>
							{lookups.familyStatuses.map(o => (
								<option key={o.value} value={o.value}>
									{o.label}
								</option>
							))}
						</select>
					</div>
				))}

			<div>
				<label className={labelClass}>Relationship With Customer {relationRequired && "*"}</label>
				<input
					type="text"
					readOnly={relationReadOnly}
					required={relationRequired}
					value={form.relation}
					onChange={e => setForm(f => ({ ...f, relation: e.target.value }))}
					className={relationReadOnly ? readOnlyFieldClass : fieldClass}
				/>
			</div>

			<div>
				<label className={labelClass}>BPKB Address *</label>
				<textarea
					required
					rows={3}
					value={form.bpkbAddr}
					onChange={e => setForm(f => ({ ...f, bpkbAddr: e.target.value }))}
					className={fieldClass}
				/>
			</div>

			<div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
				<div>
					<label className={labelClass}>Area {areaRequired && "*"}</label>
					<select
						required={areaRequired}
						value={form.areaCd}
						onChange={e => handleAreaChange(e.target.value)}
						className={selectCls(true)}
					>
						<option value="">Select</option>
						{areas.map(o => (
							<option key={o.value} value={o.value}>
								{o.label}
							</option>
						))}
					</select>
				</div>
				<div>
					<label className={labelClass}>City *</label>
					<input
						type="text"
						required
						maxLength={20}
						value={form.cityBpkb}
						onChange={e => setForm(f => ({ ...f, cityBpkb: e.target.value }))}
						className={fieldClass}
					/>
				</div>
			</div>

			<label className="flex items-center gap-2 text-sm text-slate-600">
				<input
					type="checkbox"
					checked={form.addCollateral}
					onChange={e => setForm(f => ({ ...f, addCollateral: e.target.checked }))}
				/>
				Additional Collateral
			</label>

			{notaryVisible && (
				<div className="space-y-3 border-t border-slate-100 pt-4">
					<div>
						<label className={labelClass}>Notary Name {notaryRequired && "*"}</label>
						<select
							required={notaryRequired}
							value={form.notaryNo}
							onChange={e => handleNotaryChange(e.target.value)}
							className={selectCls(true)}
						>
							<option value="">Select</option>
							{lookups.notaries.map(o => (
								<option key={o.value} value={o.value}>
									{o.label}
								</option>
							))}
						</select>
					</div>
					<div>
						<label className={labelClass}>NPWP</label>
						<input type="text" readOnly value={npwpEditable ? form.npwpNo : ""} className={readOnlyFieldClass} />
					</div>
					<div>
						<label className={labelClass}>NPWP Address</label>
						<textarea readOnly value={npwpEditable ? form.npwpAddrs : ""} className={readOnlyFieldClass} />
					</div>
				</div>
			)}

			{errors.length > 0 && (
				<div className="rounded-lg bg-red-50 p-3 text-sm text-red-600">
					<ul className="list-disc pl-4">
						{errors.map((msg, i) => (
							<li key={i}>{msg}</li>
						))}
					</ul>
				</div>
			)}
			{warning && <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-700">{warning}</p>}

			<div className="flex justify-end pt-2">
				<button
					type="submit"
					disabled={saving}
					className="rounded-lg bg-orange-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-orange-600 disabled:opacity-50"
				>
					{saving ? "Saving…" : "Next"}
				</button>
			</div>
		</form>
	);
}