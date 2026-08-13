import { useEffect, useState } from "react";

const CONTROL_KEYS = new Set([
	"Backspace", "Delete", "Tab", "Escape", "Enter",
	"ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End",
]);

function isControlKeystroke(e: React.KeyboardEvent<HTMLInputElement>): boolean {
	return CONTROL_KEYS.has(e.key) || e.ctrlKey || e.metaKey || e.altKey;
}

export function handleDigitsOnlyKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
	if (isControlKeystroke(e)) return;
	if (!/^[0-9]$/.test(e.key)) e.preventDefault();
}

export function handlePercentKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
	if (isControlKeystroke(e)) return;
	if (e.key === "." && !e.currentTarget.value.includes(".")) return;
	if (!/^[0-9]$/.test(e.key)) e.preventDefault();
}

export function handlePercentKeyDownCapped(
	e: React.KeyboardEvent<HTMLInputElement>,
	maxCharsAfterDot = 3,
) {
	if (isControlKeystroke(e)) return;

	const value = e.currentTarget.value;
	const isDigit = /^[0-9]$/.test(e.key);
	const isDot = e.key === "." && !value.includes(".");
	const isBackspace = e.key === "Backspace";
	let valid = isDigit || isDot || isBackspace;

	const dotIndex = value.indexOf(".");
	if (dotIndex > -1) {
		const charsAfterDot = value.length + 1 - dotIndex;
		if (charsAfterDot > maxCharsAfterDot) {
			valid = isBackspace;
		}
	}

	if (!valid) e.preventDefault();
}

export function formatCurrencyDisplay(value: any): string {
	if (value === "" || value === null || value === undefined) return "";
	const num = typeof value === "number" ? value : parseFloat(String(value).replace(/[^0-9.-]/g, ""));
	if (Number.isNaN(num)) return "";
	return num.toLocaleString();
}

function stripToDigits(raw: string): string {
	return raw.replace(/[^0-9]/g, "");
}

export function Field({ label, children }: { label: string; children: React.ReactNode }) {
	return (
		<div>
			<label className="mb-1 block text-sm text-slate-600">{label}</label>
			{children}
		</div>
	);
}

export function NumberInput({
	value, onChange, onBlur, readOnly, suffix,
}: {
	value: any;
	onChange?: (v: string) => void;
	onBlur?: () => void;
	readOnly?: boolean;
	suffix?: string;
}) {
	return (
		<div className="flex items-center gap-2">
			<input
				type="text"
				inputMode="numeric"
				value={value ?? ""}
				readOnly={readOnly}
				onKeyDown={handleDigitsOnlyKeyDown}
				onChange={(e) => onChange?.(stripToDigits(e.target.value))}
				onBlur={onBlur}
				className={`w-32 rounded-lg border px-3 py-2 text-sm text-right ${readOnly ? "border-slate-200 bg-slate-50 text-slate-500" : "border-slate-300 bg-white"}`}
			/>
			{suffix && <span className="text-sm text-slate-500">{suffix}</span>}
		</div>
	);
}

export function CurrencyInput({
	value, onChange, onBlur, readOnly, className,
}: {
	value: any;
	onChange?: (v: string) => void;
	onBlur?: () => void;
	readOnly?: boolean;
	className?: string;
}) {
	const [focused, setFocused] = useState(false);
	const [text, setText] = useState(() => formatCurrencyDisplay(value));

	useEffect(() => {
		if (!focused) setText(formatCurrencyDisplay(value));
	}, [value, focused]);

	return (
		<input
			type="text"
			inputMode="numeric"
			value={text}
			readOnly={readOnly}
			onFocus={() => setFocused(true)}
			onKeyDown={handleDigitsOnlyKeyDown}
			onChange={(e) => {
				const raw = stripToDigits(e.target.value);
				setText(raw);
				onChange?.(raw);
			}}
			onBlur={() => {
				setFocused(false);
				setText(formatCurrencyDisplay(value));
				onBlur?.();
			}}
			className={`rounded-lg border px-3 py-2 text-sm text-right ${readOnly ? "border-slate-200 bg-slate-50 text-slate-500" : "border-slate-300 bg-white"} ${className || "w-full"}`}
		/>
	);
}

export function PercentInput({
	value, onChange, onBlur, readOnly, label, className, capDecimals,
}: {
	value: any;
	onChange?: (v: string) => void;
	onBlur?: () => void;
	readOnly?: boolean;
	label?: string;
	className?: string;
	capDecimals?: number;
}) {
	const keyHandler = (e: React.KeyboardEvent<HTMLInputElement>) =>
		typeof capDecimals === "number" ? handlePercentKeyDownCapped(e, capDecimals) : handlePercentKeyDown(e);

	return (
		<div className={`flex items-center gap-1 ${className || "flex-1"}`}>
			{label && <span className="text-xs text-slate-400">{label}</span>}
			<input
				type="text"
				inputMode="decimal"
				value={value ?? ""}
				readOnly={readOnly}
				onKeyDown={keyHandler}
				onChange={(e) => onChange?.(e.target.value)}
				onBlur={onBlur}
				className={`w-full rounded-lg border px-3 py-2 text-sm text-right ${readOnly ? "border-slate-200 bg-slate-50 text-slate-500" : "border-slate-300 bg-white"}`}
			/>
			<span className="text-sm text-slate-500">%</span>
		</div>
	);
}

export function RadioPair({
	name, value, options, onChange, disabled,
}: {
	name: string;
	value: any;
	options: [string, string][];
	onChange?: (v: string) => void;
	disabled?: boolean;
}) {
	return (
		<div className="flex gap-4">
			{options.map(([val, label]) => (
				<label
					key={val}
					className={`flex items-center gap-1 text-sm ${disabled ? "text-slate-400" : "text-slate-600"}`}
				>
					<input
						type="radio"
						name={name}
						value={val}
						checked={value === val}
						disabled={disabled}
						onChange={() => onChange?.(val)}
					/>
					{label}
				</label>
			))}
		</div>
	);
}

export function SelectInput({
	value, onChange, disabled, placeholder, children, className,
}: {
	value: any;
	onChange?: (v: string) => void;
	disabled?: boolean;
	placeholder?: string;
	children: React.ReactNode;
	className?: string;
}) {
	return (
		<select
			value={value ?? ""}
			disabled={disabled}
			onChange={(e) => onChange?.(e.target.value)}
			className={`w-full rounded-lg border px-3 py-2 text-sm ${disabled
				? "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400"
				: "border-slate-300 bg-white text-slate-700"
				} ${className || ""}`}
		>
			{placeholder && <option value="">{placeholder}</option>}
			{children}
		</select>
	);
}