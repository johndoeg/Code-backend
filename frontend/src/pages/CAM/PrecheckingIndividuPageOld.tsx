import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import { useLocation, useNavigate } from 'react-router-dom';

interface OCRData {
    nik?: string;
    nama?: string;
    tempatLahir?: string;
    tanggalLahir?: string;
    jenisKelamin?: string;
    golonganDarah?: string;
    alamat?: string;
    rtRw?: string;
    kelurahanDesa?: string;
    kecamatan?: string;
    kotaKabupaten?: string;
    provinsi?: string;
    agama?: string;
    pekerjaan?: string;
    photo?: string;
    sign?: string;
    [key: string]: string | undefined;
}

interface OCRResponse {
    status: string;
        reason: string;
        qualities?: {
            blur: { value: boolean };
            document: { value: string };
        };
        read?: OCRData;
        images?: {
        photo?: string;
        sign?: string;
    };
}

interface CustomerData {
    idCardNo: string;
    name: string;
    placeOfBirth: string;
    dateOfBirth: string;
    gender: string;
    bloodType: string;
    address: string;
    rt: string;
    rw: string;
    subdistrict: string;
    district: string;
    city: string;
    province: string;
    religion: string;
    job: string;
    photo?: string;
    signature?: string;
}

interface FormData {
    precheckingId: string;
    apless: string;
    customerType: 'PR';
    checkFor: 'C';
    nationality: 'WNI' | 'WNA';
    maritalStatus: string;
    spouseNationality?: 'WNI' | 'WNA';
    customer: Partial<CustomerData>;
    spouse?: Partial<CustomerData>;
    wnaData?: {
        name: string;
        idCardNo: string;
        maritalStatus: string;
        spouseName?: string;
        spouseIdCardNo?: string;
    };
    files: {
        ktp?: File;
        spouseKtp?: File;
        kitas?: File;
        spouseKitas?: File;
        kk?: File[];
        npwp?: File[];
        marriageStatement?: File[];
    };
    notes: string;
    isCarro: boolean;
}

interface ValidationErrors {
    [key: string]: string;
}

