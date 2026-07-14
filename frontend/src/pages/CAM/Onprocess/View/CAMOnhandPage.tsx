import React, { useEffect, useState, useCallback, useRef } from "react";
import api from '../../../../api/axiosInstance';
import Pagination from "../../../../helpers/Pagination";
import { DEFAULT_PAGE_LIMIT } from '../../../../constants/DefaultValue';
import CamViewTabs from './CamViewTabs';
import type { CamCtx } from './CamViewTabs';

type AccessLevel = "CMO" | "CRH" | string;
type RowColor = "default" | "revise" | "reject";

interface CamRow {
	appl_no: string;
	tgl: string;
	cons_leas: string;
	lessee_nm: string;
	namacmo: string;
	can_manage: boolean;
	reject_person: string;
	reject_comment: string;
	cbgnow: string;
	cmo_now: string;
	brch_code: string;
	color: RowColor;
	str_revisi: string;
	str_multiple: string;
	fin_type: string;
	ind_cor: string;
	guarantor: string;
	new_car: string;
	tenor: string;
	c2c: string;
	purpoffinc: string;
	cont_type: string;
	apless: string;
	r_change: string;
	go_public: string;
	menmen: number;
	tot_outs: number;
	picked_by: string;
	mstr_ca: string;
	cbgnow_co: boolean;
}

interface UserCtx {
	emp_id: string;
	username: string;
	accessLevel: AccessLevel;
}

const COLOR_MAP: Record<RowColor, string> = {
	default: "text-gray-800",
	revise: "text-green-700 font-semibold",
	reject: "text-fuchsia-600 font-semibold",
};

const LINK_COLOR_MAP: Record<RowColor, string> = {
	default: "text-blue-600 hover:text-blue-800",
	revise: "text-green-700 font-semibold hover:text-green-800",
	reject: "text-fuchsia-600 font-semibold hover:text-fuchsia-700",
};

interface ConfirmDialogProps {
	open: boolean;
	title: string;
	message: string;
	onOk: () => void;
	onCancel: () => void;
}

const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
	open, title, message, onOk, onCancel,
}) => {
	if (!open) return null;
	return (
		<div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
			<div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-6">
				<h3 className="text-lg font-bold text-red-600 mb-2">{title}</h3>
				<p className="text-gray-700 mb-6 text-sm">{message}</p>
				<div className="flex justify-end gap-3">
					<button
						onClick={onCancel}
						className="px-4 py-2 border border-gray-300 rounded-lg text-gray-600 hover:bg-gray-50 text-sm"
					>
						Cancel
					</button>
					<button
						onClick={onOk}
						className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium"
					>
						Confirm
					</button>
				</div>
			</div>
		</div>
	);
};

