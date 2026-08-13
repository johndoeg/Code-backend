import React, { useEffect, useState, useCallback } from "react";
import api from "../../../../api/axiosInstance";
import { buildCamMenu } from "./CAMEditTabs";
import type { CamMenuCtx, CamMenuItem } from "./CAMEditTabs";

interface LookupOption {
	value: string;
	label: string;
	selected?: boolean;
}

interface EditIndexData {
	apless: string;
	applno: string;
	finType: string;
	purpoffinc: string;
	contType: string;
	guarantor: string;
	newCar: string;
	goPublic: string;
	restructuringChange: string;
	boa: string;
	bot: string;
	lookups: {
		purposes: LookupOption[];
		financeTypes: LookupOption[];
		contractTypes: LookupOption[];
		restructuringChanges: LookupOption[];
	};
}

interface DpConfirmation {
	asOfDate: string;
	periodFrom: string;
	periodTo: string;
	npfRatio: number;
	minDpInvestasi: number;
	minDpMultiguna: number;
}

export interface CamEditDoneResult {
	apless: string;
	applNo: string;
	ctx: CamMenuCtx;
	menu: CamMenuItem[];
	purpoffinc: string;
	contType: string;
	restructuringChange: string;
	goPublic: string;
}

export interface CamEditPageProps {
	apless: string;
	applNo: string;
	indCor: string;
	c2c?: string;
	akseskhusus?: boolean;
	onDone: (result: CamEditDoneResult) => void;
	onClose: () => void;
}

const inputCls =
	"border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 w-full";
const labelCls = "text-sm font-semibold text-slate-700 mb-1 block";
const sectionCls = "mb-5";

