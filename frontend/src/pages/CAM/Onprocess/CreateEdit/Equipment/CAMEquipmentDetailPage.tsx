import React, { useCallback, useEffect, useState } from "react";
import api from "../../../../../api/axiosInstance";

export interface CAMEquipmentDetailPageProps {
	apless: string;
	applNo: string;
	finType: string;
	purpoffinc: string;
	newCar: string;
	onSaved: (result: { apless: string; applno: string }) => void;
}

interface Option {
	value: string;
	label: string;
}

interface SupplierResult {
	supp: string;
	name: string;
	nickname: string;
	address: string;
	city: string;
	phone: string;
	contact: string;
	suppType: string;
}

type SupplierCategory = "dealer" | "karoseri" | "accessories" | "other";

const inputCls =
	"border border-slate-300 rounded-lg px-2 py-1.5 text-sm w-full focus:outline-none focus:ring-2 focus:ring-blue-400";
const labelCls = "text-sm text-slate-600 mb-1 block";
const sectionCls = "rounded-2xl border border-slate-200 bg-white p-5 shadow-sm space-y-3";
const selectCls = (editable: boolean) =>
		`border border-slate-300 rounded-lg px-2 py-1.5 text-sm w-full focus:outline-none focus:ring-2 focus:ring-blue-400 ${
			editable ? "bg-white" : "bg-slate-100 text-slate-400 cursor-not-allowed"
		}`;

const EMPTY_FORM = {
	supp: "", suppName: "", suppAddress: "",
	brand: "", type: "", model: "", tahun: "",
	chasis: "", engine: "", colour: "", policeno: "",
	userusage: "", purpose: "",
	karoseri: "", karoseriSupp: "", karoseriName: "", karoseriAddress: "",
	accessoriesSupp: "", accessoriesName: "", accessoriesAddress: "",
	otherSupp: "", otherName: "", otherAddress: "",
	parkLoc: "", parkZipcode: "", cityPark: "",
	wheels: "", stnkValidDt: "", fundPurpose: "", finPurpose: "",
	ojkFinGoods: "", ojkFinGoodsDetail: "", ojkCollGoods: "", ojkCollGoodsDetail: "",
	redCode: false, gpsVendor: "",
};

function SupplierPicker({
	category, newCar, label, code, name, onSelect, onClear, disabled,
}: {
	category: SupplierCategory;
	newCar: string;
	label: string;
	code: string;
	name: string;
	onSelect: (r: SupplierResult) => void;
	onClear?: () => void;
	disabled?: boolean;
}) {
	const [open, setOpen] = useState(false);
	const [query, setQuery] = useState("");
	const [results, setResults] = useState<SupplierResult[]>([]);
	const [searching, setSearching] = useState(false);

	useEffect(() => {
		if (!open) return;
		const timer = setTimeout(async () => {
			setSearching(true);
			try {
				const res = await api.get("/CAM/EditIndex/suppliers", {
					params: { category, name: query, newCar },
				});
				setResults(res.data || []);
			} catch {
				setResults([]);
			} finally {
				setSearching(false);
			}
		}, 300);
		return () => clearTimeout(timer);
	}, [open, query, category, newCar]);

	return (
		<div className="relative">
			<label className={labelCls}>{label}</label>
			<div className="flex gap-2">
				<input className={inputCls} value={name} readOnly placeholder="None selected" />
				{!disabled && (
					<button
						type="button"
						onClick={() => { setOpen(o => !o); setQuery(""); }}
						className="whitespace-nowrap rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
					>
						Search
					</button>
				)}
				{!disabled && onClear && code && (
					<button
						type="button"
						onClick={onClear}
						className="whitespace-nowrap rounded-lg bg-slate-200 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-300"
					>
						Clear
					</button>
				)}
			</div>
			{open && (
				<div className="absolute z-10 mt-1 w-full rounded-lg border border-slate-200 bg-white p-2 shadow-lg">
					<input
						autoFocus
						className={inputCls}
						placeholder="Type a name to search…"
						value={query}
						onChange={e => setQuery(e.target.value)}
					/>
					<div className="mt-2 max-h-48 overflow-y-auto">
						{searching ? (
							<p className="p-2 text-sm text-slate-400">Searching…</p>
						) : results.length === 0 ? (
							<p className="p-2 text-sm text-slate-400">No results.</p>
						) : (
							results.map(r => (
								<button
									key={r.supp}
									type="button"
									onClick={() => { onSelect(r); setOpen(false); }}
									className="block w-full rounded-lg px-2 py-1.5 text-left text-sm hover:bg-slate-100"
								>
									<span className="font-medium">{r.name}</span>
									<span className="ml-2 text-slate-400">{r.address}</span>
								</button>
							))
						)}
					</div>
					<button
						type="button"
						onClick={() => setOpen(false)}
						className="mt-1 text-xs text-slate-400 hover:underline"
					>
						Close
					</button>
				</div>
			)}
		</div>
	);
}

