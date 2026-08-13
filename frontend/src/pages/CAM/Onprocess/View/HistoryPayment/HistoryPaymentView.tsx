import React, { useEffect, useState, useCallback } from 'react';
import api from '../../../../../api/axiosInstance';
import Pagination from '../../../../../helpers/Pagination';
import type { CamCtx } from '../CamViewTabs';
import { DEFAULT_PAGE_LIMIT } from '../../../../../constants/DefaultValue';

interface HistoryRow {
	no: number;
	lease_no: string;
	lessee_no: string;
	status: string;
	term_paid: number | null;
	term_total: number | null;
	reject_count: number;
	disbursement_date: string;
}

interface HistoryResponse {
	total: number;
	page: number;
	limit: number;
	rows: HistoryRow[];
}

interface ContractInfo {
	LESSEE_NO: string; trans_code: string; LESSEE_NM: string;
	ADDRESS: string; PHONE1: string; PHONE2: string; PHONE3: string;
	BPKB_AN: string; POLICENO: string; CHASIS: string; ENGINE: string;
	TAHUN: string; COLOUR: string; suppname: string; TYPE_NM: string;
	MODEL_NM: string; BRANCH_NAME: string; DATEBLOKIR: string;
	NOPOLBLOKIR: string; status_kontrak: string; JFG: string;
}

interface PaymentRow {
	girono: string; girodt: string; payment: string; bank: string;
	nominal: number; period: string; penalty: number; Shortage: number;
	inkaso: number; status: string | null; reject_description: string;
	penalty_payment: number; ShortagePay: number; InkasoPay: number;
}

interface LeaseReport {
	leaseNo: string;
	contractInfo: ContractInfo;
	payments: PaymentRow[];
	totAmount: number; totPenalty: number; totShortage: number; totInkaso: number;
	penaltyPayment: number; shortagePay: number; inkasoPay: number;
}

const LIMIT = DEFAULT_PAGE_LIMIT;

const fmt = (n: number) => (n ? n.toLocaleString('id-ID') : '0');
const todayLong = () => new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'long', year: 'numeric' });
const todayShort = () => new Date().toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: '2-digit' });

