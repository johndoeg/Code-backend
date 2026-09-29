import React, { useEffect, useState, useCallback } from "react";
import api from "../../../../../api/axiosInstance";

interface Option {
	value: string;
	label: string;
}

interface CustomerDetailData {
	[key: string]: string;
}

interface Lookups {
	customerProfiles: Option[];
	religions: Option[];
	maritalStatuses: Option[];
	countries: Option[];
	groups: Option[];
	biCustomerTypes: Option[];
	relationshipWithCompany: Option[];
	lastEducation: Option[];
	careerField: Option[];
	dependent: Option[];
	marriageAgreement: Option[];
}

export interface CAMCustomerDetailPageProps {
	apless: string;
	applNo: string;
	finType: string;
	guarantor: string;
	newCar: string;
	purpoffinc: string;
	contType: string;
	restructuringChange: string;
	onSaved: (result: { apless: string; applno: string }) => void;
}

const cellLabel =
	"border-b border-slate-100 bg-slate-50/70 px-4 py-2.5 align-top text-[11px] font-medium uppercase tracking-wide text-slate-400 whitespace-nowrap";
const cellValue = "border-b border-slate-100 px-4 py-2.5 align-top text-sm text-slate-700";
const cellEmpty = "border-b border-slate-100 px-4 py-2.5";
const subheadCell =
	"border-b border-slate-100 bg-indigo-50/70 px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wide text-indigo-600";

function SectionHeader({ children }: { children: React.ReactNode }) {
	return (
		<div className="border-b border-t border-slate-200 bg-slate-50 px-6 py-3 first:border-t-0">
			<h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">{children}</h2>
		</div>
	);
}

function Row({
	left,
	right,
	rightHeader,
}: {
	left?: [string, React.ReactNode];
	right?: [string, React.ReactNode];
	rightHeader?: string;
}) {
	return (
		<tr>
			{left ? (
				<>
					<td className={cellLabel}>{left[0]}</td>
					<td className={cellValue}>{left[1]}</td>
				</>
			) : (
				<>
					<td className={cellEmpty}></td>
					<td className={cellEmpty}></td>
				</>
			)}
			{rightHeader ? (
				<td colSpan={2} className={subheadCell}>{rightHeader}</td>
			) : right ? (
				<>
					<td className={cellLabel}>{right[0]}</td>
					<td className={cellValue}>{right[1]}</td>
				</>
			) : (
				<>
					<td className={cellEmpty}></td>
					<td className={cellEmpty}></td>
				</>
			)}
		</tr>
	);
}

function FullRow({ label, children }: { label: string; children: React.ReactNode }) {
	return (
		<tr>
			<td className={cellLabel}>{label}</td>
			<td colSpan={3} className={cellValue}>{children}</td>
		</tr>
	);
}

const inputCls =
	"border border-slate-300 rounded-lg px-2 py-1.5 text-sm w-full focus:outline-none focus:ring-2 focus:ring-blue-400";
const errCls = "text-red-600 text-xs mt-1";

