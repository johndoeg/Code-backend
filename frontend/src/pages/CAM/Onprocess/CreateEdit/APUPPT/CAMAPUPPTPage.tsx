import React, { useCallback, useEffect, useState } from "react";
import api from "../../../../../api/axiosInstance";

export interface CAMApuPptPageProps {
	apless: string;
	applNo: string;
	onSaved: (result: { apless: string; applno: string }) => void;
}

interface EddQuestion {
	value: string;
	description: string;
}

interface PartySummary {
	name: string;
	type: string;
	occupationBusinessType: string;
	apuPptStatus: string;
	identificationProcess: string;
	eddRequired: boolean;
	eddQuestions: EddQuestion[];
	previouslyPassed: boolean;
}

type Answers = Record<string, "1" | "0" | undefined>;

const labelClass = "w-1/3 py-1 align-top text-sm text-slate-500";
const valueClass = "py-1 align-top text-sm text-slate-700";

function PartyDetails({ party, entityLabel }: { party: PartySummary; entityLabel: string }) {
	return (
		<table className="w-full text-sm">
			<tbody>
				<tr>
					<td className={labelClass}>{entityLabel} Name</td>
					<td className={valueClass}>{party.name}</td>
				</tr>
				<tr>
					<td className={labelClass}>{entityLabel} Type</td>
					<td className={valueClass}>{party.type}</td>
				</tr>
				<tr>
					<td className={labelClass}>Occupation / Business Type</td>
					<td className={valueClass}>{party.occupationBusinessType}</td>
				</tr>
				<tr>
					<td className={labelClass}>APU PPT Status</td>
					<td className={valueClass}>{party.apuPptStatus}</td>
				</tr>
				<tr>
					<td className={labelClass}>Identification and Verification Process</td>
					<td className={valueClass}>{party.identificationProcess}</td>
				</tr>
			</tbody>
		</table>
	);
}

function EddQuestionnaire({
	groupName,
	instruction,
	questions,
	answers,
	onAnswer,
}: {
	groupName: string;
	instruction: React.ReactNode;
	questions: EddQuestion[];
	answers: Answers;
	onAnswer: (value: string, answer: "1" | "0") => void;
}) {
	return (
		<div className="space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
			<p className="text-sm font-bold text-slate-700">{instruction}</p>
			<table className="w-full text-sm">
				<tbody>
					{questions.map((q, idx) => (
						<tr key={q.value} className="align-top">
							<td className="w-8 py-2 text-center text-slate-500">{idx + 1}.</td>
							<td className="py-2 text-slate-700">{q.description}</td>
							<td className="w-16 py-2 text-center">
								<label className="inline-flex items-center gap-1 text-slate-600">
									<input
										type="radio"
										name={`${groupName}-${q.value}`}
										checked={answers[q.value] === "1"}
										onChange={() => onAnswer(q.value, "1")}
									/>
									YES
								</label>
							</td>
							<td className="w-16 py-2 text-center">
								<label className="inline-flex items-center gap-1 text-slate-600">
									<input
										type="radio"
										name={`${groupName}-${q.value}`}
										checked={answers[q.value] === "0"}
										onChange={() => onAnswer(q.value, "0")}
									/>
									NO
								</label>
							</td>
						</tr>
					))}
				</tbody>
			</table>
		</div>
	);
}

const CUSTOMER_EDD_INSTRUCTION = (
	<>
		Mohon diisi kuisioner EDD di bawah ini karena calon konsumen termasuk High Risk APU PPT / Please fill in the
		EDD questionnaire below because potential customers are a High Risk APU PPT
		<br />
		<span className="font-normal">
			Apakah CMO sudah melakukan identifikasi dan verifikasi secara mendalam terhadap calon konsumen, terkait hal
			berikut : / Has the CMO conducted in-depth identification and verification of potential customers, in
			relation to the following:
		</span>
	</>
);

