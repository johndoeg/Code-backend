import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import api from "../../../api/axiosInstance";

const today = new Date().toISOString().slice(0, 10);

type CustomerType = 'PR' | 'PT';
type AksesType = 'View' | 'Viewx' | 'Editor';

interface DetailData {
	no: number;
	customer_type: CustomerType;
	name: string;
	alias_name: string;
	address: string;
	phone: string;
	npwp: string;
	id_card: string;
	birth: string;
	spouse_name: string;
	mother: string;
	es_birth: string;
	contact_person: string;
	contact_address: string;
	group_code: string;
	reason_category: number | null;
	reason_other: string;
	remark: string;
	create_user: string;
	create_date: string;
	last_user: string;
	last_update: string;
	apless: string;
	ppatk_files: string[];
}

interface Director {
	name: string;
	position: string;
	other: string;
	id: number;
	type: 'bod' | 'boc';
}

interface MgmtRow {
	name: string;
	id_card: string;
	address: string;
	city: string;
	image: string;
	id: number;
}

interface PositionOption {
	value: string;
	label: string;
}

interface ManagementData {
	directors: Director[];
	management: MgmtRow[];
	bod_options: PositionOption[];
	boc_options: PositionOption[];
}

interface Group { code: string; name: string; }
interface Reason { value: string; label: string; disabled: boolean; }

const inputCls = (readonly: boolean) =>
	`w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-amber-500 focus:border-transparent focus:outline-none transition-shadow ${readonly ? 'bg-gray-50 text-gray-600 cursor-default border-gray-200' : 'border-gray-300'
	}`;

const Field = ({
	label, required, children,
}: { label: string; required?: boolean; children: React.ReactNode }) => (
	<div>
		<label className="block text-sm font-medium text-gray-700 mb-1">
			{label}{required && <span className="text-red-500 ml-0.5">*</span>}
		</label>
		{children}
	</div>
);

const ErrorBanner = ({ errors, onClose }: { errors: string[]; onClose: () => void }) => (
	<div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4 flex justify-between gap-3">
		<ul className="list-disc list-inside space-y-0.5">
			{errors.map((e, i) => <li key={i} className="text-sm text-red-700">{e}</li>)}
		</ul>
		<button onClick={onClose} className="text-red-400 hover:text-red-600 text-xl leading-none flex-shrink-0">×</button>
	</div>
);

const Badge = ({ type }: { type: CustomerType }) => (
	<span style={{
		fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 20,
		background: type === 'PR' ? '#dbeafe' : '#fef3c7',
		color: type === 'PR' ? '#1e40af' : '#92400e',
	}}>
		{type === 'PR' ? 'Individual' : 'Corporate'}
	</span>
);

