import React, { useState } from 'react';
import api from '../../../../api/axiosInstance';

interface SearchResultRow {
	id: string;
	label: string;
	address: string;
	id_card: string;
	appl_no: string;
	selectable: boolean;
	source: 'customer' | 'beneficiary';
}

interface CustomerBOSearchModalProps {
	open: boolean;
	onClose: () => void;
	lesseeTp: 'PR' | 'PT';
	ownApless: string;
	onSelect: (id: string, sourceType: 'customer' | 'beneficiary') => void;
}

const CustomerBOSearchModal: React.FC<CustomerBOSearchModalProps> = ({
	open, onClose, lesseeTp, ownApless, onSelect,
}) => {
	const [mode, setMode] = useState<'customer' | 'beneficiary'>('customer');
	const [search, setSearch] = useState('');
	const [results, setResults] = useState<SearchResultRow[]>([]);
	const [loading, setLoading] = useState(false);
	const [hasSearched, setHasSearched] = useState(false);

	if (!open) return null;

	const runSearch = async () => {
		setLoading(true);
		setHasSearched(true);
		try {
			const res = await api.get<SearchResultRow[]>('/CAM/Edit/api/customer-bo-search', {
				params: { mode, lessee_tp: lesseeTp, search, own_apless: ownApless, page: 1 },
			});
			setResults(res.data);
		} catch (err) {
			console.error('Customer/BO search error:', err);
		} finally {
			setLoading(false);
		}
	};

	const handlePick = (row: SearchResultRow) => {
		if (!row.selectable) return;
		onSelect(row.id, row.source);
		onClose();
	};

	return (
		<div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
			<div className="bg-white rounded-2xl shadow-xl w-full max-w-3xl max-h-[85vh] overflow-hidden flex flex-col">
				<div className="flex justify-between items-center p-4 border-b">
					<h3 className="font-bold text-gray-800">Select Beneficial Owner</h3>
					<button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">
						×
					</button>
				</div>

				<div className="p-4 border-b">
					<div className="flex gap-4 mb-3 text-sm">
						<label className="flex items-center gap-1">
							<input
								type="radio"
								checked={mode === 'customer'}
								onChange={() => { setMode('customer'); setResults([]); setHasSearched(false); }}
							/>
							Customer SFIN
						</label>
						<label className="flex items-center gap-1">
							<input
								type="radio"
								checked={mode === 'beneficiary'}
								onChange={() => { setMode('beneficiary'); setResults([]); setHasSearched(false); }}
							/>
							Customer Beneficial Owner
						</label>
					</div>
					<div className="flex gap-2">
						<input
							type="text"
							value={search}
							onChange={(e) => setSearch(e.target.value)}
							placeholder={mode === 'customer' ? 'Lessee Name' : 'Beneficial Owner Name'}
							className="flex-1 px-3 py-2 rounded-lg border border-gray-300 text-sm"
						/>
						<button
							onClick={runSearch}
							className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
						>
							Search
						</button>
					</div>
				</div>

				<div className="p-4 overflow-y-auto flex-grow">
					{loading ? (
						<div className="flex justify-center py-10">
							<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
						</div>
					) : !hasSearched ? (
						<div className="text-center text-gray-400 py-10 text-sm">Enter a name and search.</div>
					) : results.length === 0 ? (
						<div className="text-center text-gray-400 py-10 text-sm">No results found.</div>
					) : (
						<table className="w-full text-sm border-collapse">
							<thead>
								<tr className="bg-gray-100">
									<th className="border border-gray-300 px-2 py-1 text-left">
										{mode === 'customer' ? 'APLESS' : 'Beneficial ID'}
									</th>
									<th className="border border-gray-300 px-2 py-1 text-left">Name</th>
									<th className="border border-gray-300 px-2 py-1 text-left">
										{mode === 'customer' ? 'Address' : 'Alias'}
									</th>
									{mode === 'customer' && (
										<th className="border border-gray-300 px-2 py-1 text-left">ID Card</th>
									)}
								</tr>
							</thead>
							<tbody>
								{results.map((row, idx) => (
									<tr
										key={`${row.id}-${idx}`}
										className={`odd:bg-gray-50 ${row.selectable ? 'cursor-pointer hover:bg-blue-50' : 'opacity-40'}`}
										onClick={() => handlePick(row)}
									>
										<td className="border border-gray-300 px-2 py-1 text-blue-600">
											{row.selectable ? row.id : '-'}
										</td>
										<td className="border border-gray-300 px-2 py-1">{row.label}</td>
										<td className="border border-gray-300 px-2 py-1">{row.address}</td>
										{mode === 'customer' && (
											<td className="border border-gray-300 px-2 py-1">{row.id_card}</td>
										)}
									</tr>
								))}
							</tbody>
						</table>
					)}
				</div>
			</div>
		</div>
	);
};

export default CustomerBOSearchModal;