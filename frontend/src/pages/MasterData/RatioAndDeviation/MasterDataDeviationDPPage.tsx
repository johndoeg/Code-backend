import React, { useState, useRef, useCallback, useEffect } from "react";
import api from "../../../api/axiosInstance";

interface CamRow {
	appl_no: string;
	equipment: string;
	cam_date: string;
	cmo: string;
	id_dev: number | null;
	dp: boolean;
	br: boolean;
	dp_disabled: boolean;
	br_disabled: boolean;
	attachment: string;
	mode: "edit" | "insert" | "";
	editx: "edit_nch" | "";
	file: File | null;
}

interface CustomerOption {
	apless: string;
	lessee_nm: string;
	label: string;
}

const ACCESS_LEVEL = "NCH";

const MasterDataDeviationDPPage: React.FC = () => {
	const [npfLabel, setNpfLabel] = useState("");
	const [npfDate, setNpfDate] = useState("");
	const [npfPercent, setNpfPercent] = useState("");

	const [custName, setCustName] = useState("");
	const [apless, setApless] = useState("");
	const [suggestions, setSuggestions] = useState<CustomerOption[]>([]);
	const [showSuggestions, setShowSuggestions] = useState(false);
	const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

	const [rows, setRows] = useState<CamRow[]>([]);
	const [searched, setSearched] = useState(false);
	const [searching, setSearching] = useState(false);
	const [saving, setSaving] = useState(false);
	const [saveMsg, setSaveMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

	useEffect(() => {
		api.get("/MasterData/api/deviation-dp/npf-info")
			.then(res => {
				setNpfLabel(res.data.as_of_label || "");
				setNpfDate(res.data.as_of_date || "");
				setNpfPercent(res.data.persenya || "");
			})
			.catch(err => console.error("NPF info error:", err));
	}, []);

	const handleCustNameChange = (value: string) => {
		setCustName(value);
		setApless("");

		if (searchTimer.current) clearTimeout(searchTimer.current);
		if (value.trim().length < 3) {
			setSuggestions([]);
			setShowSuggestions(false);
			return;
		}

		searchTimer.current = setTimeout(() => {
			api.get("/MasterData/api/deviation-dp/customer-search", { params: { term: value } })
				.then(res => {
					setSuggestions(res.data || []);
					setShowSuggestions(true);
				})
				.catch(err => console.error("Customer search error:", err));
		}, 300);
	};

	const handleSelectSuggestion = (opt: CustomerOption) => {
		setCustName(opt.label);
		setApless(opt.apless);
		setShowSuggestions(false);
	};

	const handleSearch = useCallback(async () => {
		if (!apless) {
			alert("Pilih customer dari daftar terlebih dahulu");
			return;
		}

		setSearching(true);
		setSaveMsg(null);
		try {
			const res = await api.get("/MasterData/api/deviation-dp/cam-list", { params: { apless } });
			const data = res.data;

			if (!Array.isArray(data) || data.length === 0) {
				alert("Tidak ada CAM Number di onhand CMO untuk customer tersebut");
				setRows([]);
				setSearched(false);
				return;
			}

			const mapped: CamRow[] = data.map((r: any) => {
				const hasRecord = r.id_dev !== null && r.id_dev !== undefined && r.id_dev !== "";
				const dpChecked = r.dp === "1";
				const brChecked = r.br === "1";
				return {
					appl_no: r.appl_no,
					equipment: r.equipment,
					cam_date: r.cam_date,
					cmo: r.cmo,
					id_dev: hasRecord ? r.id_dev : null,
					dp: dpChecked,
					br: brChecked,
					dp_disabled: hasRecord && dpChecked,
					br_disabled: hasRecord && brChecked,
					attachment: r.attachment || "",
					mode: "",
					editx: "",
					file: null,
				};
			});

			setRows(mapped);
			setSearched(true);
		} catch (err) {
			console.error("CAM list error:", err);
			alert("Gagal mengambil data");
		} finally {
			setSearching(false);
		}
	}, [apless]);

	const computeParamx = (row: CamRow, dp: boolean, br: boolean): "edit" | "insert" | "" => {
		const hasRecord = row.id_dev !== null;
		if (dp || br) {
			return hasRecord ? "edit" : "insert";
		}
		return "";
	};

	const handleCheckbox = (index: number, field: "dp" | "br", checked: boolean) => {
		setRows(prev => prev.map((row, i) => {
			if (i !== index) return row;
			const updated = { ...row, [field]: checked };
			updated.mode = computeParamx(updated, updated.dp, updated.br);
			return updated;
		}));
	};

	const handleEditClick = (index: number) => {
		setRows(prev => prev.map((row, i) => {
			if (i !== index) return row;
			return {
				...row,
				mode: "edit",
				editx: "edit_nch",
				dp_disabled: false,
				br_disabled: false,
			};
		}));
	};

	const handleFileChange = (index: number, file: File | null) => {
		setRows(prev => prev.map((row, i) => i === index ? { ...row, file } : row));
	};

	const handleSave = async () => {
		setSaving(true);
		setSaveMsg(null);

		try {
			const formData = new FormData();
			formData.append("as_of", npfDate);

			const payload = rows.map(row => ({
				appl_no: row.appl_no,
				idnya: row.id_dev,
				dp: row.dp ? "1" : "",
				br: row.br ? "1" : "",
				paramx: row.mode,
				editx: row.editx,
			}));
			formData.append("rows", JSON.stringify(payload));

			rows.forEach((row, i) => {
				if (row.file) {
					formData.append(`attach_${i}`, row.file);
				}
			});

			const res = await api.post("/MasterData/api/deviation-dp/save", formData, {
				headers: { "Content-Type": "multipart/form-data" },
			});

			if (res.data.message === "success") {
				if (res.data.errors?.length) {
					setSaveMsg({ type: "error", text: res.data.errors.join(", ") });
				} else {
					setSaveMsg({ type: "success", text: "Data berhasil disimpan" });
				}
				handleSearch();
			} else {
				setSaveMsg({ type: "error", text: (res.data.errors || ["Gagal"]).join(", ") });
			}
		} catch (err: any) {
			console.error("Save error:", err);
			setSaveMsg({ type: "error", text: err.response?.data?.error || "Gagal" });
		} finally {
			setSaving(false);
		}
	};

	const hasUnsavedRows = rows.some(r => r.mode === "edit" || r.mode === "insert");

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-6xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6">

					<h1 className="text-2xl md:text-3xl font-bold text-gray-800 mb-6">
						Deviation for Down Payment and Base Rate Survey Fee 1
					</h1>

					<div className="grid grid-cols-1 md:grid-cols-[260px_1fr] gap-2 items-center mb-4 text-sm">
						<label className="font-medium text-gray-700">NPF as of {npfLabel}</label>
						<div className="text-gray-800">{npfPercent || "-"}</div>
					</div>

					<div className="grid grid-cols-1 md:grid-cols-[260px_1fr] gap-2 items-start mb-4 relative">
						<label className="font-medium text-gray-700 pt-2">Customer Name</label>
						<div className="relative max-w-md">
							<input
								type="text"
								value={custName}
								onChange={e => handleCustNameChange(e.target.value)}
								onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
								onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
								placeholder="Type customer name..."
								className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500"
							/>
							{showSuggestions && suggestions.length > 0 && (
								<ul className="absolute z-10 w-full bg-white border border-gray-200 rounded-lg shadow-lg mt-1 max-h-48 overflow-y-auto">
									{suggestions.map((opt, idx) => (
										<li
											key={idx}
											onMouseDown={() => handleSelectSuggestion(opt)}
											className="px-3 py-2 text-sm hover:bg-blue-50 cursor-pointer"
										>
											{opt.label}
										</li>
									))}
								</ul>
							)}
						</div>
					</div>

					<div className="mb-6">
						<button
							onClick={handleSearch}
							disabled={searching}
							className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium disabled:opacity-50"
						>
							{searching ? "Searching…" : "Search"}
						</button>
					</div>

					<div className="overflow-x-auto border border-gray-200 rounded-lg">
						<table className="w-full text-sm">
							<thead className="bg-blue-900 text-white">
								<tr>
									<th rowSpan={2} className="border border-blue-800 px-3 py-2">No.</th>
									<th rowSpan={2} className="border border-blue-800 px-3 py-2">CAM Date</th>
									<th rowSpan={2} className="border border-blue-800 px-3 py-2">CAM No.</th>
									<th rowSpan={2} className="border border-blue-800 px-3 py-2">Equipment</th>
									<th rowSpan={2} className="border border-blue-800 px-3 py-2">CMO Name</th>
									<th colSpan={2} className="border border-blue-800 px-3 py-2">Permission For</th>
									<th rowSpan={2} className="border border-blue-800 px-3 py-2">Attachment</th>
									{ACCESS_LEVEL === "NCH" && (
										<th rowSpan={2} className="border border-blue-800 px-3 py-2">Edit</th>
									)}
								</tr>
								<tr>
									<th className="border border-blue-800 px-3 py-2">Down Payment</th>
									<th className="border border-blue-800 px-3 py-2">Base Rate Survey Fee 1</th>
								</tr>
							</thead>
							<tbody>
								{!searched ? (
									<tr><td colSpan={9} className="text-center py-6 text-gray-400">Search a customer to view CAM records</td></tr>
								) : rows.length === 0 ? (
									<tr><td colSpan={9} className="text-center py-6 text-gray-400">No data</td></tr>
								) : rows.map((row, i) => {
									const hasRecord = row.id_dev !== null;
									return (
										<tr key={`${row.appl_no}-${i}`} className="text-center hover:bg-gray-50">
											<td className="border border-gray-200 px-3 py-2">{i + 1}</td>
											<td className="border border-gray-200 px-3 py-2">{row.cam_date}</td>
											<td className="border border-gray-200 px-3 py-2">{row.appl_no}</td>
											<td className="border border-gray-200 px-3 py-2">{row.equipment}</td>
											<td className="border border-gray-200 px-3 py-2">{row.cmo}</td>
											<td className="border border-gray-200 px-3 py-2">
												<input
													type="checkbox"
													checked={row.dp}
													disabled={row.dp_disabled}
													onChange={e => handleCheckbox(i, "dp", e.target.checked)}
												/>
											</td>
											<td className="border border-gray-200 px-3 py-2">
												<input
													type="checkbox"
													checked={row.br}
													disabled={row.br_disabled}
													onChange={e => handleCheckbox(i, "br", e.target.checked)}
												/>
											</td>
											<td className="border border-gray-200 px-3 py-2">
												<div className="flex flex-col items-center gap-1">
													<input
														type="file"
														accept=".pdf,.jpg,.jpeg,.png,.bmp"
														onChange={e => handleFileChange(i, e.target.files?.[0] || null)}
														className="text-xs"
													/>
													{row.attachment && (
														<span className="text-xs text-blue-600 break-all">{row.attachment}</span>
													)}
												</div>
											</td>
											{ACCESS_LEVEL === "NCH" && (
												<td className="border border-gray-200 px-3 py-2">
													{hasRecord && (
														<button
															onClick={() => handleEditClick(i)}
															className="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200"
														>
															Edit
														</button>
													)}
												</td>
											)}
										</tr>
									);
								})}
							</tbody>
						</table>
					</div>

					{saveMsg && (
						<div className={`mt-4 p-3 rounded-lg text-sm ${saveMsg.type === "success"
							? "bg-green-50 border border-green-200 text-green-700"
							: "bg-red-50 border border-red-200 text-red-700"}`}>
							{saveMsg.text}
						</div>
					)}

					{searched && rows.length > 0 && (
						<div className="mt-4 flex justify-end">
							<button
								onClick={handleSave}
								disabled={saving || !hasUnsavedRows}
								className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
							>
								{saving ? "Saving…" : "Save"}
							</button>
						</div>
					)}

				</div>
			</div>
		</div>
	);
};

export default MasterDataDeviationDPPage;