import React, { useEffect, useState, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import api from "../../../api/axiosInstance";

type Mode = "Add" | "Edit" | "View";
type Tab = "main" | "pic" | "bank" | "tax" | "doc" | "notes";

interface Opt { value: string; label: string; province?: string; }

interface FormOptions {
	sales_types: Opt[]; broker_types: Opt[]; genders: Opt[];
	branches: Opt[]; occupations: Opt[]; banks: Opt[];
	beneficiary_types: Opt[]; resident_statuses: Opt[];
	npwp_types_pr: Opt[]; npwp_types_pt: Opt[]; npwp_details: Opt[];
	provinces: Opt[]; cities: Opt[]; tax_types: Opt[];
	pic_occupations: Opt[];
}

interface MainForm {
	sal_type: string; broker: string; status: string; branch: string;
	cmo_name: string; sales_no: string; initial_sales_no: string;
	name: string; gender: string; nick_name: string; bd_occupation: string;
	idcard: string; exp_date: string; certain_per: string;
	address: string; city_sales: string; post: string; phone: string;
	email_addr: string; fax: string; paid: string;
	create_by: string; create_date: string; update_by: string; lastupdate: string;
}

interface PicForm {
	cont_name: string; occupation: string; cont_idcard: string;
	exp_date: string; id_validdt: string;
	cont_addr: string; cont_city: string; post: string;
	cont_phone: string; email_addr: string;
}

interface BankAccount {
	acc_no: string; acc_name: string; bank: string; bank_name: string;
	bank_branch: string; beneficiary_type: string; ben_type_label: string;
	resident_status: string; res_status_label: string; is_default: boolean;
}

interface BankForm {
	acc_no: string; acc_name: string; bank: string; bank_branch: string;
	beneficiary_type: string; resident_status: string; is_default: boolean;
}

interface TaxForm {
	npwp_type: string; npwp_no: string; npwp_detail: string;
	npwp_nm: string; npwp_addr: string; city: string; province: string;
	npwp_start: string; ppnsts: string; ppnstartdate: string;
	taxfree: string; taxfree2: string;
	pph: string; rate: string; dpp: string;
	update_by: string; lastupdate: string; is_saved: boolean;
}

interface SalesFile {
	id: number; aws_key: string; file_nm: string; file_ext: string;
	doc_type: string; ket: string; created_date: string; download_url: string;
}

interface DocTypeConfig {
	key: string;
	label: string;
	hasLainnya?: boolean;
}

const SALESMAN_DOCS: DocTypeConfig[] = [
	{ key: "commission-receiver", label: "Form Data Penerima Komisi" },
	{ key: "sales-ktp", label: "KTP Salesman" },
	{ key: "sales-npwp", label: "NPWP" },
	{ key: "sales-bank-account", label: "Buku Tabungan / Rekening Koran" },
	{ key: "sales-npwp-statement", label: "Surat Pernyataan NPWP *" },
	{ key: "sales-other", label: "Lainnya", hasLainnya: true },
];

const BROKER_PT_DOCS: DocTypeConfig[] = [
	{ key: "commission-receiver", label: "Form Data Penerima Komisi" },
	{ key: "sales-contact-person", label: "KTP Contact Person" },
	{ key: "sales-siup", label: "SIUP" },
	{ key: "sales-npwp", label: "NPWP" },
	{ key: "sales-bank-account", label: "Buku Tabungan / Rekening Koran" },
	{ key: "sales-other", label: "Lainnya", hasLainnya: true },
];

const BROKER_PR_DOCS: DocTypeConfig[] = [
	{ key: "commission-receiver", label: "Form Data Penerima Komisi" },
	{ key: "sales-ktp", label: "KTP Broker" },
	{ key: "sales-npwp", label: "NPWP" },
	{ key: "sales-bank-account", label: "Buku Tabungan / Rekening Koran" },
	{ key: "sales-npwp-statement", label: "Surat Pernyataan NPWP *" },
	{ key: "sales-other", label: "Lainnya", hasLainnya: true },
];

function getDocConfig(salType: string, brokerType: string): {
	title: string; docs: DocTypeConfig[]; showNpwpNote: boolean;
} {
	if (salType === "PT" && brokerType === "PT")
		return { title: "Upload Broker Legal Entity File", docs: BROKER_PT_DOCS, showNpwpNote: false };
	if (salType === "PT" && brokerType === "PR")
		return { title: "Upload Broker Individual File", docs: BROKER_PR_DOCS, showNpwpNote: true };

	return { title: "Upload File", docs: SALESMAN_DOCS, showNpwpNote: true };
}

const defMain: MainForm = {
	sal_type: "", broker: "", status: "A", branch: "", cmo_name: "",
	sales_no: "", initial_sales_no: "", name: "", gender: "", nick_name: "",
	bd_occupation: "", idcard: "", exp_date: "0", certain_per: "",
	address: "", city_sales: "", post: "", phone: "", email_addr: "", fax: "",
	paid: "1", create_by: "", create_date: "", update_by: "", lastupdate: "",
};

const defPic: PicForm = {
	cont_name: "", occupation: "", cont_idcard: "", exp_date: "0",
	id_validdt: "", cont_addr: "", cont_city: "", post: "", cont_phone: "", email_addr: "",
};

const defBankForm: BankForm = {
	acc_no: "", acc_name: "", bank: "", bank_branch: "",
	beneficiary_type: "", resident_status: "", is_default: false,
};

const defTax: TaxForm = {
	npwp_type: "", npwp_no: "", npwp_detail: "", npwp_nm: "", npwp_addr: "",
	city: "", province: "", npwp_start: "", ppnsts: "", ppnstartdate: "",
	taxfree: "", taxfree2: "", pph: "", rate: "", dpp: "100",
	update_by: "", lastupdate: "", is_saved: false,
};

const cls = {
	inp: "w-full bg-white border border-gray-300 rounded-md px-2.5 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed",
	sel: "w-full bg-white border border-gray-300 rounded-md px-2.5 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed",
	ta: "w-full bg-white border border-gray-300 rounded-md px-2.5 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed resize-none",
	btn: "px-4 py-1.5 rounded-lg text-sm font-medium transition-colors",
};

function FieldRow({ label, children, hidden, required }:
	{ label: string; children: React.ReactNode; hidden?: boolean; required?: boolean }) {
	if (hidden) return null;
	return (
		<div className="flex items-start gap-3 py-2 border-b border-gray-100 last:border-0">
			<label className="w-40 text-sm text-gray-600 flex-shrink-0 pt-1.5 text-right">
				{label}{required && <span className="text-red-500 ml-0.5">*</span>}
			</label>
			<div className="flex-1">{children}</div>
		</div>
	);
}

function SelectField({ opts, value, onChange, disabled, placeholder = "Select" }:
	{ opts: Opt[]; value: string; onChange: (v: string) => void; disabled?: boolean; placeholder?: string; }) {
	return (
		<select value={value} onChange={e => onChange(e.target.value)} disabled={disabled} className={cls.sel}>
			<option value="">{placeholder}</option>
			{opts.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
		</select>
	);
}

function Msg({ msg }: { msg?: { type: "success" | "error"; text: string } }) {
	if (!msg) return null;
	return (
		<div className={`mt-3 p-3 rounded-lg text-sm ${msg.type === "success"
			? "bg-green-50 border border-green-200 text-green-800"
			: "bg-red-50 border border-red-200 text-red-800"}`}>
			{msg.text}
		</div>
	);
}

const SalesEntryPage: React.FC = () => {
	const navigate = useNavigate();
	const [searchParams] = useSearchParams();

	const mode0 = (searchParams.get("id") || "View") as Mode;
	const salesNo0 = searchParams.get("salesno") || "";
	const salType0 = searchParams.get("sal_type") || "";
	const brokerType0 = searchParams.get("broker") || "";

	const [mode, setMode] = useState<Mode>(mode0);
	const [currentSno, setCurrentSno] = useState(salesNo0);
	const [activeTab, setActiveTab] = useState<Tab>("main");
	const [options, setOptions] = useState<FormOptions | null>(null);
	const [cmoList, setCmoList] = useState<Opt[]>([]);

	const [main, setMain] = useState<MainForm>({ ...defMain, sal_type: salType0, broker: brokerType0 });
	const [pic, setPic] = useState<PicForm>(defPic);
	const [banks, setBanks] = useState<BankAccount[]>([]);
	const [bankForm, setBankForm] = useState<BankForm>(defBankForm);
	const [bankEdit, setBankEdit] = useState<string | null>(null);
	const [tax, setTax] = useState<TaxForm>(defTax);

	const [saving, setSaving] = useState<Partial<Record<Tab, boolean>>>({});
	const [msgs, setMsgs] = useState<Partial<Record<Tab, { type: "success" | "error"; text: string }>>>({});

	const [filesByType, setFilesByType] = useState<Record<string, SalesFile[]>>({});
	const [lainnya, setLainnya] = useState("");
	const [uploading, setUploading] = useState<string | null>(null);

	const [notes, setNotes] = useState("");
	const [savingNotes, setSavingNotes] = useState(false);

	const isView = mode === "View";
	const mainSaved = currentSno !== "";

	const salType = main.sal_type;
	const brokerType = main.broker;

	const showBroker = salType === "PT";
	const showPersonal = salType === "PR" || (salType === "PT" && brokerType === "PR");
	const showCompany = salType === "PT" && brokerType === "PT";
	const showCertainDate = main.exp_date === "1";
	const showPicTab = salType === "PT" && brokerType !== "";
	const taxNpwpType = tax.npwp_type;
	const showNpwpStart = taxNpwpType === "PR";
	const showPpnFields = taxNpwpType === "PT";
	const npwpFieldsLocked = taxNpwpType === "00" || isView || tax.is_saved;

	const tabs: { id: Tab; label: string; disabled: boolean }[] = [
		{ id: "main", label: "Main", disabled: false },
		{ id: "pic", label: "PIC", disabled: !showPicTab || (!mainSaved && mode === "Add") },
		{ id: "bank", label: "Bank Account", disabled: !mainSaved && mode === "Add" },
		{ id: "tax", label: "Tax", disabled: !mainSaved && mode === "Add" },
		{ id: "doc", label: "Document Sales", disabled: !mainSaved && mode === "Add" },
		{ id: "notes", label: "Additional Notes", disabled: !mainSaved && mode === "Add" },
	];

	useEffect(() => {
		api.get("/MasterData/api/sales-entry/options")
			.then(r => {
				setOptions(r.data);
				if (mode === "Add" && r.data.current_user) {
					setMain(f => ({ ...f, create_by: r.data.current_user }));
				}
			})
			.catch(() => setMsgs(m => ({ ...m, main: { type: "error", text: "Failed to load form options." } })));
	}, []);  // eslint-disable-line react-hooks/exhaustive-deps

	const loadCmo = useCallback((branchCd: string) => {
		if (!branchCd) { setCmoList([]); return; }
		api.get("/MasterData/api/sales-entry/cmo-list", { params: { branch_cd: branchCd } })
			.then(r => setCmoList(r.data))
			.catch(() => setCmoList([]));
	}, []);

	const loadFiles = useCallback(async () => {
		if (!currentSno) return;
		try {
			const r = await api.get(`/MasterData/api/sales-entry/${currentSno}/files`);
			setFilesByType(r.data.files || {});
			setLainnya(r.data.lainnya || "");
		} catch {
			setMsgs(m => ({ ...m, doc: { type: "error", text: "Failed to load files." } }));
		}
	}, [currentSno]);

	const loadNotes = useCallback(async () => {
		if (!currentSno) return;
		try {
			const r = await api.get(`/MasterData/api/sales-entry/${currentSno}/notes`);
			setNotes(r.data.notes || "");
		} catch {
			setMsgs(m => ({ ...m, notes: { type: "error", text: "Failed to load notes." } }));
		}
	}, [currentSno]);

	useEffect(() => {
		if (activeTab === "doc" && currentSno) loadFiles();
		if (activeTab === "notes" && currentSno) loadNotes();
	}, [activeTab, currentSno, loadFiles, loadNotes]);

	useEffect(() => {
		if ((mode === "Edit" || mode === "View") && salesNo0) {
			api.get(`/MasterData/api/sales-entry/${salesNo0}`)
				.then(r => {
					const d = r.data;
					setMain({ ...defMain, ...d.main });
					if (d.pic) setPic(p => ({ ...p, ...d.pic }));
					if (d.banks) setBanks(d.banks);
					if (d.tax) setTax(t => ({ ...t, ...d.tax }));
					loadCmo(d.main.branch || "");
				})
				.catch(() =>
					setMsgs(m => ({ ...m, main: { type: "error", text: "Failed to load sales data." } })));
		}
	}, [mode, salesNo0, loadCmo]);

	const setMsg = (tab: Tab, msg: { type: "success" | "error"; text: string } | undefined) =>
		setMsgs(m => ({ ...m, [tab]: msg }));

	const onMain = (field: keyof MainForm, val: string) => {
		setMain(f => {
			const next = { ...f, [field]: val };
			if (field === "sal_type") {
				next.broker = "";
				if (val === "PT") {
					next.idcard = "";
					next.certain_per = "";
					next.exp_date = "0";
				}
			}

			if (field === "broker" && val === "PT") {
				next.idcard = "";
				next.certain_per = "";
				next.exp_date = "0";
			}

			if (field === "branch") loadCmo(val);
			return next;
		});
	};

	const handleSaveMain = async () => {
		if (!main.name || !main.branch || !main.sal_type) {
			setMsg("main", { type: "error", text: "Name, Branch, and Sales Type are required." });
			return;
		}
		setSaving(s => ({ ...s, main: true }));
		setMsg("main", undefined);
		try {
			if (mode === "Add") {
				const r = await api.post("/MasterData/api/sales-entry", main);
				if (r.data.success) {
					const sno = r.data.sales_no;
					setCurrentSno(sno);
					setMain(f => ({ ...f, sales_no: sno }));
					setMode("Edit");
					setMsg("main", { type: "success", text: `Sales created successfully. Sales No: ${sno}` });
					navigate(`/sales-entry?id=Edit&salesno=${sno}&sal_type=${main.sal_type}&broker=${main.broker}`, { replace: true });
				} else {
					setMsg("main", { type: "error", text: r.data.message || "Save failed." });
				}
			} else {
				const r = await api.put(`/MasterData/api/sales-entry/${currentSno}`, main);
				if (r.data.success) {
					setMsg("main", { type: "success", text: "Main tab updated successfully." });
				} else {
					setMsg("main", { type: "error", text: r.data.message || "Update failed." });
				}
			}
		} catch {
			setMsg("main", { type: "error", text: "An error occurred. Please try again." });
		} finally {
			setSaving(s => ({ ...s, main: false }));
		}
	};

	const handleSavePic = async () => {
		setSaving(s => ({ ...s, pic: true }));
		setMsg("pic", undefined);
		try {
			const method = pic.cont_idcard ? "put" : "post";
			const r = await api[method](`/MasterData/api/sales-entry/${currentSno}/pic`, { ...pic, sal_type: main.sal_type });
			setMsg("pic", r.data.success
				? { type: "success", text: "PIC saved successfully." }
				: { type: "error", text: r.data.message || "Save failed." });
		} catch {
			setMsg("pic", { type: "error", text: "An error occurred." });
		} finally {
			setSaving(s => ({ ...s, pic: false }));
		}
	};

	const loadBanks = useCallback(async () => {
		if (!currentSno) return;
		const r = await api.get(`/MasterData/api/sales-entry/${currentSno}/bank-accounts`);
		setBanks(r.data);
	}, [currentSno]);

	useEffect(() => {
		if (activeTab === "bank" && currentSno) loadBanks();
	}, [activeTab, currentSno, loadBanks]);

	const handleAddBank = async () => {
		if (!bankForm.acc_no || !bankForm.acc_name || !bankForm.bank) {
			setMsg("bank", { type: "error", text: "Account No., Name, and Bank are required." });
			return;
		}
		setSaving(s => ({ ...s, bank: true }));
		setMsg("bank", undefined);
		try {
			const r = bankEdit !== null
				? await api.put(`/MasterData/api/sales-entry/${currentSno}/bank-accounts/${bankEdit}`, bankForm)
				: await api.post(`/MasterData/api/sales-entry/${currentSno}/bank-accounts`, bankForm);
			if (r.data.success) {
				setBankForm(defBankForm);
				setBankEdit(null);
				await loadBanks();
				setMsg("bank", { type: "success", text: bankEdit ? "Bank account updated." : "Bank account added." });
			} else {
				setMsg("bank", { type: "error", text: r.data.message || "Save failed." });
			}
		} catch {
			setMsg("bank", { type: "error", text: "An error occurred." });
		} finally {
			setSaving(s => ({ ...s, bank: false }));
		}
	};

	const handleDeleteBank = async (accNo: string) => {
		if (!window.confirm(`Delete account ${accNo}?`)) return;
		try {
			await api.delete(`/MasterData/api/sales-entry/${currentSno}/bank-accounts/${accNo}`);
			await loadBanks();
			setMsg("bank", { type: "success", text: "Account deleted." });
		} catch {
			setMsg("bank", { type: "error", text: "Delete failed." });
		}
	};

	const handleEditBank = (b: BankAccount) => {
		setBankEdit(b.acc_no);
		setBankForm({
			acc_no: b.acc_no, acc_name: b.acc_name, bank: b.bank,
			bank_branch: b.bank_branch, beneficiary_type: b.beneficiary_type,
			resident_status: b.resident_status, is_default: b.is_default,
		});
	};

	const handleSaveTax = async () => {
		setSaving(s => ({ ...s, tax: true }));
		setMsg("tax", undefined);
		try {
			const method = tax.is_saved ? "put" : "post";
			const r = await api[method](`/MasterData/api/sales-entry/${currentSno}/tax`, {
				...tax, sal_type: main.sal_type, gender: main.gender,
			});
			if (r.data.success) {
				setTax(t => ({ ...t, is_saved: true }));
				setMsg("tax", { type: "success", text: "Tax information saved." });
			} else {
				setMsg("tax", { type: "error", text: r.data.message || "Save failed." });
			}
		} catch {
			setMsg("tax", { type: "error", text: "An error occurred." });
		} finally {
			setSaving(s => ({ ...s, tax: false }));
		}
	};

	const onTaxNpwpType = (val: string) => {
		setTax(t => ({
			...t,
			npwp_type: val,
			pph: val === "PT" ? "2" : "1",
			rate: val === "PT" ? "2" : "",
			dpp: "100",
		}));
	};

	const handleFileUpload = async (docType: string, fileList: FileList) => {
		if (!fileList.length) return;
		setUploading(docType);
		setMsg("doc", undefined);
		const fd = new FormData();
		Array.from(fileList).forEach(f => fd.append("file", f));
		if (docType === "sales-other" && lainnya) fd.append("lainnya", lainnya);
		try {
			const r = await api.post(
				`/MasterData/api/sales-entry/${currentSno}/files/${docType}`,
				fd,
				{ headers: { "Content-Type": "multipart/form-data" } }
			);
			if (r.data.success) {
				await loadFiles();
				setMsg("doc", { type: "success", text: `${r.data.uploaded?.length ?? 1} file(s) uploaded.` });
			} else {
				setMsg("doc", { type: "error", text: r.data.message || "Upload failed." });
			}
		} catch {
			setMsg("doc", { type: "error", text: "Upload failed. Please try again." });
		} finally {
			setUploading(null);
		}
	};

	const handleFileDelete = async (fileId: number) => {
		if (!window.confirm("Delete this file?")) return;
		try {
			await api.delete(`/MasterData/api/sales-entry/${currentSno}/files/${fileId}`);
			await loadFiles();
			setMsg("doc", { type: "success", text: "File deleted." });
		} catch {
			setMsg("doc", { type: "error", text: "Delete failed." });
		}
	};

	const handleFileDownload = async (f: SalesFile) => {
		try {
			const r = await api.get(f.download_url);
			window.open(r.data.url, "_blank", "noopener,noreferrer");
		} catch {
			setMsg("doc", { type: "error", text: "Failed to get download link." });
		}
	};

	const handleSaveNotes = async () => {
		setSavingNotes(true);
		setMsg("notes", undefined);
		try {
			const r = await api.post(`/MasterData/api/sales-entry/${currentSno}/notes`, { notes });
			setMsg("notes", r.data.success
				? { type: "success", text: "Notes saved successfully." }
				: { type: "error", text: r.data.message || "Save failed." });
		} catch {
			setMsg("notes", { type: "error", text: "An error occurred." });
		} finally {
			setSavingNotes(false);
		}
	};

	if (!options) return <div className="p-8 text-center text-gray-400">Loading form…</div>;

	const npwpTypeOpts = salType === "PT" && brokerType === "PT"
		? options.npwp_types_pt
		: options.npwp_types_pr;

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="mx-auto max-w-6xl">

				<div className="mb-4 flex items-center justify-between">
					<div>
						<h1 className="text-xl font-bold text-gray-800">
							{mode === "Add" ? "Add New Sales" : `Sales Entry — ${currentSno}`}
						</h1>
						<p className="text-sm text-gray-500">
							{mode === "Add" ? "Create a new sales record" : `${mode} mode${main.sal_type ? ` · ${main.sal_type}` : ""}${main.broker ? ` / ${main.broker}` : ""}`}
						</p>
					</div>
					<button
						onClick={() => navigate("/sales")}
						className={`${cls.btn} border border-gray-300 text-gray-700 hover:bg-gray-50`}
					>
						← Back to Sales
					</button>
				</div>

				<div className="rounded-2xl bg-white shadow-lg overflow-hidden">
					<div className="flex border-b border-gray-200 bg-gray-50 overflow-x-auto">
						{tabs.map(t => (
							<button
								key={t.id}
								disabled={t.disabled}
								onClick={() => !t.disabled && setActiveTab(t.id)}
								className={`
										px-5 py-3 text-sm font-medium whitespace-nowrap transition-colors
										${activeTab === t.id
										? "border-b-2 border-blue-600 text-blue-600 bg-white"
										: t.disabled
											? "text-gray-300 cursor-not-allowed"
											: "text-gray-500 hover:text-gray-700 hover:bg-white"}
                		`}
							>
								{t.label}
							</button>
						))}
					</div>

					<div className="p-6">

						{activeTab === "main" && (
							<div>
								<h2 className="text-base font-semibold text-gray-700 mb-4 pb-2 border-b">SALES</h2>
								<div className="space-y-0">

									<FieldRow label="Sales Type" required>
										<SelectField opts={options.sales_types} value={main.sal_type}
											onChange={v => onMain("sal_type", v)} disabled={isView}
											placeholder="Select Sales Type" />
									</FieldRow>

									<FieldRow label="Broker Type" hidden={!showBroker}>
										<SelectField opts={options.broker_types} value={main.broker}
											onChange={v => onMain("broker", v)} disabled={isView}
											placeholder="Select Broker Type" />
									</FieldRow>

									<FieldRow label="Status">
										<SelectField opts={[{ value: "A", label: "Active" }, { value: "I", label: "Inactive" }]}
											value={main.status} onChange={v => onMain("status", v)} disabled={isView} />
									</FieldRow>

									<FieldRow label="Branch" required>
										<SelectField opts={options.branches} value={main.branch}
											onChange={v => onMain("branch", v)} disabled={isView}
											placeholder="Select Branch" />
									</FieldRow>

									<FieldRow label="CMO Name">
										<SelectField opts={cmoList} value={main.cmo_name}
											onChange={v => onMain("cmo_name", v)} disabled={isView}
											placeholder="Select CMO" />
									</FieldRow>

									<FieldRow label="Sales / Broker No.">
										<input value={main.sales_no || (mode === "Add" ? "(assigned on save)" : "")}
											readOnly className={cls.inp} />
									</FieldRow>

									<FieldRow label="Initial Sales No." hidden={!main.initial_sales_no}>
										<input value={main.initial_sales_no} readOnly className={cls.inp} />
									</FieldRow>

									<FieldRow label="Name" required>
										<input value={main.name} disabled={isView}
											onChange={e => onMain("name", e.target.value)} className={cls.inp} />
									</FieldRow>

									<FieldRow label="Gender">
										<SelectField opts={options.genders} value={main.gender}
											onChange={v => onMain("gender", v)} disabled={isView} placeholder="Select" />
									</FieldRow>

									<FieldRow label="Nick Name" hidden={!showCompany}>
										<input value={main.nick_name} disabled={isView}
											onChange={e => onMain("nick_name", e.target.value)} className={cls.inp} />
									</FieldRow>

									<FieldRow label="Occupation" hidden={!showPersonal}>
										<SelectField opts={options.occupations} value={main.bd_occupation}
											onChange={v => onMain("bd_occupation", v)} disabled={isView} placeholder="Select" />
									</FieldRow>

									<FieldRow label="ID Card" hidden={!showPersonal}>
										<input value={main.idcard} disabled={isView}
											onChange={e => onMain("idcard", e.target.value.replace(/\D/g, ""))}
											className={cls.inp} maxLength={16} />
									</FieldRow>

									<FieldRow label="ID Valid Date" hidden={!showPersonal}>
										<div className="flex items-center gap-4">
											<label className="flex items-center gap-1.5 text-sm cursor-pointer">
												<input type="radio" name="exp_date" value="0" disabled={isView}
													checked={main.exp_date === "0"}
													onChange={() => onMain("exp_date", "0")} />
												No Expire Date
											</label>
											<label className="flex items-center gap-1.5 text-sm cursor-pointer">
												<input type="radio" name="exp_date" value="1" disabled={isView}
													checked={main.exp_date === "1"}
													onChange={() => onMain("exp_date", "1")} />
												Certain Period
											</label>
										</div>
										{showCertainDate && (
											<input type="date" className={`${cls.inp} mt-2 w-48`}
												value={main.certain_per ? main.certain_per.split("-").reverse().join("-") : ""}
												disabled={isView}
												onChange={e => {
													const v = e.target.value; // YYYY-MM-DD
													if (v) {
														const [y, m, d] = v.split("-");
														onMain("certain_per", `${d}-${m}-${y}`);
													}
												}} />
										)}
									</FieldRow>

									<FieldRow label="Address">
										<textarea value={main.address} disabled={isView} rows={2}
											onChange={e => onMain("address", e.target.value)} className={cls.ta} />
									</FieldRow>

									<FieldRow label="City / Post Code">
										<div className="flex gap-2">
											<input value={main.city_sales} disabled={isView}
												onChange={e => onMain("city_sales", e.target.value)}
												className={cls.inp} placeholder="City" />
											<input value={main.post} disabled={isView}
												onChange={e => onMain("post", e.target.value.replace(/\D/g, ""))}
												className={`${cls.inp} w-28`} maxLength={5} placeholder="Post Code" />
										</div>
									</FieldRow>

									<FieldRow label="Phone">
										<input value={main.phone} disabled={isView}
											onChange={e => onMain("phone", e.target.value.replace(/\D/g, ""))}
											className={cls.inp} />
									</FieldRow>

									<FieldRow label="Email Address" hidden={!showPersonal}>
										<input type="email" value={main.email_addr} disabled={isView}
											onChange={e => onMain("email_addr", e.target.value)} className={cls.inp} />
									</FieldRow>

									<FieldRow label="Fax" hidden={!showCompany}>
										<input value={main.fax} disabled={isView}
											onChange={e => onMain("fax", e.target.value.replace(/\D/g, ""))}
											className={cls.inp} />
									</FieldRow>

									<FieldRow label="Refund Payment">
										<div className="flex items-center gap-4">
											{[{ v: "1", l: "Paid" }, { v: "0", l: "Hold" }].map(({ v, l }) => (
												<label key={v} className="flex items-center gap-1.5 text-sm cursor-pointer">
													<input type="radio" name="paid" value={v} disabled={isView}
														checked={main.paid === v} onChange={() => onMain("paid", v)} />
													{l}
												</label>
											))}
										</div>
									</FieldRow>

									<FieldRow label="Created By">
										<input value={main.create_by} readOnly className={cls.inp} />
									</FieldRow>
									<FieldRow label="Created Date">
										<input value={main.create_date} readOnly className={`${cls.inp} w-48`} />
									</FieldRow>

									{(main.update_by || main.lastupdate) && (
										<>
											<FieldRow label="Updated By">
												<input value={main.update_by} readOnly className={cls.inp} />
											</FieldRow>
											<FieldRow label="Last Update">
												<input value={main.lastupdate} readOnly className={`${cls.inp} w-48`} />
											</FieldRow>
										</>
									)}
								</div>

								{!isView && (
									<div className="mt-6 flex gap-3">
										<button onClick={handleSaveMain} disabled={saving.main}
											className={`${cls.btn} bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-60`}>
											{saving.main ? "Saving…" : mode === "Add" ? "Save" : "Update"}
										</button>
										<button onClick={() => navigate("/sales")}
											className={`${cls.btn} border border-gray-300 text-gray-700 hover:bg-gray-50`}>
											Cancel
										</button>
									</div>
								)}
								<Msg msg={msgs.main} />
							</div>
						)}

						{activeTab === "pic" && showPicTab && (
							<div>
								<h2 className="text-base font-semibold text-gray-700 mb-4 pb-2 border-b">PIC SALES</h2>
								<div className="space-y-0">

									<FieldRow label="Contact Person">
										<input value={pic.cont_name} disabled={isView}
											onChange={e => setPic(f => ({ ...f, cont_name: e.target.value }))} className={cls.inp} />
									</FieldRow>

									<FieldRow label="Occupation">
										<SelectField opts={options.pic_occupations} value={pic.occupation}
											onChange={v => setPic(f => ({ ...f, occupation: v }))} disabled={isView} placeholder="Select" />
									</FieldRow>

									<FieldRow label="ID Card">
										<input value={pic.cont_idcard} disabled={isView}
											onChange={e => setPic(f => ({ ...f, cont_idcard: e.target.value }))} className={cls.inp} />
									</FieldRow>

									<FieldRow label="ID Valid Date">
										<div className="flex items-center gap-4">
											{[{ v: "0", l: "No Expire Date" }, { v: "1", l: "Certain Period" }].map(({ v, l }) => (
												<label key={v} className="flex items-center gap-1.5 text-sm cursor-pointer">
													<input type="radio" name="pic_exp" value={v} disabled={isView}
														checked={pic.exp_date === v}
														onChange={() => setPic(f => ({ ...f, exp_date: v }))} />
													{l}
												</label>
											))}
										</div>
										{pic.exp_date === "1" && (
											<input type="date" className={`${cls.inp} mt-2 w-48`}
												value={pic.id_validdt ? pic.id_validdt.split("-").reverse().join("-") : ""}
												disabled={isView}
												onChange={e => {
													const v = e.target.value;
													if (v) {
														const [y, m, d] = v.split("-");
														setPic(f => ({ ...f, id_validdt: `${d}-${m}-${y}` }));
													}
												}} />
										)}
									</FieldRow>

									<FieldRow label="Address">
										<textarea value={pic.cont_addr} disabled={isView} rows={2}
											onChange={e => setPic(f => ({ ...f, cont_addr: e.target.value }))} className={cls.ta} />
									</FieldRow>

									<FieldRow label="City / Post Code">
										<div className="flex gap-2">
											<input value={pic.cont_city} disabled={isView}
												onChange={e => setPic(f => ({ ...f, cont_city: e.target.value }))}
												className={cls.inp} placeholder="City" />
											<input value={pic.post} disabled={isView}
												onChange={e => setPic(f => ({ ...f, post: e.target.value.replace(/\D/g, "") }))}
												className={`${cls.inp} w-28`} maxLength={5} placeholder="Post Code" />
										</div>
									</FieldRow>

									<FieldRow label="Phone">
										<input value={pic.cont_phone} disabled={isView}
											onChange={e => setPic(f => ({ ...f, cont_phone: e.target.value }))} className={cls.inp} />
									</FieldRow>

									<FieldRow label="Email Address">
										<input type="email" value={pic.email_addr} disabled={isView}
											onChange={e => setPic(f => ({ ...f, email_addr: e.target.value }))} className={cls.inp} />
									</FieldRow>
								</div>

								{!isView && (
									<div className="mt-6 flex gap-3">
										<button onClick={handleSavePic} disabled={saving.pic}
											className={`${cls.btn} bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-60`}>
											{saving.pic ? "Saving…" : pic.cont_name ? "Update" : "Save"}
										</button>
										<button onClick={() => navigate("/sales")}
											className={`${cls.btn} border border-gray-300 text-gray-700 hover:bg-gray-50`}>
											Cancel
										</button>
									</div>
								)}
								<Msg msg={msgs.pic} />
							</div>
						)}

						{activeTab === "bank" && (
							<div>
								<h2 className="text-base font-semibold text-gray-700 mb-4 pb-2 border-b">BANK ACCOUNT</h2>

								{!isView && (
									<div className="mb-6 p-4 bg-gray-50 rounded-xl border border-gray-200">
										<p className="text-sm font-medium text-gray-600 mb-3">
											{bankEdit ? `Edit account: ${bankEdit}` : "Add Commission Account"}
										</p>
										<div className="grid grid-cols-2 gap-3">
											<FieldRow label="Account Type">
												<input value="Commission Account (C)" readOnly className={cls.inp} />
											</FieldRow>
											<FieldRow label="Account Name" required>
												<input value={bankForm.acc_name}
													onChange={e => setBankForm(f => ({ ...f, acc_name: e.target.value }))}
													className={cls.inp} />
											</FieldRow>
											<FieldRow label="Account No." required>
												<input value={bankForm.acc_no} readOnly={bankEdit !== null}
													onChange={e => setBankForm(f => ({ ...f, acc_no: e.target.value.replace(/\D/g, "") }))}
													className={cls.inp} maxLength={50} />
											</FieldRow>
											<FieldRow label="Bank" required>
												<SelectField opts={options.banks} value={bankForm.bank}
													onChange={v => setBankForm(f => ({ ...f, bank: v }))} placeholder="Select Bank" />
											</FieldRow>
											<FieldRow label="Bank Branch">
												<input value={bankForm.bank_branch}
													onChange={e => setBankForm(f => ({ ...f, bank_branch: e.target.value }))}
													className={cls.inp} />
											</FieldRow>
											<FieldRow label="Beneficiary Type">
												<SelectField opts={options.beneficiary_types} value={bankForm.beneficiary_type}
													onChange={v => setBankForm(f => ({ ...f, beneficiary_type: v }))} placeholder="Select" />
											</FieldRow>
											<FieldRow label="Resident Status">
												<SelectField opts={options.resident_statuses} value={bankForm.resident_status}
													onChange={v => setBankForm(f => ({ ...f, resident_status: v }))} placeholder="Select" />
											</FieldRow>
											<FieldRow label="Default">
												<label className="flex items-center gap-2 text-sm cursor-pointer">
													<input type="checkbox" checked={bankForm.is_default}
														onChange={e => setBankForm(f => ({ ...f, is_default: e.target.checked }))}
														className="w-4 h-4 rounded border-gray-300 text-blue-600" />
													Set as Default
												</label>
											</FieldRow>
										</div>
										<div className="mt-3 flex gap-2">
											<button onClick={handleAddBank} disabled={saving.bank}
												className={`${cls.btn} bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-60`}>
												{saving.bank ? "Saving…" : bankEdit ? "Update" : "Save"}
											</button>
											{bankEdit && (
												<button onClick={() => { setBankEdit(null); setBankForm(defBankForm); }}
													className={`${cls.btn} border border-gray-300 text-gray-700 hover:bg-gray-50`}>
													Cancel Edit
												</button>
											)}
										</div>
									</div>
								)}

								<div className="overflow-x-auto rounded-lg border border-gray-200">
									<table className="w-full text-sm">
										<thead className="bg-gray-50 text-xs text-gray-500 uppercase">
											<tr>
												{!isView && <th className="px-3 py-2 text-left">Action</th>}
												<th className="px-3 py-2 text-left">Account Name</th>
												<th className="px-3 py-2 text-left">Account No.</th>
												<th className="px-3 py-2 text-left">Bank</th>
												<th className="px-3 py-2 text-left">Branch</th>
												<th className="px-3 py-2 text-left">Ben. Type</th>
												<th className="px-3 py-2 text-left">Resident</th>
												<th className="px-3 py-2 text-center">Default</th>
											</tr>
										</thead>
										<tbody className="divide-y divide-gray-100">
											{banks.length === 0 ? (
												<tr><td colSpan={isView ? 7 : 8} className="py-6 text-center text-gray-400">No bank accounts yet</td></tr>
											) : banks.map(b => (
												<tr key={b.acc_no} className="hover:bg-gray-50">
													{!isView && (
														<td className="px-3 py-2 whitespace-nowrap">
															<button onClick={() => handleEditBank(b)} title="Edit"
																className="text-blue-600 hover:text-blue-800 mr-2 text-xs">Edit</button>
															<button onClick={() => handleDeleteBank(b.acc_no)} title="Delete"
																className="text-red-500 hover:text-red-700 text-xs">Del</button>
														</td>
													)}
													<td className="px-3 py-2">{b.acc_name}</td>
													<td className="px-3 py-2 font-mono">{b.acc_no}</td>
													<td className="px-3 py-2">{b.bank_name || b.bank}</td>
													<td className="px-3 py-2">{b.bank_branch}</td>
													<td className="px-3 py-2">{b.ben_type_label || b.beneficiary_type}</td>
													<td className="px-3 py-2">{b.res_status_label || b.resident_status}</td>
													<td className="px-3 py-2 text-center">
														{b.is_default
															? <span className="text-green-600 font-bold">✓</span>
															: <span className="text-gray-300">—</span>}
													</td>
												</tr>
											))}
										</tbody>
									</table>
								</div>
								<Msg msg={msgs.bank} />
							</div>
						)}

						{activeTab === "tax" && (
							<div>
								<h2 className="text-base font-semibold text-gray-700 mb-4 pb-2 border-b">TAX</h2>
								{tax.is_saved && !isView && (
									<div className="mb-3 p-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg">
										Tax has been saved. Fields are locked after first save (matches legacy behaviour).
										Contact admin to modify.
									</div>
								)}
								<div className="space-y-0">

									<FieldRow label="NPWP Type" required>
										<SelectField opts={npwpTypeOpts} value={tax.npwp_type}
											onChange={onTaxNpwpType}
											disabled={isView || (tax.is_saved && salType === "PT")}
											placeholder="Select" />
									</FieldRow>

									<FieldRow label="NPWP No.">
										<input value={tax.npwp_no} disabled={npwpFieldsLocked}
											onChange={e => setTax(t => ({ ...t, npwp_no: e.target.value.replace(/\D/g, "") }))}
											className={cls.inp} maxLength={15} placeholder="XX.XXX.XXX.X-XXX.XXXX" />
									</FieldRow>

									<FieldRow label="NPWP Detail">
										<SelectField opts={options.npwp_details} value={tax.npwp_detail}
											onChange={v => setTax(t => ({ ...t, npwp_detail: v }))}
											disabled={npwpFieldsLocked || main.gender === "M"}
											placeholder="Select" />
									</FieldRow>

									<FieldRow label="NPWP Name">
										<input value={tax.npwp_nm} disabled={npwpFieldsLocked}
											onChange={e => setTax(t => ({ ...t, npwp_nm: e.target.value }))} className={cls.inp} />
									</FieldRow>

									<FieldRow label="NPWP Address">
										<textarea value={tax.npwp_addr} disabled={npwpFieldsLocked} rows={2}
											onChange={e => setTax(t => ({ ...t, npwp_addr: e.target.value }))} className={cls.ta} />
									</FieldRow>

									<FieldRow label="Province">
										<SelectField opts={options.provinces} value={tax.province}
											onChange={v => setTax(t => ({ ...t, province: v }))}
											disabled={npwpFieldsLocked} placeholder="Select Province" />
									</FieldRow>

									<FieldRow label="City">
										<SelectField
											opts={(options.cities || []).filter(c => !tax.province || c.province === tax.province)}
											value={tax.city}
											onChange={v => setTax(t => ({ ...t, city: v }))}
											disabled={npwpFieldsLocked} placeholder="Select City" />
									</FieldRow>

									<FieldRow label="NPWP Start" hidden={!showNpwpStart}>
										<input value={tax.npwp_start} disabled={isView}
											onChange={e => setTax(t => ({ ...t, npwp_start: e.target.value.replace(/\D/g, "") }))}
											className={`${cls.inp} w-24`} maxLength={4} placeholder="YYYY" />
									</FieldRow>

									<FieldRow label="PPN Status" hidden={!showPpnFields}>
										<SelectField opts={[{ value: "1", label: "PPN" }, { value: "0", label: "Non PPN" }]}
											value={tax.ppnsts} onChange={v => setTax(t => ({ ...t, ppnsts: v }))}
											disabled={npwpFieldsLocked} placeholder="Select" />
									</FieldRow>

									<FieldRow label="PPN Start Date" hidden={!showPpnFields}>
										<input value={tax.ppnstartdate} readOnly className={`${cls.inp} w-36`} />
									</FieldRow>

									<FieldRow label="Tax Free (From – To)" hidden={!showPpnFields}>
										<div className="flex items-center gap-2">
											<input type="date" disabled={npwpFieldsLocked}
												value={tax.taxfree ? tax.taxfree.split("-").reverse().join("-") : ""}
												onChange={e => {
													const v = e.target.value;
													if (v) {
														const [y, m, d] = v.split("-");
														setTax(t => ({ ...t, taxfree: `${d}-${m}-${y}` }));
													}
												}} className={`${cls.inp} w-40`} />
											<span className="text-gray-400">to</span>
											<input type="date" disabled={npwpFieldsLocked}
												value={tax.taxfree2 ? tax.taxfree2.split("-").reverse().join("-") : ""}
												onChange={e => {
													const v = e.target.value;
													if (v) {
														const [y, m, d] = v.split("-");
														setTax(t => ({ ...t, taxfree2: `${d}-${m}-${y}` }));
													}
												}} className={`${cls.inp} w-40`} />
										</div>
									</FieldRow>

									<FieldRow label="Tax Type">
										<SelectField opts={options.tax_types} value={tax.pph}
											onChange={() => { }} disabled={true} placeholder="—" />
									</FieldRow>

									<FieldRow label="Tax Rate">
										<div className="flex items-center gap-2">
											<SelectField
												opts={[{ value: "1", label: "Progressive" }, { value: "2", label: "Flat" }]}
												value={tax.rate} onChange={() => { }} disabled={true} placeholder="—" />
											{tax.rate === "2" && (
												<span className="text-sm text-gray-500">{tax.rate}%</span>
											)}
										</div>
									</FieldRow>

									<FieldRow label="DPP">
										<div className="flex items-center gap-2">
											<input value={tax.dpp} readOnly className={`${cls.inp} w-20`} />
											<span className="text-sm text-gray-500">% × Bruto</span>
										</div>
									</FieldRow>

									{(tax.update_by || tax.lastupdate) && (
										<>
											<FieldRow label="Update By">
												<input value={tax.update_by} readOnly className={cls.inp} />
											</FieldRow>
											<FieldRow label="Last Update">
												<input value={tax.lastupdate} readOnly className={`${cls.inp} w-40`} />
											</FieldRow>
										</>
									)}
								</div>

								{!isView && !tax.is_saved && (
									<div className="mt-6 flex gap-3">
										<button onClick={handleSaveTax} disabled={saving.tax}
											className={`${cls.btn} bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-60`}>
											{saving.tax ? "Saving…" : "Save"}
										</button>
										<button onClick={() => navigate("/sales")}
											className={`${cls.btn} border border-gray-300 text-gray-700 hover:bg-gray-50`}>
											Cancel
										</button>
									</div>
								)}
								{!isView && tax.is_saved && (
									<div className="mt-6 flex gap-3">
										<button onClick={handleSaveTax} disabled={saving.tax}
											className={`${cls.btn} bg-amber-500 text-white hover:bg-amber-600 disabled:opacity-60`}>
											{saving.tax ? "Updating…" : "Update Tax"}
										</button>
									</div>
								)}
								<Msg msg={msgs.tax} />
							</div>
						)}

						{activeTab === "doc" && (() => {
							const { title, docs, showNpwpNote } = getDocConfig(salType, brokerType);

							const FileRow = ({ doc }: { doc: DocTypeConfig }) => {
								const filesForType = filesByType[doc.key] || [];
								const isUploading = uploading === doc.key;

								return (
									<tr className="border-b border-gray-100 align-top">
										<td className="py-3 pr-4 w-56 text-sm text-gray-700">
											{doc.label}
											{doc.hasLainnya && (
												<input
													className="mt-1 block w-full border border-gray-300 rounded px-2 py-1 text-xs
                                     focus:ring-1 focus:ring-blue-500 disabled:bg-gray-100"
													placeholder="Keterangan…"
													value={lainnya}
													disabled={isView}
													onChange={e => setLainnya(e.target.value)}
												/>
											)}
										</td>
										<td className="py-3">
											{!isView && (
												<label className={`
														inline-flex items-center gap-1.5 cursor-pointer rounded-lg border border-dashed
														border-blue-300 bg-blue-50 hover:bg-blue-100 px-3 py-1.5 text-xs text-blue-700
														transition-colors ${isUploading ? "opacity-60 cursor-not-allowed" : ""}
														`}>
													<svg className={`w-4 h-4 ${isUploading ? "animate-spin" : ""}`}
														fill="none" viewBox="0 0 24 24" stroke="currentColor">
														{isUploading
															? <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
															: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
														}
													</svg>
													{isUploading ? "Uploading…" : "Choose File(s)"}
													<input type="file" multiple className="hidden"
														disabled={isUploading}
														onChange={e => {
															if (e.target.files?.length) {
																handleFileUpload(doc.key, e.target.files);
																e.target.value = "";
															}
														}} />
												</label>
											)}

											{filesForType.length > 0 && (
												<div className="mt-2 space-y-1">
													{filesForType.map(f => (
														<div key={f.id}
															className="flex items-center gap-2 rounded-lg bg-gray-50 border border-gray-200 px-3 py-1.5">
															<svg className="w-4 h-4 flex-shrink-0 text-gray-400" fill="none"
																viewBox="0 0 24 24" stroke="currentColor">
																<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
																	d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
															</svg>
															<span className="text-xs text-gray-700 flex-1 truncate">
																{f.file_nm}{f.file_ext ? `.${f.file_ext}` : ""}
															</span>
															{f.created_date && (
																<span className="text-xs text-gray-400 whitespace-nowrap">{f.created_date}</span>
															)}
															<button onClick={() => handleFileDownload(f)}
																className="text-xs text-blue-600 hover:text-blue-800 font-medium whitespace-nowrap">
																Download
															</button>
															{!isView && (
																<button
																	onClick={() => handleFileDelete(f.id)}
																	className="text-xs text-red-500 hover:text-red-700 font-medium whitespace-nowrap">
																	Delete
																</button>
															)}
														</div>
													))}
												</div>
											)}
										</td>
									</tr>
								);
							};

							return (
								<div>
									<h2 className="text-base font-semibold text-gray-700 mb-4 pb-2 border-b">{title}</h2>
									<table className="w-full">
										<tbody>
											{docs.map(doc => (
												<React.Fragment key={doc.key}>
													<FileRow doc={doc} />
												</React.Fragment>
											))}
										</tbody>
									</table>
									{showNpwpNote && (
										<p className="mt-4 text-xs italic text-gray-500">
											*) Khusus jika terdapat perubahan Status NPWP atau Perubahan Nomor NPWP
										</p>
									)}
									<Msg msg={msgs.doc} />
								</div>
							);
						})()}

						{activeTab === "notes" && (
							<div>
								<h2 className="text-base font-semibold text-gray-700 mb-4 pb-2 border-b">
									Additional Notes
								</h2>
								<textarea
									value={notes}
									disabled={isView}
									onChange={e => setNotes(e.target.value)}
									rows={8}
									className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm
											font-sans focus:ring-2 focus:ring-blue-500 focus:border-blue-500
											disabled:bg-gray-100 disabled:cursor-not-allowed resize-none"
									placeholder={isView ? "" : "Enter additional notes here…"}
								/>
								{!isView && (
									<div className="mt-4 flex gap-3">
										<button
											onClick={handleSaveNotes}
											disabled={savingNotes}
											className={`${cls.btn} bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-60`}
										>
											{savingNotes ? "Saving…" : notes ? "Update" : "Save"}
										</button>
										<button
											onClick={() => navigate("/sales")}
											className={`${cls.btn} border border-gray-300 text-gray-700 hover:bg-gray-50`}
										>
											Cancel
										</button>
									</div>
								)}
								<Msg msg={msgs.notes} />
							</div>
						)}
					</div>
				</div>
			</div>
		</div>
	);
};

export default SalesEntryPage;