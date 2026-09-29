import React, { useEffect, useState } from 'react';
import api from '../../../../api/axiosInstance';
import AsOfDatePicker from '../../../../components/AsOfDatePickerComponent';

interface BranchOption {
	branch_cd: string;
	branch_name: string;
}

interface DetailRow {
	no: number;
	cam_no: string;
	appl_no: string;
	customer_name: string;
	brand_type: string;
	net_finance: number;
	irr: number;
	tenor: number;
	approval_date: string;
	cmo: string;
	approved_by: string;
	is_revision: boolean;
}

interface SegmentMetrics {
	net_finance: number;
	units: number;
	avg_irr: number;
	avg_tenor: number;
	avg_net_finance: number;
}

interface GroupTotals {
	passenger_new: SegmentMetrics;
	passenger_used: SegmentMetrics;
	commercial_new: SegmentMetrics;
	commercial_used: SegmentMetrics;
	total: SegmentMetrics;
}

interface GrandTotals {
	sl: GroupTotals;
	if: GroupTotals;
	grand_total: SegmentMetrics;
}

interface ListResponse {
	rows: DetailRow[];
	total_count: number;
	page: number;
	page_size: number;
	total_pages: number;
	grand_totals: GrandTotals;
	period_label: string;
	disabled: boolean;
	search_branch: string;
}

interface HistoryEntry {
	date: string;
	approved_by: string;
	status: string;
	comment: string;
}

interface CamInfo {
	appl_no_display: string;
	customer_name: string;
	cmo_name: string;
	history: HistoryEntry[];
}

interface CommentsResponse {
	main: CamInfo;
	related: CamInfo[];
}

const toISO = (d: Date): string => {
	const year = d.getFullYear();
	const month = String(d.getMonth() + 1).padStart(2, '0');
	const day = String(d.getDate()).padStart(2, '0');
	return `${year}-${month}-${day}`;
};

const fmt = (n: number) => (n ?? 0).toLocaleString('id-ID', { maximumFractionDigits: 0 });

const SEGMENT_ROWS: { key: keyof Omit<GroupTotals, 'total'>; type: string; condition: string }[] = [
	{ key: 'passenger_new', type: 'Passenger', condition: 'New' },
	{ key: 'passenger_used', type: 'Passenger', condition: 'Used' },
	{ key: 'commercial_new', type: 'Commercial', condition: 'New' },
	{ key: 'commercial_used', type: 'Commercial', condition: 'Used' },
];

const GrandTotalGroup: React.FC<{ label: string; group: GroupTotals }> = ({ label, group }) => (
	<>
		{SEGMENT_ROWS.map((seg, idx) => {
			const metrics = group[seg.key];
			return (
				<tr key={seg.key} className="odd:bg-gray-50">
					{idx === 0 && (
						<td rowSpan={5} className="border border-gray-300 px-2 py-1 font-medium align-top">
							{label}
						</td>
					)}
					<td className="border border-gray-300 px-2 py-1">{seg.type}</td>
					<td className="border border-gray-300 px-2 py-1">{seg.condition}</td>
					<td className="border border-gray-300 px-2 py-1 text-right">{fmt(metrics.net_finance)}</td>
					<td className="border border-gray-300 px-2 py-1 text-right">{fmt(metrics.units)}</td>
					<td className="border border-gray-300 px-2 py-1 text-right">{metrics.avg_irr}</td>
					<td className="border border-gray-300 px-2 py-1 text-right">{fmt(metrics.avg_tenor)}</td>
					<td className="border border-gray-300 px-2 py-1 text-right">{fmt(metrics.avg_net_finance)}</td>
				</tr>
			);
		})}
		<tr className="bg-gray-100 font-semibold">
			<td colSpan={2} className="border border-gray-300 px-2 py-1 text-right">
				Grand Total {label}
			</td>
			<td className="border border-gray-300 px-2 py-1 text-right">{fmt(group.total.net_finance)}</td>
			<td className="border border-gray-300 px-2 py-1 text-right">{fmt(group.total.units)}</td>
			<td className="border border-gray-300 px-2 py-1 text-right">{group.total.avg_irr}</td>
			<td className="border border-gray-300 px-2 py-1 text-right">{fmt(group.total.avg_tenor)}</td>
			<td className="border border-gray-300 px-2 py-1 text-right">{fmt(group.total.avg_net_finance)}</td>
		</tr>
	</>
);

