import React, { useState } from 'react';

interface DocChipProps {
	name: string;
	onPreview: () => void;
	onDelete?: () => void;
	deleting?: boolean;
}

const EyeIcon: React.FC = () => (
	<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
		<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
		<circle cx="12" cy="12" r="3" />
	</svg>
);

const TrashIcon: React.FC = () => (
	<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
		<polyline points="3 6 5 6 21 6" />
		<path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6m5 0V4a1 1 0 011-1h2a1 1 0 011 1v2" />
		<line x1="10" y1="11" x2="10" y2="17" />
		<line x1="14" y1="11" x2="14" y2="17" />
	</svg>
);

const SpinnerIcon: React.FC = () => (
	<svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="animate-spin">
		<circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity={0.25} />
		<path d="M22 12a10 10 0 00-10-10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
	</svg>
);

const DocChip: React.FC<DocChipProps> = ({ name, onPreview, onDelete, deleting = false }) => {
	const [viewHovered, setViewHovered] = useState(false);
	const [deleteHover, setDeleteHover] = useState(false);

	return (
		<div style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
			<button
				type="button"
				onClick={onPreview}
				onMouseEnter={() => setViewHovered(true)}
				onMouseLeave={() => setViewHovered(false)}
				style={{
					display: 'inline-flex',
					alignItems: 'center',
					gap: 6,
					border: `1px solid ${viewHovered ? '#ea580c' : '#f97316'}`,
					background: viewHovered ? '#f97316' : '#fff7ed',
					color: viewHovered ? '#fff' : '#c2410c',
					borderRadius: 6,
					padding: '5px 12px',
					fontSize: 13,
					fontWeight: 500,
					cursor: 'pointer',
					transition: 'background 0.15s, color 0.15s, border-color 0.15s',
				}}
			>
				<EyeIcon />
				View
			</button>

			<span
				title={name}
				style={{
					fontSize: 13,
					color: '#374151',
					maxWidth: 260,
					overflow: 'hidden',
					textOverflow: 'ellipsis',
					whiteSpace: 'nowrap',
				}}
			>
				{name}
			</span>

			{onDelete && (
				<button
					type="button"
					onClick={onDelete}
					onMouseEnter={() => setDeleteHover(true)}
					onMouseLeave={() => setDeleteHover(false)}
					disabled={deleting}
					title="Delete file"
					aria-label="Delete file"
					style={{
						display: 'inline-flex',
						alignItems: 'center',
						justifyContent: 'center',
						width: 26,
						height: 26,
						borderRadius: 6,
						border: 'none',
						flexShrink: 0,
						background: deleteHover && !deleting ? '#fee2e2' : 'transparent',
						color: deleting ? '#9ca3af' : deleteHover ? '#dc2626' : '#6b7280',
						cursor: deleting ? 'not-allowed' : 'pointer',
						transition: 'background 0.15s, color 0.15s',
					}}
				>
					{deleting ? <SpinnerIcon /> : <TrashIcon />}
				</button>
			)}
		</div>
	);
};

export default DocChip;