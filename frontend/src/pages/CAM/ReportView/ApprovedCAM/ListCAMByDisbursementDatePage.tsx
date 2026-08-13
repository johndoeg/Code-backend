import React, { useState } from 'react';
import api from '../../../../api/axiosInstance';
import AsOfDatePicker from '../../../../components/AsOfDatePickerComponent';
import Pagination from '../../../../helpers/Pagination';
import { DEFAULT_PAGE_LIMIT } from '../../../../constants/DefaultValue';

interface BranchOption {
	branch_cd: string;
	branch_name: string;
}

interface DetailRow {
	no: number;
	appl_no: string;
	cons_leas: string;
	revision_suffix: string;
	customer_name: string;
	brand_type: string;
	net_finance: number;
	irr: number;
	selling_rate: number;
	ltv: number;
	tenor: number;
	disbursement_date: string;
	cmo: string;
	edit_link_params: Record<string, string | number>;
}

interface VehicleSummaryRow {
	type: 'detail' | 'subtotal' | 'grand_total';
	label?: string;
	cons_leas?: string;
	model?: string;
	condition?: string;
	net_finance: number;
	units: number;
	avg_irr?: number;
	avg_sell?: number;
	avg_ltv?: number;
	avg_tenor?: number;
	avg_fin?: number;
}

interface DetailResponse {
	data: DetailRow[];
	date_range_label: string;
	summary_by_vehicle: VehicleSummaryRow[];
}

interface DimensionRow {
	label: string;
	net_finance: number;
	units: number;
	avg_irr: number;
	avg_sell: number;
	avg_ltv: number;
	avg_fin: number;
	avg_tenor?: number;
	avg_tahun?: number;
	proportion?: number;
}

interface DimensionSummary {
	metric: 'tenor_and_year' | 'tenor' | 'proportion_tenor' | 'proportion_fin';
	data: DimensionRow[];
	grand_total: DimensionRow;
}

type DimensionKey = 'branch' | 'cmo' | 'tenor' | 'karoseri' | 'model' | 'cmh';

const DIMENSION_LABELS: Record<DimensionKey, string> = {
	branch: 'Branch',
	cmo: 'CMO',
	tenor: 'Tenor',
	karoseri: 'Karoseri',
	model: 'Model',
	cmh: 'CMH',
};

const PAGE_SIZE = DEFAULT_PAGE_LIMIT;

