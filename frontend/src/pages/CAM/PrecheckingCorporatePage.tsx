import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import Base64Formatter from '../../helpers/Base64Formatter';

// --- Interfaces ---
interface CorporatePIC {
	id?: number;
	nik: string;
	nama: string;
	tempatLahir: string;
	tglLahir: string;
	jenisKelamin: string;
	golonganDarah: string;
	alamat: string;
	rtRw: string;
	kelurahan: string;
	kecamatan: string;
	kota: string;
	provinsi: string;
	agama: string;
	pekerjaan: string;
	status_perkawinan: string;
	kewarnegaraan: string;
	foto: string;
	tandaTangan: string;
}

interface OCRData {
	corporate?: CorporatePIC[];
	customer?: Record<string, string>;
	spouse?: Record<string, string>;
	lastOCROn: string;
	ocrRateData: unknown; // Will be normalized to array
}

interface ConfidenceData {
	confidence: number;
	isVerified: boolean;
}

// --- Main Component ---
const PrecheckingCorporatePage: React.FC = () => {
	const navigate = useNavigate();
	const location = useLocation();
	const { idCard, customerType, customerName } = location.state || {};

	const [precheckData, setPrecheckData] = useState<OCRData | null>(null);
	const [isLoading, setIsLoading] = useState(true);
	const [corporateConfidence, setCorporateConfidence] = useState<Record<number, Record<string, ConfidenceData>>>({});

	// --- Field Mappings ---
	const fieldLabels: Record<string, string> = {
		nik: "NIK",
		nama: "Nama",
		tempatLahir: "Tempat Lahir",
		tglLahir: "Tgl Lahir",
		jenisKelamin: "Jenis Kelamin",
		golonganDarah: "Golongan Darah",
		alamat: "Alamat",
		rtRw: "RT/RW",
		kelurahan: "Kelurahan/Desa",
		kecamatan: "Kecamatan",
		kota: "Kota/Kabupaten",
		provinsi: "Provinsi",
		agama: "Agama",
		pekerjaan: "Pekerjaan",
		status_perkawinan: "Status Perkawinan",
		kewarnegaraan: "Kewarganegaraan",
		foto: "Foto",
		tandaTangan: "Tanda Tangan",
	};

	const dbFieldToJSKey: Record<string, string> = {
		"NIK": "nik",
		"Nama": "nama",
		"Tempat_Lahir": "tempatLahir",
		"Tgl_Lahir": "tglLahir",
		"Jenis_Kelamin": "jenisKelamin",
		"Golongan_Darah": "golonganDarah",
		"Alamat": "alamat",
		"RT": "rt",
		"RW": "rw",
		"Kelurahan": "kelurahan",
		"Kecamatan": "kecamatan",
		"Kota": "kota",
		"Provinsi": "provinsi",
		"Agama": "agama",
		"Pekerjaan": "pekerjaan",
		"Status_Perkawinan": "status_perkawinan",
		"Kewarnegaraan": "kewarnegaraan",
		"Foto": "foto",
		"Tanda_Tangan": "tandaTangan",
	};

	const mapDBFieldNameToJS = (dbField: string): string | undefined => {
		return dbFieldToJSKey[dbField];
	};

	// --- File Upload State ---
	const [uploadedFiles, setUploadedFiles] = useState<Record<string, File | null>>({
		customerKTP: null,
		kk: null,
		npwp: null,
		akta: null,
	});

	// --- File Input Component ---
	const FileInput = ({
		id,
		label,
	}: {
		id: string;
		label: string;
	}) => {
		const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
			const file = e.target.files?.[0] || null;
			setUploadedFiles((prev) => ({ ...prev, [id]: file }));
		};

		return (
			<div className="flex items-center gap-4">
				<label className="w-48 text-sm font-medium">{label}</label>
				<div className="flex items-center gap-3">
					<input
						id={id}
						type="file"
						className="hidden"
						onChange={handleFileChange}
					/>
					<button
						className="px-3 py-1 bg-gray-200 rounded"
						onClick={() => document.getElementById(id)?.click()}
					>
						Choose file
					</button>
					<span className="text-blue-600 text-sm">
						{uploadedFiles[id]?.name || "No file chosen"}
					</span>
				</div>
			</div>
		);
	};

	// --- Render Single Field Row ---
	const renderFieldRow = (
		key: string,
		value: string,
		confidenceMap: Record<string, ConfidenceData>
	) => {
		const label = fieldLabels[key] || key;
		const rate = confidenceMap[key];
		const confidencePercent = rate?.confidence ?? 0;
		const isVerified = rate?.isVerified ?? false;

		const confidence = `${confidencePercent}%`;
		const verified = isVerified ? "True" : "False";

		if (key === 'foto' || key === 'tandaTangan') {
			const src = Base64Formatter.getBase64ImageSrc(value);

			return (
				<div
					key={key}
					className="grid grid-cols-12 items-center border-b border-gray-200 py-2"
				>
					<span className="col-span-2 text-sm text-gray-700">{label}</span>
					<div className="col-span-6 flex items-center">
						{src ? (
							<img
								src={src}
								alt={label}
								className="max-w-[120px] max-h-[120px] object-contain border rounded"
							/>
						) : (
							<span className="text-sm text-gray-500">No image</span>
						)}
					</div>
					<span className="col-span-2 text-center text-xs text-blue-600 font-semibold">
						{confidence}
					</span>
					<span className="col-span-2 text-right text-xs text-blue-600 font-semibold">
						-
					</span>
				</div>
			);
		}

		return (
			<div
				key={key}
				className="grid grid-cols-12 items-center border-b border-gray-200 py-2"
			>
				<span className="col-span-2 text-sm text-gray-700">{label}</span>
				<span className="col-span-6 text-sm font-mono">{value || "-"}</span>
				<span className="col-span-2 text-center text-xs text-blue-600 font-semibold">
					{confidence}
				</span>
				<span className="col-span-2 text-right text-xs text-blue-600 font-semibold">
					{verified}
				</span>
			</div>
		);
	};

	// --- Fetch Data on Mount ---
	useEffect(() => {
		const fetchOCRData = async () => {
			if (!idCard || !customerType) {
				navigate('/add-cam', { replace: true });
				return;
			}

			setIsLoading(true);
			try {
				const response = await fetch(`${import.meta.env.VITE_API_URL}/CAM/get_data_customer`, {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({ idCard, customerType }),
					credentials: "include",
				});

				if (!response.ok) {
					const errorData = await response.json().catch(() => ({}));
					throw new Error(errorData.message || 'Failed to fetch precheck data');
				}

				const data = await response.json();
				const rawPrecheckingData = data.precheckingData;

				// Normalize precheckingData with safe defaults
				const corporateList = Array.isArray(rawPrecheckingData?.corporate)
					? rawPrecheckingData.corporate
					: [];

				const rateDataArray = Array.isArray(rawPrecheckingData?.ocrRateData)
					? rawPrecheckingData.ocrRateData
					: [];

				const lastOCROn = typeof rawPrecheckingData?.lastOCROn === 'string'
					? rawPrecheckingData.lastOCROn
					: 'Unknown';

				// Build rate map: { [Id]: { NIK: 99, ... } }
				const rateMap: Record<number, Record<string, number>> = {};
				rateDataArray.forEach((rate: unknown) => {
					if (rate && typeof rate === 'object') {
						const rateObj = rate as Record<string, any>;
						const id = rateObj.Id;
						if (typeof id === 'number') {
							const { Id, ...fields } = rateObj;
							// Ensure all field values are numbers
							const cleanFields: Record<string, number> = {};
							for (const [key, val] of Object.entries(fields)) {
								if (typeof val === 'number') {
									cleanFields[key] = val;
								}
							}
							rateMap[id] = cleanFields;
						}
					}
				});

				// Build confidence per PIC
				const picConfidences: Record<number, Record<string, ConfidenceData>> = {};
				corporateList.forEach((pic) => {
					if (!pic || typeof pic !== 'object' || pic.id == null) return;
					const rateFields = rateMap[pic.id] || {};
					const confMap: Record<string, ConfidenceData> = {};

					Object.entries(rateFields).forEach(([dbField, conf]) => {
						const jsKey = mapDBFieldNameToJS(dbField);
						if (jsKey && typeof conf === 'number') {
							confMap[jsKey] = {
								confidence: conf,
								isVerified: conf >= 80,
							};
						}
					});

					picConfidences[pic.id] = confMap;
				});

				setPrecheckData({
					corporate: corporateList,
					lastOCROn,
					ocrRateData: rateDataArray,
				});
				setCorporateConfidence(picConfidences);
			} catch (err: any) {
				console.error('Fetch error:', err);
				alert(`Failed to load precheck data: ${err.message}`);
				setPrecheckData({
					corporate: [],
					lastOCROn: 'Error',
					ocrRateData: [],
				});
				setCorporateConfidence({});
			} finally {
				setIsLoading(false);
			}
		};

		fetchOCRData();
	}, [idCard, customerType, navigate]);

	// --- Loading State ---
	if (isLoading) {
		return <div className="p-8 text-center text-lg">Loading precheck data...</div>;
	}

	// --- Submit Handler ---
	const handleSubmit = () => {
		alert('Precheck data submitted!');
		navigate('/add-cam');
	};

	// --- Render ---
	return (
		<div className="max-w-6xl mx-auto p-6 bg-white rounded-lg shadow-md">
			<h1 className="text-2xl font-bold mb-6">ADD PRECHECKING DATA</h1>

			{/* Top Info */}
			<div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6 bg-gray-50 p-4 rounded">
				<div className="flex items-center gap-4 md:col-start-1">
					<label className="w-48 text-sm font-medium">Checking For</label>
					<input
						type="text"
						value="Customer"
						readOnly
						className="flex-1 px-3 py-2 border rounded bg-gray-100"
					/>
				</div>
				<div className="flex items-center gap-4 md:col-start-1">
					<label className="w-48 text-sm font-medium">Customer Type</label>
					<input
						type="text"
						value={customerType === 'PR' ? 'Individu' : 'Corporate'}
						readOnly
						className="flex-1 px-3 py-2 border rounded bg-gray-100"
					/>
				</div>
				<div className="flex items-center gap-4 md:col-start-1">
					<label className="w-48 text-sm font-medium">New / RO</label>
					<input
						type="text"
						value="New"
						readOnly
						className="flex-1 px-3 py-2 border rounded bg-gray-100"
					/>
				</div>
				<div className="flex items-center gap-4 md:col-start-1">
					<label className="w-48 text-sm font-medium">Temporary Customer No.</label>
					<input
						type="text"
						value="P256964"
						readOnly
						className="flex-1 px-3 py-2 border rounded bg-gray-100"
					/>
				</div>
				<div className="flex items-center gap-4 md:col-start-1">
					<label className="w-48 text-sm font-medium">Marital Status</label>
					<input
						type="text"
						value="Married"
						readOnly
						className="flex-1 px-3 py-2 border rounded bg-gray-100"
					/>
				</div>
			</div>

			{/* Render All Corporate PICs */}
			{precheckData?.corporate && precheckData.corporate.length > 0 ? (
				precheckData.corporate.map((pic) => (
					<div key={pic.id || pic.nik} className="border border-gray-300 rounded-lg mb-6">
						<div className="bg-gray-100 px-4 py-2 font-semibold">
							PIC: {pic.nama || 'Unknown'}
						</div>
						<div className="p-4">
							<div className="flex items-center gap-4 mb-4">
								<label className="w-32 text-sm font-medium">Nationality</label>
								<input
									type="text"
									value={pic.kewarnegaraan || 'WNI'}
									readOnly
									className="flex-2 px-3 py-2 border rounded bg-gray-100"
								/>
							</div>
							<div className="flex items-center gap-4 mb-4">
								<label className="w-32 text-sm font-medium">ID Card File</label>
								<div className="flex gap-2">
									<button className="px-3 py-1 bg-gray-200 rounded">Choose file</button>
									<button className="px-3 py-1 bg-gray-200 rounded">Browse</button>
									<span className="text-blue-600">KTP.jpg</span>
								</div>
							</div>
							<p className="text-xs text-gray-500 mb-2">
								Last OCR Data on {precheckData.lastOCROn || '–'}
							</p>
							<div className="space-y-1 mt-2">
								{Object.entries(fieldLabels).map(([jsKey]) => {
									const value = (pic as Record<string, string>)[jsKey] || "";
									const confidenceMap = corporateConfidence[pic.id!] || {};
									return renderFieldRow(jsKey, value, confidenceMap);
								})}
							</div>
						</div>
					</div>
				))
			) : (
				<div className="border border-gray-300 rounded-lg mb-6 p-4 text-gray-500">
					No PIC data available.
				</div>
			)}

			{/* File Uploads & Reference */}
			<div className="space-y-4 mb-6">
				{['KK', 'NPWP', 'Akta Cerai / Akta Kematian'].map((label) => (
					<div key={label} className="flex items-center gap-4">
						<div className="flex gap-2">
							<FileInput id={label} label={label} />
						</div>
					</div>
				))}
				<div className="flex items-center gap-4">
					<label className="w-48 text-sm font-medium">Reference</label>
					<select className="px-3 py-2 border rounded w-64">
						<option>Carro</option>
						<option>Non Carro</option>
					</select>
				</div>
				<div>
					<label className="block mb-1 text-sm font-medium">Note for Prechecking</label>
					<textarea
						className="w-full px-3 py-2 border border-gray-300 rounded-md"
						rows={3}
						placeholder="Enter any notes or observations..."
					></textarea>
				</div>
			</div>

			{/* Buttons */}
			<div className="flex justify-center gap-4">
				<button
					onClick={() => navigate(-1)}
					className="px-6 py-2 bg-gray-500 text-white rounded hover:bg-gray-600 transition"
				>
					Cancel
				</button>
				<button
					onClick={handleSubmit}
					className="px-6 py-2 bg-orange-500 text-white rounded hover:bg-orange-600 transition"
				>
					Submit
				</button>
			</div>
		</div>
	);
};

export default PrecheckingCorporatePage;