const PrecheckingIndividuPage: React.FC = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const fileInputRefs = useRef<{ [key: string]: HTMLInputElement | null }>({});

    // State
    const [loading, setLoading] = useState(false);
    const [ocrLoading, setOcrLoading] = useState(false);
    const [formData, setFormData] = useState<FormData>({
        precheckingId: '',
        apless: '',
        customerType: 'PR',
        checkFor: 'C',
        nationality: 'WNI',
        maritalStatus: '',
        customer: {},
        files: {},
        notes: '',
        isCarro: true,
    });

    const [ocrResults, setOcrResults] = useState<{
        customer?: { read: OCRData; images?: { photo?: string; sign?: string } };
        spouse?: { read: OCRData; images?: { photo?: string; sign?: string } };
        wnaSpouse?: { read: OCRData; images?: { photo?: string; sign?: string } };
    }>({});

    const [verificationResults, setVerificationResults] = useState<{
        customer?: Record<string, string>;
        spouse?: Record<string, string>;
        wnaSpouse?: Record<string, string>;
    }>({});
        const [errors, setErrors] = useState<ValidationErrors>({});
        const [showSpouseSection, setShowSpouseSection] = useState(false);
        const [showWNASection, setShowWNASection] = useState(false);
        const [showWNASpouseSection, setShowWNASpouseSection] = useState(false);
        const [modal, setModal] = useState<{
            show: boolean;
            type: 'reject' | 'inprogress' | 'valid' | 'expired' | null;
            message: string;
            apless?: string;
            precheckingId?: string;
        }>({ show: false, type: null, message: '' });

    const API_BASE = import.meta.env.VITE_API_URL || '/api';

    useEffect(() => {
        const initializeForm = async () => {
        setLoading(true);
            try {
                const [aplessRes, precheckRes] = await Promise.all([
                    axios.post(`${API_BASE}/cam_request_generate_temp_apless`, { customer_type: 'PR' }),
                    axios.post(`${API_BASE}/cam_request_generate_temp_precheckingid`, {}),
                ]);
                
                setFormData(prev => ({
                    ...prev,
                    apless: aplessRes.data,
                    precheckingId: precheckRes.data,
                    ...location.state,
                }));
            } catch (error) {
                console.error('Failed to initialize form:', error);
            } finally {
                setLoading(false);
            }
        };
        initializeForm();
    }, [location.state]);

    const handleNationalityChange = (value: 'WNI' | 'WNA') => {
        setFormData(prev => ({ ...prev, nationality: value }));
        setShowWNASection(value === 'WNA');
        if (value === 'WNI') {
            setShowSpouseSection(false);
            setShowWNASpouseSection(false);
        }
    };

    const handleMaritalStatusChange = (value: string) => {
        setFormData(prev => ({ ...prev, maritalStatus: value }));
        const isMarried = ['M', 'O'].includes(value);
        setShowSpouseSection(isMarried && formData.nationality === 'WNI');
        setShowWNASpouseSection(isMarried && formData.nationality === 'WNA');
        if (!isMarried) {
            setFormData(prev => ({ ...prev, spouseNationality: undefined }));
        }
    };

    const handleSpouseNationalityChange = (value: 'WNI' | 'WNA') => {
            setFormData(prev => ({ ...prev, spouseNationality: value }));
                if (formData.nationality === 'WNI') {
                if (value === 'WNI') {
                    // Show WNI spouse OCR section
                } else {
                    // Show WNA spouse section
                }
            }
    };

    const handleFileUpload = async (file: File, type: 'customer' | 'spouse' | 'wna_spouse') => {
        if (file.size > 10 * 1024 * 1024) {
            alert('File size exceeds 10 MB');
            return;
        }

        setOcrLoading(true);
        try {
            const qualityFormData = new FormData();
            qualityFormData.append('image', file);
            qualityFormData.append('param', 'check_qualities');
            qualityFormData.append('prechecking_id', formData.precheckingId);

            const qualityRes = await axios.post<OCRResponse>(
                `${API_BASE}/scanOCRCustomer`,
                qualityFormData,
                { headers: { 'Content-Type': 'multipart/form-data' } }
            );

            if (qualityRes.data.status !== 'SUCCESS' || qualityRes.data.qualities?.blur.value) {
                alert('Document checking failed. Please upload a clearer image.');
                return;
            }

            const ocrFormData = new FormData();
            ocrFormData.append('image', file);
            ocrFormData.append('param', 'ocr_customer');
            ocrFormData.append('apless', formData.apless);
            ocrFormData.append('customer_type', 'PR');
            ocrFormData.append('prechecking_id', formData.precheckingId);
            ocrFormData.append('check_for', 'C');
            ocrFormData.append('repeat_order', '0');
            ocrFormData.append('ocr_for', type === 'customer' ? 'C' : 'S');

            const ocrRes = await axios.post<OCRResponse>(
                `${API_BASE}/scanOCRCustomer`,
                ocrFormData,
                { headers: { 'Content-Type': 'multipart/form-data' } }
            );

            if (ocrRes.data.status === 'SUCCESS' && ocrRes.data.read) {
                setOcrResults(prev => ({
                    ...prev,
                    [type]: {
                        read: ocrRes.data.read!,
                        images: ocrRes.data.images,
                    },
                }));

                const ocrData = ocrRes.data.read;
                const rtRw = ocrData.rtRw?.split('/') || ['', ''];
                
                setFormData(prev => ({
                    ...prev,
                    customer: type === 'customer' ? {
                        ...prev.customer,
                        idCardNo: ocrData.nik || '',
                        name: ocrData.nama || '',
                        placeOfBirth: ocrData.tempatLahir || '',
                        dateOfBirth: ocrData.tanggalLahir || '',
                        gender: ocrData.jenisKelamin || '',
                        bloodType: ocrData.golonganDarah || '',
                        address: ocrData.alamat || '',
                        rt: rtRw[0] || '',
                        rw: rtRw[1] || '',
                        subdistrict: ocrData.kelurahanDesa || '',
                        district: ocrData.kecamatan || '',
                        city: ocrData.kotaKabupaten || '',
                        province: ocrData.provinsi || '',
                        religion: ocrData.agama || '',
                        job: ocrData.pekerjaan || '',
                        photo: ocrRes.data.images?.photo,
                        signature: ocrRes.data.images?.sign,
                    } : prev.customer,
                }));

                if (type === 'customer') {
                const historyRes = await axios.post(`${API_BASE}/checking_customer_history`, {
                    idNo: ocrData.nik,
                    prechecking_id: formData.precheckingId,
                    lesseeType: 'PR',
                    checking_for: 'C',
                });

                if (historyRes.data[0]?.length) {
                    showHistoryModal(
                    historyRes.data[0],
                    historyRes.data[1],
                    historyRes.data[2],
                    historyRes.data[3]
                    );
                }
            }
            }
        } catch (error: any) {
            console.error('OCR failed:', error);
            alert(error.response?.data?.reason || 'OCR processing failed');
        } finally {
            setOcrLoading(false);
        }
    };

    const handleVerify = async (type: 'customer' | 'spouse' | 'wna_spouse') => {
        setLoading(true);
        try {
            const data = {
                param: 'check_data_duckapil',
                prechecking_id: formData.precheckingId,
                ...(type === 'customer' ? {
                nik: formData.customer.idCardNo,
                name: formData.customer.name,
                place_of_birth: formData.customer.placeOfBirth,
                date_of_birth: formData.customer.dateOfBirth,
                gender: formData.customer.gender,
                address: formData.customer.address,
                rt: formData.customer.rt,
                rw: formData.customer.rw,
                subdistrict: formData.customer.subdistrict,
                district: formData.customer.district,
                city: formData.customer.city,
                province: formData.customer.province,
                job_type: formData.customer.job,
                } : {}),
        };

        const res = await axios.post(`${API_BASE}/scanOCRCustomer`, data);
        
        if (res.data.result) {
                setVerificationResults(prev => ({
                ...prev,
                [type]: res.data.result,
                }));
            }
        } catch (error) {
            console.error('Verification failed:', error);
            alert('Verification failed');
        } finally {
            setLoading(false);
        }
    };

    const showHistoryModal = (message: string, apless: string, type: string, precheckingId: string) => {
        setModal({
            show: true,
            type: type as any,
            message,
            apless,
            precheckingId,
        });
    };

    const handleSubmit = async (action: 'save' | 'cancel') => {
        if (action === 'cancel') {
            try {
                await axios.post(`${API_BASE}/prechecking_back_end`, {
                addmode: 99,
                prechecking_id: formData.precheckingId,
                });
                navigate('/');
            } catch (error) {
                console.error('Cancel failed:', error);
            }
            return;
        }

        const newErrors: ValidationErrors = {};
        if (!formData.customer.idCardNo) newErrors.customer_idCardNo = 'NIK is required';
        if (!formData.customer.name) newErrors.customer_name = 'Name is required';
        if (!formData.customer.placeOfBirth) newErrors.customer_name = 'Place of Birth is required';
        if (!formData.customer.dateOfBirth) newErrors.customer_name = 'Date Of Birth is required';
        if (!formData.customer.gender) newErrors.customer_name = 'Gender is required';
        if (!formData.customer.bloodType) newErrors.customer_name = 'bloodType is required';
        if (!formData.customer.address) newErrors.customer_name = 'address';
        if (!formData.customer.rt) newErrors.customer_name = 'RT/RW is required';
        if (!formData.customer.subdistrict) newErrors.customer_name = 'Subdistrict is required';
        if (!formData.customer.district) newErrors.customer_name = 'District';
        if (!formData.customer.city) newErrors.customer_name = 'city is required';
        if (!formData.customer.province) newErrors.customer_name = 'Province is required';
        if (!formData.customer.religion) newErrors.customer_name = 'Religion is required';
        if (!formData.customer.job) newErrors.customer_name = 'Job is required';
    
        if (Object.keys(newErrors).length > 0) {
            setErrors(newErrors);
            return;
        }

        setLoading(true);
        try {
            const submitData = new FormData();
            submitData.append('prechecking_id', formData.precheckingId);
            submitData.append('apless', formData.apless);
        
            await axios.post(`${API_BASE}/prechecking_pr`, submitData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            });
        
            navigate('/next-page', { state: { precheckingId: formData.precheckingId } });
        } catch (error: any) {
            console.error('Submit failed:', error);
            alert(error.response?.data?.message || 'Submission failed');
        } finally {
            setLoading(false);
        }
    };

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>, type: 'ktp' | 'spouse_ktp' | 'kitas' | 'spouse_kitas') => {
        const file = e.target.files?.[0];
        if (file) {
            setFormData(prev => ({
                ...prev,
                files: { ...prev.files, [type]: file },
            }));
            if (type === 'ktp' || type === 'spouse_ktp') {
                handleFileUpload(file, type === 'ktp' ? 'customer' : 'spouse');
            }
        }
    };

    const OCRDataRow: React.FC<{
        label: string;
        field: keyof CustomerData;
        value: string;
        ocrValue?: string;
        confidence?: string;
        verifiedValue?: string;
        error?: string;
        onChange: (value: string) => void;
        required?: boolean;
    }> = ({ label, field, value, ocrValue, confidence, verifiedValue, error, onChange, required }) => (
        <tr className="border-b border-gray-100">
            <td className="py-3 px-3 font-medium text-gray-700">
                {label}
                {required && <span className="text-red-500 ml-1">*</span>}
            </td>
            <td className="py-3 px-3">
                <input
                    type="text"
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
                        error ? 'border-red-500' : 'border-gray-300'
                    }`}
                    maxLength={field === 'address' ? 250 : field === 'idCardNo' ? 16 : 100}
                />
                {error && <p className="text-red-500 text-sm mt-1">{error}</p>}
            </td>
            <td className="py-3 px-3 text-center">
                <input
                    type="text"
                    value={confidence || ''}
                    readOnly
                    className="w-full px-2 py-1 bg-gray-50 border border-gray-200 rounded text-center text-sm"
                />
            </td>
            <td className="py-3 px-3 text-center">
                <input
                    type="text"
                    value={verifiedValue || ''}
                    readOnly
                    className="w-full px-2 py-1 bg-green-50 border border-green-200 rounded text-center text-sm text-green-700"
                />
            </td>
        </tr>
    );

    if (loading) {
        return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50">
            <div className="text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-500 border-t-transparent mx-auto mb-4"></div>
                <p className="text-gray-600">Loading...</p>
            </div>
        </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50 py-8">
            <div className="max-w-7xl mx-auto px-3">
                {/* Header */}
                <div className="bg-blue-800 text-white rounded-t-xl p-4 flex justify-between items-center">
                    <h1 className="text-xl font-bold">Add Prechecking Data</h1>
                    <div className="text-sm">
                        Prechecking ID: 
                        <input
                            type="text"
                            value={formData.precheckingId}
                            readOnly
                            className="ml-2 px-2 py-1 bg-blue-700 border-none text-white font-bold rounded w-24 text-center"
                        />
                    </div>
                </div>

                <form className="bg-white rounded-b-xl shadow-lg p-6 space-y-6">
                    {/* Basic Info Section */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                Checking For <span className="text-red-500">*</span>
                            </label>
                        </div>
                        <div>
                            <select
                                value={formData.checkFor}
                                disabled
                                className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50"
                            >
                                <option value="C">Customer</option>
                            </select>
                        </div>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                Consumer Type <span className="text-red-500">*</span>
                            </label>
                        </div>
                        <div>
                            <select
                                value={formData.customerType}
                                disabled
                                className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50"
                            >
                                <option value="PR">Individu</option>
                            </select>
                        </div>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                New/Repeat Order
                            </label>
                        </div>
                        <div>
                            <select
                                value="New"
                                disabled
                                className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50"
                            >
                                <option value="New">New</option>
                            </select>
                        </div>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                Temporary Customer No.
                            </label>
                        </div>
                        <div>
                            <input
                                type="text"
                                value={formData.apless}
                                readOnly
                                className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50"
                            />
                        </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                            Marital Status <span className="text-red-500">*</span>
                            </label>
                        </div>
                        <div>
                            <select
                                value={formData.maritalStatus}
                                onChange={(e) => handleMaritalStatusChange(e.target.value)}
                                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                            >
                            <option value="">Select</option>
                            <option value="S">Single</option>
                            <option value="M">Married</option>
                            <option value="O">Other</option>
                            </select>
                        </div>
                    </div>

                    {/* WNI Customer OCR Section */}
                    {formData.nationality === 'WNI' && (
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <label className="text-sm font-medium text-gray-700">
                            Upload ID Card for OCR <span className="text-red-500">*</span>
                            </label>
                            <input
                                type="file"
                                ref={el => fileInputRefs.current['ktp'] = el}
                                accept=".png,.jpg,.jpeg,.pdf,.tiff"
                                onChange={(e) => handleFileChange(e, 'ktp')}
                                className="text-sm"
                            />
                        </div>

                        {ocrLoading && (
                            <div className="flex items-center justify-center py-4">
                            <div className="animate-spin rounded-full h-8 w-8 border-4 border-blue-500 border-t-transparent mr-3"></div>
                            <span className="text-gray-600">Processing OCR...</span>
                            </div>
                        )}

                        <div className="overflow-x-auto">
                            <table className="w-full border-collapse">
                                <thead>
                                    <tr className="bg-blue-800 text-white">
                                        <th className="py-3 px-3 text-left w-1/4">Field</th>
                                        <th className="py-3 px-3 text-left w-1/3">Value</th>
                                        <th className="py-3 px-3 text-center w-1/6">Confidence</th>
                                        <th className="py-3 px-3 text-center w-1/6">
                                            <button
                                                type="button"
                                                onClick={() => handleVerify('customer')}
                                                disabled={loading}
                                                className="px-3 py-1 bg-green-600 hover:bg-green-700 text-white rounded text-sm disabled:opacity-50"
                                            >
                                            Verify
                                            </button>
                                        </th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <OCRDataRow
                                        label="NIK"
                                        field="idCardNo"
                                        value={formData.customer.idCardNo || ''}
                                        ocrValue={ocrResults.customer?.read?.nik}
                                        confidence={ocrResults.customer?.read?.nik ? '85%' : undefined}
                                        verifiedValue={verificationResults.customer?.nik}
                                        error={errors.customer_idCardNo}
                                        onChange={(val) => setFormData(prev => ({
                                            ...prev,
                                            customer: { ...prev.customer, idCardNo: val }
                                        }))}
                                        required
                                    />
                                    <OCRDataRow
                                        label="Nama"
                                        field="name"
                                        value={formData.customer.name || ''}
                                        ocrValue={ocrResults.customer?.read?.nama}
                                        confidence={ocrResults.customer?.read?.nama ? '90%' : undefined}
                                        verifiedValue={verificationResults.customer?.name}
                                        error={errors.customer_name}
                                        onChange={(val) => setFormData(prev => ({
                                            ...prev,
                                            customer: { ...prev.customer, name: val }
                                        }))}
                                        required
                                    />
                                    {/* Add more rows for other fields... */}
                                    <OCRDataRow
                                        label="Tempat Lahir"
                                        field="placeOfBirth"
                                        value={formData.customer.placeOfBirth || ''}
                                        ocrValue={ocrResults.customer?.read?.tempatLahir}
                                        confidence={ocrResults.customer?.read?.tempatLahir ? '99%' : undefined}
                                        verifiedValue={verificationResults.customer?.place_of_birth}
                                        error={errors.customer_placeOfBirth}
                                        onChange={(val) => setFormData(prev => ({
                                            ...prev,
                                            customer: { ...prev.customer, placeOfBirth: val }
                                        }))}
                                        required
                                    />
                                    <OCRDataRow
                                        label="Tgl Lahir"
                                        field="dateOfBirth"
                                        value={formData.customer.dateOfBirth || ''}
                                        ocrValue={ocrResults.customer?.read?.tanggalLahir}
                                        confidence={ocrResults.customer?.read?.tanggalLahir ? '99%' : undefined}
                                        verifiedValue={verificationResults.customer?.date_of_birth}
                                        error={errors.customer_dateOfBirth}
                                        onChange={(val) => setFormData(prev => ({
                                            ...prev,
                                            customer: { ...prev.customer, dateOfBirth: val }
                                        }))}
                                        required
                                    />
                                    <OCRDataRow
                                        label="Jenis Kelamin"
                                        field="gender"
                                        value={formData.customer.gender || ''}
                                        ocrValue={ocrResults.customer?.read?.jenisKelamin}
                                        confidence={ocrResults.customer?.read?.jenisKelamin ? '94%' : undefined}
                                        verifiedValue={verificationResults.customer?.gender}
                                        error={errors.customer_gender}
                                        onChange={(val) => setFormData(prev => ({
                                            ...prev,
                                            customer: { ...prev.customer, gender: val }
                                        }))}
                                        required
                                    />
                                    <OCRDataRow
                                        label="Golongan Darah"
                                        field="bloodType"
                                        value={formData.customer.bloodType || ''}
                                        ocrValue={ocrResults.customer?.read?.golonganDarah}
                                        confidence={ocrResults.customer?.read?.golonganDarah ? '0%' : undefined}
                                        verifiedValue={verificationResults.customer?.blood_type}
                                        error={errors.customer_bloodType}
                                        onChange={(val) => setFormData(prev => ({
                                            ...prev,
                                            customer: { ...prev.customer, bloodType: val }
                                        }))}
                                    />
                                    <OCRDataRow
                                        label="Alamat"
                                        field="address"
                                        value={formData.customer.address || ''}
                                        ocrValue={ocrResults.customer?.read?.alamat}
                                        confidence={ocrResults.customer?.read?.alamat ? '99%' : undefined}
                                        verifiedValue={verificationResults.customer?.address}
                                        error={errors.customer_address}
                                        onChange={(val) => setFormData(prev => ({
                                            ...prev,
                                            customer: { ...prev.customer, address: val }
                                        }))}
                                        required
                                    />
                                    <OCRDataRow
                                        label="RT/RW"
                                        field="rt"
                                        value={`${formData.customer.rt || ''} / ${formData.customer.rw || ''}`}
                                        ocrValue={ocrResults.customer?.read?.rtRw}
                                        confidence={ocrResults.customer?.read?.rtRw ? '99%' : undefined}
                                        verifiedValue={verificationResults.customer?.rt ? `${verificationResults.customer.rt} / ${verificationResults.customer.rw}` : undefined}
                                        error={errors.customer_rt}
                                        onChange={(val) => {
                                            const [rt, rw] = val.split('/').map(s => s.trim());
                                            setFormData(prev => ({
                                                ...prev,
                                                customer: { ...prev.customer, rt: rt || '', rw: rw || '' }
                                            }));
                                        }}
                                        required
                                    />
                                    <OCRDataRow
                                        label="Kelurahan/Desa"
                                        field="subdistrict"
                                        value={formData.customer.subdistrict || ''}
                                        ocrValue={ocrResults.customer?.read?.kelurahanDesa}
                                        confidence={ocrResults.customer?.read?.kelurahanDesa ? '99%' : undefined}
                                        verifiedValue={verificationResults.customer?.subdistrict}
                                        error={errors.customer_subdistrict}
                                        onChange={(val) => setFormData(prev => ({
                                            ...prev,
                                            customer: { ...prev.customer, subdistrict: val }
                                        }))}
                                        required
                                    />
                                    <OCRDataRow
                                        label="Kecamatan"
                                        field="district"
                                        value={formData.customer.district || ''}
                                        ocrValue={ocrResults.customer?.read?.kecamatan}
                                        confidence={ocrResults.customer?.read?.kecamatan ? '100%' : undefined}
                                        verifiedValue={verificationResults.customer?.district}
                                        error={errors.customer_district}
                                        onChange={(val) => setFormData(prev => ({
                                            ...prev,
                                            customer: { ...prev.customer, district: val }
                                        }))}
                                        required
                                    />
                                    <OCRDataRow
                                        label="Kota/Kabupaten"
                                        field="city"
                                        value={formData.customer.city || ''}
                                        ocrValue={ocrResults.customer?.read?.kotaKabupaten}
                                        confidence={ocrResults.customer?.read?.kotaKabupaten ? '99%' : undefined}
                                        verifiedValue={verificationResults.customer?.city}
                                        error={errors.customer_city}
                                        onChange={(val) => setFormData(prev => ({
                                            ...prev,
                                            customer: { ...prev.customer, city: val }
                                        }))}
                                        required
                                    />
                                    <OCRDataRow
                                        label="Provinsi"
                                        field="province"
                                        value={formData.customer.province || ''}
                                        ocrValue={ocrResults.customer?.read?.provinsi}
                                        confidence={ocrResults.customer?.read?.provinsi ? '99%' : undefined}
                                        verifiedValue={verificationResults.customer?.province}
                                        error={errors.customer_province}
                                        onChange={(val) => setFormData(prev => ({
                                            ...prev,
                                            customer: { ...prev.customer, province: val }
                                        }))}
                                        required
                                    />
                                    <OCRDataRow
                                        label="Agama"
                                        field="religion"
                                        value={formData.customer.religion || ''}
                                        ocrValue={ocrResults.customer?.read?.agama}
                                        confidence={ocrResults.customer?.read?.agama ? '99%' : undefined}
                                        verifiedValue={verificationResults.customer?.religion}
                                        error={errors.customer_religion}
                                        onChange={(val) => setFormData(prev => ({
                                            ...prev,
                                            customer: { ...prev.customer, religion: val }
                                        }))}
                                        required
                                    />
                                    <OCRDataRow
                                        label="Pekerjaan"
                                        field="job"
                                        value={formData.customer.job || ''}
                                        ocrValue={ocrResults.customer?.read?.pekerjaan}
                                        confidence={ocrResults.customer?.read?.pekerjaan ? '99%' : undefined}
                                        verifiedValue={verificationResults.customer?.job_type}
                                        error={errors.customer_job}
                                        onChange={(val) => setFormData(prev => ({
                                            ...prev,
                                            customer: { ...prev.customer, job: val }
                                        }))}
                                        required
                                    />
                                    
                                    {/* Photo & Signature */}
                                    <tr className="border-b border-gray-100">
                                        <td className="py-3 px-3 font-medium text-gray-700">
                                            Foto <span className="text-red-500">*</span>
                                        </td>
                                        <td colSpan={3}>
                                            {formData.customer.photo || ocrResults.customer?.images?.photo ? (
                                            <img
                                                src={`data:image/jpeg;base64,${formData.customer.photo || ocrResults.customer?.images?.photo}`}
                                                alt="Customer Photo"
                                                className="h-32 w-24 object-cover border rounded"
                                            />
                                            ) : (
                                            <div className="h-32 w-24 bg-gray-100 border-2 border-dashed border-gray-300 rounded flex items-center justify-center text-gray-400 text-sm">
                                                No Photo
                                            </div>
                                            )}
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                    )}

                    {/* WNA Section */}
                    {showWNASection && (
                    <div className="space-y-4 p-4 bg-blue-50 rounded-lg">
                        <h3 className="font-semibold text-blue-900">WNA Customer Details</h3>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Name <span className="text-red-500">*</span>
                                </label>
                                <input
                                    type="text"
                                    value={formData.wnaData?.name || ''}
                                    onChange={(e) => setFormData(prev => ({
                                    ...prev,
                                    wnaData: { ...prev.wnaData!, name: e.target.value }
                                    }))}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                                />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">
                                        ID Card No. <span className="text-red-500">*</span>
                                    </label>
                                    <input
                                        type="text"
                                        value={formData.wnaData?.idCardNo || ''}
                                        onChange={(e) => setFormData(prev => ({
                                        ...prev,
                                        wnaData: { ...prev.wnaData!, idCardNo: e.target.value }
                                    }))}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                                />
                                </div>
                        </div>
                    {/* Add more WNA fields... */}
                    </div>
                    )}

                    {/* Spouse Section */}
                    <div className="border-t pt-6">

                        {/* Spouse Section for WNI */}
                        {showSpouseSection && formData.nationality === 'WNI' && (
                        <div className="mt-6 p-4 bg-gray-50 rounded-lg">
                            <h3 className="font-semibold text-gray-800 mb-4">Spouse Details (WNI)</h3>
                            <div className="space-y-4 mb-4">
                                <div className="flex items-center gap-4">
                                    <label className="w-48 text-sm font-medium text-gray-700">
                                    Spouse Nationality
                                    </label>
                                    <select
                                        value={formData.spouseNationality || ''}
                                        onChange={(e) => handleSpouseNationalityChange(e.target.value as 'WNI' | 'WNA')}
                                        className="flex-1 max-w-xs px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                                        >
                                        <option value="">Select</option>
                                        <option value="WNI">WNI</option>
                                        <option value="WNA">WNA</option>
                                    </select>
                                </div>

                                {formData.spouseNationality === 'WNI' && (
                                <div className="flex items-center gap-4">
                                <label className="w-48 text-sm font-medium text-gray-700">
                                    Upload Spouse ID Card for OCR
                                </label>
                                <input
                                    type="file"
                                    accept=".png,.jpg,.jpeg,.pdf,.tiff"
                                    onChange={(e) => {
                                    const file = e.target.files?.[0];
                                    if (file) handleFileUpload(file, 'spouse');
                                    }}
                                    className="text-sm"
                                />
                                </div>
                                )}
                            </div>
                            
                            {/* Spouse OCR Table - Proper table structure */}
                            {formData.spouseNationality === 'WNI' && ocrResults.spouse && (
                            <div className="overflow-x-auto">
                                <table className="w-full border-collapse">
                                    <thead>
                                        <tr className="bg-blue-800 text-white">
                                            <th className="py-3 px-3 text-left w-1/4">Field</th>
                                            <th className="py-3 px-3 text-left w-1/3">Value</th>
                                            <th className="py-3 px-3 text-center w-1/6">Confidence</th>
                                            <th className="py-3 px-3 text-center w-1/6">
                                                <button
                                                type="button"
                                                onClick={() => handleVerify('spouse')}
                                                disabled={loading}
                                                className="px-3 py-1 bg-green-600 hover:bg-green-700 text-white rounded text-sm disabled:opacity-50"
                                                >
                                                Verify
                                                </button>
                                            </th>
                                        </tr>
                                    </thead>
                                <tbody>
                                    <OCRDataRow
                                        label="NIK"
                                        field="idCardNo"
                                        value={formData.spouse?.idCardNo || ''}
                                        ocrValue={ocrResults.spouse?.read?.nik}
                                        confidence={ocrResults.spouse?.read?.nik ? '99%' : undefined}
                                        verifiedValue={verificationResults.spouse?.nik}
                                        error={errors.spouse_idCardNo}
                                        onChange={(val) => setFormData(prev => ({
                                            ...prev,
                                            spouse: { ...prev.spouse, idCardNo: val }
                                        }))}
                                        required
                                    />
                                    <OCRDataRow
                                        label="Nama"
                                        field="name"
                                        value={formData.spouse?.name || ''}
                                        ocrValue={ocrResults.spouse?.read?.nama}
                                        confidence={ocrResults.spouse?.read?.nama ? '99%' : undefined}
                                        verifiedValue={verificationResults.spouse?.name}
                                        error={errors.spouse_name}
                                        onChange={(val) => setFormData(prev => ({
                                            ...prev,
                                            spouse: { ...prev.spouse, name: val }
                                        }))}
                                        required
                                    />
                                    <OCRDataRow
                                        label="Tempat Lahir"
                                        field="placeOfBirth"
                                        value={formData.spouse?.placeOfBirth || ''}
                                        ocrValue={ocrResults.spouse?.read?.tempatLahir}
                                        confidence={ocrResults.spouse?.read?.tempatLahir ? '99%' : undefined}
                                        verifiedValue={verificationResults.spouse?.place_of_birth}
                                        error={errors.spouse_placeOfBirth}
                                        onChange={(val) => setFormData(prev => ({
                                            ...prev,
                                            spouse: { ...prev.spouse, placeOfBirth: val }
                                        }))}
                                        required
                                    />
                                    <OCRDataRow
                                        label="Tgl Lahir"
                                        field="dateOfBirth"
                                        value={formData.spouse?.dateOfBirth || ''}
                                        ocrValue={ocrResults.spouse?.read?.tanggalLahir}
                                        confidence={ocrResults.spouse?.read?.tanggalLahir ? '99%' : undefined}
                                        verifiedValue={verificationResults.spouse?.date_of_birth}
                                        error={errors.spouse_dateOfBirth}
                                        onChange={(val) => setFormData(prev => ({
                                            ...prev,
                                            spouse: { ...prev.spouse, dateOfBirth: val }
                                        }))}
                                        required
                                    />
                                    <OCRDataRow
                                        label="Jenis Kelamin"
                                        field="gender"
                                        value={formData.spouse?.gender || ''}
                                        ocrValue={ocrResults.spouse?.read?.jenisKelamin}
                                        confidence={ocrResults.spouse?.read?.jenisKelamin ? '94%' : undefined}
                                        verifiedValue={verificationResults.spouse?.gender}
                                        error={errors.spouse_gender}
                                        onChange={(val) => setFormData(prev => ({
                                            ...prev,
                                            spouse: { ...prev.spouse, gender: val }
                                        }))}
                                        required
                                    />
                                    <OCRDataRow
                                        label="Golongan Darah"
                                        field="bloodType"
                                        value={formData.spouse?.bloodType || ''}
                                        ocrValue={ocrResults.spouse?.read?.golonganDarah}
                                        confidence={ocrResults.spouse?.read?.golonganDarah ? '0%' : undefined}
                                        verifiedValue={verificationResults.spouse?.blood_type}
                                        error={errors.spouse_bloodType}
                                        onChange={(val) => setFormData(prev => ({
                                            ...prev,
                                            spouse: { ...prev.spouse, bloodType: val }
                                        }))}
                                    />
                                    <OCRDataRow
                                        label="Alamat"
                                        field="address"
                                        value={formData.spouse?.address || ''}
                                        ocrValue={ocrResults.spouse?.read?.alamat}
                                        confidence={ocrResults.spouse?.read?.alamat ? '99%' : undefined}
                                        verifiedValue={verificationResults.spouse?.address}
                                        error={errors.spouse_address}
                                        onChange={(val) => setFormData(prev => ({
                                            ...prev,
                                            spouse: { ...prev.spouse, address: val }
                                        }))}
                                        required
                                    />
                                    <OCRDataRow
                                        label="RT/RW"
                                        field="rt"
                                        value={`${formData.spouse?.rt || ''} / ${formData.spouse?.rw || ''}`}
                                        ocrValue={ocrResults.spouse?.read?.rtRw}
                                        confidence={ocrResults.spouse?.read?.rtRw ? '99%' : undefined}
                                        verifiedValue={verificationResults.spouse?.rt ? `${verificationResults.spouse.rt} / ${verificationResults.spouse.rw}` : undefined}
                                        error={errors.spouse_rt}
                                        onChange={(val) => {
                                            const [rt, rw] = val.split('/').map(s => s.trim());
                                            setFormData(prev => ({
                                            ...prev,
                                            spouse: { ...prev.spouse, rt: rt || '', rw: rw || '' }
                                            }));
                                        }}
                                        required
                                    />
                                    <OCRDataRow
                                        label="Kelurahan/Desa"
                                        field="subdistrict"
                                        value={formData.spouse?.subdistrict || ''}
                                        ocrValue={ocrResults.spouse?.read?.kelurahanDesa}
                                        confidence={ocrResults.spouse?.read?.kelurahanDesa ? '99%' : undefined}
                                        verifiedValue={verificationResults.spouse?.subdistrict}
                                        error={errors.spouse_subdistrict}
                                        onChange={(val) => setFormData(prev => ({
                                            ...prev,
                                            spouse: { ...prev.spouse, subdistrict: val }
                                        }))}
                                        required
                                    />
                                    <OCRDataRow
                                        label="Kecamatan"
                                        field="district"
                                        value={formData.spouse?.district || ''}
                                        ocrValue={ocrResults.spouse?.read?.kecamatan}
                                        confidence={ocrResults.spouse?.read?.kecamatan ? '100%' : undefined}
                                        verifiedValue={verificationResults.spouse?.district}
                                        error={errors.spouse_district}
                                        onChange={(val) => setFormData(prev => ({
                                            ...prev,
                                            spouse: { ...prev.spouse, district: val }
                                        }))}
                                        required
                                    />
                                    <OCRDataRow
                                        label="Kota/Kabupaten"
                                        field="city"
                                        value={formData.spouse?.city || ''}
                                        ocrValue={ocrResults.spouse?.read?.kotaKabupaten}
                                        confidence={ocrResults.spouse?.read?.kotaKabupaten ? '99%' : undefined}
                                        verifiedValue={verificationResults.spouse?.city}
                                        error={errors.spouse_city}
                                        onChange={(val) => setFormData(prev => ({
                                            ...prev,
                                            spouse: { ...prev.spouse, city: val }
                                        }))}
                                        required
                                    />
                                    <OCRDataRow
                                        label="Provinsi"
                                        field="province"
                                        value={formData.spouse?.province || ''}
                                        ocrValue={ocrResults.spouse?.read?.provinsi}
                                        confidence={ocrResults.spouse?.read?.provinsi ? '99%' : undefined}
                                        verifiedValue={verificationResults.spouse?.province}
                                        error={errors.spouse_province}
                                        onChange={(val) => setFormData(prev => ({
                                            ...prev,
                                            spouse: { ...prev.spouse, province: val }
                                        }))}
                                        required
                                    />
                                    <OCRDataRow
                                        label="Agama"
                                        field="religion"
                                        value={formData.spouse?.religion || ''}
                                        ocrValue={ocrResults.spouse?.read?.agama}
                                        confidence={ocrResults.spouse?.read?.agama ? '99%' : undefined}
                                        verifiedValue={verificationResults.spouse?.religion}
                                        error={errors.spouse_religion}
                                        onChange={(val) => setFormData(prev => ({
                                            ...prev,
                                            spouse: { ...prev.spouse, religion: val }
                                        }))}
                                        required
                                    />
                                    <OCRDataRow
                                        label="Pekerjaan"
                                        field="job"
                                        value={formData.spouse?.job || ''}
                                        ocrValue={ocrResults.spouse?.read?.pekerjaan}
                                        confidence={ocrResults.spouse?.read?.pekerjaan ? '99%' : undefined}
                                        verifiedValue={verificationResults.spouse?.job_type}
                                        error={errors.spouse_job}
                                        onChange={(val) => setFormData(prev => ({
                                            ...prev,
                                            spouse: { ...prev.spouse, job: val }
                                        }))}
                                        required
                                    />
                                    {/* Spouse Photo & Signature */}
                                    <tr className="border-b border-gray-100">
                                        <td className="py-3 px-3 font-medium text-gray-700">
                                            Foto <span className="text-red-500">*</span>
                                        </td>
                                        <td colSpan={3}>
                                            {formData.spouse?.photo || ocrResults.spouse?.images?.photo ? (
                                            <img
                                                src={`data:image/jpeg;base64,${formData.spouse?.photo || ocrResults.spouse?.images?.photo}`}
                                                alt="Spouse Photo"
                                                className="h-32 w-24 object-cover border rounded"
                                            />
                                            ) : (
                                            <div className="h-32 w-24 bg-gray-100 border-2 border-dashed border-gray-300 rounded flex items-center justify-center text-gray-400 text-sm">
                                                No Photo
                                            </div>
                                            )}
                                        </td>
                                    </tr>
                                    <tr>
                                        <td className="py-3 px-3 font-medium text-gray-700">
                                            Tanda Tangan <span className="text-red-500">*</span>
                                        </td>
                                        <td colSpan={3}>
                                            {formData.spouse?.signature || ocrResults.spouse?.images?.sign ? (
                                            <img
                                                src={`data:image/jpeg;base64,${formData.spouse?.signature || ocrResults.spouse?.images?.sign}`}
                                                alt="Spouse Signature"
                                                className="h-16 border rounded"
                                            />
                                            ) : (
                                            <div className="h-16 bg-gray-100 border-2 border-dashed border-gray-300 rounded"></div>
                                            )}
                                        </td>
                                    </tr>
                                </tbody>
                                </table>
                            </div>
                            )}
                        </div>
                        )}
                    </div>

                    {/* Additional Documents */}
                    <div className="border-t pt-6 space-y-4">
                        <h3 className="font-semibold text-gray-800">Additional Documents</h3>
                            {[
                            { key: 'kk', label: 'KK (Family Card)', multiple: true },
                            { key: 'npwp', label: 'NPWP', multiple: true },
                            { key: 'marriageStatement', label: 'Divorce/Death Certificate', multiple: true },
                            ].map((doc) => (
                        <div key={doc.key} className="flex items-center gap-4">
                            <label className="w-48 text-sm font-medium text-gray-700">{doc.label}</label>
                            <input
                                type="file"
                                multiple={doc.multiple}
                                accept=".png,.jpg,.jpeg,.pdf,.tiff"
                                onChange={(e) => {
                                    const files = e.target.files;
                                    if (files) {
                                    setFormData(prev => ({
                                        ...prev,
                                        files: {
                                        ...prev.files,
                                        [doc.key]: doc.multiple ? Array.from(files) : files[0],
                                        },
                                    }));
                                    }
                                }}
                                className="flex-1 text-sm"
                            />
                        </div>
                        ))}
                    </div>

                    {/* Reference & Notes */}
                    <div className="border-t pt-6 grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                Reference
                            </label>
                            <select
                                value={formData.isCarro ? '1' : '0'}
                                onChange={(e) => setFormData(prev => ({
                                ...prev,
                                isCarro: e.target.value === '1',
                                }))}
                                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                            >
                                <option value="1">Carro</option>
                                <option value="0">Non Carro</option>
                            </select>
                        </div>
                    </div>

                     <div className="border-t pt-6 grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                Notes for Prechecking
                            </label>
                            <textarea
                                value={formData.notes}
                                onChange={(e) => setFormData(prev => ({ ...prev, notes: e.target.value }))}
                                rows={3}
                                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                            />
                        </div>
                    </div>


                    {/* Action Buttons */}
                    <div className="flex justify-end gap-4 pt-6 border-t">
                        <button
                            type="button"
                            onClick={() => handleSubmit('cancel')}
                            disabled={loading}
                            className="px-6 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                        >
                        Cancel
                        </button>
                        <button
                            type="button"
                            onClick={() => handleSubmit('save')}
                            disabled={loading}
                            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center"
                        >
                        {loading && (
                            <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent mr-2"></div>
                        )}
                        Submit
                        </button>
                    </div>
                </form>
            </div>

            {/* Loading Overlay */}
            {ocrLoading && (
            <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                <div className="bg-white rounded-xl p-6 text-center max-w-sm mx-4">
                    <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-500 border-t-transparent mx-auto mb-4"></div>
                    <p className="text-gray-700 font-medium">Processing OCR, please wait...</p>
                </div>
            </div>
            )}

            {/* Modal Dialog */}
            {modal.show && (
            <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
                <div className="bg-white rounded-xl shadow-xl max-w-md w-full overflow-hidden">
                    <div className="bg-gradient-to-r from-blue-600 to-indigo-600 px-6 py-4">
                        <h3 className="text-white font-bold text-lg">Notification</h3>
                    </div>
                    <div className="p-6">
                        <p className="text-gray-700 mb-6">{modal.message}</p>
                    
                        {modal.type === 'reject' && (
                            <div className="flex justify-end gap-3">
                            <button
                                onClick={() => {
                                setModal({ show: false, type: null, message: '' });
                                // Continue to prechecking
                                }}
                                className="px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                            >
                                YES
                            </button>
                            <button
                                onClick={() => navigate('/')}
                                className="px-3 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
                            >
                                NO
                            </button>
                            </div>
                        )}
                    
                        {modal.type === 'valid' && (
                            <div className="flex justify-end gap-3">
                            <button
                                onClick={() => navigate(`/create-cam?apless=${modal.apless}&prechecking_id=${modal.precheckingId}`)}
                                className="px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                            >
                                Create New CAM
                            </button>
                            <button
                                onClick={() => navigate(`/repeat-order?apless=${modal.apless}&prechecking_id=${modal.precheckingId}`)}
                                className="px-3 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
                            >
                                Prechecking
                            </button>
                            </div>
                        )}
                    
                        {(modal.type === 'inprogress' || modal.type === 'expired') && (
                            <div className="flex justify-end">
                            <button
                                onClick={() => {
                                setModal({ show: false, type: null, message: '' });
                                if (modal.type === 'expired') {
                                    navigate(`/repeat-order?apless=${modal.apless}&prechecking_id=${modal.precheckingId}`);
                                }
                                }}
                                className="px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                            >
                                Close
                            </button>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        )}
        </div>
    );
};

export default PrecheckingIndividuPage;