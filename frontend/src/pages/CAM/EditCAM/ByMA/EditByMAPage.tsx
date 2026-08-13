import React, { useState } from 'react';
import api from '../../../../api/axiosInstance';

interface EditByMARows {
	appl_no: string;
	cam_no: string;
	create_date: string;
	customer_name: string;
	status: string;
	branch_cmo: string;
	editable: boolean;
}

interface EditByMAPageProps {
	onEdit: (applno: string) => void;
}

const EditByMAPage: React.FC<EditByMAPageProps> = ({ onEdit }) => {
	const [searchBy, setSearchBy] = useState('');
	const [searchVal, setSearchVal] = useState('');
	const [rows, setRows] = useState<EditByMARows[]>([]);
	const [loading, setLoading] = useState(false);
	const [hasSearched, setHasSearched] = useState(false);

	const runSearch = async () => {
		setLoading(true);
		setHasSearched(true);
		try {
			const res = await api.get<EditByMARows[]>('/CAM/Edit/api/cam-on-hand/list', {
				params: { search_by: searchBy, search_val: searchVal },
			});
			setRows(res.data);
		} catch (err) {
			console.error('Edit CAM search error:', err);
		} finally {
			setLoading(false);
		}
	};

	React.useEffect(() => {
		runSearch();
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, []);

	const handleEditClick = (row: EditByMARows) => {
		if (!row.editable) {
			alert('The Cam No is invalid.');
			return;
		}
		if (window.confirm('Are you sure to update data?')) {
			onEdit(row.appl_no);
		}
	};

	return (
		<div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
			<div className="max-w-6xl mx-auto">
				<div className="bg-white rounded-2xl shadow-lg p-6">
					<h1 className="text-xl md:text-2xl font-bold text-gray-800 mb-6">Edit CAM</h1>

					<div className="flex flex-wrap gap-2 items-center mb-6">
						<select
							value={searchBy}
							onChange={(e) => setSearchBy(e.target.value)}
							className="px-3 py-2 rounded-lg border border-gray-300 text-sm"
						>
							<option value="1">CAM No</option>
							<option value="2">Customer Name</option>
						</select>
						<input
							type="text"
							value={searchVal}
							onChange={(e) => setSearchVal(e.target.value)}
							placeholder="Search value"
							className="px-3 py-2 rounded-lg border border-gray-300 text-sm flex-1 min-w-[200px]"
						/>
						<button
							onClick={runSearch}
							className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
						>
							Search
						</button>
					</div>

					{loading ? (
						<div className="py-10 text-center">
							<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto" />
						</div>
					) : (
						<div className="overflow-x-auto rounded-lg border border-gray-200">
							<table className="w-full text-sm border-collapse">
								<thead>
									<tr className="bg-gray-100 text-gray-700">
										<th className="border border-gray-300 px-2 py-2 text-left">CAM Date</th>
										<th className="border border-gray-300 px-2 py-2 text-left">CAM No.</th>
										<th className="border border-gray-300 px-2 py-2 text-left">Customer Name</th>
										<th className="border border-gray-300 px-2 py-2 text-left">Status</th>
										<th className="border border-gray-300 px-2 py-2 text-left">Branch - CMO</th>
										<th className="border border-gray-300 px-2 py-2"></th>
									</tr>
								</thead>
								<tbody>
									{rows.length === 0 && hasSearched ? (
										<tr>
											<td colSpan={6} className="border border-gray-300 px-2 py-3 text-center text-gray-400">
												No records found.
											</td>
										</tr>
									) : (
										rows.map((row) => (
											<tr key={row.appl_no} className="odd:bg-gray-50">
												<td className="border border-gray-300 px-2 py-1 whitespace-nowrap">{row.create_date}</td>
												<td className="border border-gray-300 px-2 py-1 whitespace-nowrap">{row.cam_no}</td>
												<td className="border border-gray-300 px-2 py-1">{row.customer_name}</td>
												<td className="border border-gray-300 px-2 py-1">{row.status}</td>
												<td className="border border-gray-300 px-2 py-1">{row.branch_cmo}</td>
												<td className="border border-gray-300 px-2 py-1 text-center">
													<button
														onClick={() => handleEditClick(row)}
														className="bg-gray-200 hover:bg-gray-300 px-3 py-1 rounded text-xs"
													>
														Edit
													</button>
												</td>
											</tr>
										))
									)}
								</tbody>
							</table>
						</div>
					)}
				</div>
			</div>
		</div>
	);
};

export default EditByMAPage;