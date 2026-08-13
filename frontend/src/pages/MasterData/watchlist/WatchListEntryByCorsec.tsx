import React, { useState, useEffect } from 'react';
import api from '../../../api/axiosInstance';
import Pagination from '../../../helpers/Pagination';
import { DEFAULT_PAGE_LIMIT } from '../../../constants/DefaultValue';
import AsOfDatePicker from '../../../components/AsOfDatePickerComponent';

type LesseeType = 'PR' | 'PT';
type SearchBy = '' | '1' | '2' | '3';
type FormMode = 'create' | 'edit' | 'view';

interface EntrySummary {
	no: number;
	identitas: string;
	name: string;
	address: string;
	lessee_type: string;
	reason_category: string;
}

interface EntryDetail {
	no?: number;
	apless?: string | null;
	lessee_type: LesseeType;
	name: string;
	alias_name: string;
	address: string;
	phone: string;
	id_card: string;
	npwp: string;
	date_of_birth: string | null;
	spouse_name: string;
	mothers_maiden_name: string;
	contact_person: string;
	contact_address: string;
	contact_group_code: string;
	remark: string;
	reason_other: string;
	create_user?: string;
	create_date?: string | null;
	last_user?: string;
	last_update?: string | null;
}

interface CustomerLookupRow {
	apless: string;
	name: string;
	lessee_type: string;
	address: string;
	id_card: string | null;
	npwp: string | null;
	phone: string;
}

const PAGE_SIZE = DEFAULT_PAGE_LIMIT;

const emptyEntry = (): EntryDetail => ({
	lessee_type: 'PR',
	name: '',
	alias_name: '',
	address: '',
	phone: '',
	id_card: '',
	npwp: '',
	date_of_birth: null,
	spouse_name: '',
	mothers_maiden_name: '',
	contact_person: '',
	contact_address: '',
	contact_group_code: '',
	remark: '',
	reason_other: '',
});

const attachmentUrl = (filename: string) =>
	`/MasterData/api/files/ppatk/${encodeURIComponent(filename)}`;

const SpinnerIcon: React.FC = () => (
	<svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
		<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
		<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
	</svg>
);