function buildLeaseReport(
	leaseNo: string,
	data: { contractInfo: ContractInfo; payments: PaymentRow[] }
): LeaseReport {
	let totAmount = 0, totPenalty = 0, totShortage = 0, totInkaso = 0;
	let penaltyPayment = 0, shortagePay = 0, inkasoPay = 0;
	data.payments.forEach((row, idx) => {
		if (!String(row.period ?? '').includes('*')) totAmount += row.nominal ?? 0;
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
		leaseNo, contractInfo: data.contractInfo, payments: data.payments,
		totAmount, totPenalty, totShortage, totInkaso, penaltyPayment, shortagePay, inkasoPay
	};
}

function PrintPreview({ report, onClose }: { report: LeaseReport; onClose: () => void }) {
	const ci = report.contractInfo;
	let prevGiro = '';
	let rowNum = 0;
	const td: React.CSSProperties = { border: '1px solid #000', padding: '2px 4px' };

	return (
		<>
			<style>{`
				@media print {
					.hp-no-print { display: none !important; }
					.hp-print-area { background: white !important; padding: 0 !important; }
					.hp-page { box-shadow: none !important; margin: 0 !important; padding: 12px !important; max-width: 100% !important; }
				}
      `}</style>

			<div className="hp-no-print sticky top-0 z-10 bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between shadow-sm">
				<button
					onClick={onClose}
					className="flex items-center gap-2 px-4 py-2 text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition font-medium"
				>
					<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
					</svg>
					Close
				</button>

				<span className="text-sm text-gray-500 font-medium">
					{report.leaseNo} — Customer History Payment Report
				</span>

				<button
					onClick={() => window.print()}
					className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition font-medium shadow"
				>
					<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
							d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" />
					</svg>
					Print
				</button>
			</div>

			<div className="hp-print-area bg-gray-100 min-h-screen py-6 px-4">
				<div
					className="hp-page bg-white mx-auto p-6 shadow-md"
					style={{ maxWidth: 1050, fontFamily: 'Tahoma, sans-serif', fontSize: 12 }}
				>
					<table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 4 }}>
						<tbody>
							<tr>
								<td style={{ width: '76%' }}>{ci.BRANCH_NAME} Branch</td>
								<td>Date: {todayShort()}</td>
							</tr>
							<tr><td /><td>Page: 1</td></tr>
						</tbody>
					</table>

					<div style={{ textAlign: 'center', marginBottom: 8 }}>
						<strong><u>CUSTOMER HISTORY PAYMENT REPORT</u><br />As of {todayLong()}</strong>
					</div>

					<table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 8 }}>
						<tbody>
							<tr>
								<td style={{ width: '15%' }}>Transaction Code</td>
								<td style={{ width: '33%' }}>: {ci.trans_code}</td>
								<td style={{ width: '10%' }} rowSpan={2}>Address</td>
								<td style={{ width: '42%' }} rowSpan={2}>: {ci.ADDRESS}</td>
							</tr>
							<tr>
								<td>Customer No.</td>
								<td>: {ci.LESSEE_NO}</td>
							</tr>
							<tr>
								<td>Contract No.</td>
								<td>: {report.leaseNo} \ {ci.LESSEE_NM}</td>
								<td>Telp</td>
								<td>: {[ci.PHONE1, ci.PHONE2, ci.PHONE3].filter(Boolean).join(', ')}</td>
							</tr>
						</tbody>
					</table>

					<table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 4 }}>
						<thead>
							<tr style={{ backgroundColor: '#f0f0f0', textAlign: 'center' }}>
								{['No.', 'Cheque No.', 'Date Due', 'Bank', 'Amount', 'OD Days', 'Sts', 'Payment Date', 'Penalty Charge', 'Shortage', 'Inkaso', 'Remark'].map(h => (
									<th key={h} style={td}>{h}</th>
								))}
							</tr>
						</thead>
						<tbody>
							{report.payments.map((row, ri) => {
								let displayGiro: string;
								if (row.girono === prevGiro) { displayGiro = ''; }
								else { displayGiro = row.girono ?? ''; prevGiro = row.girono ?? ''; }

								const isAsterisk = String(row.period ?? '').includes('*');
								if (!isAsterisk) rowNum++;

								let odDays = '';
								if (row.status != null && row.payment && row.girodt) {
									const [pd, pm, py] = row.payment.split('-').map(Number);
									const [gd, gm, gy] = row.girodt.split('-').map(Number);
									const diff = Math.floor(
										(new Date(gy, gm - 1, gd).getTime() - new Date(py, pm - 1, pd).getTime()) / 86400000
									);
									odDays = diff > 0 ? String(diff) : '0';
								}

								return (
									<tr key={ri}>
										<td style={{ ...td, textAlign: 'center' }}>{isAsterisk ? '' : rowNum}</td>
										<td style={{ ...td, textAlign: 'center' }}>{displayGiro}</td>
										<td style={{ ...td, textAlign: 'center' }}>{row.girodt}</td>
										<td style={td}>{row.bank}</td>
										<td style={{ ...td, textAlign: 'right' }}>{fmt(row.nominal)}</td>
										<td style={{ ...td, textAlign: 'center' }}>{odDays}</td>
										<td style={{ ...td, textAlign: 'center' }}>{row.status}</td>
										<td style={{ ...td, textAlign: 'center' }}>{row.payment}</td>
										<td style={{ ...td, textAlign: 'right' }}>{fmt(row.penalty)}</td>
										<td style={{ ...td, textAlign: 'right' }}>{fmt(row.Shortage)}</td>
										<td style={{ ...td, textAlign: 'right' }}>{fmt(row.inkaso * 25000)}</td>
										<td style={td}>{row.reject_description}</td>
									</tr>
								);
							})}

							<tr>
								<td colSpan={4} style={{ ...td, textAlign: 'right' }}><strong>TOTAL</strong></td>
								<td style={{ ...td, textAlign: 'right' }}><strong>{fmt(report.totAmount)}</strong></td>
								<td colSpan={3} style={td} />
								<td style={{ ...td, textAlign: 'right' }}><strong>{fmt(report.totPenalty)}</strong></td>
								<td style={{ ...td, textAlign: 'right' }}><strong>{fmt(report.totShortage)}</strong></td>
								<td style={{ ...td, textAlign: 'right' }}><strong>{fmt(report.totInkaso)}</strong></td>
								<td style={td} />
							</tr>
							<tr>
								<td colSpan={8} style={{ ...td, textAlign: 'right' }}><strong>TOTAL PAYMENT</strong></td>
								<td style={{ ...td, textAlign: 'right' }}><strong>{fmt(report.penaltyPayment)}</strong></td>
								<td style={{ ...td, textAlign: 'right' }}><strong>{fmt(report.shortagePay)}</strong></td>
								<td style={{ ...td, textAlign: 'right' }}><strong>{fmt(report.inkasoPay)}</strong></td>
								<td style={td} />
							</tr>
						</tbody>
					</table>

					<table style={{ width: '100%', borderCollapse: 'collapse' }}>
						<tbody>
							<tr>
								<td style={{ width: '11%' }}>Supplier</td>
								<td style={{ width: '35%' }}>: {ci.suppname}</td>
								<td style={{ width: '7%' }}>Chasis</td>
								<td style={{ width: '18%' }}>: {ci.CHASIS}</td>
								<td style={{ width: '10%' }}>Blocking Date</td>
								<td style={{ width: '19%' }}>: {ci.DATEBLOKIR}</td>
							</tr>
							<tr>
								<td>BPKB A/N</td><td>: {ci.BPKB_AN}</td>
								<td>Engine</td><td>: {ci.ENGINE}</td>
								<td>No. Blocking</td><td>: {ci.NOPOLBLOKIR}</td>
							</tr>
							<tr>
								<td>Police No.</td><td>: {ci.POLICENO}</td>
								<td>Year</td><td>: {ci.TAHUN}</td>
								<td>Contract Status</td><td>: {ci.status_kontrak} {ci.JFG}</td>
							</tr>
							<tr>
								<td>Type</td><td>: {ci.TYPE_NM}</td>
								<td>Colour</td><td colSpan={3}>: {ci.COLOUR}</td>
							</tr>
							<tr>
								<td>Model</td><td>: {ci.MODEL_NM}</td>
								<td /><td colSpan={3} />
							</tr>
						</tbody>
					</table>
				</div>
			</div>
		</>
	);
}

