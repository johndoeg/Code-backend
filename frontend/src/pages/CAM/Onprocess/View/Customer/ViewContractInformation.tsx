import React, { useEffect, useState } from 'react';
import api from '../../../../../api/axiosInstance';

interface IndividualDetail {
	name_in_id_card: string;
	name_without_title: string;
	gender: string;
	place_of_birth: string;
	date_of_birth: string;
	address: string;
	area: string;
	province: string;
	city: string;
	kecamatan: string;
	kelurahan: string;
	postcode: string;
	mobile_phone: string;
	email: string;
	citizenship: string;
	nationality: string;
	id_type: string;
	id_card_no: string;
	validity_type: string;
	validity_until: string | null;
	passport_no: string;
}

interface EntityDetail {
	name_in_akta: string;
	name_in_npwp: string;
	name_without_title: string;
	establishment_place: string;
	establishment_date: string;
	address: string;
	area: string;
	province: string;
	city: string;
	kecamatan: string;
	kelurahan: string;
	id_type: string;
	npwp_formatted: string;
	validity_type: string;
	validity_until: string | null;
	address_npwp: string;
	area_npwp: string;
	province_npwp: string;
	city_npwp: string;
	kecamatan_npwp: string;
	kelurahan_npwp: string;
	postcode_npwp: string;
	mobile_phone: string;
	email: string;
}

interface ManagementDetailResponse {
	management_nm: string;
	share_status: string;
	individual?: IndividualDetail;
	entity?: EntityDetail;
}

interface ViewContractInformationProps {
	apless: string;
	period: string;
	managementNm: string;
	shareStatus: string;
	onClose: () => void;
}

const controlClass =
	"w-full rounded border border-slate-300 bg-slate-100 px-3 py-2 text-sm text-slate-800 disabled:cursor-not-allowed disabled:opacity-100";

function FormRow({ label, children }: { label: string; children: React.ReactNode }) {
	return (
		<div className="flex flex-col gap-1 py-2 sm:flex-row sm:items-start sm:gap-4">
			<label className="pt-2 text-sm font-bold text-slate-600 sm:w-52 sm:shrink-0">{label}</label>
			<div className="flex flex-1 flex-wrap items-center gap-2">{children}</div>
		</div>
	);
}

function DisabledInput({ value, width }: { value?: string | null; width?: string }) {
	return (
		<input type="text" value={value || ''} disabled readOnly className={controlClass} style={width ? { width } : undefined} />
	);
}

function DisabledSelect({ value, width }: { value?: string | null; width?: string }) {
	return (
		<select disabled className={controlClass} style={width ? { width } : { maxWidth: 320 }} value="0">
			<option value="0">{value || '-'}</option>
		</select>
	);
}

function DisabledTextarea({ value }: { value?: string | null }) {
	return (
		<textarea value={value || ''} disabled readOnly rows={2} className={`${controlClass} resize`} />
	);
}

function DisabledPhone({ value }: { value?: string | null }) {
	return (
		<div className="relative w-full max-w-xs">
			<span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-slate-500">62</span>
			<input type="text" value={value || ''} disabled readOnly className={`${controlClass} pl-8`} />
		</div>
	);
}

