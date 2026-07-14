import React, { useEffect, useState, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import api from '../../api/axiosInstance';

interface ContractInfo {
	LESSEE_NO: string;
	trans_code: string;
	LESSEE_NM: string;
	ADDRESS: string;
	PHONE1: string;
	PHONE2: string;
	PHONE3: string;
	BPKB_AN: string;
	POLICENO: string;
	CHASIS: string;
	ENGINE: string;
	TAHUN: string;
	COLOUR: string;
	suppname: string;
	TYPE_NM: string;
	MODEL_NM: string;
	BRANCH_NAME: string;
	DATEBLOKIR: string;
	NOPOLBLOKIR: string;
	status_kontrak: string;
	JFG: string;
}

interface PaymentRow {
	girono: string;
	girodt: string;
	payment: string;
	bank: string;
	nominal: number;
	period: string;
	penalty: number;
	Shortage: number;
	inkaso: number;
	status: string | null;
	reject_description: string;
	penalty_payment: number;
	ShortagePay: number;
	InkasoPay: number;
}

interface LeaseReport {
	leaseNo: string;
	contractInfo: ContractInfo;
	payments: PaymentRow[];
	totAmount: number;
	totPenalty: number;
	totShortage: number;
	totInkaso: number;
	penaltyPayment: number;
	shortagePay: number;
	inkasoPay: number;
}

const fmt = (n: number | null | undefined) =>
	n ? n.toLocaleString("id-ID") : "0";

const fmtDate = (d: string | null | undefined) => {
	if (!d) return "";
	const dt = new Date(d);
	if (isNaN(dt.getTime())) return d;
	return dt.toLocaleDateString("id-ID", {
		day: "2-digit",
		month: "2-digit",
		year: "numeric",
	});
};

const todayLong = () =>
	new Date().toLocaleDateString("en-GB", {
		day: "2-digit",
		month: "long",
		year: "numeric",
	});

const todayShort = () =>
	new Date().toLocaleDateString("en-GB", {
		day: "2-digit",
		month: "2-digit",
		year: "2-digit",
	});

const PrintHistoryPayment: React.FC = () => {
	const [searchParams] = useSearchParams();
	const leaseNoParam = searchParams.get("lease_no") ?? "";
	const leaseNos = leaseNoParam.split(",").filter(Boolean);

	const [reports, setReports] = useState<LeaseReport[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const hasFetched = useRef(false);

	useEffect(() => {
		if (hasFetched.current || leaseNos.length === 0) return;
		hasFetched.current = true;
		fetchAllReports();
	}, []);

	const fetchAllReports = async () => {
		setLoading(true);
		setError(null);
		try {
			const results = await Promise.all(
				leaseNos.map((ln) =>
					api
						.get<{ contractInfo: ContractInfo; payments: PaymentRow[] }>(
							'/HistoryPayment/api/history-payment/print',
							{ params: { lease_no: ln } }
						)
						.then(({ data }) => {
							const { contractInfo, payments } = data;

							let totAmount = 0;
							let totPenalty = 0;
							let totShortage = 0;
							let totInkaso = 0;
							let penaltyPayment = 0;
							let shortagePay = 0;
							let inkasoPay = 0;

							payments.forEach((row, idx) => {
								if (!String(row.period ?? "").includes("*")) {
									totAmount += row.nominal ?? 0;
								}
								totPenalty += row.penalty ?? 0;
								totShortage += row.Shortage ?? 0;
								totInkaso += (row.inkaso ?? 0) * 25000;

								if (idx === 0) {
									penaltyPayment = row.penalty_payment ?? 0;
									shortagePay = row.ShortagePay ?? 0;
									inkasoPay = row.InkasoPay ?? 0;
								}
							});

							return {
								leaseNo: ln,
								contractInfo,
								payments,
								totAmount,
								totPenalty,
								totShortage,
								totInkaso,
								penaltyPayment,
								shortagePay,
								inkasoPay,
							} satisfies LeaseReport;
						})
				)
			);
			setReports(results);
		} catch (err: any) {
			console.error(err);
			setError(
				err.response?.data?.message ??
				"Failed to load report data. Please try again."
			);
		} finally {
			setLoading(false);
		}
	};

	if (loading) {
		return (
			<div className="min-h-screen flex items-center justify-center bg-white">
				<div className="flex flex-col items-center gap-4 text-gray-500">
					<svg
						className="animate-spin h-10 w-10 text-blue-600"
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
						/>
						<path
							className="opacity-75"
							fill="currentColor"
							d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
						/>
					</svg>
					<p>Loading report…</p>
				</div>
			</div>
		);
	}

	if (error) {
		return (
			<div className="min-h-screen flex items-center justify-center bg-white">
				<div className="text-center text-red-600 space-y-3">
					<p className="text-lg font-semibold">{error}</p>
					<button
						onClick={fetchAllReports}
						className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 transition"
					>
						Retry
					</button>
				</div>
			</div>
		);
	}

	return (
		<>
			<style>{`
				@media print {
					.no-print { display: none !important; }
					.page { page-break-after: always; }
					body { font-family: Tahoma, sans-serif; font-size: 10px; }
				}

				@media screen {
					body { font-family: Tahoma, sans-serif; font-size: 12px; background: #f3f4f6; }
					.page { background: white; margin: 16px auto; padding: 24px; max-width: 1100px; box-shadow: 0 2px 8px rgba(0,0,0,.12); }
				}
				table { border-collapse: collapse; width: 100%; }
				td, th { padding: 2px 4px; vertical-align: top; }
				.tbl-border td, .tbl-border th { border: 1px solid #000; }
				.tbl-border td { vertical-align: middle; }
			`}</style>

			<div className="no-print p-4 flex justify-end max-w-[1100px] mx-auto">
				<button
					onClick={() => window.print()}
					className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded shadow transition"
				>
					🖨 Print
				</button>
			</div>

			{reports.map((rpt, idx) => {
				const ci = rpt.contractInfo;
				const pageNo = idx + 1;

				let prevGiro = "";
				let rowNum = 0;

				return (
					<div key={rpt.leaseNo} className="page">
						<table>
							<tbody>
								<tr valign="top">
									<td style={{ width: "76%" }} rowSpan={2}>
										{ci.BRANCH_NAME} Branch
									</td>
									<td>Date: {todayShort()}</td>
								</tr>
								<tr>
									<td>Page: {pageNo}</td>
								</tr>
							</tbody>
						</table>

						<div style={{ textAlign: "center", marginBottom: 8 }}>
							<strong>
								<u>CUSTOMER HISTORY PAYMENT REPORT</u>
								<br />
								As of {todayLong()}
							</strong>
						</div>

						<table style={{ marginBottom: 8 }}>
							<tbody>
								<tr valign="top">
									<td style={{ width: "15%" }}>Transaction Code</td>
									<td style={{ width: "33%" }}>: {ci.trans_code}</td>
									<td style={{ width: "10%" }} rowSpan={2}>Address</td>
									<td style={{ width: "42%" }} rowSpan={2}>
										: {ci.ADDRESS?.toUpperCase()}
									</td>
								</tr>
								<tr>
									<td>Customer No.</td>
									<td>: {ci.LESSEE_NO}</td>
								</tr>
								<tr>
									<td>Contract No.</td>
									<td>
										: {rpt.leaseNo}&nbsp;\&nbsp;{ci.LESSEE_NM}
									</td>
									<td>Telp</td>
									<td>
										:{" "}
										{[ci.PHONE1, ci.PHONE2, ci.PHONE3]
											.filter(Boolean)
											.join(", ")}
									</td>
								</tr>
							</tbody>
						</table>

						<table className="tbl-border" style={{ marginBottom: 4 }}>
							<thead>
								<tr style={{ textAlign: "center", backgroundColor: "#f0f0f0" }}>
									<th style={{ width: "3%" }}>No.</th>
									<th style={{ width: "8%" }}>Cheque No.</th>
									<th style={{ width: "8%" }}>Date Due</th>
									<th style={{ width: "10%" }}>Bank</th>
									<th style={{ width: "10%" }}>Amount</th>
									<th style={{ width: "5%" }}>OD Days</th>
									<th style={{ width: "3%" }}>Sts</th>
									<th style={{ width: "9%" }}>Payment Date</th>
									<th style={{ width: "10%" }}>Penalty Charge</th>
									<th style={{ width: "10%" }}>Shortage</th>
									<th style={{ width: "9%" }}>Inkaso</th>
									<th style={{ width: "15%" }}>Remark</th>
								</tr>
							</thead>
							<tbody>
								{rpt.payments.map((row, ri) => {
									let displayGiro: string;
									if (row.girono === prevGiro) {
										displayGiro = "";
									} else {
										displayGiro = row.girono ?? "";
										prevGiro = row.girono ?? "";
									}

									const isAsterisk = String(row.period ?? "").includes("*");
									if (!isAsterisk) rowNum++;
									const displayNum = isAsterisk ? "" : String(rowNum);

									let odDays = "";
									if (row.status != null && row.payment && row.girodt) {
										const d1 = new Date(row.payment);
										const d2 = new Date(row.girodt);
										const diff = Math.floor(
											(d2.getTime() - d1.getTime()) / 86400000
										);
										odDays = diff > 0 ? String(diff) : "0";
									}

									const inkasoAmt = (row.inkaso ?? 0) * 25000;

									return (
										<tr key={ri}>
											<td style={{ textAlign: "center" }}>{displayNum}</td>
											<td style={{ textAlign: "center" }}>{displayGiro}</td>
											<td style={{ textAlign: "center" }}>
												{fmtDate(row.girodt)}
											</td>
											<td>{row.bank}</td>
											<td style={{ textAlign: "right" }}>
												{row.nominal ? fmt(row.nominal) : "0"}
											</td>
											<td style={{ textAlign: "center" }}>{odDays}</td>
											<td style={{ textAlign: "center" }}>{row.status}</td>
											<td style={{ textAlign: "center" }}>
												{fmtDate(row.payment)}
											</td>
											<td style={{ textAlign: "right" }}>
												{row.penalty ? fmt(row.penalty) : "0"}
											</td>
											<td style={{ textAlign: "right" }}>
												{row.Shortage ? fmt(row.Shortage) : "0"}
											</td>
											<td style={{ textAlign: "right" }}>
												{inkasoAmt ? fmt(inkasoAmt) : "0"}
											</td>
											<td>{row.reject_description}</td>
										</tr>
									);
								})}

								<tr>
									<td colSpan={4} style={{ textAlign: "right" }}>
										<strong>TOTAL</strong>
									</td>
									<td style={{ textAlign: "right" }}>
										<strong>{fmt(rpt.totAmount)}</strong>
									</td>
									<td colSpan={3} />
									<td style={{ textAlign: "right" }}>
										<strong>{fmt(rpt.totPenalty)}</strong>
									</td>
									<td style={{ textAlign: "right" }}>
										<strong>{fmt(rpt.totShortage)}</strong>
									</td>
									<td style={{ textAlign: "right" }}>
										<strong>{fmt(rpt.totInkaso)}</strong>
									</td>
									<td />
								</tr>

								<tr>
									<td colSpan={8} style={{ textAlign: "right" }}>
										<strong>TOTAL PAYMENT</strong>
									</td>
									<td style={{ textAlign: "right" }}>
										<strong>{fmt(rpt.penaltyPayment)}</strong>
									</td>
									<td style={{ textAlign: "right" }}>
										<strong>{fmt(rpt.shortagePay)}</strong>
									</td>
									<td style={{ textAlign: "right" }}>
										<strong>{fmt(rpt.inkasoPay)}</strong>
									</td>
									<td />
								</tr>
							</tbody>
						</table>

						<table>
							<tbody>
								<tr valign="top">
									<td style={{ width: "11%" }}>Supplier</td>
									<td style={{ width: "35%" }}>: {ci.suppname}</td>
									<td style={{ width: "7%" }}>Chasis</td>
									<td style={{ width: "18%" }}>: {ci.CHASIS}</td>
									<td style={{ width: "10%" }}>Blocking Date</td>
									<td style={{ width: "19%" }}>: {ci.DATEBLOKIR}</td>
								</tr>
								<tr>
									<td>BPKB A/N</td>
									<td>: {ci.BPKB_AN}</td>
									<td>Engine</td>
									<td>: {ci.ENGINE}</td>
									<td>No. Blocking</td>
									<td>: {ci.NOPOLBLOKIR}</td>
								</tr>
								<tr>
									<td>Police No.</td>
									<td>: {ci.POLICENO}</td>
									<td>Year</td>
									<td>: {ci.TAHUN}</td>
									<td>Contract Status</td>
									<td>
										: {ci.status_kontrak} {ci.JFG}
									</td>
								</tr>
								<tr>
									<td>Type</td>
									<td>: {ci.TYPE_NM}</td>
									<td>Colour</td>
									<td colSpan={3}>: {ci.COLOUR}</td>
								</tr>
								<tr>
									<td>Model</td>
									<td>: {ci.MODEL_NM}</td>
									<td />
									<td colSpan={3} />
								</tr>
							</tbody>
						</table>
					</div>
				);
			})}
		</>
	);
};

export default PrintHistoryPayment;