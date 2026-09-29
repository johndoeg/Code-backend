import React, { useState, useCallback, useRef } from "react";
import api from '../../api/axiosInstance';

interface AmortizationRow {
	PERIOD: number;
	DueDate: string;
	RENTAL: string;
	ACCRUAL1: string;
	ACCRUAL2: string;
	L_INCOME: string;
	I_RECOVERY: string;
	OUTS_PRINC: string;
	UN_INCOME: string;
	OUTS_REC: string;
	Payment: string;
	L_INCOME_PSAK: string;
	I_RECOVERY_PSAK: string;
	OUTS_PRINC_PSAK: string;
	UN_INCOME_PSAK: string;
	ATRIBUTE: string;
}

interface AmortizationData {
	customerName: string;
	declrate: number;
	irr: number;
	rows: AmortizationRow[];
}

const AmortizationReport: React.FC = () => {
	const [leaseNo, setLeaseNo] = useState<string>("");
	const [loading, setLoading] = useState<boolean>(false);
	const [data, setData] = useState<AmortizationData | null>(null);
	const [error, setError] = useState<string | null>(null);
	const tableContainerRef = useRef<HTMLDivElement>(null);

	const fetchAmortization = useCallback(async () => {
		if (!leaseNo.trim()) {
			setError("Please enter a Contract No.");
			return;
		}

		setLoading(true);
		setError(null);

		try {
			const response = await api.get<AmortizationData>(
				'/HistoryPayment/api/amortization',
				{
					params: { lease_no: leaseNo },
				}
			);
			setData(response.data);
		} catch (err: any) {
			console.error("Failed to fetch amortization data:", err);
			setError(
				err.response?.data?.message ||
				"Failed to load amortization report. Please check the contract number."
			);
			setData(null);
		} finally {
			setLoading(false);
		}
	}, [leaseNo]);

	const handlePreview = () => {
		fetchAmortization();
	};

	const handlePrint = (type: "contractual" | "all") => {
		if (!data) return;
		const url = `/HistoryPayment/api/print/amortization?lease_no=${leaseNo}&type=${type}`;
		window.open(url, "_blank");
	};

	const handleExport = () => {
		if (!data) return;
		const url = `/HistoryPayment/api/export/amortization?lease_no=${leaseNo}&format=xlsx`;
		window.open(url, "_blank");
	};

	const formatCurrency = (value: string) => {
		return value;
	};

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-[1920px] mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6 mb-6">
					<div className="mb-6">
						<h1 className="text-2xl md:text-3xl font-bold text-gray-800">
							Amortization Report
						</h1>
						<p className="text-gray-600 mt-1">
							View and export amortization schedules for lease contracts
						</p>
					</div>

					<div className="bg-gray-50 rounded-xl p-4 border border-gray-200 mb-6 no-print">
						<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">
									Contract No. *
								</label>
								<input
									type="text"
									inputMode="numeric"
									value={leaseNo}
									onChange={(e) => {
										const digitsOnly = e.target.value.replace(/\D/g, "").slice(0, 16);
										setLeaseNo(digitsOnly);
									}}
									onKeyPress={(e) => e.key === "Enter" && handlePreview()}
									placeholder="Enter contract number"
									maxLength={16}
									className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all"
								/>
							</div>
							<div>
								<label className="block text-sm font-medium text-gray-700 mb-1">
									Customer Name
								</label>
								<input
									type="text"
									value={data?.customerName || ""}
									readOnly
									className="w-full px-3 py-2.5 bg-gray-100 border border-gray-300 rounded-lg text-gray-700 cursor-not-allowed"
								/>
							</div>
						</div>

						<div className="flex flex-wrap gap-3 mt-4">
							<button
								onClick={handlePreview}
								disabled={loading || !leaseNo.trim()}
								className={`px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed`}
							>
								{loading ? (
									<>
										<svg
											className="animate-spin h-4 w-4 text-white"
											fill="none"
											viewBox="0 0 24 24"
										>
											<circle
												className="opacity-25"
												cx="12"
												cy="12"
												r="10"
												stroke="currentColor"
												strokeWidth="4"
											></circle>
											<path
												className="opacity-75"
												fill="currentColor"
												d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
											></path>
										</svg>
										Loading...
									</>
								) : (
									<>
										<svg
											className="w-4 h-4"
											fill="none"
											stroke="currentColor"
											viewBox="0 0 24 24"
										>
											<path
												strokeLinecap="round"
												strokeLinejoin="round"
												strokeWidth="2"
												d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
											/>
											<path
												strokeLinecap="round"
												strokeLinejoin="round"
												strokeWidth="2"
												d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
											/>
										</svg>
										Preview
									</>
								)}
							</button>

							{data && (
								<>
									<button
										onClick={() => handlePrint("contractual")}
										className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center gap-2"
									>
										<svg
											className="w-4 h-4"
											fill="none"
											stroke="currentColor"
											viewBox="0 0 24 24"
										>
											<path
												strokeLinecap="round"
												strokeLinejoin="round"
												strokeWidth="2"
												d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"
											/>
										</svg>
										Print Contractual
									</button>

									<button
										onClick={() => handlePrint("all")}
										className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors flex items-center gap-2"
									>
										<svg
											className="w-4 h-4"
											fill="none"
											stroke="currentColor"
											viewBox="0 0 24 24"
										>
											<path
												strokeLinecap="round"
												strokeLinejoin="round"
												strokeWidth="2"
												d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"
											/>
										</svg>
										Print All
									</button>

									<button
										onClick={handleExport}
										className="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 transition-colors flex items-center gap-2"
									>
										<svg
											className="w-4 h-4"
											fill="none"
											stroke="currentColor"
											viewBox="0 0 24 24"
										>
											<path
												strokeLinecap="round"
												strokeLinejoin="round"
												strokeWidth="2"
												d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
											/>
										</svg>
										Export to Excel
									</button>
								</>
							)}
						</div>
					</div>

					{error && (
						<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 flex items-start gap-3">
							<svg
								className="w-5 h-5 mt-0.5 flex-shrink-0"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									strokeLinecap="round"
									strokeLinejoin="round"
									strokeWidth="2"
									d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
								/>
							</svg>
							<span>{error}</span>
						</div>
					)}

					{data && (
						<div
							ref={tableContainerRef}
							className="overflow-x-auto rounded-lg border border-gray-200"
							style={{ maxHeight: "70vh" }}
						>
							<table className="w-full text-sm font-tahoma table-fixed">
								<colgroup>
									<col className="w-[60px]" />
									<col className="w-[100px]" />
									<col className="w-[120px]" />
									<col className="w-[100px]" />
									<col className="w-[100px]" />
									<col className="w-[110px]" />
									<col className="w-[100px]" />
									<col className="w-[130px]" />
									<col className="w-[110px]" />
									<col className="w-[130px]" />
									<col className="w-[100px]" />
									<col className="w-[110px]" />
									<col className="w-[100px]" />
									<col className="w-[130px]" />
									<col className="w-[110px]" />
									<col className="w-[90px]" />
								</colgroup>

								<thead className="bg-gradient-to-r from-gray-50 to-gray-100 sticky top-0 z-10">
									<tr>
										<th
											rowSpan={2}
											className="py-3 px-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider border border-gray-300 bg-gray-100"
										>
											Period
										</th>
										<th
											rowSpan={2}
											className="py-3 px-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider border border-gray-300 bg-gray-100"
										>
											Due Date
										</th>
										<th
											rowSpan={2}
											className="py-3 px-2 text-right text-xs font-medium text-gray-500 uppercase tracking-wider border border-gray-300 bg-gray-100"
										>
											Installment
										</th>
										<th
											colSpan={7}
											className="py-3 px-2 text-center text-xs font-medium text-blue-700 uppercase tracking-wider border border-gray-300 bg-blue-100"
										>
											Contractual ({data.declrate}%)
										</th>
										<th
											rowSpan={2}
											className="py-3 px-2 text-center text-xs font-medium text-gray-500 uppercase tracking-wider border border-gray-300 bg-gray-100"
										>
											Payment Date
										</th>
										<th
											colSpan={5}
											className="py-3 px-2 text-center text-xs font-medium text-green-700 uppercase tracking-wider border border-gray-300 bg-green-100"
										>
											PSAK ({data.irr}%)
										</th>
									</tr>
									<tr className="bg-gray-50">
										<th className="py-2 px-2 text-right text-[10px] font-medium text-gray-600 border border-gray-300 bg-blue-50">
											Accrual 1
										</th>
										<th className="py-2 px-2 text-right text-[10px] font-medium text-gray-600 border border-gray-300 bg-blue-50">
											Accrual 2
										</th>
										<th className="py-2 px-2 text-right text-[10px] font-medium text-gray-600 border border-gray-300 bg-blue-50">
											Interest Income
										</th>
										<th className="py-2 px-2 text-right text-[10px] font-medium text-gray-600 border border-gray-300 bg-blue-50">
											Recovery
										</th>
										<th className="py-2 px-2 text-right text-[10px] font-medium text-gray-600 border border-gray-300 bg-blue-50">
											Outstanding Principal
										</th>
										<th className="py-2 px-2 text-right text-[10px] font-medium text-gray-600 border border-gray-300 bg-blue-50">
											Unearned Income
										</th>
										<th className="py-2 px-2 text-right text-[10px] font-medium text-gray-600 border border-gray-300 bg-blue-50">
											Outstanding Receivable
										</th>
										<th className="py-2 px-2 text-right text-[10px] font-medium text-gray-600 border border-gray-300 bg-green-50">
											Interest Income
										</th>
										<th className="py-2 px-2 text-right text-[10px] font-medium text-gray-600 border border-gray-300 bg-green-50">
											Recovery
										</th>
										<th className="py-2 px-2 text-right text-[10px] font-medium text-gray-600 border border-gray-300 bg-green-50">
											Outstanding Principal
										</th>
										<th className="py-2 px-2 text-right text-[10px] font-medium text-gray-600 border border-gray-300 bg-green-50">
											Unearned Income
										</th>
										<th className="py-2 px-2 text-right text-[10px] font-medium text-gray-600 border border-gray-300 bg-green-50">
											Attribute
										</th>
									</tr>
								</thead>
								<tbody className="divide-y divide-gray-200">
									{data.rows.map((row, idx) => (
										<tr
											key={row.PERIOD}
											className={`hover:bg-blue-50 transition-colors ${idx % 2 === 0 ? "bg-white" : "bg-gray-50/50"
												}`}
										>
											<td className="py-2 px-2 text-center border border-gray-200 font-medium text-gray-900">
												{row.PERIOD}
											</td>
											<td className="py-2 px-2 border border-gray-200 text-gray-700">
												{row.DueDate}
											</td>
											<td className="py-2 px-2 text-right border border-gray-200 font-semibold text-gray-900">
												{formatCurrency(row.RENTAL)}
											</td>
											<td className="py-2 px-2 text-right border border-gray-200 text-gray-700">
												{formatCurrency(row.ACCRUAL1)}
											</td>
											<td className="py-2 px-2 text-right border border-gray-200 text-gray-700">
												{formatCurrency(row.ACCRUAL2)}
											</td>
											<td className="py-2 px-2 text-right border border-gray-200 text-gray-700">
												{formatCurrency(row.L_INCOME)}
											</td>
											<td className="py-2 px-2 text-right border border-gray-200 text-gray-700">
												{formatCurrency(row.I_RECOVERY)}
											</td>
											<td className="py-2 px-2 text-right border border-gray-200 font-medium text-gray-900">
												{formatCurrency(row.OUTS_PRINC)}
											</td>
											<td className="py-2 px-2 text-right border border-gray-200 text-gray-700">
												{formatCurrency(row.UN_INCOME)}
											</td>
											<td className="py-2 px-2 text-right border border-gray-200 font-medium text-gray-900">
												{formatCurrency(row.OUTS_REC)}
											</td>
											<td className="py-2 px-2 border border-gray-200 text-gray-700">
												{row.Payment || "-"}
											</td>
											<td className="py-2 px-2 text-right border border-gray-200 text-gray-700">
												{formatCurrency(row.L_INCOME_PSAK)}
											</td>
											<td className="py-2 px-2 text-right border border-gray-200 text-gray-700">
												{formatCurrency(row.I_RECOVERY_PSAK)}
											</td>
											<td className="py-2 px-2 text-right border border-gray-200 font-medium text-gray-900">
												{formatCurrency(row.OUTS_PRINC_PSAK)}
											</td>
											<td className="py-2 px-2 text-right border border-gray-200 text-gray-700">
												{formatCurrency(row.UN_INCOME_PSAK)}
											</td>
											<td className="py-2 px-2 text-right border border-gray-200 text-gray-700">
												{formatCurrency(row.ATRIBUTE)}
											</td>
										</tr>
									))}
								</tbody>
							</table>
						</div>
					)}

					{loading && (
						<div className="py-10 text-center">
							<div className="flex justify-center">
								<svg
									className="animate-spin h-8 w-8 text-blue-600"
									fill="none"
									viewBox="0 0 24 24"
								>
									<circle
										className="opacity-25"
										cx="12"
										cy="12"
										r="10"
										stroke="currentColor"
										strokeWidth="4"
									></circle>
									<path
										className="opacity-75"
										fill="currentColor"
										d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
									></path>
								</svg>
							</div>
							<p className="mt-4 text-gray-600">Loading amortization data...</p>
						</div>
					)}

					{!loading && !data && !error && (
						<div className="py-10 text-center text-gray-500">
							<svg
								className="w-16 h-16 text-gray-300 mx-auto mb-4"
								fill="none"
								stroke="currentColor"
								viewBox="0 0 24 24"
							>
								<path
									strokeLinecap="round"
									strokeLinejoin="round"
									strokeWidth="2"
									d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
								/>
							</svg>
							<p className="text-lg">Enter a Contract No. to view amortization</p>
							<p className="text-sm mt-1">
								Preview will show the amortization schedule for the contract
							</p>
						</div>
					)}
				</div>

				<div className="text-center text-sm text-gray-500 mt-4">
					<p>
						Contractual rate: <span className="font-medium text-blue-600">{data?.declrate}%</span> |
						PSAK rate: <span className="font-medium text-green-600">{data?.irr}%</span>
					</p>
				</div>
			</div>

			<style>{`
			@media print {
				@page {
					size: A4 landscape;
					margin: 0.5cm;
				}
			
				.no-print {
					display: none !important;
				}
			
				body {
					font-family: Tahoma, Geneva, sans-serif;
					font-size: 8px;
					-webkit-print-color-adjust: exact;
					print-color-adjust: exact;
					background: white !important;
				}
				
				table {
					font-family: Tahoma, Geneva, sans-serif;
					font-size: 7.5px;
					width: 100% !important;
					table-layout: fixed !important;
				}
				
				th, td {
					padding: 1px 2px !important;
					white-space: nowrap !important;
					overflow: hidden !important;
					text-overflow: ellipsis !important;
				}
				
				col:nth-child(1) { width: 45px !important; }
				col:nth-child(2) { width: 75px !important; }
				col:nth-child(3) { width: 90px !important; }
				col:nth-child(4) { width: 75px !important; }
				col:nth-child(5) { width: 75px !important; }
				col:nth-child(6) { width: 85px !important; }
				col:nth-child(7) { width: 75px !important; }
				col:nth-child(8) { width: 100px !important; }
				col:nth-child(9) { width: 85px !important; }
				col:nth-child(10) { width: 100px !important; }
				col:nth-child(11) { width: 75px !important; }
				col:nth-child(12) { width: 85px !important; }
				col:nth-child(13) { width: 75px !important; }
				col:nth-child(14) { width: 100px !important; }
				col:nth-child(15) { width: 85px !important; }
				col:nth-child(16) { width: 70px !important; }
				
				h1 {
					font-size: 11px !important;
				}
				
				tr:hover {
					background: transparent !important;
				}
				
				.border-gray-200, .border-gray-300 {
					border-color: #000 !important;
				}
			}
				
			@media screen {
				.font-tahoma {
					font-family: Tahoma, Geneva, sans-serif;
				}
				
				thead.sticky {
					position: sticky;
					top: 0;
					z-index: 20;
					box-shadow: 0 2px 4px rgba(0,0,0,0.1);
				}
				
				.overflow-x-auto {
					scroll-behavior: smooth;
					-webkit-overflow-scrolling: touch;
				}
				
				tbody tr:hover {
					background-color: #eff6ff !important;
					transform: translateX(0);
					transition: background-color 0.15s ease;
				}
			}
				
			.text-nowrap {
				white-space: nowrap;
			}
			
			.text-truncate {
				overflow: hidden;
				text-overflow: ellipsis;
				white-space: nowrap;
			}
      `}</style>
		</div>
	);
};

export default AmortizationReport;