export default function CAMEquipmentDetailPage({ apless, applNo, finType, purpoffinc, newCar, onSaved }: CAMEquipmentDetailPageProps) {
	const condition = newCar === "2" ? "NEW" : newCar === "1" ? "USED" : "";

	const [loading, setLoading] = useState(true);
	const [saving, setSaving] = useState(false);
	const [error, setError] = useState("");
	const [d, setD] = useState(EMPTY_FORM);

	const [brands, setBrands] = useState<Option[]>([]);
	const [models, setModels] = useState<Option[]>([]);
	const [types, setTypes] = useState<Option[]>([]);
	const [karoseriOptions, setKaroseriOptions] = useState<Option[]>([]);
	const [purposes, setPurposes] = useState<Option[]>([]);
	const [areas, setAreas] = useState<Option[]>([]);
	const [gpsVendors, setGpsVendors] = useState<Option[]>([]);
	const [financingPurposes, setFinancingPurposes] = useState<Option[]>([]);
	const [ojkFinGoods, setOjkFinGoods] = useState<Option[]>([]);
	const [ojkFinGoodsDetailOpts, setOjkFinGoodsDetailOpts] = useState<Option[]>([]);
	const [ojkCollGood, setOjkCollGood] = useState<Option | null>(null);
	const [ojkCollGoodDetail, setOjkCollGoodDetail] = useState<Option[]>([]);
	const [wheelsRequired, setWheelsRequired] = useState(false);
	const [showFinancingPurpose, setShowFinancingPurpose] = useState(false);
	const [showOjkFinGoods, setShowOjkFinGoods] = useState(false);

	const set = (key: keyof typeof EMPTY_FORM, value: string | boolean) => setD(prev => ({ ...prev, [key]: value }));

	const load = useCallback(async () => {
		setLoading(true);
		setError("");
		try {
			const res = await api.get("/CAM/EditIndex/equipment", {
				params: { apless, applno: applNo, finType, purpoffinc, newCar },
			});
			const eq = res.data.equipment;
			if (eq) {
				setD({
					...EMPTY_FORM,
					...eq,
					wheels: eq.wheels != null ? String(eq.wheels) : "",
				});
			}
			const lk = res.data.lookups;
			setBrands(lk.brands || []);
			setModels(lk.models || []);
			setTypes(lk.types || []);
			setKaroseriOptions(lk.karoseri || []);
			setPurposes(lk.purposes || []);
			setAreas(lk.areas || []);
			setGpsVendors(lk.gpsVendors || []);
			setFinancingPurposes(lk.financingPurposes || []);
			setOjkFinGoods(lk.ojkFinGoods || []);
			setOjkCollGood(lk.ojkCollGood || null);
			setOjkCollGoodDetail(lk.ojkCollGoodDetail || []);
			setWheelsRequired(!!lk.wheelsRequired);
			setShowFinancingPurpose(!!res.data.showFinancingPurpose);
			setShowOjkFinGoods(!!res.data.showOjkFinGoods);
			if (eq?.ojkFinGoods) {
				const detailRes = await api.get("/CAM/EditIndex/equipment/ojk-fin-goods-detail", {
					params: {
						finGood: eq.ojkFinGoods, finType, purpoffinc, brand: eq.brand,
						type: eq.type, model: eq.model, condition,
					},
				});
				setOjkFinGoodsDetailOpts(detailRes.data || []);
			}
		} catch {
			setError("Failed to load equipment data.");
		} finally {
			setLoading(false);
		}
	}, [apless, applNo, finType, purpoffinc, newCar, condition]);

	useEffect(() => {
		load();
	}, [load]);

	const refreshModelOptions = useCallback(async (brand: string, model: string) => {
		try {
			const res = await api.get("/CAM/EditIndex/equipment/model-options", {
				params: { brand, model, newCar, purpoffinc, finType },
			});
			setTypes(res.data.types || []);
			setKaroseriOptions(res.data.karoseri || []);
			setOjkCollGood(res.data.ojkCollGood || null);
			setOjkCollGoodDetail(res.data.ojkCollGoodDetail || []);
			setWheelsRequired(!!res.data.wheelsRequired);
		} catch {}
	}, [newCar, purpoffinc, finType]);

	const handleBrandChange = (value: string) => {
		set("brand", value);
		set("type", "");
		refreshModelOptions(value, d.model);
	};

	const handleModelChange = (value: string) => {
		set("model", value);
		set("type", "");
		set("karoseri", "");
		refreshModelOptions(d.brand, value);
	};

	const handleFinGoodChange = async (value: string) => {
		set("ojkFinGoods", value);
		set("ojkFinGoodsDetail", "");
		if (!value) {
			setOjkFinGoodsDetailOpts([]);
			return;
		}
		try {
			const res = await api.get("/CAM/EditIndex/equipment/ojk-fin-goods-detail", {
				params: { finGood: value, finType, purpoffinc, brand: d.brand, type: d.type, model: d.model, condition },
			});
			setOjkFinGoodsDetailOpts(res.data || []);
		} catch {
			setOjkFinGoodsDetailOpts([]);
		}
	};

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		setSaving(true);
		setError("");
		try {
			const res = await api.post("/CAM/EditIndex/equipment", {
				apless, applno: applNo, finType, condition,
				...d,
				ojkCollGoods: ojkCollGood?.value || "",
				ojkCollGoodsDetail: ojkCollGoodDetail[0]?.value || "",
			});
			if (!res.data.success) {
				setError(res.data.message || "Save failed.");
				return;
			}
			onSaved({ apless, applno: applNo });
		} catch {
			setError("Save failed. Please try again.");
		} finally {
			setSaving(false);
		}
	};

	if (loading) {
		return (
			<div className="flex justify-center py-16">
				<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
			</div>
		);
	}

	const showKaroseri = karoseriOptions.length > 0 || d.karoseri;

	return (
		<form onSubmit={handleSubmit} className="space-y-4">
			<h2 className="text-xl font-bold text-slate-800">{finType === "S" ? "Financing Object" : "Equipment"}</h2>

			<div className={sectionCls}>
				<SupplierPicker
					category="dealer"
					newCar={newCar}
					label={finType === "S" || finType === "D" || finType === "M" || finType === "W" ? "Dealer Name" : "Dealer Name *"}
					code={d.supp}
					name={d.suppName}
					onSelect={r => setD(prev => ({ ...prev, supp: r.supp, suppName: r.name, suppAddress: `${r.address}\n${r.city}` }))}
				/>
				<div>
					<label className={labelCls}>Dealer Address</label>
					<textarea className={inputCls} value={d.suppAddress} readOnly rows={2} />
				</div>

				<div className="grid grid-cols-2 gap-3">
					<div>
						<label className={labelCls}>Brand *</label>
						<select className={selectCls(true)} value={d.brand} onChange={e => handleBrandChange(e.target.value)} required>
							<option value="">Select</option>
							{brands.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
						</select>
					</div>
					<div>
						<label className={labelCls}>Model *</label>
						<select className={selectCls(true)} value={d.model} onChange={e => handleModelChange(e.target.value)} required>
							<option value="">Select</option>
							{models.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
						</select>
					</div>
				</div>
				<div>
					<label className={labelCls}>Type *</label>
					<select className={selectCls(true)} value={d.type} onChange={e => set("type", e.target.value)} required>
						<option value="">Select</option>
						{types.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
					</select>
				</div>
			</div>

			{showOjkFinGoods && (
				<div className={sectionCls}>
					<div>
						<label className={labelCls}>OJK Financing Goods *</label>
						<select className={selectCls(true)} value={d.ojkFinGoods} onChange={e => handleFinGoodChange(e.target.value)} required>
							<option value="">Select</option>
							{ojkFinGoods.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
						</select>
					</div>
					<div>
						<label className={labelCls}>OJK Financing Goods Detail *</label>
						<select className={selectCls(true)} value={d.ojkFinGoodsDetail} onChange={e => set("ojkFinGoodsDetail", e.target.value)} required>
							<option value="">Select</option>
							{ojkFinGoodsDetailOpts.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
						</select>
					</div>
				</div>
			)}

			{ojkCollGood && (
				<div className={sectionCls}>
					<p className="text-xs uppercase tracking-wide text-slate-400">OJK Collateral Goods (auto-determined by model)</p>
					<p className="text-sm text-slate-700">{ojkCollGood.label}{ojkCollGoodDetail[0] ? ` — ${ojkCollGoodDetail[0].label}` : ""}</p>
				</div>
			)}

			<div className={`${sectionCls} grid grid-cols-2 gap-3`}>
				<div>
					<label className={labelCls}>Year *</label>
					<input className={inputCls} value={d.tahun} maxLength={4} onChange={e => set("tahun", e.target.value.replace(/\D/g, ""))} required />
				</div>
				<div>
					<label className={labelCls}>Condition</label>
					<input className={inputCls} value={condition} readOnly />
				</div>
				<div>
					<label className={labelCls}>Chasis No</label>
					<input className={inputCls} value={d.chasis} maxLength={20} onChange={e => set("chasis", e.target.value)} />
				</div>
				<div>
					<label className={labelCls}>Engine No</label>
					<input className={inputCls} value={d.engine} maxLength={24} onChange={e => set("engine", e.target.value)} />
				</div>
				<div>
					<label className={labelCls}>Color</label>
					<input className={inputCls} value={d.colour} maxLength={20} onChange={e => set("colour", e.target.value)} />
				</div>
				<div>
					<label className={labelCls}>Police No</label>
					<input className={inputCls} value={d.policeno} maxLength={100} onChange={e => set("policeno", e.target.value)} />
				</div>
				{condition === "USED" && (
					<div>
						<label className={labelCls}>STNK Valid Date</label>
						<input type="date" className={inputCls} value={d.stnkValidDt} onChange={e => set("stnkValidDt", e.target.value)} />
					</div>
				)}
				{wheelsRequired && (
					<div>
						<label className={labelCls}>Wheels *</label>
						<input className={inputCls} value={d.wheels} onChange={e => set("wheels", e.target.value.replace(/\D/g, ""))} required />
					</div>
				)}
			</div>

			<div className={sectionCls}>
				<div>
					<label className={labelCls}>User Usage *</label>
					<input className={inputCls} value={d.userusage} maxLength={100} onChange={e => set("userusage", e.target.value)} required />
				</div>
				<div>
					<label className={labelCls}>Vehicle Purpose *</label>
					<select className={selectCls(true)} value={d.purpose} onChange={e => set("purpose", e.target.value)} required>
						<option value="">Select</option>
						{purposes.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
					</select>
				</div>
			</div>

			{showKaroseri && (
				<div className={sectionCls}>
					<div>
						<label className={labelCls}>Karoseri</label>
						<select className={selectCls(true)} value={d.karoseri} onChange={e => set("karoseri", e.target.value)}>
							<option value="">Select</option>
							{karoseriOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
						</select>
					</div>
					<SupplierPicker
						category="karoseri"
						newCar={newCar}
						label="Karoseri Name"
						code={d.karoseriSupp}
						name={d.karoseriName}
						onSelect={r => setD(prev => ({ ...prev, karoseriSupp: r.supp, karoseriName: r.name, karoseriAddress: `${r.address}\n${r.city}` }))}
						onClear={() => setD(prev => ({ ...prev, karoseriSupp: "", karoseriName: "", karoseriAddress: "" }))}
					/>
					<textarea className={inputCls} value={d.karoseriAddress} readOnly rows={2} />
				</div>
			)}

			<div className={sectionCls}>
				<SupplierPicker
					category="accessories"
					newCar={newCar}
					label="Accessories Name"
					code={d.accessoriesSupp}
					name={d.accessoriesName}
					onSelect={r => setD(prev => ({ ...prev, accessoriesSupp: r.supp, accessoriesName: r.name, accessoriesAddress: `${r.address}\n${r.city}` }))}
					onClear={() => setD(prev => ({ ...prev, accessoriesSupp: "", accessoriesName: "", accessoriesAddress: "" }))}
				/>
				<textarea className={inputCls} value={d.accessoriesAddress} readOnly rows={2} />
			</div>

			<div className={sectionCls}>
				<SupplierPicker
					category="other"
					newCar={newCar}
					label="Others Name"
					code={d.otherSupp}
					name={d.otherName}
					onSelect={r => setD(prev => ({ ...prev, otherSupp: r.supp, otherName: r.name, otherAddress: `${r.address}\n${r.city}` }))}
					onClear={() => setD(prev => ({ ...prev, otherSupp: "", otherName: "", otherAddress: "" }))}
				/>
				<textarea className={inputCls} value={d.otherAddress} readOnly rows={2} />
			</div>

			<div className={sectionCls}>
				<div>
					<label className={labelCls}>Parking Address *</label>
					<textarea className={inputCls} value={d.parkLoc} onChange={e => set("parkLoc", e.target.value)} required rows={2} />
				</div>
				<div className="grid grid-cols-2 gap-3">
					<div>
						<label className={labelCls}>Zip Code *</label>
						<input
							className={inputCls}
							value={d.parkZipcode}
							maxLength={5}
							onChange={e => set("parkZipcode", e.target.value.replace(/\D/g, ""))}
							required
						/>
					</div>
					<div>
						<label className={labelCls}>City *</label>
						<select className={selectCls(true)} value={d.cityPark} onChange={e => set("cityPark", e.target.value)} required>
							<option value="">Select</option>
							{areas.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
						</select>
					</div>
				</div>
			</div>

			{showFinancingPurpose && (
				<div className={sectionCls}>
					<div>
						<label className={labelCls}>Financing Purpose *</label>
						<select className={selectCls(true)} value={d.finPurpose} onChange={e => set("finPurpose", e.target.value)} required>
							<option value="">Select</option>
							{financingPurposes.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
						</select>
					</div>
					{(finType === "D" || finType === "M" || finType === "W") && (
						<div>
							<label className={labelCls}>Description for Customer Purpose *</label>
							<textarea className={inputCls} value={d.fundPurpose} onChange={e => set("fundPurpose", e.target.value)} required rows={3} />
							<p className="mt-1 text-xs text-red-600">
								Note: please describe the purpose fully and clearly, in formal Indonesian.
							</p>
						</div>
					)}
				</div>
			)}

			<div className={sectionCls}>
				<label className="flex items-center gap-2 text-sm text-slate-600">
					<input type="checkbox" checked={d.redCode} onChange={e => set("redCode", e.target.checked)} />
					Red Code
				</label>
				{d.redCode && (
					<select className={inputCls} value={d.gpsVendor} onChange={e => set("gpsVendor", e.target.value)} required>
						<option value="">Select GPS Vendor</option>
						{gpsVendors.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
					</select>
				)}
			</div>

			{error && <p className="text-sm text-red-600">{error}</p>}

			<div className="flex justify-end gap-3">
				<button
					type="submit"
					disabled={saving}
					className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white rounded-lg text-sm font-medium"
				>
					{saving ? "Saving…" : "Next"}
				</button>
			</div>
		</form>
	);
}