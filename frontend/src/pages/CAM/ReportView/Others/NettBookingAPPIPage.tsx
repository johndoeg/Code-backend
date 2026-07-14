import { useState } from "react";
import * as XLSX from "xlsx";
import api from "../../../../api/axiosInstance";
import DatePicker, { registerLocale } from "react-datepicker";
import { id } from "date-fns/locale";
import "react-datepicker/dist/react-datepicker.css";

registerLocale("id", id);

interface NettBookingData {
	tot_fin1a: number | null;
	tot_fin1b: number | null;
	tot_fin1c: number | null;
	tot_fin1d: number | null;
	tot_fin3a: number | null;
	tot_fin3b: number | null;
	tot_fin3c: number | null;
	tot_cust: number | null;
	tot_unit_listrik_period: number | null;
	tot_fin_listrik_period: number | null;
	tot_unit_hybrid_period: number | null;
	tot_fin_hybrid_period: number | null;
	tot_unit_listrik_out: number | null;
	tot_fin_listrik_out: number | null;
	tot_unit_hybrid_out: number | null;
	tot_fin_hybrid_out: number | null;
}

const F1_LABELS: Record<string, string> = {
	"1A": "Total Nett Booking Bulanan MOBIL BENSIN BARU KONVENSIONAL (tanpa bunga)",
	"1B": "Total Nett Booking Bulanan MOBIL BENSIN BEKAS KONVENSIONAL (tanpa bunga)",
	"1C": "Total Nett Booking Bulanan MOBIL LISTRIK KONVENSIONAL (tanpa bunga)",
	"1D": "Total Nett Booking Bulanan MOBIL HYBRID KONVENSIONAL (tanpa bunga)",
};

const F3_LABELS: Record<string, string> = {
	"3A": "Total Nett Booking Bulanan berdasarkan PEMBIAYAAN INVESTASI",
	"3B": "Total Nett Booking Bulanan berdasarkan PEMBIAYAAN MODAL KERJA",
	"3C": "Total Nett Booking Bulanan berdasarkan PEMBIAYAAN MULTIGUNA",
};

function fmtMonth(d: Date | null): string {
	if (!d) return "";
	return d.toLocaleString("id-ID", { month: "long", year: "numeric" });
}

function dateToParam(d: Date): string {
	const y = d.getFullYear();
	const m = String(d.getMonth() + 1).padStart(2, "0");
	return `${y}-${m}-01`;
}

function exportExcel(data: NettBookingData, selectedDate: Date): void {
	const month = fmtMonth(selectedDate);
	const wb = XLSX.utils.book_new();
	const ws: XLSX.WorkSheet = {};

	const s = (ref: string, v: string | number | null) => {
		ws[ref] = { v: v ?? "", t: typeof v === "number" ? "n" : "s" };
	};

	s("A1", "NETT BOOKING APPI");
	s("A2", " FORMULIR1 "); s("B2", " NETT BOOKING KONVENSIONAL "); s("C2", month);
	s("A3", "1A"); s("B3", F1_LABELS["1A"]); s("C3", data.tot_fin1a);
	s("A4", "1B"); s("B4", F1_LABELS["1B"]); s("C4", data.tot_fin1b);
	s("A5", "1C"); s("B5", F1_LABELS["1C"]); s("C5", data.tot_fin1c);
	s("A6", "1D"); s("B6", F1_LABELS["1D"]); s("C6", data.tot_fin1d);
	s("A7", " FORMULIR3 "); s("B7", " NETT BOOKING BERDASARKAN KEGIATAN USAHA "); s("C7", " JAWABAN DALAM JUTAAN RP ");
	s("A8", "3A"); s("B8", F3_LABELS["3A"]); s("C8", data.tot_fin3a);
	s("A9", "3B"); s("B9", F3_LABELS["3B"]); s("C9", data.tot_fin3b);
	s("A10", "3C"); s("B10", F3_LABELS["3C"]); s("C10", data.tot_fin3c);
	s("A11", " FORMULIR9 "); s("B11", " FORMULIR EXISTING CUSTOMER "); s("C11", " JAWABAN ");
	s("A12", "9A"); s("B12", "Existing Customer"); s("C12", data.tot_cust);
	s("A13", " KBLBB sesuai Periode Laporan Bulanan "); s("B13", " UNIT "); s("C13", " NOMINAL "); s("D13", " KONTRAK ");
	s("A14", "Murni Listrik"); s("B14", data.tot_unit_listrik_period); s("C14", data.tot_fin_listrik_period); s("D14", data.tot_unit_listrik_period);
	s("A15", "Hybrid"); s("B15", data.tot_unit_hybrid_period); s("C15", data.tot_fin_hybrid_period); s("D15", data.tot_unit_hybrid_period);
	s("A16", " KBLBB sesuai Outstanding "); s("B16", " UNIT "); s("C16", " NOMINAL "); s("D16", " KONTRAK ");
	s("A17", "Murni Listrik"); s("B17", data.tot_unit_listrik_out); s("C17", data.tot_fin_listrik_out); s("D17", data.tot_unit_listrik_out);
	s("A18", "Hybrid"); s("B18", data.tot_unit_hybrid_out); s("C18", data.tot_fin_hybrid_out); s("D18", data.tot_unit_hybrid_out);

	ws["!ref"] = "A1:D18";
	ws["!cols"] = [{ wch: 6 }, { wch: 58 }, { wch: 22 }, { wch: 14 }];
	ws["!merges"] = [{ s: { r: 0, c: 0 }, e: { r: 0, c: 2 } }];

	XLSX.utils.book_append_sheet(wb, ws, "NettBookingAPPI");
	XLSX.writeFile(wb, "NettBookingAPPI.xlsx");
}

