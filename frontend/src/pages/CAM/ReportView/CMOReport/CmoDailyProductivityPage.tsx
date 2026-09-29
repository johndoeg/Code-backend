import React, { useEffect, useState } from 'react';
import api from '../../../../api/axiosInstance';
import AsOfDatePicker from '../../../../components/AsOfDatePickerComponent';

interface BranchOption {
	branch_cd: string;
	branch_name: string;
}

interface CmoOption {
	employee_id: string;
	full_name: string;
}

interface ContextData {
	is_hq: boolean;
	own_branch: BranchOption | null;
	branches: BranchOption[];
	cmos: CmoOption[];
	access_level: string;
}

interface DetailRow {
	no: number;
	appl_no: string;
	id_reject: string;
	customer_name: string;
	date: string;
	status: string;
	cmo_name: string;
	reject_status: string;
	editable: boolean;
}

interface DetailTotals {
	cam_created: number;
	reject_watchlist: number;
	not_feasible: number;
	financed_elsewhere: number;
	cancelled: number;
	total: number;
}

interface RejectStatusOption {
	value: string;
	label: string;
}

const toISO = (d: Date): string => {
	const year = d.getFullYear();
	const month = String(d.getMonth() + 1).padStart(2, '0');
	const day = String(d.getDate()).padStart(2, '0');
	return `${year}-${month}-${day}`;
};