const WatchListEntryByCorsec: React.FC = () => {
	const [searchBy, setSearchBy] = useState<SearchBy>('');
	const [searchVal, setSearchVal] = useState('');
	const [results, setResults] = useState<EntrySummary[]>([]);
	const [page, setPage] = useState(1);
	const [totalPages, setTotalPages] = useState(1);
	const [total, setTotal] = useState(0);
	const [loading, setLoading] = useState(false);
	const [listError, setListError] = useState<string | null>(null);

	const [formOpen, setFormOpen] = useState(false);
	const [formMode, setFormMode] = useState<FormMode>('create');
	const [formData, setFormData] = useState<EntryDetail>(emptyEntry());
	const [lockedFromPicker, setLockedFromPicker] = useState(false);
	const [formSaving, setFormSaving] = useState(false);
	const [formLoading, setFormLoading] = useState(false);
	const [formError, setFormError] = useState<string[] | string | null>(null);
	const [attachments, setAttachments] = useState<string[]>([]);
	const [uploading, setUploading] = useState(false);

	const [pickerOpen, setPickerOpen] = useState(false);
	const [pickerQuery, setPickerQuery] = useState('');
	const [pickerResults, setPickerResults] = useState<CustomerLookupRow[]>([]);
	const [pickerLoading, setPickerLoading] = useState(false);

	const [deleteNo, setDeleteNo] = useState<number | null>(null);
	const [deleteReason, setDeleteReason] = useState('');
	const [deleting, setDeleting] = useState(false);

	const fetchList = async (targetPage: number = 1) => {
		setLoading(true);
		setListError(null);
		try {
			const response = await api.get('/MasterData/api/watchlist-corsec/list', {
				params: { search_by: searchBy, search_val: searchVal, page: targetPage, page_size: PAGE_SIZE },
			});
			setResults(response.data.data);
			setPage(response.data.page);
			setTotalPages(response.data.total_pages);
			setTotal(response.data.total);
		} catch (err) {
			console.error('Watchlist entry list error:', err);
			setListError('Failed to load data. Please try again.');
		} finally {
			setLoading(false);
		}
	};

	useEffect(() => { fetchList(1); }, []);

	const handleSearch = () => fetchList(1);

	const handleClearSearch = () => {
		setSearchVal('');
		fetchList(1);
	};

	const openCreate = () => {
		setFormMode('create');
		setFormData(emptyEntry());
		setLockedFromPicker(false);
		setAttachments([]);
		setFormError(null);
		setFormOpen(true);
	};

	const loadEntry = async (no: number, mode: FormMode) => {
		setFormMode(mode);
		setFormOpen(true);
		setFormLoading(true);
		setFormError(null);
		setLockedFromPicker(true);
		try {
			const [detailRes, attachRes] = await Promise.all([
				api.get<EntryDetail>(`/MasterData/api/watchlist-corsec/${no}`),
				api.get<string[]>(`/MasterData/api/watchlist-corsec/${no}/attachments`),
			]);
			setFormData({ ...detailRes.data, no });
			setAttachments(attachRes.data);
		} catch (err) {
			console.error('Load entry error:', err);
			setFormError('Failed to load this entry. Please try again.');
		} finally {
			setFormLoading(false);
		}
	};

	const closeForm = () => setFormOpen(false);

	const updateField = <K extends keyof EntryDetail>(key: K, value: EntryDetail[K]) => {
		setFormData((prev) => ({ ...prev, [key]: value }));
	};

	const handleSave = async () => {
		setFormSaving(true);
		setFormError(null);
		try {
			if (formMode === 'create') {
				const response = await api.post('/MasterData/api/watchlist-corsec', formData);
				setFormOpen(false);
				fetchList(page);
				return response.data;
			} else if (formMode === 'edit' && formData.no) {
				await api.put(`/MasterData/api/watchlist-corsec/${formData.no}`, formData);
				setFormOpen(false);
				fetchList(page);
			}
		} catch (err: any) {
			console.error('Save entry error:', err);
			const body = err?.response?.data;
			setFormError(body?.errors ?? body?.error ?? 'Failed to save. Please try again.');
		} finally {
			setFormSaving(false);
		}
	};

	const handleUploadFiles = async (fileList: FileList | null) => {
		if (!fileList || fileList.length === 0 || !formData.no) return;
		setUploading(true);
		try {
			const body = new FormData();
			Array.from(fileList).forEach((f) => body.append('files', f));
			const response = await api.post(`/MasterData/api/watchlist-corsec/${formData.no}/attachments`, body, {
				headers: { 'Content-Type': 'multipart/form-data' },
			});
			setAttachments((prev) => [...prev, ...response.data.saved]);
		} catch (err: any) {
			console.error('Upload error:', err);
			alert(err?.response?.data?.error ?? 'Failed to upload file.');
		} finally {
			setUploading(false);
		}
	};

	const handleRemoveAttachment = async (filename: string) => {
		if (!formData.no) return;
		try {
			await api.delete(`/MasterData/api/watchlist-corsec/${formData.no}/attachments/${encodeURIComponent(filename)}`);
			setAttachments((prev) => prev.filter((f) => f !== filename));
		} catch (err) {
			console.error('Remove attachment error:', err);
			alert('Failed to remove attachment.');
		}
	};

	const openPicker = () => {
		setPickerQuery('');
		setPickerResults([]);
		setPickerOpen(true);
	};

	const runPickerSearch = async () => {
		setPickerLoading(true);
		try {
			const response = await api.get<{ data: CustomerLookupRow[] }>('/MasterData/api/customers', {
				params: { name: pickerQuery, lessee_type: formData.lessee_type },
			});
			setPickerResults(response.data.data);
		} catch (err) {
			console.error('Customer picker search error:', err);
		} finally {
			setPickerLoading(false);
		}
	};

	const selectCustomer = (row: CustomerLookupRow) => {
		setFormData((prev) => ({
			...prev,
			name: row.name,
			address: row.address,
			phone: row.phone,
			id_card: row.id_card ?? prev.id_card,
			npwp: row.npwp ?? prev.npwp,
		}));
		setLockedFromPicker(true);
		setPickerOpen(false);
	};

	const openDeleteModal = (no: number) => {
		setDeleteNo(no);
		setDeleteReason('');
	};

	const confirmDelete = async () => {
		if (!deleteNo || !deleteReason.trim()) {
			alert('Please fill the reason for delete.');
			return;
		}
		setDeleting(true);
		try {
			await api.post(`/MasterData/api/watchlist-corsec/${deleteNo}/delete`, { reason: deleteReason });
			setDeleteNo(null);
			fetchList(page);
		} catch (err: any) {
			console.error('Delete error:', err);
			alert(err?.response?.data?.error ?? 'Failed to delete. Please try again.');
		} finally {
			setDeleting(false);
		}
	};

	const readOnly = formMode === 'view';

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-6xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6 mb-6">
					<div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
						<h1 className="text-2xl md:text-3xl font-bold text-gray-800">Watchlist Entry</h1>
						<div className="flex items-center gap-3">
							<span className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm font-medium">
								Total: {total}
							</span>
							<button
								onClick={openCreate}
								className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium
								           flex items-center gap-2 transition-colors"
							>
								<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
								</svg>
								Add Watchlist Entry
							</button>
						</div>
					</div>

					<div className="flex flex-wrap gap-2 mb-6">
						<select
							value={searchBy}
							onChange={(e) => { setSearchBy(e.target.value as SearchBy); setSearchVal(''); }}
							className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
						>
							<option value="">All</option>
							<option value="1">ID Card</option>
							<option value="2">Name</option>
							<option value="3">NPWP</option>
						</select>
						<input
							type="text"
							value={searchVal}
							onChange={(e) => setSearchVal(e.target.value)}
							onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
							disabled={searchBy === ''}
							placeholder={searchBy === '' ? 'Showing all active entries' : 'Search value'}
							className="border border-gray-300 rounded-lg px-3 py-2 text-sm flex-1 min-w-[200px]
							           focus:ring-2 focus:ring-blue-500 focus:outline-none
							           disabled:bg-gray-50 disabled:text-gray-400"
						/>
						<button
							onClick={handleSearch}
							className="bg-gray-800 hover:bg-gray-900 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors"
						>
							Search
						</button>
						{searchVal && (
							<button
								onClick={handleClearSearch}
								className="border border-gray-300 text-gray-600 hover:bg-gray-50 px-4 py-2 rounded-lg text-sm transition-colors"
							>
								Clear
							</button>
						)}
					</div>

					{listError && (
						<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
							{listError}
						</div>
					)}

					<div className="overflow-x-auto rounded-lg border border-gray-200">
						<table className="w-full text-sm">
							<thead className="bg-gray-50">
								<tr>
									<th className="py-2 px-3 text-left text-xs font-medium text-gray-500 uppercase">ID Card / NPWP</th>
									<th className="py-2 px-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
									<th className="py-2 px-3 text-left text-xs font-medium text-gray-500 uppercase">Address</th>
									<th className="py-2 px-3 text-left text-xs font-medium text-gray-500 uppercase">Action</th>
								</tr>
							</thead>
							<tbody className="divide-y divide-gray-100">
								{loading ? (
									<tr><td colSpan={4} className="py-10 text-center">
										<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto" />
									</td></tr>
								) : results.length === 0 ? (
									<tr><td colSpan={4} className="py-8 text-center text-gray-500">No records found.</td></tr>
								) : (
									results.map((row) => (
										<tr key={row.no} className="hover:bg-gray-50">
											<td className="py-2 px-3">{row.identitas}</td>
											<td className="py-2 px-3">{row.name}</td>
											<td className="py-2 px-3">{row.address}</td>
											<td className="py-2 px-3">
												<div className="flex gap-2 flex-wrap">
													<button
														onClick={() => loadEntry(row.no, 'edit')}
														className="bg-blue-500 hover:bg-blue-600 text-white px-3 py-1 rounded-md text-xs font-medium transition-colors"
													>
														Edit
													</button>
													<button
														onClick={() => loadEntry(row.no, 'view')}
														className="bg-gray-500 hover:bg-gray-600 text-white px-3 py-1 rounded-md text-xs font-medium transition-colors"
													>
														View
													</button>
													<button
														onClick={() => openDeleteModal(row.no)}
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
							onPageChange={(newPage) => fetchList(newPage)}
							totalItems={total}
							itemsPerPage={PAGE_SIZE}
							className="mt-6"
						/>
					)}
				</div>
			</div>

			{formOpen && (
				<div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
					<div className="bg-white rounded-2xl shadow-xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
						<div className="flex justify-between items-center p-6 border-b">
							<h2 className="text-xl font-bold text-gray-800">
								{formMode === 'create' ? 'Add Watchlist Entry' : formMode === 'edit' ? 'Edit Watchlist Entry' : 'View Watchlist Entry'}
							</h2>
							<button onClick={closeForm} className="text-gray-400 hover:text-gray-600 transition-colors">
								<svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
								</svg>
							</button>
						</div>

						<div className="p-6 overflow-y-auto flex-grow min-h-0 space-y-4">
							{formLoading ? (
								<div className="flex justify-center py-10">
									<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
								</div>
							) : (
								<>
									{formError && (
										<div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
											{Array.isArray(formError) ? (
												<ul className="list-disc pl-5">
													{formError.map((e) => <li key={e}>{e}</li>)}
												</ul>
											) : formError}
										</div>
									)}

									<div className="flex gap-6">
										<label className="flex items-center gap-2 text-sm">
											<input
												type="radio"
												checked={formData.lessee_type === 'PR'}
												disabled={readOnly || formMode === 'edit'}
												onChange={() => updateField('lessee_type', 'PR')}
											/>
											Individual
										</label>
										<label className="flex items-center gap-2 text-sm">
											<input
												type="radio"
												checked={formData.lessee_type === 'PT'}
												disabled={readOnly || formMode === 'edit'}
												onChange={() => updateField('lessee_type', 'PT')}
											/>
											Corporate
										</label>

										{formMode === 'create' && (
											<button
												onClick={openPicker}
												className="ml-auto text-sm text-blue-600 hover:text-blue-800 hover:underline transition-colors"
											>
												Pick existing customer…
											</button>
										)}
									</div>

									<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
										<div className="md:col-span-2">
											<label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
											<input
												type="text"
												value={formData.name}
												disabled={readOnly || lockedFromPicker}
												onChange={(e) => updateField('name', e.target.value)}
												className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm disabled:bg-gray-50"
											/>
										</div>

										{formData.lessee_type === 'PR' && (
											<div>
												<label className="block text-sm font-medium text-gray-700 mb-1">Alias Name</label>
												<input
													type="text"
													value={formData.alias_name}
													disabled={readOnly}
													onChange={(e) => updateField('alias_name', e.target.value)}
													className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm disabled:bg-gray-50"
												/>
											</div>
										)}

										<div className="md:col-span-2">
											<label className="block text-sm font-medium text-gray-700 mb-1">Address</label>
											<textarea
												value={formData.address}
												disabled={readOnly || lockedFromPicker}
												onChange={(e) => updateField('address', e.target.value)}
												className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm disabled:bg-gray-50"
											/>
										</div>

										<div>
											<label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
											<input
												type="text"
												value={formData.phone}
												disabled={readOnly || lockedFromPicker}
												onChange={(e) => updateField('phone', e.target.value)}
												className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm disabled:bg-gray-50"
											/>
										</div>

										{formData.lessee_type === 'PR' ? (
											<>
												<div>
													<label className="block text-sm font-medium text-gray-700 mb-1">ID Card No.</label>
													<input
														type="text"
														value={formData.id_card}
														disabled={readOnly || lockedFromPicker}
														onChange={(e) => updateField('id_card', e.target.value)}
														className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm disabled:bg-gray-50"
													/>
												</div>
												<AsOfDatePicker
													label="Date of Birth"
													value={formData.date_of_birth ? new Date(formData.date_of_birth.split('-').reverse().join('-')) : new Date()}
													onChange={(d) => updateField('date_of_birth', d ? d.toISOString().split('T')[0] : null)}
												/>
												<div>
													<label className="block text-sm font-medium text-gray-700 mb-1">NPWP</label>
													<input
														type="text"
														value={formData.npwp}
														disabled={readOnly}
														onChange={(e) => updateField('npwp', e.target.value)}
														className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm disabled:bg-gray-50"
													/>
												</div>
												<div>
													<label className="block text-sm font-medium text-gray-700 mb-1">Spouse Name</label>
													<input
														type="text"
														value={formData.spouse_name}
														disabled={readOnly}
														onChange={(e) => updateField('spouse_name', e.target.value)}
														className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm disabled:bg-gray-50"
													/>
												</div>
												<div>
													<label className="block text-sm font-medium text-gray-700 mb-1">Mother's Maiden Name</label>
													<input
														type="text"
														value={formData.mothers_maiden_name}
														disabled={readOnly}
														onChange={(e) => updateField('mothers_maiden_name', e.target.value)}
														className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm disabled:bg-gray-50"
													/>
												</div>
											</>
										) : (
											<>
												<div>
													<label className="block text-sm font-medium text-gray-700 mb-1">NPWP</label>
													<input
														type="text"
														value={formData.npwp}
														disabled={readOnly || lockedFromPicker}
														onChange={(e) => updateField('npwp', e.target.value)}
														className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm disabled:bg-gray-50"
													/>
												</div>
												<AsOfDatePicker
													label="Establishment Date"
													value={formData.date_of_birth ? new Date(formData.date_of_birth.split('-').reverse().join('-')) : new Date()}
													onChange={(d) => updateField('date_of_birth', d ? d.toISOString().split('T')[0] : null)}
												/>
												<div>
													<label className="block text-sm font-medium text-gray-700 mb-1">Contact Person</label>
													<input
														type="text"
														value={formData.contact_person}
														disabled={readOnly}
														onChange={(e) => updateField('contact_person', e.target.value)}
														className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm disabled:bg-gray-50"
													/>
												</div>
												<div>
													<label className="block text-sm font-medium text-gray-700 mb-1">Contact Address</label>
													<textarea
														value={formData.contact_address}
														disabled={readOnly}
														onChange={(e) => updateField('contact_address', e.target.value)}
														className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm disabled:bg-gray-50"
													/>
												</div>
											</>
										)}

										<div className="md:col-span-2">
											<label className="block text-sm font-medium text-gray-700 mb-1">Remark</label>
											<textarea
												value={formData.remark}
												disabled={readOnly}
												onChange={(e) => updateField('remark', e.target.value)}
												maxLength={1000}
												className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm disabled:bg-gray-50"
											/>
										</div>
									</div>

									{(formData.create_user || formData.last_user) && (
										<div className="text-xs text-gray-500 grid grid-cols-2 gap-2 border-t pt-3">
											<div>Create by: {formData.create_user} ({formData.create_date})</div>
											{formData.last_user && (
												<div>Last update by: {formData.last_user} ({formData.last_update})</div>
											)}
										</div>
									)}

									<div className="border-t pt-4">
										<div className="flex items-center justify-between mb-2">
											<label className="text-sm font-medium text-gray-700">Supporting Documents</label>
											{!readOnly && formData.no && (
												<label className="text-xs text-blue-600 hover:text-blue-800 hover:underline transition-colors cursor-pointer">
													{uploading ? 'Uploading…' : '+ Add file'}
													<input
														type="file"
														className="hidden"
														disabled={uploading}
														onChange={(e) => handleUploadFiles(e.target.files)}
													/>
												</label>
											)}
										</div>
										{!formData.no && (
											<p className="text-xs text-gray-400">Save the entry first to attach supporting documents.</p>
										)}
										<ul className="space-y-1">
											{attachments.map((f) => (
												<li key={f} className="flex items-center justify-between text-sm bg-gray-50 rounded px-3 py-1.5">
													<a href={attachmentUrl(f)} target="_blank" rel="noreferrer" className="text-blue-600 hover:text-blue-800 hover:underline transition-colors truncate">
														{f}
													</a>
													{!readOnly && (
														<button onClick={() => handleRemoveAttachment(f)} className="text-red-600 hover:text-red-800 transition-colors text-xs ml-2">
															Remove
														</button>
													)}
												</li>
											))}
										</ul>
										<p className="text-xs text-gray-400 mt-1">Max 3 files, 2MB each.</p>
									</div>
								</>
							)}
						</div>

						<div className="p-4 border-t flex justify-end gap-3">
							<button
								onClick={closeForm}
								className="px-5 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-100 transition-colors"
							>
								{readOnly ? 'Close' : 'Cancel'}
							</button>
							{!readOnly && (
								<button
									onClick={handleSave}
									disabled={formSaving || formLoading}
									className={`px-5 py-2 rounded-lg text-sm text-white font-medium transition-colors flex items-center gap-2 ${formSaving ? 'bg-blue-400 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700'
										}`}
								>
									{formSaving && <SpinnerIcon />}
									{formSaving ? 'Saving…' : 'Save'}
								</button>
							)}
						</div>
					</div>
				</div>
			)}

			{pickerOpen && (
				<div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[60] p-4">
					<div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
						<div className="flex justify-between items-center p-4 border-b">
							<h3 className="font-bold text-gray-800">Select Customer</h3>
							<button onClick={() => setPickerOpen(false)} className="text-gray-400 hover:text-gray-600 text-2xl leading-none transition-colors">
								×
							</button>
						</div>
						<div className="p-4 border-b flex gap-2">
							<input
								type="text"
								value={pickerQuery}
								onChange={(e) => setPickerQuery(e.target.value)}
								onKeyDown={(e) => e.key === 'Enter' && runPickerSearch()}
								placeholder="Search by name"
								className="flex-1 px-3 py-2 rounded-lg border border-gray-300 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
							/>
							<button
								onClick={runPickerSearch}
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
									<tbody className="divide-y divide-gray-100">
										{pickerResults.map((row) => (
											<tr key={row.apless} className="hover:bg-gray-50 cursor-pointer transition-colors" onClick={() => selectCustomer(row)}>
												<td className="py-2 px-4">
													<div className="font-medium text-gray-800">{row.name}</div>
													<div className="text-xs text-gray-500">{row.address}</div>
												</td>
												<td className="py-2 px-4 text-right text-xs text-gray-500">{row.apless}</td>
											</tr>
										))}
										{pickerResults.length === 0 && (
											<tr><td className="py-8 text-center text-gray-400 text-sm">Search for a customer above.</td></tr>
										)}
									</tbody>
								</table>
							)}
						</div>
					</div>
				</div>
			)}

			{deleteNo !== null && (
				<div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
					<div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
						<h3 className="font-bold text-gray-800 mb-4">Delete Watchlist Entry</h3>
						<label className="block text-sm font-medium text-gray-700 mb-1">Reason for delete</label>
						<textarea
							value={deleteReason}
							onChange={(e) => setDeleteReason(e.target.value)}
							className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm mb-4"
							rows={3}
						/>
						<div className="flex justify-end gap-3">
							<button
								onClick={() => setDeleteNo(null)}
								className="px-5 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-100 transition-colors"
							>
								Cancel
							</button>
							<button
								onClick={confirmDelete}
								disabled={deleting}
								className={`px-5 py-2 rounded-lg text-sm text-white font-medium transition-colors flex items-center gap-2 ${deleting ? 'bg-red-400 cursor-not-allowed' : 'bg-red-500 hover:bg-red-600'
									}`}
							>
								{deleting && <SpinnerIcon />}
								{deleting ? 'Deleting…' : 'Delete'}
							</button>
						</div>
					</div>
				</div>
			)}
		</div>
	);
};

export default WatchListEntryByCorsec;