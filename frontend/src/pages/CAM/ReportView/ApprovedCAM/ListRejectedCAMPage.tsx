import React, { useEffect, useState } from 'react';
import api from '../../../../api/axiosInstance';
import AsOfDatePicker from '../../../../components/AsOfDatePickerComponent';
import Pagination from '../../../../helpers/Pagination';
import { DEFAULT_PAGE_LIMIT } from '../../../../constants/DefaultValue';

interface BranchOption {
	branch_cd: string;
	branch_name: string;
}

interface RejectDetailOption {
	value: string;
	label: string;
}

interface DetailRow {
	appl_no: string;
	cons_leas: string;
	rejected_date: string;
	customer_name: string;
	net_finance: number;
	rejected_by: string;
	edit_link_params: Record<string, string | number | null>;
}

interface GrandTotalBucket {
	net_finance: number;
	units: number;
}

interface GrandTotal {
	passenger_new: GrandTotalBucket;
	passenger_used: GrandTotalBucket;
	commercial_new: GrandTotalBucket;
	commercial_used: GrandTotalBucket;
	grand_total: GrandTotalBucket;
}

interface ListResponse {
	data: DetailRow[];
	total_count: number;
	page: number;
	page_size: number;
	grand_total: GrandTotal;
	disabled: boolean;
	search_branch: string;
}

const REJECTED_BY_OPTIONS = ['CMH', 'BM', 'CRH', 'Maryanna', 'Fendy.K', 'Christian.H'];
const CASCADING_ROLES = new Set(['CMH', 'CRH', 'BM']);

const PAGE_SIZE = DEFAULT_PAGE_LIMIT;

const toISO = (d: Date): string => {
	const year = d.getFullYear();
	const month = String(d.getMonth() + 1).padStart(2, '0');
	const day = String(d.getDate()).padStart(2, '0');
	return `${year}-${month}-${day}`;
};

const fmt = (n: number) => n.toLocaleString('id-ID', { maximumFractionDigits: 0 });

const buildEditHref = (params: Record<string, string | number | null>) => {
	const qs = new URLSearchParams(
		Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v ?? '')]))
	).toString();
	return `/view_main.php?${qs}`;
};

