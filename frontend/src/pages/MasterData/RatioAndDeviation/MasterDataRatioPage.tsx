import React, { useEffect, useState, useCallback } from "react";
import api from "../../../api/axiosInstance";

interface ComboOption { value: string; desc_value: string; }

interface FormState {
	ratio: string;
	remark: string;
	imp_date: string;
	actual1: string;
	actual2: string;
	ojk1: string;
	ojk2: string;
	ojk_date: string;
}

const EMPTY_FORM: FormState = {
	ratio: "1", remark: "1",
	imp_date: "", actual1: "", actual2: "",
	ojk1: "", ojk2: "", ojk_date: "",
};

type FieldType = "select" | "number_x" | "number_pct";

function getFieldConfig(ratio: string): { type: FieldType; suffix: string } {
	if (ratio === "1" || ratio === "5") return { type: "select", suffix: "" };
	if (ratio === "2") return { type: "number_x", suffix: "x" };
	return { type: "number_pct", suffix: "%" };
}

const Spinner = ({ size = 6 }: { size?: number }) => (
	<svg className={`animate-spin h-${size} w-${size} text-blue-600`} fill="none" viewBox="0 0 24 24">
		<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
		<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
	</svg>
);

const MasterDataRatioPage: React.FC = () => {

	const [ratioOpts, setRatioOpts] = useState<ComboOption[]>([]);
	const [remarkOpts, setRemarkOpts] = useState<ComboOption[]>([]);
	const [thresOpts, setThresOpts] = useState<ComboOption[]>([]);

	const [ratioSelected, setRatioSelected] = useState("1");
	const [fullname, setFullname] = useState("");

	const [modalOpen, setModalOpen] = useState(false);
	const [form, setForm] = useState<FormState>(EMPTY_FORM);
	const [ojkLoading, setOjkLoading] = useState(false);
	const [saveLoading, setSaveLoading] = useState(false);
	const [saveMsg, setSaveMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

	const currentYear = new Date().getFullYear();
	const yearOptions = Array.from({ length: 21 }, (_, i) => currentYear + 10 - i);

	useEffect(() => {
		api.get("/MasterData/api/actual-ratio/options").then(res => {
			setRatioOpts(res.data.ratio || []);
			setRemarkOpts(res.data.remark || []);
			setThresOpts(res.data.threshold || []);
			if (res.data.fullname) setFullname(res.data.fullname);
		}).catch(() => { });
	}, []);

	const fetchOjk = useCallback(async (ratio: string, imp_date: string) => {
		if (!ratio || !imp_date) return;
		setOjkLoading(true);
		try {
			const res = await api.get("/MasterData/api/actual-ratio/ojk-threshold", {
				params: { ratio, imp_date },
			});
			const d = res.data;
			setForm(f => ({
				...f,
				remark: String(d.remark),
				ojk1: d.ojk_from || "",
				ojk2: d.ojk_to || "",
				ojk_date: d.imp_date || "",
			}));
		} catch {
			setForm(f => ({ ...f, remark: "1", ojk1: "", ojk2: "", ojk_date: "" }));
		} finally {
			setOjkLoading(false);
		}
	}, []);

	useEffect(() => {
		if (modalOpen && form.imp_date) {
			fetchOjk(form.ratio, form.imp_date);
		}
	}, [form.ratio, form.imp_date, modalOpen, fetchOjk]);

	const handleOpenAdd = () => {
		setForm({ ...EMPTY_FORM, ratio: ratioSelected });
		setSaveMsg(null);
		setModalOpen(true);
	};

	const handleSave = async () => {
		const { ratio, remark, imp_date, actual1, actual2, ojk1, ojk2 } = form;

		if (!imp_date) {
			setSaveMsg({ type: "error", text: "Lengkapi data terlebih dahulu" });
			return;
		}
		if (!actual1) {
			setSaveMsg({ type: "error", text: "Lengkapi data Actual dahulu" });
			return;
		}
		if (remark === "3" && !actual2) {
			setSaveMsg({ type: "error", text: "Lengkapi data Actual dahulu" });
			return;
		}

		setSaveLoading(true);
		setSaveMsg(null);
		try {
			await api.post("/MasterData/api/actual-ratio", {
				ratio, remark, imp_date, actual1,
				actual2: remark === "3" ? actual2 : "",
				ojk1,
				ojk2: remark === "3" ? ojk2 : "",
			});
			setSaveMsg({ type: "success", text: "Data berhasil disimpan" });
			setForm({ ...EMPTY_FORM, ratio: ratioSelected });
		} catch (err: any) {
			setSaveMsg({ type: "error", text: err.response?.data?.error || "Data gagal disimpan" });
		} finally {
			setSaveLoading(false);
		}
	};

	const renderFields = (
		val1: string, val2: string,
		onChange1?: (v: string) => void,
		onChange2?: (v: string) => void,
		readonly = false
	) => {
		const cfg = getFieldConfig(form.ratio);
		const showRange = form.remark === "3";

		const baseCls = readonly
			? "border border-gray-200 rounded-lg px-3 py-2 text-sm bg-gray-100 text-gray-500 cursor-not-allowed w-40"
			: "border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 w-40";

		const numInput = (val: string, onChange?: (v: string) => void) => (
			<div className="flex items-center gap-1">
				<input
					type="text" value={val}
					readOnly={readonly}
					onChange={e => {
						if (!readonly && onChange && /^[0-9]*\.?[0-9]{0,2}$/.test(e.target.value))
							onChange(e.target.value);
					}}
					className={baseCls} placeholder="0.00"
				/>
				<span className="text-sm text-gray-400">{cfg.suffix}</span>
			</div>
		);

		const selInput = (val: string, onChange?: (v: string) => void) => (
			<select
				value={val} disabled={readonly}
				onChange={e => onChange && onChange(e.target.value)}
				className={baseCls}
			>
				<option value="">Select</option>
				{thresOpts.map(o => <option key={o.value} value={o.value}>{o.desc_value}</option>)}
			</select>
		);

		const field1 = cfg.type === "select" ? selInput(val1, onChange1) : numInput(val1, onChange1);
		const field2 = cfg.type === "select" ? selInput(val2, onChange2) : numInput(val2, onChange2);

		return (
			<div className="flex items-center gap-2 flex-wrap">
				{field1}
				{showRange && (
					<>
						<span className="text-sm text-gray-500 font-medium">s/d</span>
						{field2}
					</>
				)}
			</div>
		);
	};

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-3xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6">

					<div className="mb-6">
						<h1 className="text-2xl md:text-3xl font-bold text-gray-800">Actual Ratio</h1>
						<p className="text-gray-600 mt-1">Record actual vs OJK threshold values per ratio</p>
					</div>

					<div className="bg-gray-50 rounded-xl p-4 border border-gray-200">
						<div className="flex flex-wrap items-end gap-4">
							<div className="min-w-[220px]">
								<label className="block text-sm font-medium text-gray-700 mb-1">Ratio</label>
								<select
									value={ratioSelected}
									onChange={e => setRatioSelected(e.target.value)}
									className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white"
								>
									{ratioOpts.map(o => <option key={o.value} value={o.value}>{o.desc_value}</option>)}
								</select>
							</div>
							<button
								onClick={handleOpenAdd}
								className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center gap-2"
							>
								<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
								</svg>
								Add
							</button>
						</div>
					</div>

				</div>
			</div>

			{modalOpen && (
				<div
					className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
					onClick={e => { if (e.target === e.currentTarget) setModalOpen(false); }}
				>
					<div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl mx-4 overflow-hidden">

						<div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-gray-50">
							<h2 className="text-lg font-bold text-gray-800">Add New Record</h2>
							<button onClick={() => setModalOpen(false)} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">&times;</button>
						</div>

						<div className="px-6 py-5 space-y-4">
							<div className="grid grid-cols-2 gap-6">
								<div>
									<label className="block text-sm font-medium text-gray-700 mb-1">
										As of {form.ratio === "5" ? "(Year)" : "(Month)"}
									</label>
									{form.ratio === "5" ? (
										<select
											value={form.imp_date}
											onChange={e => setForm(f => ({ ...f, imp_date: e.target.value, actual1: "", actual2: "" }))}
											className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 bg-white"
										>
											<option value="">Select year</option>
											{yearOptions.map(y => <option key={y} value={String(y)}>{y}</option>)}
										</select>
									) : (
										<div className="flex gap-2">
											<select
												value={form.imp_date ? form.imp_date.split("-")[1] : ""}
												onChange={e => {
													const yr = form.imp_date ? form.imp_date.split("-")[0] : String(new Date().getFullYear());
													const mo = e.target.value;
													setForm(f => ({ ...f, imp_date: mo ? `${yr}-${mo}` : "", actual1: "", actual2: "" }));
												}}
												className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 bg-white"
											>
												<option value="">Month</option>
												{["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
													.map((m, i) => (
														<option key={i} value={String(i + 1).padStart(2, "0")}>{m}</option>
													))}
											</select>
											<select
												value={form.imp_date ? form.imp_date.split("-")[0] : ""}
												onChange={e => {
													const mo = form.imp_date ? form.imp_date.split("-")[1] : "";
													const yr = e.target.value;
													setForm(f => ({ ...f, imp_date: (mo && yr) ? `${yr}-${mo}` : "", actual1: "", actual2: "" }));
												}}
												className="w-24 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 bg-white"
											>
												<option value="">Year</option>
												{yearOptions.map(y => <option key={y} value={String(y)}>{y}</option>)}
											</select>
										</div>
									)}
								</div>
								<div>
									<label className="block text-sm font-medium text-gray-700 mb-1">Create By</label>
									<input
										type="text"
										value={fullname}
										readOnly
										className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-gray-100 text-gray-500 cursor-not-allowed"
									/>
								</div>
								<div>
									<label className="block text-sm font-medium text-gray-700 mb-1">Create Date</label>
									<input
										type="text"
										value={new Date().toLocaleDateString("id-ID", { day: "2-digit", month: "2-digit", year: "numeric" })}
										readOnly
										className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-gray-100 text-gray-500 cursor-not-allowed"
									/>
								</div>
							</div>

							<div className="grid grid-cols-2 gap-6">
								<div>
									<label className="block text-sm font-medium text-gray-700 mb-1">Remark</label>
									{ojkLoading ? (
										<div className="flex items-center gap-2 py-2 text-sm text-gray-400">
											<Spinner size={4} /> Loading...
										</div>
									) : (
										<select
											value={form.remark}
											disabled
											className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-gray-100 text-gray-500 cursor-not-allowed"
										>
											<option value="">—</option>
											{remarkOpts.map(o => <option key={o.value} value={o.value}>{o.desc_value}</option>)}
										</select>
									)}
									<p className="text-xs text-gray-400 mt-1">Auto-filled from OJK threshold</p>
								</div>
							</div>

							<div className="border-t border-gray-100 pt-1">
								<p className="text-xs font-bold text-gray-500 uppercase tracking-wider">Amount / Category</p>
							</div>

							<div className="grid grid-cols-[140px_1fr] items-center gap-4">
								<label className="text-sm font-medium text-gray-700">Actual</label>
								{renderFields(
									form.actual1, form.actual2,
									v => setForm(f => ({ ...f, actual1: v })),
									v => setForm(f => ({ ...f, actual2: v })),
									false
								)}
							</div>

							<div className="grid grid-cols-[140px_1fr] items-center gap-4">
								<div>
									<label className="text-sm font-medium text-gray-700">Threshold Level (OJK)</label>
									{form.ojk_date && !ojkLoading && (
										<p className="text-xs text-gray-400 mt-0.5">as of {form.ojk_date}</p>
									)}
								</div>
								{ojkLoading
									? <span className="text-sm text-gray-400 flex items-center gap-1"><Spinner size={4} /> Loading...</span>
									: renderFields(form.ojk1, form.ojk2, undefined, undefined, true)
								}
							</div>

							{saveMsg && (
								<div className={`p-3 rounded-lg text-sm flex items-center gap-2 ${saveMsg.type === "success"
									? "bg-green-50 border border-green-200 text-green-700"
									: "bg-red-50 border border-red-200 text-red-700"
									}`}>
									{saveMsg.type === "success" ? (
										<svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
											<path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
										</svg>
									) : (
										<svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
										</svg>
									)}
									{saveMsg.text}
								</div>
							)}
						</div>

						<div className="px-6 py-4 border-t border-gray-200 bg-gray-50 flex justify-end gap-3">
							<button
								onClick={() => setModalOpen(false)}
								className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-100 text-sm font-medium"
							>
								Close
							</button>
							<button
								onClick={handleSave}
								disabled={saveLoading}
								className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
							>
								{saveLoading ? (
									<><Spinner size={4} /> Saving…</>
								) : (
									<>
										<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
										</svg>
										Save
									</>
								)}
							</button>
						</div>
					</div>
				</div>
			)}
		</div>
	);
};

export default MasterDataRatioPage;