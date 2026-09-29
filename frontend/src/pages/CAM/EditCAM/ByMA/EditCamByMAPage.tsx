import React, { useEffect, useState } from 'react';
import api from '../../../../api/axiosInstance';
import CustomerBOSearchModal from './CustomerBOSearchModal';

interface Option { value: string; label: string; }

interface IndustryState {
	level0_options: Option[]; level0_selected: string;
	level1_options: Option[]; level1_selected: string;
	level2_options: Option[]; level2_selected: string;
	level3_options: Option[]; level3_selected: string;
	level4_options: Option[]; level4_selected: string;
	level5_options: Option[]; level5_selected: string;
}

interface BOFormFields {
	bo_name?: string; alias?: string; bo_cat?: string; mobile_phone1?: string; email1?: string; id_card?: string;
	placebirth?: string; tglbirth?: string; gender?: string; marital?: string; citizen?: string;
	nationality?: string; income?: number; src_fund1?: string; lain1?: string; comp_name?: string;
	comp_address?: string; comp_phone?: string; comp_position?: string; ocu_type?: string; update_by?: string;
	last_update?: string; bo_address?: string; area_cd?: string; city1?: string; kecamatan1?: string;
	kelurahan1?: string; rt1?: string; rw1?: string; zipcode1?: string; fax1?: string; phone1?: string;
	add_address?: string; add_city?: string; add_phone?: string; add_post?: string; add_fax?: string;
	npwp?: string; siup?: string; lob?: string;
}

interface DetailResponse {
	cam: { appl_no: string; lessee_nm: string; apless: string };
	bi_cust_type: string;
	industry: IndustryState;
	bo_id: string;
	bo_type: string;
	bo_ide: string;
	is_apless_source: boolean;
	bo_form: BOFormFields;
	occupation_options: Option[];
	occupation_disabled: boolean;
}

interface Lookups {
	bi_customer_types: Option[];
	areas: Option[];
	marital_statuses: Option[];
	source_funds_pr: Option[];
	source_funds_pt: Option[];
	bo_categories_pr: Option[];
	bo_categories_pt: Option[];
}

interface EditCamByMAPageProps {
	applno: string;
}

const emptyIndustry: IndustryState = {
	level0_options: [], level0_selected: '',
	level1_options: [], level1_selected: '',
	level2_options: [], level2_selected: '',
	level3_options: [], level3_selected: '',
	level4_options: [], level4_selected: '',
	level5_options: [], level5_selected: '',
};

const Field: React.FC<{ label: string; required?: boolean; children: React.ReactNode }> = ({ label, required, children }) => (
	<tr>
		<td className="py-1 pr-3 text-sm text-gray-600 align-top w-56">
			{label}{required && ' *'}
		</td>
		<td className="py-1">{children}</td>
	</tr>
);

const inputCls = 'w-full px-2 py-1.5 border border-gray-300 rounded text-sm';

