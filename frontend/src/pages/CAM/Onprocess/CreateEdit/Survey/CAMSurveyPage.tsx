import { useCallback, useEffect, useMemo, useState } from "react";
import api from "../../../../../api/axiosInstance";

export interface CAMSurveyPageProps {
	apless: string;
	applNo: string;
	indCor: "1" | "2";
	onSaved: (result: { apless: string; applno: string }) => void;
	onHome?: () => void;
}

interface ComboOption {
	value: string;
	label: string;
}

interface SikDocument {
	subject?: string;
	description?: string;
	creditBureau?: string;
	relatedParty?: string;
	status?: string;
	type?: string;
	score?: string;
	grade?: string;
	downloadUrl?: string | null;
}

interface Lookups {
	creditHistory: ComboOption[];
	reference: ComboOption[];
	workExp: ComboOption[];
	dp: ComboOption[];
	sourceOfFund: ComboOption[];
	businessSize: ComboOption[];
	paymentMethod?: ComboOption[];
	livingType?: ComboOption[];
	livingStatusHouse?: ComboOption[];
	livingStatusApartment?: ComboOption[];
	carOwnership?: ComboOption[];
	spouseJob?: ComboOption[];
	companyStatus?: ComboOption[];
	businessScale?: ComboOption[];
	businessLocation?: ComboOption[];
	unitOwned?: ComboOption[];
	unitFree?: ComboOption[];
	netProfitRatio?: ComboOption[];
	estimatedAsset?: ComboOption[];
}

interface IndividualForm {
	creditHis: string;
	reference: string;
	workExp: string;
	businessSize: string;
	businessSizeDisabled: boolean;
	noteChar: string;
	living: string;
	livingSts: string;
	carOwn: string;
	deposit: boolean;
	bankStat: boolean;
	depositAmt: number | string;
	bankStatAmt: string;
	noteCapital: string;
	fixInc: number;
	fixIncSource: string;
	fixIncSourceOther: string;
	spouseMaritalDisabled: boolean;
	spouseJob: string;
	spouseIncome: number;
	totOthInc: number;
	totOthIncSource: string;
	totOthIncSourceOther: string;
	totInc: number;
	totIncYear: number;
	totCredit: number | string;
	noteCapacity: string;
	dp: string;
	pmt: string;
	noteCollateral: string;
	noteSid: string;
}

interface CorporateForm {
	creditHis: string;
	reference: string;
	workExp: string;
	companyStatus: string;
	scale: string;
	businessSize: string;
	noteChar: string;
	businessLocation: string;
	unitOwned: string;
	unitFree: string;
	deposit: boolean;
	bankStat: boolean;
	bankStatDisabled: boolean;
	depositAmt: number | string;
	bankStatAmt: string;
	noteCapital: string;
	monthProfit: number | string;
	monthProfitSource: string;
	monthProfitSourceOther: string;
	monthSales: number | string;
	netProfit: string;
	totCredit: number | string;
	noteCapacity: string;
	dp: string;
	pmt: string;
	noteCollateral: string;
	noteSid: string;
	estimatedAsset?: string;
	estimatedAssetAsOf?: string;
}

const BANK_STAT_LABELS: Record<string, string> = {
	"1": "Above collateral value",
	"2": "Equal to collateral value",
	"3": "Below collateral value",
};

const VALUE_BOX_WIDTH = "w-80";

const TEXT_INPUT_CLASS = "rounded-lg border border-slate-300 bg-white p-2 text-sm";
const TEXTAREA_CLASS = "w-full rounded-lg border border-slate-300 bg-white p-2 text-sm";
const READONLY_BOX_CLASS = `${VALUE_BOX_WIDTH} inline-block rounded-lg border border-slate-200 bg-slate-50 p-2 text-right text-sm`;

