import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import api from "../../../api/axiosInstance";
import Pagination from "../../../helpers/Pagination";
import { DEFAULT_PAGE_LIMIT } from "../../../constants/DefaultValue";

interface Sales {
	SALES_NO: string;
	NAME: string;
	ADDRESS: string;
	IDCARD: string;
	Status: string;
	Sales_Type: string;
	IsSalesTV: boolean;
}

type SearchBy = "" | "1" | "2" | "3";

const SEARCH_BY_OPTIONS: { value: SearchBy; label: string }[] = [
	{ value: "1", label: "Sales No" },
	{ value: "2", label: "Name" },
	{ value: "3", label: "KTP" },
];

interface CopyTvInfo {
	initial_sales_no: string;
	initial_name: string;
	new_sales_no: string;
	new_name: string;
	created_by: string;
}

function CopyTvModal({
	info,
	onConfirm,
	onClose,
	busy,
}: {
	info: CopyTvInfo;
	onConfirm: () => void;
	onClose: () => void;
	busy: boolean;
}) {
	return (
		<div
			className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
			onClick={e => { if (e.target === e.currentTarget) onClose(); }}
		>
			<div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl">
				<h2 className="mb-4 text-lg font-bold text-gray-800">Copy Sales TV</h2>
				<table className="w-full text-sm">
					<tbody>
						<tr className="border-b">
							<td className="py-2 pr-4 text-gray-500">Created By</td>
							<td className="py-2 font-medium">{info.created_by}</td>
						</tr>
						<tr className="border-b">
							<td className="py-2 pr-4 text-gray-500">Initial Sales No.</td>
							<td className="py-2 font-medium">{info.initial_sales_no}</td>
							<td className="py-2 pr-4 text-gray-500 pl-6">Copied Sales No.</td>
							<td className="py-2 font-medium">{info.new_sales_no}</td>
						</tr>
						<tr>
							<td className="py-2 pr-4 text-gray-500">Initial Name</td>
							<td className="py-2 font-medium">{info.initial_name}</td>
							<td className="py-2 pr-4 text-gray-500 pl-6">Copied Name</td>
							<td className="py-2 font-medium">{info.new_name}</td>
						</tr>
					</tbody>
				</table>
				<div className="mt-6 flex justify-center gap-3">
					<button
						onClick={onConfirm}
						disabled={busy}
						className="rounded-lg bg-blue-600 px-6 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
					>
						{busy ? "Copying…" : "Copy Sales TV"}
					</button>
					<button
						onClick={onClose}
						disabled={busy}
						className="rounded-lg border border-gray-300 px-6 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
					>
						Cancel
					</button>
				</div>
			</div>
		</div>
	);
}

