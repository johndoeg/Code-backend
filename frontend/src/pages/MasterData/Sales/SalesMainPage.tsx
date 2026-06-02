import React, { useEffect, useState, useCallback } from "react";
import api from "../../../api/axiosInstance";
import { useNavigate, useLocation } from "react-router-dom";

interface SalesFormData {
	SALES_NO: string;
	NAME: string;
	ADDRESS: string;
	CITY: string;
	ZIPCODE: string;
	PHONE: string;
	FAX: string;
	EMAIL: string;
	IDCARD: string;
	GENDER: string;
	NICKNAME: string;
	OCCUPATION: string;
	ID_VALID_DT: string;
	EXPIRE_OPTION: "0" | "1"; // 0 = No Expire, 1 = Certain Period
	PAID: "0" | "1";
	STATUS: "A" | "I";
	SALES_TYPE: "PT" | "PR" | "";
	BROKER_TYPE: "PT" | "PR" | "";
	BRANCH_CD: string;
	CMO_NAME: string;
	CREATED_BY: string;
	CREATED_DATE: string;
	UPDATE_BY: string;
	LAST_UPDATE: string;
}

interface ComboOption {
	VALUE: string;
	DESC_VALUE: string;
}

interface Branch {
	BRANCH_CD: string;
	BRANCH_NAME: string;
}

interface CMO {
	EMPLOYEE_ID: string;
	FULLNAME: string;
}

interface ApiResponse<T> {
	success: boolean;
	message: string;
	data?: T;
}

