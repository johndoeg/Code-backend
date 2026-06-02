import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { useNavigate, useLocation } from "react-router-dom";

interface CustomerFormData {
	APLESS: string;
	LESSEE_NM: string;
	LESSEE_CAT: string;
	ALIAS_NAME: string;
	ID_CARD_NAME: string;
	PLACEBIRTH: string;
	TGLBIRTH: string;
	GENDER: "M" | "F" | "";
	RELIGION: string;
	CITIZEN: "WNI" | "WNA" | "";
	NATIONALITY: string;
	PASSPORT_NO: string;
	ID_CARD: string;
	ID_CARD_VALID: string;
	ID_CARD_EXPIRE_OPTION: "0" | "1";
	FAM_CARD: string;
	MOTHER_NAME: string;
	MARITAL: string;
	SPOUSE_NAME: string;
	SPOUSE_NAME_WT: string;
	SPOUSE_PLACEBIRTH: string;
	SPOUSE_TGLBIRTH: string;
	SPOUSE_CITIZEN: "WNI" | "WNA" | "";
	SPOUSE_NATIONALITY: string;
	SPOUSE_ID_CARD: string;
	SPOUSE_ID_CARD_VALID: string;
	SPOUSE_ID_CARD_EXPIRE_OPTION: "0" | "1";
	SPOUSE_PASSPORT: string;
	SPOUSE_MARRIAGE_AGREE: string;
	SPOUSE_DEPENDENT: string;
	RELATIONSHIP_MLCI: string;
	ADDRESS1: string;
	AREA_CD: string;
	PROVINCE: string;
	CITY: string;
	KECAMATAN: string;
	KELURAHAN: string;
	RT: string;
	RW: string;
	ZIPCODE: string;
	YEAR_LIVE: string;
	ADDRESS_NPWP: string;
	AREA_CD_NPWP: string;
	PROVINCE_NPWP: string;
	CITY_NPWP: string;
	KECAMATAN_NPWP: string;
	KELURAHAN_NPWP: string;
	ZIPCODE_NPWP: string;
	SPOUSE_ADDRESS: string;
	SPOUSE_AREA_CD: string;
	SPOUSE_PROVINCE: string;
	SPOUSE_CITY: string;
	SPOUSE_KECAMATAN: string;
	SPOUSE_KELURAHAN: string;
	SPOUSE_RT: string;
	SPOUSE_RW: string;
	SPOUSE_ZIPCODE: string;
	SPOUSE_ADDRESS_SAME: boolean;
	PHONE_CODE: string;
	PHONE_AREA: string;
	PHONE_NUMBER: string;
	FAX_CODE: string;
	FAX_AREA: string;
	FAX_NUMBER: string;
	MOBILE1_CODE: string;
	MOBILE1_NUMBER: string;
	MOBILE2_CODE: string;
	MOBILE2_NUMBER: string;
	MOBILE3_CODE: string;
	MOBILE3_NUMBER: string;
	OTHER_PHONE1_CODE: string;
	OTHER_PHONE1_AREA: string;
	OTHER_PHONE1_NUMBER: string;
	OTHER_PHONE1_NOTES: string;
	OTHER_PHONE2_CODE: string;
	OTHER_PHONE2_AREA: string;
	OTHER_PHONE2_NUMBER: string;
	OTHER_PHONE2_NOTES: string;
	SEND_SMS: boolean;
	EMAIL1: string;
	EMAIL2: string;
	OCCUPATION_TYPE: string;
	LAST_EDUCATION: string;
	CAREER_FIELD: string;
	INDUS_CODE: string;
	INDUS_CODE_1: string;
	INDUS_CODE_2: string;
	INDUS_CODE_3: string;
	INDUS_CODE_4: string;
	INDUS_CODE_5: string;
	MLCL_CODE: string;
	NPWP: string;
	NPWP_AREA_CD: string;
	CUST_TYPE: string;
	GRP_CODE: string;
	EMERGENCY_NAME: string;
	EMERGENCY_ADDRESS: string;
	EMERGENCY_PHONE: string;
	EMERGENCY_RELATION: string;
}

interface ComboOption { VALUE: string; DESC_VALUE: string; }
interface Area { AREA_CD: string; Propinsi: string; Kabupaten: string; }
interface Kecamatan { Kecamatan_CD: string; Desc_Name: string; }
interface Kelurahan { Kelurahan_CD: string; Desc_Name: string; }
interface IndustryCode { MLCI_Code: string; Descrip: string; Header: string; Parent: string; }
interface ApiResponse<T> { success: boolean; message: string; data?: T; }

const API_URL = import.meta.env.VITE_API_URL;