const CamOnHandPage: React.FC = () => {
	const userCtx: UserCtx = {
		emp_id: (window as any).__USER_EMP_ID__ || "",
		username: (window as any).__USER_NAME__ || "",
		accessLevel: (window as any).__ACCESS_LEVEL__ || "",
	};
	const { emp_id, username, accessLevel } = userCtx;

	const [rows, setRows] = useState<CamRow[]>([]);
	const [total, setTotal] = useState(0);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	const [page, setPage] = useState(1);
	const limit = DEFAULT_PAGE_LIMIT;
	const totalPages = Math.ceil(total / limit);

	const [searchBy, setSearchBy] = useState("1");
	const [searchVal, setSearchVal] = useState("");
	const [appliedSearch, setAppliedSearch] = useState({ by: "", val: "" });

	const [checkedAppl, setCheckedAppl] = useState<Set<string>>(new Set());
	const [multipleMode, setMultipleMode] = useState(false);

	const [checkedPickup, setCheckedPickup] = useState<Set<string>>(new Set());

	const [confirmDelete, setConfirmDelete] = useState<{ open: boolean; apless: string; appl_no: string }>({ open: false, apless: "", appl_no: "" });
	const [confirmWatchlist, setConfirmWatchlist] = useState<{ open: boolean; apless: string; appl_no: string }>({ open: false, apless: "", appl_no: "" });
	const [confirmSend, setConfirmSend] = useState(false);
	const [confirmPickSave, setConfirmPickSave] = useState(false);

	const [activeCam, setActiveCam] = useState<{ ctx: CamCtx; menu: number } | null>(null);

	const hasCrhPickRow = useRef(false);

	const fetchRows = useCallback(async () => {
		setLoading(true);
		setError(null);
		setCheckedAppl(new Set());
		setCheckedPickup(new Set());

		try {
			const res = await api.get('/CAM/api/onhand', {
				params: {
					page,
					limit,
					search_by: appliedSearch.by,
					search_val: appliedSearch.val,
				},
			});
			setRows(res.data.data ?? []);
			setTotal(res.data.total ?? 0);
		} catch {
			setError("Failed to load data. Please try again.");
		} finally {
			setLoading(false);
		}
	}, [page, limit, appliedSearch]);

	useEffect(() => {
		fetchRows();
	}, [fetchRows]);

	useEffect(() => {
		setPage(1);
	}, [appliedSearch]);

	useEffect(() => {
		if (!activeCam) return;
		const original = document.body.style.overflow;
		document.body.style.overflow = "hidden";
		return () => {
			document.body.style.overflow = original;
		};
	}, [activeCam]);

	const handleSearch = () => {
		setAppliedSearch({ by: searchBy, val: searchVal });
	};

	const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
		if (e.key === "Enter") handleSearch();
	};

	const toggleCheck = (appl_no: string) => {
		setCheckedAppl(prev => {
			const next = new Set(prev);
			next.has(appl_no) ? next.delete(appl_no) : next.add(appl_no);
			return next;
		});
	};

	const handleSend = async () => {
		if (checkedAppl.size === 0) {
			alert("Check it first please");
			return;
		}
		setConfirmSend(true);
	};

	const doSend = async () => {
		setConfirmSend(false);
		try {
			const res = await api.post('/CAM/api/onhand/send', {
				appl_nos: Array.from(checkedAppl),
				multiple: multipleMode,
			});
			if (res.data.success) {
				window.location.href = res.data.redirect;
			} else {
				alert(res.data.message);
			}
		} catch {
			alert("Send failed. Please try again.");
		}
	};

	const handleCekValidasi = async (appl_no: string, apless: string) => {
		try {
			const res = await api.post('/CAM/api/onhand/validate', { appl_no });
			if (!res.data.valid) {
				alert(res.data.message);
				fetchRows();
			} else {
				window.location.href = `/cam_approval?apless=${apless}&applno=${appl_no}`;
			}
		} catch {
			window.location.href = `/cam_approval?apless=${apless}&applno=${appl_no}`;
		}
	};

	const doDelete = async () => {
		const { apless, appl_no } = confirmDelete;
		setConfirmDelete({ open: false, apless: "", appl_no: "" });
		try {
			await api.delete(`/CAM/api/onhand/${appl_no}`, {
				params: { apless },
			});
			fetchRows();
		} catch {
			alert("Delete failed. Please try again.");
		}
	};

	const doRejectWatchlist = async () => {
		const { apless, appl_no } = confirmWatchlist;
		setConfirmWatchlist({ open: false, apless: "", appl_no: "" });
		try {
			await api.post(`/CAM/api/onhand/${appl_no}/reject-watchlist`, { apless });
			fetchRows();
		} catch {
			alert("Action failed. Please try again.");
		}
	};

	const togglePickup = (appl_no: string, disabled: boolean) => {
		if (disabled) return;
		setCheckedPickup(prev => {
			const next = new Set(prev);
			next.has(appl_no) ? next.delete(appl_no) : next.add(appl_no);
			return next;
		});
	};

	const doPickSave = async () => {
		setConfirmPickSave(false);
		try {
			await api.post('/CAM/api/onhand/pick', {
				appl_nos: Array.from(checkedPickup),
			});
			alert("Success");
			fetchRows();
		} catch {
			alert("Save failed.");
		}
	};

	const handleEdit = (row: CamRow) => {
		if (row.appl_no.length > 11) {
			alert("The Cam No is invalid.");
			return;
		}

		if (!window.confirm("Are you sure to update data?")) return;
		const p = new URLSearchParams({
			id1: row.fin_type,
			id2: row.ind_cor,
			id3: "1",
			id4: row.guarantor,
			id5: row.new_car,
			id6: "Edit",
			id7: row.purpoffinc,
			id8: row.c2c,
			id9: row.cont_type,
			apless: row.apless,
			applno: row.appl_no,
			id10: row.r_change,
			id13: row.go_public,
		});
		window.parent.location.href = `/edit_index?${p}`;
	};

	hasCrhPickRow.current = rows.some(
		r => accessLevel === "CRH" && r.tot_outs > 300_000_000 && r.tot_outs <= 600_000_000
	);

	const startIndex = (page - 1) * limit + 1;

	const openCam = (row: CamRow, mode: "Edit" | "View") => {
		setActiveCam({
			menu: 1,
			ctx: {
				finType: row.fin_type,
				indCor: row.ind_cor,
				repeat: "1",
				guarantor: row.guarantor,
				newCar: row.new_car,
				status: mode,
				purpoffinc: row.purpoffinc,
				c2c: row.c2c,
				contType: row.cont_type,
				apless: row.apless,
				applno: row.appl_no,
			},
		});
	};

	const camLabel = (row: CamRow) =>
		`${row.cons_leas} - ${row.appl_no}${row.str_revisi}${row.str_multiple}`;

	const crhCheckboxState = (row: CamRow): { disabled: boolean; checked: boolean } => {
		const inRange = row.tot_outs > 300_000_000 && row.tot_outs <= 600_000_000;
		if (!inRange) return { disabled: true, checked: false };
		if (!row.picked_by) return { disabled: false, checked: checkedPickup.has(row.appl_no) };
		if (row.picked_by === emp_id) return { disabled: true, checked: true };
		return { disabled: true, checked: false };
	};

	const renderCmoHeaders = () => (
		<tr className="bg-gradient-to-r from-slate-100 to-slate-200">
			{["Date", "CAM No.", "Customer Name", "Status", "Branch", "", "Actions", "Send"].map((h, i) => (
				<th key={i} className="py-3 px-4 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider whitespace-nowrap">
					{h}
				</th>
			))}
		</tr>
	);

	const renderApproverHeaders = (extra: string) => (
		<tr className="bg-gradient-to-r from-slate-100 to-slate-200">
			{["Date", "CAM No.", "Customer Name", "Status", "Branch - CMO", "", "Actions", extra].map((h, i) => (
				<th key={i} className="py-3 px-4 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider whitespace-nowrap">
					{h}
				</th>
			))}
		</tr>
	);

	const renderCmoRow = (row: CamRow, idx: number) => {
		if (row.cbgnow_co) return null;

		const colorCls = COLOR_MAP[row.color];
		const linkColorCls = LINK_COLOR_MAP[row.color];
		const isReject = row.color === "reject";

		const statusCell = isReject ? (
			<span>
				<strong>Reject by:</strong> {row.reject_person}<br />
				<strong>Comment:</strong> {row.reject_comment}{" "}
				<span className="italic text-xs">Click No. CAM for Detail..</span>
			</span>
		) : (
			<span>{row.namacmo}</span>
		);

		return (
			<tr key={row.appl_no || `cmo-${idx}`}
				className={`${idx % 2 === 0 ? "bg-white" : "bg-slate-50"} hover:bg-blue-50 transition-colors`}>
				<td className="py-3 px-4 text-sm whitespace-nowrap text-gray-600">{row.tgl}</td>
				<td className="py-3 px-4 text-sm whitespace-nowrap">
					<button type="button" onClick={() => openCam(row, "Edit")}
						className={`text-left underline-offset-2 hover:underline ${linkColorCls}`}>
						{camLabel(row)}
					</button>
				</td>
				<td className={`py-3 px-4 text-sm ${colorCls}`}>{row.lessee_nm}</td>
				<td className={`py-3 px-4 text-sm ${colorCls}`}>{statusCell}</td>
				<td className={`py-3 px-4 text-sm ${colorCls}`}>{row.brch_code}</td>
				<td className="py-3 px-4" />
				<td className="py-3 px-4 text-sm whitespace-nowrap">
					{row.can_manage && (
						<div className="flex flex-wrap gap-1">
							<button onClick={() => handleEdit(row)}
								className="px-2 py-1 bg-blue-500 hover:bg-blue-600 text-white rounded text-xs font-medium">
								Edit
							</button>
							<button onClick={() => setConfirmDelete({ open: true, apless: row.apless, appl_no: row.appl_no })}
								className="px-2 py-1 bg-red-500 hover:bg-red-600 text-white rounded text-xs font-medium">
								Delete
							</button>
							<button onClick={() => setConfirmWatchlist({ open: true, apless: row.apless, appl_no: row.appl_no })}
								className="px-2 py-1 bg-orange-500 hover:bg-orange-600 text-white rounded text-xs font-medium">
								Reject to Watchlist
							</button>
						</div>
					)}
				</td>
				<td className="py-3 px-4 text-center">
					<input type="checkbox" checked={checkedAppl.has(row.appl_no)}
						onChange={() => toggleCheck(row.appl_no)}
						className="w-4 h-4 accent-blue-600" />
				</td>
			</tr>
		);
	};

	const renderApproverRow = (row: CamRow, idx: number) => {
		if (row.cbgnow_co) return null;

		const colorCls = COLOR_MAP[row.color];
		const linkColorCls = LINK_COLOR_MAP[row.color];
		const isCrh = accessLevel === "CRH";
		const inCrhRange = row.tot_outs > 300_000_000 && row.tot_outs <= 600_000_000;
		const { disabled: cbDisabled, checked: cbChecked } = isCrh ? crhCheckboxState(row) : { disabled: true, checked: false };
		const showPickupCol = isCrh && inCrhRange;

		return (
			<tr key={row.appl_no || `appr-${idx}`}
				className={`${idx % 2 === 0 ? "bg-white" : "bg-slate-50"} hover:bg-blue-50 transition-colors`}>
				<td className="py-3 px-4 text-sm whitespace-nowrap text-gray-600">{row.tgl}</td>
				<td className="py-3 px-4 text-sm whitespace-nowrap">
					<button type="button" onClick={() => openCam(row, "View")}
						className={`text-left underline-offset-2 hover:underline ${linkColorCls}`}>
						{camLabel(row)}
					</button>
				</td>
				<td className={`py-3 px-4 text-sm ${colorCls}`}>{row.lessee_nm}</td>
				<td className={`py-3 px-4 text-sm ${colorCls}`}>{row.namacmo}</td>
				<td className={`py-3 px-4 text-sm ${colorCls}`}>
					{row.cbgnow}&nbsp;&nbsp;({row.cmo_now})
				</td>
				<td className="py-3 px-4" />
				<td className="py-3 px-4 text-sm whitespace-nowrap">
					<button onClick={() => handleCekValidasi(row.appl_no, row.apless)}
						className="px-3 py-1 bg-emerald-500 hover:bg-emerald-600 text-white rounded text-xs font-medium">
						Send
					</button>
				</td>
				{isCrh ? (
					<td className="py-3 px-4 text-center">
						{showPickupCol && (
							<input type="checkbox"
								checked={cbChecked}
								disabled={cbDisabled}
								onChange={() => togglePickup(row.appl_no, cbDisabled)}
								className="w-4 h-4 accent-blue-600 disabled:opacity-40" />
						)}
					</td>
				) : (
					<td className="py-3 px-4" />
				)}
			</tr>
		);
	};

	return (
		<div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 p-4 md:p-6">
			<div className="max-w-full mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6 mb-6">
					<div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
						<div>
							<h1 className="text-2xl md:text-3xl font-bold text-slate-800">
								On Process — On Hand
							</h1>
							<p className="text-slate-500 mt-1 text-sm">
								Credit Approval Memo tracking
							</p>
						</div>
						<span className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm font-medium self-start md:self-auto">
							Total: {total}
						</span>
					</div>

					<div className="flex flex-wrap items-center gap-2 mb-4">
						<select
							value={searchBy}
							onChange={e => setSearchBy(e.target.value)}
							className="border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
						>
							<option value="1">CAM No.</option>
							<option value="2">Customer Name</option>
						</select>
						<input
							type="text"
							value={searchVal}
							onChange={e => setSearchVal(e.target.value)}
							onKeyDown={handleSearchKeyDown}
							placeholder="Search…"
							className="border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 w-48"
						/>
						<button
							onClick={handleSearch}
							className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium"
						>
							Search
						</button>
					</div>

					{error && (
						<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm flex items-center justify-between">
							{error}
							<button onClick={fetchRows} className="underline ml-4">Retry</button>
						</div>
					)}

					<div className="overflow-x-auto rounded-xl border border-slate-200">
						<table className="w-full text-sm">
							<thead>
								{accessLevel === "CMO"
									? renderCmoHeaders()
									: renderApproverHeaders(accessLevel === "CRH" ? "Pick Up CAM" : "")}
							</thead>
							<tbody className="divide-y divide-slate-100">
								{loading ? (
									<tr>
										<td colSpan={8} className="py-14 text-center text-slate-400">
											<div className="flex justify-center">
												<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
											</div>
										</td>
									</tr>
								) : rows.length === 0 ? (
									<tr>
										<td colSpan={8} className="py-14 text-center text-slate-400">
											No records found
										</td>
									</tr>
								) : (
									rows.map((row, idx) =>
										accessLevel === "CMO"
											? renderCmoRow(row, idx)
											: renderApproverRow(row, idx)
									)
								)}
							</tbody>
						</table>
					</div>

					{accessLevel === "CMO" && !loading && (
						<div className="flex items-center gap-4 mt-4">
							<label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer select-none">
								<input
									type="checkbox"
									checked={multipleMode}
									onChange={e => setMultipleMode(e.target.checked)}
									className="w-4 h-4 accent-blue-600"
								/>
								Multiple
							</label>
							<button
								onClick={handleSend}
								disabled={checkedAppl.size === 0}
								className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white rounded-lg text-sm font-medium"
							>
								Send
							</button>
						</div>
					)}

					{accessLevel === "CRH" && hasCrhPickRow.current && !loading && (
						<div className="flex justify-end mt-4">
							<button
								onClick={() => setConfirmPickSave(true)}
								disabled={checkedPickup.size === 0}
								className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white rounded-lg text-sm font-medium"
							>
								Save
							</button>
						</div>
					)}

					{!loading && total > 0 && (
						<Pagination
							page={page}
							totalPages={totalPages}
							onPageChange={setPage}
							totalItems={total}
							itemsPerPage={limit}
							className="mt-6"
						/>
					)}
				</div>

				<div className="flex items-center gap-6 px-2">
					<div className="flex items-center gap-2">
						<span className="inline-block w-4 h-4 rounded border border-slate-200 bg-green-600" />
						<span className="text-sm text-slate-600">Revise</span>
					</div>
					<div className="flex items-center gap-2">
						<span className="inline-block w-4 h-4 rounded border border-slate-200 bg-fuchsia-500" />
						<span className="text-sm text-slate-600">Reject</span>
					</div>
				</div>
			</div>

			<ConfirmDialog
				open={confirmDelete.open}
				title="Delete CAM"
				message="Are you sure you want to delete this data?"
				onOk={doDelete}
				onCancel={() => setConfirmDelete({ open: false, apless: "", appl_no: "" })}
			/>

			<ConfirmDialog
				open={confirmWatchlist.open}
				title="Reject to Watchlist"
				message="Are you sure you want to reject this CAM to the watchlist?"
				onOk={doRejectWatchlist}
				onCancel={() => setConfirmWatchlist({ open: false, apless: "", appl_no: "" })}
			/>

			<ConfirmDialog
				open={confirmSend}
				title="Confirm Send"
				message="Are you sure your selection is correct?"
				onOk={doSend}
				onCancel={() => setConfirmSend(false)}
			/>

			<ConfirmDialog
				open={confirmPickSave}
				title="Save Pick-up"
				message={`Save pick-up for ${checkedPickup.size} item(s)?`}
				onOk={doPickSave}
				onCancel={() => setConfirmPickSave(false)}
			/>

			{activeCam && (
				<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
					<div
						role="dialog"
						aria-modal="true"
						aria-label={`CAM ${activeCam.ctx.applno} detail`}
						className="flex max-h-[90vh] w-[90vw] flex-col overflow-hidden rounded-2xl bg-white shadow-2xl"
					>
						<div className="min-h-0 flex-1 overflow-y-auto">
							<CamViewTabs
								ctx={activeCam.ctx}
								initialMenu={activeCam.menu}
								initialSubmenu={1}
								onHome={() => setActiveCam(null)}
							/>
						</div>
					</div>
				</div>
			)}
		</div>
	);
};

export default CamOnHandPage;