function ReportModal({ leaseNo, onClose }: { leaseNo: string; onClose: () => void }) {
	const [report, setReport] = useState<LeaseReport | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
		window.addEventListener('keydown', handler);
		return () => window.removeEventListener('keydown', handler);
	}, [onClose]);

	useEffect(() => {
		let active = true;
		setLoading(true);
		setError(null);
		api
			.get('/HistoryPayment/api/history-payment/print', { params: { lease_no: leaseNo } })
			.then(({ data }: { data: { contractInfo: ContractInfo; payments: PaymentRow[] } }) => {
				if (active) setReport(buildLeaseReport(leaseNo, data));
			})
			.catch(() => { if (active) setError('Could not load payment history for this contract.'); })
			.finally(() => { if (active) setLoading(false); });
		return () => { active = false; };
	}, [leaseNo]);

	return (
		<div className="fixed inset-0 z-50 bg-white overflow-auto" role="dialog" aria-modal="true">
			{loading && (
				<div className="flex flex-col items-center justify-center min-h-screen gap-3 text-slate-500">
					<svg className="animate-spin h-8 w-8 text-blue-600" fill="none" viewBox="0 0 24 24">
						<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
						<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
					</svg>
					<span className="text-sm">Loading payment history…</span>
				</div>
			)}
			{error && (
				<div className="flex flex-col items-center justify-center min-h-screen gap-4 p-8">
					<p className="text-red-600 text-center">{error}</p>
					<button
						onClick={onClose}
						className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-gray-700 font-medium transition"
					>
						Close
					</button>
				</div>
			)}
			{!loading && !error && report && (
				<PrintPreview report={report} onClose={onClose} />
			)}
		</div>
	);
}

function NoDataRow() {
	return (
		<tr>
			<td colSpan={6} className="py-10 text-center">
				<span className="text-2xl font-bold text-red-600">NO DATA</span>
			</td>
		</tr>
	);
}

