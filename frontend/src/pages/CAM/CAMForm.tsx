import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom'; // 👈 Add useLocation

interface PurposeOption {
    code: string;
    desc: string;
}

interface FinanceTypeOption {
    code: string;
    name: string;
}

export default function CamForm() {
    const navigate = useNavigate();
    const location = useLocation();
    
    const state = location.state as {
        apless: string;
        precheckingId: string;
        lesseeTp: 'PR' | 'PT';
        customerName?: string;
    } | null;
    
    const apless = state?.apless || '';
    const precheckingId = state?.precheckingId || '';
    const lesseeTp = state?.lesseeTp || 'PR';
    const customerName = state?.customerName || '';

    const [purposes, setPurposes] = useState<PurposeOption[]>([]);
    const [financeTypes, setFinanceTypes] = useState<FinanceTypeOption[]>([]);
    
    const [purpoffinc, setPurpoffinc] = useState('');
    const [finType, setFinType] = useState('');
    const [repeat] = useState('1');
    const [guarantor, setGuarantor] = useState('');
    const [newCar, setNewCar] = useState('');
    const [publicStatus, setPublicStatus] = useState('');
    const [boa, setBoa] = useState('');
    const [bot, setBot] = useState('');

    const showPublic = lesseeTp === 'PT';
    const showBoa = publicStatus === '1';
    const showBot = boa === '2';

    const [errors, setErrors] = useState<string[]>([]);
    const [isSubmitting, setIsSubmitting] = useState(false);

    useEffect(() => {
        if (!apless) {
            alert('Customer data not found. Please start from Add CAM.');
            navigate('/cam/add');
            return;
        }
    }, [apless, navigate]);

    useEffect(() => {
        const loadOptions = async () => {
            try {
                const res = await fetch(`${import.meta.env.VITE_API_URL}/CAM/init`);
                if (!res.ok) throw new Error('Failed to load options');
                const data = await res.json();
                setPurposes(data.purposes);
                setFinanceTypes(data.financeTypes);
            } catch (err) {
                console.error(err);
                setErrors(['Failed to load form options.']);
            }
        };
        loadOptions();
    }, []);

    const validate = () => {
        const errs: string[] = [];
        if (!purpoffinc) errs.push('Purpose of Finance must not be empty');
        if (!finType) errs.push('Finance type must not be empty');
        if (!guarantor) errs.push('Guarantor availability must not be empty');
        if (!newCar) errs.push('Vehicle condition must not be empty');
        if (showPublic && !publicStatus) errs.push('Go Public must not be empty');
        if (publicStatus === '1' && !boa) errs.push('Beneficial Owner Availability must not be empty');
        if (boa === '2' && !bot) errs.push('Beneficial Owner Type must not be empty');

        setErrors(errs);
        return errs.length === 0;
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!validate()) return;

        setIsSubmitting(true);
        setErrors([]);

        try {
            const params = new URLSearchParams({
                id1: finType,
                id2: lesseeTp === 'PR' ? '1' : '2',
                id3: repeat,
                id4: guarantor,
                id5: newCar,
                id6: 'New',
                id7: purpoffinc,
                id9: 'NEW',
                id11: boa || '1',
                id12: bot || '1',
                id13: publicStatus,
                apless: apless,
                applno: '',
                ins_loan: '',
                prechecking_id: precheckingId
            });

            navigate(`/cam/customer/detail?${params.toString()}`);
            
        } catch (err) {
            console.error(err);
            setErrors(['Submission failed. Please try again.']);
        } finally {
            setIsSubmitting(false);
        }
    };

   const handleFinTypeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
        const val = e.target.value;
        setFinType(val);

        if (val === 'S' || val === 'D' || val === 'M' || val === 'W') {
            setNewCar('1');
        }
    };

    const handlePublicChange = (val: string) => {
        setPublicStatus(val);
        if (val !== '1') {
            setBoa('');
            setBot('');
        }
    };

    const handleBoaChange = (val: string) => {
        setBoa(val);
        if (val !== '2') {
            setBot('');
        }
    };

    return (
        <div className="max-w-2xl mx-auto p-6 bg-white rounded shadow">
            <h1 className="text-xl font-bold text-blue-800 mb-6">Credit Approval Memorandum (CAM)</h1>

            {errors.length > 0 && (
                <div className="mb-4 p-3 bg-red-100 text-red-700 rounded">
                    {errors.map((err, i) => (
                        <div key={i}>{err}</div>
                    ))}
                </div>
            )}

            <form onSubmit={handleSubmit}>
                {/* Purpose of Finance */}
                <div className="mb-4">
                    <label className="block font-medium mb-1">Purpose of Finance</label>
                    <select
                        className="w-full p-2 border rounded"
                        value={purpoffinc}
                        onChange={(e) => setPurpoffinc(e.target.value)}
                    >
                        <option value="">Select</option>
                        {purposes.map((p) => (
                            <option key={p.code} value={p.code}>
                                {p.desc}
                            </option>
                        ))}
                    </select>
                </div>

                {/* Finance Type */}
                <div className="mb-4">
                    <label className="block font-medium mb-1">Finance Type</label>
                    <select
                        className="w-full p-2 border rounded"
                        value={finType}
                        onChange={handleFinTypeChange}
                    >
                        <option value="">Select</option>
                        {financeTypes.map((f) => (
                            <option key={f.code} value={f.code}>
                                {f.name}
                            </option>
                        ))}
                    </select>
                </div>

                {/* Customer Type */}
                <div className="mb-4">
                    <label className="block font-medium mb-1">Customer Type</label>
                    <div className="flex items-center space-x-4">
                        <label className="inline-flex items-center">
                            <input
                                type="radio"
                                name="ind_cor"
                                value="1"
                                checked={lesseeTp === 'PR'}
                                className="mr-2"
                                disabled
                            />
                            Individu
                        </label>
                        <label className="inline-flex items-center">
                            <input
                                type="radio"
                                name="ind_cor"
                                value="2"
                                checked={lesseeTp === 'PT'}
                                className="mr-2"
                                disabled
                            />
                            Corporate
                        </label>
                    </div>
                </div>

                {/* Vehicle Condition */}
                <div className="mb-4">
                    <label className="block font-medium mb-1">Vehicle Condition</label>
                    <div className="flex space-x-6">
                        <label className="inline-flex items-center">
                            <input
                                type="radio"
                                name="new_car"
                                value="1"
                                checked={newCar === '1'}
                                onChange={() => setNewCar('1')}
                                className="mr-2"
                            />
                            Used
                        </label>
                        <label className="inline-flex items-center">
                            <input
                                type="radio"
                                name="new_car"
                                value="2"
                                checked={newCar === '2'}
                                onChange={() => setNewCar('2')}
                                className="mr-2"
                                disabled={finType === 'S' || finType === 'D' || finType === 'M' || finType === 'W'}
                            />
                            New
                        </label>
                    </div>
                </div>

                {/* Guarantor */}
                <div className="mb-4">
                    <label className="block font-medium mb-1">Guarantor Availability</label>
                    <div className="flex space-x-6">
                        <label className="inline-flex items-center">
                            <input
                                type="radio"
                                name="guarantor"
                                value="1"
                                checked={guarantor === '1'}
                                onChange={() => setGuarantor('1')}
                                className="mr-2"
                            />
                            No
                        </label>
                        <label className="inline-flex items-center">
                            <input
                                type="radio"
                                name="guarantor"
                                value="2"
                                checked={guarantor === '2'}
                                onChange={() => setGuarantor('2')}
                                className="mr-2"
                            />
                            Yes
                        </label>
                    </div>
                </div>

                {/* Go Public (Corporate only) */}
                {showPublic && (
                    <>
                        <div className="mb-4">
                            <label className="block font-medium mb-1">Go Public</label>
                            <div className="flex space-x-6">
                                <label className="inline-flex items-center">
                                    <input
                                        type="radio"
                                        name="public"
                                        value="0"
                                        checked={publicStatus === '0'}
                                        onChange={() => handlePublicChange('0')}
                                        className="mr-2"
                                    />
                                    No
                                </label>
                                <label className="inline-flex items-center">
                                    <input
                                        type="radio"
                                        name="public"
                                        value="1"
                                        checked={publicStatus === '1'}
                                        onChange={() => handlePublicChange('1')}
                                        className="mr-2"
                                    />
                                    Yes
                                </label>
                            </div>
                        </div>

                        {showBoa && (
                            <div className="mb-4">
                                <label className="block font-medium mb-1">Beneficial Owner Availability</label>
                                <div className="flex space-x-6">
                                    <label className="inline-flex items-center">
                                        <input
                                            type="radio"
                                            name="boa"
                                            value="1"
                                            checked={boa === '1'}
                                            onChange={() => handleBoaChange('1')}
                                            className="mr-2"
                                        />
                                        Available
                                    </label>
                                    <label className="inline-flex items-center">
                                        <input
                                            type="radio"
                                            name="boa"
                                            value="2"
                                            checked={boa === '2'}
                                            onChange={() => handleBoaChange('2')}
                                            className="mr-2"
                                        />
                                        Not Available
                                    </label>
                                </div>
                            </div>
                        )}

                        {showBot && (
                            <div className="mb-4">
                                <label className="block font-medium mb-1">Beneficial Owner Type</label>
                                <div className="flex space-x-6">
                                    <label className="inline-flex items-center">
                                        <input
                                            type="radio"
                                            name="bot"
                                            value="1"
                                            checked={bot === '1'}
                                            onChange={() => setBot('1')}
                                            className="mr-2"
                                        />
                                        Type A
                                    </label>
                                    <label className="inline-flex items-center">
                                        <input
                                            type="radio"
                                            name="bot"
                                            value="2"
                                            checked={bot === '2'}
                                            onChange={() => setBot('2')}
                                            className="mr-2"
                                        />
                                        Type B
                                    </label>
                                </div>
                            </div>
                        )}
                    </>
                )}

                <button
                    type="submit"
                    disabled={isSubmitting}
                    className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                >
                    {isSubmitting ? 'Submitting...' : 'Submit'}
                </button>
            </form>
        </div>
    );
}