const CmoDailyProductivityPage: React.FC = () => {
	const [context, setContext] = useState<ContextData | null>(null);
	const [rejectStatusOptions, setRejectStatusOptions] = useState<RejectStatusOption[]>([]);

	const [startDate, setStartDate] = useState<Date | null>(null);
	const [endDate, setEndDate] = useState<Date | null>(null);
	const [selectedBranch, setSelectedBranch] = useState('');
	const [selectedCmo, setSelectedCmo] = useState('');
	const [hqCmoOptions, setHqCmoOptions] = useState<CmoOption[]>([]);

	const [rows, setRows] = useState<DetailRow[]>([]);
	const [totals, setTotals] = useState<DetailTotals | null>(null);
	const [showActions, setShowActions] = useState(false);
	const [consolidated, setConsolidated] = useState(true);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [hasSearched, setHasSearched] = useState(false);

	const [modalOpen, setModalOpen] = useState(false);
	const [modalMode, setModalMode] = useState<'add' | 'edit'>('add');
	const [editingIdReject, setEditingIdReject] = useState<string | null>(null);
	const [formDate, setFormDate] = useState<Date | null>(null);
	const [formCustName, setFormCustName] = useState('');
	const [formStatus, setFormStatus] = useState('');

	useEffect(() => {
		(async () => {
			try {
				const [ctxRes, statusRes] = await Promise.all([
					api.get<ContextData>('/CAM/CMO/api/daily-productivity-detail/context'),
					api.get<RejectStatusOption[]>('/CAM/CMO/api/daily-productivity-detail/reject-statuses'),
				]);
				const ctx = ctxRes.data;
				setContext(ctx);
				setRejectStatusOptions(statusRes.data);

				const params = new URLSearchParams(window.location.search);
				const lemparStart = params.get('lempar_start_dt');
				const lemparEnd = params.get('lempar_end_dt');
				const lemparBranch = params.get('lempar_branch');
				const lemparCmo = params.get('lempar_cmo');

				const initialStart = lemparStart ? new Date(lemparStart) : null;
				const initialEnd = lemparEnd ? new Date(lemparEnd) : null;
				setStartDate(initialStart);
				setEndDate(initialEnd);

				let branchToSearch = '';
				let cmoToSearch = '';

				if (ctx.is_hq) {
					branchToSearch = lemparBranch || '000';
					setSelectedBranch(branchToSearch);
					if (branchToSearch !== '000') {
						const cmoRes = await api.get<CmoOption[]>(
							'/CAM/CMO/api/daily-productivity-detail/cmos-by-branch',
							{ params: { branch: branchToSearch } }
						);
						setHqCmoOptions(cmoRes.data);
						const match = cmoRes.data.find((c) => c.employee_id === lemparCmo);
						cmoToSearch = match ? match.employee_id : '000';
						setSelectedCmo(cmoToSearch);
					}
				} else if (ctx.own_branch) {
					branchToSearch = ctx.own_branch.branch_cd;
					setSelectedBranch(branchToSearch);
					const match = ctx.cmos.find((c) => c.employee_id === lemparCmo);
					cmoToSearch = match && ctx.own_branch.branch_cd !== '000' ? match.employee_id : (ctx.cmos[0]?.employee_id ?? '');
					setSelectedCmo(cmoToSearch);
				}

				if (lemparBranch && initialStart && initialEnd && branchToSearch) {
					await runSearch(initialStart, initialEnd, branchToSearch, cmoToSearch, ctx.access_level);
				}
			} catch (err) {
				console.error('Context load error:', err);
			}
		})();
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, []);

	const handleBranchChange = async (branchCd: string) => {
		setSelectedBranch(branchCd);
		setSelectedCmo('');
		setHqCmoOptions([]);
		if (branchCd && branchCd !== '000') {
			try {
				const res = await api.get<CmoOption[]>('/CAM/CMO/api/daily-productivity-detail/cmos-by-branch', {
					params: { branch: branchCd },
				});
				setHqCmoOptions(res.data);
				setSelectedCmo('000');
			} catch (err) {
				console.error('CMO-by-branch error:', err);
			}
		}
	};

	const runSearch = async (
		start: Date,
		end: Date,
		branchCd: string,
		cmo: string,
		accessLevel: string
	) => {
		setLoading(true);
		setError(null);
		setHasSearched(true);
		try {
			const response = await api.get('/CAM/CMO/api/daily-productivity-detail/list', {
				params: {
					start_date: toISO(start),
					end_date: toISO(end),
					branch: branchCd,
					cmo,
				},
			});
			setRows(response.data.data);
			setTotals(response.data.totals);
			setShowActions(response.data.show_actions);
			setConsolidated(response.data.consolidated);
		} catch (err) {
			console.error('CMO daily productivity detail error:', err);
			setError('Failed to load report. Please try again.');
		} finally {
			setLoading(false);
		}
	};

	const handleSearch = () => {
		if (!startDate || !endDate || !selectedBranch || !context) return;
		runSearch(startDate, endDate, selectedBranch, selectedCmo, context.access_level);
	};

	const refreshAfterMutation = () => {
		if (startDate && endDate && selectedBranch && context) {
			runSearch(startDate, endDate, selectedBranch, selectedCmo, context.access_level);
		}
	};

	const openAddModal = () => {
		setModalMode('add');
		setEditingIdReject(null);
		setFormDate(null);
		setFormCustName('');
		setFormStatus('');
		setModalOpen(true);
	};

	const openEditModal = async (idReject: string) => {
		try {
			const res = await api.get(`/CAM/CMO/api/daily-productivity-detail/reject/${idReject}`);
			setModalMode('edit');
			setEditingIdReject(idReject);
			setFormDate(res.data.create_date ? parseDdMmYyyy(res.data.create_date) : null);
			setFormCustName(res.data.customer_name || '');
			setFormStatus(String(res.data.reject_status || ''));
			setModalOpen(true);
		} catch (err) {
			console.error('Reject fetch error:', err);
		}
	};

	const parseDdMmYyyy = (s: string): Date | null => {
		const [d, m, y] = s.split('-').map(Number);
		if (!d || !m || !y) return null;
		return new Date(y, m - 1, d);
	};

	const handleConfirm = async () => {
		if (!formDate || !formCustName.trim() || !formStatus) {
			alert('Lengkapi Data!');
			return;
		}
		const payload = {
			date: toISO(formDate),
			customer_name: formCustName.trim(),
			reject_status: formStatus,
		};
		try {
			if (modalMode === 'add') {
				await api.post('/CAM/CMO/api/daily-productivity-detail/reject', payload);
				alert('Data berhasil disimpan');
			} else if (editingIdReject) {
				await api.put(`/CAM/CMO/api/daily-productivity-detail/reject/${editingIdReject}`, payload);
				alert('Data berhasil update');
			}
			setModalOpen(false);
			refreshAfterMutation();
		} catch (err) {
			console.error('Reject save error:', err);
			alert('Data gagal disimpan');
		}
	};

	const handleDelete = async (idReject: string) => {
		if (!window.confirm('Are you sure to delete this record?!')) return;
		try {
			await api.delete(`/CAM/CMO/api/daily-productivity-detail/reject/${idReject}`);
			refreshAfterMutation();
		} catch (err) {
			console.error('Reject delete error:', err);
		}
	};

	const cmoOptionsToShow = context?.is_hq ? hqCmoOptions : context?.cmos ?? [];
	const showAddButton = context?.access_level === 'CMO';

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-6xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6 mb-6">
					<div className="mb-6">
						<h1 className="text-xl md:text-2xl font-bold text-gray-800">
							Detail of Credit Marketing Officer Daily Productivity Report
						</h1>
					</div>

					<div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6 text-sm items-end">
						<div>
							<label className="text-gray-500 block mb-1">Start Date</label>
							<AsOfDatePicker label="" value={startDate} onChange={setStartDate} required />
						</div>
						<div>
							<label className="text-gray-500 block mb-1">End Date</label>
							<AsOfDatePicker label="" value={endDate} onChange={setEndDate} required />
						</div>
						<div>
							<label className="text-gray-500 block mb-1">Branch</label>
							{context?.is_hq ? (
								<select
									value={selectedBranch}
									onChange={(e) => handleBranchChange(e.target.value)}
									className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
								>
									{context.branches.map((b) => (
										<option key={b.branch_cd} value={b.branch_cd}>
											{b.branch_name}
										</option>
									))}
								</select>
							) : (
								<select
									value={selectedBranch}
									disabled
									className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm bg-gray-50"
								>
									{context?.own_branch && (
										<option value={context.own_branch.branch_cd}>{context.own_branch.branch_name}</option>
									)}
								</select>
							)}
						</div>
						<div>
							<label className="text-gray-500 block mb-1">CMO Name</label>
							<select
								value={selectedCmo}
								onChange={(e) => setSelectedCmo(e.target.value)}
								className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
							>
								{cmoOptionsToShow.map((c) => (
									<option key={c.employee_id} value={c.employee_id}>
										{c.full_name}
									</option>
								))}
							</select>
						</div>
					</div>

					<div className="mb-6 flex gap-2">
						<button
							onClick={handleSearch}
							disabled={!startDate || !endDate || !selectedBranch}
							className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
						>
							Search
						</button>
						{showAddButton && (
							<button
								onClick={openAddModal}
								className="bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
							>
								Add
							</button>
						)}
					</div>

					{error && (
						<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
							{error}
						</div>
					)}

					<div className="overflow-x-auto rounded-lg border border-gray-200 mb-6">
						<table className="w-full text-sm border-collapse">
							<thead>
								<tr className="bg-gray-100 text-gray-700">
									<th className="border border-gray-300 px-2 py-2">No.</th>
									<th className="border border-gray-300 px-2 py-2">Date</th>
									<th className="border border-gray-300 px-2 py-2">CAM No.</th>
									{consolidated && <th className="border border-gray-300 px-2 py-2">CMO</th>}
									<th className="border border-gray-300 px-2 py-2">Customer Name</th>
									<th className="border border-gray-300 px-2 py-2">Status</th>
									{showActions && <th className="border border-gray-300 px-2 py-2">Action</th>}
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
											Choose a period, branch, and CMO, then click Search.
										</td>
									</tr>
								) : rows.length === 0 ? (
									<tr>
										<td colSpan={7} className="border border-gray-300 px-2 py-4 text-center text-gray-400">
											No records found for this period.
										</td>
									</tr>
								) : (
									rows.map((row) => (
										<tr key={`${row.appl_no}-${row.id_reject}-${row.no}`} className="odd:bg-gray-50">
											<td className="border border-gray-300 px-2 py-1 text-center">{row.no}</td>
											<td className="border border-gray-300 px-2 py-1 text-center">{row.date}</td>
											<td className="border border-gray-300 px-2 py-1 text-center">{row.appl_no}</td>
											{consolidated && <td className="border border-gray-300 px-2 py-1 text-center">{row.cmo_name}</td>}
											<td className="border border-gray-300 px-2 py-1">{row.customer_name}</td>
											<td className="border border-gray-300 px-2 py-1">{row.status}</td>
											{showActions && (
												<td className="border border-gray-300 px-2 py-1 text-center">
													{row.editable && (
														<div className="flex gap-2 justify-center">
															<button
																onClick={() => openEditModal(row.id_reject)}
																className="text-blue-600 hover:underline text-xs"
															>
																Edit
															</button>
															<button
																onClick={() => handleDelete(row.id_reject)}
																className="text-red-600 hover:underline text-xs"
															>
																Delete
															</button>
														</div>
													)}
												</td>
											)}
										</tr>
									))
								)}
							</tbody>
						</table>
					</div>

					{totals && hasSearched && (
						<div className="overflow-x-auto rounded-lg border border-gray-200">
							<table className="w-full text-sm border-collapse">
								<thead>
									<tr className="bg-gray-100 text-gray-700">
										<th className="border border-gray-300 px-2 py-2" colSpan={5}>Status</th>
										<th className="border border-gray-300 px-2 py-2">Total Application</th>
									</tr>
									<tr className="bg-gray-100 text-gray-700">
										<th className="border border-gray-300 px-2 py-2">CAM Created</th>
										<th className="border border-gray-300 px-2 py-2">Reject to Watchlist</th>
										<th className="border border-gray-300 px-2 py-2">Customer is Not Feasible to be Financed</th>
										<th className="border border-gray-300 px-2 py-2">Customer is Financed by Another Leasing Company</th>
										<th className="border border-gray-300 px-2 py-2">Customer Cancel Their Application</th>
										<th className="border border-gray-300 px-2 py-2"></th>
									</tr>
								</thead>
								<tbody>
									<tr>
										<td className="border border-gray-300 px-2 py-1 text-center">{totals.cam_created}</td>
										<td className="border border-gray-300 px-2 py-1 text-center">{totals.reject_watchlist}</td>
										<td className="border border-gray-300 px-2 py-1 text-center">{totals.not_feasible}</td>
										<td className="border border-gray-300 px-2 py-1 text-center">{totals.financed_elsewhere}</td>
										<td className="border border-gray-300 px-2 py-1 text-center">{totals.cancelled}</td>
										<td className="border border-gray-300 px-2 py-1 text-center font-semibold">{totals.total}</td>
									</tr>
								</tbody>
							</table>
						</div>
					)}
				</div>
			</div>

			{modalOpen && (
				<div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
					<div className="bg-white rounded-2xl shadow-xl w-full max-w-lg overflow-hidden">
						<div className="flex justify-between items-center p-4 border-b">
							<h3 className="font-bold text-gray-800">Application Information</h3>
							<button onClick={() => setModalOpen(false)} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">
								×
							</button>
						</div>
						<div className="p-4 space-y-3 text-sm">
							<div>
								<label className="text-gray-500 block mb-1">Date</label>
								<AsOfDatePicker label="" value={formDate} onChange={setFormDate} required />
							</div>
							<div>
								<label className="text-gray-500 block mb-1">Customer Name</label>
								<input
									type="text"
									value={formCustName}
									onChange={(e) => setFormCustName(e.target.value)}
									className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
								/>
							</div>
							<div>
								<label className="text-gray-500 block mb-1">Status</label>
								<select
									value={formStatus}
									onChange={(e) => setFormStatus(e.target.value)}
									className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
								>
									<option value="">Select</option>
									{rejectStatusOptions.map((opt) => (
										<option key={opt.value} value={opt.value}>
											{opt.label}
										</option>
									))}
								</select>
							</div>
						</div>
						<div className="p-4 border-t flex justify-end">
							<button
								onClick={handleConfirm}
								className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
							>
								Confirm
							</button>
						</div>
					</div>
				</div>
			)}
		</div>
	);
};

export default CmoDailyProductivityPage;