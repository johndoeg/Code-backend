import React, { useEffect, useState, useCallback, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import api from "../../../api/axiosInstance";
import Pagination from "../../../helpers/Pagination";
import { DEFAULT_PAGE_LIMIT } from '../../../constants/DefaultValue';

type CustomerType = "PR" | "PT";

interface WatchlistEntryPage {
	no: number;
	display_id: string;
	id_card: string;
	npwp: string;
	name: string;
	address: string;
	apless: string;
	customer_type: CustomerType;
	reason_category: number | null;
}

interface Reason {
	value: string;
	label: string;
	disabled: boolean;
}

interface Group {
	code: string;
	name: string;
}

interface AddForm {
	name: string;
	alias_name: string;
	address: string;
	phone: string;
	id_card: string;
	birth: string;
	spouse_name: string;
	mother: string;
	npwp: string;
	contact_person: string;
	contact_address: string;
	group_code: string;
	es_birth: string;
	reason: string;
	reason_other: string;
	remark: string;
	create_date: string;
}

const today = new Date().toISOString().slice(0, 10);

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
	"w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-amber-500 focus:border-transparent focus:outline-none transition-shadow";

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

const WatchlistEntryPage: React.FC = () => {
	const navigate = useNavigate();
	const [searchParams] = useSearchParams();
	const menuId = searchParams.get("menu_id") ?? "";

	const [entries, setEntries] = useState<WatchlistEntryPage[]>([]);
	const [total, setTotal] = useState(0);
	const [page, setPage] = useState(1);
	const [loading, setLoading] = useState(true);
	const [listErrors, setListErrors] = useState<string[]>([]);

	const [searchBy, setSearchBy] = useState("2");
	const [searchVal, setSearchVal] = useState("");
	const [appliedSearch, setAppliedSearch] = useState({ by: "2", val: "" });

	const limit = DEFAULT_PAGE_LIMIT;
	const totalPages = Math.ceil(total / limit);

	const [reasons, setReasons] = useState<Reason[]>([]);
	const [groups, setGroups] = useState<Group[]>([]);

	const [addOpen, setAddOpen] = useState(false);
	const [addErrors, setAddErrors] = useState<string[]>([]);
	const [addLoading, setAddLoading] = useState(false);
	const [custType, setCustType] = useState<CustomerType>("PR");
	const [addForm, setAddForm] = useState<AddForm>({
		name: "",
		alias_name: "",
		address: "",
		phone: "",
		id_card: "",
		birth: "",
		spouse_name: "",
		mother: "",
		npwp: "",
		contact_person: "",
		contact_address: "",
		group_code: "",
		es_birth: "",
		reason: "",
		reason_other: "",
		remark: "",
		create_date: today,
	});

	const [deleteOpen, setDeleteOpen] = useState(false);
	const [deleteTarget, setDeleteTarget] = useState<WatchlistEntryPage | null>(null);
	const [deleteReason, setDeleteReason] = useState("");
	const [deleteFile, setDeleteFile] = useState<File | null>(null);
	const [deleteErrors, setDeleteErrors] = useState<string[]>([]);
	const [deleteLoading, setDeleteLoading] = useState(false);
	const fileInputRef = useRef<HTMLInputElement>(null);

	const fetchList = useCallback(async () => {
		setLoading(true);
		setListErrors([]);
		try {
			const { data } = await api.get('/MasterData/api/watchlist', {
				params: {
					page,
					limit,
					search_by: appliedSearch.by,
					search_val: appliedSearch.val,
				}
			});
			setEntries(data.data || []);
			setTotal(data.total || 0);
		} catch {
			setListErrors(["Failed to load watchlist data. Please try again."]);
		} finally {
			setLoading(false);
		}
	}, [page, appliedSearch]);

	const fetchCombos = useCallback(async () => {
		try {
			const [r, g] = await Promise.all([
				api.get('/MasterData/api/watchlist/reasons'),
				api.get('/MasterData/api/watchlist/groups'),
			]);
			setReasons(r.data || []);
			setGroups(g.data || []);
		} catch { }
	}, []);

	useEffect(() => {
		fetchList();
	}, [fetchList]);

	useEffect(() => {
		fetchCombos();
	}, [fetchCombos]);

	const handleSearch = () => {
		setPage(1);
		setAppliedSearch({ by: searchBy, val: searchVal });
	};

	const handleSearchKey = (e: React.KeyboardEvent) => {
		if (e.key === "Enter") handleSearch();
	};

	const openAdd = () => {
		setAddForm({
			name: "",
			alias_name: "",
			address: "",
			phone: "",
			id_card: "",
			birth: "",
			spouse_name: "",
			mother: "",
			npwp: "",
			contact_person: "",
			contact_address: "",
			group_code: "",
			es_birth: "",
			reason: "",
			reason_other: "",
			remark: "",
			create_date: today,
		});
		setCustType("PR");
		setAddErrors([]);
		setAddOpen(true);
	};

	const setField = (field: keyof AddForm, value: string) =>
		setAddForm((f) => ({ ...f, [field]: value }));

	const handleSave = async () => {
		setAddLoading(true);
		setAddErrors([]);
		try {
			await api.post(
				'/MasterData/api/watchlist/save',
				{ ...addForm, customer_type: custType }
			);
			setAddOpen(false);
			fetchList();
		} catch (err: any) {
			const errs = err?.response?.data?.errors;
			setAddErrors(
				Array.isArray(errs) ? errs : ["Save failed. Please try again."]
			);
		} finally {
			setAddLoading(false);
		}
	};

	const openDelete = (entry: WatchlistEntryPage) => {
		setDeleteTarget(entry);
		setDeleteReason("");
		setDeleteFile(null);
		setDeleteErrors([]);
		setDeleteOpen(true);
	};

	const handleDelete = async () => {
		if (!deleteTarget) return;
		setDeleteLoading(true);
		setDeleteErrors([]);
		const fd = new FormData();
		fd.append("no", String(deleteTarget.no));
		fd.append("reason_delete", deleteReason);
		if (deleteFile) fd.append("attachment_delete", deleteFile);

		try {
			await api.post('/MasterData/api/watchlist/delete', fd, {
				headers: { "Content-Type": "multipart/form-data" },
			});
			setDeleteOpen(false);
			fetchList();
		} catch (err: any) {
			const errs = err?.response?.data?.errors;
			setDeleteErrors(
				Array.isArray(errs) ? errs : ["Delete failed. Please try again."]
			);
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
								Watchlist Entry
							</h1>
							<p className="text-gray-500 mt-1 text-sm">
								Manage watchlisted customers (Individual &amp; Corporate)
							</p>
						</div>
						<div className="flex items-center gap-3">
							<span className="bg-amber-100 text-amber-800 px-3 py-1 rounded-full text-sm font-medium">
								Total: {total}
							</span>
							<button
								onClick={openAdd}
								className="bg-amber-600 hover:bg-amber-700 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors"
							>
								<svg
									className="w-4 h-4"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
								>
									<path
										strokeLinecap="round"
										strokeLinejoin="round"
										strokeWidth={2}
										d="M12 4v16m8-8H4"
									/>
								</svg>
								Add Watchlist
							</button>
						</div>
					</div>

					<div className="flex flex-col sm:flex-row gap-3 mb-6">
						<select
							value={searchBy}
							onChange={(e) => setSearchBy(e.target.value)}
							className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-amber-500 focus:outline-none"
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
							className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-amber-500 focus:outline-none"
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
									{[
										"No.",
										"ID Card / NPWP",
										"Name",
										"Address",
										"Type",
										"Action",
									].map((h) => (
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
												<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-500" />
											</div>
										</td>
									</tr>
								) : entries.length === 0 ? (
									<tr>
										<td
											colSpan={6}
											className="py-16 text-center text-gray-400 text-sm"
										>
											No records found
										</td>
									</tr>
								) : (
									entries.map((entry, i) => (
										<tr
											key={entry.no}
											className={`hover:bg-amber-50/30 transition-colors ${i % 2 === 0 ? "bg-white" : "bg-gray-50/50"
												}`}
										>
											<td className="py-3 px-4 text-sm text-gray-500 text-center">
												{(page - 1) * limit + i + 1}
											</td>
											<td className="py-3 px-4 text-sm font-mono text-gray-800">
												{entry.display_id}
											</td>
											<td className="py-3 px-4 text-sm font-medium text-gray-900">
												{entry.name}
											</td>
											<td className="py-3 px-4 text-sm text-gray-600 max-w-xs truncate">
												{entry.address}
											</td>
											<td className="py-3 px-4">
												<Badge type={entry.customer_type} />
											</td>
											<td className="py-3 px-4">
												<div className="flex gap-2 flex-wrap">
													<button
														onClick={() =>
															navigate(
																`/watchlist/edit?no=${entry.no}&akses=Editor&menu_id=${menuId}`
															)
														}
														className="bg-amber-500 hover:bg-amber-600 text-white px-3 py-1 rounded-md text-xs font-medium transition-colors"
													>
														View Detail
													</button>

													{entry.reason_category !== 8 && (
														<button
															onClick={() => openDelete(entry)}
															className="bg-red-500 hover:bg-red-600 text-white px-3 py-1 rounded-md text-xs font-medium transition-colors"
														>
															Delete
														</button>
													)}
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

			{addOpen && (
				<div className="fixed inset-0 bg-black bg-opacity-50 flex items-start justify-center z-50 p-4 overflow-y-auto">
					<div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl my-8">

						<div className="flex justify-between items-center px-6 py-5 border-b">
							<div>
								<h2 className="text-xl font-bold text-gray-800">
									Add Watchlist Entry
								</h2>
								<p className="text-sm text-gray-500 mt-0.5">
									Fill in all required fields
								</p>
							</div>
							<button
								onClick={() => setAddOpen(false)}
								className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
							>
								×
							</button>
						</div>

						<div className="p-6">
							{addErrors.length > 0 && (
								<ErrorBanner
									errors={addErrors}
									onClose={() => setAddErrors([])}
								/>
							)}

							<div className="mb-6">
								<label className="block text-sm font-semibold text-gray-700 mb-2">
									Customer Type <span className="text-red-500">*</span>
								</label>
								<div className="flex gap-4">
									{(["PR", "PT"] as CustomerType[]).map((t) => (
										<label
											key={t}
											className="flex items-center gap-2 cursor-pointer"
										>
											<input
												type="radio"
												name="customer_type"
												value={t}
												checked={custType === t}
												onChange={() => setCustType(t)}
												className="text-amber-600"
											/>
											<span className="text-sm font-medium text-gray-700">
												{t === "PR" ? "Individual" : "Corporate"}
											</span>
										</label>
									))}
								</div>
							</div>

							<div className="grid grid-cols-1 md:grid-cols-2 gap-5">

								<div className="space-y-4">
									<h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
										{custType === "PR"
											? "Personal Information"
											: "Company Information"}
									</h3>

									<Field label="Name" required>
										<input
											type="text"
											value={addForm.name}
											onChange={(e) => setField("name", e.target.value)}
											className={inputCls}
											placeholder="Full name"
										/>
									</Field>

									{custType === "PR" && (
										<Field label="Alias Name">
											<input
												type="text"
												value={addForm.alias_name}
												onChange={(e) => setField("alias_name", e.target.value)}
												className={inputCls}
												placeholder="Alias / other name"
											/>
										</Field>
									)}

									<Field label="Address" required>
										<textarea
											value={addForm.address}
											onChange={(e) => setField("address", e.target.value)}
											className={`${inputCls} resize-none`}
											rows={3}
											placeholder="Full address"
										/>
									</Field>

									<Field label="Phone">
										<input
											type="tel"
											value={addForm.phone}
											onChange={(e) =>
												setField("phone", e.target.value.replace(/\D/g, ""))
											}
											className={inputCls}
											placeholder="08xx-xxxx-xxxx"
										/>
									</Field>

									{custType === "PR" && (
										<>
											<Field label="ID Card No." required>
												<input
													type="text"
													value={addForm.id_card}
													onChange={(e) =>
														setField(
															"id_card",
															e.target.value.replace(/\D/g, "")
														)
													}
													className={inputCls}
													placeholder="16-digit KTP"
													maxLength={16}
												/>
											</Field>

											<Field label="Date of Birth">
												<input
													type="date"
													value={addForm.birth}
													max={today}
													onChange={(e) => setField("birth", e.target.value)}
													className={inputCls}
												/>
											</Field>

											<Field label="NPWP">
												<input
													type="text"
													value={addForm.npwp}
													onChange={(e) =>
														setField(
															"npwp",
															e.target.value.replace(/\D/g, "")
														)
													}
													className={inputCls}
													placeholder="15-digit NPWP"
													maxLength={15}
												/>
											</Field>

											<Field label="Spouse Name">
												<input
													type="text"
													value={addForm.spouse_name}
													onChange={(e) =>
														setField("spouse_name", e.target.value)
													}
													className={inputCls}
												/>
											</Field>

											<Field label="Mother's Maiden Name">
												<input
													type="text"
													value={addForm.mother}
													onChange={(e) => setField("mother", e.target.value)}
													className={inputCls}
												/>
											</Field>
										</>
									)}

									{custType === "PT" && (
										<>
											<Field label="NPWP" required>
												<input
													type="text"
													value={addForm.npwp}
													onChange={(e) =>
														setField(
															"npwp",
															e.target.value.replace(/\D/g, "")
														)
													}
													className={inputCls}
													placeholder="15-digit NPWP"
													maxLength={15}
												/>
											</Field>

											<Field label="Establishment Date">
												<input
													type="date"
													value={addForm.es_birth}
													max={today}
													onChange={(e) =>
														setField("es_birth", e.target.value)
													}
													className={inputCls}
												/>
											</Field>
										</>
									)}
								</div>

								<div className="space-y-4">
									<h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
										{custType === "PT" ? "Contact Person" : "Case Information"}
									</h3>

									{custType === "PT" && (
										<>
											<Field label="Contact Person Name">
												<input
													type="text"
													value={addForm.contact_person}
													onChange={(e) =>
														setField("contact_person", e.target.value)
													}
													className={inputCls}
												/>
											</Field>

											<Field label="Contact Person Address">
												<textarea
													value={addForm.contact_address}
													onChange={(e) =>
														setField("contact_address", e.target.value)
													}
													className={`${inputCls} resize-none`}
													rows={3}
												/>
											</Field>

											<Field label="Group">
												<select
													value={addForm.group_code}
													onChange={(e) =>
														setField("group_code", e.target.value)
													}
													className={inputCls}
												>
													<option value="">— Select —</option>
													{groups.map((g) => (
														<option key={g.code} value={g.code}>
															{g.name}
														</option>
													))}
												</select>
											</Field>
										</>
									)}

									<Field label="Reason" required>
										<select
											value={addForm.reason}
											onChange={(e) => setField("reason", e.target.value)}
											className={inputCls}
										>
											<option value="">— Select reason —</option>
											{reasons.map((r) => (
												<option
													key={r.value}
													value={r.value}
													disabled={r.disabled}
												>
													{r.label}
												</option>
											))}
										</select>
									</Field>

									{addForm.reason === "5" && (
										<Field label="Reason Other" required>
											<textarea
												value={addForm.reason_other}
												onChange={(e) =>
													setField("reason_other", e.target.value)
												}
												className={`${inputCls} resize-none`}
												rows={2}
												placeholder="Specify other reason…"
											/>
										</Field>
									)}

									<Field label="Remark">
										<textarea
											value={addForm.remark}
											onChange={(e) => setField("remark", e.target.value)}
											className={`${inputCls} resize-none`}
											rows={3}
										/>
									</Field>

									<Field label="Create Date">
										<input
											type="date"
											value={addForm.create_date}
											readOnly
											className={`${inputCls} bg-gray-50 cursor-not-allowed`}
										/>
									</Field>
								</div>
							</div>
						</div>

						<div className="flex justify-end gap-3 px-6 py-4 border-t bg-gray-50 rounded-b-2xl">
							<button
								onClick={() => setAddOpen(false)}
								className="px-5 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-100 transition-colors"
							>
								Cancel
							</button>
							<button
								onClick={handleSave}
								disabled={addLoading}
								className={`px-6 py-2 rounded-lg text-sm text-white font-medium transition-colors flex items-center gap-2 ${addLoading
									? "bg-amber-400 cursor-not-allowed"
									: "bg-amber-600 hover:bg-amber-700"
									}`}
							>
								{addLoading && (
									<svg
										className="animate-spin h-4 w-4"
										fill="none"
										viewBox="0 0 24 24"
									>
										<circle
											className="opacity-25"
											cx="12"
											cy="12"
											r="10"
											stroke="currentColor"
											strokeWidth="4"
										/>
										<path
											className="opacity-75"
											fill="currentColor"
											d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
										/>
									</svg>
								)}
								{addLoading ? "Saving…" : "Save Entry"}
							</button>
						</div>
					</div>
				</div>
			)}

			{deleteOpen && deleteTarget && (
				<div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
					<div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">

						<div className="flex justify-between items-center px-6 py-5 border-b">
							<div>
								<h2 className="text-lg font-bold text-gray-800">
									Delete Watchlist Entry
								</h2>
								<p className="text-sm text-gray-500 mt-0.5 font-mono">
									{deleteTarget.name}
								</p>
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
								<ErrorBanner
									errors={deleteErrors}
									onClose={() => setDeleteErrors([])}
								/>
							)}

							<div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex gap-3">
								<svg
									className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
								>
									<path
										strokeLinecap="round"
										strokeLinejoin="round"
										strokeWidth={2}
										d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
									/>
								</svg>
								<p className="text-sm text-amber-700">
									A reason and supporting memo are required. The entry will be
									soft-deleted and retained for audit purposes.
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

							<Field label="Upload Supporting Memo">
								<div
									onClick={() => fileInputRef.current?.click()}
									className="border-2 border-dashed border-gray-300 hover:border-amber-400 rounded-lg p-4 cursor-pointer transition-colors text-center"
								>
									<input
										ref={fileInputRef}
										type="file"
										className="hidden"
										accept=".pdf,.jpg,.jpeg,.png,.doc,.docx"
										onChange={(e) =>
											setDeleteFile(e.target.files?.[0] || null)
										}
									/>
									{deleteFile ? (
										<div className="flex items-center justify-center gap-2">
											<svg
												className="w-5 h-5 text-green-500"
												fill="none"
												stroke="currentColor"
												viewBox="0 0 24 24"
											>
												<path
													strokeLinecap="round"
													strokeLinejoin="round"
													strokeWidth={2}
													d="M5 13l4 4L19 7"
												/>
											</svg>
											<span className="text-sm text-gray-700">
												{deleteFile.name}
											</span>
											<button
												onClick={(e) => {
													e.stopPropagation();
													setDeleteFile(null);
													if (fileInputRef.current)
														fileInputRef.current.value = "";
												}}
												className="text-red-500 hover:text-red-700 text-xs ml-2"
											>
												Remove
											</button>
										</div>
									) : (
										<div className="text-gray-400 text-sm">
											<svg
												className="w-8 h-8 mx-auto mb-2 text-gray-300"
												fill="none"
												stroke="currentColor"
												viewBox="0 0 24 24"
											>
												<path
													strokeLinecap="round"
													strokeLinejoin="round"
													strokeWidth={1.5}
													d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
												/>
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
								className={`px-5 py-2 rounded-lg text-sm text-white font-medium transition-colors flex items-center gap-2 ${deleteLoading
									? "bg-red-400 cursor-not-allowed"
									: "bg-red-500 hover:bg-red-600"
									}`}
							>
								{deleteLoading && (
									<svg
										className="animate-spin h-4 w-4"
										fill="none"
										viewBox="0 0 24 24"
									>
										<circle
											className="opacity-25"
											cx="12"
											cy="12"
											r="10"
											stroke="currentColor"
											strokeWidth="4"
										/>
										<path
											className="opacity-75"
											fill="currentColor"
											d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
										/>
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

export default WatchlistEntryPage;