import React, { useState } from 'react';
import { isImageFile } from '../constants/DefaultValue';

export interface PreviewState {
	open: boolean;
	name: string;
	url: string;
}

export const PREVIEW_CLOSED: PreviewState = { open: false, name: '', url: '' };

interface DocPreviewModalProps {
	state: PreviewState;
	onClose: () => void;
}

const DocPreviewModal: React.FC<DocPreviewModalProps> = ({ state, onClose }) => {
	const [imgError, setImgError] = useState(false);

	if (!state.open) return null;

	const cleanName = state.name.split('?')[0];
	const isImage = isImageFile(cleanName);
	const isPdf = cleanName.split('.').pop()?.toLowerCase() === 'pdf';

	return (
		<div
			onClick={onClose}
			style={{
				position: 'fixed',
				inset: 0,
				background: 'rgba(0,0,0,.7)',
				zIndex: 9999,
				display: 'flex',
				justifyContent: 'center',
				alignItems: 'center',
			}}
		>
			<div
				onClick={(e) => e.stopPropagation()}
				style={{
					width: '90%',
					height: '90%',
					background: '#fff',
					borderRadius: 10,
					overflow: 'hidden',
					display: 'flex',
					flexDirection: 'column',
				}}
			>
				<div
					style={{
						padding: '12px 16px',
						borderBottom: '1px solid #e5e7eb',
						display: 'flex',
						justifyContent: 'space-between',
						alignItems: 'center',
					}}
				>
					<span style={{ fontWeight: 600, fontSize: '.9rem' }}>{state.name}</span>
					<button onClick={onClose} style={{ cursor: 'pointer', background: 'none', border: 'none', fontSize: '1.2rem' }}>
						✕
					</button>
				</div>

				<div style={{ flex: 1, overflow: 'hidden', padding: 20 }}>
					{isImage && !imgError ? (
						<img
							src={state.url}
							alt={state.name}
							style={{ width: '100%', height: '100%', objectFit: 'contain' }}
							onError={() => setImgError(true)}
						/>
					) : isPdf ? (
						<iframe title={state.name} src={state.url} width="100%" height="100%" />
					) : (
						<div style={{ textAlign: 'center', paddingTop: 40 }}>
							<p style={{ marginBottom: 12, color: '#64748b' }}>
								{imgError ? 'Failed to load image.' : 'Preview not available for this file type.'}
							</p>
						</div>
					)}
				</div>
			</div>
		</div>
	);
};

export default DocPreviewModal;