function HistoryTable({
	rows,
	onContractClick,
}: {
	rows: HistoryRow[];
	onContractClick: (row: HistoryRow) => void;
}) {
	return (
		<table className="w-full text-sm">
			<thead>
				<tr className="bg-slate-100 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
					<th className="px-3 py-2 w-12">No.</th>
					<th className="px-3 py-2">Contract No.</th>
					<th className="px-3 py-2">Status</th>
					<th className="px-3 py-2">Term</th>
					<th className="px-3 py-2">Time of Reject</th>
					<th className="px-3 py-2">Disbursement Date</th>
				</tr>
			</thead>
			<tbody>
				{rows.length === 0 ? (
					<NoDataRow />
				) : (
					rows.map((r, idx) => (
						<tr key={`${r.lease_no}-${r.no}`} className={idx % 2 === 0 ? 'bg-slate-50' : 'bg-white'}>
							<td className="px-3 py-2">{r.no}</td>
							<td className="px-3 py-2">
								<button
									onClick={() => onContractClick(r)}
									className="font-medium text-blue-600 hover:underline focus:outline-none"
								>
									{r.lease_no}
								</button>
							</td>
							<td className="px-3 py-2">{r.status}</td>
							<td className="px-3 py-2">{r.term_paid ?? '-'} of {r.term_total ?? '-'}</td>
							<td className="px-3 py-2">{r.reject_count}</td>
							<td className="px-3 py-2">{r.disbursement_date}</td>
						</tr>
					))
				)}
			</tbody>
		</table>
	);
}

function HistorySection({
	title, endpoint, ctx, needsApplno, onContractClick,
}: {
	title: string; endpoint: string; ctx: CamCtx;
	needsApplno?: boolean; onContractClick: (row: HistoryRow) => void;
}) {
	const [page, setPage] = useState(1);
	const [data, setData] = useState<HistoryResponse | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		let active = true;
		setLoading(true);
		setError(null);
		const params: Record<string, string | number> = { apless: ctx.apless, page, limit: LIMIT };
		if (needsApplno) params.applno = ctx.applno;
		api
			.get(endpoint, { params })
			.then((res) => { if (active) setData(res.data); })
			.catch(() => { if (active) setError('Failed to load payment history.'); })
			.finally(() => { if (active) setLoading(false); });
		return () => { active = false; };
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [endpoint, ctx.apless, ctx.applno, page]);

	const totalPages = data ? Math.max(1, Math.ceil(data.total / LIMIT)) : 1;

	return (
		<div className="mb-4 overflow-hidden rounded-2xl bg-white shadow">
			<div className="border-b border-slate-100 bg-slate-50 px-5 py-3">
				<h2 className="text-sm font-semibold text-slate-700">{title}</h2>
			</div>
			<div className="p-2">
				{loading ? (
					<div className="p-8 text-center text-sm text-slate-500">Loading…</div>
				) : error || !data ? (
					<div className="p-8 text-center text-sm text-red-500">{error || 'No data found.'}</div>
				) : (
					<>
						<HistoryTable rows={data.rows} onContractClick={onContractClick} />
						{data.total > 0 && (
							<div className="px-3 py-2">
								<Pagination
									page={page}
									totalPages={totalPages}
									onPageChange={setPage}
									totalItems={data.total}
									itemsPerPage={LIMIT}
								/>
							</div>
						)}
					</>
				)}
			</div>
		</div>
	);
}

export default function HistoryPaymentView({ ctx }: { ctx: CamCtx }) {
	const [activeLeaseNo, setActiveLeaseNo] = useState<string | null>(null);

	const handleContractClick = useCallback((row: HistoryRow) => {
		setActiveLeaseNo(row.lease_no);
	}, []);

	const handleClose = useCallback(() => setActiveLeaseNo(null), []);

	return (
		<>
			<HistorySection
				title="List of Contract"
				endpoint="/CAM/View/api/history-payment/contract"
				ctx={ctx}
				needsApplno
				onContractClick={handleContractClick}
			/>
			<HistorySection
				title="Group"
				endpoint="/CAM/View/api/history-payment/group"
				ctx={ctx}
				onContractClick={handleContractClick}
			/>

			{activeLeaseNo && (
				<ReportModal leaseNo={activeLeaseNo} onClose={handleClose} />
			)}
		</>
	);
}