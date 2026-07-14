import React, { useEffect, useState, useCallback } from "react";
import api from '../../../../api/axiosInstance';
import Pagination from "../../../../helpers/Pagination";
import { DEFAULT_PAGE_LIMIT } from '../../../../constants/DefaultValue';

type RowColor = "default" | "revise";

interface CamRow {
	appl_no: string;
	tgl: string;
	cons_leas: string;
	lessee_nm: string;
	appr_id: string;
	cbgnow: string;
	color: RowColor;
	str_revisi: string;
	str_multiple: string;
	fin_type: string;
	ind_cor: string;
	guarantor: string;
	new_car: string;
	tenor: string;
	c2c: string;
	apless: string;
	menmen: number;
	can_withdraw: boolean;
}

interface UserCtx {
	username: string;
	accessLevel: string;
}

const COLOR_MAP: Record<RowColor, string> = {
	default: "text-gray-800",
	revise: "text-green-700 font-semibold",
};

interface ConfirmDialogProps {
	open: boolean;
	title: string;
	message: string;
	confirmLabel: string;
	busy: boolean;
	onOk: () => void;
	onCancel: () => void;
}

const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
	open, title, message, confirmLabel, busy, onOk, onCancel,
}) => {
	if (!open) return null;
	return (
		<div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
			<div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-6">
				<h3 className="text-lg font-bold text-amber-600 mb-2">{title}</h3>
				<p className="text-gray-700 mb-6 text-sm">{message}</p>
				<div className="flex justify-end gap-3">
					<button
						onClick={onCancel}
						disabled={busy}
						className="px-4 py-2 border border-gray-300 rounded-lg text-gray-600 hover:bg-gray-50 text-sm"
					>
						Cancel
					</button>
					<button
						onClick={onOk}
						disabled={busy}
						className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-sm font-medium disabled:opacity-50"
					>
						{busy ? "Working…" : confirmLabel}
					</button>
				</div>
			</div>
		</div>
	);
};

const CamInProgressPage: React.FC = () => {
	const userCtx: UserCtx = {
		username: (window as any).__USER_NAME__ || "",
		accessLevel: (window as any).__ACCESS_LEVEL__ || "",
	};
	const { accessLevel } = userCtx;

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

	const [withdrawTarget, setWithdrawTarget] = useState<{ apless: string; appl_no: string } | null>(null);
	const [withdrawing, setWithdrawing] = useState(false);

	const fetchRows = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			const res = await api.get('/CAM/api/inprogress', {
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

	const handleSearch = () => {
		setAppliedSearch({ by: searchBy, val: searchVal });
	};

	const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
		if (e.key === "Enter") handleSearch();
	};

	const camHref = (row: CamRow) => {
		const p = new URLSearchParams({
			id1: row.fin_type,
			id2: row.ind_cor,
			id3: "1",
			id4: row.guarantor,
			id5: row.new_car,
			id6: "Edit",
			id7: row.tenor,
			id8: row.c2c,
			apless: row.apless,
			applno: row.appl_no,
		});
		if (accessLevel !== "CMO") {
			p.set("menu", String(row.menmen));
			p.set("submenu", "1");
		}
		return `/view_main?${p.toString()}`;
	};

	const camLabel = (row: CamRow) =>
		`${row.cons_leas} - ${row.appl_no}${row.str_revisi}${row.str_multiple}`;

	const doWithdraw = async () => {
		if (!withdrawTarget) return;
		setWithdrawing(true);
		try {
			const res = await api.post('/CAM/api/inprogress/withdraw', withdrawTarget);
			if (res.data.success) {
				setWithdrawTarget(null);
				fetchRows();
			} else {
				alert(res.data.message || "Withdraw failed.");
				setWithdrawTarget(null);
			}
		} catch {
			alert("Withdraw failed. Please try again.");
			setWithdrawTarget(null);
		} finally {
			setWithdrawing(false);
		}
	};

	return (
		<div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 p-4 md:p-6">
			<div className="max-w-full mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6 mb-6">
					<div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
						<div>
							<h1 className="text-2xl md:text-3xl font-bold text-slate-800">
								On Process — In Progress
							</h1>
							<p className="text-slate-500 mt-1 text-sm">
								CAMs where your step is done but a later approver hasn't acted yet
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
								<tr className="bg-gradient-to-r from-slate-100 to-slate-200">
									{["Date", "CAM No.", "Customer Name", "Status", "Branch", ""].map((h, i) => (
										<th key={i} className="py-3 px-4 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider whitespace-nowrap">
											{h}
										</th>
									))}
								</tr>
							</thead>
							<tbody className="divide-y divide-slate-100">
								{loading ? (
									<tr>
										<td colSpan={6} className="py-14 text-center text-slate-400">
											<div className="flex justify-center">
												<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
											</div>
										</td>
									</tr>
								) : rows.length === 0 ? (
									<tr>
										<td colSpan={6} className="py-14 text-center text-slate-400">
											No records found
										</td>
									</tr>
								) : (
									rows.map((row, idx) => (
										<tr key={row.appl_no || idx}
											className={`${idx % 2 === 0 ? "bg-white" : "bg-slate-50"} hover:bg-blue-50 transition-colors`}>
											<td className="py-3 px-4 text-sm whitespace-nowrap text-gray-600">{row.tgl}</td>
											<td className="py-3 px-4 text-sm whitespace-nowrap">
												<a href={camHref(row)} target="_parent"
													className={`underline-offset-2 hover:underline ${COLOR_MAP[row.color]}`}>
													{camLabel(row)}
												</a>
											</td>
											<td className={`py-3 px-4 text-sm ${COLOR_MAP[row.color]}`}>{row.lessee_nm}</td>
											<td className={`py-3 px-4 text-sm ${COLOR_MAP[row.color]}`}>{row.appr_id}</td>
											<td className={`py-3 px-4 text-sm ${COLOR_MAP[row.color]}`}>{row.cbgnow}</td>
											<td className="py-3 px-4 text-sm whitespace-nowrap">
												{row.can_withdraw && (
													<button
														onClick={() => setWithdrawTarget({ apless: row.apless, appl_no: row.appl_no })}
														className="px-3 py-1 bg-amber-500 hover:bg-amber-600 text-white rounded text-xs font-medium"
													>
														Withdraw
													</button>
												)}
											</td>
										</tr>
									))
								)}
							</tbody>
						</table>
					</div>

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
				open={!!withdrawTarget}
				title="Withdraw CAM"
				message={`Withdraw CAM ${withdrawTarget?.appl_no ?? ""} from the current approver?`}
				confirmLabel="Confirm"
				busy={withdrawing}
				onOk={doWithdraw}
				onCancel={() => setWithdrawTarget(null)}
			/>
		</div>
	);
};

export default CamInProgressPage;