const ListRejectedCAMPage: React.FC = () => {
	const [branches, setBranches] = useState<BranchOption[]>([]);
	const [branchDisabled, setBranchDisabled] = useState(false);

	const [startDate, setStartDate] = useState<Date | null>(null);
	const [endDate, setEndDate] = useState<Date | null>(null);
	const [branchCd, setBranchCd] = useState('');
	const [rejectedBy, setRejectedBy] = useState('');
	const [rejectDetailOptions, setRejectDetailOptions] = useState<RejectDetailOption[]>([]);
	const [rejectDetail, setRejectDetail] = useState('');

	const [rows, setRows] = useState<DetailRow[]>([]);
	const [grandTotal, setGrandTotal] = useState<GrandTotal | null>(null);
	const [totalCount, setTotalCount] = useState(0);
	const [page, setPage] = useState(1);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [hasSearched, setHasSearched] = useState(false);
	const [exporting, setExporting] = useState(false);

	const totalPages = Math.ceil(totalCount / PAGE_SIZE);
	const showCascading = CASCADING_ROLES.has(rejectedBy);

	useEffect(() => {
		(async () => {
			try {
				const [branchRes, ctxRes] = await Promise.all([
					api.get<BranchOption[]>('/CAM/Approved/api/rejected-cam/branches'),
					api.get('/CAM/Approved/api/rejected-cam/context'),
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

	const handleRejectedByChange = async (value: string) => {
		setRejectedBy(value);
		setRejectDetail('');
		setRejectDetailOptions([]);
		if (!value) return;
		try {
			const res = await api.get<RejectDetailOption[]>('/CAM/Approved/api/rejected-cam/reject-detail-options', {
				params: { rejected_by: value, branch_cd: branchCd },
			});
			setRejectDetailOptions(res.data);
			if (!CASCADING_ROLES.has(value) && res.data.length === 1) {
				setRejectDetail(res.data[0].value);
			}
		} catch (err) {
			console.error('Reject-detail options error:', err);
		}
	};

	const buildParams = (pageNum: number) => ({
		start_date: startDate ? toISO(startDate) : '',
		end_date: endDate ? toISO(endDate) : '',
		branch_cd_search: branchCd,
		reject_detail: rejectDetail,
		page: pageNum,
		page_size: PAGE_SIZE,
	});

	const runSearch = async (pageNum: number) => {
		if (!rejectDetail) {
			alert('Please select who rejected the CAM');
			return;
		}
		setLoading(true);
		setError(null);
		setHasSearched(true);
		try {
			const response = await api.get<ListResponse>('/CAM/Approved/api/rejected-cam/list', {
				params: buildParams(pageNum),
			});
			setRows(response.data.data);
			setGrandTotal(response.data.grand_total);
			setTotalCount(response.data.total_count);
			setPage(pageNum);
		} catch (err) {
			console.error('Rejected CAM list error:', err);
			setError('Failed to load report. Please try again.');
		} finally {
			setLoading(false);
		}
	};

	const handlePreview = () => runSearch(1);
	const handlePageChange = (nextPage: number) => runSearch(nextPage);

	const handlePrint = () => {
		if (!rejectDetail) {
			alert('Please select who rejected the CAM');
			return;
		}
		const params = new URLSearchParams(
			Object.entries(buildParams(1)).reduce((acc, [k, v]) => ({ ...acc, [k]: String(v) }), {} as Record<string, string>)
		);
		const baseURL = (api.defaults.baseURL || '').replace(/\/$/, '');
		window.open(`${baseURL}/CAM/Approved/api/rejected-cam/print?${params.toString()}`, '_blank');
	};

	const handleExport = async () => {
		if (!rejectDetail) {
			alert('Please select who rejected the CAM');
			return;
		}
		setExporting(true);
		try {
			const response = await api.get('/CAM/Approved/api/rejected-cam/export', {
				params: buildParams(1),
				responseType: 'blob',
			});
			const blob = new Blob([response.data], {
				type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
			});
			const url = window.URL.createObjectURL(blob);
			const link = document.createElement('a');
			link.href = url;
			link.download = 'ListRejectedCam.xlsx';
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

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-6xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6">
					<div className="mb-6">
						<h1 className="text-xl md:text-2xl font-bold text-gray-800">List Rejected CAM</h1>
					</div>

					<div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4 text-sm items-end">
						<div>
							<label className="text-gray-500 block mb-1">Start Rejected Date</label>
							<AsOfDatePicker label="" value={startDate} onChange={setStartDate} />
						</div>
						<div>
							<label className="text-gray-500 block mb-1">End Rejected Date</label>
							<AsOfDatePicker label="" value={endDate} onChange={setEndDate} />
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
						<div>
							<label className="text-gray-500 block mb-1">Rejected By</label>
							<div className="flex gap-2">
								<select
									value={rejectedBy}
									onChange={(e) => handleRejectedByChange(e.target.value)}
									className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
								>
									<option value="">Select</option>
									{REJECTED_BY_OPTIONS.map((opt) => (
										<option key={opt} value={opt}>{opt}</option>
									))}
								</select>
								{showCascading && (
									<select
										value={rejectDetail}
										onChange={(e) => setRejectDetail(e.target.value)}
										className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
									>
										<option value="">Select</option>
										{rejectDetailOptions.map((opt) => (
											<option key={opt.value} value={opt.value}>{opt.label}</option>
										))}
									</select>
								)}
							</div>
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

					<div className="overflow-x-auto rounded-lg border border-gray-200 mb-4">
						<table className="w-full text-sm border-collapse">
							<thead>
								<tr className="bg-gray-100 text-gray-700">
									<th className="border border-gray-300 px-2 py-2">Rejected Date</th>
									<th className="border border-gray-300 px-2 py-2">CAM No.</th>
									<th className="border border-gray-300 px-2 py-2">Customer Name</th>
									<th className="border border-gray-300 px-2 py-2">Net Finance</th>
									<th className="border border-gray-300 px-2 py-2">Rejected By</th>
								</tr>
							</thead>
							<tbody>
								{loading ? (
									<tr>
										<td colSpan={5} className="py-10 text-center">
											<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto" />
										</td>
									</tr>
								) : !hasSearched ? (
									<tr>
										<td colSpan={5} className="border border-gray-300 px-2 py-8 text-center text-gray-400">
											Choose who rejected the CAM (and optionally a period/branch), then click Preview.
										</td>
									</tr>
								) : rows.length === 0 ? (
									<tr>
										<td colSpan={5} className="border border-gray-300 px-2 py-4 text-center text-red-600 font-bold">
											Data Not Found
										</td>
									</tr>
								) : (
									rows.map((row) => (
										<tr key={row.appl_no} className="odd:bg-gray-50">
											<td className="border border-gray-300 px-2 py-1">{row.rejected_date}</td>
											<td className="border border-gray-300 px-2 py-1">
												<a href={buildEditHref(row.edit_link_params)} target="_parent" className="text-blue-600 hover:underline">
													{row.cons_leas} - {row.appl_no}
												</a>
											</td>
											<td className="border border-gray-300 px-2 py-1">{row.customer_name}</td>
											<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.net_finance)}</td>
											<td className="border border-gray-300 px-2 py-1">{row.rejected_by}</td>
										</tr>
									))
								)}
							</tbody>
						</table>
					</div>

					{!loading && totalCount > PAGE_SIZE && (
						<Pagination
							page={page}
							totalPages={totalPages}
							onPageChange={handlePageChange}
							totalItems={totalCount}
							itemsPerPage={PAGE_SIZE}
							className="mb-6"
						/>
					)}

					{grandTotal && hasSearched && (
						<div className="max-w-lg">
							<div className="text-sm font-semibold mb-2 underline">
								Grand Total* (based on latest revised CAM, if any):
							</div>
							<div className="overflow-x-auto rounded-lg border border-gray-200">
								<table className="w-full text-sm border-collapse">
									<thead>
										<tr className="bg-gray-100 text-gray-700">
											<th className="border border-gray-300 px-2 py-2">Type</th>
											<th className="border border-gray-300 px-2 py-2">Condition</th>
											<th className="border border-gray-300 px-2 py-2">Net Finance</th>
											<th className="border border-gray-300 px-2 py-2">Units</th>
										</tr>
									</thead>
									<tbody>
										<tr>
											<td className="border border-gray-300 px-2 py-1">Passenger</td>
											<td className="border border-gray-300 px-2 py-1">New</td>
											<td className="border border-gray-300 px-2 py-1 text-right">{fmt(grandTotal.passenger_new.net_finance)}</td>
											<td className="border border-gray-300 px-2 py-1 text-right">{grandTotal.passenger_new.units}</td>
										</tr>
										<tr>
											<td className="border border-gray-300 px-2 py-1">Passenger</td>
											<td className="border border-gray-300 px-2 py-1">Used</td>
											<td className="border border-gray-300 px-2 py-1 text-right">{fmt(grandTotal.passenger_used.net_finance)}</td>
											<td className="border border-gray-300 px-2 py-1 text-right">{grandTotal.passenger_used.units}</td>
										</tr>
										<tr>
											<td className="border border-gray-300 px-2 py-1">Commercial</td>
											<td className="border border-gray-300 px-2 py-1">New</td>
											<td className="border border-gray-300 px-2 py-1 text-right">{fmt(grandTotal.commercial_new.net_finance)}</td>
											<td className="border border-gray-300 px-2 py-1 text-right">{grandTotal.commercial_new.units}</td>
										</tr>
										<tr>
											<td className="border border-gray-300 px-2 py-1">Commercial</td>
											<td className="border border-gray-300 px-2 py-1">Used</td>
											<td className="border border-gray-300 px-2 py-1 text-right">{fmt(grandTotal.commercial_used.net_finance)}</td>
											<td className="border border-gray-300 px-2 py-1 text-right">{grandTotal.commercial_used.units}</td>
										</tr>
										<tr className="bg-gray-100 font-semibold">
											<td className="border border-gray-300 px-2 py-1 text-center" colSpan={2}>Grand Total</td>
											<td className="border border-gray-300 px-2 py-1 text-right">{fmt(grandTotal.grand_total.net_finance)}</td>
											<td className="border border-gray-300 px-2 py-1 text-right">{grandTotal.grand_total.units}</td>
										</tr>
									</tbody>
								</table>
							</div>
							<div className="text-xs text-gray-400 mt-1 italic">
								*Grand Total Net Finance and Unit based on latest revised CAM (if any)
							</div>
						</div>
					)}
				</div>
			</div>
		</div>
	);
};

export default ListRejectedCAMPage;