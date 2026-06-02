import React, { useEffect, useState, useCallback } from 'react';
import api from '../../api/axiosInstance';
import Pagination from '../../helpers/Pagination';
import { DEFAULT_PAGE_LIMIT } from '../../constants/DefaultValue';

interface InsuranceRecord {
    lease_no: string;
    lessee_nm: string;
    ins_co: string;
    policy_no: string;
    status: string;
    respond: string;
    success_dt: string;
}

interface ContractRow {
    lease_no: string;
    LESSEE_NM: string;
    INS_CD: string;
    INS_CO: string;
    MSTR_CL: string;
}

interface InsuranceCompany {
    INS_CD: string;
    INS_CO: string;
}

const isWithinSaveWindow = (): boolean => {
    const now = new Date(
        new Date().toLocaleString('en-US', { timeZone: 'Asia/Jakarta' })
    );
    const h = now.getHours();
    const m = now.getMinutes();
    const totalMin = h * 60 + m;
    return totalMin >= 6 * 60 && totalMin < 12 * 60;
};

const StatusIcon: React.FC<{ status: string }> = ({ status }) => {
    if (status === '') return null;
    if (status === 'ER') return <span title="Error" className="text-red-500 text-lg">✗</span>;
    return <span title="Success" className="text-green-500 text-lg">✓</span>;
};