interface MonthYearPickerProps {
	value: Date | null;
	onChange: (d: Date | null) => void;
	label?: string;
	required?: boolean;
	disabled?: boolean;
}

function MonthYearPicker({
	value,
	onChange,
	label = "Periode (Bulan)",
	required = false,
	disabled = false,
}: MonthYearPickerProps) {
	return (
		<div className="flex-1 min-w-[180px] max-w-xs">
			{label && (
				<label className="block text-xs font-medium text-gray-500 mb-1">
					{label}
					{required && <span className="text-red-500 ml-1" aria-hidden="true">*</span>}
				</label>
			)}
			<DatePicker
				selected={value}
				onChange={onChange}
				locale="id"
				dateFormat="MMMM yyyy"
				showMonthYearPicker
				showFourColumnMonthYearPicker
				disabled={disabled}
				placeholderText="Pilih bulan…"
				className={[
					"w-full px-3 py-2 border border-gray-300 rounded-lg text-sm",
					"focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500",
					"bg-white text-gray-800",
					disabled ? "opacity-60 cursor-not-allowed" : "cursor-pointer",
				].join(" ")}
				wrapperClassName="w-full"
				calendarClassName="shadow-xl border border-gray-200 rounded-xl overflow-hidden"
				renderCustomHeader={({ date, increaseYear, decreaseYear }) => (
					<div className="flex items-center justify-between px-3 py-2 bg-gradient-to-r from-blue-600 to-indigo-700">
						<button type="button" onClick={decreaseYear}
							className="text-white hover:text-blue-200 font-bold text-lg px-1 leading-none">
							‹
						</button>
						<span className="text-white text-sm font-semibold">{date.getFullYear()}</span>
						<button type="button" onClick={increaseYear}
							className="text-white hover:text-blue-200 font-bold text-lg px-1 leading-none">
							›
						</button>
					</div>
				)}
			/>
			<style>{`
				.react-datepicker { font-family: inherit; border: none; border-radius: 0.75rem; }
				.react-datepicker__month-container { float: none; }
				.react-datepicker__header { background: transparent; border-bottom: 1px solid #e5e7eb; padding: 0; }
				.react-datepicker__month .react-datepicker__month-text,
				.react-datepicker__month .react-datepicker__quarter-text {
					display: inline-flex; align-items: center; justify-content: center;
					width: 5rem; padding: 0.4rem 0; margin: 2px;
					font-size: 0.8rem; color: #374151; border-radius: 0.375rem;
				}
				.react-datepicker__month-text--keyboard-selected,
				.react-datepicker__month--selected,
				.react-datepicker__month-text:hover {
					background: linear-gradient(to right, #2563eb, #4338ca) !important;
					color: white !important; border-radius: 0.375rem;
				}
				.react-datepicker-popper { z-index: 50; }
			`}</style>
		</div>
	);
}

const NettBookingAPPIPage: React.FC = () => {
	const [selectedDate, setSelectedDate] = useState<Date | null>(null);
	const [loading, setLoading] = useState<boolean>(false);
	const [error, setError] = useState<string | null>(null);

	const handleExport = async () => {
		if (!selectedDate) return;
		setLoading(true);
		setError(null);
		try {
			const res = await api.get<NettBookingData>("/CAM/Others/NetBookingAPPI/api/nett-booking/excel", {
				params: { date_from: dateToParam(selectedDate) },
			});
			exportExcel(res.data, selectedDate);
		} catch {
			setError("Gagal mengekspor data. Silakan coba lagi.");
		} finally {
			setLoading(false);
		}
	};

	return (
		<div className="min-h-screen bg-gray-50 p-4 md:p-6">
			<div className="max-w-5xl mx-auto">
				<div className="mb-6">
					<h1 className="text-2xl font-semibold text-gray-800">Nett Booking APPI</h1>
					<p className="text-sm text-gray-500 mt-1">
						Laporan bulanan pembiayaan konvensional dan KBLBB
					</p>
				</div>

				<div className="bg-white rounded-xl border border-gray-200 p-4 flex flex-wrap gap-3 items-end">
					<MonthYearPicker
						value={selectedDate}
						onChange={(d) => { setSelectedDate(d); setError(null); }}
						required
					/>
					<button
						onClick={handleExport}
						disabled={!selectedDate || loading}
						className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-all
							bg-green-50 text-green-800 border border-green-200
							hover:bg-green-100 disabled:opacity-40 disabled:cursor-not-allowed"
					>
						{loading ? "Memuat…" : "Export to Excel"}
					</button>
				</div>

				{error && (
					<div className="mt-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
						{error}
					</div>
				)}

			</div>
		</div>
	);
};

export default NettBookingAPPIPage;