const EditCamByMAPage: React.FC<EditCamByMAPageProps> = ({ applno }) => {
	const [loading, setLoading] = useState(true);
	const [saving, setSaving] = useState(false);
	const [message, setMessage] = useState<string | null>(null);
	const [errors, setErrors] = useState<string[]>([]);

	const [cam, setCam] = useState({ appl_no: '', lessee_nm: '', apless: '' });
	const [biCustType, setBiCustType] = useState('');
	const [industry, setIndustry] = useState<IndustryState>(emptyIndustry);
	const [boType, setBoType] = useState('');
	const [boId, setBoId] = useState('');
	const [boIde, setBoIde] = useState('');
	const [isApleSSource, setIsApleSSource] = useState(false);
	const [form, setForm] = useState<BOFormFields>({});
	const [occupationOptions, setOccupationOptions] = useState<Option[]>([]);
	const [occupationDisabled, setOccupationDisabled] = useState(false);
	const [lookups, setLookups] = useState<Lookups | null>(null);
	const [pickerOpen, setPickerOpen] = useState(false);

	useEffect(() => {
		(async () => {
			try {
				const res = await api.get<Lookups>('/CAM/Edit/api/cam-edit-ma/lookups');
				setLookups(res.data);
			} catch (err) {
				console.error('Lookups load error:', err);
			}
		})();
	}, []);

	const loadDetail = async (overrideBoIde?: string, overrideBoType?: string) => {
		setLoading(true);
		try {
			const res = await api.get<DetailResponse>('/CAM/Edit/api/cam-edit-ma/detail', {
				params: { applno, bo_ide: overrideBoIde ?? '', bo_type: overrideBoType ?? '' },
			});
			const d = res.data;
			setCam(d.cam);
			setBiCustType(d.bi_cust_type);
			setIndustry(d.industry);
			setBoType(d.bo_type);
			setBoId(d.bo_id);
			setBoIde(d.bo_ide);
			setIsApleSSource(d.is_apless_source);
			setForm(d.bo_form);
			setOccupationOptions(d.occupation_options);
			setOccupationDisabled(d.occupation_disabled);
		} catch (err) {
			console.error('Detail load error:', err);
		} finally {
			setLoading(false);
		}
	};

	useEffect(() => {
		loadDetail();
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [applno]);

	const updateField = (key: keyof BOFormFields, value: string | number) => {
		setForm((prev) => ({ ...prev, [key]: value }));
	};

	const fetchChildren = async (level: number, header: string, parent: string): Promise<Option[]> => {
		const res = await api.get<Option[]>('/CAM/Edit/api/cam-edit-ma/industry-children', {
			params: { level, header, parent },
		});
		return res.data;
	};

	const handleLevel0Change = async (header: string) => {
		const level1 = header ? await fetchChildren(1, header, '') : [];
		setIndustry((prev) => ({
			...prev, level0_selected: header,
			level1_options: level1, level1_selected: '',
			level2_options: [], level2_selected: '',
			level3_options: [], level3_selected: '',
			level4_options: [], level4_selected: '',
			level5_options: [], level5_selected: '',
		}));
	};

	const handleLevelChange = async (level: 1 | 2 | 3 | 4, composite: string) => {
		const [code, header] = composite.split('|');
		const nextLevel = level + 1;
		const nextOptions = composite
			? await fetchChildren(nextLevel, header || industry.level0_selected, code || '')
			: [];
		setIndustry((prev) => {
			const next = { ...prev, [`level${level}_selected`]: composite } as IndustryState;
			for (let l = nextLevel; l <= 5; l++) {
				(next as any)[`level${l}_options`] = l === nextLevel ? nextOptions : [];
				(next as any)[`level${l}_selected`] = '';
			}
			return next;
		});
	};

	const handleLevel5Change = (code: string) => {
		setIndustry((prev) => ({ ...prev, level5_selected: code }));
	};

	const handleBoCatChange = async (cat: string) => {
		updateField('bo_cat', cat);
		try {
			const res = await api.get('/CAM/Edit/api/cam-edit-ma/occupation-options', { params: { bo_cat: cat } });
			setOccupationOptions(res.data.options);
			setOccupationDisabled(res.data.disabled);
			updateField('ocu_type', '');
		} catch (err) {
			console.error('Occupation options error:', err);
		}
	};

	const handleAreaChange = async (areaCd: string) => {
		updateField('area_cd', areaCd);
		if (!areaCd) return;
		try {
			const res = await api.get('/CAM/Edit/api/cam-edit-ma/province-city', { params: { area_cd: areaCd } });
			updateField('city1', res.data.city);
		} catch (err) {
			console.error('Province/city lookup error:', err);
		}
	};

	const handleBoTypeChange = (type: 'PR' | 'PT') => {
		setBoType(type);
	};

	const handlePickerSelect = (id: string, source: 'customer' | 'beneficiary') => {
		setBoIde(id);
		setIsApleSSource(source === 'customer');
		loadDetail(id, boType);
	};

	const handleSave = async () => {
		setSaving(true);
		setMessage(null);
		setErrors([]);
		try {
			const payload = {
				appl_no: cam.appl_no,
				apless: cam.apless,
				bo_id: boId,
				bo_ide: boIde,
				bo_type: boType,
				bi_cust_type: biCustType,
				ind_code5: industry.level5_selected,
				is_apless_source: isApleSSource,
				pr: boType === 'PR' ? form : undefined,
				pt: boType === 'PT' ? form : undefined,
			};
			const res = await api.post('/CAM/Edit/api/cam-edit-ma/save', payload);
			if (res.data.success) {
				setMessage(res.data.message || 'Successful');
				setBoId(res.data.bo_id || boId);
				setBoIde('');
			} else {
				setErrors(res.data.errors || ['Save failed.']);
			}
		} catch (err: any) {
			console.error('Save error:', err);
			setErrors(err?.response?.data?.errors || ['Save failed. Please try again.']);
		} finally {
			setSaving(false);
		}
	};

	if (loading) {
		return (
			<div className="py-20 text-center">
				<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto" />
			</div>
		);
	}

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-5xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6 mb-4">
					<h1 className="text-xl md:text-2xl font-bold text-gray-800 mb-4">CAM Information</h1>
					<table className="w-full">
						<tbody>
							<Field label="CAM No.">{cam.appl_no}</Field>
							<Field label="Customer Name">{cam.lessee_nm}</Field>
							<Field label="BI Customer Type" required>
								<select
									value={biCustType}
									onChange={(e) => setBiCustType(e.target.value)}
									className={inputCls}
								>
									<option value="">Select</option>
									{lookups?.bi_customer_types.map((o) => (
										<option key={o.value} value={o.value}>{o.label}</option>
									))}
								</select>
							</Field>
							<Field label="Industry Code" required>
								<select
									value={industry.level0_selected}
									onChange={(e) => handleLevel0Change(e.target.value)}
									className={inputCls}
								>
									<option value="">Select</option>
									{industry.level0_options.map((o) => (
										<option key={o.value} value={o.value}>{o.label}</option>
									))}
								</select>
							</Field>
							{industry.level1_options.length > 0 && (
								<Field label="">
									<select
										value={industry.level1_selected}
										onChange={(e) => handleLevelChange(1, e.target.value)}
										className={inputCls}
									>
										<option value="">Select</option>
										{industry.level1_options.map((o) => (
											<option key={o.value} value={o.value}>{o.label}</option>
										))}
									</select>
								</Field>
							)}
							{industry.level2_options.length > 0 && (
								<Field label="">
									<select
										value={industry.level2_selected}
										onChange={(e) => handleLevelChange(2, e.target.value)}
										className={inputCls}
									>
										<option value="">Select</option>
										{industry.level2_options.map((o) => (
											<option key={o.value} value={o.value}>{o.label}</option>
										))}
									</select>
								</Field>
							)}
							{industry.level3_options.length > 0 && (
								<Field label="">
									<select
										value={industry.level3_selected}
										onChange={(e) => handleLevelChange(3, e.target.value)}
										className={inputCls}
									>
										<option value="">Select</option>
										{industry.level3_options.map((o) => (
											<option key={o.value} value={o.value}>{o.label}</option>
										))}
									</select>
								</Field>
							)}
							{industry.level4_options.length > 0 && (
								<Field label="">
									<select
										value={industry.level4_selected}
										onChange={(e) => handleLevelChange(4, e.target.value)}
										className={inputCls}
									>
										<option value="">Select</option>
										{industry.level4_options.map((o) => (
											<option key={o.value} value={o.value}>{o.label}</option>
										))}
									</select>
								</Field>
							)}
							{industry.level5_options.length > 0 && (
								<Field label="">
									<select
										value={industry.level5_selected}
										onChange={(e) => handleLevel5Change(e.target.value)}
										className={inputCls}
									>
										<option value="">Select</option>
										{industry.level5_options.map((o) => (
											<option key={o.value} value={o.value}>{o.label}</option>
										))}
									</select>
								</Field>
							)}
							<Field label="Beneficial Owner Type">
								<label className="mr-4 text-sm">
									<input
										type="radio"
										checked={boType === 'PR'}
										onChange={() => handleBoTypeChange('PR')}
										className="mr-1"
									/>
									Individual
								</label>
								<label className="text-sm">
									<input
										type="radio"
										checked={boType === 'PT'}
										onChange={() => handleBoTypeChange('PT')}
										className="mr-1"
									/>
									Corporate
								</label>
							</Field>
						</tbody>
					</table>
				</div>

				{(boType === 'PR' || boType === 'PT') && (
					<div className="bg-white rounded-2xl shadow-lg p-6 mb-4">
						<div className="flex justify-between items-center mb-4">
							<h2 className="text-lg font-bold text-gray-800">
								{boType === 'PR' ? 'Individual Beneficial Owner' : 'Corporate Beneficial Owner'}
							</h2>
							<button
								onClick={() => setPickerOpen(true)}
								className="text-blue-600 hover:underline text-sm"
							>
								Select from existing customer / beneficial owner
							</button>
						</div>

						<table className="w-full">
							<tbody>
								<Field label="Beneficial Owner Name" required>
									<input
										type="text"
										value={form.bo_name || ''}
										onChange={(e) => updateField('bo_name', e.target.value)}
										className={inputCls}
									/>
								</Field>
								{boType === 'PR' && (
									<Field label="Alias Name">
										<input
											type="text"
											value={form.alias || ''}
											onChange={(e) => updateField('alias', e.target.value)}
											className={inputCls}
										/>
									</Field>
								)}
								{boType === 'PR' && (
									<Field label="ID Card No." required>
										<input
											type="text"
											value={form.id_card || ''}
											onChange={(e) => updateField('id_card', e.target.value)}
											className={inputCls}
											maxLength={30}
										/>
									</Field>
								)}
								{boType === 'PT' && (
									<Field label="NPWP">
										<input
											type="text"
											value={form.npwp || ''}
											onChange={(e) => updateField('npwp', e.target.value)}
											className={inputCls}
											maxLength={20}
										/>
									</Field>
								)}
								<Field label="Beneficial Owner Category" required>
									<select
										value={form.bo_cat || ''}
										onChange={(e) => handleBoCatChange(e.target.value)}
										className={inputCls}
									>
										<option value="">Select</option>
										{(boType === 'PR' ? lookups?.bo_categories_pr : lookups?.bo_categories_pt)?.map((o) => (
											<option key={o.value} value={o.value}>{o.label}</option>
										))}
									</select>
								</Field>
								<Field label="Occupation / Business Type" required>
									<select
										value={form.ocu_type || ''}
										onChange={(e) => updateField('ocu_type', e.target.value)}
										disabled={occupationDisabled}
										className={inputCls}
									>
										<option value="">Select</option>
										{occupationOptions.map((o) => (
											<option key={o.value} value={o.value}>{o.label}</option>
										))}
									</select>
								</Field>
								{boType === 'PR' && (
									<Field label="Gender">
										<select
											value={form.gender || ''}
											onChange={(e) => updateField('gender', e.target.value)}
											className={inputCls}
										>
											<option value="">Select</option>
											<option value="M">Male</option>
											<option value="F">Female</option>
										</select>
									</Field>
								)}
								<Field label={boType === 'PR' ? 'Place / Date of Birth' : 'Establishment Place / Date'} required>
									<div className="flex gap-2">
										<input
											type="text"
											value={form.placebirth || ''}
											onChange={(e) => updateField('placebirth', e.target.value)}
											className={inputCls}
										/>
										<input
											type="text"
											placeholder="dd-mm-yyyy"
											value={form.tglbirth || ''}
											onChange={(e) => updateField('tglbirth', e.target.value)}
											className={inputCls}
										/>
									</div>
								</Field>
								<Field label={boType === 'PR' ? 'ID Address' : 'Address'} required>
									<textarea
										value={form.bo_address || ''}
										onChange={(e) => updateField('bo_address', e.target.value)}
										className={inputCls}
									/>
								</Field>
								<Field label="Area" required>
									<select
										value={form.area_cd || ''}
										onChange={(e) => handleAreaChange(e.target.value)}
										className={inputCls}
									>
										<option value="">Select</option>
										{lookups?.areas.map((o) => (
											<option key={o.value} value={o.value}>{o.label}</option>
										))}
									</select>
								</Field>
								<Field label="City">
									<input type="text" value={form.city1 || ''} readOnly className={`${inputCls} bg-gray-100`} />
								</Field>
								<Field label="Kecamatan">
									<input
										type="text"
										value={form.kecamatan1 || ''}
										onChange={(e) => updateField('kecamatan1', e.target.value)}
										className={inputCls}
									/>
								</Field>
								<Field label="Kelurahan">
									<input
										type="text"
										value={form.kelurahan1 || ''}
										onChange={(e) => updateField('kelurahan1', e.target.value)}
										className={inputCls}
									/>
								</Field>
								<Field label="RT / RW">
									<div className="flex gap-2">
										<input
											type="text"
											value={form.rt1 || ''}
											onChange={(e) => updateField('rt1', e.target.value)}
											className={inputCls}
											maxLength={4}
										/>
										<input
											type="text"
											value={form.rw1 || ''}
											onChange={(e) => updateField('rw1', e.target.value)}
											className={inputCls}
											maxLength={4}
										/>
									</div>
								</Field>
								<Field label="Postal Code" required>
									<input
										type="text"
										value={form.zipcode1 || ''}
										onChange={(e) => updateField('zipcode1', e.target.value)}
										className={inputCls}
										maxLength={5}
									/>
								</Field>
								<Field label="Fax">
									<input
										type="text"
										value={form.fax1 || ''}
										onChange={(e) => updateField('fax1', e.target.value)}
										className={inputCls}
									/>
								</Field>
								<Field label="Phone" required>
									<input
										type="text"
										value={form.phone1 || ''}
										onChange={(e) => updateField('phone1', e.target.value)}
										className={inputCls}
									/>
								</Field>
								{boType === 'PR' && (
									<>
										<Field label="Marital Status" required>
											<select
												value={form.marital || ''}
												onChange={(e) => updateField('marital', e.target.value)}
												className={inputCls}
											>
												<option value="">Select</option>
												{lookups?.marital_statuses.map((o) => (
													<option key={o.value} value={o.value}>{o.label}</option>
												))}
											</select>
										</Field>
										<Field label="Citizenship" required>
											<label className="mr-4 text-sm">
												<input
													type="radio"
													checked={form.citizen === 'WNI'}
													onChange={() => updateField('citizen', 'WNI')}
													className="mr-1"
												/>
												WNI
											</label>
											<label className="text-sm">
												<input
													type="radio"
													checked={form.citizen === 'WNA'}
													onChange={() => updateField('citizen', 'WNA')}
													className="mr-1"
												/>
												WNA
											</label>
										</Field>
										<Field label="Nationality" required>
											<input
												type="text"
												value={form.nationality || ''}
												onChange={(e) => updateField('nationality', e.target.value)}
												className={inputCls}
											/>
										</Field>
										<Field label="Average Income per Year" required>
											<input
												type="number"
												value={form.income ?? ''}
												onChange={(e) => updateField('income', Number(e.target.value))}
												className={inputCls}
											/>
										</Field>
										<Field label="Mobile" required>
											<input
												type="text"
												value={form.mobile_phone1 || ''}
												onChange={(e) => updateField('mobile_phone1', e.target.value)}
												className={inputCls}
											/>
										</Field>
										<Field label="Email">
											<input
												type="text"
												value={form.email1 || ''}
												onChange={(e) => updateField('email1', e.target.value)}
												className={inputCls}
											/>
										</Field>
									</>
								)}
								{boType === 'PT' && (
									<>
										<Field label="Line of Business">
											<textarea
												value={form.lob || ''}
												onChange={(e) => updateField('lob', e.target.value)}
												className={inputCls}
											/>
										</Field>
										<Field label="SIUP No.">
											<input
												type="text"
												value={form.siup || ''}
												onChange={(e) => updateField('siup', e.target.value)}
												className={inputCls}
											/>
										</Field>
										<Field label="Email">
											<input
												type="text"
												value={form.email1 || ''}
												onChange={(e) => updateField('email1', e.target.value)}
												className={inputCls}
											/>
										</Field>
										<Field label="Contact Name" required>
											<input
												type="text"
												value={form.comp_name || ''}
												onChange={(e) => updateField('comp_name', e.target.value)}
												className={inputCls}
											/>
										</Field>
										<Field label="Contact Position" required>
											<input
												type="text"
												value={form.comp_position || ''}
												onChange={(e) => updateField('comp_position', e.target.value)}
												className={inputCls}
											/>
										</Field>
										<Field label="Contact Address" required>
											<textarea
												value={form.comp_address || ''}
												onChange={(e) => updateField('comp_address', e.target.value)}
												className={inputCls}
											/>
										</Field>
									</>
								)}
								<Field label="Source Of Fund" required>
									<select
										value={form.src_fund1 || ''}
										onChange={(e) => updateField('src_fund1', e.target.value)}
										className={inputCls}
									>
										<option value="">Select</option>
										{(boType === 'PR' ? lookups?.source_funds_pr : lookups?.source_funds_pt)?.map((o) => (
											<option key={o.value} value={o.value}>{o.label}</option>
										))}
									</select>
								</Field>
								<Field label="Source Of Fund (Other)">
									<input
										type="text"
										value={form.lain1 || ''}
										onChange={(e) => updateField('lain1', e.target.value)}
										className={inputCls}
									/>
								</Field>
								{boType === 'PR' && (
									<>
										<Field label="Company Name" required>
											<input
												type="text"
												value={form.comp_name || ''}
												onChange={(e) => updateField('comp_name', e.target.value)}
												className={inputCls}
											/>
										</Field>
										<Field label="Company Address">
											<textarea
												value={form.comp_address || ''}
												onChange={(e) => updateField('comp_address', e.target.value)}
												className={inputCls}
											/>
										</Field>
										<Field label="Company Phone" required>
											<input
												type="text"
												value={form.comp_phone || ''}
												onChange={(e) => updateField('comp_phone', e.target.value)}
												className={inputCls}
											/>
										</Field>
										<Field label="Additional Address" required>
											<textarea
												value={form.add_address || ''}
												onChange={(e) => updateField('add_address', e.target.value)}
												className={inputCls}
											/>
										</Field>
										<Field label="Additional City">
											<input
												type="text"
												value={form.add_city || ''}
												onChange={(e) => updateField('add_city', e.target.value)}
												className={inputCls}
											/>
										</Field>
										<Field label="Additional Phone">
											<input
												type="text"
												value={form.add_phone || ''}
												onChange={(e) => updateField('add_phone', e.target.value)}
												className={inputCls}
											/>
										</Field>
										<Field label="Additional Postal Code">
											<input
												type="text"
												value={form.add_post || ''}
												onChange={(e) => updateField('add_post', e.target.value)}
												className={inputCls}
											/>
										</Field>
										<Field label="Additional Fax">
											<input
												type="text"
												value={form.add_fax || ''}
												onChange={(e) => updateField('add_fax', e.target.value)}
												className={inputCls}
											/>
										</Field>
									</>
								)}
								<Field label="Update By">
									<input type="text" value={form.update_by || ''} readOnly className={`${inputCls} bg-gray-100`} />
								</Field>
								<Field label="Last Update">
									<input type="text" value={form.last_update || ''} readOnly className={`${inputCls} bg-gray-100`} />
								</Field>
							</tbody>
						</table>
					</div>
				)}

				{errors.length > 0 && (
					<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
						{errors.map((e, i) => <div key={i}>{e}</div>)}
					</div>
				)}
				{message && (
					<div className="mb-4 p-4 bg-green-50 border border-green-200 rounded-lg text-green-700 text-sm">
						{message}
					</div>
				)}

				<div className="text-center pb-6">
					<button
						onClick={handleSave}
						disabled={saving}
						className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white px-6 py-2 rounded-lg text-sm font-medium"
					>
						{saving ? 'Saving…' : 'Save'}
					</button>
				</div>
			</div>

			<CustomerBOSearchModal
				open={pickerOpen}
				onClose={() => setPickerOpen(false)}
				lesseeTp={(boType || 'PR') as 'PR' | 'PT'}
				ownApless={cam.apless}
				onSelect={handlePickerSelect}
			/>
		</div>
	);
};

export default EditCamByMAPage;