const InsuranceEntryPage: React.FC = () => {
    const [records, setRecords] = useState<InsuranceRecord[]>([]);
    const [companies, setCompanies] = useState<InsuranceCompany[]>([]);
    const [selectedIns, setSelectedIns] = useState<string>('All');
    const [contractNo, setContractNo] = useState<string>('');
    const [uploadFailed, setUploadFailed] = useState<boolean>(false);
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    const [page, setPage] = useState<number>(1);
    const [total, setTotal] = useState<number>(0);
    const limit = DEFAULT_PAGE_LIMIT;

    const [addModalOpen, setAddModalOpen] = useState<boolean>(false);
    const [retailContractNo, setRetailContractNo] = useState<string>('');
    const [masterContract, setMasterContract] = useState<string>('');
    const [contractRows, setContractRows] = useState<ContractRow[]>([]);
    const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());
    const [selectAll, setSelectAll] = useState<boolean>(false);
    const [saving, setSaving] = useState<boolean>(false);

    const branchCd: string = (window as any).__USER_BRANCH__ ?? '';

    const fetchCompanies = useCallback(async () => {
        try {
            const res = await api.get('/InsuranceEntry/api/companies');
            setCompanies(res.data ?? []);
        } catch {
            // non-fatal; dropdown will just be empty
        }
    }, []);

    const fetchRecords = useCallback(async (
        ins_cd = selectedIns,
        search = contractNo,
        failed = uploadFailed,
    ) => {
        setLoading(true);
        setError(null);
        try {
            const res = await api.get('/InsuranceEntry/api/list', {
                params: {
                    ins_cd: ins_cd === 'All' ? '00' : ins_cd,
                    search_val: search,
                    is_failed: failed ? 1 : 0,
                    page,
                    limit,
                },
            });
            if (res.data?.data) {
                setRecords(res.data.data);
                setTotal(res.data.total ?? res.data.data.length);
            } else {
                setRecords([]);
                setTotal(0);
            }
        } catch {
            setError('Failed to load data. Please try again.');
        } finally {
            setLoading(false);
        }
    }, [selectedIns, contractNo, uploadFailed, page, limit]);

    useEffect(() => { fetchCompanies(); }, [fetchCompanies]);
    useEffect(() => { fetchRecords(); }, [fetchRecords]);

    useEffect(() => { setPage(1); }, [selectedIns, uploadFailed]);

    const handleInsChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
        setSelectedIns(e.target.value);
        setContractNo('');
        setUploadFailed(false);
    };

    const handleSearch = () => {
        if (!contractNo.trim()) { alert('Please fill Contract No.'); return; }
        fetchRecords(selectedIns, contractNo, uploadFailed);
    };

    const handleUploadFailedChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setUploadFailed(e.target.checked);
    };

    const handleCancel = async (leaseNo: string) => {
        if (!leaseNo) { alert("Can't cancel this contract"); return; }
        try {
            const res = await api.post('/InsuranceEntry/api/cancel', { lease_no: leaseNo });
            if (res.data?.success) {
                alert('Data has been canceled');
                fetchRecords();
            } else {
                alert('Error canceling contract.');
            }
        } catch {
            alert('Error canceling contract.');
        }
    };

    const openAddModal = () => {
        if (!isWithinSaveWindow()) {
            alert('Save data hanya saat diantara jam 6 dan 12 WIB!');
            return;
        }
        setRetailContractNo('');
        setMasterContract('');
        setContractRows([]);
        setSelectedItems(new Set());
        setSelectAll(false);
        setAddModalOpen(true);
    };

    const handleGetContractData = async () => {
        if (!retailContractNo.trim()) { alert('Please fill Contract Retail No.'); return; }
        try {
            const res = await api.get('/InsuranceEntry/api/contract', {
                params: { lease_no: retailContractNo },
            });
            if (res.data?.error) {
                alert(res.data.error);
                return;
            }
            const rows: ContractRow[] = res.data ?? [];
            setContractRows(rows);
            setSelectedItems(new Set());
            setSelectAll(false);
            if (rows.length > 0) setMasterContract(rows[0].MSTR_CL ?? '');
        } catch {
            alert('Failed to fetch contract data.');
        }
    };

    const toggleSelectAll = (checked: boolean) => {
        setSelectAll(checked);
        if (checked) {
            setSelectedItems(new Set(contractRows.map(r => `${r.INS_CD},${r.lease_no}`)));
        } else {
            setSelectedItems(new Set());
        }
    };

    const toggleItem = (key: string) => {
        setSelectedItems(prev => {
            const next = new Set(prev);
            next.has(key) ? next.delete(key) : next.add(key);
            return next;
        });
    };

    const handleSave = async () => {
        if (!isWithinSaveWindow()) {
            alert('Save data hanya saat diantara jam 6 dan 12 WIB!');
            return;
        }
        if (!retailContractNo.trim()) { alert('Please fill Contract Retail No.'); return; }
        if (selectedItems.size === 0) { alert('Please, select at least one contract!'); return; }

        const arrayData = Array.from(selectedItems).map(key => {
            const [ins_cd, lease_no] = key.split(',');
            return { ins_cd: ins_cd.trim(), lease_no: lease_no.trim() };
        });

        setSaving(true);
        try {
            await api.post('/InsuranceEntry/api/save', { arrayData });
            alert('SUCCESS');
            setAddModalOpen(false);
            fetchRecords();
        } catch {
            alert('Failed to save. Please try again.');
        } finally {
            setSaving(false);
        }
    };

    const totalPages = Math.ceil(total / limit);
    const startIndex = (page - 1) * limit + 1;
    const canAdd = branchCd === '100';

    return (
        <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
            <div className="max-w-7xl mx-auto">
                <div className="bg-white rounded-2xl shadow-lg p-6 mb-6">

                    {/* Header */}
                    <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4 mb-6">
                        <div>
                            <h1 className="text-2xl md:text-3xl font-bold text-gray-800">Entry Host to Host</h1>
                            <p className="text-gray-600 mt-1">Manage insurance H2H entries</p>
                        </div>
                        <button
                            onClick={openAddModal}
                            disabled={!canAdd}
                            title={!canAdd ? 'Only branch 100 can add entries' : ''}
                            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed
							           text-white w-12 h-12 rounded-xl text-2xl font-bold flex items-center justify-center
							           shadow-md hover:shadow-lg transition-all self-start"
                        >
                            +
                        </button>
                    </div>

                    {/* Filters */}
                    <div className="flex flex-col sm:flex-row flex-wrap gap-4 mb-6">
                        {/* Insurance company */}
                        <div className="flex flex-col gap-1.5">
                            <label htmlFor="ins_cd" className="text-sm font-medium text-gray-700">
                                Insurance Company:
                            </label>
                            <select
                                id="ins_cd"
                                value={selectedIns}
                                onChange={handleInsChange}
                                className="px-3 py-2 border border-gray-300 rounded-md shadow-sm text-sm
								           focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                style={{ height: '2.2rem' }}
                            >
                                <option value="All">All Insurance Company</option>
                                {companies.map(c => (
                                    <option key={c.INS_CD} value={c.INS_CD}>{c.INS_CO}</option>
                                ))}
                            </select>
                        </div>

                        {/* Contract search */}
                        <div className="flex flex-col gap-1.5">
                            <label htmlFor="contract_no" className="text-sm font-medium text-gray-700">
                                Search By Contract No:
                            </label>
                            <div className="flex gap-2">
                                <input
                                    id="contract_no"
                                    type="text"
                                    value={contractNo}
                                    onChange={e => setContractNo(e.target.value)}
                                    onKeyDown={e => e.key === 'Enter' && handleSearch()}
                                    className="px-3 py-1.5 border border-gray-300 rounded-md text-sm
									           focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    style={{ height: '2.2rem', width: '200px' }}
                                />
                                <button
                                    onClick={handleSearch}
                                    className="bg-blue-600 hover:bg-blue-700 text-white px-4 rounded-md text-sm
									           font-medium transition-colors"
                                    style={{ height: '2.2rem' }}
                                >
                                    Search
                                </button>
                            </div>
                        </div>

                        {/* Upload failed checkbox */}
                        <div className="flex items-end gap-2 pb-1">
                            <label htmlFor="upload_failed" className="text-sm font-medium text-gray-700">
                                Upload Failed
                            </label>
                            <input
                                type="checkbox"
                                id="upload_failed"
                                checked={uploadFailed}
                                onChange={handleUploadFailedChange}
                                className="w-4 h-4 text-blue-600 rounded border-gray-300
								           focus:ring-blue-500 cursor-pointer"
                            />
                        </div>
                    </div>

                    {/* Error banner */}
                    {error && (
                        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700
						                flex items-center gap-2 text-sm">
                            <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24"
                                stroke="currentColor" strokeWidth={2}>
                                <circle cx="12" cy="12" r="10" />
                                <line x1="12" y1="8" x2="12" y2="12" />
                                <line x1="12" y1="16" x2="12.01" y2="16" />
                            </svg>
                            {error}
                            <button onClick={() => fetchRecords()} className="ml-auto underline text-red-900">
                                Retry
                            </button>
                        </div>
                    )}

                    {/* Table */}
                    <div className="overflow-x-auto overflow-y-auto rounded-lg border border-gray-200 max-h-[65vh]">
                        <table className="w-full text-sm">
                            <thead className="bg-gradient-to-r from-gray-50 to-gray-100 sticky top-0">
                                <tr>
                                    {['No.', 'Contract No.', 'Customer Name', 'Insurance Company',
                                        'Policy No.', 'Status', 'Message', 'Success Date', ''].map(h => (
                                            <th key={h}
                                                className="py-3 px-4 text-left text-xs font-medium text-gray-500
										               uppercase tracking-wider whitespace-nowrap">
                                                {h}
                                            </th>
                                        ))}
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-200">
                                {loading ? (
                                    <tr>
                                        <td colSpan={9} className="py-10 text-center">
                                            <div className="flex justify-center">
                                                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
                                            </div>
                                        </td>
                                    </tr>
                                ) : records.length === 0 ? (
                                    <tr>
                                        <td colSpan={9} className="py-10 text-center text-gray-500">
                                            No records found.
                                        </td>
                                    </tr>
                                ) : (
                                    records.map((r, idx) => (
                                        <tr key={r.lease_no + idx}
                                            className={`hover:bg-gray-50 transition-colors
										               ${idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}`}>
                                            <td className="py-3 px-4 text-center font-medium text-gray-900">
                                                {startIndex + idx}
                                            </td>
                                            <td className="py-3 px-4 text-gray-700">{r.lease_no}</td>
                                            <td className="py-3 px-4 text-gray-700 max-w-[200px] truncate">{r.lessee_nm}</td>
                                            <td className="py-3 px-4 text-gray-700 max-w-[160px] truncate">{r.ins_co}</td>
                                            <td className="py-3 px-4 text-gray-700">{r.policy_no}</td>
                                            <td className="py-3 px-4 text-center">
                                                <StatusIcon status={r.status} />
                                            </td>
                                            <td className="py-3 px-4 text-gray-700 max-w-[200px] truncate"
                                                title={r.respond}>
                                                {r.respond}
                                            </td>
                                            <td className="py-3 px-4 text-gray-700 whitespace-nowrap">{r.success_dt}</td>
                                            <td className="py-3 px-4 text-center">
                                                {r.status === '' && (
                                                    <button
                                                        onClick={() => handleCancel(r.lease_no)}
                                                        className="bg-blue-600 hover:bg-blue-700 text-white
														           px-3 py-1 rounded text-xs font-medium transition-colors"
                                                    >
                                                        Cancel
                                                    </button>
                                                )}
                                            </td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>

                    {!loading && total > 0 && (
                        <Pagination
                            page={page}
                            totalPages={totalPages}
                            onPageChange={setPage}
                            totalItems={total}
                            itemsPerPage={limit}
                            className="mt-6"
                        />
                    )}
                </div>
            </div>

            {/* Add-contract modal                                                   */}
            {addModalOpen && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
                    <div className="bg-white rounded-2xl shadow-xl w-full max-w-5xl max-h-[90vh]
					                overflow-hidden flex flex-col">

                        {/* Modal header */}
                        <div className="flex justify-between items-center p-6 border-b">
                            <h2 className="text-xl font-bold text-gray-800">
                                Entry Host To Host — Input Contract
                            </h2>
                            <button onClick={() => setAddModalOpen(false)}
                                className="text-gray-500 hover:text-gray-700">
                                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                                        d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>

                        {/* Modal body */}
                        <div className="p-6 overflow-y-auto flex-grow min-h-0 space-y-4">

                            {/* Contract retail row */}
                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 items-end">
                                <div className="flex flex-col gap-1.5">
                                    <label className="text-sm font-medium text-gray-700">
                                        Contract Retail No.
                                    </label>
                                    <input
                                        type="text"
                                        value={retailContractNo}
                                        onChange={e => setRetailContractNo(e.target.value)}
                                        onKeyDown={e => e.key === 'Enter' && handleGetContractData()}
                                        className="px-3 py-2 border border-gray-300 rounded-md text-sm
										           focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                </div>
                                <div>
                                    <button
                                        onClick={handleGetContractData}
                                        className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2
										           rounded-md text-sm font-medium transition-colors"
                                    >
                                        Search
                                    </button>
                                </div>
                            </div>

                            {/* Contract master (read-only) */}
                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 items-end">
                                <div className="flex flex-col gap-1.5">
                                    <label className="text-sm font-medium text-gray-700">
                                        Contract Master No.
                                    </label>
                                    <input
                                        type="text"
                                        readOnly
                                        value={masterContract}
                                        className="px-3 py-2 border border-gray-200 rounded-md text-sm
										           bg-gray-50 text-gray-600 cursor-not-allowed"
                                    />
                                </div>
                            </div>

                            {/* Cover date (read-only, today) */}
                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 items-end">
                                <div className="flex flex-col gap-1.5">
                                    <label className="text-sm font-medium text-gray-700">Cover Date</label>
                                    <input
                                        type="text"
                                        readOnly
                                        value={new Date().toLocaleDateString('id-ID', {
                                            day: '2-digit', month: 'short', year: 'numeric',
                                        })}
                                        className="px-3 py-2 border border-gray-200 rounded-md text-sm
										           bg-gray-50 text-gray-600 cursor-not-allowed"
                                    />
                                </div>
                            </div>

                            {/* Entry table */}
                            <div className="overflow-x-auto rounded-lg border border-gray-200 max-h-[35vh]">
                                <table className="w-full text-sm">
                                    <thead className="bg-gradient-to-r from-gray-50 to-gray-100 sticky top-0">
                                        <tr>
                                            <th className="py-3 px-4 text-left text-xs font-medium text-gray-500
											               uppercase tracking-wider" style={{ width: '5%' }}>
                                                No.
                                            </th>
                                            <th className="py-3 px-4 text-left text-xs font-medium text-gray-500
											               uppercase tracking-wider" style={{ width: '15%' }}>
                                                Contract No.
                                            </th>
                                            <th className="py-3 px-4 text-left text-xs font-medium text-gray-500
											               uppercase tracking-wider" style={{ width: '25%' }}>
                                                Customer Name
                                            </th>
                                            <th className="py-3 px-4 text-left text-xs font-medium text-gray-500
											               uppercase tracking-wider" style={{ width: '15%' }}>
                                                Insurance Company
                                            </th>
                                            <th className="py-3 px-4 text-center text-xs font-medium text-gray-500
											               uppercase tracking-wider" style={{ width: '10%' }}>
                                                <div className="flex items-center justify-center gap-2">
                                                    Select All
                                                    <input
                                                        type="checkbox"
                                                        checked={selectAll}
                                                        onChange={e => toggleSelectAll(e.target.checked)}
                                                        className="w-4 h-4 text-blue-600 rounded border-gray-300
														           focus:ring-blue-500 cursor-pointer"
                                                    />
                                                </div>
                                            </th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-200">
                                        {contractRows.length === 0 ? (
                                            <tr>
                                                <td colSpan={5}
                                                    className="py-8 text-center text-gray-400 text-sm italic">
                                                    Search a contract to see available rows.
                                                </td>
                                            </tr>
                                        ) : (
                                            contractRows.map((row, idx) => {
                                                const key = `${row.INS_CD},${row.lease_no}`;
                                                return (
                                                    <tr key={key}
                                                        className={`hover:bg-gray-50 transition-colors
													               ${idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}`}>
                                                        <td className="py-3 px-4 text-center text-gray-900 font-medium">
                                                            {idx + 1}
                                                        </td>
                                                        <td className="py-3 px-4 text-gray-700">{row.lease_no}</td>
                                                        <td className="py-3 px-4 text-gray-700">{row.LESSEE_NM}</td>
                                                        <td className="py-3 px-4 text-gray-700">{row.INS_CO}</td>
                                                        <td className="py-3 px-4 text-center">
                                                            <input
                                                                type="checkbox"
                                                                checked={selectedItems.has(key)}
                                                                onChange={() => toggleItem(key)}
                                                                className="w-4 h-4 text-blue-600 rounded border-gray-300
																           focus:ring-blue-500 cursor-pointer"
                                                            />
                                                        </td>
                                                    </tr>
                                                );
                                            })
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        {/* Modal footer */}
                        <div className="p-4 border-t flex justify-end gap-3">
                            <button
                                onClick={() => setAddModalOpen(false)}
                                className="px-4 py-2 border border-gray-300 rounded-md text-sm
								           text-gray-700 hover:bg-gray-50 transition-colors"
                            >
                                Close
                            </button>
                            <button
                                onClick={handleSave}
                                disabled={saving}
                                className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400
								           disabled:cursor-not-allowed text-white px-4 py-2 rounded-md
								           text-sm font-medium flex items-center gap-2 transition-colors"
                            >
                                {saving ? (
                                    <>
                                        <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                                            <circle className="opacity-25" cx="12" cy="12" r="10"
                                                stroke="currentColor" strokeWidth="4" />
                                            <path className="opacity-75" fill="currentColor"
                                                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                        </svg>
                                        Saving…
                                    </>
                                ) : 'Save'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default InsuranceEntryPage;