const SalesPage: React.FC = () => {
	const navigate = useNavigate();

	const [sales, setSales] = useState<Sales[]>([]);
	const [search, setSearch] = useState("");
	const [searchBy, setSearchBy] = useState<SearchBy>("1");
	const [page, setPage] = useState(1);
	const [total, setTotal] = useState(0);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [akses, setAkses] = useState("");

	const [copyTvInfo, setCopyTvInfo] = useState<CopyTvInfo | null>(null);
	const [copyTvTarget, setCopyTvTarget] = useState<string>("");
	const [copyTvBusy, setCopyTvBusy] = useState(false);

	const limit = DEFAULT_PAGE_LIMIT;

	const fetchSales = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			const res = await api.get("/MasterData/api/sales", {
				params: { search_val: search, search_by: searchBy, page, limit },
			});
			setSales(res.data.data ?? []);
			setTotal(res.data.total ?? 0);
			if (res.data.akses !== undefined) setAkses(String(res.data.akses));
		} catch (err) {
			console.error(err);
			setError("Failed to load sales data. Please try again.");
		} finally {
			setLoading(false);
		}
	}, [search, searchBy, page, limit]);

	useEffect(() => { fetchSales(); }, [fetchSales]);

	const handleSearch = () => {
		setPage(1);
		fetchSales();
	};

	const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
		if (e.key === "Enter") handleSearch();
	};

	const canEdit = (s: Sales) => akses === "9" && !s.IsSalesTV;

	const handleView = (s: Sales) =>
		navigate(`/sales-entry?id=View&salesno=${s.SALES_NO}&sal_type=${s.Sales_Type}`);

	const handleEdit = (s: Sales) =>
		navigate(`/sales-entry?id=Edit&salesno=${s.SALES_NO}&sal_type=${s.Sales_Type}`);

	const handleCopyTvOpen = async (salesNo: string) => {
		try {
			const res = await api.get(`/MasterData/api/sales/copy-tv-info/${salesNo}`);
			setCopyTvInfo(res.data);
			setCopyTvTarget(salesNo);
		} catch {
			setError("Failed to load Copy TV info.");
		}
	};

	const handleCopyTvConfirm = async () => {
		if (!copyTvTarget) return;
		setCopyTvBusy(true);
		try {
			const res = await api.post("/MasterData/api/sales/copy-tv", {
				initial_sales_no: copyTvTarget,
			});
			if (res.data.success) {
				setCopyTvInfo(null);
				setCopyTvTarget("");
				fetchSales();
			} else {
				setError(res.data.message || "Copy failed.");
			}
		} catch {
			setError("Failed to copy Sales TV.");
		} finally {
			setCopyTvBusy(false);
		}
	};

	const totalPages = Math.ceil(total / limit);

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="mx-auto max-w-7xl">
				<div className="mb-6 rounded-2xl bg-white p-6 shadow-lg">

					<div className="mb-6 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
						<div>
							<h1 className="text-2xl font-bold text-gray-800 md:text-3xl">Sales</h1>
							<p className="mt-1 text-gray-600">View and manage your sales records</p>
						</div>
						<div className="flex items-center gap-3">
							<span className="rounded-full bg-blue-100 px-3 py-1 text-sm font-medium text-blue-800">
								Total: {total}
							</span>
							{akses === "9" && (
								<button
									onClick={() => navigate("/sales-entry?id=Add&new=baru")}
									className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-green-500 to-emerald-600 px-4 py-2 text-sm font-medium text-white shadow hover:from-green-600 hover:to-emerald-700"
								>
									<svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
										<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
									</svg>
									Add New
								</button>
							)}
						</div>
					</div>

					<div className="mb-6 flex flex-col gap-3 md:flex-row">
						<select
							value={searchBy}
							onChange={e => setSearchBy(e.target.value as SearchBy)}
							className="rounded-lg border border-gray-300 px-3 py-3 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-500 md:w-36"
						>
							{SEARCH_BY_OPTIONS.map(o => (
								<option key={o.value} value={o.value}>{o.label}</option>
							))}
						</select>

						<div className="relative flex-1">
							<svg
								className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-400"
								viewBox="0 0 24 24" fill="none" aria-hidden="true"
							>
								<path d="M15.5 14H14.71L14.43 13.73C15.41 12.59 16 11.11 16 9.5C16 5.91 13.09 3 9.5 3C5.91 3 3 5.91 3 9.5C3 13.09 5.91 16 9.5 16C11.11 16 12.59 15.41 13.73 14.43L14 14.71V15.5L19 20.49L20.49 19L15.5 14ZM9.5 14C7.01 14 5 11.99 5 9.5C5 7.01 7.01 5 9.5 5C11.99 5 14 7.01 14 9.5C14 11.99 11.99 14 9.5 14Z" fill="currentColor" />
							</svg>
							<input
								type="text"
								placeholder={
									searchBy === "1" ? "Search by Sales No…"
										: searchBy === "2" ? "Search by Name…"
											: "Search by ID Card (KTP)…"
								}
								value={search}
								onChange={e => setSearch(e.target.value)}
								onKeyDown={handleKeyDown}
								className="w-full rounded-lg border border-gray-300 py-3 pl-10 pr-4 focus:border-blue-500 focus:ring-2 focus:ring-blue-500"
							/>
						</div>

						<button
							onClick={handleSearch}
							disabled={loading}
							className={`flex items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-blue-600 to-indigo-700 px-6 py-3 font-medium text-white shadow-md transition-all hover:from-blue-700 hover:to-indigo-800 hover:shadow-lg ${loading ? "cursor-not-allowed opacity-75" : ""}`}
						>
							{loading ? (
								<>
									<svg className="-ml-1 mr-2 h-4 w-4 animate-spin text-white" fill="none" viewBox="0 0 24 24">
										<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
										<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
									</svg>
									Searching…
								</>
							) : (
								<>
									<svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" aria-hidden="true">
										<path d="M15.5 14H14.71L14.43 13.73C15.41 12.59 16 11.11 16 9.5C16 5.91 13.09 3 9.5 3C5.91 3 3 5.91 3 9.5C3 13.09 5.91 16 9.5 16C11.11 16 12.59 15.41 13.73 14.43L14 14.71V15.5L19 20.49L20.49 19L15.5 14ZM9.5 14C7.01 14 5 11.99 5 9.5C5 7.01 7.01 5 9.5 5C11.99 5 14 7.01 14 9.5C14 11.99 11.99 14 9.5 14Z" fill="currentColor" />
									</svg>
									Search
								</>
							)}
						</button>
					</div>

					{error && (
						<div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">
							{error}
							<button onClick={fetchSales} className="ml-4 underline text-red-900">
								Retry
							</button>
						</div>
					)}

					<div className="overflow-x-auto rounded-lg border border-gray-200">
						<table className="w-full">
							<thead className="bg-gradient-to-r from-gray-50 to-gray-100">
								<tr>
									{["Sales No", "Name", "Address", "ID Card", "Status", "Actions"].map(h => (
										<th
											key={h}
											className="px-6 py-4 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
										>
											{h}
										</th>
									))}
								</tr>
							</thead>
							<tbody className="divide-y divide-gray-200">
								{sales.length === 0 && !loading ? (
									<tr>
										<td colSpan={6} className="px-6 py-10 text-center text-gray-500">
											<div className="flex flex-col items-center justify-center">
												<svg
													className="mb-4 h-16 w-16 text-gray-300"
													fill="none" stroke="currentColor" viewBox="0 0 24 24"
												>
													<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
														d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
												</svg>
												<p className="text-lg">No sales records found</p>
												<p className="mt-1 text-sm">Try adjusting your search</p>
											</div>
										</td>
									</tr>
								) : (
									<>
										{sales.map((s, idx) => (
											<tr
												key={s.SALES_NO}
												className={`transition-colors hover:bg-blue-50 ${idx % 2 === 0 ? "bg-white" : "bg-gray-50"}`}
											>
												<td className="whitespace-nowrap px-6 py-4 text-sm font-medium text-gray-900">
													{s.SALES_NO}
												</td>
												<td className="whitespace-nowrap px-6 py-4 text-sm font-medium text-gray-700">
													{s.NAME}
													{s.IsSalesTV && (
														<span className="ml-2 rounded-full bg-purple-100 px-2 py-0.5 text-xs font-semibold text-purple-700">
															TV
														</span>
													)}
												</td>
												<td className="max-w-xs truncate px-6 py-4 text-sm text-gray-600">
													{s.ADDRESS}
												</td>
												<td className="whitespace-nowrap px-6 py-4 text-sm text-gray-600">
													{s.IDCARD}
												</td>
												<td className="whitespace-nowrap px-6 py-4">
													<span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold leading-5 ${s.Status === "Active"
															? "bg-green-100 text-green-800"
															: "bg-red-100 text-red-800"
														}`}>
														{s.Status}
													</span>
												</td>
												<td className="whitespace-nowrap px-6 py-4 text-sm">
													<div className="flex items-center gap-2">
														{canEdit(s) ? (
															<button
																onClick={() => handleEdit(s)}
																className="rounded px-3 py-1 text-xs bg-blue-500 text-white hover:bg-blue-600"
															>
																Edit
															</button>
														) : (
															<button
																onClick={() => handleView(s)}
																className="rounded px-3 py-1 text-xs bg-gray-500 text-white hover:bg-gray-600"
															>
																View
															</button>
														)}

														{/* {akses === "9" && !s.IsSalesTV && (
															<button
																onClick={() => handleCopyTvOpen(s.SALES_NO)}
																className="rounded px-3 py-1 text-xs bg-purple-500 text-white hover:bg-purple-600"
															>
																Copy TV
															</button>
														)} */}
													</div>
												</td>
											</tr>
										))}

										{loading && (
											<tr>
												<td colSpan={6} className="px-6 py-4 text-center">
													<div className="flex justify-center">
														<svg className="h-6 w-6 animate-spin text-blue-600" fill="none" viewBox="0 0 24 24">
															<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
															<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
														</svg>
													</div>
												</td>
											</tr>
										)}
									</>
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
			</div>

			{copyTvInfo && (
				<CopyTvModal
					info={copyTvInfo}
					onConfirm={handleCopyTvConfirm}
					onClose={() => { setCopyTvInfo(null); setCopyTvTarget(""); }}
					busy={copyTvBusy}
				/>
			)}
		</div>
	);
};

export default SalesPage;