const CamInfoBlock: React.FC<{ info: CamInfo }> = ({ info }) => (
	<table className="w-full text-sm border-collapse mb-4">
		<tbody>
			<tr>
				<td className="w-1/5 py-1 text-gray-500">CAM No.</td>
				<td className="py-1">{info.appl_no_display}</td>
			</tr>
			<tr>
				<td className="py-1 text-gray-500">Customer Name</td>
				<td className="py-1">{info.customer_name}</td>
			</tr>
			<tr>
				<td className="py-1 text-gray-500">CMO Name</td>
				<td className="py-1">{info.cmo_name}</td>
			</tr>
			<tr>
				<td colSpan={2} className="pt-2">
					<table className="w-full text-sm border-collapse">
						<thead>
							<tr className="bg-gray-100">
								<th className="border border-gray-300 px-2 py-1 text-left w-1/4">Date</th>
								<th className="border border-gray-300 px-2 py-1 text-left w-2/5">Approval By</th>
								<th className="border border-gray-300 px-2 py-1 text-left">CAM Status</th>
							</tr>
						</thead>
						<tbody>
							{info.history.length === 0 ? (
								<tr>
									<td colSpan={3} className="border border-gray-300 px-2 py-2 text-center text-gray-400">
										No history found.
									</td>
								</tr>
							) : (
								info.history.map((h, idx) => (
									<React.Fragment key={idx}>
										<tr className={idx % 2 === 0 ? 'bg-gray-50' : ''}>
											<td className="border border-gray-300 px-2 py-1" rowSpan={2}>{h.date}</td>
											<td className="border border-gray-300 px-2 py-1">{h.approved_by}</td>
											<td className="border border-gray-300 px-2 py-1">{h.status}</td>
										</tr>
										<tr className={idx % 2 === 0 ? 'bg-gray-50' : ''}>
											<td className="border border-gray-300 px-2 py-1" colSpan={2}>Comment : {h.comment}</td>
										</tr>
									</React.Fragment>
								))
							)}
						</tbody>
					</table>
				</td>
			</tr>
		</tbody>
	</table>
);

