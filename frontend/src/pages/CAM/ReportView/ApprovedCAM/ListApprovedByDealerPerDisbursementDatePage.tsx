import React, { useEffect, useState } from 'react';
import api from '../../../../api/axiosInstance';
import AsOfDatePicker from '../../../../components/AsOfDatePickerComponent';
import Pagination from '../../../../helpers/Pagination';
import { DEFAULT_PAGE_LIMIT } from '../../../../constants/DefaultValue';

interface BranchOption {
	branch_cd: string;
	branch_name: string;
}

interface DetailRow {
	appl_no: string;
	cons_leas: string;
	revision_suffix: string;
	customer_name: string;
	dealer_nickname: string;
	branch_name: string;
	disbursement_date: string;
	cmo_name: string;
	edit_link_params: Record<string, string | number | null>;
}

interface Summary {
	new_cam_count: number;
	new_cam_net_finance: number;
	revised_count: number;
	revised_net_finance: number;
	grand_count: number;
	grand_net_finance: number;
}

interface ListResponse {
	data: DetailRow[];
	total_count: number;
	page: number;
	page_size: number;
	summary: Summary;
	show_branch_column: boolean;
	show_dealer_column: boolean;
}

interface Dealer {
	supp: string;
	name: string;
	nickname: string;
	address: string;
	phone: string;
	contact: string;
}

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

