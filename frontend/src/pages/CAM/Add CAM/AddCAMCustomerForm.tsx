import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

interface CustomerTypeOption {
	value: string;
	label: string;
}

const Spinner: React.FC<{ className?: string }> = ({ className = 'w-4 h-4' }) => (
	<svg className={`animate-spin ${className}`} viewBox="0 0 24 24" fill="none">
		<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
		<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
	</svg>
);

const AddCAMCustomerForm: React.FC = () => {
	const navigate = useNavigate();

	const [customerType, setCustomerType] = useState<string>('PR');
	const [idCard, setIdCard] = useState<string>('');
	const [apless, setApless] = useState<string>('');
	const [customerName, setCustomerName] = useState<string>('');
	const [isPrechecking, setIsPrechecking] = useState<boolean>(false);
	const [isCreating, setIsCreating] = useState<boolean>(false);

	const customerTypeOptions: CustomerTypeOption[] = [
		{ value: 'PR', label: 'Individu' },
		{ value: 'PT', label: 'Corporate' },
	];

	useEffect(() => {
		if (idCard.length <= 12) {
			setCustomerName('');
			setApless('');
			return;
		}

		const timer = setTimeout(async () => {
			setIsPrechecking(true);
			try {
				const response = await fetch(`${import.meta.env.VITE_API_URL}/CAM/check`, {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ idCard, customerType }),
					credentials: 'include',
				});

				const data = await response.json();

				if (!response.ok) {
					throw new Error(data.message || 'Failed to fetch customer data');
				}

				setCustomerName(data.customerName || '');
				setApless(data.APLESS || '');
			} catch (err) {
				console.error('Precheck error:', err);
				setCustomerName('');
				setApless('');
			} finally {
				setIsPrechecking(false);
			}
		}, 500);

		return () => clearTimeout(timer);
	}, [idCard, customerType]);

	const handlePrecheck = async () => {
		if (!idCard.trim()) return;

		setIsPrechecking(true);
		try {
			const response = await fetch(`${import.meta.env.VITE_API_URL}/CAM/check`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ idCard, customerType }),
				credentials: 'include',
			});

			const data = await response.json();

			if (!response.ok) throw new Error(data.message);

			setCustomerName(data.customerName || '');
			setApless(data.APLESS || '');

			const route = customerType === 'PR'
				? '/PrecheckingIndividuPage'
				: '/PrecheckingCorporatePage';

			navigate(route, {
				state: {
					idCard,
					customerType,
					customerName: data.customerName,
				},
			});
		} catch (err: any) {
			alert(err.message || 'Precheck failed. Please try again.');
		} finally {
			setIsPrechecking(false);
		}
	};

	const handleCreateCam = () => {
		if (!customerName.trim()) return;

		setIsCreating(true);
		navigate('/CAMForm', {
			state: {
				idCard,
				customerType,
				customerName,
				apless,
			},
		});
	};

	const idLabel = customerType === 'PR' ? 'ID Card' : 'NPWP';
	const hasCustomerData = !!customerName.trim();

	return (
		<div className="bg-white rounded-2xl shadow-md border border-gray-100 overflow-hidden">
			<div className="bg-gradient-to-br from-orange-500 to-orange-600 px-6 py-5">
				<div className="flex items-center gap-3">
					<div className="bg-white/20 backdrop-blur-sm rounded-xl p-2.5 shrink-0">
						<svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
								d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
						</svg>
					</div>
					<div>
						<h1 className="text-lg font-bold text-white tracking-tight">Add New CAM</h1>
					</div>
				</div>
			</div>

			<div className="px-6 py-6 space-y-5">
				<div>
					<label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
						Customer Type
					</label>
					<div className="grid grid-cols-2 gap-2 p-1 bg-gray-100 rounded-lg">
						{customerTypeOptions.map((option) => (
							<button
								key={option.value}
								type="button"
								onClick={() => setCustomerType(option.value)}
								className={`py-2 px-4 rounded-md text-sm font-medium transition-all duration-150 ${customerType === option.value
									? 'bg-white text-orange-600 shadow-sm border border-orange-100'
									: 'text-gray-500 hover:text-gray-700'
									}`}
							>
								{option.label}
							</button>
						))}
					</div>
				</div>

				<hr className="border-gray-100" />

				<div>
					<label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
						{idLabel}
					</label>
					<div className="relative">
						<div className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
							<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
									d="M10 6H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V8a2 2 0 00-2-2h-5m-4 0V5a2 2 0 114 0v1m-4 0a2 2 0 104 0m-5 8a2 2 0 100-4 2 2 0 000 4zm0 0c1.306 0 2.417.835 2.83 2M9 14a3.001 3.001 0 00-2.83 2" />
							</svg>
						</div>
						<input
							type="text"
							value={idCard}
							onChange={(e) => setIdCard(e.target.value)}
							maxLength={16}
							placeholder={`Enter ${idLabel} number`}
							className="w-full pl-10 pr-14 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/25 focus:border-orange-400 transition-all placeholder:text-gray-300"
						/>
						<span className={`absolute right-3 top-1/2 -translate-y-1/2 text-xs tabular-nums transition-colors ${idCard.length === 16 ? 'text-orange-500 font-medium' : 'text-gray-300'
							}`}>
							{idCard.length}/16
						</span>
					</div>
				</div>

				<div>
					<div className="flex items-center justify-between mb-2">
						<label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider">
							Customer Name
						</label>

						{isPrechecking && (
							<span className="inline-flex items-center gap-1.5 text-xs font-medium text-blue-600 bg-blue-50 px-2.5 py-0.5 rounded-full">
								<Spinner className="w-3 h-3" />
								Fetching…
							</span>
						)}
						{!isPrechecking && hasCustomerData && (
							<span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-600 bg-emerald-50 px-2.5 py-0.5 rounded-full">
								<svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
								</svg>
								Verified
							</span>
						)}
					</div>
					<div className="relative">
						<div className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-300">
							<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
									d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
							</svg>
						</div>
						<input
							type="text"
							value={customerName}
							readOnly
							placeholder="Customer's Name"
							className="w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-lg bg-gray-50 text-sm text-gray-700 cursor-not-allowed placeholder:text-gray-300"
						/>
					</div>
				</div>
			</div>

			<div className="mx-6 border-t border-gray-100" />

			<div className="px-6 py-4 flex gap-3">
				<button
					onClick={handlePrecheck}
					disabled={!idCard.trim() || isPrechecking}
					className={`flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold text-white transition-all duration-150 ${!idCard.trim() || isPrechecking
						? 'bg-blue-300 cursor-not-allowed'
						: 'bg-blue-500 hover:bg-blue-600 shadow-sm hover:shadow-md hover:shadow-blue-200 active:scale-[0.98]'
						}`}
				>
					{isPrechecking ? (
						<><Spinner /> Checking…</>
					) : (
						<>
							<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
									d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
							</svg>
							Precheck
						</>
					)}
				</button>

				<button
					onClick={handleCreateCam}
					disabled={!hasCustomerData || isCreating}
					className={`flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold text-white transition-all duration-150 ${!hasCustomerData || isCreating
						? 'bg-orange-300 cursor-not-allowed'
						: 'bg-orange-500 hover:bg-orange-600 shadow-sm hover:shadow-md hover:shadow-orange-200 active:scale-[0.98]'
						}`}
				>
					{isCreating ? (
						<><Spinner /> Creating…</>
					) : (
						<>
							<svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
									d="M12 4v16m8-8H4" />
							</svg>
							Create CAM
						</>
					)}
				</button>
			</div>
		</div>
	);
};

export default AddCAMCustomerForm;