const CustomerDetailInformation: React.FC = () => {
	const navigate = useNavigate();
	const location = useLocation();
	const params = new URLSearchParams(location.search);
	const mode = params.get("id") as "Add" | "Edit" | "View" | null;
	const apless = params.get("apless") || "";
	const applno = params.get("applno") || "";

	const [formData, setFormData] = useState<CustomerFormData>({
		APLESS: "", LESSEE_NM: "", LESSEE_CAT: "", ALIAS_NAME: "", ID_CARD_NAME: "",
		PLACEBIRTH: "", TGLBIRTH: "", GENDER: "", RELIGION: "", CITIZEN: "", NATIONALITY: "",
		PASSPORT_NO: "", ID_CARD: "", ID_CARD_VALID: "", ID_CARD_EXPIRE_OPTION: "1",
		FAM_CARD: "", MOTHER_NAME: "", MARITAL: "", SPOUSE_NAME: "", SPOUSE_NAME_WT: "",
		SPOUSE_PLACEBIRTH: "", SPOUSE_TGLBIRTH: "", SPOUSE_CITIZEN: "", SPOUSE_NATIONALITY: "",
		SPOUSE_ID_CARD: "", SPOUSE_ID_CARD_VALID: "", SPOUSE_ID_CARD_EXPIRE_OPTION: "1",
		SPOUSE_PASSPORT: "", SPOUSE_MARRIAGE_AGREE: "", SPOUSE_DEPENDENT: "", RELATIONSHIP_MLCI: "",
		ADDRESS1: "", AREA_CD: "", PROVINCE: "", CITY: "", KECAMATAN: "", KELURAHAN: "",
		RT: "", RW: "", ZIPCODE: "", YEAR_LIVE: "", ADDRESS_NPWP: "", AREA_CD_NPWP: "",
		PROVINCE_NPWP: "", CITY_NPWP: "", KECAMATAN_NPWP: "", KELURAHAN_NPWP: "", ZIPCODE_NPWP: "",
		SPOUSE_ADDRESS: "", SPOUSE_AREA_CD: "", SPOUSE_PROVINCE: "", SPOUSE_CITY: "",
		SPOUSE_KECAMATAN: "", SPOUSE_KELURAHAN: "", SPOUSE_RT: "", SPOUSE_RW: "", SPOUSE_ZIPCODE: "",
		SPOUSE_ADDRESS_SAME: false, PHONE_CODE: "62", PHONE_AREA: "", PHONE_NUMBER: "",
		FAX_CODE: "62", FAX_AREA: "", FAX_NUMBER: "", MOBILE1_CODE: "62", MOBILE1_NUMBER: "",
		MOBILE2_CODE: "62", MOBILE2_NUMBER: "", MOBILE3_CODE: "62", MOBILE3_NUMBER: "",
		OTHER_PHONE1_CODE: "", OTHER_PHONE1_AREA: "", OTHER_PHONE1_NUMBER: "", OTHER_PHONE1_NOTES: "",
		OTHER_PHONE2_CODE: "", OTHER_PHONE2_AREA: "", OTHER_PHONE2_NUMBER: "", OTHER_PHONE2_NOTES: "",
		SEND_SMS: false, EMAIL1: "", EMAIL2: "", OCCUPATION_TYPE: "", LAST_EDUCATION: "",
		CAREER_FIELD: "", INDUS_CODE: "", INDUS_CODE_1: "", INDUS_CODE_2: "", INDUS_CODE_3: "",
		INDUS_CODE_4: "", INDUS_CODE_5: "", MLCL_CODE: "", NPWP: "", NPWP_AREA_CD: "",
		CUST_TYPE: "", GRP_CODE: "", EMERGENCY_NAME: "", EMERGENCY_ADDRESS: "", EMERGENCY_PHONE: "", EMERGENCY_RELATION: "",
	});

	const [loading, setLoading] = useState(false);
	const [saving, setSaving] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [success, setSuccess] = useState<string | null>(null);
	const [areas, setAreas] = useState<Area[]>([]);
	const [kecamatans, setKecamatans] = useState<Kecamatan[]>([]);
	const [kelurahans, setKelurahans] = useState<Kelurahan[]>([]);
	const [religions, setReligions] = useState<ComboOption[]>([]);
	const [maritals, setMaritals] = useState<ComboOption[]>([]);
	const [genders] = useState<ComboOption[]>([{ VALUE: "M", DESC_VALUE: "Male" }, { VALUE: "F", DESC_VALUE: "Female" }]);
	const [citizenships] = useState<ComboOption[]>([{ VALUE: "WNI", DESC_VALUE: "WNI" }, { VALUE: "WNA", DESC_VALUE: "WNA" }]);
	const [countries, setCountries] = useState<ComboOption[]>([]);
	const [lesseeCategories, setLesseeCategories] = useState<ComboOption[]>([]);
	const [educations, setEducations] = useState<ComboOption[]>([]);
	const [careers, setCareers] = useState<ComboOption[]>([]);
	const [customerTypes, setCustomerTypes] = useState<ComboOption[]>([]);
	const [groups, setGroups] = useState<ComboOption[]>([]);
	const [yesNoOptions, setYesNoOptions] = useState<ComboOption[]>([]);
	const [relationships, setRelationships] = useState<ComboOption[]>([]);
	const [dependents, setDependents] = useState<ComboOption[]>([]);
	const [industryCodes, setIndustryCodes] = useState<Record<number, IndustryCode[]>>({});
	const [occupationOptions, setOccupationOptions] = useState<ComboOption[]>([]);

	const isViewMode = mode === "View";
	const isEditMode = mode === "Edit";
	const isAddMode = mode === "Add";
	const isMarried = formData.MARITAL === "M" || formData.MARITAL === "O";
	const isForeigner = formData.CITIZEN === "WNA";
	const isSpouseForeigner = formData.SPOUSE_CITIZEN === "WNA";
	const showSpouseFields = isMarried;
	const showPassportField = isForeigner;
	const showSpousePassportField = showSpouseFields && isSpouseForeigner;
	const showIdCardValidDate = formData.ID_CARD_EXPIRE_OPTION === "0";
	const showSpouseIdCardValidDate = showSpouseFields && formData.SPOUSE_ID_CARD_EXPIRE_OPTION === "0";

	//   const fetchComboData = useCallback(async () => {
	//     try {
	//       const [relRes, marRes, couRes, areRes, catRes, eduRes, carRes, typRes, grpRes, yesRes, depRes] = await Promise.all([
	//         axios.get(`${API_URL}/MasterData/api/combo/RELIGION`),
	//         axios.get(`${API_URL}/MasterData/api/combo/MARITAL`),
	//         axios.get(`${API_URL}/MasterData/api/countries`),
	//         axios.get(`${API_URL}/MasterData/api/areas`),
	//         axios.get(`${API_URL}/MasterData/api/combo/LESSEE_CATEGORY`),
	//         axios.get(`${API_URL}/MasterData/api/combo/LAST_EDU`),
	//         axios.get(`${API_URL}/MasterData/api/combo/CAREER_FIELD`),
	//         axios.get(`${API_URL}/MasterData/api/combo/BI_CUSTOMER_TYPE`),
	//         axios.get(`${API_URL}/MasterData/api/groups`),
	//         axios.get(`${API_URL}/MasterData/api/combo/YES_NO`),
	//         axios.get(`${API_URL}/MasterData/api/combo/RELATIONSHIP_MLCI`),
	//         axios.get(`${API_URL}/MasterData/api/combo/DEPENDENT`),
	//       ]);
	//       setReligions(relRes.data); setMaritals(marRes.data); setCountries(couRes.data);
	//       setAreas(areRes.data); setLesseeCategories(catRes.data); setEducations(eduRes.data);
	//       setCareers(carRes.data); setCustomerTypes(typRes.data); setGroups(grpRes.data);
	//       setYesNoOptions(yesRes.data); setRelationships(relRes.data); setDependents(depRes.data);
	//     } catch (err) { console.error("Failed to fetch combo data:", err); }
	//   }, []);

	const fetchCustomerData = useCallback(async () => {
		if (!apless) return;
		setLoading(true); setError(null);
		try {
			//   const { data } = await axios.get<CustomerFormData>(`${API_URL}/Customer/api/detail`, { params: { apless }, timeout: 10000 });
			//   const parsePhone = (p: string) => { if (!p) return { code: "62", area: "", number: "" }; const pts = p.split("-"); return pts.length >= 3 ? { code: pts[0]||"62", area: pts[1], number: pts[2] } : pts.length === 2 ? { code: pts[0]||"62", area: "", number: pts[1] } : { code: "62", area: "", number: p }; };
			//   const fmtDate = (d: string) => d ? d.split("-").reverse().join("-") : "";


			const response = await axios.get(`${API_URL}/Customer/api/detail`, {
				params: { apless: apless },
				timeout: 10000,
			});


			console.log('response', response)


			// setFormData(prev => ({
			//   ...prev, ...data,
			//   PHONE_CODE: parsePhone(data.PHONE2 || "").code, PHONE_AREA: parsePhone(data.PHONE2 || "").area, PHONE_NUMBER: parsePhone(data.PHONE2 || "").number,
			//   FAX_CODE: parsePhone(data.FAX1 || "").code, FAX_AREA: parsePhone(data.FAX1 || "").area, FAX_NUMBER: parsePhone(data.FAX1 || "").number,
			//   MOBILE1_CODE: parsePhone(data.Mobile_phone1 || "").code, MOBILE1_NUMBER: parsePhone(data.Mobile_phone1 || "").number,
			//   MOBILE2_CODE: parsePhone(data.Mobile_phone2 || "").code, MOBILE2_NUMBER: parsePhone(data.Mobile_phone2 || "").number,
			//   MOBILE3_CODE: parsePhone(data.Mobile_phone3 || "").code, MOBILE3_NUMBER: parsePhone(data.Mobile_phone3 || "").number,
			//   OTHER_PHONE1_CODE: parsePhone(data.OTHER_PHONE1 || "").code, OTHER_PHONE1_AREA: parsePhone(data.OTHER_PHONE1 || "").area, OTHER_PHONE1_NUMBER: parsePhone(data.OTHER_PHONE1 || "").number,
			//   OTHER_PHONE2_CODE: parsePhone(data.OTHER_PHONE2 || "").code, OTHER_PHONE2_AREA: parsePhone(data.OTHER_PHONE2 || "").area, OTHER_PHONE2_NUMBER: parsePhone(data.OTHER_PHONE2 || "").number,
			//   TGLBIRTH: fmtDate(data.TGLBIRTH), ID_CARD_VALID: fmtDate(data.ID_CARD_VALID),
			//   SPOUSE_TGLBIRTH: fmtDate(data.SPOUSE_TGLBIRTH), SPOUSE_ID_CARD_VALID: fmtDate(data.SPOUSE_ID_CARD_VALID),
			//   ID_CARD_EXPIRE_OPTION: data.ID_CARD_VALID ? "0" : "1",
			//   SPOUSE_ID_CARD_EXPIRE_OPTION: data.SPOUSE_ID_CARD_VALID ? "0" : "1",
			//   SPOUSE_ADDRESS_SAME: data.SPOUSE_ADDRESS === data.ADDRESS1,
			// }));
			// if (data.AREA_CD) setKecamatans((await axios.get(`${API_URL}/MasterData/api/kecamatans`, { params: { area_cd: data.AREA_CD } })).data);
			// if (data.KECAMATAN) setKelurahans((await axios.get(`${API_URL}/MasterData/api/kelurahans`, { params: { kecamatan_cd: data.KECAMATAN } })).data);
			// if (data.LESSEE_CAT) setOccupationOptions((await axios.get(data.LESSEE_CAT === "EM" ? `${API_URL}/MasterData/api/combo/PEP` : `${API_URL}/MasterData/api/combo/USAHA_HIGH_RISK`)).data);
		} catch (err) { setError("Failed to load customer record."); } finally { setLoading(false); }
	}, [apless]);

	//   useEffect(() => { fetchComboData(); }, [fetchComboData]);
	//   useEffect(() => { if (mode === "Edit" || mode === "View") fetchCustomerData(); }, [mode, fetchCustomerData]);


	useEffect(() => {
		fetchCustomerData();
	}, [fetchCustomerData]);

	const handleChange = useCallback((field: keyof CustomerFormData, value: string | boolean) => {
		setFormData(prev => ({ ...prev, [field]: value }));
		if (error) setError(null); if (success) setSuccess(null);
	}, [error, success]);

	const handleCitizenChange = useCallback((citizen: "WNI" | "WNA" | "", isSpouse: boolean) => {
		const p = isSpouse ? "SPOUSE_" : "";
		setFormData(prev => ({ ...prev, [`${p}CITIZEN`]: citizen, [`${p}NATIONALITY`]: citizen === "WNI" ? "ID" : prev[`${p}NATIONALITY` as keyof CustomerFormData], [`${p}PASSPORT`]: citizen === "WNI" ? "" : prev[`${p}PASSPORT` as keyof CustomerFormData] }));
	}, []);

	const handleMaritalChange = useCallback((marital: string) => {
		const married = marital === "M" || marital === "O";
		setFormData(prev => ({ ...prev, MARITAL: marital, ...(!married && { SPOUSE_NAME: "", SPOUSE_NAME_WT: "", SPOUSE_PLACEBIRTH: "", SPOUSE_TGLBIRTH: "", SPOUSE_CITIZEN: "", SPOUSE_NATIONALITY: "", SPOUSE_ID_CARD: "", SPOUSE_ID_CARD_VALID: "", SPOUSE_PASSPORT: "", SPOUSE_MARRIAGE_AGREE: "", SPOUSE_DEPENDENT: "", SPOUSE_ADDRESS: "", SPOUSE_ADDRESS_SAME: false }) }));
	}, []);

	const handleAddressSameChange = useCallback((same: boolean) => {
		if (same) setFormData(prev => ({ ...prev, SPOUSE_ADDRESS_SAME: true, SPOUSE_ADDRESS: prev.ADDRESS1, SPOUSE_AREA_CD: prev.AREA_CD, SPOUSE_PROVINCE: prev.PROVINCE, SPOUSE_CITY: prev.CITY, SPOUSE_KECAMATAN: prev.KECAMATAN, SPOUSE_KELURAHAN: prev.KELURAHAN, SPOUSE_RT: prev.RT, SPOUSE_RW: prev.RW, SPOUSE_ZIPCODE: prev.ZIPCODE }));
		else setFormData(prev => ({ ...prev, SPOUSE_ADDRESS_SAME: false, SPOUSE_ADDRESS: "", SPOUSE_AREA_CD: "", SPOUSE_PROVINCE: "", SPOUSE_CITY: "", SPOUSE_KECAMATAN: "", SPOUSE_KELURAHAN: "", SPOUSE_RT: "", SPOUSE_RW: "", SPOUSE_ZIPCODE: "" }));
	}, []);

	const handleAreaChange = useCallback(async (areaCd: string, isSpouse = false) => {
		const p = isSpouse ? "SPOUSE_" : "";
		setFormData(prev => ({ ...prev, [`${p}AREA_CD`]: areaCd }));
		const area = areas.find(a => a.AREA_CD === areaCd);
		if (area) setFormData(prev => ({ ...prev, [`${p}PROVINCE`]: area.Propinsi, [`${p}CITY`]: area.Kabupaten }));
		if (!isSpouse) setKecamatans((await axios.get(`${API_URL}/MasterData/api/kecamatans`, { params: { area_cd: areaCd } })).data);
	}, [areas]);

	const handleKecamatanChange = useCallback(async (kecCd: string, isSpouse = false) => {
		const p = isSpouse ? "SPOUSE_" : "";
		setFormData(prev => ({ ...prev, [`${p}KECAMATAN`]: kecCd }));
		if (!isSpouse) setKelurahans((await axios.get(`${API_URL}/MasterData/api/kelurahans`, { params: { kecamatan_cd: kecCd } })).data);
	}, []);

	const handleLesseeCategoryChange = useCallback(async (cat: string) => {
		setFormData(prev => ({ ...prev, LESSEE_CAT: cat }));
		setOccupationOptions((await axios.get(cat === "EM" ? `${API_URL}/MasterData/api/combo/PEP` : `${API_URL}/MasterData/api/combo/USAHA_HIGH_RISK`)).data);
	}, []);

	const handleIndustryCodeChange = useCallback((level: number, value: string) => {
		setFormData(prev => ({ ...prev, [`INDUS_CODE_${level}`]: value }));
	}, []);

	const validateForm = useCallback((): boolean => {
		const errs: string[] = [];
		if (!formData.ID_CARD_NAME?.trim()) errs.push("ID Card Name is required");
		if (!formData.LESSEE_CAT) errs.push("Customer Profile is required");
		if (!formData.ADDRESS1?.trim()) errs.push("Address is required");
		if (!formData.ZIPCODE || formData.ZIPCODE.length !== 5) errs.push("Post Code must be 5 digits");
		if (!formData.PHONE_NUMBER) errs.push("Phone is required");
		if (!formData.MOBILE1_NUMBER) errs.push("Mobile 1 is required");
		if (!formData.PLACEBIRTH?.trim()) errs.push("Place of Birth is required");
		if (!formData.TGLBIRTH) errs.push("Date of Birth is required");
		if (!formData.GENDER) errs.push("Gender is required");
		if (!formData.MARITAL) errs.push("Marital Status is required");
		if (!formData.RELIGION) errs.push("Religion is required");
		if (!formData.CITIZEN) errs.push("Citizenship is required");
		if (!formData.ID_CARD?.trim()) errs.push("ID Card No. is required");
		if (!formData.FAM_CARD?.trim()) errs.push("Family Card No. is required");
		if (!formData.LAST_EDUCATION) errs.push("Education is required");
		if (!formData.CAREER_FIELD) errs.push("Career Field is required");
		if (!formData.INDUS_CODE_5) errs.push("Industrial Code is required");
		if (!formData.NPWP || formData.NPWP.replace(/\D/g, "").length !== 15) errs.push("NPWP must be 15 digits");
		if (isMarried && !formData.SPOUSE_NAME?.trim()) errs.push("Spouse Name is required");
		if (!formData.EMERGENCY_NAME?.trim()) errs.push("Emergency Name is required");
		if (!formData.EMERGENCY_ADDRESS?.trim()) errs.push("Emergency Address is required");
		if (!formData.EMERGENCY_PHONE?.trim()) errs.push("Emergency Phone is required");
		if (!formData.EMERGENCY_RELATION?.trim()) errs.push("Emergency Relation is required");
		if (errs.length) { setError(errs.join("\n")); return false; }
		return true;
	}, [formData, isMarried]);

	const handleSubmit = useCallback((e: React.FormEvent) => {
		e.preventDefault();
		if (!validateForm()) return;
		setSaving(true); setError(null); setSuccess(null);
		setTimeout(() => {
			setSuccess("Record saved successfully!");
			setSaving(false);
			navigate("/customers");
		}, 1000);
	}, [validateForm, navigate]);

	const handleNpwpInput = useCallback((part: number, value: string, max: number) => {
		const clean = value.replace(/\D/g, "").slice(0, max);
		const npwp = formData.NPWP.replace(/\D/g, "").padEnd(15, "0");
		const idx = part === 1 ? 0 : part === 2 ? 2 : part === 3 ? 5 : part === 4 ? 8 : part === 5 ? 9 : 12;
		const end = part === 1 ? 2 : part === 2 ? 5 : part === 3 ? 8 : part === 4 ? 9 : part === 5 ? 12 : 16;
		const next = npwp.slice(0, idx) + clean + npwp.slice(end);
		handleChange("NPWP", next.replace(/(.{2})(.{3})(.{3})(.{1})(.{3})(.{4})/, "$1.$2.$3.$4-$5.$6"));
	}, [formData.NPWP, handleChange]);

	if (loading && (mode === "Edit" || mode === "View")) return <div className="p-6 animate-pulse space-y-4">{[...Array(8)].map((_, i) => <div key={i} className="h-10 bg-gray-200 rounded"></div>)}</div>;

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-7xl mx-auto bg-white rounded-2xl shadow-lg p-6 mb-6">
				<div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
					<div><h1 className="text-2xl font-bold text-gray-800">{mode === "Add" ? "Add" : mode === "Edit" ? "Edit" : "View"} Customer</h1><p className="text-gray-600">Manage customer details</p></div>
					{formData.APLESS && <span className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm">#{formData.APLESS}</span>}
				</div>
				{error && <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 whitespace-pre-wrap">{error}</div>}
				{success && <div className="mb-4 p-4 bg-green-50 border border-green-200 rounded-lg text-green-700">{success}</div>}

				<form onSubmit={handleSubmit} className="space-y-8">
					{/* Basic Info */}
					<section className="bg-gray-50 rounded-xl p-4 border border-gray-200">
						<h3 className="font-semibold text-gray-800 mb-4">Basic Information</h3>
						<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
							{/* FIXED: Added readOnly={true} to prevent React warning */}
							<div className="md:col-span-2">
								<label className="block text-sm font-medium mb-1">Name in ID Card *</label>
								<input type="text" value={formData.LESSEE_NM} readOnly className="w-full px-3 py-2 bg-gray-100 border border-gray-300 rounded-lg text-gray-700" />
							</div>
							<div>
								<label className="block text-sm font-medium mb-1">Customer No.</label>
								<input type="text" value={formData.APLESS} readOnly onChange={() => { }} className="w-full px-3 py-2 bg-gray-100 border border-gray-300 rounded-lg text-gray-700" />
							</div>
							<div className="md:col-span-2">
								<label className="block text-sm font-medium mb-1">Customer Name Without Title *</label>
								<input type="text" value={formData.ID_CARD_NAME} onChange={e => handleChange("ID_CARD_NAME", e.target.value)} disabled={isViewMode} required className="w-full px-3 py-2 border rounded-lg" />
							</div>
							<div className="grid grid-cols-2 gap-2 md:col-span-2">
								<div><label className="block text-sm font-medium mb-1">Place of Birth *</label><input type="text" value={formData.PLACEBIRTH} onChange={e => handleChange("PLACEBIRTH", e.target.value)} disabled={isViewMode} required className="w-full px-3 py-2 border rounded-lg" /></div>
								<div><label className="block text-sm font-medium mb-1">Date of Birth *</label><input type="text" value={formData.TGLBIRTH} onChange={e => handleChange("TGLBIRTH", e.target.value)} disabled={isViewMode} required placeholder="DD-MM-YYYY" className="w-full px-3 py-2 border rounded-lg" /></div>
							</div>
							<div><label className="block text-sm font-medium mb-1">Alias Name</label><input type="text" value={formData.ALIAS_NAME} onChange={e => handleChange("ALIAS_NAME", e.target.value)} disabled={isViewMode} className="w-full px-3 py-2 border rounded-lg" /></div>
							<div><label className="block text-sm font-medium mb-1">Gender *</label><select value={formData.GENDER} onChange={e => handleChange("GENDER", e.target.value)} disabled={isViewMode} required className="w-full px-3 py-2 border rounded-lg"><option value="">Select</option>{genders.map(g => <option key={g.VALUE} value={g.VALUE}>{g.DESC_VALUE}</option>)}</select></div>
							<div><label className="block text-sm font-medium mb-1">Religion *</label><select value={formData.RELIGION} onChange={e => handleChange("RELIGION", e.target.value)} disabled={isViewMode} required className="w-full px-3 py-2 border rounded-lg"><option value="">Select</option>{religions.map(r => <option key={r.VALUE} value={r.VALUE}>{r.DESC_VALUE}</option>)}</select></div>
							<div><label className="block text-sm font-medium mb-1">Citizenship *</label><select value={formData.CITIZEN} onChange={e => { handleChange("CITIZEN", e.target.value); handleCitizenChange(e.target.value as any, false); }} disabled={isViewMode} required className="w-full px-3 py-2 border rounded-lg"><option value="">Select</option>{citizenships.map(c => <option key={c.VALUE} value={c.VALUE}>{c.DESC_VALUE}</option>)}</select></div>
							<div><label className="block text-sm font-medium mb-1">Nationality</label><select value={formData.NATIONALITY} onChange={e => handleChange("NATIONALITY", e.target.value)} disabled={isViewMode || formData.CITIZEN === "WNI"} className="w-full px-3 py-2 border rounded-lg"><option value="">Select</option>{countries.map(c => <option key={c.VALUE} value={c.VALUE} disabled={c.VALUE === "ID"}>{c.DESC_VALUE}</option>)}</select></div>
							{showPassportField && <div><label className="block text-sm font-medium mb-1">Passport No.</label><input type="text" value={formData.PASSPORT_NO} onChange={e => handleChange("PASSPORT_NO", e.target.value)} disabled={isViewMode} className="w-full px-3 py-2 border rounded-lg" /></div>}

							{/* FIXED: Added readOnly={true} */}
							<div><label className="block text-sm font-medium mb-1">ID Card No. *</label><input type="text" value={formData.ID_CARD} readOnly className="w-full px-3 py-2 bg-gray-100 border border-gray-300 rounded-lg text-gray-700" /></div>

							<div><label className="block text-sm font-medium mb-1">ID Card Validity *</label><div className="flex gap-4"><label className="flex items-center gap-2"><input type="radio" name="idCardExpire" value="1" checked={formData.ID_CARD_EXPIRE_OPTION === "1"} onChange={() => handleChange("ID_CARD_EXPIRE_OPTION", "1")} disabled={isViewMode} /><span>No Expire</span></label><label className="flex items-center gap-2"><input type="radio" name="idCardExpire" value="0" checked={formData.ID_CARD_EXPIRE_OPTION === "0"} onChange={() => handleChange("ID_CARD_EXPIRE_OPTION", "0")} disabled={isViewMode} /><span>Certain Period</span></label></div></div>
							{showIdCardValidDate && <div><label className="block text-sm font-medium mb-1">Valid Until</label><input type="text" value={formData.ID_CARD_VALID} onChange={e => handleChange("ID_CARD_VALID", e.target.value)} disabled={isViewMode} placeholder="DD-MM-YYYY" className="w-full px-3 py-2 border rounded-lg" /></div>}
							<div><label className="block text-sm font-medium mb-1">Family Card No. *</label><input type="text" value={formData.FAM_CARD} onChange={e => handleChange("FAM_CARD", e.target.value)} disabled={isViewMode} required className="w-full px-3 py-2 border rounded-lg" /></div>
							<div><label className="block text-sm font-medium mb-1">Mother's Maiden Name *</label><input type="text" value={formData.MOTHER_NAME} onChange={e => handleChange("MOTHER_NAME", e.target.value)} disabled={isViewMode} required className="w-full px-3 py-2 border rounded-lg" /></div>
							<div><label className="block text-sm font-medium mb-1">Marital Status *</label><select value={formData.MARITAL} onChange={e => { handleChange("MARITAL", e.target.value); handleMaritalChange(e.target.value); }} disabled={isViewMode} required className="w-full px-3 py-2 border rounded-lg"><option value="">Select</option>{maritals.map(m => <option key={m.VALUE} value={m.VALUE}>{m.DESC_VALUE}</option>)}</select></div>
						</div>
					</section>


					{/* Section: Address Information */}
					<section className="bg-gray-50 rounded-xl p-4 border border-gray-200">
						<h3 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
							<svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
								<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
							</svg>
							Address Information
						</h3>

						<div className="grid grid-cols-1 md:grid-cols-2 gap-6">
							{/* Customer Address */}
							<div className="space-y-4">
								<h4 className="font-medium text-gray-700">ID Card Address *</h4>

								<div>
									<label className="block text-sm font-medium text-gray-700 mb-1">Address</label>
									<textarea
										value={formData.ADDRESS1}
										onChange={(e) => handleChange("ADDRESS1", e.target.value)}
										disabled={isViewMode}
										required
										rows={3}
										className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all resize-none"
									/>
								</div>

								<div className="grid grid-cols-2 gap-4">
									<div>
										<label className="block text-sm font-medium text-gray-700 mb-1">Area *</label>
										<select
											value={formData.AREA_CD}
											onChange={(e) => handleAreaChange(e.target.value)}
											disabled={isViewMode}
											required
											className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
										>
											<option value="">Select</option>
											{areas.map(a => (
												<option key={a.AREA_CD} value={a.AREA_CD}>
													{a.Propinsi} - {a.Kabupaten}
												</option>
											))}
										</select>
									</div>
									<div>
										<label className="block text-sm font-medium text-gray-700 mb-1">Live Since (Year) *</label>
										<input
											type="text"
											value={formData.YEAR_LIVE}
											onChange={(e) => handleChange("YEAR_LIVE", e.target.value.replace(/\D/g, "").slice(0, 4))}
											disabled={isViewMode}
											required
											maxLength={4}
											placeholder="YYYY"
											className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
										/>
									</div>
								</div>

								<div className="grid grid-cols-2 gap-4">
									<div>
										<label className="block text-sm font-medium text-gray-700 mb-1">Province *</label>
										<input
											type="text"
											value={formData.PROVINCE}
											readOnly
											className="w-full px-3 py-2.5 bg-gray-100 border border-gray-300 rounded-lg text-gray-700"
										/>
									</div>
									<div>
										<label className="block text-sm font-medium text-gray-700 mb-1">City *</label>
										<input
											type="text"
											value={formData.CITY}
											readOnly
											className="w-full px-3 py-2.5 bg-gray-100 border border-gray-300 rounded-lg text-gray-700"
										/>
									</div>
								</div>

								<div className="grid grid-cols-2 gap-4">
									<div>
										<label className="block text-sm font-medium text-gray-700 mb-1">Kecamatan *</label>
										<select
											value={formData.KECAMATAN}
											onChange={(e) => handleKecamatanChange(e.target.value)}
											disabled={isViewMode}
											required
											className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
										>
											<option value="">Select</option>
											{kecamatans.map(k => (
												<option key={k.Kecamatan_CD} value={k.Kecamatan_CD}>{k.Desc_Name}</option>
											))}
										</select>
									</div>
									<div>
										<label className="block text-sm font-medium text-gray-700 mb-1">Kelurahan *</label>
										<select
											value={formData.KELURAHAN}
											onChange={(e) => handleChange("KELURAHAN", e.target.value)}
											disabled={isViewMode}
											required
											className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
										>
											<option value="">Select</option>
											{kelurahans.map(k => (
												<option key={k.Kelurahan_CD} value={k.Kelurahan_CD}>{k.Desc_Name}</option>
											))}
										</select>
									</div>
								</div>

								<div className="grid grid-cols-2 gap-4">
									<div>
										<label className="block text-sm font-medium text-gray-700 mb-1">RT *</label>
										<input
											type="text"
											value={formData.RT}
											onChange={(e) => handleChange("RT", e.target.value.replace(/\D/g, "").slice(0, 4))}
											disabled={isViewMode}
											required
											maxLength={4}
											className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
										/>
									</div>
									<div>
										<label className="block text-sm font-medium text-gray-700 mb-1">RW *</label>
										<input
											type="text"
											value={formData.RW}
											onChange={(e) => handleChange("RW", e.target.value.replace(/\D/g, "").slice(0, 4))}
											disabled={isViewMode}
											required
											maxLength={4}
											className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
										/>
									</div>
								</div>

								<div>
									<label className="block text-sm font-medium text-gray-700 mb-1">Post Code *</label>
									<input
										type="text"
										value={formData.ZIPCODE}
										onChange={(e) => handleChange("ZIPCODE", e.target.value.replace(/\D/g, "").slice(0, 5))}
										disabled={isViewMode}
										required
										maxLength={5}
										className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
									/>
								</div>
							</div>

							{/* NPWP Address */}
							<div className="space-y-4">
								<h4 className="font-medium text-gray-700">NPWP Address *</h4>

								<div>
									<label className="block text-sm font-medium text-gray-700 mb-1">Address</label>
									<textarea
										value={formData.ADDRESS_NPWP}
										onChange={(e) => handleChange("ADDRESS_NPWP", e.target.value)}
										disabled={isViewMode}
										required
										rows={3}
										className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all resize-none"
									/>
								</div>

								<div>
									<label className="block text-sm font-medium text-gray-700 mb-1">Area *</label>
									<select
										value={formData.AREA_CD_NPWP}
										onChange={(e) => handleAreaChange(e.target.value, false)}
										disabled={isViewMode}
										required
										className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
									>
										<option value="">Select</option>
										{areas.map(a => (
											<option key={a.AREA_CD} value={a.AREA_CD}>
												{a.Propinsi} - {a.Kabupaten}
											</option>
										))}
									</select>
								</div>

								<div className="grid grid-cols-2 gap-4">
									<div>
										<label className="block text-sm font-medium text-gray-700 mb-1">Province *</label>
										<input
											type="text"
											value={formData.PROVINCE_NPWP}
											readOnly
											className="w-full px-3 py-2.5 bg-gray-100 border border-gray-300 rounded-lg text-gray-700"
										/>
									</div>
									<div>
										<label className="block text-sm font-medium text-gray-700 mb-1">City *</label>
										<input
											type="text"
											value={formData.CITY_NPWP}
											readOnly
											className="w-full px-3 py-2.5 bg-gray-100 border border-gray-300 rounded-lg text-gray-700"
										/>
									</div>
								</div>

								<div className="grid grid-cols-2 gap-4">
									<div>
										<label className="block text-sm font-medium text-gray-700 mb-1">Kecamatan *</label>
										<select
											value={formData.KECAMATAN_NPWP}
											onChange={(e) => handleChange("KECAMATAN_NPWP", e.target.value)}
											disabled={isViewMode}
											required
											className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
										>
											<option value="">Select</option>
											{kecamatans.map(k => (
												<option key={k.Kecamatan_CD} value={k.Kecamatan_CD}>{k.Desc_Name}</option>
											))}
										</select>
									</div>
									<div>
										<label className="block text-sm font-medium text-gray-700 mb-1">Kelurahan *</label>
										<select
											value={formData.KELURAHAN_NPWP}
											onChange={(e) => handleChange("KELURAHAN_NPWP", e.target.value)}
											disabled={isViewMode}
											required
											className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
										>
											<option value="">Select</option>
											{kelurahans.map(k => (
												<option key={k.Kelurahan_CD} value={k.Kelurahan_CD}>{k.Desc_Name}</option>
											))}
										</select>
									</div>
								</div>

								<div>
									<label className="block text-sm font-medium text-gray-700 mb-1">Post Code *</label>
									<input
										type="text"
										value={formData.ZIPCODE_NPWP}
										onChange={(e) => handleChange("ZIPCODE_NPWP", e.target.value.replace(/\D/g, "").slice(0, 5))}
										disabled={isViewMode}
										required
										maxLength={5}
										className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
									/>
								</div>

								{/* NPWP Number */}
								<div>
									<label className="block text-sm font-medium text-gray-700 mb-1">NPWP *</label>
									<div className="flex flex-wrap gap-1 items-center">
										{[
											{ part: 1, len: 2 },
											{ part: 2, len: 3 },
											{ part: 3, len: 3 },
											{ part: 4, len: 1 },
											{ part: 5, len: 3 },
											{ part: 6, len: 4 },
										].map(({ part, len }, idx) => (
											<React.Fragment key={part}>
												<input
													type="text"
													value={formData.NPWP.replace(/\D/g, "").slice(
														part === 1 ? 0 : part === 2 ? 2 : part === 3 ? 5 : part === 4 ? 8 : part === 5 ? 9 : 12,
														part === 1 ? 2 : part === 2 ? 5 : part === 3 ? 8 : part === 4 ? 9 : part === 5 ? 12 : 16
													)}
													onChange={(e) => handleNpwpInput(part, e.target.value, len)}
													disabled={isViewMode}
													maxLength={len}
													className="w-8 md:w-12 px-2 py-1.5 border border-gray-300 rounded text-center focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
												/>
												{idx < 3 ? <span>.</span> : idx === 3 ? <span>-</span> : idx === 4 ? <span>.</span> : null}
											</React.Fragment>
										))}
									</div>
								</div>
							</div>
						</div>
					</section>

					{/* Section: Contact Information */}
					<section className="bg-gray-50 rounded-xl p-4 border border-gray-200">
						<h3 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
							<svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
							</svg>
							Contact Information
						</h3>

						<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
							{/* Phone */}
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Phone *</label>
								<div className="flex gap-2">
									<input
										type="text"
										value={formData.PHONE_CODE}
										onChange={(e) => handleChange("PHONE_CODE", e.target.value.replace(/\D/g, "").slice(0, 3))}
										disabled={isViewMode}
										maxLength={3}
										className="w-20 px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
									/>
									<input
										type="text"
										value={formData.PHONE_AREA}
										onChange={(e) => handleChange("PHONE_AREA", e.target.value.replace(/\D/g, "").slice(0, 4))}
										disabled={isViewMode}
										maxLength={4}
										className="w-24 px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
									/>
									<input
										type="text"
										value={formData.PHONE_NUMBER}
										onChange={(e) => handlePhoneInput(e, "PHONE_NUMBER")}
										disabled={isViewMode}
										required
										maxLength={11}
										className="flex-1 px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
									/>
								</div>
							</div>

							{/* Fax */}
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Fax</label>
								<div className="flex gap-2">
									<input
										type="text"
										value={formData.FAX_CODE}
										onChange={(e) => handleChange("FAX_CODE", e.target.value.replace(/\D/g, "").slice(0, 3))}
										disabled={isViewMode}
										maxLength={3}
										className="w-20 px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
									/>
									<input
										type="text"
										value={formData.FAX_AREA}
										onChange={(e) => handleChange("FAX_AREA", e.target.value.replace(/\D/g, "").slice(0, 4))}
										disabled={isViewMode}
										maxLength={4}
										className="w-24 px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
									/>
									<input
										type="text"
										value={formData.FAX_NUMBER}
										onChange={(e) => handlePhoneInput(e, "FAX_NUMBER")}
										disabled={isViewMode}
										maxLength={11}
										className="flex-1 px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
									/>
								</div>
							</div>

							{/* Mobile Phones */}
							{[
								{ label: "Mobile 1 *", code: "MOBILE1_CODE", number: "MOBILE1_NUMBER", required: true },
								{ label: "Mobile 2", code: "MOBILE2_CODE", number: "MOBILE2_NUMBER", required: false },
								{ label: "Mobile 3", code: "MOBILE3_CODE", number: "MOBILE3_NUMBER", required: false },
							].map(({ label, code, number, required }) => (
								<div key={code}>
									<label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
									<div className="flex gap-2">
										<input
											type="text"
											value={formData[code as keyof CustomerFormData] as string}
											readOnly
											className="w-20 px-3 py-2.5 bg-gray-100 border border-gray-300 rounded-lg text-gray-700"
										/>
										<input
											type="text"
											value={formData[number as keyof CustomerFormData] as string}
											onChange={(e) => handlePhoneInput(e, number)}
											disabled={isViewMode}
											required={required}
											maxLength={16}
											className="flex-1 px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
										/>
									</div>
								</div>
							))}

							{/* Send SMS */}
							<div className="flex items-center gap-2">
								<input
									type="checkbox"
									id="sendSms"
									checked={formData.SEND_SMS}
									onChange={(e) => handleChange("SEND_SMS", e.target.checked)}
									disabled={isViewMode}
									className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
								/>
								<label htmlFor="sendSms" className="text-sm text-gray-700">Send SMS</label>
							</div>

							{/* Emails */}
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Email 1</label>
								<input
									type="email"
									value={formData.EMAIL1}
									onChange={(e) => handleChange("EMAIL1", e.target.value)}
									disabled={isViewMode}
									className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
								/>
							</div>
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Email 2</label>
								<input
									type="email"
									value={formData.EMAIL2}
									onChange={(e) => handleChange("EMAIL2", e.target.value)}
									disabled={isViewMode}
									className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
								/>
							</div>
						</div>
					</section>

					{/* Section: Professional Information */}
					<section className="bg-gray-50 rounded-xl p-4 border border-gray-200">
						<h3 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
							<svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
							</svg>
							Professional Information
						</h3>

						<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
							{/* Customer Profile */}
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Customer Profile *</label>
								<select
									value={formData.LESSEE_CAT}
									onChange={(e) => handleLesseeCategoryChange(e.target.value)}
									disabled={isViewMode}
									required
									className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
								>
									<option value="">Select</option>
									{lesseeCategories.map(c => (
										<option key={c.VALUE} value={c.VALUE}>{c.DESC_VALUE}</option>
									))}
								</select>
							</div>

							{/* Occupation/Business Type */}
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Occupation/Business Type</label>
								<select
									value={formData.OCCUPATION_TYPE}
									onChange={(e) => handleChange("OCCUPATION_TYPE", e.target.value)}
									disabled={isViewMode || formData.LESSEE_CAT === "PF"}
									className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
								>
									<option value="">Select</option>
									{occupationOptions.map(o => (
										<option key={o.VALUE} value={o.VALUE}>{o.DESC_VALUE}</option>
									))}
								</select>
							</div>

							{/* Last Education */}
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Last Education *</label>
								<select
									value={formData.LAST_EDUCATION}
									onChange={(e) => handleChange("LAST_EDUCATION", e.target.value)}
									disabled={isViewMode}
									required
									className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
								>
									<option value="">Select</option>
									{educations.map(e => (
										<option key={e.VALUE} value={e.VALUE}>{e.DESC_VALUE}</option>
									))}
								</select>
							</div>

							{/* Career Field */}
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Career Field *</label>
								<select
									value={formData.CAREER_FIELD}
									onChange={(e) => handleChange("CAREER_FIELD", e.target.value)}
									disabled={isViewMode}
									required
									className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
								>
									<option value="">Select</option>
									{careers.map(c => (
										<option key={c.VALUE} value={c.VALUE}>{c.DESC_VALUE}</option>
									))}
								</select>
							</div>

							{/* BI Customer Type */}
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">BI Customer Type</label>
								<select
									value={formData.CUST_TYPE}
									onChange={(e) => handleChange("CUST_TYPE", e.target.value)}
									disabled={isViewMode}
									className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
								>
									<option value="">Select</option>
									{customerTypes.map(c => (
										<option key={c.VALUE} value={c.VALUE}>{c.DESC_VALUE}</option>
									))}
								</select>
							</div>

							{/* Group */}
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Group *</label>
								<select
									value={formData.GRP_CODE}
									onChange={(e) => handleChange("GRP_CODE", e.target.value)}
									disabled={isViewMode}
									required
									className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
								>
									<option value="">Select</option>
									{groups.map(g => (
										<option key={g.VALUE} value={g.VALUE}>{g.DESC_VALUE}</option>
									))}
								</select>
							</div>
						</div>

						{/* Industrial Code (Cascading) */}
						<div className="mt-4">
							<label className="block text-sm font-medium text-gray-700 mb-2">Industrial Code *</label>
							<div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
								{[1, 2, 3, 4, 5].map(level => (
									<select
										key={level}
										value={formData[`INDUS_CODE_${level}` as keyof CustomerFormData] as string}
										onChange={(e) => handleIndustryCodeChange(level, e.target.value)}
										disabled={isViewMode || !formData[`INDUS_CODE_${level - 1}` as keyof CustomerFormData]}
										required={level === 5}
										className="px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed text-sm"
									>
										<option value="">Select</option>
										{industryCodes[level]?.map(code => (
											<option key={code.MLCI_Code} value={code.MLCI_Code}>
												{code.Descrip}
											</option>
										))}
									</select>
								))}
							</div>
						</div>
					</section>

					{/* Section: Spouse Information (Conditional) */}
					{showSpouseFields && (
						<section className="bg-gray-50 rounded-xl p-4 border border-gray-200">
							<h3 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
								<svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
								</svg>
								Spouse Information
							</h3>

							<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
								{/* Address Same Checkbox */}
								<div className="md:col-span-2">
									<label className="flex items-center gap-3">
										<input
											type="radio"
											name="spouseAddress"
											checked={formData.SPOUSE_ADDRESS_SAME}
											onChange={() => handleAddressSameChange(true)}
											disabled={isViewMode}
											className="w-4 h-4 text-blue-600"
										/>
										<span className="text-sm">Same with Customer's Address in ID Card</span>
									</label>
									<label className="flex items-center gap-3 mt-2">
										<input
											type="radio"
											name="spouseAddress"
											checked={!formData.SPOUSE_ADDRESS_SAME}
											onChange={() => handleAddressSameChange(false)}
											disabled={isViewMode}
											className="w-4 h-4 text-blue-600"
										/>
										<span className="text-sm">Different with Customer's Address in ID Card</span>
									</label>
								</div>

								{/* Spouse Name */}
								<div className="md:col-span-2">
									<label className="block text-sm font-medium text-gray-700 mb-1">
										Spouse Name in ID Card *
									</label>
									<input
										type="text"
										value={formData.SPOUSE_NAME}
										onChange={(e) => handleChange("SPOUSE_NAME", e.target.value)}
										disabled={isViewMode}
										required={isMarried}
										className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
									/>
								</div>

								{/* Spouse Name Without Title */}
								<div className="md:col-span-2">
									<label className="block text-sm font-medium text-gray-700 mb-1">
										Spouse Name Without Title *
									</label>
									<input
										type="text"
										value={formData.SPOUSE_NAME_WT}
										onChange={(e) => handleChange("SPOUSE_NAME_WT", e.target.value)}
										disabled={isViewMode}
										required={isMarried}
										className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
									/>
								</div>

								{/* Spouse Place/Date of Birth */}
								<div className="grid grid-cols-2 gap-2 md:col-span-2">
									<div>
										<label className="block text-sm font-medium text-gray-700 mb-1">Place of Birth *</label>
										<input
											type="text"
											value={formData.SPOUSE_PLACEBIRTH}
											onChange={(e) => handleChange("SPOUSE_PLACEBIRTH", e.target.value)}
											disabled={isViewMode}
											required={isMarried}
											className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
										/>
									</div>
									<div>
										<label className="block text-sm font-medium text-gray-700 mb-1">Date of Birth *</label>
										<input
											type="text"
											value={formData.SPOUSE_TGLBIRTH}
											onChange={(e) => handleChange("SPOUSE_TGLBIRTH", e.target.value)}
											disabled={isViewMode}
											placeholder="DD-MM-YYYY"
											required={isMarried}
											className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
										/>
									</div>
								</div>

								{/* Spouse Citizenship */}
								<div>
									<label className="block text-sm font-medium text-gray-700 mb-1">Citizenship *</label>
									<select
										value={formData.SPOUSE_CITIZEN}
										onChange={(e) => {
											handleChange("SPOUSE_CITIZEN", e.target.value);
											handleCitizenChange(e.target.value as "WNI" | "WNA" | "", true);
										}}
										disabled={isViewMode}
										required={isMarried}
										className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
									>
										<option value="">Select</option>
										{citizenships.map(c => (
											<option key={c.VALUE} value={c.VALUE}>{c.DESC_VALUE}</option>
										))}
									</select>
								</div>

								{/* Spouse Nationality */}
								<div>
									<label className="block text-sm font-medium text-gray-700 mb-1">Nationality</label>
									<select
										value={formData.SPOUSE_NATIONALITY}
										onChange={(e) => handleChange("SPOUSE_NATIONALITY", e.target.value)}
										disabled={isViewMode || formData.SPOUSE_CITIZEN === "WNI"}
										className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
									>
										<option value="">Select</option>
										{countries.map(c => (
											<option key={c.VALUE} value={c.VALUE} disabled={c.VALUE === "ID"}>
												{c.DESC_VALUE}
											</option>
										))}
									</select>
								</div>

								{/* Spouse ID Card */}
								<div>
									<label className="block text-sm font-medium text-gray-700 mb-1">ID Card No. *</label>
									<input
										type="text"
										value={formData.SPOUSE_ID_CARD}
										onChange={(e) => handleChange("SPOUSE_ID_CARD", e.target.value)}
										disabled={isViewMode}
										required={isMarried}
										className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
									/>
								</div>

								{/* Spouse ID Card Validity */}
								<div>
									<label className="block text-sm font-medium text-gray-700 mb-1">ID Card Validity *</label>
									<div className="flex gap-4">
										<label className="flex items-center gap-2">
											<input
												type="radio"
												name="spouseIdCardExpire"
												value="1"
												checked={formData.SPOUSE_ID_CARD_EXPIRE_OPTION === "1"}
												onChange={() => handleChange("SPOUSE_ID_CARD_EXPIRE_OPTION", "1")}
												disabled={isViewMode}
												className="w-4 h-4 text-blue-600"
											/>
											<span className="text-sm">No Expire</span>
										</label>
										<label className="flex items-center gap-2">
											<input
												type="radio"
												name="spouseIdCardExpire"
												value="0"
												checked={formData.SPOUSE_ID_CARD_EXPIRE_OPTION === "0"}
												onChange={() => handleChange("SPOUSE_ID_CARD_EXPIRE_OPTION", "0")}
												disabled={isViewMode}
												className="w-4 h-4 text-blue-600"
											/>
											<span className="text-sm">Certain Period</span>
										</label>
									</div>
								</div>

								{/* Spouse ID Card Valid Date */}
								{showSpouseIdCardValidDate && (
									<div>
										<label className="block text-sm font-medium text-gray-700 mb-1">Valid Until</label>
										<input
											type="text"
											value={formData.SPOUSE_ID_CARD_VALID}
											onChange={(e) => handleChange("SPOUSE_ID_CARD_VALID", e.target.value)}
											disabled={isViewMode}
											placeholder="DD-MM-YYYY"
											className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
										/>
									</div>
								)}

								{/* Spouse Passport */}
								{showSpousePassportField && (
									<div>
										<label className="block text-sm font-medium text-gray-700 mb-1">Passport No. *</label>
										<input
											type="text"
											value={formData.SPOUSE_PASSPORT}
											onChange={(e) => handleChange("SPOUSE_PASSPORT", e.target.value)}
											disabled={isViewMode}
											required={isSpouseForeigner}
											className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
										/>
									</div>
								)}

								{/* Spouse Marriage Agreement */}
								<div>
									<label className="block text-sm font-medium text-gray-700 mb-1">Marriage Agreement *</label>
									<select
										value={formData.SPOUSE_MARRIAGE_AGREE}
										onChange={(e) => handleChange("SPOUSE_MARRIAGE_AGREE", e.target.value)}
										disabled={isViewMode}
										required={isMarried}
										className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
									>
										<option value="">Select</option>
										{yesNoOptions.map(o => (
											<option key={o.VALUE} value={o.VALUE}>{o.DESC_VALUE}</option>
										))}
									</select>
								</div>

								{/* Spouse Dependents */}
								<div>
									<label className="block text-sm font-medium text-gray-700 mb-1">Total Dependents</label>
									<select
										value={formData.SPOUSE_DEPENDENT}
										onChange={(e) => handleChange("SPOUSE_DEPENDENT", e.target.value)}
										disabled={isViewMode}
										className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
									>
										<option value="">Select</option>
										{dependents.map(d => (
											<option key={d.VALUE} value={d.VALUE}>{d.DESC_VALUE}</option>
										))}
									</select>
								</div>

								{/* Spouse Relationship */}
								<div>
									<label className="block text-sm font-medium text-gray-700 mb-1">Relationship with Company *</label>
									<select
										value={formData.RELATIONSHIP_MLCI}
										onChange={(e) => handleChange("RELATIONSHIP_MLCI", e.target.value)}
										disabled={isViewMode}
										required
										className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
									>
										<option value="">Select</option>
										{relationships.map(r => (
											<option key={r.VALUE} value={r.VALUE}>{r.DESC_VALUE}</option>
										))}
									</select>
								</div>

								{/* Spouse Address (if different) */}
								{!formData.SPOUSE_ADDRESS_SAME && (
									<div className="md:col-span-2 space-y-4">
										<h4 className="font-medium text-gray-700">Spouse Address *</h4>

										<div>
											<label className="block text-sm font-medium text-gray-700 mb-1">Address</label>
											<textarea
												value={formData.SPOUSE_ADDRESS}
												onChange={(e) => handleChange("SPOUSE_ADDRESS", e.target.value)}
												disabled={isViewMode}
												required={isMarried && !formData.SPOUSE_ADDRESS_SAME}
												rows={2}
												className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all resize-none"
											/>
										</div>

										<div className="grid grid-cols-2 gap-4">
											<div>
												<label className="block text-sm font-medium text-gray-700 mb-1">Area *</label>
												<select
													value={formData.SPOUSE_AREA_CD}
													onChange={(e) => handleAreaChange(e.target.value, true)}
													disabled={isViewMode}
													required={isMarried && !formData.SPOUSE_ADDRESS_SAME}
													className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
												>
													<option value="">Select</option>
													{areas.map(a => (
														<option key={a.AREA_CD} value={a.AREA_CD}>
															{a.Propinsi} - {a.Kabupaten}
														</option>
													))}
												</select>
											</div>
											<div>
												<label className="block text-sm font-medium text-gray-700 mb-1">Province *</label>
												<input
													type="text"
													value={formData.SPOUSE_PROVINCE}
													readOnly
													className="w-full px-3 py-2.5 bg-gray-100 border border-gray-300 rounded-lg text-gray-700"
												/>
											</div>
										</div>

										<div className="grid grid-cols-2 gap-4">
											<div>
												<label className="block text-sm font-medium text-gray-700 mb-1">City *</label>
												<input
													type="text"
													value={formData.SPOUSE_CITY}
													readOnly
													className="w-full px-3 py-2.5 bg-gray-100 border border-gray-300 rounded-lg text-gray-700"
												/>
											</div>
											<div>
												<label className="block text-sm font-medium text-gray-700 mb-1">Kecamatan *</label>
												<select
													value={formData.SPOUSE_KECAMATAN}
													onChange={(e) => handleKecamatanChange(e.target.value, true)}
													disabled={isViewMode}
													required={isMarried && !formData.SPOUSE_ADDRESS_SAME}
													className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
												>
													<option value="">Select</option>
													{kecamatans.map(k => (
														<option key={k.Kecamatan_CD} value={k.Kecamatan_CD}>{k.Desc_Name}</option>
													))}
												</select>
											</div>
										</div>

										<div className="grid grid-cols-2 gap-4">
											<div>
												<label className="block text-sm font-medium text-gray-700 mb-1">Kelurahan *</label>
												<select
													value={formData.SPOUSE_KELURAHAN}
													onChange={(e) => handleChange("SPOUSE_KELURAHAN", e.target.value)}
													disabled={isViewMode}
													required={isMarried && !formData.SPOUSE_ADDRESS_SAME}
													className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
												>
													<option value="">Select</option>
													{kelurahans.map(k => (
														<option key={k.Kelurahan_CD} value={k.Kelurahan_CD}>{k.Desc_Name}</option>
													))}
												</select>
											</div>
											<div className="grid grid-cols-2 gap-2">
												<input
													type="text"
													value={formData.SPOUSE_RT}
													onChange={(e) => handleChange("SPOUSE_RT", e.target.value.replace(/\D/g, "").slice(0, 4))}
													disabled={isViewMode}
													placeholder="RT"
													required={isMarried && !formData.SPOUSE_ADDRESS_SAME}
													maxLength={4}
													className="px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
												/>
												<input
													type="text"
													value={formData.SPOUSE_RW}
													onChange={(e) => handleChange("SPOUSE_RW", e.target.value.replace(/\D/g, "").slice(0, 4))}
													disabled={isViewMode}
													placeholder="RW"
													required={isMarried && !formData.SPOUSE_ADDRESS_SAME}
													maxLength={4}
													className="px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
												/>
											</div>
										</div>

										<div>
											<label className="block text-sm font-medium text-gray-700 mb-1">Post Code *</label>
											<input
												type="text"
												value={formData.SPOUSE_ZIPCODE}
												onChange={(e) => handleChange("SPOUSE_ZIPCODE", e.target.value.replace(/\D/g, "").slice(0, 5))}
												disabled={isViewMode}
												required={isMarried && !formData.SPOUSE_ADDRESS_SAME}
												maxLength={5}
												className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
											/>
										</div>
									</div>
								)}
							</div>
						</section>
					)}

					{/* Section: Emergency Contact */}
					<section className="bg-gray-50 rounded-xl p-4 border border-gray-200">
						<h3 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
							<svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M18.364 5.636l-3.536 3.536m0 5.656l3.536 3.536M9.172 9.172L5.636 5.636m3.536 9.192l-3.536 3.536M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-5 0a4 4 0 11-8 0 4 4 0 018 0z" />
							</svg>
							Emergency Contact
						</h3>

						<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Emergency Name *</label>
								<input
									type="text"
									value={formData.EMERGENCY_NAME}
									onChange={(e) => handleChange("EMERGENCY_NAME", e.target.value)}
									disabled={isViewMode}
									required
									className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
								/>
							</div>
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">Emergency Phone *</label>
								<input
									type="text"
									value={formData.EMERGENCY_PHONE}
									onChange={(e) => handleChange("EMERGENCY_PHONE", e.target.value)}
									disabled={isViewMode}
									required
									className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
								/>
							</div>
							<div className="md:col-span-2">
								<label className="block text-sm font-medium text-gray-700 mb-1">Emergency Address *</label>
								<textarea
									value={formData.EMERGENCY_ADDRESS}
									onChange={(e) => handleChange("EMERGENCY_ADDRESS", e.target.value)}
									disabled={isViewMode}
									required
									rows={2}
									className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all resize-none"
								/>
							</div>
							<div className="md:col-span-2">
								<label className="block text-sm font-medium text-gray-700 mb-1">Emergency Relation *</label>
								<input
									type="text"
									value={formData.EMERGENCY_RELATION}
									onChange={(e) => handleChange("EMERGENCY_RELATION", e.target.value)}
									disabled={isViewMode}
									required
									className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
								/>
							</div>
						</div>
					</section>

					{/* Action Buttons */}
					<div className="flex gap-3 pt-4 border-t">
						{isAddMode && <button type="submit" disabled={saving} className="px-6 py-2.5 bg-blue-600 text-white rounded-lg disabled:opacity-75">{saving ? "Saving..." : "Save"}</button>}
						{isEditMode && <button type="submit" disabled={saving} className="px-6 py-2.5 bg-green-600 text-white rounded-lg disabled:opacity-75">{saving ? "Updating..." : "Update"}</button>}
						<button type="button" onClick={() => navigate("/customers")} className="px-6 py-2.5 bg-gray-200 rounded-lg">Cancel</button>
					</div>
				</form>
			</div>
		</div>
	);
};

export default CustomerDetailInformation;