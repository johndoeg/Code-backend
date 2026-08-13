import React, { useState } from 'react';
import EditByMAPage from './EditByMAPage';
import EditCamByMAPage from './EditCamByMAPage';

const CamEditContainer: React.FC = () => {
	const [editingApplNo, setEditingApplNo] = useState<string | null>(null);

	if (editingApplNo) {
		return (
			<div>
				<div className="max-w-6xl mx-auto pt-4 px-4 md:px-6">
					<button
						onClick={() => setEditingApplNo(null)}
						className="text-sm text-blue-600 hover:underline"
					>
						&larr; Back to list
					</button>
				</div>
				<EditCamByMAPage applno={editingApplNo} />
			</div>
		);
	}

	return <EditByMAPage onEdit={(applno) => setEditingApplNo(applno)} />;
};

export default CamEditContainer;