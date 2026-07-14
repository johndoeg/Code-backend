import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
interface Option {
	value: string;
	label: string;
}
export interface CustomerFormData {
	nameInIdCard: string;
	customerNameWithoutTitle: string;
	aliasName: string;
	customerProfile: string;
	occupation: string;
	addressInIdCard: string;
	area: string;
	province: string;
	districtCity: string;
	kecamatan: string;
	kelurahan: string;
	rt: string;
	rw: string;
	postCode: string;
	fax: string;
	liveHereSince: string;
	phone: string;
	mobile1: string;
	sendSms: boolean;
	mobile2: string;
	mobile3: string;
	otherPhone1: string;
	otherPhoneNotes1: string;
	otherPhone2: string;
	otherPhoneNotes2: string;
	email1: string;
	email2: string;
	group: string;
	biCustomerType: string;
	industrialCode: string[];

	customerNo: string;
	placeDateOfBirth: string;
	gender: string;
	religion: string;
	lastEducation: string;
	careerField: string;
	npwp: string;
	addressInNpwp: string;
	npwpArea: string;
	npwpProvince: string;
	npwpDistrictCity: string;
	npwpKecamatan: string;
	npwpKelurahan: string;
	npwpPostCode: string;
	citizenship: string;
	idCardNo: string;
	validityIdCard: string;
	passportNo: string;
	familyCardNo: string;
	mothersMaidenName: string;
	maritalStatus: string;

	spouseNameInIdCard: string;
	spouseNameWithoutTitle: string;
	spouseAddressSameAsCustomer: boolean;
	spouseAddress: string;
	spouseArea: string;
	spouseProvince: string;
	spouseDistrictCity: string;
	spouseKecamatan: string;
	spouseKelurahan: string;
	spouseRt: string;
	spouseRw: string;
	spousePostCode: string;
	spousePlaceDateOfBirth: string;
	spouseCitizenship: string;
	spouseIdCardNo: string;
	spouseValidityIdCard: string;
	spousePassportNo: string;
	spouseMarriageAgreement: string;
	spouseTotalDependent: string;
	spouseRelationshipWithCompany: string;

	emergencyName: string;
	emergencyAddress: string;
	emergencyPhone: string;
	emergencyRelation: string;
}