const CAMCustomerDetailPage: React.FC<CAMCustomerDetailPageProps> = ({
	apless: initialApless, applNo, finType, guarantor, newCar, purpoffinc, contType, restructuringChange, onSaved,
}) => {
	const [loading, setLoading] = useState(true);
	const [saving, setSaving] = useState(false);
	const [errors, setErrors] = useState<Record<string, string>>({});
	const [lookups, setLookups] = useState<Lookups | null>(null);
	const [d, setD] = useState<CustomerDetailData>({});

	const [npwpParts, setNpwpParts] = useState(["", "", "", "", "", ""]);
	const [sameAsCustomerAddress, setSameAsCustomerAddress] = useState(true);

	const [areas, setAreas] = useState<Option[]>([]);
	const [kecamatan1Options, setKecamatan1Options] = useState<Option[]>([]);
	const [kelurahan1Options, setKelurahan1Options] = useState<Option[]>([]);
	const [kecamatanNpwpOptions, setKecamatanNpwpOptions] = useState<Option[]>([]);
	const [kelurahanNpwpOptions, setKelurahanNpwpOptions] = useState<Option[]>([]);
	const [kecamatan1zOptions, setKecamatan1zOptions] = useState<Option[]>([]);
	const [kelurahan1zOptions, setKelurahan1zOptions] = useState<Option[]>([]);
	const [businessTypeOptions, setBusinessTypeOptions] = useState<Option[]>([]);

	const set = (key: string, value: string) => setD(prev => ({ ...prev, [key]: value }));

	const load = useCallback(async () => {
		setLoading(true);
		try {
			const [detailRes, areasRes] = await Promise.all([
				api.get("/CAM/Customer/detail", { params: { apless: initialApless } }),
				api.get("/CAM/Combo/provinces-and-cities"),
			]);
			setD(detailRes.data.data);
			setLookups(detailRes.data.lookups);
			setAreas(areasRes.data);

			const npwp = (detailRes.data.data.npwp || "").padEnd(16, " ");
			setNpwpParts([
				npwp.slice(0, 2).trim(), npwp.slice(2, 5).trim(), npwp.slice(5, 8).trim(),
				npwp.slice(8, 9).trim(), npwp.slice(9, 12).trim(), npwp.slice(12, 16).trim(),
			]);

			if (detailRes.data.data.address1 && detailRes.data.data.grnSpouseAdd) {
				setSameAsCustomerAddress(detailRes.data.data.address1 === detailRes.data.data.grnSpouseAdd);
			}

			if (detailRes.data.data.areaCd) {
				const r = await api.get("/CAM/Combo/kecamatan", { params: { areaCd: detailRes.data.data.areaCd } });
				setKecamatan1Options(r.data);
			}
			if (detailRes.data.data.kecamatan1) {
				const r = await api.get("/CAM/Combo/kelurahan", { params: { kecamatanCd: detailRes.data.data.kecamatan1 } });
				setKelurahan1Options(r.data);
			}
			if (detailRes.data.data.areaCdNpwp) {
				const r = await api.get("/CAM/Combo/kecamatan", { params: { areaCd: detailRes.data.data.areaCdNpwp } });
				setKecamatanNpwpOptions(r.data);
			}
			if (detailRes.data.data.lesseeCat) {
				const r = await api.get("/CAM/Combo/business-type-detail", { params: { custType: detailRes.data.data.lesseeCat } });
				setBusinessTypeOptions(r.data);
			}
		} catch {
		} finally {
			setLoading(false);
		}
	}, [initialApless]);

	useEffect(() => {
		load();
	}, [load]);

	const handleAreaChange = async (value: string) => {
		set("areaCd", value);
		const area = areas.find(a => a.value === value);
		if (area) {
			const [, city] = area.label.split(" - ");
			set("city1", city || "");
		}
		const r = await api.get("/CAM/Combo/kecamatan", { params: { areaCd: value } });
		setKecamatan1Options(r.data);
		setKelurahan1Options([]);
		set("kecamatan1", "");
		set("kelurahan1", "");
	};

	const handleKecamatan1Change = async (value: string) => {
		set("kecamatan1", value);
		const r = await api.get("/CAM/Combo/kelurahan", { params: { kecamatanCd: value } });
		setKelurahan1Options(r.data);
		set("kelurahan1", "");
	};

	const handleAreaNpwpChange = async (value: string) => {
		set("areaCdNpwp", value);
		const area = areas.find(a => a.value === value);
		if (area) {
			const [prov, city] = area.label.split(" - ");
			set("provinceNpwp", prov || "");
			set("cityNpwp", city || "");
		}
		const r = await api.get("/CAM/Combo/kecamatan", { params: { areaCd: value } });
		setKecamatanNpwpOptions(r.data);
		setKelurahanNpwpOptions([]);
	};

	const handleAreazChange = async (value: string) => {
		set("areaCdz", value);
		const area = areas.find(a => a.value === value);
		if (area) {
			const [, city] = area.label.split(" - ");
			set("city1z", city || "");
		}
		const r = await api.get("/CAM/Combo/kecamatan", { params: { areaCd: value } });
		setKecamatan1zOptions(r.data);
		setKelurahan1zOptions([]);
	};

	const handleLesseeCatChange = async (value: string) => {
		set("lesseeCat", value);
		const r = await api.get("/CAM/Combo/business-type-detail", { params: { custType: value } });
		setBusinessTypeOptions(r.data);
		set("ocuType", "");
	};

	const handleSameAddressToggle = (same: boolean) => {
		setSameAsCustomerAddress(same);
		if (same) {
			set("grnSpouseAdd", d.address1 || "");
			set("areaCdz", d.areaCd || "");
			set("kecamatan1z", d.kecamatan1 || "");
			set("kelurahan1z", d.kelurahan1 || "");
			set("rt1z", d.rt1 || "");
			set("rw1z", d.rw1 || "");
			set("zipcode1z", d.zipcode1 || "");
			setKecamatan1zOptions(kecamatan1Options);
			setKelurahan1zOptions(kelurahan1Options);
		} else {
			set("grnSpouseAdd", "");
			set("areaCdz", "");
			set("kecamatan1z", "");
			set("kelurahan1z", "");
			set("rt1z", "");
			set("rw1z", "");
			set("zipcode1z", "");
		}
	};

	const requiresSpouseFields = d.marital === "M" || d.marital === "O";

	const handleSubmit = async () => {
		setSaving(true);
		setErrors({});
		try {
			const npwp = npwpParts.join("");
			const res = await api.post("/CAM/Customer/detail", {
				...d,
				npwp,
				apless: initialApless,
				applno: applNo,
				finType, guarantor, newCar, purpoffinc, contType,
				restructuringChange,
				editable: 1,
			});
			if (res.data.success) {
				if (res.data.watchlistWarning) alert(res.data.watchlistWarning);
				onSaved({ apless: res.data.apless, applno: res.data.applno });
			} else if (res.data.blocked) {
				alert(res.data.message);
			} else if (res.data.errors) {
				setErrors(res.data.errors);
			} else {
				alert(res.data.message || "Failed");
			}
		} catch {
			alert("Save failed. Please try again.");
		} finally {
			setSaving(false);
		}
	};

	const inputCls =
		"border border-slate-300 rounded-lg px-2 py-1.5 text-sm w-full focus:outline-none focus:ring-2 focus:ring-blue-400";
	const selectCls = (editable: boolean) =>
		`border border-slate-300 rounded-lg px-2 py-1.5 text-sm w-full focus:outline-none focus:ring-2 focus:ring-blue-400 ${
			editable ? "bg-white" : "bg-slate-100 text-slate-400 cursor-not-allowed"
		}`;

	if (loading || !lookups) {
		return (
			<div className="flex justify-center py-16">
				<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
			</div>
		);
	}

	return (
		<div>
			<h2 className="text-xl font-bold text-slate-800 mb-1">Detail Information</h2>
			<p className="text-sm text-slate-500 mb-4">Customer No. {initialApless || "(new)"}</p>

			<div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
				<SectionHeader>Customer Detail</SectionHeader>

				<div className="overflow-x-auto">
					<table className="w-full min-w-[820px] border-collapse text-sm">
						<tbody>
							<Row
								left={["Name in ID Card *", (
									<>
										<input className={inputCls} value={d.lesseeNm || ""} readOnly />
										{errors.lesseeNm && <p className={errCls}>{errors.lesseeNm}</p>}
									</>
								)]}
								right={["Alias Name", (
									<input className={inputCls} value={d.aliasName || ""} onChange={e => set("aliasName", e.target.value)} />
								)]}
							/>
							<Row
								left={["Customer Name Without Title *", (
									<>
										<input className={inputCls} value={d.idCardName || ""} onChange={e => set("idCardName", e.target.value)} />
										{errors.idCardName && <p className={errCls}>{errors.idCardName}</p>}
									</>
								)]}
								right={["Customer Profile *", (
									<>
										<select className={selectCls(true)} value={d.lesseeCat || ""} onChange={e => handleLesseeCatChange(e.target.value)}>
											<option value="">Select</option>
											{lookups.customerProfiles.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
										</select>
										{errors.lesseeCat && <p className={errCls}>{errors.lesseeCat}</p>}
									</>
									
								)]}
							/>
							<Row
								left={["Gender *", (
									<>
										<select className={selectCls(true)} value={d.gender || ""} onChange={e => set("gender", e.target.value)}>
											<option value="">Select</option>
											<option value="M">Male</option>
											<option value="F">Female</option>
										</select>
										{errors.gender && <p className={errCls}>{errors.gender}</p>}
									</>
								)]}
								right={["Religion *", (
									<>
										<select className={selectCls(true)} value={d.religion || ""} onChange={e => set("religion", e.target.value)}>
											<option value="">Select</option>
											{lookups.religions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
										</select>
										{errors.religion && <p className={errCls}>{errors.religion}</p>}
									</>
								)]}
							/>
							<Row
								left={["Occupation / Business Type", (
									<select className={selectCls(true)} value={d.ocuType || ""} onChange={e => set("ocuType", e.target.value)}>
										<option value="">Select</option>
										{businessTypeOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
									</select>
								)]}
								right={["Place / Date of Birth *", (
									<>
										<div className="flex gap-2">
											<input className={inputCls} value={d.placebirth || ""} onChange={e => set("placebirth", e.target.value)} placeholder="Place" />
											<input className={inputCls} value={d.tglbirth || ""} onChange={e => set("tglbirth", e.target.value)} placeholder="dd-mm-yyyy" />
										</div>
										{errors.tglbirth && <p className={errCls}>{errors.tglbirth}</p>}
									</>
								)]}
							/>

							<tr>
								<td colSpan={4} className={subheadCell}>Address in ID Card</td>
							</tr>
							<FullRow label="Address in ID Card *">
								<textarea className={inputCls} value={d.address1 || ""} onChange={e => set("address1", e.target.value)} />
								{errors.address1 && <p className={errCls}>{errors.address1}</p>}
							</FullRow>
							<Row
								left={["Area *", (
									<>
										<select className={selectCls(true)} value={d.areaCd || ""} onChange={e => handleAreaChange(e.target.value)}>
											<option value="">Select</option>
											{areas.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
										</select>
										{errors.areaCd && <p className={errCls}>{errors.areaCd}</p>}
									</>
								)]}
								right={["District / City *", (
									<>
										<input className={inputCls} value={d.city1 || ""} readOnly />
										{errors.city1 && <p className={errCls}>{errors.city1}</p>}
									</>
								)]}
							/>
							<Row
								left={["Kecamatan *", (
									<select className={selectCls(true)} value={d.kecamatan1 || ""} onChange={e => handleKecamatan1Change(e.target.value)}>
										<option value="">Select</option>
										{kecamatan1Options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
									</select>
								)]}
								right={["Kelurahan *", (
									<select className={selectCls(true)} value={d.kelurahan1 || ""} onChange={e => set("kelurahan1", e.target.value)}>
										<option value="">Select</option>
										{kelurahan1Options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
									</select>
								)]}
							/>
							<Row
								left={["RT / RW *", (
									<div className="flex gap-2">
										<input className={inputCls} value={d.rt1 || ""} onChange={e => set("rt1", e.target.value)} placeholder="RT" />
										<input className={inputCls} value={d.rw1 || ""} onChange={e => set("rw1", e.target.value)} placeholder="RW" />
									</div>
								)]}
								right={["Post Code *", (
									<>
										<input className={inputCls} value={d.zipcode1 || ""} onChange={e => set("zipcode1", e.target.value)} maxLength={5} />
										{errors.zipcode1 && <p className={errCls}>{errors.zipcode1}</p>}
									</>
								)]}
							/>
							<Row
								left={["Live here since (year) *", (
									<>
										<input className={inputCls} value={d.yearLive || ""} onChange={e => set("yearLive", e.target.value)} maxLength={4} />
										{errors.yearLive && <p className={errCls}>{errors.yearLive}</p>}
									</>
								)]}
							/>

							<tr>
								<td colSpan={4} className={subheadCell}>Identity</td>
							</tr>
							<Row
								left={["ID Card No. *", (
									<>
										<input className={selectCls(true)} value={d.idCard || ""} readOnly />
										{errors.idCard && <p className={errCls}>{errors.idCard}</p>}
									</>
								)]}
								right={["Citizenship *", (
									<>
										<div className="flex gap-2">
											<select className={selectCls(true)} value={d.citizen1 || ""} onChange={e => set("citizen1", e.target.value)}>
												<option value="">Select</option>
												<option value="WNI">WNI</option>
												<option value="WNA">WNA</option>
											</select>
											<select
												className={selectCls(true)}
												value={d.citizen1 === "WNI" ? "ID" : (d.nationality || "")}
												disabled={d.citizen1 !== "WNA"}
												onChange={e => set("nationality", e.target.value)}
											>
												<option value="">Nationality</option>
												{lookups.countries.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
											</select>
										</div>
										{errors.citizen1 && <p className={errCls}>{errors.citizen1}</p>}
										{errors.nationality && <p className={errCls}>{errors.nationality}</p>}
									</>
								)]}
							/>
							<Row
								left={["Validity ID Card *", (
									<div className="flex gap-2">
										<select
											className={selectCls(true)}
											value={d.idCardValid ? "0" : "1"}
											onChange={e => { if (e.target.value === "1") set("idCardValid", ""); else set("idCardValid", d.idCardValid || " "); }}
										>
											<option value="1">No Expire Date</option>
											<option value="0">Certain Period</option>
										</select>
										<input
											className={inputCls}
											placeholder="dd-mm-yyyy"
											value={(d.idCardValid || "").trim()}
											disabled={!d.idCardValid}
											onChange={e => set("idCardValid", e.target.value)}
										/>
									</div>
								)]}
								right={["Family Card No. *", (
									<>
										<input className={inputCls} value={d.famCard || ""} onChange={e => set("famCard", e.target.value)} />
										{errors.famCard && <p className={errCls}>{errors.famCard}</p>}
									</>
								)]}
							/>
							<Row
								right={["BI Customer Type", (
									<select className={selectCls(true)} value={d.custType || ""} onChange={e => set("custType", e.target.value)}>
										<option value="">Select</option>
										{lookups.biCustomerTypes.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
									</select>
								)]}
							/>
							<FullRow label="NPWP *">
								<div className="flex gap-1 items-center">
									{[2, 3, 3, 1, 3, 4].map((len, i) => (
										<input
											key={i}
											className={inputCls}
											style={{ width: `${len * 14 + 16}px` }}
											maxLength={len}
											value={npwpParts[i]}
											onChange={e => {
												const next = [...npwpParts];
												next[i] = e.target.value.replace(/\D/g, "");
												setNpwpParts(next);
											}}
										/>
									))}
								</div>
								{errors.npwp && <p className={errCls}>{errors.npwp}</p>}
							</FullRow>

							<tr>
								<td colSpan={4} className={subheadCell}>NPWP Address</td>
							</tr>
							<FullRow label="Address in NPWP *">
								<textarea className={inputCls} value={d.addrNpwp || ""} onChange={e => set("addrNpwp", e.target.value)} maxLength={250} />
							</FullRow>
							<Row
								left={["Area *", (
									<select className={selectCls(true)} value={d.areaCdNpwp || ""} onChange={e => handleAreaNpwpChange(e.target.value)}>
										<option value="">Select</option>
										{areas.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
									</select>
								)]}
								right={["Kecamatan / Kelurahan *", (
									<div className="flex gap-2">
										<select className={selectCls(true)} value={d.kecamatanNpwp || ""} onChange={async e => {
											set("kecamatanNpwp", e.target.value);
											const r = await api.get("/CAM/Combo/kelurahan", { params: { kecamatanCd: e.target.value } });
											setKelurahanNpwpOptions(r.data);
										}}>
											<option value="">Kecamatan</option>
											{kecamatanNpwpOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
										</select>
										<select className={selectCls(true)} value={d.kelurahanNpwp || ""} onChange={e => set("kelurahanNpwp", e.target.value)}>
											<option value="">Kelurahan</option>
											{kelurahanNpwpOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
										</select>
									</div>
								)]}
							/>
							<Row
								left={["Post Code *", (
									<input className={inputCls} value={d.zipcode2Npwp || ""} onChange={e => set("zipcode2Npwp", e.target.value)} maxLength={5} />
								)]}
							/>

							<tr>
								<td colSpan={4} className={subheadCell}>Contact</td>
							</tr>
							<Row
								left={["Phone *", (
									<>
										<input className={inputCls} value={d.phone2 || ""} onChange={e => set("phone2", e.target.value)} />
										{errors.phone2 && <p className={errCls}>{errors.phone2}</p>}
									</>
								)]}
								right={["Whatsapp No. *", (
									<>
										<input className={inputCls} value={d.mobilePhone1 || ""} onChange={e => set("mobilePhone1", e.target.value)} />
										{errors.mobilePhone1 && <p className={errCls}>{errors.mobilePhone1}</p>}
									</>
								)]}
							/>
							<Row
								left={["Mobile 2", (
									<input className={inputCls} value={d.mobilePhone2 || ""} onChange={e => set("mobilePhone2", e.target.value)} />
								)]}
								right={["Mobile 3", (
									<input className={inputCls} value={d.mobilePhone3 || ""} onChange={e => set("mobilePhone3", e.target.value)} />
								)]}
							/>
							<Row
								left={["Email 1 *", (
									<input type="email" className={inputCls} value={d.email1 || ""} onChange={e => set("email1", e.target.value)} />
								)]}
								right={["Email 2", (
									<input type="email" className={inputCls} value={d.email2 || ""} onChange={e => set("email2", e.target.value)} />
								)]}
							/>
							<Row
								left={["Mother's Maiden Name (Without Title) *", (
									<>
										<input className={inputCls} value={d.mother || ""} onChange={e => set("mother", e.target.value)} />
										{errors.mother && <p className={errCls}>{errors.mother}</p>}
									</>
								)]}
								right={["Marital Status *", (
									<>
										<select className={selectCls(true)} value={d.marital || ""} onChange={e => set("marital", e.target.value)}>
											<option value="">Select</option>
											{lookups.maritalStatuses.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
										</select>
										{errors.marital && <p className={errCls}>{errors.marital}</p>}
									</>
								)]}
							/>
							<Row
								left={["Group *", (
									<select className={selectCls(true)} value={d.grpcode || ""} onChange={e => set("grpcode", e.target.value)}>
										<option value="">Select</option>
										{lookups.groups.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
									</select>
								)]}
								right={["Last Education *", (
									<>
										<select className={selectCls(true)} value={d.lEdu || ""} onChange={e => set("lEdu", e.target.value)}>
											<option value="">Select</option>
											{lookups.lastEducation.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
										</select>
										{errors.lEdu && <p className={errCls}>{errors.lEdu}</p>}
									</>
								)]}
							/>
							<Row
								left={["Career Field *", (
									<>
										<select className={selectCls(true)} value={d.career || ""} onChange={e => set("career", e.target.value)}>
											<option value="">Select</option>
											{lookups.careerField.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
										</select>
										{errors.career && <p className={errCls}>{errors.career}</p>}
									</>
								)]}
								right={["Relationship with Company *", (
									<select className={selectCls(true)} value={d.relMlci || "e3"} onChange={e => set("relMlci", e.target.value)}>
										{lookups.relationshipWithCompany.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
									</select>
								)]}
							/>

							{requiresSpouseFields && (
								<>
									<Row rightHeader="Spouse Information" />
									<Row
										left={["Spouse Name in ID Card *", (
											<input className={inputCls} value={d.spouse || ""} onChange={e => set("spouse", e.target.value)} />
										)]}
										right={["Spouse Name Without Title *", (
											<input className={inputCls} value={d.spouseWt || ""} onChange={e => set("spouseWt", e.target.value)} />
										)]}
									/>
									<Row
										left={["Spouse Place / Date of Birth *", (
											<div className="flex gap-2">
												<input className={inputCls} value={d.placebirth2 || ""} onChange={e => set("placebirth2", e.target.value)} placeholder="Place" />
												<input className={inputCls} value={d.tglbirth2 || ""} onChange={e => set("tglbirth2", e.target.value)} placeholder="dd-mm-yyyy" />
											</div>
										)]}
										right={["Spouse Citizenship *", (
											<div className="flex gap-2">
												<select className={selectCls(true)} value={d.citizen2 || ""} onChange={e => set("citizen2", e.target.value)}>
													<option value="">Select</option>
													<option value="WNI">WNI</option>
													<option value="WNA">WNA</option>
												</select>
												<select
													className={inputCls}
													value={d.citizen2 === "WNI" ? "ID" : (d.nationality2 || "")}
													disabled={d.citizen2 !== "WNA"}
													onChange={e => set("nationality2", e.target.value)}
												>
													<option value="">Nationality</option>
													{lookups.countries.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
												</select>
											</div>
										)]}
									/>
									<Row
										left={["Spouse ID Card No. *", (
											<input className={inputCls} value={d.idCard2 || ""} onChange={e => set("idCard2", e.target.value)} />
										)]}
										right={["Spouse Passport No. *", (
											<input className={inputCls} value={d.sPass || ""} onChange={e => set("sPass", e.target.value)} disabled={d.citizen2 === "WNI"} />
										)]}
									/>
									<Row
										left={["Marriage Agreement *", (
											<select className={selectCls(true)} value={d.mAgree || ""} onChange={e => set("mAgree", e.target.value)}>
												<option value="">Select</option>
												{lookups.marriageAgreement.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
											</select>
										)]}
										right={["Total of Dependent", (
											<select className={selectCls(true)} value={d.dependent || ""} onChange={e => set("dependent", e.target.value)}>
												<option value="">Select</option>
												{lookups.dependent.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
											</select>
										)]}
									/>
									<Row
										left={["Spouse Mobile Phone No. *", (
											<input className={inputCls} value={d.spouseMobilePhone || ""} onChange={e => set("spouseMobilePhone", e.target.value)} />
										)]}
										right={["Spouse Email *", (
											<input type="email" className={inputCls} value={d.spouseEmail || ""} onChange={e => set("spouseEmail", e.target.value)} />
										)]}
									/>
									<FullRow label="Spouse Address in ID Card *">
										<div className="flex gap-6 mb-2">
											<label className="flex items-center gap-2 text-sm">
												<input type="radio" checked={sameAsCustomerAddress} onChange={() => handleSameAddressToggle(true)} />
												Same with Customer's Address in ID Card
											</label>
											<label className="flex items-center gap-2 text-sm">
												<input type="radio" checked={!sameAsCustomerAddress} onChange={() => handleSameAddressToggle(false)} />
												Different
											</label>
										</div>
										<textarea
											className={inputCls}
											value={d.grnSpouseAdd || ""}
											readOnly={sameAsCustomerAddress}
											onChange={e => set("grnSpouseAdd", e.target.value)}
										/>
									</FullRow>
									<Row
										left={["Area *", (
											<select
												className={selectCls(true)}
												value={d.areaCdz || ""}
												disabled={sameAsCustomerAddress}
												onChange={e => handleAreazChange(e.target.value)}
											>
												<option value="">Select</option>
												{areas.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
											</select>
										)]}
										right={["Kecamatan / Kelurahan *", (
											<div className="flex gap-2">
												<select
													className={selectCls(true)}
													value={d.kecamatan1z || ""}
													disabled={sameAsCustomerAddress}
													onChange={async e => {
														set("kecamatan1z", e.target.value);
														const r = await api.get("/CAM/Combo/kelurahan", { params: { kecamatanCd: e.target.value } });
														setKelurahan1zOptions(r.data);
													}}
												>
													<option value="">Kecamatan</option>
													{kecamatan1zOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
												</select>
												<select
													className={selectCls(true)}
													value={d.kelurahan1z || ""}
													disabled={sameAsCustomerAddress}
													onChange={e => set("kelurahan1z", e.target.value)}
												>
													<option value="">Kelurahan</option>
													{kelurahan1zOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
												</select>
											</div>
										)]}
									/>
									<Row
										left={["RT / RW *", (
											<div className="flex gap-2">
												<input className={inputCls} value={d.rt1z || ""} disabled={sameAsCustomerAddress} onChange={e => set("rt1z", e.target.value)} placeholder="RT" />
												<input className={inputCls} value={d.rw1z || ""} disabled={sameAsCustomerAddress} onChange={e => set("rw1z", e.target.value)} placeholder="RW" />
											</div>
										)]}
										right={["Post Code *", (
											<input className={inputCls} value={d.zipcode1z || ""} disabled={sameAsCustomerAddress} onChange={e => set("zipcode1z", e.target.value)} maxLength={5} />
										)]}
									/>
								</>
							)}

							<Row rightHeader="Emergency Contact" />
							<Row
								left={["Emergency Name *", (
									<input className={inputCls} value={d.emergencyName || ""} onChange={e => set("emergencyName", e.target.value)} />
								)]}
								right={["Emergency Phone *", (
									<input className={inputCls} value={d.emergencyPhone || ""} onChange={e => set("emergencyPhone", e.target.value)} />
								)]}
							/>
							<FullRow label="Emergency Address *">
								<textarea className={inputCls} value={d.emergencyAddress || ""} onChange={e => set("emergencyAddress", e.target.value)} />
							</FullRow>
							<Row
								left={["Emergency Relation *", (
									<input className={inputCls} value={d.emergencyRelation || ""} onChange={e => set("emergencyRelation", e.target.value)} />
								)]}
							/>
						</tbody>
					</table>
				</div>
			</div>

			<div className="flex justify-end gap-3 mt-6">
				<button
					onClick={handleSubmit}
					disabled={saving}
					className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white rounded-lg text-sm font-medium"
				>
					{saving ? "Saving…" : "Next"}
				</button>
			</div>
		</div>
	);
};

export default CAMCustomerDetailPage;