export default function ViewContractInformation({ apless, period, managementNm, shareStatus, onClose }: ViewContractInformationProps) {
	const [data, setData] = useState<ManagementDetailResponse | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		let active = true;
		setLoading(true);
		setError(null);
		api
			.get('/CAM/View/api/management-detail', {
				params: { apless, period, management_nm: managementNm, share_status: shareStatus },
			})
			.then((res) => {
				if (active) setData(res.data);
			})
			.catch(() => {
				if (active) setError('Failed to load detail.');
			})
			.finally(() => {
				if (active) setLoading(false);
			});
		return () => {
			active = false;
		};
	}, [apless, period, managementNm, shareStatus]);

	const isEntity = shareStatus === '1';

	return (
		<div
			onClick={onClose}
			style={{
				position: "fixed", inset: 0,
				background: "rgba(0,0,0,.6)",
				zIndex: 9999, display: "flex",
				justifyContent: "center", alignItems: "center",
				padding: 20,
			}}
		>
			<div
				onClick={(e) => e.stopPropagation()}
				className="rounded-lg border border-slate-300 bg-white shadow-xl"
				style={{ width: "100%", maxWidth: 780, maxHeight: "88vh", overflow: "hidden", display: "flex", flexDirection: "column" }}
			>
				<div className="flex items-center justify-between border-b border-slate-300 bg-slate-100 px-6 py-3">
					<h2 className="text-base font-bold text-slate-800">Management Detail Information</h2>
					<button type="button" onClick={onClose} className="text-slate-400 hover:text-slate-600" style={{ cursor: "pointer", background: "none", border: "none", fontSize: "1.2rem" }}>
						✕
					</button>
				</div>

				<div className="overflow-y-auto px-6 py-4">
					{loading && <div className="py-6 text-center text-sm text-slate-500">Loading…</div>}
					{error && <div className="py-6 text-center text-sm text-red-500">{error}</div>}

					{!loading && !error && data && !isEntity && data.individual && (() => {
						const d = data.individual;
						return (
							<div className="divide-y divide-slate-100">
								<FormRow label="BOD / BOC Name in ID Card"><DisabledInput value={d.name_in_id_card} /></FormRow>
								<FormRow label="BOD / BOC Name Without Title"><DisabledInput value={d.name_without_title} /></FormRow>
								<FormRow label="Gender"><DisabledSelect value={d.gender} width="200px" /></FormRow>
								<FormRow label="Place / Date of Birth">
									<DisabledInput value={d.place_of_birth} width="60%" />
									<DisabledInput value={d.date_of_birth} width="35%" />
								</FormRow>
								<FormRow label="ID Address"><DisabledTextarea value={d.address} /></FormRow>
								<FormRow label="Area"><DisabledSelect value={d.area} /></FormRow>
								<FormRow label="Province"><DisabledInput value={d.province} /></FormRow>
								<FormRow label="District / City"><DisabledInput value={d.city} /></FormRow>
								<FormRow label="Kecamatan"><DisabledSelect value={d.kecamatan} /></FormRow>
								<FormRow label="Kelurahan"><DisabledSelect value={d.kelurahan} /></FormRow>
								<FormRow label="Post Code"><DisabledInput value={d.postcode} width="140px" /></FormRow>
								<FormRow label="Mobile Phone No."><DisabledPhone value={d.mobile_phone} /></FormRow>
								<FormRow label="Email"><DisabledInput value={d.email} /></FormRow>
								<FormRow label="Citizenship">
									<DisabledSelect value={d.citizenship} width="110px" />
									<DisabledSelect value={d.nationality} width="220px" />
								</FormRow>
								<FormRow label="ID Type"><DisabledInput value={d.id_type} width="200px" /></FormRow>
								{d.id_type !== 'Paspor' && (
									<FormRow label="ID Card No."><DisabledInput value={d.id_card_no} /></FormRow>
								)}
								<FormRow label="Validity ID Card">
									<DisabledSelect value={d.validity_type} width="200px" />
									{d.validity_type === 'Certain Period' && <DisabledInput value={d.validity_until} width="160px" />}
								</FormRow>
								{d.citizenship === 'WNA' && (
									<FormRow label="Passport No."><DisabledInput value={d.passport_no} /></FormRow>
								)}
							</div>
						);
					})()}

					{!loading && !error && data && isEntity && data.entity && (() => {
						const d = data.entity;
						return (
							<div className="divide-y divide-slate-100">
								<FormRow label="Name in Akta"><DisabledInput value={d.name_in_akta} /></FormRow>
								<FormRow label="Name in NPWP"><DisabledInput value={d.name_in_npwp} /></FormRow>
								<FormRow label="Name in Akta Without Title"><DisabledInput value={d.name_without_title} /></FormRow>
								<FormRow label="Establishment Place / Date">
									<DisabledInput value={d.establishment_place} width="60%" />
									<DisabledInput value={d.establishment_date} width="35%" />
								</FormRow>
								<FormRow label="Address in SK. Domisili"><DisabledTextarea value={d.address} /></FormRow>
								<FormRow label="Area"><DisabledSelect value={d.area} /></FormRow>
								<FormRow label="Province"><DisabledInput value={d.province} /></FormRow>
								<FormRow label="District / City"><DisabledInput value={d.city} /></FormRow>
								<FormRow label="Kecamatan"><DisabledSelect value={d.kecamatan} /></FormRow>
								<FormRow label="Kelurahan"><DisabledSelect value={d.kelurahan} /></FormRow>
								<FormRow label="ID Type"><DisabledInput value={d.id_type} width="200px" /></FormRow>
								<FormRow label="NPWP No."><DisabledInput value={d.npwp_formatted} /></FormRow>
								<FormRow label="Validity ID Card">
									<DisabledSelect value={d.validity_type} width="200px" />
									{d.validity_type === 'Certain Period' && <DisabledInput value={d.validity_until} width="160px" />}
								</FormRow>
								<FormRow label="Address in NPWP"><DisabledTextarea value={d.address_npwp} /></FormRow>
								<FormRow label="Area (NPWP)"><DisabledSelect value={d.area_npwp} /></FormRow>
								<FormRow label="Province (NPWP)"><DisabledInput value={d.province_npwp} /></FormRow>
								<FormRow label="District / City (NPWP)"><DisabledInput value={d.city_npwp} /></FormRow>
								<FormRow label="Kecamatan (NPWP)"><DisabledSelect value={d.kecamatan_npwp} /></FormRow>
								<FormRow label="Kelurahan (NPWP)"><DisabledSelect value={d.kelurahan_npwp} /></FormRow>
								<FormRow label="Post Code (NPWP)"><DisabledInput value={d.postcode_npwp} width="140px" /></FormRow>
								<FormRow label="Mobile Phone No."><DisabledPhone value={d.mobile_phone} /></FormRow>
								<FormRow label="Email"><DisabledInput value={d.email} /></FormRow>
							</div>
						);
					})()}
				</div>

				<div className="border-t border-slate-300 px-6 py-3 text-right">
					<button
						type="button"
						onClick={onClose}
						className="rounded-md bg-slate-600 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
					>
						Close
					</button>
				</div>
			</div>
		</div>
	);
}