const ListCAMByApprovalDatePage: React.FC = () => {
	const [branches, setBranches] = useState<BranchOption[]>([]);
	const [branchDisabled, setBranchDisabled] = useState(false);

	const [startDate, setStartDate] = useState<Date | null>(null);
	const [endDate, setEndDate] = useState<Date | null>(null);
	const [lesseeNm, setLesseeNm] = useState('');
	const [branchCd, setBranchCd] = useState('');

	const [rows, setRows] = useState<DetailRow[]>([]);
	const [grandTotals, setGrandTotals] = useState<GrandTotals | null>(null);
	const [periodLabel, setPeriodLabel] = useState('');
	const [page, setPage] = useState(1);
	const [totalPages, setTotalPages] = useState(1);
	const [totalCount, setTotalCount] = useState(0);

	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [hasSearched, setHasSearched] = useState(false);
	const [exporting, setExporting] = useState(false);

	const [commentsOpen, setCommentsOpen] = useState(false);
	const [commentsLoading, setCommentsLoading] = useState(false);
	const [comments, setComments] = useState<CommentsResponse | null>(null);

	useEffect(() => {
		(async () => {
			try {
				const [branchRes, ctxRes] = await Promise.all([
					api.get<BranchOption[]>('/CAM/Approved/api/cam-by-app-date/branches'),
					api.get('/CAM/Approved/api/cam-by-app-date/context'),
				]);
				setBranches(branchRes.data);
				setBranchDisabled(ctxRes.data.disabled);
				if (ctxRes.data.disabled) {
					setBranchCd(ctxRes.data.forced_branch_cd);
				}
			} catch (err) {
				console.error('Context load error:', err);
			}
		})();
	}, []);

	const isFilterEmpty = () => !startDate && !endDate && !lesseeNm.trim() && !branchCd;

	const buildParams = (pageOverride?: number) => ({
		start_date: startDate ? toISO(startDate) : '',
		end_date: endDate ? toISO(endDate) : '',
		lessee_nm: lesseeNm,
		branch_cd: branchCd,
		page: pageOverride ?? page,
	});

	const fetchPage = async (pageNum: number) => {
		setLoading(true);
		setError(null);
		try {
			const response = await api.get<ListResponse>('/CAM/Approved/api/cam-by-app-date/list', {
				params: buildParams(pageNum),
			});
			setRows(response.data.rows);
			setGrandTotals(response.data.grand_totals);
			setPeriodLabel(response.data.period_label);
			setPage(response.data.page);
			setTotalPages(response.data.total_pages);
			setTotalCount(response.data.total_count);
		} catch (err) {
			console.error('CAM by Approval Date list error:', err);
			setError('Failed to load report. Please try again.');
		} finally {
			setLoading(false);
		}
	};

	const handlePreview = async () => {
		if (isFilterEmpty()) {
			alert('Please Fill The Field');
			return;
		}
		setHasSearched(true);
		await fetchPage(1);
	};

	const handlePageChange = (newPage: number) => {
		if (newPage < 1 || newPage > totalPages || newPage === page) return;
		fetchPage(newPage);
	};

	const toQueryString = (obj: Record<string, string | number>): URLSearchParams => {
		const stringEntries: Record<string, string> = {};
		Object.entries(obj).forEach(([key, value]) => {
			stringEntries[key] = String(value);
		});
		return new URLSearchParams(stringEntries);
	};

	const handlePrint = () => {
		if (isFilterEmpty()) {
			alert('Please Fill The Field');
			return;
		}
		const params = toQueryString(buildParams(1));
		const baseURL = (api.defaults.baseURL || '').replace(/\/$/, '');
		window.open(`${baseURL}/CAM/Approved/api/cam-by-app-date/print?${params.toString()}`, '_blank');
	};

	const handleExport = async () => {
		if (isFilterEmpty()) {
			alert('Please Fill The Field');
			return;
		}
		setExporting(true);
		try {
			const response = await api.get('/CAM/Approved/api/cam-by-app-date/export', {
				params: buildParams(1),
				responseType: 'blob',
			});
			const blob = new Blob([response.data], {
				type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
			});
			const url = window.URL.createObjectURL(blob);
			const link = document.createElement('a');
			link.href = url;
			link.download = 'ListCamByApprovalDate.xlsx';
			document.body.appendChild(link);
			link.click();
			document.body.removeChild(link);
			window.URL.revokeObjectURL(url);
		} catch (err) {
			console.error('Export error:', err);
			alert('Failed to export. Please try again.');
		} finally {
			setExporting(false);
		}
	};

	const openComments = async (applNo: string) => {
		setCommentsOpen(true);
		setCommentsLoading(true);
		setComments(null);
		try {
			const res = await api.get<CommentsResponse>('/CAM/Approved/api/cam-by-app-date/comments', {
				params: { appl_no: applNo },
			});
			setComments(res.data);
		} catch (err) {
			console.error('Comments load error:', err);
		} finally {
			setCommentsLoading(false);
		}
	};

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-6xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6">
					<div className="mb-6">
						<h1 className="text-xl md:text-2xl font-bold text-gray-800">List CAM by Approval Date</h1>
					</div>

					<div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4 text-sm items-end">
						<div>
							<label className="text-gray-500 block mb-1">Start Approval Date</label>
							<AsOfDatePicker label="" value={startDate} onChange={setStartDate} />
						</div>
						<div>
							<label className="text-gray-500 block mb-1">End Approval Date</label>
							<AsOfDatePicker label="" value={endDate} onChange={setEndDate} />
						</div>
						<div>
							<label className="text-gray-500 block mb-1">Customer Name</label>
							<input
								type="text"
								value={lesseeNm}
								onChange={(e) => setLesseeNm(e.target.value)}
								className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
							/>
						</div>
						<div>
							<label className="text-gray-500 block mb-1">Branch</label>
							<select
								value={branchCd}
								onChange={(e) => setBranchCd(e.target.value)}
								disabled={branchDisabled}
								className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none disabled:bg-gray-100"
							>
								<option value="">Select</option>
								{branches.map((b) => (
									<option key={b.branch_cd} value={b.branch_cd}>
										{b.branch_name}
									</option>
								))}
							</select>
						</div>
					</div>

					<div className="mb-6 flex gap-2">
						<button
							onClick={handlePreview}
							className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
						>
							Preview
						</button>
						<button
							onClick={handlePrint}
							className="bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
						>
							Print
						</button>
						<button
							onClick={handleExport}
							disabled={exporting}
							className="bg-green-600 hover:bg-green-700 disabled:bg-gray-300 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
						>
							{exporting ? 'Exporting…' : 'Export to Excel'}
						</button>
					</div>

					{error && (
						<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
							{error}
						</div>
					)}

					{loading ? (
						<div className="py-10 text-center">
							<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto" />
						</div>
					) : !hasSearched ? (
						<div className="py-10 text-center text-gray-400 text-sm">
							Choose your filters and click Preview.
						</div>
					) : (
						<>
							{totalPages > 1 && (
								<div className="flex items-center justify-between text-sm mb-3">
									<span className="text-gray-500">
										Page {page} of {totalPages} ({fmt(totalCount)} records)
									</span>
									<div className="flex gap-2">
										<button
											onClick={() => handlePageChange(page - 1)}
											disabled={page <= 1}
											className="px-3 py-1 rounded border border-gray-300 disabled:opacity-40"
										>
											Prev
										</button>
										<button
											onClick={() => handlePageChange(page + 1)}
											disabled={page >= totalPages}
											className="px-3 py-1 rounded border border-gray-300 disabled:opacity-40"
										>
											Next
										</button>
									</div>
								</div>
							)}

							<div className="overflow-x-auto rounded-lg border border-gray-200 mb-6">
								<table className="w-full text-sm border-collapse">
									<thead>
										<tr className="bg-gray-100 text-gray-700">
											<th className="border border-gray-300 px-1 py-2">No.</th>
											<th className="border border-gray-300 px-1 py-2">CAM No.</th>
											<th className="border border-gray-300 px-1 py-2">Customer Name</th>
											<th className="border border-gray-300 px-1 py-2">Brand/Type</th>
											<th className="border border-gray-300 px-1 py-2">Net Finance</th>
											<th className="border border-gray-300 px-1 py-2">%IRR</th>
											<th className="border border-gray-300 px-1 py-2">Tenor (Month)</th>
											<th className="border border-gray-300 px-1 py-2">Approval Date</th>
											<th className="border border-gray-300 px-1 py-2">CMO</th>
											<th className="border border-gray-300 px-1 py-2">Approved by</th>
											<th className="border border-gray-300 px-1 py-2">Credit Committee Comments</th>
										</tr>
									</thead>
									<tbody>
										{rows.length === 0 ? (
											<tr>
												<td colSpan={11} className="border border-gray-300 px-2 py-2 text-center text-red-600 font-bold bg-gray-100">
													Data Not Found
												</td>
											</tr>
										) : (
											rows.map((row) => (
												<tr key={row.appl_no} className="odd:bg-gray-50">
													<td className="border border-gray-300 px-1 py-1 text-center">{row.no}</td>
													<td className="border border-gray-300 px-1 py-1">
														{row.cam_no}
														{row.is_revision && (
															<span className="ml-1 inline-block px-1.5 py-0.5 rounded text-[10px] bg-purple-100 text-purple-700">
																Revised
															</span>
														)}
													</td>
													<td className="border border-gray-300 px-1 py-1">{row.customer_name}</td>
													<td className="border border-gray-300 px-1 py-1">{row.brand_type}</td>
													<td className="border border-gray-300 px-1 py-1 text-right">{fmt(row.net_finance)}</td>
													<td className="border border-gray-300 px-1 py-1 text-right">{row.irr.toFixed(2)}</td>
													<td className="border border-gray-300 px-1 py-1 text-center">{row.tenor}</td>
													<td className="border border-gray-300 px-1 py-1">{row.approval_date}</td>
													<td className="border border-gray-300 px-1 py-1">{row.cmo}</td>
													<td className="border border-gray-300 px-1 py-1">{row.approved_by}</td>
													<td className="border border-gray-300 px-1 py-1 text-center">
														<button
															onClick={() => openComments(row.appl_no)}
															className="bg-gray-200 hover:bg-gray-300 px-2 py-1 rounded text-xs"
														>
															View
														</button>
													</td>
												</tr>
											))
										)}
									</tbody>
								</table>
							</div>

							{grandTotals && (
								<div>
									<div className="font-semibold underline mb-2 text-sm">
										Grand Total* ({periodLabel.replace('Period : ', '') || 'All Dates'}):
									</div>
									<div className="overflow-x-auto">
										<table className="text-sm border-collapse w-full max-w-4xl">
											<thead>
												<tr className="bg-gray-100">
													<th className="border border-gray-300 px-2 py-1">Contract Type</th>
													<th className="border border-gray-300 px-2 py-1">Type</th>
													<th className="border border-gray-300 px-2 py-1">Condition</th>
													<th className="border border-gray-300 px-2 py-1">Net Finance</th>
													<th className="border border-gray-300 px-2 py-1">Units</th>
													<th className="border border-gray-300 px-2 py-1">Avg. IRR</th>
													<th className="border border-gray-300 px-2 py-1">Avg. Tenor</th>
													<th className="border border-gray-300 px-2 py-1">Avg. Net Finance</th>
												</tr>
											</thead>
											<tbody>
												<GrandTotalGroup label="SL" group={grandTotals.sl} />
												<GrandTotalGroup label="IF" group={grandTotals.if} />
												<tr className="bg-gray-200 font-bold">
													<td colSpan={3} className="border border-gray-300 px-2 py-1 text-right">
														Grand Total
													</td>
													<td className="border border-gray-300 px-2 py-1 text-right">{fmt(grandTotals.grand_total.net_finance)}</td>
													<td className="border border-gray-300 px-2 py-1 text-right">{fmt(grandTotals.grand_total.units)}</td>
													<td className="border border-gray-300 px-2 py-1 text-right">{grandTotals.grand_total.avg_irr}</td>
													<td className="border border-gray-300 px-2 py-1 text-right">{fmt(grandTotals.grand_total.avg_tenor)}</td>
													<td className="border border-gray-300 px-2 py-1 text-right">{fmt(grandTotals.grand_total.avg_net_finance)}</td>
												</tr>
											</tbody>
										</table>
									</div>
									<div className="text-xs text-gray-400 italic mt-2">
										*Grand Total Net Finance and Unit based on latest revised CAM (if any)
									</div>
								</div>
							)}
						</>
					)}
				</div>
			</div>

			{commentsOpen && (
				<div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
					<div className="bg-white rounded-2xl shadow-xl w-full max-w-3xl max-h-[85vh] overflow-hidden flex flex-col">
						<div className="flex justify-between items-center p-4 border-b">
							<h3 className="font-bold text-gray-800">Credit Committee Comments</h3>
							<button onClick={() => setCommentsOpen(false)} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">
								×
							</button>
						</div>
						<div className="p-4 overflow-y-auto flex-grow">
							{commentsLoading ? (
								<div className="flex justify-center py-10">
									<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
								</div>
							) : comments ? (
								<>
									<CamInfoBlock info={comments.main} />
									{comments.related.map((info, idx) => (
										<div key={idx} className="border border-gray-300 rounded-lg p-3 mb-3">
											<div className="text-xs text-gray-400 mb-2">Related CAM</div>
											<CamInfoBlock info={info} />
										</div>
									))}
								</>
							) : (
								<div className="text-center text-gray-400 py-10">No data.</div>
							)}
						</div>
					</div>
				</div>
			)}
		</div>
	);
};

export default ListCAMByApprovalDatePage;