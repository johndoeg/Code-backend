import React, { useEffect, useState, useCallback, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import api from "../../../api/axiosInstance";
import Pagination from "../../../helpers/Pagination";
import { DEFAULT_PAGE_LIMIT } from "../../../constants/DefaultValue";

type CustomerType = "PR" | "PT";

interface BlacklistRow {
	no: number;
	id_card_npwp: string;
	name: string;
	address: string;
	apless: string;
	customer_type: CustomerType;
}

const Badge = ({ type }: { type: CustomerType }) => (
	<span
		style={{
			fontSize: 11,
			fontWeight: 600,
			padding: "2px 8px",
			borderRadius: 20,
			background: type === "PR" ? "#dbeafe" : "#fef3c7",
			color: type === "PR" ? "#1e40af" : "#92400e",
		}}
	>
		{type === "PR" ? "Individual" : "Corporate"}
	</span>
);

const ErrorBanner = ({
	errors,
	onClose,
}: {
	errors: string[];
	onClose: () => void;
}) => (
	<div
		style={{
			background: "#fef2f2",
			border: "1px solid #fecaca",
			borderRadius: 8,
			padding: "12px 16px",
			marginBottom: 16,
			display: "flex",
			justifyContent: "space-between",
			alignItems: "flex-start",
			gap: 12,
		}}
	>
		<ul style={{ margin: 0, paddingLeft: 18 }}>
			{errors.map((e, i) => (
				<li key={i} style={{ fontSize: 13, color: "#dc2626" }}>
					{e}
				</li>
			))}
		</ul>
		<button
			onClick={onClose}
			style={{
				background: "none",
				border: "none",
				cursor: "pointer",
				color: "#dc2626",
				fontSize: 18,
				lineHeight: 1,
			}}
		>
			×
		</button>
	</div>
);

const inputCls =
	"w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-red-500 focus:border-transparent focus:outline-none transition-shadow";

const Field = ({
	label,
	required,
	children,
}: {
	label: string;
	required?: boolean;
	children: React.ReactNode;
}) => (
	<div>
		<label className="block text-sm font-medium text-gray-700 mb-1">
			{label}
			{required && <span className="text-red-500 ml-0.5">*</span>}
		</label>
		{children}
	</div>
);

const BlackListEntryPage: React.FC = () => {
	const navigate = useNavigate();
	const [searchParams] = useSearchParams();
	const menuId = searchParams.get("menu_id") ?? "";

	const [rows, setRows] = useState<BlacklistRow[]>([]);
	const [total, setTotal] = useState(0);
	const [page, setPage] = useState(1);
	const [loading, setLoading] = useState(true);
	const [listErrors, setListErrors] = useState<string[]>([]);

	const [searchBy, setSearchBy] = useState("2");
	const [searchVal, setSearchVal] = useState("");
	const [appliedSearch, setAppliedSearch] = useState({ by: "2", val: "" });

	const limit = DEFAULT_PAGE_LIMIT;
	const totalPages = Math.ceil(total / limit);

	const [deleteOpen, setDeleteOpen] = useState(false);
	const [deleteTarget, setDeleteTarget] = useState<BlacklistRow | null>(null);
	const [deleteReason, setDeleteReason] = useState("");
	const [deleteFile, setDeleteFile] = useState<File | null>(null);
	const [deleteErrors, setDeleteErrors] = useState<string[]>([]);
	const [deleteLoading, setDeleteLoading] = useState(false);
	const fileInputRef = useRef<HTMLInputElement>(null);

	const fetchList = useCallback(async () => {
		setLoading(true);
		setListErrors([]);
		try {
			const { data } = await api.get("/MasterData/api/blacklist/list", {
				params: {
					page,
					limit,
					search_by: appliedSearch.by,
					search_val: appliedSearch.val,
				},
			});
			setRows(data.rows || []);
			setTotal(data.total || 0);
		} catch {
			setListErrors(["Failed to load blacklist data. Please try again."]);
		} finally {
			setLoading(false);
		}
	}, [page, appliedSearch]);

	useEffect(() => {
		fetchList();
	}, [fetchList]);

	const handleSearch = () => {
		setPage(1);
		setAppliedSearch({ by: searchBy, val: searchVal });
	};

	const handleSearchKey = (e: React.KeyboardEvent) => {
		if (e.key === "Enter") handleSearch();
	};

	const goToAddNew = () => {
		navigate(`/blacklist/new?menu_id=${menuId}`);
	};

	const goToDetail = (row: BlacklistRow) => {
		const mode = row.apless ? "view" : "edit";
		navigate(`/blacklist/${row.no}?mode=${mode}&menu_id=${menuId}`);
	};

	const openDelete = (row: BlacklistRow) => {
		setDeleteTarget(row);
		setDeleteReason("");
		setDeleteFile(null);
		setDeleteErrors([]);
		setDeleteOpen(true);
	};

	const handleDelete = async () => {
		if (!deleteTarget) return;

		if (!deleteReason) {
			setDeleteErrors(["fill the reason first"]);
			return;
		}
		if (!deleteFile) {
			setDeleteErrors(["Upload the file first"]);
			return;
		}

		setDeleteLoading(true);
		setDeleteErrors([]);
		try {
			const fd = new FormData();
			fd.append("reason", deleteReason);
			fd.append("name", deleteTarget.name);
			fd.append("address", deleteTarget.address);
			fd.append("attachment", deleteFile);

			await api.delete(`/MasterData/api/blacklist/${deleteTarget.no}`, {
				data: fd,
				headers: { "Content-Type": "multipart/form-data" },
			});

			setDeleteOpen(false);
			fetchList();
		} catch (err: any) {
			const msg = err?.response?.data?.error;
			setDeleteErrors([msg || "Delete failed. Please try again."]);
		} finally {
			setDeleteLoading(false);
		}
	};

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-7xl mx-auto">

				<div className="bg-white rounded-2xl shadow-lg p-6 mb-6">

					<div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
						<div>
							<h1 className="text-2xl md:text-3xl font-bold text-gray-800">
								Blacklist
							</h1>
							<p className="text-gray-500 mt-1 text-sm">
								Manage blacklisted customers (Individual &amp; Corporate)
							</p>
						</div>
						<div className="flex items-center gap-3">
							<span className="bg-red-100 text-red-800 px-3 py-1 rounded-full text-sm font-medium">
								Total: {total}
							</span>
							<button
								onClick={goToAddNew}
								className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors"
							>
								<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
								</svg>
								Add Blacklist
							</button>
						</div>
					</div>

					<div className="flex flex-col sm:flex-row gap-3 mb-6">
						<select
							value={searchBy}
							onChange={(e) => setSearchBy(e.target.value)}
							className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-red-500 focus:outline-none"
						>
							<option value="1">ID Card</option>
							<option value="2">Name</option>
							<option value="3">NPWP</option>
						</select>
						<input
							type="text"
							value={searchVal}
							onChange={(e) => setSearchVal(e.target.value)}
							onKeyDown={handleSearchKey}
							placeholder="Search…"
							className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-red-500 focus:outline-none"
						/>
						<button
							onClick={handleSearch}
							className="bg-gray-800 hover:bg-gray-900 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors"
						>
							Search
						</button>
						{appliedSearch.val && (
							<button
								onClick={() => {
									setSearchVal("");
									setAppliedSearch({ by: searchBy, val: "" });
									setPage(1);
								}}
								className="border border-gray-300 text-gray-600 hover:bg-gray-50 px-4 py-2 rounded-lg text-sm transition-colors"
							>
								Clear
							</button>
						)}
					</div>

					{listErrors.length > 0 && (
						<ErrorBanner errors={listErrors} onClose={() => setListErrors([])} />
					)}

					<div className="overflow-x-auto rounded-xl border border-gray-200">
						<table className="w-full">
							<thead className="bg-gradient-to-r from-gray-50 to-gray-100">
								<tr>
									{["No.", "ID Card / NPWP", "Name", "Address", "Type", "Action"].map((h) => (
										<th
											key={h}
											className="py-3 px-4 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider"
										>
											{h}
										</th>
									))}
								</tr>
							</thead>
							<tbody className="divide-y divide-gray-100">
								{loading ? (
									<tr>
										<td colSpan={6} className="py-16 text-center">
											<div className="flex justify-center">
												<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-red-500" />
											</div>
										</td>
									</tr>
								) : rows.length === 0 ? (
									<tr>
										<td colSpan={6} className="py-16 text-center text-gray-400 text-sm">
											No records found
										</td>
									</tr>
								) : (
									rows.map((row, i) => (
										<tr
											key={row.no}
											className={`hover:bg-red-50/30 transition-colors ${i % 2 === 0 ? "bg-white" : "bg-gray-50/50"}`}
										>
											<td className="py-3 px-4 text-sm text-gray-500 text-center">
												{(page - 1) * limit + i + 1}
											</td>
											<td className="py-3 px-4 text-sm font-mono text-gray-800">
												{row.id_card_npwp}
											</td>
											<td className="py-3 px-4 text-sm font-medium text-gray-900">
												{row.name}
											</td>
											<td className="py-3 px-4 text-sm text-gray-600 max-w-xs truncate">
												{row.address}
											</td>
											<td className="py-3 px-4">
												<Badge type={row.customer_type} />
											</td>
											<td className="py-3 px-4">
												<div className="flex gap-2 flex-wrap">
													<button
														onClick={() => goToDetail(row)}
														className="bg-blue-500 hover:bg-blue-600 text-white px-3 py-1 rounded-md text-xs font-medium transition-colors"
													>
														{row.apless ? "View Detail" : "Edit"}
													</button>
													<button
														onClick={() => openDelete(row)}
														className="bg-red-500 hover:bg-red-600 text-white px-3 py-1 rounded-md text-xs font-medium transition-colors"
													>
														Delete
													</button>
												</div>
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
			</div>

			{deleteOpen && deleteTarget && (
				<div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
					<div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">

						<div className="flex justify-between items-center px-6 py-5 border-b">
							<div>
								<h2 className="text-lg font-bold text-gray-800">Delete Blacklist Entry</h2>
								<p className="text-sm text-gray-500 mt-0.5 font-mono">{deleteTarget.name}</p>
							</div>
							<button
								onClick={() => setDeleteOpen(false)}
								className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
							>
								×
							</button>
						</div>

						<div className="p-6 space-y-4">
							{deleteErrors.length > 0 && (
								<ErrorBanner errors={deleteErrors} onClose={() => setDeleteErrors([])} />
							)}

							<div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex gap-3">
								<svg className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
								</svg>
								<p className="text-sm text-amber-700">
									A reason and supporting memo are required. The entry will be soft-deleted and retained for audit purposes.
								</p>
							</div>

							<Field label="Reason for Deletion" required>
								<textarea
									value={deleteReason}
									onChange={(e) => setDeleteReason(e.target.value)}
									className={`${inputCls} resize-none`}
									rows={3}
									placeholder="State the reason for removing this entry…"
								/>
							</Field>

							<Field label="Upload Supporting Memo" required>
								<div
									onClick={() => fileInputRef.current?.click()}
									className="border-2 border-dashed border-gray-300 hover:border-red-400 rounded-lg p-4 cursor-pointer transition-colors text-center"
								>
									<input
										ref={fileInputRef}
										type="file"
										className="hidden"
										accept=".pdf,.jpg,.jpeg,.png,.doc,.docx"
										onChange={(e) => setDeleteFile(e.target.files?.[0] || null)}
									/>
									{deleteFile ? (
										<div className="flex items-center justify-center gap-2">
											<svg className="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
											</svg>
											<span className="text-sm text-gray-700">{deleteFile.name}</span>
											<button
												onClick={(e) => {
													e.stopPropagation();
													setDeleteFile(null);
													if (fileInputRef.current) fileInputRef.current.value = "";
												}}
												className="text-red-500 hover:text-red-700 text-xs ml-2"
											>
												Remove
											</button>
										</div>
									) : (
										<div className="text-gray-400 text-sm">
											<svg className="w-8 h-8 mx-auto mb-2 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
											</svg>
											Click to select file (PDF, image, Word — max 2 MB)
										</div>
									)}
								</div>
							</Field>
						</div>

						<div className="flex justify-end gap-3 px-6 py-4 border-t bg-gray-50 rounded-b-2xl">
							<button
								onClick={() => setDeleteOpen(false)}
								className="px-5 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-100 transition-colors"
							>
								Cancel
							</button>
							<button
								onClick={handleDelete}
								disabled={deleteLoading}
								className={`px-5 py-2 rounded-lg text-sm text-white font-medium transition-colors flex items-center gap-2 ${deleteLoading ? "bg-red-400 cursor-not-allowed" : "bg-red-500 hover:bg-red-600"}`}
							>
								{deleteLoading && (
									<svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
										<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
										<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
									</svg>
								)}
								{deleteLoading ? "Deleting…" : "Confirm Delete"}
							</button>
						</div>
					</div>
				</div>
			)}
		</div>
	);
};

export default BlackListEntryPage;