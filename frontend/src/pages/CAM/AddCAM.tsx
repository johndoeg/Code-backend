import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

interface CustomerTypeOption {
    value: string;
    label: string;
}

const AddCamForm: React.FC = () => {
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

    // Auto fetch customer data when ID Card/NPWP > 10 characters
    useEffect(() => {
        if (idCard.length > 10) {
            const fetchData = async () => {
                setIsPrechecking(true);
                try {
                    const response = await fetch(`${import.meta.env.VITE_API_URL}/CAM/check`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ idCard, customerType }),
                        credentials: "include",
                    });

                    const data = await response.json();

                    if (!response.ok) {
                        throw new Error(data.message || 'Failed to fetch customer data');
                    }

                    // Success - populate data
                    setCustomerName(data.customerName || '');
                    setApless(data.APLESS || '');
                } catch (err) {
                    console.error('Precheck error:', err);
                    setCustomerName('');
                    setApless('');
                } finally {
                    setIsPrechecking(false);
                }
            };

            fetchData();
        } else {
            // Clear data if ID is too short
            setCustomerName('');
            setApless('');
        }
    }, [idCard, customerType]);

    const handlePrecheck = async () => {
        if (!idCard.trim()) return;

        setIsPrechecking(true);
        try {
            const response = await fetch(`${import.meta.env.VITE_API_URL}/CAM/check`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ idCard, customerType }),
                credentials: "include",
            });

            const data = await response.json();

            if (!response.ok) throw new Error(data.message);

            setCustomerName(data.customerName || '');
            setApless(data.APLESS || '');

            // Navigate to Prechecking page
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
        <div className="max-w-md mx-auto p-6 bg-white rounded-lg shadow-md">
            <h1 className="text-2xl font-bold mb-6">ADD CAM</h1>

            <div className="space-y-6">
                {/* Customer Type */}
                <div className="flex items-center">
                    <label className="w-32 text-sm font-medium text-gray-700">Customer Type</label>
                    <select
                        value={customerType}
                        onChange={(e) => setCustomerType(e.target.value)}
                        className="flex-1 px-3 py-2 bg-white text-black rounded-md border border-gray-300 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                    >
                        {customerTypeOptions.map((option) => (
                            <option key={option.value} value={option.value}>
                                {option.label}
                            </option>
                        ))}
                    </select>
                </div>

                {/* ID Card / NPWP */}
                <div className="flex items-center">
                    <label className="w-32 text-sm font-medium text-gray-700">{idLabel}</label>
                    <input
                        type="text"
                        value={idCard}
                        onChange={(e) => setIdCard(e.target.value)}
                        maxLength={16}
                        placeholder={`Enter ${idLabel}`}
                        className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent"
                    />
                </div>

                {/* Customer Name - NON EDITABLE */}
                <div className="flex items-center">
                    <label className="w-32 text-sm font-medium text-gray-700">Customer Name</label>
                    <input
                        type="text"
                        value={customerName}
                        readOnly
                        className="flex-1 px-3 py-2 border border-gray-300 rounded-md bg-gray-50 text-gray-700 cursor-not-allowed"
                        placeholder="Auto-filled after search"
                    />
                </div>
            </div>

            {/* Buttons */}
            <div className="mt-8 flex gap-4">
                {/* Precheck Button - Always visible, enabled when ID Card is filled */}
                <button
                    onClick={handlePrecheck}
                    disabled={!idCard.trim() || isPrechecking}
                    className={`flex-1 px-6 py-2 rounded-md font-medium text-white transition-colors ${!idCard.trim() || isPrechecking
                            ? 'bg-blue-400 cursor-not-allowed'
                            : 'bg-blue-500 hover:bg-blue-600'
                        }`}
                >
                    {isPrechecking ? 'Checking...' : 'Precheck'}
                </button>

                {/* Create CAM Button - Only show when customer data exists */}
                {hasCustomerData && (
                    <button
                        onClick={handleCreateCam}
                        disabled={isCreating}
                        className={`flex-1 px-6 py-2 rounded-md font-medium text-white transition-colors ${isCreating
                                ? 'bg-orange-400 cursor-not-allowed'
                                : 'bg-orange-500 hover:bg-orange-600'
                            }`}
                    >
                        {isCreating ? 'Creating...' : 'Create CAM'}
                    </button>
                )}
            </div>
        </div>
    );
};

export default AddCamForm;