function formatThousands(raw: string): string {
	const digitsOnly = raw.replace(/[^\d]/g, "");
	if (digitsOnly === "") return "";
	return digitsOnly.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function fmt(value: number | string | undefined | null) {
	if (value === undefined || value === null || value === "") return "0";
	const raw = typeof value === "string" ? value : String(Math.trunc(value));
	const formatted = formatThousands(raw);
	return formatted === "" ? "0" : formatted;
}

function parseNum(value: number | string | undefined | null) {
	if (typeof value === "string") return parseFloat(value.replace(/,/g, "")) || 0;
	return value || 0;
}

function CurrencyInput({
	value,
	onChange,
	className,
}: {
	value: number | string | undefined;
	onChange: (value: string) => void;
	className?: string;
}) {
	const display = formatThousands(typeof value === "string" ? value : String(value ?? ""));
	return (
		<input
			type="text"
			inputMode="numeric"
			className={className}
			value={display}
			onChange={e => onChange(formatThousands(e.target.value))}
		/>
	);
}

export default function CAMSurveyPage({ apless, applNo, indCor, onSaved, onHome }: CAMSurveyPageProps) {
	const [loading, setLoading] = useState(true);
	const [loadError, setLoadError] = useState("");
	const [showCreditHistory, setShowCreditHistory] = useState(false);
	const [showReference, setShowReference] = useState(false);
	const [lookups, setLookups] = useState<Lookups | null>(null);
	const [individual, setIndividual] = useState<IndividualForm | null>(null);
	const [corporate, setCorporate] = useState<CorporateForm | null>(null);
	const [sikDocs, setSikDocs] = useState<SikDocument[]>([]);
	const [saving, setSaving] = useState(false);
	const [saveMessage, setSaveMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
	const [advancing, setAdvancing] = useState(false);
	const [nextError, setNextError] = useState("");

	const load = useCallback(async () => {
		setLoading(true);
		setLoadError("");
		try {
			const res = await api.get("/CAM/EditIndex/survey", { params: { apless, applno: applNo, indCor } });
			if (res.data.blocked) {
				setLoadError(res.data.message || "This application cannot be edited right now.");
				return;
			}
			setShowCreditHistory(!!res.data.showCreditHistory);
			setShowReference(!!res.data.showReference);
			setLookups(res.data.lookups);
			setIndividual(res.data.individual);
			setCorporate(res.data.corporate);
			setSikDocs(res.data.sikCheckingDocuments || []);
		} catch {
			setLoadError("Failed to load Survey. Please try again.");
		} finally {
			setLoading(false);
		}
	}, [apless, applNo, indCor]);

	useEffect(() => {
		load();
	}, [load]);

	const totIncLive = useMemo(() => {
		if (!individual) return 0;
		return (individual.fixInc || 0) + (individual.totOthInc || 0) + (individual.spouseIncome || 0);
	}, [individual]);
	const totIncYearLive = totIncLive * 12;

	const netProfitLive = useMemo(() => {
		if (!corporate) return "";
		const profit = parseNum(corporate.monthProfit);
		const sales = parseNum(corporate.monthSales);
		if (!profit || !sales) return corporate.netProfit || "";
		const ratio = (profit / sales) * 100;
		if (ratio > 30) return "1";
		if (ratio >= 10) return "2";
		return "3";
	}, [corporate]);
	const avgIncomeLive = useMemo(() => parseNum(corporate?.monthSales) * 12, [corporate]);

	useEffect(() => {
		if (corporate && netProfitLive && netProfitLive !== corporate.netProfit) {
			setCorporate(prev => (prev ? { ...prev, netProfit: netProfitLive } : prev));
		}
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [netProfitLive]);

	const updateIndividual = (patch: Partial<IndividualForm>) => setIndividual(prev => (prev ? { ...prev, ...patch } : prev));
	const updateCorporate = (patch: Partial<CorporateForm>) => setCorporate(prev => (prev ? { ...prev, ...patch } : prev));

	const buildPayload = () => ({
		apless,
		applno: applNo,
		indCor,
		individual: indCor === "1" && individual ? { ...individual, totInc: totIncLive, totIncYear: totIncYearLive } : undefined,
		corporate: indCor === "2" && corporate ? { ...corporate, netProfit: netProfitLive || corporate.netProfit } : undefined,
	});

	const handleSave = async () => {
		setSaving(true);
		setSaveMessage(null);
		try {
			const res = await api.post("/CAM/EditIndex/survey/save", buildPayload());
			setSaveMessage(res.data.success ? { type: "success", text: "Successful" } : { type: "error", text: res.data.message || "Failed" });
		} catch (err: any) {
			setSaveMessage({ type: "error", text: err?.response?.data?.message || "Failed" });
		} finally {
			setSaving(false);
		}
	};

	const handleNext = async () => {
		setAdvancing(true);
		setNextError("");
		try {
			const res = await api.post("/CAM/EditIndex/survey/next", buildPayload());
			if (res.data.success) {
				onSaved({ apless, applno: applNo });
			} else {
				setNextError(res.data.message || "Please try again.");
			}
		} catch (err: any) {
			setNextError(err?.response?.data?.message || "Please try again.");
		} finally {
			setAdvancing(false);
		}
	};

	if (loading) {
		return (
			<div className="rounded-2xl bg-white p-8 text-center shadow">
				<p className="text-sm text-slate-400">Loading…</p>
			</div>
		);
	}
	if (loadError) {
		return (
			<div className="rounded-2xl bg-white p-8 text-center shadow">
				<p className="text-sm text-red-600">{loadError}</p>
			</div>
		);
	}
	if (!lookups || (indCor === "1" && !individual) || (indCor === "2" && !corporate)) {
		return (
			<div className="rounded-2xl bg-white p-8 text-center shadow">
				<p className="text-sm text-slate-400">No survey data found.</p>
			</div>
		);
	}

	return (
		<div className="space-y-6 rounded-2xl bg-white p-6 shadow">
			<Section title="Character">
				{showCreditHistory && (
					<Field label="Credit History">
						<Select
							value={indCor === "1" ? individual!.creditHis : corporate!.creditHis}
							onChange={v => (indCor === "1" ? updateIndividual({ creditHis: v }) : updateCorporate({ creditHis: v }))}
							options={lookups.creditHistory}
						/>
					</Field>
				)}
				{showReference && (
					<Field label="Reference">
						<Select
							value={indCor === "1" ? individual!.reference : corporate!.reference}
							onChange={v => (indCor === "1" ? updateIndividual({ reference: v }) : updateCorporate({ reference: v }))}
							options={lookups.reference}
						/>
					</Field>
				)}
				<Field label="Working/ Business Experience">
					<Select
						value={indCor === "1" ? individual!.workExp : corporate!.workExp}
						onChange={v => (indCor === "1" ? updateIndividual({ workExp: v }) : updateCorporate({ workExp: v }))}
						options={lookups.workExp}
					/>
				</Field>

				{indCor === "2" && (
					<>
						<Field label="Company Status">
							<Select value={corporate!.companyStatus} onChange={v => updateCorporate({ companyStatus: v })} options={lookups.companyStatus || []} />
						</Field>
						<Field label="Scale of Business">
							<Select value={corporate!.scale} onChange={v => updateCorporate({ scale: v })} options={lookups.businessScale || []} />
						</Field>
					</>
				)}

				<Field label="Business Size">
					{indCor === "1" ? (
						<Select
							value={individual!.businessSize}
							onChange={v => updateIndividual({ businessSize: v })}
							options={lookups.businessSize}
							disabled={individual!.businessSizeDisabled}
							widthClassName={individual!.businessSizeDisabled ? VALUE_BOX_WIDTH : undefined}
						/>
					) : (
						<Select value={corporate!.businessSize} onChange={() => {}} options={lookups.businessSize} disabled widthClassName={VALUE_BOX_WIDTH} />
					)}
				</Field>

				<Field label="Note">
					<textarea
						className={TEXTAREA_CLASS}
						rows={3}
						value={indCor === "1" ? individual!.noteChar : corporate!.noteChar}
						onChange={e => (indCor === "1" ? updateIndividual({ noteChar: e.target.value }) : updateCorporate({ noteChar: e.target.value }))}
					/>
				</Field>
			</Section>

			<Section title="Capital">
				{indCor === "1" ? (
					<>
						<Field label="Residential Type">
							<Select value={individual!.living} onChange={v => updateIndividual({ living: v, livingSts: "" })} options={lookups.livingType || []} />
						</Field>
						{individual!.living && (
							<Field label="Residential Status">
								<Select
									value={individual!.livingSts}
									onChange={v => updateIndividual({ livingSts: v })}
									options={(individual!.living === "1" ? lookups.livingStatusHouse : lookups.livingStatusApartment) || []}
								/>
							</Field>
						)}
						<Field label="Car Ownership">
							<Select value={individual!.carOwn} onChange={v => updateIndividual({ carOwn: v })} options={lookups.carOwnership || []} />
						</Field>
					</>
				) : (
					<>
						<Field label="Business Location">
							<Select value={corporate!.businessLocation} onChange={v => updateCorporate({ businessLocation: v })} options={lookups.businessLocation || []} />
						</Field>
						<Field label="Total Unit Owned (Vehicle)">
							<Select value={corporate!.unitOwned} onChange={v => updateCorporate({ unitOwned: v })} options={lookups.unitOwned || []} />
						</Field>
						<Field label="Unit Free from Finance">
							<Select value={corporate!.unitFree} onChange={v => updateCorporate({ unitFree: v })} options={lookups.unitFree || []} />
						</Field>
						<Field label={`Estimated Total Assets${corporate!.estimatedAssetAsOf ? ` (as of ${corporate!.estimatedAssetAsOf})` : ""}`}>
							<Select value={corporate!.estimatedAsset || ""} onChange={() => {}} options={lookups.estimatedAsset || []} disabled widthClassName={VALUE_BOX_WIDTH} />
						</Field>
					</>
				)}

				<Field label="Deposit">
					<label className="flex items-center gap-2 text-sm">
						<input
							type="checkbox"
							checked={indCor === "1" ? individual!.deposit : corporate!.deposit}
							onChange={e => (indCor === "1" ? updateIndividual({ deposit: e.target.checked }) : updateCorporate({ deposit: e.target.checked }))}
						/>
						Has Deposit
					</label>
				</Field>
				{(indCor === "1" ? individual!.deposit : corporate!.deposit) && (
					<Field label="Deposit Amount">
						<CurrencyInput
							className={`${VALUE_BOX_WIDTH} ${TEXT_INPUT_CLASS} text-right`}
							value={indCor === "1" ? individual!.depositAmt : corporate!.depositAmt}
							onChange={v => (indCor === "1" ? updateIndividual({ depositAmt: v }) : updateCorporate({ depositAmt: v }))}
						/>
					</Field>
				)}
				<Field label="Bank Statement">
					<label className="flex items-center gap-2 text-sm">
						<input
							type="checkbox"
							checked={indCor === "1" ? individual!.bankStat : corporate!.bankStat}
							disabled={indCor === "2" && corporate!.bankStatDisabled}
							onChange={e => (indCor === "1" ? updateIndividual({ bankStat: e.target.checked }) : updateCorporate({ bankStat: e.target.checked }))}
						/>
						Bank Statement Provided
					</label>
				</Field>
				<Field label="Bank Statement Assessment">
					<span className="text-sm text-slate-600">
						{BANK_STAT_LABELS[indCor === "1" ? individual!.bankStatAmt : corporate!.bankStatAmt] || "Not yet assessed"}
					</span>
				</Field>

				<Field label="Note">
					<textarea
						className={TEXTAREA_CLASS}
						rows={3}
						value={indCor === "1" ? individual!.noteCapital : corporate!.noteCapital}
						onChange={e => (indCor === "1" ? updateIndividual({ noteCapital: e.target.value }) : updateCorporate({ noteCapital: e.target.value }))}
					/>
				</Field>
			</Section>

			<Section title="Capacity">
				{indCor === "1" ? (
					<>
						<Field label="Fixed Monthly Income">
							<div className="flex flex-wrap items-center gap-2">
								<span className={READONLY_BOX_CLASS}>Rp {fmt(individual!.fixInc)}</span>
								<span className="text-sm text-slate-500">Source of Fund</span>
								<Select value={individual!.fixIncSource} onChange={v => updateIndividual({ fixIncSource: v })} options={lookups.sourceOfFund} />
								{individual!.fixIncSource === "4" && (
									<input
										type="text"
										className={TEXT_INPUT_CLASS}
										value={individual!.fixIncSourceOther}
										onChange={e => updateIndividual({ fixIncSourceOther: e.target.value })}
									/>
								)}
							</div>
						</Field>
						<Field label="Spouse Occupation">
							<Select
								value={individual!.spouseJob}
								onChange={v => updateIndividual({ spouseJob: v })}
								options={lookups.spouseJob || []}
								disabled={individual!.spouseMaritalDisabled}
								widthClassName={individual!.spouseMaritalDisabled ? VALUE_BOX_WIDTH : undefined}
							/>
						</Field>
						<Field label="Spouse Income per Month">
							<span className={READONLY_BOX_CLASS}>Rp {fmt(individual!.spouseIncome)}</span>
						</Field>
						<Field label="Total Other Income per Month">
							<div className="flex flex-wrap items-center gap-2">
								<span className={READONLY_BOX_CLASS}>Rp {fmt(individual!.totOthInc)}</span>
								<span className="text-sm text-slate-500">Source of Fund</span>
								<Select value={individual!.totOthIncSource} onChange={v => updateIndividual({ totOthIncSource: v })} options={lookups.sourceOfFund} />
								{individual!.totOthIncSource === "4" && (
									<input
										type="text"
										className={TEXT_INPUT_CLASS}
										value={individual!.totOthIncSourceOther}
										onChange={e => updateIndividual({ totOthIncSourceOther: e.target.value })}
									/>
								)}
							</div>
						</Field>
						<Field label="Total Income per Month">
							<span className={READONLY_BOX_CLASS}>Rp {fmt(totIncLive)}</span>
						</Field>
						<Field label="Average Income per Year">
							<span className={READONLY_BOX_CLASS}>Rp {fmt(totIncYearLive)}</span>
						</Field>
					</>
				) : (
					<>
						<Field label="Monthly Profit">
							<div className="flex flex-wrap items-center gap-2">
								<CurrencyInput
									className={`${VALUE_BOX_WIDTH} ${TEXT_INPUT_CLASS} text-right`}
									value={corporate!.monthProfit}
									onChange={v => updateCorporate({ monthProfit: v })}
								/>
								<span className="text-sm text-slate-500">Source of Fund</span>
								<Select value={corporate!.monthProfitSource} onChange={v => updateCorporate({ monthProfitSource: v })} options={lookups.sourceOfFund} />
								<input
									type="text"
									className={TEXT_INPUT_CLASS}
									value={corporate!.monthProfitSourceOther}
									onChange={e => updateCorporate({ monthProfitSourceOther: e.target.value })}
								/>
							</div>
						</Field>
						<Field label="Sales/ Month">
							<CurrencyInput
								className={`${VALUE_BOX_WIDTH} ${TEXT_INPUT_CLASS} text-right`}
								value={corporate!.monthSales}
								onChange={v => updateCorporate({ monthSales: v })}
							/>
						</Field>
						<Field label="Monthly Sales to Profit (Nett Profit : Sales)">
							<Select value={netProfitLive || corporate!.netProfit} onChange={v => updateCorporate({ netProfit: v })} options={lookups.netProfitRatio || []} />
						</Field>
						<Field label="Average Income per Year">
							<span className={READONLY_BOX_CLASS}>Rp {fmt(avgIncomeLive)}</span>
						</Field>
					</>
				)}

				<Field label="Total Credit (Bank Transactions)">
					<span className={READONLY_BOX_CLASS}>Rp {fmt(indCor === "1" ? individual!.totCredit : corporate!.totCredit)}</span>
				</Field>

				<Field label="Note">
					<textarea
						className={TEXTAREA_CLASS}
						rows={3}
						value={indCor === "1" ? individual!.noteCapacity : corporate!.noteCapacity}
						onChange={e => (indCor === "1" ? updateIndividual({ noteCapacity: e.target.value }) : updateCorporate({ noteCapacity: e.target.value }))}
					/>
				</Field>
			</Section>

			<Section title="Collateral">
				<Field label="DP">
					<Select
						value={indCor === "1" ? individual!.dp : corporate!.dp}
						onChange={v => (indCor === "1" ? updateIndividual({ dp: v }) : updateCorporate({ dp: v }))}
						options={lookups.dp}
					/>
				</Field>
				<Field label="Payment Method">
					<Select
						value={indCor === "1" ? individual!.pmt : corporate!.pmt}
						onChange={v => (indCor === "1" ? updateIndividual({ pmt: v }) : updateCorporate({ pmt: v }))}
						options={lookups.paymentMethod || []}
					/>
				</Field>
				<Field label="Note">
					<textarea
						className={TEXTAREA_CLASS}
						rows={3}
						value={indCor === "1" ? individual!.noteCollateral : corporate!.noteCollateral}
						onChange={e => (indCor === "1" ? updateIndividual({ noteCollateral: e.target.value }) : updateCorporate({ noteCollateral: e.target.value }))}
					/>
				</Field>
			</Section>

			<Section title="SIK Checking Document">
				{sikDocs.length === 0 ? (
					<p className="text-sm text-slate-400">No SIK checking documents found.</p>
				) : (
					<div className="overflow-x-auto">
						<table className="w-full text-left text-sm">
							<thead>
								<tr className="border-b border-slate-200 text-slate-500">
									<th className="p-2">Subject</th>
									<th className="p-2">Related Party</th>
									<th className="p-2">Credit Bureau</th>
									<th className="p-2">Status</th>
									<th className="p-2">Score</th>
									<th className="p-2">Grade</th>
									<th className="p-2">File</th>
								</tr>
							</thead>
							<tbody>
								{sikDocs.map((doc, idx) => (
									<tr key={idx} className="border-b border-slate-100">
										<td className="p-2">{doc.subject || "-"}</td>
										<td className="p-2">{doc.relatedParty || "-"}</td>
										<td className="p-2">{doc.creditBureau || "-"}</td>
										<td className="p-2">{doc.status || "-"}</td>
										<td className="p-2">{doc.score || "-"}</td>
										<td className="p-2">{doc.grade || "-"}</td>
										<td className="p-2">
											{doc.downloadUrl ? (
												<a href={doc.downloadUrl} target="_blank" rel="noreferrer" className="text-orange-600 hover:underline">
													Download
												</a>
											) : (
												"-"
											)}
										</td>
									</tr>
								))}
							</tbody>
						</table>
					</div>
				)}
				<Field label="Note">
					<textarea
						className={TEXTAREA_CLASS}
						rows={4}
						maxLength={1000}
						value={indCor === "1" ? individual!.noteSid : corporate!.noteSid}
						onChange={e => (indCor === "1" ? updateIndividual({ noteSid: e.target.value }) : updateCorporate({ noteSid: e.target.value }))}
					/>
				</Field>
			</Section>

			<div className="flex items-center gap-3 pt-2">
				<button
					type="button"
					onClick={handleSave}
					disabled={saving}
					className="rounded-lg bg-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-300 disabled:opacity-50"
				>
					{saving ? "Saving…" : "Save"}
				</button>

				{saveMessage && (
					<span className={`text-sm ${saveMessage.type === "success" ? "text-green-600" : "text-red-600"}`}>{saveMessage.text}</span>
				)}

				{saveMessage?.type === "success" && (
					<button
						type="button"
						onClick={() => onHome?.()}
						className="rounded-lg bg-slate-700 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
					>
						Finish
					</button>
				)}
			</div>

			{nextError && <p className="text-sm text-red-600">{nextError}</p>}

			<div className="flex justify-end pt-2">
				<button
					type="button"
					onClick={handleNext}
					disabled={advancing}
					className="rounded-lg bg-orange-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-orange-600 disabled:opacity-50"
				>
					{advancing ? "Please wait…" : "Next"}
				</button>
			</div>
		</div>
	);
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
	return (
		<div className="space-y-3">
			<h3 className="text-sm font-semibold uppercase tracking-wide text-orange-600">{title}</h3>
			<div className="space-y-3">{children}</div>
		</div>
	);
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
	return (
		<div className="grid grid-cols-1 gap-1 sm:grid-cols-[240px_1fr] sm:items-start sm:gap-4">
			<label className="text-sm font-medium text-slate-600">{label}</label>
			<div>{children}</div>
		</div>
	);
}

function Select({
	value,
	onChange,
	options,
	disabled,
	widthClassName = "w-full max-w-xs",
}: {
	value: string;
	onChange: (value: string) => void;
	options: ComboOption[];
	disabled?: boolean;
	widthClassName?: string;
}) {
	return (
		<select
			className={`${widthClassName} rounded-lg border border-slate-300 bg-white p-2 text-sm disabled:bg-slate-100`}
			value={value || ""}
			disabled={disabled}
			onChange={e => onChange(e.target.value)}
		>
			<option value="">Select</option>
			{options.map(opt => (
				<option key={opt.value} value={opt.value}>
					{opt.label}
				</option>
			))}
		</select>
	);
}