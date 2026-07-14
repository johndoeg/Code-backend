import React, { useState } from 'react';

interface PaginationProps {
	page: number;
	totalPages: number;
	onPageChange: (page: number) => void;
	totalItems: number;
	itemsPerPage: number;
	className?: string;
}

const Pagination: React.FC<PaginationProps> = ({
	page,
	totalPages,
	onPageChange,
	totalItems,
	itemsPerPage,
	className = ""
}) => {
	const [jumpValue, setJumpValue] = useState('');

	const startIndex = Math.min((page - 1) * itemsPerPage + 1, totalItems);
	const endIndex = Math.min(page * itemsPerPage, totalItems);

	const getPageNumbers = () => {
		const pages: number[] = [];
		if (totalPages <= 5) {
			for (let i = 1; i <= totalPages; i++) pages.push(i);
		} else if (page <= 3) {
			for (let i = 1; i <= 5; i++) pages.push(i);
		} else if (page >= totalPages - 2) {
			for (let i = totalPages - 4; i <= totalPages; i++) pages.push(i);
		} else {
			for (let i = page - 2; i <= page + 2; i++) pages.push(i);
		}
		return pages;
	};

	const handleJump = () => {
		const target = parseInt(jumpValue, 10);
		if (!isNaN(target) && target >= 1 && target <= totalPages) {
			onPageChange(target);
		}
		setJumpValue('');
	};

	const handleJumpKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
		if (e.key === 'Enter') handleJump();
	};

	const iconBtn = (disabled: boolean, onClick: () => void, title: string, children: React.ReactNode) => (
		<button
			onClick={onClick}
			disabled={disabled}
			title={title}
			className={`p-2 rounded-lg transition-colors ${disabled
				? 'text-gray-300 cursor-not-allowed'
				: 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
				}`}
		>
			{children}
		</button>
	);

	return (
		<div className={`flex items-center justify-between gap-4 ${className}`}>
			<div className="text-sm text-gray-500 shrink-0">
				Showing <span className="font-semibold text-gray-800">{startIndex}</span> to{' '}
				<span className="font-semibold text-gray-800">{endIndex}</span> of{' '}
				<span className="font-semibold text-gray-800">{totalItems}</span> results
			</div>

			<div className="flex items-center gap-2">
				{totalPages > 5 && (
					<div className="flex items-center gap-1.5 text-sm text-gray-600 mr-2">
						<span className="whitespace-nowrap">Go to</span>
						<input
							type="number"
							min={1}
							max={totalPages}
							value={jumpValue}
							onChange={(e) => setJumpValue(e.target.value)}
							onKeyDown={handleJumpKeyDown}
							placeholder="page"
							className="w-14 px-2 py-1.5 text-center border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
						/>
						<button
							onClick={handleJump}
							disabled={!jumpValue}
							className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
						>
							Go
						</button>
					</div>
				)}

				<div className="flex items-center space-x-1">
					{iconBtn(page === 1, () => onPageChange(1), 'First page', (
						<svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 19l-7-7 7-7M18 19l-7-7 7-7" />
						</svg>
					))}

					{iconBtn(page === 1, () => onPageChange(Math.max(page - 1, 1)), 'Previous page', (
						<svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7" />
						</svg>
					))}

					{getPageNumbers().map((pageNum) => (
						<button
							key={pageNum}
							onClick={() => onPageChange(pageNum)}
							className={`w-10 h-10 rounded-lg flex items-center justify-center text-sm font-medium transition-colors ${page === pageNum
								? 'bg-blue-600 text-white shadow-md'
								: 'text-gray-700 hover:bg-gray-100'
								}`}
						>
							{pageNum}
						</button>
					))}

					{iconBtn(page === totalPages, () => onPageChange(Math.min(page + 1, totalPages)), 'Next page', (
						<svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
						</svg>
					))}

					{iconBtn(page === totalPages, () => onPageChange(totalPages), 'Last page', (
						<svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 5l7 7-7 7M6 5l7 7-7 7" />
						</svg>
					))}
				</div>
			</div>
		</div>
	);
};

export default Pagination;