const fmt = (n: number | undefined) => (n ?? 0).toLocaleString('id-ID', { maximumFractionDigits: 0 });
const fmt2 = (n: number | undefined) => (n ?? 0).toLocaleString('id-ID', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const toISO = (d: Date): string => {
	const year = d.getFullYear();
	const month = String(d.getMonth() + 1).padStart(2, '0');
	const day = String(d.getDate()).padStart(2, '0');
	return `${year}-${month}-${day}`;
};

const ListCAMByDisbursementDatePage: React.FC = () => {
	const [branches, setBranches] = useState<BranchOption[]>([]);
	const [branchesLoaded, setBranchesLoaded] = useState(false);

	const [startDate, setStartDate] = useState<Date | null>(null);
	const [endDate, setEndDate] = useState<Date | null>(null);
	const [branch, setBranch] = useState('');
	const [excludeJf, setExcludeJf] = useState(false);

	const [activeTab, setActiveTab] = useState<'summary' | 'detail'>('summary');

	const [detail, setDetail] = useState<DetailResponse | null>(null);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const [dimension, setDimension] = useState<DimensionKey | ''>('');
	const [dimensionSummary, setDimensionSummary] = useState<DimensionSummary | null>(null);
	const [dimensionLoading, setDimensionLoading] = useState(false);

	const [page, setPage] = useState(1);
	const detailRows = detail?.data ?? [];
	const totalPages = Math.ceil(detailRows.length / PAGE_SIZE);
	const pageRows = detailRows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

	React.useEffect(() => {
		if (branchesLoaded) return;
		(async () => {
			try {
				const res = await api.get<BranchOption[]>('/CAM/Approved/api/cam-by-disbursement-date/branches');
				setBranches(res.data);
				setBranchesLoaded(true);
			} catch (err) {
				console.error('Branch list error:', err);
			}
		})();
	}, [branchesLoaded]);

	const handlePreview = async () => {
		if (!startDate && !endDate && !branch) {
			alert('Please Fill The Field');
			return;
		}
		setLoading(true);
		setError(null);
		try {
			const response = await api.get<DetailResponse>('/CAM/Approved/api/cam-by-disbursement-date/detail', {
				params: {
					branch,
					start_date: startDate ? toISO(startDate) : '',
					end_date: endDate ? toISO(endDate) : '',
					exclude_jf: excludeJf ? '1' : '0',
				},
			});
			setDetail(response.data);
			setActiveTab('summary');
			setDimension('');
			setDimensionSummary(null);
			setPage(1);
		} catch (err) {
			console.error('Detail fetch error:', err);
			setError('Failed to load report. Please try again.');
		} finally {
			setLoading(false);
		}
	};

	const handleDimensionChange = async (value: string) => {
		const dim = value as DimensionKey | '';
		setDimension(dim);
		setDimensionSummary(null);
		if (!dim) return;
		setDimensionLoading(true);
		try {
			const response = await api.get<DimensionSummary>('/CAM/Approved/api/cam-by-disbursement-date/summary', {
				params: {
					dimension: dim,
					branch,
					start_date: startDate ? toISO(startDate) : '',
					end_date: endDate ? toISO(endDate) : '',
					exclude_jf: excludeJf ? '1' : '0',
				},
			});
			setDimensionSummary(response.data);
		} catch (err) {
			console.error('Dimension summary error:', err);
		} finally {
			setDimensionLoading(false);
		}
	};

	const buildEditHref = (params: Record<string, string | number>) => {
		const qs = new URLSearchParams(
			Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v ?? '')]))
		).toString();
		return `/view_main.php?${qs}`;
	};

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-6xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6 mb-6">
					<div className="mb-6">
						<h1 className="text-xl md:text-2xl font-bold text-gray-800">List CAM by Disbursement Date</h1>
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
								value={branch}
								onChange={(e) => setBranch(e.target.value)}
								className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
							>
								<option value="">Select</option>
								{branches.map((b) => (
									<option key={b.branch_cd} value={b.branch_cd}>
										{b.branch_name}
									</option>
								))}
							</select>
						</div>
						<div className="flex items-center gap-2 pb-2">
							<input
								type="checkbox"
								id="excludeJf"
								checked={excludeJf}
								onChange={(e) => setExcludeJf(e.target.checked)}
							/>
							<label htmlFor="excludeJf" className="text-gray-600">Exclude JF Portion</label>
						</div>
					</div>

					<div className="mb-6">
						<button
							onClick={handlePreview}
							className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
						>
							Preview
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
					) : detail ? (
						<>
							<div className="flex gap-2 border-b mb-4">
								<button
									onClick={() => setActiveTab('summary')}
									className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${activeTab === 'summary' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500'
										}`}
								>
									Summary
								</button>
								<button
									onClick={() => setActiveTab('detail')}
									className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${activeTab === 'detail' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500'
										}`}
								>
									Detail
								</button>
							</div>

							{activeTab === 'detail' && (
								<>
									<div className="overflow-x-auto rounded-lg border border-gray-200">
										<table className="w-full text-sm border-collapse">
											<thead>
												<tr className="bg-gray-100 text-gray-700">
													<th className="border border-gray-300 px-2 py-2">No.</th>
													<th className="border border-gray-300 px-2 py-2">CAM No.</th>
													<th className="border border-gray-300 px-2 py-2">Customer Name</th>
													<th className="border border-gray-300 px-2 py-2">Brand/Type</th>
													<th className="border border-gray-300 px-2 py-2">Net Finance</th>
													<th className="border border-gray-300 px-2 py-2">%IRR</th>
													<th className="border border-gray-300 px-2 py-2">%Selling</th>
													<th className="border border-gray-300 px-2 py-2">%LTV</th>
													<th className="border border-gray-300 px-2 py-2">Tenor (Month)</th>
													<th className="border border-gray-300 px-2 py-2">Disbursement Date</th>
													<th className="border border-gray-300 px-2 py-2">CMO</th>
												</tr>
											</thead>
											<tbody>
												{pageRows.length === 0 ? (
													<tr>
														<td colSpan={11} className="border border-gray-300 px-2 py-8 text-center text-gray-400">
															No records found.
														</td>
													</tr>
												) : (
													pageRows.map((row) => (
														<tr key={row.appl_no} className="odd:bg-gray-50">
															<td className="border border-gray-300 px-2 py-1 text-center">{row.no}</td>
															<td className="border border-gray-300 px-2 py-1">
																<a href={buildEditHref(row.edit_link_params)} target="_parent" className="text-blue-600 hover:underline">
																	{row.cons_leas} - {row.appl_no}{row.revision_suffix}
																</a>
															</td>
															<td className="border border-gray-300 px-2 py-1">{row.customer_name}</td>
															<td className="border border-gray-300 px-2 py-1">{row.brand_type}</td>
															<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.net_finance)}</td>
															<td className="border border-gray-300 px-2 py-1 text-right">{fmt2(row.irr)}</td>
															<td className="border border-gray-300 px-2 py-1 text-right">{fmt2(row.selling_rate)}</td>
															<td className="border border-gray-300 px-2 py-1 text-right">{fmt2(row.ltv)}</td>
															<td className="border border-gray-300 px-2 py-1 text-center">{row.tenor}</td>
															<td className="border border-gray-300 px-2 py-1">{row.disbursement_date}</td>
															<td className="border border-gray-300 px-2 py-1">{row.cmo}</td>
														</tr>
													))
												)}
											</tbody>
										</table>
									</div>

									{detailRows.length > PAGE_SIZE && (
										<Pagination
											page={page}
											totalPages={totalPages}
											onPageChange={setPage}
											totalItems={detailRows.length}
											itemsPerPage={PAGE_SIZE}
											className="mt-6"
										/>
									)}
								</>
							)}

							{activeTab === 'summary' && (
								<div>
									<div className="mb-4 text-sm flex items-center gap-2">
										<span className="text-gray-600">Summary By:</span>
										<select
											value={dimension}
											onChange={(e) => handleDimensionChange(e.target.value)}
											className="px-3 py-2 rounded-lg border border-gray-300 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
										>
											<option value="">Select</option>
											{(Object.keys(DIMENSION_LABELS) as DimensionKey[]).map((k) => (
												<option key={k} value={k}>
													{DIMENSION_LABELS[k]}
												</option>
											))}
										</select>
									</div>

									{dimensionLoading && (
										<div className="py-6 text-center">
											<div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500 mx-auto" />
										</div>
									)}

									{dimensionSummary && (
										<div className="overflow-x-auto rounded-lg border border-gray-200 mb-6">
											<table className="w-full text-sm border-collapse">
												<thead>
													<tr className="bg-gray-100 text-gray-700">
														<th className="border border-gray-300 px-2 py-2">{DIMENSION_LABELS[dimension as DimensionKey]}</th>
														<th className="border border-gray-300 px-2 py-2">Net Finance</th>
														<th className="border border-gray-300 px-2 py-2">Units</th>
														<th className="border border-gray-300 px-2 py-2">Avg. IRR</th>
														<th className="border border-gray-300 px-2 py-2">Avg. Selling Rate</th>
														<th className="border border-gray-300 px-2 py-2">Avg. LTV</th>
														<th className="border border-gray-300 px-2 py-2">
															{dimensionSummary.metric.startsWith('proportion') ? 'Proportion (%)' : 'Avg. Tenor'}
														</th>
														<th className="border border-gray-300 px-2 py-2">Avg. Net Finance</th>
														{dimensionSummary.metric === 'tenor_and_year' && (
															<th className="border border-gray-300 px-2 py-2">Avg. Year</th>
														)}
													</tr>
												</thead>
												<tbody>
													{dimensionSummary.data.map((row, idx) => (
														<tr key={idx} className="odd:bg-gray-50">
															<td className="border border-gray-300 px-2 py-1">{row.label}</td>
															<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.net_finance)}</td>
															<td className="border border-gray-300 px-2 py-1 text-right">{row.units}</td>
															<td className="border border-gray-300 px-2 py-1 text-right">{fmt2(row.avg_irr)}</td>
															<td className="border border-gray-300 px-2 py-1 text-right">{fmt2(row.avg_sell)}</td>
															<td className="border border-gray-300 px-2 py-1 text-right">{fmt2(row.avg_ltv)}</td>
															<td className="border border-gray-300 px-2 py-1 text-right">
																{dimensionSummary.metric.startsWith('proportion') ? fmt2(row.proportion) : fmt2(row.avg_tenor)}
															</td>
															<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.avg_fin)}</td>
															{dimensionSummary.metric === 'tenor_and_year' && (
																<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.avg_tahun)}</td>
															)}
														</tr>
													))}
													<tr className="bg-gray-100 font-semibold">
														<td className="border border-gray-300 px-2 py-1 text-right">{dimensionSummary.grand_total.label}</td>
														<td className="border border-gray-300 px-2 py-1 text-right">{fmt(dimensionSummary.grand_total.net_finance)}</td>
														<td className="border border-gray-300 px-2 py-1 text-right">{dimensionSummary.grand_total.units}</td>
														<td className="border border-gray-300 px-2 py-1 text-right">{fmt2(dimensionSummary.grand_total.avg_irr)}</td>
														<td className="border border-gray-300 px-2 py-1 text-right">{fmt2(dimensionSummary.grand_total.avg_sell)}</td>
														<td className="border border-gray-300 px-2 py-1 text-right">{fmt2(dimensionSummary.grand_total.avg_ltv)}</td>
														<td className="border border-gray-300 px-2 py-1 text-right">
															{dimensionSummary.metric.startsWith('proportion')
																? fmt2(dimensionSummary.grand_total.proportion)
																: fmt2(dimensionSummary.grand_total.avg_tenor)}
														</td>
														<td className="border border-gray-300 px-2 py-1 text-right">{fmt(dimensionSummary.grand_total.avg_fin)}</td>
														{dimensionSummary.metric === 'tenor_and_year' && (
															<td className="border border-gray-300 px-2 py-1 text-right">{fmt(dimensionSummary.grand_total.avg_tahun)}</td>
														)}
													</tr>
												</tbody>
											</table>
										</div>
									)}

									<div className="text-sm font-semibold mb-2 underline">
										Grand Total Net Finance and Unit based on latest revised CAM (if any) ({detail.date_range_label}):
									</div>
									<div className="overflow-x-auto rounded-lg border border-gray-200">
										<table className="w-full text-sm border-collapse">
											<thead>
												<tr className="bg-gray-100 text-gray-700">
													<th className="border border-gray-300 px-2 py-2">Contract Type</th>
													<th className="border border-gray-300 px-2 py-2">Vehicle Type</th>
													<th className="border border-gray-300 px-2 py-2">Condition</th>
													<th className="border border-gray-300 px-2 py-2">Net Finance</th>
													<th className="border border-gray-300 px-2 py-2">Units</th>
													<th className="border border-gray-300 px-2 py-2">Avg. IRR</th>
													<th className="border border-gray-300 px-2 py-2">Avg. Selling Rate</th>
													<th className="border border-gray-300 px-2 py-2">Avg. LTV</th>
													<th className="border border-gray-300 px-2 py-2">Avg. Tenor</th>
													<th className="border border-gray-300 px-2 py-2">Avg. Net Finance</th>
												</tr>
											</thead>
											<tbody>
												{detail.summary_by_vehicle.map((row, idx) =>
													row.type === 'detail' ? (
														<tr key={idx} className="odd:bg-gray-50">
															<td className="border border-gray-300 px-2 py-1">{row.cons_leas}</td>
															<td className="border border-gray-300 px-2 py-1">{row.model}</td>
															<td className="border border-gray-300 px-2 py-1">{row.condition}</td>
															<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.net_finance)}</td>
															<td className="border border-gray-300 px-2 py-1 text-right">{row.units}</td>
															<td className="border border-gray-300 px-2 py-1 text-right">{fmt2(row.avg_irr)}</td>
															<td className="border border-gray-300 px-2 py-1 text-right">{fmt2(row.avg_sell)}</td>
															<td className="border border-gray-300 px-2 py-1 text-right">{fmt2(row.avg_ltv)}</td>
															<td className="border border-gray-300 px-2 py-1 text-right">{fmt2(row.avg_tenor)}</td>
															<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.avg_fin)}</td>
														</tr>
													) : (
														<tr key={idx} className="bg-gray-100 font-semibold">
															<td className="border border-gray-300 px-2 py-1 text-right" colSpan={3}>{row.label}</td>
															<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.net_finance)}</td>
															<td className="border border-gray-300 px-2 py-1 text-right">{row.units}</td>
															<td className="border border-gray-300 px-2 py-1 text-right">{fmt2(row.avg_irr)}</td>
															<td className="border border-gray-300 px-2 py-1 text-right">{fmt2(row.avg_sell)}</td>
															<td className="border border-gray-300 px-2 py-1 text-right">{fmt2(row.avg_ltv)}</td>
															<td className="border border-gray-300 px-2 py-1 text-right">{fmt2(row.avg_tenor)}</td>
															<td className="border border-gray-300 px-2 py-1 text-right">{fmt(row.avg_fin)}</td>
														</tr>
													)
												)}
											</tbody>
										</table>
									</div>
								</div>
							)}
						</>
					) : (
						<div className="py-10 text-center text-gray-400 text-sm">
							Fill in the search fields above and click Preview.
						</div>
					)}
				</div>
			</div>
		</div>
	);
};

export default ListCAMByDisbursementDatePage;