const SalesMainPage: React.FC = () => {
	const navigate = useNavigate();
	const location = useLocation();

	const params = new URLSearchParams(location.search);
	const mode = params.get("id") as "Add" | "Edit" | "View" | null;
	const initialSalesNo = params.get("salesno") || "";
	const initialSalType = params.get("sal_type") as "PT" | "PR" | "";
	const initialBroker = params.get("broker") as "PT" | "PR" | "";

	const [formData, setFormData] = useState<SalesFormData>({
		SALES_NO: "",
		NAME: "",
		ADDRESS: "",
		CITY: "",
		ZIPCODE: "",
		PHONE: "",
		FAX: "",
		EMAIL: "",
		IDCARD: "",
		GENDER: "",
		NICKNAME: "",
		OCCUPATION: "",
		ID_VALID_DT: "",
		EXPIRE_OPTION: "0",
		PAID: "1",
		STATUS: "A",
		SALES_TYPE: "",
		BROKER_TYPE: "",
		BRANCH_CD: "",
		CMO_NAME: "",
		CREATED_BY: "",
		CREATED_DATE: "",
		UPDATE_BY: "",
		LAST_UPDATE: "",
	});

	const [loading, setLoading] = useState(false);
	const [saving, setSaving] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [success, setSuccess] = useState<string | null>(null);
	const [branches, setBranches] = useState<Branch[]>([]);
	const [cmos, setCMOs] = useState<CMO[]>([]);
	const [salesTypes, setSalesTypes] = useState<ComboOption[]>([]);
	const [brokerTypes, setBrokerTypes] = useState<ComboOption[]>([]);
	const [genders, setGenders] = useState<ComboOption[]>([]);
	const [occupations] = useState([
		{ VALUE: "1", DESC_VALUE: "Kacab" },
		{ VALUE: "2", DESC_VALUE: "OM" },
		{ VALUE: "3", DESC_VALUE: "PIC" },
		{ VALUE: "4", DESC_VALUE: "Salesman" },
		{ VALUE: "5", DESC_VALUE: "Supervisor" },
		{ VALUE: "6", DESC_VALUE: "Owner" },
		{ VALUE: "7", DESC_VALUE: "Director" },
	]);

	const isViewMode = mode === "View";
	const isEditMode = mode === "Edit";
	const isAddMode = mode === "Add";
	const isBroker = formData.SALES_TYPE === "PT" && formData.BROKER_TYPE;
	const isIndividual = formData.SALES_TYPE === "PR" || formData.BROKER_TYPE === "PR";
	const showBrokerFields = formData.SALES_TYPE === "PT";
	const showIndividualFields = isIndividual;
	const showExpireDate = formData.EXPIRE_OPTION === "1" && showIndividualFields;
	const showFax = formData.BROKER_TYPE === "PT";
	const showNickname = formData.BROKER_TYPE === "PT";
	const showLastUpdate = (formData.LAST_UPDATE || formData.UPDATE_BY) && !isAddMode;

	const fetchComboData = useCallback(async () => {
		try {
			const [salesTypesRes, brokerTypesRes, gendersRes, branchesRes] = await Promise.all([
				api.get<ComboOption[]>('/MasterData/api/combo/SALES_TYPE'),
				api.get<ComboOption[]>('/MasterData/api/combo/TIPE_CUST'),
				api.get<ComboOption[]>('/MasterData/api/combo/GENDER'),
				api.get<Branch[]>('/MasterData/api/branches'),
			]);
			setSalesTypes(salesTypesRes.data);
			setBrokerTypes(brokerTypesRes.data.filter(b => b.VALUE !== "00"));
			setGenders(gendersRes.data);
			setBranches(branchesRes.data.filter(b => !["00", "01"].includes(b.BRANCH_CD)));
		} catch (err) {
			console.error("Failed to fetch combo data:", err);
			setError("Failed to load form data. Please refresh the page.");
		}
	}, []);

	const fetchCMOs = useCallback(async (branchCd: string) => {
		if (!branchCd) {
			setCMOs([]);
			return;
		}
		try {
			const response = await api.get<CMO[]>('/MasterData/api/cmos', {
				params: { branch: branchCd },
			});
			setCMOs(response.data.filter(c => c.EMPLOYEE_ID && c.EMPLOYEE_ID !== "9999"));
		} catch (err) {
			console.error("Failed to fetch CMOs:", err);
		}
	}, []);

	const fetchSalesData = useCallback(async () => {
		if (!initialSalesNo || !initialSalType) return;

		setLoading(true);
		setError(null);

		try {
			const response = await api.get<SalesFormData>('/MasterData/api/sales/${initialSalesNo}', {
				params: { type: initialSalType, broker: initialBroker },
			});

			const data = response.data;
			const formatDate = (dateStr: string) => {
				if (!dateStr) return "";
				const [year, month, day] = dateStr.split("-");
				return `${day}-${month}-${year}`;
			};

			setFormData(prev => ({
				...prev,
				...data,
				ID_VALID_DT: data.ID_VALID_DT ? formatDate(data.ID_VALID_DT) : "",
				CREATED_DATE: data.CREATED_DATE ? formatDate(data.CREATED_DATE) : "",
				LAST_UPDATE: data.LAST_UPDATE ? formatDate(data.LAST_UPDATE) : "",
				EXPIRE_OPTION: data.ID_VALID_DT ? "1" : "0",
			}));

			if (data.BRANCH_CD) {
				await fetchCMOs(data.BRANCH_CD);
			}
		} catch (err) {
			console.error("Failed to fetch sales data:", err);
			setError("Failed to load sales record. Please try again.");
		} finally {
			setLoading(false);
		}
	}, [initialSalesNo, initialSalType, initialBroker, fetchCMOs]);

	const generateSalesNo = useCallback(async (branchCd: string) => {
		if (!branchCd) return;
		try {
			const response = await api.get<{ SALES_NO: string; CMO_NAME: string }>(
				'/MasterData/api/sales/generate-number',
				{ params: { branch: branchCd } }
			);
			setFormData(prev => ({
				...prev,
				SALES_NO: response.data.SALES_NO,
				CMO_NAME: response.data.CMO_NAME,
			}));
		} catch (err) {
			console.error("Failed to generate sales number:", err);
		}
	}, []);

	useEffect(() => {
		fetchComboData();
	}, [fetchComboData]);

	useEffect(() => {
		if (mode === "Edit" || mode === "View") {
			fetchSalesData();
		} else if (mode === "Add") {
			setFormData(prev => ({
				...prev,
				STATUS: "A",
				PAID: "1",
				EXPIRE_OPTION: "0",
				CREATED_BY: localStorage.getItem("username") || "",
				CREATED_DATE: new Date().toLocaleDateString("id-ID"),
			}));
		}
	}, [mode, fetchSalesData]);

	const handleBranchChange = useCallback((branchCd: string) => {
		setFormData(prev => ({ ...prev, BRANCH_CD: branchCd }));
		fetchCMOs(branchCd);
		if (mode === "Add" && branchCd) {
			generateSalesNo(branchCd);
		}
	}, [fetchCMOs, generateSalesNo, mode]);

	const handleSalesTypeChange = useCallback((value: "PT" | "PR" | "") => {
		setFormData(prev => ({
			...prev,
			SALES_TYPE: value,
			BROKER_TYPE: value === "PT" ? prev.BROKER_TYPE : "",
			IDCARD: value === "PT" ? "" : prev.IDCARD,
			OCCUPATION: value === "PT" ? "" : prev.OCCUPATION,
			EMAIL: value === "PT" ? "" : prev.EMAIL,
		}));
	}, []);

	const handleBrokerTypeChange = useCallback((value: "PT" | "PR" | "") => {
		setFormData(prev => ({
			...prev,
			BROKER_TYPE: value,
			NICKNAME: value === "PT" ? prev.NICKNAME : "",
			FAX: value === "PT" ? prev.FAX : "",
		}));
	}, []);

	const handleExpireOptionChange = useCallback((value: "0" | "1") => {
		setFormData(prev => ({
			...prev,
			EXPIRE_OPTION: value,
			ID_VALID_DT: value === "0" ? "" : prev.ID_VALID_DT,
		}));
	}, []);

	const handleChange = useCallback((field: keyof SalesFormData, value: string) => {
		setFormData(prev => ({ ...prev, [field]: value }));
		// Clear errors when user types
		if (error) setError(null);
		if (success) setSuccess(null);
	}, [error, success]);

	const formatForApi = useCallback((dateStr: string): string | null => {
		if (!dateStr) return null;
		const [day, month, year] = dateStr.split("-");
		return `${year}-${month}-${day}`;
	}, []);

	const validateForm = useCallback((): boolean => {
		if (!formData.NAME?.trim()) {
			setError("Name is required");
			return false;
		}
		if (!formData.SALES_TYPE) {
			setError("Sales Type is required");
			return false;
		}
		if (formData.SALES_TYPE === "PT" && !formData.BROKER_TYPE) {
			setError("Broker Type is required for PT Sales");
			return false;
		}
		if (formData.EXPIRE_OPTION === "1" && !formData.ID_VALID_DT && isIndividual) {
			setError("ID Valid Date is required when 'Certain Period' is selected");
			return false;
		}
		if (formData.IDCARD && !/^\d+$/.test(formData.IDCARD) && isIndividual) {
			setError("ID Card must contain only numbers");
			return false;
		}
		return true;
	}, [formData, isIndividual]);

	const handleSave = useCallback(async () => {
		if (!validateForm()) return;

		setSaving(true);
		setError(null);
		setSuccess(null);

		try {
			const payload = {
				...formData,
				ID_VALID_DT: formData.EXPIRE_OPTION === "1" ? formatForApi(formData.ID_VALID_DT) : null,
				CREATED_DATE: formatForApi(formData.CREATED_DATE),
			};

			const response = await api.post<ApiResponse<{ SALES_NO: string }>>(
				'/MasterData/api/sales',
				payload
			);

			if (response.data.success) {
				setSuccess("Sales record created successfully!");
				setTimeout(() => {
					navigate(`/sales-entry?id=Edit&salesno=${response.data.data?.SALES_NO}&sal_type=${formData.SALES_TYPE}&broker=${formData.BROKER_TYPE}`);
				}, 1500);
			} else {
				setError(response.data.message || "Failed to save record");
			}
		} catch (err: any) {
			console.error("Save error:", err);
			setError(err.response?.data?.message || "Failed to save. Please try again.");
		} finally {
			setSaving(false);
		}
	}, [formData, validateForm, formatForApi, navigate]);

	const handleUpdate = useCallback(async () => {
		if (!validateForm()) return;

		setSaving(true);
		setError(null);
		setSuccess(null);

		try {
			const payload = {
				...formData,
				ID_VALID_DT: formData.EXPIRE_OPTION === "1" ? formatForApi(formData.ID_VALID_DT) : null,
				LAST_UPDATE: new Date().toISOString().split("T")[0],
				UPDATE_BY: localStorage.getItem("username") || "",
			};

			const response = await api.put<ApiResponse>(
				'/MasterData/api/sales/${formData.SALES_NO}',
				payload
			);

			if (response.data.success) {
				setSuccess("Sales record updated successfully!");
				await fetchSalesData();
			} else {
				setError(response.data.message || "Failed to update record");
			}
		} catch (err: any) {
			console.error("Update error:", err);
			setError(err.response?.data?.message || "Failed to update. Please try again.");
		} finally {
			setSaving(false);
		}
	}, [formData, validateForm, formatForApi, fetchSalesData]);

	const handleSubmit = useCallback((e: React.FormEvent) => {
		e.preventDefault();
		if (isAddMode) {
			handleSave();
		} else if (isEditMode) {
			handleUpdate();
		}
	}, [isAddMode, isEditMode, handleSave, handleUpdate]);

	const handleCancel = useCallback(() => {
		navigate("/sales");
	}, [navigate]);

	if (loading && (mode === "Edit" || mode === "View")) {
		return (
			<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
				<div className="max-w-6xl mx-auto">
					<div className="bg-white rounded-2xl shadow-lg p-6 animate-pulse">
						<div className="h-8 bg-gray-200 rounded w-1/4 mb-6"></div>
						<div className="grid grid-cols-1 md:grid-cols-2 gap-6">
							{[...Array(12)].map((_, i) => (
								<div key={i} className="space-y-2">
									<div className="h-4 bg-gray-200 rounded w-1/3"></div>
									<div className="h-10 bg-gray-200 rounded"></div>
								</div>
							))}
						</div>
					</div>
				</div>
			</div>
		);
	}

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-6xl mx-auto">
				{/* Header */}
				<div className="bg-white rounded-2xl shadow-lg p-6 mb-6">
					<div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
						<div>
							<h1 className="text-2xl md:text-3xl font-bold text-gray-800">
								{mode === "Add" ? "Add New Sales" : mode === "Edit" ? "Edit Sales" : "View Sales"}
							</h1>
							<p className="text-gray-600 mt-1">
								{mode === "Add"
									? "Create a new sales or broker record"
									: mode === "Edit"
										? "Update sales or broker information"
										: "View sales record details"}
							</p>
						</div>
						{formData.SALES_NO && (
							<div className="flex items-center gap-3">
								<span className="bg-blue-100 text-blue-800 px-4 py-2 rounded-full text-sm font-medium">
									#{formData.SALES_NO}
								</span>
								<span className={`px-3 py-1 rounded-full text-xs font-semibold ${formData.STATUS === "A"
										? "bg-green-100 text-green-800"
										: "bg-red-100 text-red-800"
									}`}>
									{formData.STATUS === "A" ? "Active" : "Inactive"}
								</span>
							</div>
						)}
					</div>

					{/* Messages */}
					{error && (
						<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 flex items-start gap-3">
							<svg className="w-5 h-5 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
							</svg>
							<span>{error}</span>
						</div>
					)}

					{success && (
						<div className="mb-4 p-4 bg-green-50 border border-green-200 rounded-lg text-green-700 flex items-start gap-3">
							<svg className="w-5 h-5 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
							</svg>
							<span>{success}</span>
						</div>
					)}

					{/* Form */}
					<form onSubmit={handleSubmit} className="space-y-6">
						{/* Sales Information Section */}
						<div className="bg-gray-50 rounded-xl p-4 border border-gray-200">
							<h3 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
								<svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
								</svg>
								Sales Information
							</h3>

							<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
								{/* Sales Type */}
								<div>
									<label className="block text-sm font-medium text-gray-700 mb-1">
										Sales Type <span className="text-red-500">*</span>
									</label>
									<select
										value={formData.SALES_TYPE}
										onChange={(e) => handleSalesTypeChange(e.target.value as "PT" | "PR" | "")}
										disabled={isViewMode || isEditMode}
										className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
									>
										<option value="">Select Type</option>
										{salesTypes.map(type => (
											<option key={type.VALUE} value={type.VALUE}>{type.DESC_VALUE}</option>
										))}
									</select>
								</div>

								{/* Broker Type - Only for PT */}
								{showBrokerFields && (
									<div>
										<label className="block text-sm font-medium text-gray-700 mb-1">
											Broker Type <span className="text-red-500">*</span>
										</label>
										<select
											value={formData.BROKER_TYPE}
											onChange={(e) => handleBrokerTypeChange(e.target.value as "PT" | "PR" | "")}
											disabled={isViewMode}
											className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
										>
											<option value="">Select Broker</option>
											{brokerTypes.map(type => (
												<option key={type.VALUE} value={type.VALUE}>{type.DESC_VALUE}</option>
											))}
										</select>
									</div>
								)}

								{/* Status */}
								<div>
									<label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
									<select
										value={formData.STATUS}
										onChange={(e) => handleChange("STATUS", e.target.value as "A" | "I")}
										disabled={isViewMode}
										className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
									>
										<option value="A">Active</option>
										<option value="I">Inactive</option>
									</select>
								</div>

								{/* Branch */}
								<div>
									<label className="block text-sm font-medium text-gray-700 mb-1">Branch</label>
									<select
										value={formData.BRANCH_CD}
										onChange={(e) => handleBranchChange(e.target.value)}
										disabled={isViewMode || (isEditMode && !["10", "11"].includes(formData.SALES_NO?.substring(0, 2) || ""))}
										className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
									>
										<option value="">Select Branch</option>
										{branches.map(branch => (
											<option key={branch.BRANCH_CD} value={branch.BRANCH_CD}>
												{branch.BRANCH_NAME}
											</option>
										))}
									</select>
								</div>

								{/* CMO Name */}
								<div>
									<label className="block text-sm font-medium text-gray-700 mb-1">CMO Name</label>
									<select
										value={formData.CMO_NAME}
										onChange={(e) => handleChange("CMO_NAME", e.target.value)}
										disabled={isViewMode}
										className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
									>
										<option value="">Select CMO</option>
										{cmos.map(cmo => (
											<option key={cmo.EMPLOYEE_ID} value={cmo.EMPLOYEE_ID}>
												{cmo.FULLNAME}
											</option>
										))}
									</select>
								</div>

								{/* Sales No */}
								<div>
									<label className="block text-sm font-medium text-gray-700 mb-1">
										{isBroker ? "Broker" : "Sales"} No.
									</label>
									<input
										type="text"
										value={formData.SALES_NO}
										readOnly
										className="w-full px-3 py-2.5 bg-gray-100 border border-gray-300 rounded-lg text-gray-700 cursor-not-allowed"
									/>
								</div>

								{/* Initial Sales No */}
								<div>
									<label className="block text-sm font-medium text-gray-700 mb-1">Initial Sales No.</label>
									<input
										type="text"
										value={formData.SALES_NO?.substring(0, 2) || ""}
										readOnly
										className="w-full px-3 py-2.5 bg-gray-100 border border-gray-300 rounded-lg text-gray-700 cursor-not-allowed"
									/>
								</div>
							</div>
						</div>

						{/* Personal/Broker Details Section */}
						<div className="bg-gray-50 rounded-xl p-4 border border-gray-200">
							<h3 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
								<svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
								</svg>
								{isBroker ? "Broker" : "Sales"} Details
							</h3>

							<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
								{/* Name */}
								<div className="md:col-span-2">
									<label className="block text-sm font-medium text-gray-700 mb-1">
										Name <span className="text-red-500">*</span>
									</label>
									<input
										type="text"
										value={formData.NAME}
										onChange={(e) => handleChange("NAME", e.target.value)}
										disabled={isViewMode}
										placeholder="Enter full name"
										className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
									/>
								</div>

								{/* Gender - Only for Individual */}
								{showIndividualFields && (
									<div>
										<label className="block text-sm font-medium text-gray-700 mb-1">Gender</label>
										<select
											value={formData.GENDER}
											onChange={(e) => handleChange("GENDER", e.target.value)}
											disabled={isViewMode}
											className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
										>
											<option value="">Select Gender</option>
											{genders.map(gender => (
												<option key={gender.VALUE} value={gender.VALUE}>{gender.DESC_VALUE}</option>
											))}
										</select>
									</div>
								)}

								{/* Nickname - Only for PT Broker */}
								{showNickname && (
									<div>
										<label className="block text-sm font-medium text-gray-700 mb-1">Nick Name</label>
										<input
											type="text"
											value={formData.NICKNAME}
											onChange={(e) => handleChange("NICKNAME", e.target.value)}
											disabled={isViewMode}
											className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
										/>
									</div>
								)}

								{/* Occupation - Only for Individual */}
								{showIndividualFields && (
									<div>
										<label className="block text-sm font-medium text-gray-700 mb-1">Occupation</label>
										<select
											value={formData.OCCUPATION}
											onChange={(e) => handleChange("OCCUPATION", e.target.value)}
											disabled={isViewMode}
											className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
										>
											<option value="">Select Occupation</option>
											{occupations.map(occ => (
												<option key={occ.VALUE} value={occ.VALUE}>{occ.DESC_VALUE}</option>
											))}
										</select>
									</div>
								)}

								{/* ID Card - Only for Individual */}
								{showIndividualFields && (
									<div>
										<label className="block text-sm font-medium text-gray-700 mb-1">ID Card</label>
										<input
											type="text"
											value={formData.IDCARD}
											onChange={(e) => handleChange("IDCARD", e.target.value.replace(/\D/g, ""))}
											disabled={isViewMode}
											placeholder="Numbers only"
											maxLength={20}
											className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
										/>
									</div>
								)}

								{/* ID Valid Date - Only for Individual */}
								{showIndividualFields && (
									<div className="md:col-span-2">
										<label className="block text-sm font-medium text-gray-700 mb-2">ID Valid Date</label>
										<div className="flex flex-wrap gap-4 items-center">
											<label className="flex items-center gap-2 cursor-pointer">
												<input
													type="radio"
													name="expireOption"
													value="0"
													checked={formData.EXPIRE_OPTION === "0"}
													onChange={() => handleExpireOptionChange("0")}
													disabled={isViewMode}
													className="w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500 disabled:cursor-not-allowed"
												/>
												<span className="text-sm text-gray-700">No Expire Date</span>
											</label>
											<label className="flex items-center gap-2 cursor-pointer">
												<input
													type="radio"
													name="expireOption"
													value="1"
													checked={formData.EXPIRE_OPTION === "1"}
													onChange={() => handleExpireOptionChange("1")}
													disabled={isViewMode}
													className="w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500 disabled:cursor-not-allowed"
												/>
												<span className="text-sm text-gray-700">Certain Period</span>
											</label>
										</div>

										{showExpireDate && (
											<div className="mt-3">
												<input
													type="text"
													value={formData.ID_VALID_DT}
													onChange={(e) => handleChange("ID_VALID_DT", e.target.value)}
													disabled={isViewMode}
													placeholder="DD-MM-YYYY"
													className="w-full md:w-48 px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
												/>
												<p className="text-xs text-gray-500 mt-1">Format: DD-MM-YYYY</p>
											</div>
										)}
									</div>
								)}

								{/* Address */}
								<div className="md:col-span-2">
									<label className="block text-sm font-medium text-gray-700 mb-1">Address</label>
									<textarea
										value={formData.ADDRESS}
										onChange={(e) => handleChange("ADDRESS", e.target.value)}
										disabled={isViewMode}
										rows={3}
										className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all resize-none"
									/>
								</div>

								{/* City & Postcode */}
								<div className="grid grid-cols-2 gap-4 md:col-span-2">
									<div>
										<label className="block text-sm font-medium text-gray-700 mb-1">City</label>
										<input
											type="text"
											value={formData.CITY}
											onChange={(e) => handleChange("CITY", e.target.value)}
											disabled={isViewMode}
											className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
										/>
									</div>
									<div>
										<label className="block text-sm font-medium text-gray-700 mb-1">Post Code</label>
										<input
											type="text"
											value={formData.ZIPCODE}
											onChange={(e) => handleChange("ZIPCODE", e.target.value.replace(/\D/g, ""))}
											disabled={isViewMode}
											maxLength={5}
											placeholder="5 digits"
											className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
										/>
									</div>
								</div>

								{/* Phone */}
								<div>
									<label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
									<input
										type="text"
										value={formData.PHONE}
										onChange={(e) => handleChange("PHONE", e.target.value.replace(/\D/g, ""))}
										disabled={isViewMode}
										placeholder="Numbers only"
										className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
									/>
								</div>

								{/* Fax - Only for PT Broker */}
								{showFax && (
									<div>
										<label className="block text-sm font-medium text-gray-700 mb-1">Fax</label>
										<input
											type="text"
											value={formData.FAX}
											onChange={(e) => handleChange("FAX", e.target.value.replace(/\D/g, ""))}
											disabled={isViewMode}
											placeholder="Numbers only"
											className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
										/>
									</div>
								)}

								{/* Email - Only for Individual */}
								{showIndividualFields && (
									<div className="md:col-span-2">
										<label className="block text-sm font-medium text-gray-700 mb-1">Email Address</label>
										<input
											type="email"
											value={formData.EMAIL}
											onChange={(e) => handleChange("EMAIL", e.target.value)}
											disabled={isViewMode}
											placeholder="email@example.com"
											className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed transition-all"
										/>
									</div>
								)}

								{/* Refund Payment */}
								<div>
									<label className="block text-sm font-medium text-gray-700 mb-2">Refund Payment</label>
									<div className="flex gap-4">
										<label className="flex items-center gap-2 cursor-pointer">
											<input
												type="radio"
												name="paid"
												value="1"
												checked={formData.PAID === "1"}
												onChange={(e) => handleChange("PAID", e.target.value as "0" | "1")}
												disabled={isViewMode}
												className="w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500 disabled:cursor-not-allowed"
											/>
											<span className="text-sm text-gray-700">Paid</span>
										</label>
										<label className="flex items-center gap-2 cursor-pointer">
											<input
												type="radio"
												name="paid"
												value="0"
												checked={formData.PAID === "0"}
												onChange={(e) => handleChange("PAID", e.target.value as "0" | "1")}
												disabled={isViewMode}
												className="w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500 disabled:cursor-not-allowed"
											/>
											<span className="text-sm text-gray-700">Hold</span>
										</label>
									</div>
								</div>
							</div>
						</div>

						{/* Audit Trail - Read Only */}
						{showLastUpdate && (
							<div className="bg-gray-50 rounded-xl p-4 border border-gray-200">
								<h3 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
									<svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
									</svg>
									Audit Trail
								</h3>

								<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
									<div>
										<label className="block text-xs font-medium text-gray-500 mb-1">Created By</label>
										<input
											type="text"
											value={formData.CREATED_BY}
											readOnly
											className="w-full px-3 py-2 bg-gray-100 border border-gray-200 rounded-lg text-gray-600"
										/>
									</div>
									<div>
										<label className="block text-xs font-medium text-gray-500 mb-1">Created Date</label>
										<input
											type="text"
											value={formData.CREATED_DATE}
											readOnly
											className="w-full px-3 py-2 bg-gray-100 border border-gray-200 rounded-lg text-gray-600"
										/>
									</div>
									<div>
										<label className="block text-xs font-medium text-gray-500 mb-1">Last Update By</label>
										<input
											type="text"
											value={formData.UPDATE_BY}
											readOnly
											className="w-full px-3 py-2 bg-gray-100 border border-gray-200 rounded-lg text-gray-600"
										/>
									</div>
									<div>
										<label className="block text-xs font-medium text-gray-500 mb-1">Last Update</label>
										<input
											type="text"
											value={formData.LAST_UPDATE}
											readOnly
											className="w-full px-3 py-2 bg-gray-100 border border-gray-200 rounded-lg text-gray-600"
										/>
									</div>
								</div>
							</div>
						)}

						{/* Action Buttons */}
						<div className="flex flex-wrap gap-3 pt-4 border-t border-gray-200">
							{isAddMode && (
								<>
									<button
										type="submit"
										disabled={saving}
										className={`px-6 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-700 hover:from-blue-700 hover:to-indigo-800 text-white font-medium rounded-lg shadow-md hover:shadow-lg transition-all flex items-center gap-2 disabled:opacity-75 disabled:cursor-not-allowed ${saving ? "animate-pulse" : ""
											}`}
									>
										{saving ? (
											<>
												<svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
													<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
													<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
												</svg>
												Saving...
											</>
										) : (
											<>
												<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
													<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-4 0V5a2 2 0 114 0v2m-4 0h4" />
												</svg>
												Save Record
											</>
										)}
									</button>
									<button
										type="button"
										onClick={handleCancel}
										disabled={saving}
										className="px-6 py-2.5 bg-gray-200 hover:bg-gray-300 text-gray-800 font-medium rounded-lg transition-all disabled:opacity-75 disabled:cursor-not-allowed"
									>
										Cancel
									</button>
								</>
							)}

							{isEditMode && (
								<>
									<button
										type="submit"
										disabled={saving}
										className={`px-6 py-2.5 bg-gradient-to-r from-green-600 to-emerald-700 hover:from-green-700 hover:to-emerald-800 text-white font-medium rounded-lg shadow-md hover:shadow-lg transition-all flex items-center gap-2 disabled:opacity-75 disabled:cursor-not-allowed ${saving ? "animate-pulse" : ""
											}`}
									>
										{saving ? (
											<>
												<svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
													<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
													<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
												</svg>
												Updating...
											</>
										) : (
											<>
												<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
													<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
												</svg>
												Update Record
											</>
										)}
									</button>
									<button
										type="button"
										onClick={handleCancel}
										disabled={saving}
										className="px-6 py-2.5 bg-gray-200 hover:bg-gray-300 text-gray-800 font-medium rounded-lg transition-all disabled:opacity-75 disabled:cursor-not-allowed"
									>
										Cancel
									</button>
								</>
							)}

							{isViewMode && (
								<button
									type="button"
									onClick={handleCancel}
									className="px-6 py-2.5 bg-gray-200 hover:bg-gray-300 text-gray-800 font-medium rounded-lg transition-all"
								>
									Back to List
								</button>
							)}
						</div>
					</form>
				</div>

				{/* Help Text */}
				<div className="text-center text-sm text-gray-500 mt-4">
					<p>
						Fields marked with <span className="text-red-500">*</span> are required.
						{isViewMode && " This record is in view-only mode."}
					</p>
				</div>
			</div>
		</div>
	);
};

export default SalesMainPage;