import React, { useState, useEffect, useCallback } from "react";
import api from '../../api/axiosInstance';
import AsOfDatePicker from '../../components/AsOfDatePickerComponent';

interface Branch {
	BRANCH_CD: string;
	BRANCH_NAME: string;
}

interface EquipmentType {
	VALUE: string;
	DESC_VALUE: string;
}

const DetailAgingReportPage: React.FC = () => {
	const [asof, setAsof] = useState<Date | null>(null);
	const [branchCd, setBranchCd] = useState<string>("");
	const [typeOf, setTypeOf] = useState<string>("");

	const [branches, setBranches] = useState<Branch[]>([]);
	const [equipmentTypes, setEquipmentTypes] = useState<EquipmentType[]>([]);

	const [loading, setLoading] = useState<boolean>(false);
	const [error, setError] = useState<string | null>(null);

	const formatDateForApi = (date: Date | null): string => {
		if (!date) return "";
		const day = String(date.getDate()).padStart(2, "0");
		const month = String(date.getMonth() + 1).padStart(2, "0");
		const year = date.getFullYear();

		return `${day}-${month}-${year}`;
	};

	useEffect(() => {
		const fetchDropdownData = async () => {
			setLoading(true);
			try {
				const [branchesRes, typesRes] = await Promise.all([
					api.get<Branch[]>('/Common/api/branches'),
					api.get<EquipmentType[]>('/Common/api/combo/TYPE_OF_EQUIPMENT'),
				]);

				const extractData = <T,>(response: { success: boolean; data: T[]; total?: number } | T[]): T[] => {
					return Array.isArray(response) ? response : response.data || [];
				};

				setBranches(extractData<Branch>(branchesRes.data));
				setEquipmentTypes(extractData<EquipmentType>(typesRes.data));

			} catch (err) {
				console.error("Failed to fetch dropdown data:", err);
				setError("Failed to load form options. Please refresh the page.");
			} finally {
				setLoading(false);
			}
		};
		fetchDropdownData();
	}, []);

	const handleExportExcel = useCallback(() => {
		if (!asof) {
			alert("Please select date first");
			return;
		}

		const params = new URLSearchParams({
			asof: formatDateForApi(asof),
			branch_cd: branchCd,
			type_of: typeOf,
		});

		window.open(`/Report/export/aging-detail?${params.toString()}`, "_blank");
	}, [asof, branchCd, typeOf]);

	const handleExportPDF = useCallback(() => {
		if (!asof) {
			alert("Please select date first");
			return;
		}

		const params = new URLSearchParams({
			asof: formatDateForApi(asof),
			branch_cd: branchCd,
			type_of: typeOf,
		});

		window.open(`/Report/print/aging-detail?${params.toString()}`, "_blank");
	}, [asof, branchCd, typeOf]);


	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-4xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6 mb-6">
					<div className="mb-6">
						<h1 className="text-2xl md:text-3xl font-bold text-gray-800">
							Detail Aging Report
						</h1>
						<p className="text-gray-600 mt-1">
							Generate detailed aging reports by branch and equipment type
						</p>
					</div>

					{error && (
						<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 flex items-start gap-3">
							<svg className="w-5 h-5 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
							</svg>
							<span>{error}</span>
						</div>
					)}

					<div className="bg-gray-50 rounded-xl p-4 border border-gray-200 no-print">
						<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
							<div>
								<AsOfDatePicker value={asof} onChange={setAsof} format="DD-MM-YYYY" label="As of" required />
								<p className="text-xs text-gray-500 mt-1">Format: DD-MM-YYYY</p>
							</div>

							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">
									Branch
								</label>
								<select
									id="branch_cd"
									value={branchCd}
									onChange={(e) => setBranchCd(e.target.value)}
									className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all"
								>
									<option value="">Select</option>
									{branches.map(branch => (
										<option key={branch.BRANCH_CD} value={branch.BRANCH_CD}>
											{branch.BRANCH_NAME}
										</option>
									))}
								</select>
							</div>

							<div className="md:col-span-2">
								<label className="block text-sm font-medium text-gray-700 mb-1">
									Type of Equipment
								</label>
								<select
									id="type_of"
									value={typeOf}
									onChange={(e) => setTypeOf(e.target.value)}
									className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all"
								>
									<option value="">Select</option>
									{equipmentTypes.map(type => (
										<option key={type.VALUE} value={type.VALUE}>
											{type.DESC_VALUE}
										</option>
									))}
								</select>
							</div>
						</div>

						<div className="flex flex-wrap gap-3 mt-6">
							<button
								onClick={handleExportExcel}
								disabled={!asof || loading}
								className={`px-6 py-2.5 bg-gradient-to-r from-green-600 to-emerald-700 hover:from-green-700 hover:to-emerald-800 text-white font-medium rounded-lg shadow-md hover:shadow-lg transition-all flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed`}
							>
								<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
								</svg>
								Export to Excel
							</button>

							<button
								onClick={handleExportPDF}
								disabled={!asof || loading}
								className={`px-6 py-2.5 bg-gradient-to-r from-red-600 to-rose-700 hover:from-red-700 hover:to-rose-800 text-white font-medium rounded-lg shadow-md hover:shadow-lg transition-all flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed`}
							>
								<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
								</svg>
								Export to PDF
							</button>
						</div>
					</div>
				</div>
			</div>

			<style>{`
                @media print {
                    .no-print {
                        display: none !important;
                    }
                }
            `}</style>
		</div>
	);
};

export default DetailAgingReportPage;