const BO_EDD_INSTRUCTION = (
	<>
		Mohon diisi kuisioner EDD di bawah ini karena beneficial owner termasuk High Risk APU PPT / Please fill in the
		EDD questionnaire below because the beneficial owner is a High Risk APU PPT
		<br />
		<span className="font-normal">
			Apakah CMO sudah melakukan identifikasi dan verifikasi secara mendalam terhadap Beneficial Owner (BO),
			terkait hal berikut : / Has the CMO carried out in-depth identification and verification of the
			Beneficial Owner (BO), in relation to the following:
		</span>
	</>
);

export default function CAMApuPptPage({ apless, applNo, onSaved }: CAMApuPptPageProps) {
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState("");
	const [customer, setCustomer] = useState<PartySummary | null>(null);
	const [bo, setBo] = useState<PartySummary | null>(null);
	const [customerAnswers, setCustomerAnswers] = useState<Answers>({});
	const [boAnswers, setBoAnswers] = useState<Answers>({});
	const [saving, setSaving] = useState(false);
	const [saveError, setSaveError] = useState("");

	const load = useCallback(async () => {
		setLoading(true);
		setError("");
		try {
			const res = await api.get("/CAM/EditIndex/apu-ppt", { params: { apless, applno: applNo } });
			const cust: PartySummary = res.data.customer;
			const boData: PartySummary | null = res.data.beneficialOwner || null;
			setCustomer(cust);
			setBo(boData);

			if (cust?.previouslyPassed) {
				const seeded: Answers = {};
				cust.eddQuestions.forEach(q => (seeded[q.value] = "1"));
				setCustomerAnswers(seeded);
			}
			if (boData?.previouslyPassed) {
				const seeded: Answers = {};
				boData.eddQuestions.forEach(q => (seeded[q.value] = "1"));
				setBoAnswers(seeded);
			}
		} catch {
			setError("Failed to load APU PPT data. Please try again.");
		} finally {
			setLoading(false);
		}
	}, [apless, applNo]);

	useEffect(() => {
		load();
	}, [load]);

	const handleNext = async () => {
		setSaving(true);
		setSaveError("");
		try {
			const res = await api.post("/CAM/EditIndex/apu-ppt/next", {
				apless,
				applno: applNo,
				customerAnswers,
				boAnswers,
			});
			if (res.data.success) {
				onSaved({ apless, applno: applNo });
			} else {
				setSaveError(res.data.message || "Save failed.");
			}
		} catch (err: any) {
			setSaveError(err?.response?.data?.message || "Save failed. Please try again.");
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
	if (error || !customer) {
		return (
			<div className="rounded-2xl bg-white p-8 text-center shadow">
				<p className="text-sm text-red-600">{error || "No APU PPT data found for this application."}</p>
			</div>
		);
	}

	return (
		<div className="space-y-4 rounded-2xl bg-white p-6 shadow">
			<h2 className="text-base font-semibold text-slate-700">APU PPT</h2>

			<div>
				<h3 className="mb-2 text-sm font-semibold text-slate-600">Customer</h3>
				<PartyDetails party={customer} entityLabel="Customer" />
			</div>

			{customer.eddRequired && (
				<EddQuestionnaire
					groupName="customer"
					instruction={CUSTOMER_EDD_INSTRUCTION}
					questions={customer.eddQuestions}
					answers={customerAnswers}
					onAnswer={(value, answer) => setCustomerAnswers(prev => ({ ...prev, [value]: answer }))}
				/>
			)}

			{bo && (
				<>
					<div>
						<h3 className="mb-2 text-sm font-semibold text-slate-600">Beneficial Owner</h3>
						<PartyDetails party={bo} entityLabel="Beneficial Owner" />
					</div>

					{bo.eddRequired && (
						<EddQuestionnaire
							groupName="bo"
							instruction={BO_EDD_INSTRUCTION}
							questions={bo.eddQuestions}
							answers={boAnswers}
							onAnswer={(value, answer) => setBoAnswers(prev => ({ ...prev, [value]: answer }))}
						/>
					)}
				</>
			)}

			{saveError && <p className="text-sm text-red-600">{saveError}</p>}

			<div className="flex justify-end pt-2">
				<button
					type="button"
					onClick={handleNext}
					disabled={saving}
					className="rounded-lg bg-orange-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-orange-600 disabled:opacity-50"
				>
					{saving ? "Saving…" : "Next"}
				</button>
			</div>
		</div>
	);
}