const ListApprovedByDealerPerDisbursementDatePage: React.FC = () => {
	const [branches, setBranches] = useState<BranchOption[]>([]);
	const [branchRestricted, setBranchRestricted] = useState(false);

	const [startDate, setStartDate] = useState<Date | null>(null);
	const [endDate, setEndDate] = useState<Date | null>(null);
	const [branchCd, setBranchCd] = useState('000');
	const [dealerNickname, setDealerNickname] = useState('');

	const [rows, setRows] = useState<DetailRow[]>([]);
	const [summary, setSummary] = useState<Summary | null>(null);
	const [showBranchColumn, setShowBranchColumn] = useState(true);
	const [showDealerColumn, setShowDealerColumn] = useState(true);
	const [totalCount, setTotalCount] = useState(0);
	const [page, setPage] = useState(1);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [hasSearched, setHasSearched] = useState(false);
	const [exporting, setExporting] = useState(false);

	const [pickerOpen, setPickerOpen] = useState(false);
	const [pickerSearch, setPickerSearch] = useState('');
	const [pickerResults, setPickerResults] = useState<Dealer[]>([]);
	const [pickerLoading, setPickerLoading] = useState(false);

	const totalPages = Math.ceil(totalCount / PAGE_SIZE);

	useEffect(() => {
		(async () => {
			try {
				const res = await api.get('/CAM/Approved/api/cam-by-dealer/branches');
				setBranches(res.data.branches);
				setBranchRestricted(res.data.restricted);
				setBranchCd(res.data.default_branch_cd);
			} catch (err) {
				console.error('Branch list error:', err);
			}
		})();
	}, []);

	const buildParams = (pageNum: number) => ({
		start_date: startDate ? toISO(startDate) : '',
		end_date: endDate ? toISO(endDate) : '',
		branch_cd_search: branchCd,
		dealer_nickname: dealerNickname,
		page: pageNum,
		page_size: PAGE_SIZE,
	});

	const runSearch = async (pageNum: number) => {
		setLoading(true);
		setError(null);
		setHasSearched(true);
		try {
			const response = await api.get<ListResponse>('/CAM/Approved/api/cam-by-dealer/list', {
				params: buildParams(pageNum),
			});
			setRows(response.data.data);
			setSummary(response.data.summary);
			setShowBranchColumn(response.data.show_branch_column);
			setShowDealerColumn(response.data.show_dealer_column);
			setTotalCount(response.data.total_count);
			setPage(pageNum);
		} catch (err) {
			console.error('CAM by Dealer list error:', err);
			setError('Failed to load report. Please try again.');
		} finally {
			setLoading(false);
		}
	};

	const handlePreview = () => runSearch(1);
	const handlePageChange = (nextPage: number) => runSearch(nextPage);

	const handlePrint = () => {
		const params = new URLSearchParams(
			Object.entries(buildParams(1)).reduce((acc, [k, v]) => ({ ...acc, [k]: String(v) }), {} as Record<string, string>)
		);
		const baseURL = (api.defaults.baseURL || '').replace(/\/$/, '');
		window.open(`${baseURL}/CAM/Approved/api/cam-by-dealer/print?${params.toString()}`, '_blank');
	};

	const handleExport = async () => {
		setExporting(true);
		try {
			const response = await api.get('/CAM/Approved/api/cam-by-dealer/export', {
				params: buildParams(1),
				responseType: 'blob',
			});
			const blob = new Blob([response.data], {
				type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
			});
			const url = window.URL.createObjectURL(blob);
			const link = document.createElement('a');
			link.href = url;
			link.download = 'CamByDealer.xlsx';
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

	const openPicker = () => {
		setPickerSearch('');
		setPickerResults([]);
		setPickerOpen(true);
		runPickerSearch('');
	};

	const runPickerSearch = async (search: string = pickerSearch) => {
		setPickerLoading(true);
		try {
			const res = await api.get<{ data: Dealer[] }>('/CAM/Approved/api/cam-by-dealer/dealers', {
				params: { search, branch_cd: branchCd },
			});
			setPickerResults(res.data.data);
		} catch (err) {
			console.error('Dealer picker error:', err);
		} finally {
			setPickerLoading(false);
		}
	};

	const selectDealer = (dealer: Dealer) => {
		setDealerNickname(dealer.nickname);
		setPickerOpen(false);
	};

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-6xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6">
					<div className="mb-6">
						<h1 className="text-xl md:text-2xl font-bold text-gray-800">
							List Approved by Dealer per Disbursement Date
						</h1>
					</div>

					<div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4 text-sm items-end">
						<div>
							<label className="text-gray-500 block mb-1">Start Disbursement Date</label>
							<AsOfDatePicker label="" value={startDate} onChange={setStartDate} />
						</div>
						<div>
							<label className="text-gray-500 block mb-1">End Disbursement Date</label>
							<AsOfDatePicker label="" value={endDate} onChange={setEndDate} />
						</div>
						<div>
							<label className="text-gray-500 block mb-1">Branch</label>
							<select
								value={branchCd}
								onChange={(e) => setBranchCd(e.target.value)}
								disabled={branchRestricted}
								className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none disabled:bg-gray-100"
							>
								{!branchRestricted && <option value="000">All Branches</option>}
								{branches.map((b) => (
									<option key={b.branch_cd} value={b.branch_cd}>
										{b.branch_name}
									</option>
								))}
							</select>
						</div>
						<div>
							<label className="text-gray-500 block mb-1">
								<button onClick={openPicker} className="text-blue-600 hover:underline">
									Dealer Nickname
								</button>
							</label>
							<input
								type="text"
								value={dealerNickname}
								readOnly
								onClick={openPicker}
								placeholder="Click to search"
								className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm bg-gray-50 cursor-pointer"
							/>
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
									<th className="border border-gray-300 px-2 py-2">No.</th>
									<th className="border border-gray-300 px-2 py-2">CAM No.</th>
									<th className="border border-gray-300 px-2 py-2">Customer Name</th>
									{showDealerColumn && <th className="border border-gray-300 px-2 py-2">Dealer Nickname</th>}
									{showBranchColumn && <th className="border border-gray-300 px-2 py-2">Branch</th>}
									<th className="border border-gray-300 px-2 py-2">Disbursement Date</th>
									<th className="border border-gray-300 px-2 py-2">CMO</th>
								</tr>
							</thead>
							<tbody>
								{loading ? (
									<tr>
										<td colSpan={7} className="py-10 text-center">
											<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto" />
										</td>
									</tr>
								) : !hasSearched ? (
									<tr>
										<td colSpan={7} className="border border-gray-300 px-2 py-8 text-center text-gray-400">
											Choose your filters and click Preview.
										</td>
									</tr>
								) : rows.length === 0 ? (
									<tr>
										<td colSpan={7} className="border border-gray-300 px-2 py-4 text-center text-red-600 font-bold">
											Data Not Found
										</td>
									</tr>
								) : (
									rows.map((row, idx) => (
										<tr key={row.appl_no} className="odd:bg-gray-50">
											<td className="border border-gray-300 px-2 py-1 text-center">
												{(page - 1) * PAGE_SIZE + idx + 1}
											</td>
											<td className="border border-gray-300 px-2 py-1">
												<a href={buildEditHref(row.edit_link_params)} target="_parent" className="text-blue-600 hover:underline">
													{row.cons_leas} - {row.appl_no}{row.revision_suffix}
												</a>
											</td>
											<td className="border border-gray-300 px-2 py-1">{row.customer_name}</td>
											{showDealerColumn && <td className="border border-gray-300 px-2 py-1">{row.dealer_nickname}</td>}
											{showBranchColumn && <td className="border border-gray-300 px-2 py-1">{row.branch_name}</td>}
											<td className="border border-gray-300 px-2 py-1">{row.disbursement_date}</td>
											<td className="border border-gray-300 px-2 py-1">{row.cmo_name}</td>
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

					{summary && hasSearched && (
						<table className="text-sm">
							<tbody>
								<tr>
									<td className="pr-4 py-1">New CAM</td>
									<td className="pr-8 py-1">= {fmt(summary.new_cam_count)}</td>
									<td className="pr-4 py-1">Net Finance</td>
									<td className="py-1">= {fmt(summary.new_cam_net_finance)}</td>
								</tr>
								<tr>
									<td className="pr-4 py-1">Revisi</td>
									<td className="pr-8 py-1">= {fmt(summary.revised_count)}</td>
									<td className="pr-4 py-1">Net Finance</td>
									<td className="py-1">= {fmt(summary.revised_net_finance)}</td>
								</tr>
								<tr className="font-semibold">
									<td className="pr-4 py-1">Total</td>
									<td className="pr-8 py-1">= {fmt(summary.grand_count)}</td>
									<td className="pr-4 py-1">Total Net Finance</td>
									<td className="py-1">= {fmt(summary.grand_net_finance)}</td>
								</tr>
							</tbody>
						</table>
					)}
				</div>
			</div>

			{pickerOpen && (
				<div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
					<div className="bg-white rounded-2xl shadow-xl w-full max-w-3xl max-h-[80vh] overflow-hidden flex flex-col">
						<div className="flex justify-between items-center p-4 border-b">
							<h3 className="font-bold text-gray-800">List Dealer</h3>
							<button onClick={() => setPickerOpen(false)} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">
								×
							</button>
						</div>
						<div className="p-4 border-b flex gap-2">
							<input
								type="text"
								value={pickerSearch}
								onChange={(e) => setPickerSearch(e.target.value)}
								onKeyDown={(e) => e.key === 'Enter' && runPickerSearch()}
								placeholder="Search by nickname"
								className="flex-1 px-3 py-2 rounded-lg border border-gray-300 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
							/>
							<button
								onClick={() => runPickerSearch()}
								className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
							>
								Search
							</button>
						</div>
						<div className="overflow-y-auto flex-grow">
							{pickerLoading ? (
								<div className="flex justify-center py-10">
									<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
								</div>
							) : (
								<table className="w-full text-sm">
									<thead className="bg-gray-50 sticky top-0">
										<tr>
											<th className="py-2 px-3 text-left text-xs font-medium text-gray-500 uppercase">Dealer Code</th>
											<th className="py-2 px-3 text-left text-xs font-medium text-gray-500 uppercase">Dealer Name</th>
											<th className="py-2 px-3 text-left text-xs font-medium text-gray-500 uppercase">Nickname</th>
											<th className="py-2 px-3 text-left text-xs font-medium text-gray-500 uppercase">Address</th>
											<th className="py-2 px-3 text-left text-xs font-medium text-gray-500 uppercase">Phone</th>
											<th className="py-2 px-3 text-left text-xs font-medium text-gray-500 uppercase">Contact</th>
										</tr>
									</thead>
									<tbody className="divide-y divide-gray-100">
										{pickerResults.map((d) => (
											<tr key={d.supp} className="hover:bg-gray-50 cursor-pointer transition-colors" onClick={() => selectDealer(d)}>
												<td className="py-2 px-3 text-blue-600 font-medium">{d.supp}</td>
												<td className="py-2 px-3">{d.name}</td>
												<td className="py-2 px-3">{d.nickname}</td>
												<td className="py-2 px-3 text-gray-500">{d.address}</td>
												<td className="py-2 px-3 text-gray-500">{d.phone}</td>
												<td className="py-2 px-3 text-gray-500">{d.contact}</td>
											</tr>
										))}
										{pickerResults.length === 0 && (
											<tr><td colSpan={6} className="py-8 text-center text-gray-400 text-sm">No dealers found.</td></tr>
										)}
									</tbody>
								</table>
							)}
						</div>
					</div>
				</div>
			)}
		</div>
	);
};

export default ListApprovedByDealerPerDisbursementDatePage;