const WatchlistEditPage: React.FC = () => {
	const [searchParams] = useSearchParams();
	const navigate = useNavigate();

	const no = searchParams.get('no') || '';
	const akses = (searchParams.get('akses') || 'View') as AksesType;
	const menuId = searchParams.get('menu_id') || '';

	const isReadonly = akses === 'View' || akses === 'Viewx';

	const [data, setData] = useState<DetailData | null>(null);
	const [loading, setLoading] = useState(true);
	const [errors, setErrors] = useState<string[]>([]);
	const [saving, setSaving] = useState(false);
	const [saved, setSaved] = useState(false);

	const [form, setForm] = useState<Partial<DetailData>>({});

	const [groups, setGroups] = useState<Group[]>([]);
	const [reasons, setReasons] = useState<Reason[]>([]);

	const [bodOpen, setBodOpen] = useState(false);
	const [mgmtData, setMgmtData] = useState<ManagementData | null>(null);
	const [mgmtLoad, setMgmtLoad] = useState(false);

	const [ppatkFiles, setPpatkFiles] = useState<string[]>([]);
	const [ppatkUploading, setPpatkUploading] = useState(false);
	const ppatkRef = useRef<HTMLInputElement>(null);

	const fetchDetail = useCallback(async () => {
		if (!no) return;
		setLoading(true);
		setErrors([]);
		try {
			const { data: d } = await api.get('/MasterData/api/watchlist/detail', {
				params: { no }
			});
			setData(d);
			setForm(d);
			setPpatkFiles(d.ppatk_files || []);
		} catch (err: any) {
			setErrors([err?.response?.data?.error || 'Failed to load record.']);
		} finally {
			setLoading(false);
		}
	}, [no]);

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

	useEffect(() => { fetchDetail(); fetchCombos(); }, [fetchDetail, fetchCombos]);

	const setField = (key: keyof DetailData, value: string) =>
		setForm(f => ({ ...f, [key]: value }));

	const handleSave = async () => {
		setSaving(true);
		setErrors([]);
		setSaved(false);
		try {
			await api.post('/MasterData/api/watchlist/update',
				{ ...form, no });
			setSaved(true);
			await fetchDetail();
		} catch (err: any) {
			const errs = err?.response?.data?.errors;
			setErrors(Array.isArray(errs) ? errs : ['Save failed. Please try again.']);
		} finally {
			setSaving(false);
		}
	};

	const openBodModal = async () => {
		setBodOpen(true);
		setMgmtLoad(true);
		try {
			const { data: d } = await api.get('/MasterData/api/watchlist/management', {
				params: {
					npwp: form.npwp, name: form.name,
					reason_category: form.reason_category,
				}
			});
			setMgmtData(d);
		} catch {  }
		finally { setMgmtLoad(false); }
	};

	const handlePpatkUpload = async (file: File) => {
		setPpatkUploading(true);
		const fd = new FormData();
		fd.append('apless', form.apless || data?.apless || '');
		fd.append('fileppatk', file);
		try {
			const { data: r } = await api.post(
				'/MasterData/api/watchlist/upload-ppatk', fd,
				{ headers: { 'Content-Type': 'multipart/form-data' } }
			);
			if (r.success) setPpatkFiles(f => [...f, r.fname]);
		} catch { setErrors(['PPATK file upload failed.']); }
		finally { setPpatkUploading(false); }
	};

	const handlePpatkDelete = async (fname: string) => {
		try {
			await api.post('/MasterData/api/watchlist/delete-ppatk',
				{ fname, apless: form.apless || data?.apless });
			setPpatkFiles(f => f.filter(x => x !== fname));
		} catch { setErrors(['Failed to delete file.']); }
	};

	const handleDeleteAttach = async (mgmtName: string) => {
		try {
			await api.post('/MasterData/api/watchlist/delete-attach',
				{ npwp: form.npwp, management_name: mgmtName });
			setMgmtData(d => d ? {
				...d,
				management: d.management.map(m =>
					m.name === mgmtName ? { ...m, image: '' } : m
				),
			} : d);
		} catch { setErrors(['Failed to delete attachment.']); }
	};

	if (loading) return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center">
			<div className="animate-spin rounded-full h-10 w-10 border-b-2 border-amber-500" />
		</div>
	);

	if (!data) return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center">
			<p className="text-gray-500">Record not found.</p>
		</div>
	);

	const ctype = (form.customer_type || data.customer_type) as CustomerType;
	const reason_cat = String(form.reason_category ?? data.reason_category ?? '');
	const locked = reason_cat === '8';

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-6xl mx-auto space-y-5">

				<div className="bg-white rounded-2xl shadow-lg px-6 py-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
					<div className="flex items-center gap-3">
						<button
							onClick={() => navigate(`/watchlist?menu_id=${menuId}`)}
							className="text-gray-400 hover:text-gray-600 transition-colors"
							title="Back to list"
						>
							<svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
							</svg>
						</button>
						<div>
							<div className="flex items-center gap-2">
								<h1 className="text-xl font-bold text-gray-800">Watchlist Detail</h1>
								<Badge type={ctype} />
								{isReadonly && (
									<span className="bg-gray-100 text-gray-500 text-xs px-2 py-0.5 rounded-full font-medium">
										Read-only
									</span>
								)}
							</div>
							<p className="text-sm text-gray-500 mt-0.5">No. {data.no} · {data.name}</p>
						</div>
					</div>

					<div className="flex gap-2">
						{akses === 'Editor' && (
							<button
								onClick={handleSave}
								disabled={saving}
								className={`px-5 py-2 rounded-lg text-sm text-white font-medium flex items-center gap-2 transition-colors ${saving ? 'bg-amber-400 cursor-not-allowed' : 'bg-amber-600 hover:bg-amber-700'
									}`}
							>
								{saving && (
									<svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
										<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
										<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
									</svg>
								)}
								{saving ? 'Saving…' : 'Save'}
							</button>
						)}
						<button
							onClick={() => navigate(`/watchlist?menu_id=${menuId}`)}
							className="px-5 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50 transition-colors"
						>
							Cancel
						</button>
					</div>
				</div>

				{saved && (
					<div className="bg-green-50 border border-green-200 rounded-lg px-4 py-3 flex items-center gap-2 text-green-700 text-sm">
						<svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
						</svg>
						Record saved successfully.
					</div>
				)}

				{errors.length > 0 && (
					<ErrorBanner errors={errors} onClose={() => setErrors([])} />
				)}

				<div className="bg-white rounded-2xl shadow-lg p-6">
					<div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-5">

						<div className="space-y-4">
							<h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider border-b pb-1">
								{ctype === 'PR' ? 'Personal Information' : 'Company Information'}
							</h3>

							<Field label="Customer Type">
								<div className="flex gap-6 mt-1">
									{(['PR', 'PT'] as CustomerType[]).map(t => (
										<label key={t} className="flex items-center gap-2 cursor-not-allowed">
											<input type="radio" disabled checked={ctype === t} readOnly className="accent-amber-600" />
											<span className="text-sm text-gray-600">{t === 'PR' ? 'Individual' : 'Corporate'}</span>
										</label>
									))}
								</div>
							</Field>

							<Field label="Name" required>
								<input type="text" value={form.name ?? ''} readOnly={isReadonly || locked}
									onChange={e => setField('name', e.target.value)}
									className={inputCls(isReadonly || locked)} />
							</Field>

							{ctype === 'PR' && (
								<Field label="Alias Name">
									<input type="text" value={form.alias_name ?? ''} readOnly={isReadonly || locked}
										onChange={e => setField('alias_name', e.target.value)}
										className={inputCls(isReadonly || locked)} />
								</Field>
							)}

							<Field label="Address" required>
								<textarea value={form.address ?? ''} readOnly={isReadonly || locked}
									onChange={e => setField('address', e.target.value)}
									rows={3} className={`${inputCls(isReadonly || locked)} resize-none`} />
							</Field>

							<Field label="Phone">
								<input type="tel" value={form.phone ?? ''} readOnly={isReadonly || locked}
									onChange={e => setField('phone', e.target.value.replace(/\D/g, ''))}
									className={inputCls(isReadonly || locked)} />
							</Field>

							{ctype === 'PR' && (<>
								<Field label="ID Card No." required>
									<input type="text" value={form.id_card ?? ''} readOnly={isReadonly || locked}
										onChange={e => setField('id_card', e.target.value.replace(/\D/g, ''))}
										className={inputCls(isReadonly || locked)} maxLength={16} />
								</Field>
								<Field label="Date of Birth">
									<input type="date" value={form.birth ?? ''} readOnly={isReadonly || locked}
										max={today} onChange={e => setField('birth', e.target.value)}
										className={inputCls(isReadonly || locked)} />
								</Field>
								<Field label="NPWP">
									<input type="text" value={form.npwp ?? ''} readOnly={isReadonly || locked}
										onChange={e => setField('npwp', e.target.value.replace(/\D/g, ''))}
										className={inputCls(isReadonly || locked)} maxLength={15} />
								</Field>
								<Field label="Spouse Name">
									<input type="text" value={form.spouse_name ?? ''} readOnly={isReadonly || locked}
										onChange={e => setField('spouse_name', e.target.value)}
										className={inputCls(isReadonly || locked)} />
								</Field>
								<Field label="Mother's Maiden Name">
									<input type="text" value={form.mother ?? ''} readOnly={isReadonly || locked}
										onChange={e => setField('mother', e.target.value)}
										className={inputCls(isReadonly || locked)} />
								</Field>
							</>)}

							{ctype === 'PT' && (<>
								<Field label="NPWP" required>
									<input type="text" value={form.npwp ?? ''} readOnly={isReadonly || locked}
										onChange={e => setField('npwp', e.target.value.replace(/\D/g, ''))}
										className={inputCls(isReadonly || locked)} maxLength={15} />
								</Field>
								<Field label="Establishment Date">
									<input type="date" value={form.es_birth ?? ''} readOnly={isReadonly || locked}
										max={today} onChange={e => setField('es_birth', e.target.value)}
										className={inputCls(isReadonly || locked)} />
								</Field>
								<div className="pt-1">
									<p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3 border-b pb-1">
										Contact Person
									</p>
									<div className="space-y-4">
										<Field label="Name">
											<input type="text" value={form.contact_person ?? ''} readOnly={isReadonly || locked}
												onChange={e => setField('contact_person', e.target.value)}
												className={inputCls(isReadonly || locked)} />
										</Field>
										<Field label="Address">
											<textarea value={form.contact_address ?? ''} readOnly={isReadonly || locked}
												onChange={e => setField('contact_address', e.target.value)}
												rows={2} className={`${inputCls(isReadonly || locked)} resize-none`} />
										</Field>
										<Field label="Group">
											<select value={form.group_code ?? ''} disabled={isReadonly || locked}
												onChange={e => setField('group_code', e.target.value)}
												className={inputCls(isReadonly || locked)}>
												<option value="">— Select —</option>
												{groups.map(g => (
													<option key={g.code} value={g.code}>{g.name}</option>
												))}
											</select>
										</Field>
									</div>
								</div>

								{!locked && (
									<Field label="Composition BOD / BOC">
										<button type="button" onClick={openBodModal}
											className="px-4 py-2 border border-amber-400 text-amber-700 hover:bg-amber-50 rounded-lg text-sm font-medium transition-colors">
											View / Edit Structure
										</button>
									</Field>
								)}
							</>)}
						</div>

						<div className="space-y-4">
							<h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider border-b pb-1">
								Case Information
							</h3>

							<Field label="Reason" required>
								<select value={reason_cat}
									disabled={isReadonly || locked}
									onChange={e => setField('reason_category', e.target.value)}
									className={inputCls(isReadonly || locked)}>
									<option value="">— Select —</option>
									{reasons.map(r => (
										<option key={r.value} value={r.value} disabled={r.disabled}>
											{r.label}
										</option>
									))}
								</select>
							</Field>

							{reason_cat === '5' && (
								<Field label="Reason Other" required>
									<textarea value={form.reason_other ?? ''} readOnly={isReadonly || locked}
										onChange={e => setField('reason_other', e.target.value)}
										rows={2} className={`${inputCls(isReadonly || locked)} resize-none`} />
								</Field>
							)}

							<Field label="Remark">
								<textarea value={form.remark ?? ''} readOnly={isReadonly}
									onChange={e => setField('remark', e.target.value)}
									rows={4} maxLength={1000}
									className={`${inputCls(isReadonly)} resize-none`} />
							</Field>

							<div className="grid grid-cols-2 gap-3">
								<Field label="Create By">
									<input type="text" value={data.create_user} readOnly className={inputCls(true)} />
								</Field>
								<Field label="Create Date">
									<input type="date" value={data.create_date} readOnly className={inputCls(true)} />
								</Field>
							</div>

							{(data.last_user || data.last_update) && (
								<div className="grid grid-cols-2 gap-3">
									<Field label="Updated By">
										<input type="text" value={data.last_user} readOnly className={inputCls(true)} />
									</Field>
									<Field label="Last Update">
										<input type="date" value={data.last_update} readOnly className={inputCls(true)} />
									</Field>
								</div>
							)}

							{locked && (
								<div className="pt-2">
									<p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3 border-b pb-1">
										Attachments (PPATK)
									</p>

									{ppatkFiles.map(fname => (
										<div key={fname} className="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2 mb-2 text-sm">
											<span className="truncate text-gray-700 font-mono text-xs">{fname}</span>
											<div className="flex gap-2 flex-shrink-0 ml-2">
												<a
													href={`/MasterData/ppatk/view?fname=${encodeURIComponent(fname)}`}
													target="_blank" rel="noreferrer"
													className="text-amber-600 hover:underline text-xs font-medium"
												>View</a>
												{akses === 'Editor' && (
													<button onClick={() => handlePpatkDelete(fname)}
														className="text-red-500 hover:text-red-700 text-xs font-medium">
														Delete
													</button>
												)}
											</div>
										</div>
									))}

									{akses === 'Editor' && ppatkFiles.length < 3 && (
										<div
											onClick={() => ppatkRef.current?.click()}
											className="border-2 border-dashed border-amber-200 hover:border-amber-400 rounded-lg p-3 text-center cursor-pointer transition-colors"
										>
											<input
												ref={ppatkRef} type="file"
												accept=".pdf,.jpg,.jpeg,.png,.doc,.docx"
												className="hidden"
												onChange={e => {
													const f = e.target.files?.[0];
													if (f) { handlePpatkUpload(f); e.target.value = ''; }
												}}
											/>
											{ppatkUploading
												? <span className="text-xs text-gray-400">Uploading…</span>
												: <span className="text-xs text-gray-400">+ Upload file (max 2 MB)</span>
											}
										</div>
									)}
									{ppatkFiles.length === 0 && <p className="text-xs text-gray-400 mt-1">No attachments yet.</p>}
								</div>
							)}
						</div>
					</div>
				</div>
			</div>

			{bodOpen && (
				<div className="fixed inset-0 bg-black bg-opacity-50 flex items-start justify-center z-50 p-4 overflow-y-auto">
					<div className="bg-white rounded-2xl shadow-2xl w-full max-w-5xl my-8">

						<div className="flex justify-between items-center px-6 py-5 border-b">
							<div>
								<h2 className="text-lg font-bold text-gray-800">
									Composition of BOD &amp; BOC
								</h2>
								<p className="text-sm text-gray-500 mt-0.5">Susunan Direksi &amp; Dewan Komisaris</p>
							</div>
							<button onClick={() => setBodOpen(false)} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">×</button>
						</div>

						<div className="p-6 space-y-6">
							{mgmtLoad ? (
								<div className="flex justify-center py-10">
									<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-500" />
								</div>
							) : mgmtData ? (<>

								<div>
									<h3 className="text-sm font-semibold text-gray-600 mb-3">Directors &amp; Commissioners</h3>
									<div className="overflow-x-auto rounded-xl border border-gray-200">
										<table className="w-full text-sm">
											<thead className="bg-gray-50">
												<tr>
													{['No.', 'Name', 'BOD Position', 'BOC Position', 'Other'].map(h => (
														<th key={h} className="py-2 px-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">{h}</th>
													))}
												</tr>
											</thead>
											<tbody className="divide-y divide-gray-100">
												{mgmtData.directors.length === 0 ? (
													<tr><td colSpan={5} className="py-8 text-center text-gray-400 text-xs">No directors registered</td></tr>
												) : mgmtData.directors.map((d, i) => (
													<tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'}>
														<td className="py-2 px-3 text-gray-500">{i + 1}</td>
														<td className="py-2 px-3 font-medium text-gray-800">{d.name}</td>
														<td className="py-2 px-3">
															{d.type === 'bod' ? (
																<span className="bg-blue-100 text-blue-800 text-xs px-2 py-0.5 rounded-full">
																	{mgmtData.bod_options.find(o => o.value === d.position)?.label || d.position}
																</span>
															) : '—'}
														</td>
														<td className="py-2 px-3">
															{d.type === 'boc' ? (
																<span className="bg-purple-100 text-purple-800 text-xs px-2 py-0.5 rounded-full">
																	{mgmtData.boc_options.find(o => o.value === d.position)?.label || d.position}
																</span>
															) : '—'}
														</td>
														<td className="py-2 px-3 text-gray-500 text-xs">{d.other || '—'}</td>
													</tr>
												))}
											</tbody>
										</table>
									</div>
								</div>

								<div>
									<h3 className="text-sm font-semibold text-gray-600 mb-3">Management Detail Information</h3>
									<div className="overflow-x-auto rounded-xl border border-gray-200">
										<table className="w-full text-sm">
											<thead className="bg-gray-50">
												<tr>
													{['No.', 'Name', 'ID Card', 'Address', 'City', 'Image'].map(h => (
														<th key={h} className="py-2 px-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">{h}</th>
													))}
												</tr>
											</thead>
											<tbody className="divide-y divide-gray-100">
												{mgmtData.management.length === 0 ? (
													<tr><td colSpan={6} className="py-8 text-center text-gray-400 text-xs">No management detail</td></tr>
												) : mgmtData.management.map((m, i) => (
													<tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'}>
														<td className="py-2 px-3 text-gray-500">{i + 1}</td>
														<td className="py-2 px-3 font-medium text-gray-800">{m.name}</td>
														<td className="py-2 px-3 font-mono text-xs text-gray-600">{m.id_card || '—'}</td>
														<td className="py-2 px-3 text-gray-600 max-w-xs truncate">{m.address || '—'}</td>
														<td className="py-2 px-3 text-gray-600">{m.city || '—'}</td>
														<td className="py-2 px-3">
															{m.image ? (
																<div className="flex gap-2 items-center">
																	<span className="text-xs text-green-600 font-medium">✓ Has image</span>
																	{akses === 'Editor' && !locked && (
																		<button onClick={() => handleDeleteAttach(m.name)}
																			className="text-red-400 hover:text-red-600 text-xs">Delete</button>
																	)}
																</div>
															) : (
																<span className="text-xs text-gray-400">—</span>
															)}
														</td>
													</tr>
												))}
											</tbody>
										</table>
									</div>
								</div>
							</>) : (
								<p className="text-center text-gray-400 text-sm py-8">Failed to load management data.</p>
							)}
						</div>

						<div className="flex justify-end px-6 py-4 border-t bg-gray-50 rounded-b-2xl">
							<button onClick={() => setBodOpen(false)}
								className="px-5 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-100 transition-colors">
								Close
							</button>
						</div>
					</div>
				</div>
			)}
		</div>
	);
};

export default WatchlistEditPage;