const CamEditPage: React.FC<CamEditPageProps> = ({
	apless, applNo, indCor: initialIndCor, c2c = "", akseskhusus, onDone, onClose,
}) => {
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [blockedMessage, setBlockedMessage] = useState<string | null>(null);

	const [data, setData] = useState<EditIndexData | null>(null);

	const [finType, setFinType] = useState("");
	const [purpoffinc, setPurpoffinc] = useState("");
	const [contType, setContType] = useState("");
	const [guarantor, setGuarantor] = useState("");
	const [newCar, setNewCar] = useState("");
	const [indCor, setIndCor] = useState(initialIndCor);
	const [goPublic, setGoPublic] = useState("");
	const [restructuringChange, setRestructuringChange] = useState("");

	const [boa, setBoa] = useState("");
	const [bot, setBot] = useState("");

	const [financeTypeOptions, setFinanceTypeOptions] = useState<LookupOption[]>([]);
	const [contractTypeOptions, setContractTypeOptions] = useState<LookupOption[]>([]);

	const [financeTypeResetWarning, setFinanceTypeResetWarning] = useState(false);

	const [submitting, setSubmitting] = useState(false);
	const [errors, setErrors] = useState<Record<string, string>>({});

	const [dpConfirm, setDpConfirm] = useState<DpConfirmation | null>(null);
	const [dpConfirmLoading, setDpConfirmLoading] = useState(false);

	const load = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			const res = await api.get("/CAM/EditIndex/get-data", { params: { apless, applno: applNo } });
			if (res.data.blocked) {
				setBlockedMessage(res.data.message || "This application can't be edited right now.");
				return;
			}
			const d: EditIndexData = res.data;
			setData(d);
			setFinType(d.finType);
			setPurpoffinc(d.purpoffinc);
			setContType(d.contType);
			setGuarantor(d.guarantor);
			setNewCar(d.newCar);
			setGoPublic(d.goPublic);
			setRestructuringChange(d.restructuringChange);
			setBoa(d.boa);
			setBot(d.bot);
			setFinanceTypeOptions(d.lookups.financeTypes);
			setContractTypeOptions(d.lookups.contractTypes);
		} catch {
			setError("Failed to load application data. Please try again.");
		} finally {
			setLoading(false);
		}
	}, [apless, applNo]);

	useEffect(() => {
		load();
	}, [load]);

	const handlePurposeChange = async (value: string) => {
		setPurpoffinc(value);
		setFinType("");
		try {
			const res = await api.get("/CAM/EditIndex/finance-types", { params: { purpoffinc: value } });
			setFinanceTypeOptions(res.data);
		} catch {
			setFinanceTypeOptions([]);
		}
	};

	const handleFinTypeChange = async (value: string) => {
		setFinanceTypeResetWarning(data ? value !== data.finType : false);
		setFinType(value);
		if ((value === "S" || value === "D") && newCar === "2") {
			setNewCar("1");
		}
		try {
			const res = await api.get("/CAM/EditIndex/contract-types", { params: { finType: value } });
			const options: LookupOption[] = res.data;
			setContractTypeOptions(options);
			const selected = options.find(o => o.selected);
			if (selected) setContType(selected.value);
		} catch {
		}
	};

	const handleIndCorChange = (value: string) => {
		setIndCor(value);
		if (value === "1") {
			setGoPublic("");
		}
	};

	const handleGoPublicChange = (value: string) => {
		setGoPublic(value);
		if (value === "1") {
			setBoa("1");
			setBot("");
		}
	};

	const validate = (): boolean => {
		const next: Record<string, string> = {};
		if (!guarantor) next.guarantor = "Guarantor availability must not be empty";
		if (!purpoffinc) next.purpoffinc = "Purpose of Finance must not be empty";
		if (!newCar) next.newCar = "Vehicle condition must not be empty";
		if (!contType) next.contType = "Contract Type must not be empty";
		if (!boa) next.boa = "Beneficial Owner Availability must not be empty";
		if (boa === "2" && !bot) next.bot = "Beneficial Owner Type must not be empty";
		if ((contType === "RS1" || contType === "RS0") && !restructuringChange) {
			next.restructuringChange = "Changes from Restructuring can't be empty";
		}
		if (indCor === "2" && !goPublic) next.goPublic = "Go Public must not be empty";
		setErrors(next);
		return Object.keys(next).length === 0;
	};

	const handleSubmitClick = async () => {
		if (!validate()) return;
		setDpConfirmLoading(true);
		try {
			const res = await api.get("/CAM/EditIndex/dp-confirmation", { params: { applno: applNo } });
			setDpConfirm(res.data);
		} catch {
			await doSubmit();
		} finally {
			setDpConfirmLoading(false);
		}
	};

	const doSubmit = async () => {
		setSubmitting(true);
		try {
			const res = await api.post("/CAM/EditIndex/submit", {
				apless,
				applno: applNo,
				finType,
				purpoffinc,
				indCor,
				guarantor,
				newCar,
				contType,
				restructuringChange,
				goPublic,
				boa,
				bot,
			});
			if (res.data.success) {
				if (res.data.financeTypeReset) {
					alert("You changed the Financing Type — BPKB and financing details have been cleared, please re-fill them.");
				} else if (res.data.purposeReset) {
					alert("You changed the Purpose of Finance — BPKB and financing details have been cleared, please re-fill them.");
				}

				const ctx: CamMenuCtx = {
					finType, indCor, guarantor, newCar, status: "Edit", c2c, boa, bot, akseskhusus,
				};
				onDone({
					apless, applNo, ctx, menu: buildCamMenu(ctx),
					purpoffinc, contType, restructuringChange, goPublic,
				});
			} else if (res.data.errors) {
				setErrors(res.data.errors);
			} else {
				alert(res.data.message || "Save failed. Please try again.");
			}
		} catch {
			alert("Save failed. Please try again.");
		} finally {
			setSubmitting(false);
			setDpConfirm(null);
		}
	};

	const selectCls = (enabled: boolean) =>
		`border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 w-full ${
			enabled ? "bg-white" : "bg-slate-100 text-slate-400 cursor-not-allowed"
	}`;

	if (blockedMessage) {
		return (
			<div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6">
				<h3 className="text-lg font-bold text-red-600 mb-2">Can't Edit This Application</h3>
				<p className="text-gray-700 mb-6 text-sm">{blockedMessage}</p>
				<div className="flex justify-end">
					<button onClick={onClose} className="px-4 py-2 bg-slate-600 hover:bg-slate-700 text-white rounded-lg text-sm">
						Close
					</button>
				</div>
			</div>
		);
	}

	return (
		<div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6">
			<div className="flex items-center justify-between mb-4">
				<h2 className="text-xl font-bold text-slate-800">Edit CAM — {applNo}</h2>
				<button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-2xl leading-none">&times;</button>
			</div>

			{loading ? (
				<div className="flex justify-center py-16">
					<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
				</div>
			) : error ? (
				<div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm flex items-center justify-between">
					{error}
					<button onClick={load} className="underline ml-4">Retry</button>
				</div>
			) : data ? (
				<div>
					<div className={sectionCls}>
						<label className={labelCls}>Purpose of Finance</label>
						<select className={selectCls(true)} value={purpoffinc} onChange={e => handlePurposeChange(e.target.value)}>
							<option value="">Select</option>
							{data.lookups.purposes.map(o => (
								<option key={o.value} value={o.value}>{o.label}</option>
							))}
						</select>
						{errors.purpoffinc && <p className="text-red-600 text-xs mt-1">{errors.purpoffinc}</p>}
					</div>

					<div className={sectionCls}>
						<label className={labelCls}>Finance Type</label>
						<select className={selectCls(!!purpoffinc)} value={finType} onChange={e => handleFinTypeChange(e.target.value)}>
							<option value="">Select</option>
							{financeTypeOptions.map(o => (
								<option key={o.value} value={o.value}>{o.label}</option>
							))}
						</select>
						{financeTypeResetWarning && (
							<p className="text-amber-600 text-xs mt-1">
								Changing the Financing Type will clear BPKB and financing details for this application.
							</p>
						)}
					</div>

					<div className={sectionCls}>
						<label className={labelCls}>Contract Type</label>
						<select
							className={selectCls(!!finType)}
							value={contType}
							onChange={e => setContType(e.target.value)}
						>
							<option value="">Select</option>
							{contractTypeOptions.map(o => (
								<option key={o.value} value={o.value}>{o.label}</option>
							))}
						</select>
						{errors.contType && <p className="text-red-600 text-xs mt-1">{errors.contType}</p>}
					</div>

					{(contType === "RS1" || contType === "RS0") && (
						<div className={sectionCls}>
							<label className={labelCls}>Changes from Restructuring</label>
							<select
								className={inputCls}
								value={restructuringChange}
								onChange={e => setRestructuringChange(e.target.value)}
							>
								<option value="">Select</option>
								{data.lookups.restructuringChanges.map(o => (
									<option key={o.value} value={o.value}>{o.label}</option>
								))}
							</select>
							{errors.restructuringChange && (
								<p className="text-red-600 text-xs mt-1">{errors.restructuringChange}</p>
							)}
						</div>
					)}

					<div className={sectionCls}>
						<label className={labelCls}>Customer Type</label>
						<div className="flex gap-6">
							<label className="flex items-center gap-2 text-sm">
								<input type="radio" name="indCor" checked={indCor === "1"} onChange={() => handleIndCorChange("1")} />
								Individu
							</label>
							<label className="flex items-center gap-2 text-sm">
								<input type="radio" name="indCor" checked={indCor === "2"} onChange={() => handleIndCorChange("2")} />
								Corporate
							</label>
						</div>
					</div>

					<div className={sectionCls}>
						<label className={labelCls}>Vehicle Condition</label>
						<div className="flex gap-6">
							<label className="flex items-center gap-2 text-sm">
								<input type="radio" name="newCar" checked={newCar === "1"} onChange={() => setNewCar("1")} />
								Used
							</label>
							<label className="flex items-center gap-2 text-sm">
								<input
									type="radio"
									name="newCar"
									checked={newCar === "2"}
									disabled={finType === "S" || finType === "D"}
									onChange={() => setNewCar("2")}
								/>
								New
							</label>
						</div>
						{errors.newCar && <p className="text-red-600 text-xs mt-1">{errors.newCar}</p>}
					</div>

					<div className={sectionCls}>
						<label className={labelCls}>Guarantor Availability</label>
						<div className="flex gap-6">
							<label className="flex items-center gap-2 text-sm">
								<input type="radio" name="guarantor" checked={guarantor === "1"} onChange={() => setGuarantor("1")} />
								No
							</label>
							<label className="flex items-center gap-2 text-sm">
								<input type="radio" name="guarantor" checked={guarantor === "2"} onChange={() => setGuarantor("2")} />
								Yes
							</label>
						</div>
						{errors.guarantor && <p className="text-red-600 text-xs mt-1">{errors.guarantor}</p>}
					</div>

					{indCor === "2" && (
						<div className={sectionCls}>
							<label className={labelCls}>Go Public</label>
							<div className="flex gap-6">
								<label className="flex items-center gap-2 text-sm">
									<input type="radio" name="goPublic" checked={goPublic === "0"} onChange={() => handleGoPublicChange("0")} />
									No
								</label>
								<label className="flex items-center gap-2 text-sm">
									<input type="radio" name="goPublic" checked={goPublic === "1"} onChange={() => handleGoPublicChange("1")} />
									Yes
								</label>
							</div>
							{errors.goPublic && <p className="text-red-600 text-xs mt-1">{errors.goPublic}</p>}
						</div>
					)}

					{goPublic !== "1" && (
						<div className={sectionCls}>
							<label className={labelCls}>Beneficial Owner Availability</label>
							<div className="flex gap-6">
								<label className="flex items-center gap-2 text-sm">
									<input type="radio" name="boa" checked={boa === "2"} onChange={() => setBoa("2")} />
									Available
								</label>
								<label className="flex items-center gap-2 text-sm">
									<input type="radio" name="boa" checked={boa === "1"} onChange={() => { setBoa("1"); setBot(""); }} />
									Not Available
								</label>
							</div>
							{errors.boa && <p className="text-red-600 text-xs mt-1">{errors.boa}</p>}

							{boa === "2" && (
								<div className="mt-3">
									<label className={labelCls}>Beneficial Owner Type</label>
									<div className="flex gap-6">
										<label className="flex items-center gap-2 text-sm">
											<input type="radio" name="bot" checked={bot === "1"} onChange={() => setBot("1")} />
											Individu
										</label>
										<label className="flex items-center gap-2 text-sm">
											<input type="radio" name="bot" checked={bot === "2"} onChange={() => setBot("2")} />
											Corporate
										</label>
									</div>
									{errors.bot && <p className="text-red-600 text-xs mt-1">{errors.bot}</p>}
								</div>
							)}
						</div>
					)}

					<div className="flex justify-end gap-3 mt-6 pt-4 border-t border-slate-100">
						<button
							onClick={onClose}
							className="px-4 py-2 border border-slate-300 rounded-lg text-slate-600 hover:bg-slate-50 text-sm"
						>
							Cancel
						</button>
						<button
							onClick={handleSubmitClick}
							disabled={submitting || dpConfirmLoading}
							className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white rounded-lg text-sm font-medium"
						>
							{dpConfirmLoading ? "Checking…" : "Submit"}
						</button>
					</div>
				</div>
			) : null}

			{dpConfirm && (
				<div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[60] p-4">
					<div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6">
						<h3 className="text-lg font-bold text-slate-800 mb-4">Minimum DP for Installment Financing Contract</h3>
						<table className="w-full text-sm mb-4">
							<tbody>
								<tr className="border-b border-slate-100">
									<td className="py-2 font-semibold">As Of</td>
									<td className="py-2 text-right">{dpConfirm.asOfDate}</td>
								</tr>
								<tr className="border-b border-slate-100">
									<td className="py-2 font-semibold">NPF Ratio</td>
									<td className="py-2 text-right">{dpConfirm.npfRatio}%</td>
								</tr>
								<tr className="border-b border-slate-100">
									<td className="py-2 font-semibold">Period</td>
									<td className="py-2 text-right">{dpConfirm.periodFrom} – {dpConfirm.periodTo}</td>
								</tr>
								<tr className="border-b border-slate-100">
									<td className="py-2 font-semibold">Min. DP — Investasi</td>
									<td className="py-2 text-right">{dpConfirm.minDpInvestasi}%</td>
								</tr>
								<tr>
									<td className="py-2 font-semibold">Min. DP — Multiguna</td>
									<td className="py-2 text-right">{dpConfirm.minDpMultiguna}%</td>
								</tr>
							</tbody>
						</table>
						<div className="flex justify-end gap-3">
							<button
								onClick={() => setDpConfirm(null)}
								className="px-4 py-2 border border-slate-300 rounded-lg text-slate-600 hover:bg-slate-50 text-sm"
							>
								Cancel
							</button>
							<button
								onClick={doSubmit}
								disabled={submitting}
								className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white rounded-lg text-sm font-medium"
							>
								{submitting ? "Saving…" : "Yes"}
							</button>
						</div>
					</div>
				</div>
			)}
		</div>
	);
};

export default CamEditPage;