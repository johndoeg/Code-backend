import React from 'react';
import DatePicker, { registerLocale } from 'react-datepicker';
import { id } from 'date-fns/locale';
import 'react-datepicker/dist/react-datepicker.css';

registerLocale('id', id);

function toDateFnsFormat(fmt: string): string {
	let out = fmt;
	out = out.replace(/YYYY/g, 'yyyy');
	out = out.replace(/DD/g, 'dd');

	return out;
}

function hasTime(fmt: string): boolean {
	return /HH|hh|mm|ss/.test(fmt.replace(/MM/g, ''));
}

interface AsOfDatePickerComponentProps {
	value: Date | null;
	onChange: (date: Date | null) => void;
	format?: string;
	timeIntervals?: number;
	label?: string;
	required?: boolean;
	placeholder?: string;
	minDate?: Date;
	maxDate?: Date;
	disabled?: boolean;
	className?: string;
}

const AsOfDatePickerComponent: React.FC<AsOfDatePickerComponentProps> = ({
	value,
	onChange,
	format = 'dd MMMM yyyy',
	timeIntervals = 30,
	label = 'As Of',
	required = false,
	placeholder = 'Pilih tanggal…',
	minDate,
	maxDate,
	disabled = false,
	className = '',
}) => {
	const dfFormat = toDateFnsFormat(format);
	const includeTime = hasTime(format);

	return (
		<div className={className}>
			{label && (
				<label className="block text-sm font-medium text-gray-700 mb-1">
					{label}
					{required && (
						<span className="text-red-500 ml-1" aria-hidden="true">*</span>
					)}
				</label>
			)}

			<DatePicker
				selected={value}
				onChange={onChange}
				locale="id"
				dateFormat={dfFormat}
				showTimeSelect={includeTime}
				showTimeSelectOnly={false}
				timeFormat="HH:mm"
				timeIntervals={timeIntervals}
				timeCaption="Waktu"
				showMonthDropdown
				showYearDropdown
				dropdownMode="select"
				yearDropdownItemNumber={10}
				minDate={minDate}
				maxDate={maxDate}
				disabled={disabled}
				placeholderText={placeholder}
				className={[
					'w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm text-sm',
					'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
					'bg-white',
					disabled ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer',
				].join(' ')}
				wrapperClassName="w-full"
				calendarClassName="shadow-xl border border-gray-200 rounded-xl overflow-hidden"
				renderCustomHeader={({
					date,
					changeYear,
					changeMonth,
					decreaseMonth,
					increaseMonth,
					prevMonthButtonDisabled,
					nextMonthButtonDisabled,
				}) => (
					<div className="flex items-center justify-between px-3 py-2
                          bg-gradient-to-r from-blue-600 to-indigo-700">
						<button
							type="button"
							onClick={decreaseMonth}
							disabled={prevMonthButtonDisabled}
							className="text-white hover:text-blue-200 font-bold text-lg
                         disabled:opacity-30 px-1 leading-none"
						>
							‹
						</button>

						<div className="flex items-center gap-2">
							{/* Month */}
							<select
								value={date.getMonth()}
								onChange={e => changeMonth(Number(e.target.value))}
								className="bg-white/20 text-white text-sm font-medium rounded px-2 py-1
                           border border-white/30 focus:outline-none cursor-pointer"
							>
								{[
									'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
									'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember',
								].map((m, i) => (
									<option key={m} value={i} className="text-gray-800 bg-white">{m}</option>
								))}
							</select>

							{/* Year */}
							<select
								value={date.getFullYear()}
								onChange={e => changeYear(Number(e.target.value))}
								className="bg-white/20 text-white text-sm font-medium rounded px-2 py-1
                           border border-white/30 focus:outline-none cursor-pointer"
							>
								{Array.from(
									{ length: 20 },
									(_, i) => new Date().getFullYear() - 10 + i
								).map(y => (
									<option key={y} value={y} className="text-gray-800 bg-white">{y}</option>
								))}
							</select>
						</div>

						<button
							type="button"
							onClick={increaseMonth}
							disabled={nextMonthButtonDisabled}
							className="text-white hover:text-blue-200 font-bold text-lg
                         disabled:opacity-30 px-1 leading-none"
						>
							›
						</button>
					</div>
				)}
			/>

			<style>{`
        .react-datepicker { font-family: inherit; border: none; border-radius: 0.75rem; }
        .react-datepicker__month-container { float: none; }
        .react-datepicker__header { background: transparent; border-bottom: 1px solid #e5e7eb; padding: 0; }
        .react-datepicker__day-names { background: #f9fafb; margin: 0; padding: 4px 0; }
        .react-datepicker__day-name { color: #6b7280; font-size: 0.7rem; font-weight: 600; text-transform: uppercase; }
        .react-datepicker__day { font-size: 0.8rem; color: #374151; width: 2rem; line-height: 2rem; margin: 1px; }
        .react-datepicker__day--selected,
        .react-datepicker__day--keyboard-selected { background: linear-gradient(to right, #2563eb, #4338ca); border-radius: 0.375rem; color: white; }
        .react-datepicker__day--selected.react-datepicker__day--today { color: white; }
        .react-datepicker__day--today { font-weight: 700; color: #2563eb; }
        .react-datepicker__day:hover:not(.react-datepicker__day--selected) { background-color: #eff6ff; border-radius: 0.375rem; }
        .react-datepicker__day--outside-month { color: #d1d5db; }
        .react-datepicker__time-container { border-left: 1px solid #e5e7eb; }
        .react-datepicker__time-list-item--selected { background: linear-gradient(to right, #2563eb, #4338ca) !important; }
        .react-datepicker__time-list-item:hover:not(.react-datepicker__time-list-item--selected) { background-color: #eff6ff !important; }
        .react-datepicker-popper { z-index: 50; }
      `}</style>
		</div>
	);
};

export default AsOfDatePickerComponent;