const CustomerDetailForm = () => {
	const navigate = useNavigate();

	const [formData, setFormData] = useState<CustomerFormData>({
		nameInIdCard: 'ABDUL',
		customerNameWithoutTitle: '',
		aliasName: '',
		customerProfile: 'Professional',
		occupation: '',
		addressInIdCard: 'JL. ALAMAT 1',
		area: '',
		province: '',
		districtCity: '',
		kecamatan: '',
		kelurahan: '',
		rt: '',
		rw: '',
		postCode: '',
		fax: '',
		liveHereSince: '',
		phone: '',
		mobile1: '',
		sendSms: true,
		mobile2: '62',
		mobile3: '62',
		otherPhone1: '',
		otherPhoneNotes1: '',
		otherPhone2: '',
		otherPhoneNotes2: '',
		email1: '',
		email2: '',
		group: '',
		biCustomerType: 'Pekerja',
		industrialCode: ['', '', '', ''],

		customerNo: '001028',
		placeDateOfBirth: '',
		gender: '',
		religion: '',
		lastEducation: '',
		careerField: '',
		npwp: '',
		addressInNpwp: '',
		npwpArea: '',
		npwpProvince: '',
		npwpDistrictCity: '',
		npwpKecamatan: '',
		npwpKelurahan: '',
		npwpPostCode: '',
		citizenship: 'WNI',
		idCardNo: '320626050596xxxx',
		validityIdCard: 'No Expire Date',
		passportNo: '',
		familyCardNo: '',
		mothersMaidenName: '',
		maritalStatus: 'Single',

		spouseNameInIdCard: '',
		spouseNameWithoutTitle: '',
		spouseAddressSameAsCustomer: true,
		spouseAddress: '',
		spouseArea: '',
		spouseProvince: '',
		spouseDistrictCity: '',
		spouseKecamatan: '',
		spouseKelurahan: '',
		spouseRt: '',
		spouseRw: '',
		spousePostCode: '',
		spousePlaceDateOfBirth: '',
		spouseCitizenship: 'Indonesia',
		spouseIdCardNo: '',
		spouseValidityIdCard: 'No Expire Date',
		spousePassportNo: '',
		spouseMarriageAgreement: '',
		spouseTotalDependent: '',
		spouseRelationshipWithCompany: 'Tidak terkait dengan Pelapor',

		emergencyName: '',
		emergencyAddress: '',
		emergencyPhone: '',
		emergencyRelation: '',
	});

	const [errors, setErrors] = useState<Record<string, string>>({});

	const validate = () => {
		const newErrors: Record<string, string> = {};

		if (!formData.nameInIdCard) newErrors.nameInIdCard = 'Required';
		if (!formData.customerNameWithoutTitle) newErrors.customerNameWithoutTitle = 'Required';
		if (!formData.customerProfile) newErrors.customerProfile = 'Required';
		if (!formData.addressInIdCard) newErrors.addressInIdCard = 'Required';
		if (!formData.area) newErrors.area = 'Required';
		if (!formData.province) newErrors.province = 'Required';
		if (!formData.districtCity) newErrors.districtCity = 'Required';
		if (!formData.kecamatan) newErrors.kecamatan = 'Required';
		if (!formData.kelurahan) newErrors.kelurahan = 'Required';
		if (!formData.rt) newErrors.rt = 'Required';
		if (!formData.rw) newErrors.rw = 'Required';
		if (!formData.postCode) newErrors.postCode = 'Required';
		if (!formData.phone) newErrors.phone = 'Required';
		if (!formData.mobile1) newErrors.mobile1 = 'Required';
		if (!formData.group) newErrors.group = 'Required';
		if (!formData.biCustomerType) newErrors.biCustomerType = 'Required';
		if (!formData.industrialCode[0]) newErrors.industrialCode = 'At least one required';

		if (!formData.customerNo) newErrors.customerNo = 'Required';
		if (!formData.placeDateOfBirth) newErrors.placeDateOfBirth = 'Required';
		if (!formData.gender) newErrors.gender = 'Required';
		if (!formData.religion) newErrors.religion = 'Required';
		if (!formData.lastEducation) newErrors.lastEducation = 'Required';
		if (!formData.careerField) newErrors.careerField = 'Required';
		if (!formData.npwp) newErrors.npwp = 'Required';
		if (!formData.addressInNpwp) newErrors.addressInNpwp = 'Required';
		if (!formData.npwpArea) newErrors.npwpArea = 'Required';
		if (!formData.npwpProvince) newErrors.npwpProvince = 'Required';
		if (!formData.npwpDistrictCity) newErrors.npwpDistrictCity = 'Required';
		if (!formData.npwpKecamatan) newErrors.npwpKecamatan = 'Required';
		if (!formData.npwpKelurahan) newErrors.npwpKelurahan = 'Required';
		if (!formData.npwpPostCode) newErrors.npwpPostCode = 'Required';
		if (!formData.citizenship) newErrors.citizenship = 'Required';
		if (!formData.idCardNo) newErrors.idCardNo = 'Required';
		if (!formData.validityIdCard) newErrors.validityIdCard = 'Required';
		if (!formData.maritalStatus) newErrors.maritalStatus = 'Required';

		if (formData.maritalStatus === 'Married') {
			if (!formData.spouseNameInIdCard) newErrors.spouseNameInIdCard = 'Required';
			if (!formData.spouseNameWithoutTitle) newErrors.spouseNameWithoutTitle = 'Required';
			if (!formData.spouseAddressSameAsCustomer && !formData.spouseAddress) newErrors.spouseAddress = 'Required';
			if (!formData.spouseArea) newErrors.spouseArea = 'Required';
			if (!formData.spouseProvince) newErrors.spouseProvince = 'Required';
			if (!formData.spouseDistrictCity) newErrors.spouseDistrictCity = 'Required';
			if (!formData.spouseKecamatan) newErrors.spouseKecamatan = 'Required';
			if (!formData.spouseKelurahan) newErrors.spouseKelurahan = 'Required';
			if (!formData.spouseRt) newErrors.spouseRt = 'Required';
			if (!formData.spouseRw) newErrors.spouseRw = 'Required';
			if (!formData.spousePostCode) newErrors.spousePostCode = 'Required';
			if (!formData.spousePlaceDateOfBirth) newErrors.spousePlaceDateOfBirth = 'Required';
			if (!formData.spouseCitizenship) newErrors.spouseCitizenship = 'Required';
			if (!formData.spouseIdCardNo) newErrors.spouseIdCardNo = 'Required';
			if (!formData.spouseValidityIdCard) newErrors.spouseValidityIdCard = 'Required';
			if (!formData.spouseMarriageAgreement) newErrors.spouseMarriageAgreement = 'Required';
			if (!formData.spouseTotalDependent) newErrors.spouseTotalDependent = 'Required';
			if (!formData.spouseRelationshipWithCompany) newErrors.spouseRelationshipWithCompany = 'Required';
		}

		if (!formData.emergencyName) newErrors.emergencyName = 'Required';
		if (!formData.emergencyAddress) newErrors.emergencyAddress = 'Required';
		if (!formData.emergencyPhone) newErrors.emergencyPhone = 'Required';
		if (!formData.emergencyRelation) newErrors.emergencyRelation = 'Required';

		setErrors(newErrors);
		return Object.keys(newErrors).length === 0;
	};

	const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
		const { name, value, type } = e.target;
		if (type === 'checkbox') {
			setFormData(prev => ({ ...prev, [name]: (e.target as HTMLInputElement).checked }));
		} else if (name.startsWith('industrialCode')) {
			const index = parseInt(name.split('-')[1]);
			const newCodes = [...formData.industrialCode];
			newCodes[index] = value;
			setFormData(prev => ({ ...prev, industrialCode: newCodes }));
		} else {
			setFormData(prev => ({ ...prev, [name]: value }));
		}
	};

	const handleSpouseAddressChange = (value: boolean) => {
		setFormData(prev => ({
			...prev,
			spouseAddressSameAsCustomer: value,
			spouseAddress: value ? formData.addressInIdCard : '',
		}));
	};

	const handleSubmit = (e: React.FormEvent) => {
		e.preventDefault();
		if (validate()) {
			navigate('/next-step');
		}
	};

	const mockOptions: Option[] = [
		{ value: '', label: 'Select' },
		{ value: 'option1', label: 'Option 1' },
		{ value: 'option2', label: 'Option 2' },
	];

	const mockProvinces: Option[] = [
		{ value: '', label: 'Select Province' },
		{ value: 'JABAR', label: 'Jawa Barat' },
		{ value: 'JATENG', label: 'Jawa Tengah' },
		{ value: 'DKI', label: 'DKI Jakarta' },
	];

	const mockCities: Option[] = [
		{ value: '', label: 'Select City' },
		{ value: 'BANDUNG', label: 'Bandung' },
		{ value: 'SEMARANG', label: 'Semarang' },
		{ value: 'JAKARTA', label: 'Jakarta' },
	];

	const mockKecamatan: Option[] = [
		{ value: '', label: 'Select Kecamatan' },
		{ value: 'CICENDO', label: 'Cicendo' },
		{ value: 'GAYAMSARI', label: 'Gayamsari' },
		{ value: 'MENTENG', label: 'Menteng' },
	];

	const mockKelurahan: Option[] = [
		{ value: '', label: 'Select Kelurahan' },
		{ value: 'CICENDO', label: 'Cicendo' },
		{ value: 'GAYAMSARI', label: 'Gayamsari' },
		{ value: 'MENTENG', label: 'Menteng' },
	];

	const mockAreas: Option[] = [
		{ value: '', label: 'Select Area' },
		{ value: 'AREA1', label: 'Area 1' },
		{ value: 'AREA2', label: 'Area 2' },
	];

	const mockGenders: Option[] = [
		{ value: '', label: 'Select Gender' },
		{ value: 'M', label: 'Male' },
		{ value: 'F', label: 'Female' },
	];

	const mockReligions: Option[] = [
		{ value: '', label: 'Select Religion' },
		{ value: 'ISLAM', label: 'Islam' },
		{ value: 'KRISTEN', label: 'Kristen' },
		{ value: 'HINDU', label: 'Hindu' },
		{ value: 'BUDDHA', label: 'Buddha' },
	];

	const mockEducations: Option[] = [
		{ value: '', label: 'Select Education' },
		{ value: 'SD', label: 'SD' },
		{ value: 'SMP', label: 'SMP' },
		{ value: 'SMA', label: 'SMA' },
		{ value: 'DIPLOMA', label: 'Diploma' },
		{ value: 'S1', label: 'S1' },
	];

	const mockCareers: Option[] = [
		{ value: '', label: 'Select Career' },
		{ value: 'TEACHER', label: 'Teacher' },
		{ value: 'ENGINEER', label: 'Engineer' },
		{ value: 'DOCTOR', label: 'Doctor' },
	];

	const mockMaritalStatuses: Option[] = [
		{ value: '', label: 'Select Status' },
		{ value: 'Single', label: 'Single' },
		{ value: 'Married', label: 'Married' },
		{ value: 'Divorced', label: 'Divorced' },
	];

	const mockCitizenships: Option[] = [
		{ value: '', label: 'Select Citizenship' },
		{ value: 'WNI', label: 'WNI' },
		{ value: 'WNA', label: 'WNA' },
	];

	const mockNationalities: Option[] = [
		{ value: '', label: 'Select Nationality' },
		{ value: 'Indonesia', label: 'Indonesia' },
		{ value: 'Singapore', label: 'Singapore' },
		{ value: 'Malaysia', label: 'Malaysia' },
	];

	const mockMarriageAgreements: Option[] = [
		{ value: '', label: 'Select Agreement' },
		{ value: 'AGREEMENT1', label: 'Agreement 1' },
		{ value: 'AGREEMENT2', label: 'Agreement 2' },
	];

	const mockDependents: Option[] = [
		{ value: '', label: 'Select' },
		{ value: '0', label: '0' },
		{ value: '1', label: '1' },
		{ value: '2', label: '2' },
		{ value: '3+', label: '3+' },
	];

	const mockRelationshipsWithCompany: Option[] = [
		{ value: '', label: 'Select Relationship' },
		{ value: 'Tidak terkait dengan Pelapor', label: 'Tidak terkait dengan Pelapor' },
		{ value: 'Direktur', label: 'Direktur' },
		{ value: 'Pemegang Saham', label: 'Pemegang Saham' },
	];

	const mockGroups: Option[] = [
		{ value: '', label: 'Select Group' },
		{ value: 'GROUP1', label: 'Group 1' },
		{ value: 'GROUP2', label: 'Group 2' },
	];

	const mockBiCustomerTypes: Option[] = [
		{ value: '', label: 'Select Type' },
		{ value: 'Pekerja', label: 'Pekerja' },
		{ value: 'Wiraswasta', label: 'Wiraswasta' },
		{ value: 'Pensiunan', label: 'Pensiunan' },
	];

	const mockIndustrialCodes: Option[] = [
		{ value: '', label: 'Select Code' },
		{ value: 'CODE1', label: 'Code 1' },
		{ value: 'CODE2', label: 'Code 2' },
		{ value: 'CODE3', label: 'Code 3' },
	];

	return (
		<div className="bg-white p-6 rounded shadow">
			<div className="flex justify-between items-center mb-4 border-b pb-2">
				<h1 className="text-xl font-bold text-blue-800">Detail Information</h1>
				<div className="text-sm text-gray-600">
					I - 10882512001 - ABDUL AZIZ
				</div>
			</div>

			<form onSubmit={handleSubmit}>
				<div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

					<div className="space-y-4">
						<div className="grid grid-cols-2 gap-4">
							<div>
								<label className="block text-sm font-medium text-gray-700">
									Name in ID Card * <span className="text-blue-600">(i)</span>
								</label>
								<input
									type="text"
									name="nameInIdCard"
									value={formData.nameInIdCard}
									onChange={handleChange}
									className={`mt-1 block w-full px-3 py-2 border ${errors.nameInIdCard ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
									disabled
								/>
								{errors.nameInIdCard && <p className="mt-1 text-sm text-red-600">{errors.nameInIdCard}</p>}
							</div>
							<div>
								<label className="block text-sm font-medium text-gray-700">
									Customer No. *
								</label>
								<input
									type="text"
									name="customerNo"
									value={formData.customerNo}
									onChange={handleChange}
									className={`mt-1 block w-full px-3 py-2 border ${errors.customerNo ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
									disabled
								/>
								{errors.customerNo && <p className="mt-1 text-sm text-red-600">{errors.customerNo}</p>}
							</div>
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Customer Name Without Title * <span className="text-blue-600">(i)</span>
							</label>
							<input
								type="text"
								name="customerNameWithoutTitle"
								value={formData.customerNameWithoutTitle}
								onChange={handleChange}
								className={`mt-1 block w-full px-3 py-2 border ${errors.customerNameWithoutTitle ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
							/>
							{errors.customerNameWithoutTitle && <p className="mt-1 text-sm text-red-600">{errors.customerNameWithoutTitle}</p>}
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Alias Name
							</label>
							<input
								type="text"
								name="aliasName"
								value={formData.aliasName}
								onChange={handleChange}
								className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
							/>
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Customer Profile *
							</label>
							<select
								name="customerProfile"
								value={formData.customerProfile}
								onChange={handleChange}
								className={`mt-1 block w-full px-3 py-2 border ${errors.customerProfile ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
							>
								{mockOptions.map(opt => (
									<option key={opt.value} value={opt.value}>{opt.label}</option>
								))}
							</select>
							{errors.customerProfile && <p className="mt-1 text-sm text-red-600">{errors.customerProfile}</p>}
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Occupation/ Business Type
							</label>
							<select
								name="occupation"
								value={formData.occupation}
								onChange={handleChange}
								className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
							>
								{mockOptions.map(opt => (
									<option key={opt.value} value={opt.value}>{opt.label}</option>
								))}
							</select>
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Address in ID Card *
							</label>
							<textarea
								name="addressInIdCard"
								value={formData.addressInIdCard}
								onChange={handleChange}
								rows={2}
								className={`mt-1 block w-full px-3 py-2 border ${errors.addressInIdCard ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
							/>
							{errors.addressInIdCard && <p className="mt-1 text-sm text-red-600">{errors.addressInIdCard}</p>}
						</div>

						<div className="grid grid-cols-2 gap-4">
							<div>
								<label className="block text-sm font-medium text-gray-700">
									Area *
								</label>
								<select
									name="area"
									value={formData.area}
									onChange={handleChange}
									className={`mt-1 block w-full px-3 py-2 border ${errors.area ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
								>
									{mockAreas.map(opt => (
										<option key={opt.value} value={opt.value}>{opt.label}</option>
									))}
								</select>
								{errors.area && <p className="mt-1 text-sm text-red-600">{errors.area}</p>}
							</div>
							<div>
								<label className="block text-sm font-medium text-gray-700">
									Province *
								</label>
								<select
									name="province"
									value={formData.province}
									onChange={handleChange}
									className={`mt-1 block w-full px-3 py-2 border ${errors.province ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
								>
									{mockProvinces.map(opt => (
										<option key={opt.value} value={opt.value}>{opt.label}</option>
									))}
								</select>
								{errors.province && <p className="mt-1 text-sm text-red-600">{errors.province}</p>}
							</div>
						</div>

						<div className="grid grid-cols-2 gap-4">
							<div>
								<label className="block text-sm font-medium text-gray-700">
									District/ City *
								</label>
								<select
									name="districtCity"
									value={formData.districtCity}
									onChange={handleChange}
									className={`mt-1 block w-full px-3 py-2 border ${errors.districtCity ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
								>
									{mockCities.map(opt => (
										<option key={opt.value} value={opt.value}>{opt.label}</option>
									))}
								</select>
								{errors.districtCity && <p className="mt-1 text-sm text-red-600">{errors.districtCity}</p>}
							</div>
							<div>
								<label className="block text-sm font-medium text-gray-700">
									Kecamatan *
								</label>
								<select
									name="kecamatan"
									value={formData.kecamatan}
									onChange={handleChange}
									className={`mt-1 block w-full px-3 py-2 border ${errors.kecamatan ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
								>
									{mockKecamatan.map(opt => (
										<option key={opt.value} value={opt.value}>{opt.label}</option>
									))}
								</select>
								{errors.kecamatan && <p className="mt-1 text-sm text-red-600">{errors.kecamatan}</p>}
							</div>
						</div>

						<div className="grid grid-cols-2 gap-4">
							<div>
								<label className="block text-sm font-medium text-gray-700">
									Kelurahan *
								</label>
								<select
									name="kelurahan"
									value={formData.kelurahan}
									onChange={handleChange}
									className={`mt-1 block w-full px-3 py-2 border ${errors.kelurahan ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
								>
									{mockKelurahan.map(opt => (
										<option key={opt.value} value={opt.value}>{opt.label}</option>
									))}
								</select>
								{errors.kelurahan && <p className="mt-1 text-sm text-red-600">{errors.kelurahan}</p>}
							</div>
							<div>
								<label className="block text-sm font-medium text-gray-700">
									RT * / RW *
								</label>
								<div className="flex space-x-2">
									<input
										type="text"
										name="rt"
										value={formData.rt}
										onChange={handleChange}
										className={`w-1/2 px-3 py-2 border ${errors.rt ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
									/>
									<input
										type="text"
										name="rw"
										value={formData.rw}
										onChange={handleChange}
										className={`w-1/2 px-3 py-2 border ${errors.rw ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
									/>
								</div>
								{(errors.rt || errors.rw) && <p className="mt-1 text-sm text-red-600">{errors.rt || errors.rw}</p>}
							</div>
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Post Code *
							</label>
							<input
								type="text"
								name="postCode"
								value={formData.postCode}
								onChange={handleChange}
								className={`mt-1 block w-full px-3 py-2 border ${errors.postCode ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
							/>
							{errors.postCode && <p className="mt-1 text-sm text-red-600">{errors.postCode}</p>}
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Fax
							</label>
							<input
								type="text"
								name="fax"
								value={formData.fax}
								onChange={handleChange}
								className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
							/>
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Live here since (year) *
							</label>
							<input
								type="text"
								name="liveHereSince"
								value={formData.liveHereSince}
								onChange={handleChange}
								className={`mt-1 block w-full px-3 py-2 border ${errors.liveHereSince ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
							/>
							{errors.liveHereSince && <p className="mt-1 text-sm text-red-600">{errors.liveHereSince}</p>}
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Phone *
							</label>
							<div className="flex space-x-2">
								<input
									type="text"
									name="phone"
									value={formData.phone}
									onChange={handleChange}
									className={`w-1/3 px-3 py-2 border ${errors.phone ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
								/>
								<input
									type="text"
									name="phone"
									value=""
									onChange={() => { }}
									className="w-1/3 px-3 py-2 border border-gray-300 rounded-md shadow-sm"
									placeholder="XXX"
								/>
								<input
									type="text"
									name="phone"
									value=""
									onChange={() => { }}
									className="w-1/3 px-3 py-2 border border-gray-300 rounded-md shadow-sm"
									placeholder="XXXX"
								/>
							</div>
							{errors.phone && <p className="mt-1 text-sm text-red-600">{errors.phone}</p>}
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Mobile 1 *
							</label>
							<div className="flex items-center space-x-2">
								<input
									type="text"
									name="mobile1"
									value={formData.mobile1}
									onChange={handleChange}
									className={`w-1/4 px-3 py-2 border ${errors.mobile1 ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
								/>
								<input
									type="text"
									name="mobile1"
									value=""
									onChange={() => { }}
									className="w-1/4 px-3 py-2 border border-gray-300 rounded-md shadow-sm"
									placeholder="XXX"
								/>
								<input
									type="text"
									name="mobile1"
									value=""
									onChange={() => { }}
									className="w-1/4 px-3 py-2 border border-gray-300 rounded-md shadow-sm"
									placeholder="XXXX"
								/>
								<label className="inline-flex items-center">
									<input
										type="checkbox"
										name="sendSms"
										checked={formData.sendSms}
										onChange={handleChange}
										className="mr-2"
									/>
									Send SMS
								</label>
							</div>
							{errors.mobile1 && <p className="mt-1 text-sm text-red-600">{errors.mobile1}</p>}
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Mobile 2
							</label>
							<div className="flex space-x-2">
								<input
									type="text"
									name="mobile2"
									value={formData.mobile2}
									onChange={handleChange}
									className="w-1/4 px-3 py-2 border border-gray-300 rounded-md shadow-sm"
								/>
								<input
									type="text"
									name="mobile2"
									value=""
									onChange={() => { }}
									className="w-1/4 px-3 py-2 border border-gray-300 rounded-md shadow-sm"
									placeholder="XXX"
								/>
								<input
									type="text"
									name="mobile2"
									value=""
									onChange={() => { }}
									className="w-1/4 px-3 py-2 border border-gray-300 rounded-md shadow-sm"
									placeholder="XXXX"
								/>
							</div>
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Mobile 3
							</label>
							<div className="flex space-x-2">
								<input
									type="text"
									name="mobile3"
									value={formData.mobile3}
									onChange={handleChange}
									className="w-1/4 px-3 py-2 border border-gray-300 rounded-md shadow-sm"
								/>
								<input
									type="text"
									name="mobile3"
									value=""
									onChange={() => { }}
									className="w-1/4 px-3 py-2 border border-gray-300 rounded-md shadow-sm"
									placeholder="XXX"
								/>
								<input
									type="text"
									name="mobile3"
									value=""
									onChange={() => { }}
									className="w-1/4 px-3 py-2 border border-gray-300 rounded-md shadow-sm"
									placeholder="XXXX"
								/>
							</div>
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Other Phone 1
							</label>
							<div className="flex space-x-2">
								<input
									type="text"
									name="otherPhone1"
									value={formData.otherPhone1}
									onChange={handleChange}
									className="w-1/3 px-3 py-2 border border-gray-300 rounded-md shadow-sm"
								/>
								<input
									type="text"
									name="otherPhone1"
									value=""
									onChange={() => { }}
									className="w-1/3 px-3 py-2 border border-gray-300 rounded-md shadow-sm"
									placeholder="XXX"
								/>
								<input
									type="text"
									name="otherPhone1"
									value=""
									onChange={() => { }}
									className="w-1/3 px-3 py-2 border border-gray-300 rounded-md shadow-sm"
									placeholder="XXXX"
								/>
							</div>
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Other Phone Notes 1
							</label>
							<input
								type="text"
								name="otherPhoneNotes1"
								value={formData.otherPhoneNotes1}
								onChange={handleChange}
								className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
							/>
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Other Phone 2
							</label>
							<div className="flex space-x-2">
								<input
									type="text"
									name="otherPhone2"
									value={formData.otherPhone2}
									onChange={handleChange}
									className="w-1/3 px-3 py-2 border border-gray-300 rounded-md shadow-sm"
								/>
								<input
									type="text"
									name="otherPhone2"
									value=""
									onChange={() => { }}
									className="w-1/3 px-3 py-2 border border-gray-300 rounded-md shadow-sm"
									placeholder="XXX"
								/>
								<input
									type="text"
									name="otherPhone2"
									value=""
									onChange={() => { }}
									className="w-1/3 px-3 py-2 border border-gray-300 rounded-md shadow-sm"
									placeholder="XXXX"
								/>
							</div>
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Other Phone Notes 2
							</label>
							<input
								type="text"
								name="otherPhoneNotes2"
								value={formData.otherPhoneNotes2}
								onChange={handleChange}
								className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
							/>
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Email 1
							</label>
							<input
								type="email"
								name="email1"
								value={formData.email1}
								onChange={handleChange}
								className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
							/>
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Email 2
							</label>
							<input
								type="email"
								name="email2"
								value={formData.email2}
								onChange={handleChange}
								className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
							/>
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Group *
							</label>
							<select
								name="group"
								value={formData.group}
								onChange={handleChange}
								className={`mt-1 block w-full px-3 py-2 border ${errors.group ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
							>
								{mockGroups.map(opt => (
									<option key={opt.value} value={opt.value}>{opt.label}</option>
								))}
							</select>
							{errors.group && <p className="mt-1 text-sm text-red-600">{errors.group}</p>}
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								BI Customer Type
							</label>
							<select
								name="biCustomerType"
								value={formData.biCustomerType}
								onChange={handleChange}
								className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
							>
								{mockBiCustomerTypes.map(opt => (
									<option key={opt.value} value={opt.value}>{opt.label}</option>
								))}
							</select>
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Industrial Code *
							</label>
							<div className="space-y-2">
								{[0, 1, 2, 3].map((i) => (
									<select
										key={i}
										name={`industrialCode-${i}`}
										value={formData.industrialCode[i]}
										onChange={handleChange}
										className={`mt-1 block w-full px-3 py-2 border ${errors.industrialCode && i === 0 ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
									>
										{mockIndustrialCodes.map(opt => (
											<option key={opt.value} value={opt.value}>{opt.label}</option>
										))}
									</select>
								))}
							</div>
							{errors.industrialCode && <p className="mt-1 text-sm text-red-600">{errors.industrialCode}</p>}
						</div>
					</div>

					<div className="space-y-4">

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Place/ Date of Birth *
							</label>
							<div className="flex space-x-2">
								<input
									type="text"
									name="placeDateOfBirth"
									value={formData.placeDateOfBirth}
									onChange={handleChange}
									className={`w-1/2 px-3 py-2 border ${errors.placeDateOfBirth ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
								/>
								<input
									type="text"
									name="placeDateOfBirth"
									value=""
									onChange={() => { }}
									className="w-1/2 px-3 py-2 border border-gray-300 rounded-md shadow-sm"
									placeholder="dd-mm-yyyy"
								/>
							</div>
							{errors.placeDateOfBirth && <p className="mt-1 text-sm text-red-600">{errors.placeDateOfBirth}</p>}
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Gender *
							</label>
							<select
								name="gender"
								value={formData.gender}
								onChange={handleChange}
								className={`mt-1 block w-full px-3 py-2 border ${errors.gender ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
							>
								{mockGenders.map(opt => (
									<option key={opt.value} value={opt.value}>{opt.label}</option>
								))}
							</select>
							{errors.gender && <p className="mt-1 text-sm text-red-600">{errors.gender}</p>}
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Religion *
							</label>
							<select
								name="religion"
								value={formData.religion}
								onChange={handleChange}
								className={`mt-1 block w-full px-3 py-2 border ${errors.religion ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
							>
								{mockReligions.map(opt => (
									<option key={opt.value} value={opt.value}>{opt.label}</option>
								))}
							</select>
							{errors.religion && <p className="mt-1 text-sm text-red-600">{errors.religion}</p>}
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Last Education *
							</label>
							<select
								name="lastEducation"
								value={formData.lastEducation}
								onChange={handleChange}
								className={`mt-1 block w-full px-3 py-2 border ${errors.lastEducation ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
							>
								{mockEducations.map(opt => (
									<option key={opt.value} value={opt.value}>{opt.label}</option>
								))}
							</select>
							{errors.lastEducation && <p className="mt-1 text-sm text-red-600">{errors.lastEducation}</p>}
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Career Field *
							</label>
							<select
								name="careerField"
								value={formData.careerField}
								onChange={handleChange}
								className={`mt-1 block w-full px-3 py-2 border ${errors.careerField ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
							>
								{mockCareers.map(opt => (
									<option key={opt.value} value={opt.value}>{opt.label}</option>
								))}
							</select>
							{errors.careerField && <p className="mt-1 text-sm text-red-600">{errors.careerField}</p>}
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								NPWP *
							</label>
							<div className="flex space-x-1">
								{[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15].map((i) => (
									<input
										key={i}
										type="text"
										name="npwp"
										value=""
										onChange={() => { }}
										className="w-6 px-1 py-1 border border-gray-300 rounded-md text-center"
										maxLength={1}
									/>
								))}
							</div>
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Address in NPWP *
							</label>
							<textarea
								name="addressInNpwp"
								value={formData.addressInNpwp}
								onChange={handleChange}
								rows={2}
								className={`mt-1 block w-full px-3 py-2 border ${errors.addressInNpwp ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
							/>
							{errors.addressInNpwp && <p className="mt-1 text-sm text-red-600">{errors.addressInNpwp}</p>}
						</div>

						<div className="grid grid-cols-2 gap-4">
							<div>
								<label className="block text-sm font-medium text-gray-700">
									Area *
								</label>
								<select
									name="npwpArea"
									value={formData.npwpArea}
									onChange={handleChange}
									className={`mt-1 block w-full px-3 py-2 border ${errors.npwpArea ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
								>
									{mockAreas.map(opt => (
										<option key={opt.value} value={opt.value}>{opt.label}</option>
									))}
								</select>
								{errors.npwpArea && <p className="mt-1 text-sm text-red-600">{errors.npwpArea}</p>}
							</div>
							<div>
								<label className="block text-sm font-medium text-gray-700">
									Province *
								</label>
								<select
									name="npwpProvince"
									value={formData.npwpProvince}
									onChange={handleChange}
									className={`mt-1 block w-full px-3 py-2 border ${errors.npwpProvince ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
								>
									{mockProvinces.map(opt => (
										<option key={opt.value} value={opt.value}>{opt.label}</option>
									))}
								</select>
								{errors.npwpProvince && <p className="mt-1 text-sm text-red-600">{errors.npwpProvince}</p>}
							</div>
						</div>

						<div className="grid grid-cols-2 gap-4">
							<div>
								<label className="block text-sm font-medium text-gray-700">
									District/ City *
								</label>
								<select
									name="npwpDistrictCity"
									value={formData.npwpDistrictCity}
									onChange={handleChange}
									className={`mt-1 block w-full px-3 py-2 border ${errors.npwpDistrictCity ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
								>
									{mockCities.map(opt => (
										<option key={opt.value} value={opt.value}>{opt.label}</option>
									))}
								</select>
								{errors.npwpDistrictCity && <p className="mt-1 text-sm text-red-600">{errors.npwpDistrictCity}</p>}
							</div>
							<div>
								<label className="block text-sm font-medium text-gray-700">
									Kecamatan *
								</label>
								<select
									name="npwpKecamatan"
									value={formData.npwpKecamatan}
									onChange={handleChange}
									className={`mt-1 block w-full px-3 py-2 border ${errors.npwpKecamatan ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
								>
									{mockKecamatan.map(opt => (
										<option key={opt.value} value={opt.value}>{opt.label}</option>
									))}
								</select>
								{errors.npwpKecamatan && <p className="mt-1 text-sm text-red-600">{errors.npwpKecamatan}</p>}
							</div>
						</div>

						<div className="grid grid-cols-2 gap-4">
							<div>
								<label className="block text-sm font-medium text-gray-700">
									Kelurahan *
								</label>
								<select
									name="npwpKelurahan"
									value={formData.npwpKelurahan}
									onChange={handleChange}
									className={`mt-1 block w-full px-3 py-2 border ${errors.npwpKelurahan ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
								>
									{mockKelurahan.map(opt => (
										<option key={opt.value} value={opt.value}>{opt.label}</option>
									))}
								</select>
								{errors.npwpKelurahan && <p className="mt-1 text-sm text-red-600">{errors.npwpKelurahan}</p>}
							</div>
							<div>
								<label className="block text-sm font-medium text-gray-700">
									Post Code *
								</label>
								<input
									type="text"
									name="npwpPostCode"
									value={formData.npwpPostCode}
									onChange={handleChange}
									className={`mt-1 block w-full px-3 py-2 border ${errors.npwpPostCode ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
								/>
								{errors.npwpPostCode && <p className="mt-1 text-sm text-red-600">{errors.npwpPostCode}</p>}
							</div>
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Citizenship *
							</label>
							<div className="flex space-x-2">
								<select
									name="citizenship"
									value={formData.citizenship}
									onChange={handleChange}
									className={`w-1/3 px-3 py-2 border ${errors.citizenship ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
								>
									{mockCitizenships.map(opt => (
										<option key={opt.value} value={opt.value}>{opt.label}</option>
									))}
								</select>
								<select
									name="nationality"
									value={formData.spouseCitizenship}
									onChange={handleChange}
									className="w-2/3 px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
								>
									{mockNationalities.map(opt => (
										<option key={opt.value} value={opt.value}>{opt.label}</option>
									))}
								</select>
							</div>
							{errors.citizenship && <p className="mt-1 text-sm text-red-600">{errors.citizenship}</p>}
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								ID Card No. *
							</label>
							<input
								type="text"
								name="idCardNo"
								value={formData.idCardNo}
								onChange={handleChange}
								className={`mt-1 block w-full px-3 py-2 border ${errors.idCardNo ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
							/>
							{errors.idCardNo && <p className="mt-1 text-sm text-red-600">{errors.idCardNo}</p>}
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Validity ID Card *
							</label>
							<div className="flex space-x-2">
								<select
									name="validityIdCard"
									value={formData.validityIdCard}
									onChange={handleChange}
									className={`w-1/2 px-3 py-2 border ${errors.validityIdCard ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
								>
									<option value="No Expire Date">No Expire Date</option>
									<option value="Expire Date">Expire Date</option>
								</select>
								<input
									type="text"
									name="validityIdCard"
									value=""
									onChange={() => { }}
									className="w-1/2 px-3 py-2 border border-gray-300 rounded-md shadow-sm"
									placeholder="dd-mm-yyyy"
								/>
							</div>
							{errors.validityIdCard && <p className="mt-1 text-sm text-red-600">{errors.validityIdCard}</p>}
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Passport No.
							</label>
							<input
								type="text"
								name="passportNo"
								value={formData.passportNo}
								onChange={handleChange}
								className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
							/>
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Family Card No. *
							</label>
							<input
								type="text"
								name="familyCardNo"
								value={formData.familyCardNo}
								onChange={handleChange}
								className={`mt-1 block w-full px-3 py-2 border ${errors.familyCardNo ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
							/>
							{errors.familyCardNo && <p className="mt-1 text-sm text-red-600">{errors.familyCardNo}</p>}
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Mother's Maiden Name (Without Title) * <span className="text-blue-600">(i)</span>
							</label>
							<input
								type="text"
								name="mothersMaidenName"
								value={formData.mothersMaidenName}
								onChange={handleChange}
								className={`mt-1 block w-full px-3 py-2 border ${errors.mothersMaidenName ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
							/>
							{errors.mothersMaidenName && <p className="mt-1 text-sm text-red-600">{errors.mothersMaidenName}</p>}
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Marital Status *
							</label>
							<select
								name="maritalStatus"
								value={formData.maritalStatus}
								onChange={handleChange}
								className={`mt-1 block w-full px-3 py-2 border ${errors.maritalStatus ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
							>
								{mockMaritalStatuses.map(opt => (
									<option key={opt.value} value={opt.value}>{opt.label}</option>
								))}
							</select>
							{errors.maritalStatus && <p className="mt-1 text-sm text-red-600">{errors.maritalStatus}</p>}
						</div>

						{formData.maritalStatus === 'Married' && (
							<>
								<div className="pt-4 border-t">
									<h3 className="font-semibold text-gray-700">Spouse Information</h3>
								</div>

								<div>
									<label className="block text-sm font-medium text-gray-700">
										Spouse Name in ID Card * <span className="text-blue-600">(i)</span>
									</label>
									<input
										type="text"
										name="spouseNameInIdCard"
										value={formData.spouseNameInIdCard}
										onChange={handleChange}
										className={`mt-1 block w-full px-3 py-2 border ${errors.spouseNameInIdCard ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
									/>
									{errors.spouseNameInIdCard && <p className="mt-1 text-sm text-red-600">{errors.spouseNameInIdCard}</p>}
								</div>

								<div>
									<label className="block text-sm font-medium text-gray-700">
										Spouse Name Without Title * <span className="text-blue-600">(i)</span>
									</label>
									<input
										type="text"
										name="spouseNameWithoutTitle"
										value={formData.spouseNameWithoutTitle}
										onChange={handleChange}
										className={`mt-1 block w-full px-3 py-2 border ${errors.spouseNameWithoutTitle ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
									/>
									{errors.spouseNameWithoutTitle && <p className="mt-1 text-sm text-red-600">{errors.spouseNameWithoutTitle}</p>}
								</div>

								<div>
									<label className="block text-sm font-medium text-gray-700">
										Spouse Address in ID Card *
									</label>
									<div className="flex items-center space-x-4 mt-1">
										<label className="inline-flex items-center">
											<input
												type="radio"
												name="spouseAddressSameAsCustomer"
												checked={formData.spouseAddressSameAsCustomer}
												onChange={() => handleSpouseAddressChange(true)}
												className="mr-2"
											/>
											Same with Customer’s Address in ID Card
										</label>
										<label className="inline-flex items-center">
											<input
												type="radio"
												name="spouseAddressSameAsCustomer"
												checked={!formData.spouseAddressSameAsCustomer}
												onChange={() => handleSpouseAddressChange(false)}
												className="mr-2"
											/>
											Different with Customer’s Address in ID Card
										</label>
									</div>
									{!formData.spouseAddressSameAsCustomer && (
										<textarea
											name="spouseAddress"
											value={formData.spouseAddress}
											onChange={handleChange}
											rows={2}
											className={`mt-2 block w-full px-3 py-2 border ${errors.spouseAddress ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
										/>
									)}
									{errors.spouseAddress && <p className="mt-1 text-sm text-red-600">{errors.spouseAddress}</p>}
								</div>

								<div className="grid grid-cols-2 gap-4">
									<div>
										<label className="block text-sm font-medium text-gray-700">
											Area *
										</label>
										<select
											name="spouseArea"
											value={formData.spouseArea}
											onChange={handleChange}
											className={`mt-1 block w-full px-3 py-2 border ${errors.spouseArea ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
										>
											{mockAreas.map(opt => (
												<option key={opt.value} value={opt.value}>{opt.label}</option>
											))}
										</select>
										{errors.spouseArea && <p className="mt-1 text-sm text-red-600">{errors.spouseArea}</p>}
									</div>
									<div>
										<label className="block text-sm font-medium text-gray-700">
											Province *
										</label>
										<select
											name="spouseProvince"
											value={formData.spouseProvince}
											onChange={handleChange}
											className={`mt-1 block w-full px-3 py-2 border ${errors.spouseProvince ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
										>
											{mockProvinces.map(opt => (
												<option key={opt.value} value={opt.value}>{opt.label}</option>
											))}
										</select>
										{errors.spouseProvince && <p className="mt-1 text-sm text-red-600">{errors.spouseProvince}</p>}
									</div>
								</div>

								<div className="grid grid-cols-2 gap-4">
									<div>
										<label className="block text-sm font-medium text-gray-700">
											District/ City *
										</label>
										<select
											name="spouseDistrictCity"
											value={formData.spouseDistrictCity}
											onChange={handleChange}
											className={`mt-1 block w-full px-3 py-2 border ${errors.spouseDistrictCity ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
										>
											{mockCities.map(opt => (
												<option key={opt.value} value={opt.value}>{opt.label}</option>
											))}
										</select>
										{errors.spouseDistrictCity && <p className="mt-1 text-sm text-red-600">{errors.spouseDistrictCity}</p>}
									</div>
									<div>
										<label className="block text-sm font-medium text-gray-700">
											Kecamatan *
										</label>
										<select
											name="spouseKecamatan"
											value={formData.spouseKecamatan}
											onChange={handleChange}
											className={`mt-1 block w-full px-3 py-2 border ${errors.spouseKecamatan ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
										>
											{mockKecamatan.map(opt => (
												<option key={opt.value} value={opt.value}>{opt.label}</option>
											))}
										</select>
										{errors.spouseKecamatan && <p className="mt-1 text-sm text-red-600">{errors.spouseKecamatan}</p>}
									</div>
								</div>

								<div className="grid grid-cols-2 gap-4">
									<div>
										<label className="block text-sm font-medium text-gray-700">
											Kelurahan *
										</label>
										<select
											name="spouseKelurahan"
											value={formData.spouseKelurahan}
											onChange={handleChange}
											className={`mt-1 block w-full px-3 py-2 border ${errors.spouseKelurahan ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
										>
											{mockKelurahan.map(opt => (
												<option key={opt.value} value={opt.value}>{opt.label}</option>
											))}
										</select>
										{errors.spouseKelurahan && <p className="mt-1 text-sm text-red-600">{errors.spouseKelurahan}</p>}
									</div>
									<div>
										<label className="block text-sm font-medium text-gray-700">
											RT * / RW *
										</label>
										<div className="flex space-x-2">
											<input
												type="text"
												name="spouseRt"
												value={formData.spouseRt}
												onChange={handleChange}
												className={`w-1/2 px-3 py-2 border ${errors.spouseRt ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
											/>
											<input
												type="text"
												name="spouseRw"
												value={formData.spouseRw}
												onChange={handleChange}
												className={`w-1/2 px-3 py-2 border ${errors.spouseRw ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
											/>
										</div>
										{(errors.spouseRt || errors.spouseRw) && <p className="mt-1 text-sm text-red-600">{errors.spouseRt || errors.spouseRw}</p>}
									</div>
								</div>

								<div>
									<label className="block text-sm font-medium text-gray-700">
										Post Code *
									</label>
									<input
										type="text"
										name="spousePostCode"
										value={formData.spousePostCode}
										onChange={handleChange}
										className={`mt-1 block w-full px-3 py-2 border ${errors.spousePostCode ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
									/>
									{errors.spousePostCode && <p className="mt-1 text-sm text-red-600">{errors.spousePostCode}</p>}
								</div>

								<div>
									<label className="block text-sm font-medium text-gray-700">
										Place/ Date of Birth *
									</label>
									<div className="flex space-x-2">
										<input
											type="text"
											name="spousePlaceDateOfBirth"
											value={formData.spousePlaceDateOfBirth}
											onChange={handleChange}
											className={`w-1/2 px-3 py-2 border ${errors.spousePlaceDateOfBirth ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
										/>
										<input
											type="text"
											name="spousePlaceDateOfBirth"
											value=""
											onChange={() => { }}
											className="w-1/2 px-3 py-2 border border-gray-300 rounded-md shadow-sm"
											placeholder="dd-mm-yyyy"
										/>
									</div>
									{errors.spousePlaceDateOfBirth && <p className="mt-1 text-sm text-red-600">{errors.spousePlaceDateOfBirth}</p>}
								</div>

								<div>
									<label className="block text-sm font-medium text-gray-700">
										Citizenship *
									</label>
									<div className="flex space-x-2">
										<select
											name="spouseCitizenship"
											value={formData.spouseCitizenship}
											onChange={handleChange}
											className={`w-1/3 px-3 py-2 border ${errors.spouseCitizenship ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
										>
											{mockCitizenships.map(opt => (
												<option key={opt.value} value={opt.value}>{opt.label}</option>
											))}
										</select>
										<select
											name="spouseNationality"
											value={formData.spouseCitizenship}
											onChange={handleChange}
											className="w-2/3 px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
										>
											{mockNationalities.map(opt => (
												<option key={opt.value} value={opt.value}>{opt.label}</option>
											))}
										</select>
									</div>
									{errors.spouseCitizenship && <p className="mt-1 text-sm text-red-600">{errors.spouseCitizenship}</p>}
								</div>

								<div>
									<label className="block text-sm font-medium text-gray-700">
										ID Card No. *
									</label>
									<input
										type="text"
										name="spouseIdCardNo"
										value={formData.spouseIdCardNo}
										onChange={handleChange}
										className={`mt-1 block w-full px-3 py-2 border ${errors.spouseIdCardNo ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
									/>
									{errors.spouseIdCardNo && <p className="mt-1 text-sm text-red-600">{errors.spouseIdCardNo}</p>}
								</div>

								<div>
									<label className="block text-sm font-medium text-gray-700">
										Validity ID Card *
									</label>
									<div className="flex space-x-2">
										<select
											name="spouseValidityIdCard"
											value={formData.spouseValidityIdCard}
											onChange={handleChange}
											className={`w-1/2 px-3 py-2 border ${errors.spouseValidityIdCard ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
										>
											<option value="No Expire Date">No Expire Date</option>
											<option value="Expire Date">Expire Date</option>
										</select>
										<input
											type="text"
											name="spouseValidityIdCard"
											value=""
											onChange={() => { }}
											className="w-1/2 px-3 py-2 border border-gray-300 rounded-md shadow-sm"
											placeholder="dd-mm-yyyy"
										/>
									</div>
									{errors.spouseValidityIdCard && <p className="mt-1 text-sm text-red-600">{errors.spouseValidityIdCard}</p>}
								</div>

								<div>
									<label className="block text-sm font-medium text-gray-700">
										Passport No.
									</label>
									<input
										type="text"
										name="spousePassportNo"
										value={formData.spousePassportNo}
										onChange={handleChange}
										className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
									/>
								</div>

								<div>
									<label className="block text-sm font-medium text-gray-700">
										Marriage Agreement *
									</label>
									<select
										name="spouseMarriageAgreement"
										value={formData.spouseMarriageAgreement}
										onChange={handleChange}
										className={`mt-1 block w-full px-3 py-2 border ${errors.spouseMarriageAgreement ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
									>
										{mockMarriageAgreements.map(opt => (
											<option key={opt.value} value={opt.value}>{opt.label}</option>
										))}
									</select>
									{errors.spouseMarriageAgreement && <p className="mt-1 text-sm text-red-600">{errors.spouseMarriageAgreement}</p>}
								</div>

								<div>
									<label className="block text-sm font-medium text-gray-700">
										Total of Dependent
									</label>
									<div className="flex items-center space-x-2">
										<select
											name="spouseTotalDependent"
											value={formData.spouseTotalDependent}
											onChange={handleChange}
											className={`w-1/2 px-3 py-2 border ${errors.spouseTotalDependent ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
										>
											{mockDependents.map(opt => (
												<option key={opt.value} value={opt.value}>{opt.label}</option>
											))}
										</select>
										<span className="text-sm text-gray-700">person(s)</span>
									</div>
									{errors.spouseTotalDependent && <p className="mt-1 text-sm text-red-600">{errors.spouseTotalDependent}</p>}
								</div>

								<div>
									<label className="block text-sm font-medium text-gray-700">
										Relationship with Company *
									</label>
									<select
										name="spouseRelationshipWithCompany"
										value={formData.spouseRelationshipWithCompany}
										onChange={handleChange}
										className={`mt-1 block w-full px-3 py-2 border ${errors.spouseRelationshipWithCompany ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
									>
										{mockRelationshipsWithCompany.map(opt => (
											<option key={opt.value} value={opt.value}>{opt.label}</option>
										))}
									</select>
									{errors.spouseRelationshipWithCompany && <p className="mt-1 text-sm text-red-600">{errors.spouseRelationshipWithCompany}</p>}
								</div>
							</>
						)}

						<div className="pt-4 border-t">
							<h3 className="font-semibold text-gray-700">Emergency Contact</h3>
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Emergency Name *
							</label>
							<input
								type="text"
								name="emergencyName"
								value={formData.emergencyName}
								onChange={handleChange}
								className={`mt-1 block w-full px-3 py-2 border ${errors.emergencyName ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
							/>
							{errors.emergencyName && <p className="mt-1 text-sm text-red-600">{errors.emergencyName}</p>}
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Emergency Address *
							</label>
							<textarea
								name="emergencyAddress"
								value={formData.emergencyAddress}
								onChange={handleChange}
								rows={2}
								className={`mt-1 block w-full px-3 py-2 border ${errors.emergencyAddress ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
							/>
							{errors.emergencyAddress && <p className="mt-1 text-sm text-red-600">{errors.emergencyAddress}</p>}
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Emergency Phone *
							</label>
							<input
								type="text"
								name="emergencyPhone"
								value={formData.emergencyPhone}
								onChange={handleChange}
								className={`mt-1 block w-full px-3 py-2 border ${errors.emergencyPhone ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
							/>
							{errors.emergencyPhone && <p className="mt-1 text-sm text-red-600">{errors.emergencyPhone}</p>}
						</div>

						<div>
							<label className="block text-sm font-medium text-gray-700">
								Emergency Relation *
							</label>
							<input
								type="text"
								name="emergencyRelation"
								value={formData.emergencyRelation}
								onChange={handleChange}
								className={`mt-1 block w-full px-3 py-2 border ${errors.emergencyRelation ? 'border-red-500' : 'border-gray-300'} rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500`}
							/>
							{errors.emergencyRelation && <p className="mt-1 text-sm text-red-600">{errors.emergencyRelation}</p>}
						</div>

					</div>
				</div>

				<div className="mt-6 flex justify-end">
					<button
						type="submit"
						className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2"
					>
						Next
					</button>
				</div>
			</form>
		</div>
	);
};

export default CustomerDetailForm;