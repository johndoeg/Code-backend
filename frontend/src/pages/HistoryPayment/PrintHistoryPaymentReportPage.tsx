//PrintHistoryPaymentReport.tsx
import React, { useEffect, useState, useCallback, useRef } from "react";
import { useLocation } from "react-router-dom";

interface PaymentRecord {
    LESSEE_NO: string;
    TRANS_CODE: string;
    LESSEE_NM: string;
    ADDRESS: string;
    PHONE1: string;
    PHONE2: string;
    PHONE3: string;
    BPKB_AN: string;
    POLICENO: string;
    CHASIS: string;
    ENGINE: string;
    TAHUN: string;
    COLOUR: string;
    SUPPNAME: string;
    TYPE_NM: string;
    MODEL_NM: string;
    BRANCH_NAME: string;
    BRAND_NM: string;
    DATEBLOKIR: string;
    NOPOLBLOKIR: string;
    STATUS_KONTRAK: string;
    JFG: string;
}

interface GiroRecord {
    girodt: string;
    payment: string;
    nominal: number;
    period: string;
    penalty: number;
    shortage: number;
    inkaso: number;
    girono: string;
    bank: string;
    status: string;
    reject_description: string;
    penalty_payment?: number;
    ShortagePay?: number;
    InkasoPay?: number;
}

interface PrintData {
    leaseNo: string;
    customer: PaymentRecord;
    giros: GiroRecord[];
    totals: {
        totalAmount: number;
        totalPenalty: number;
        totalShortage: number;
        totalInkaso: number;
        penaltyPayment: number;
        shortagePay: number;
        inkasoPay: number;
    };
}

const API_URL = import.meta.env.VITE_API_URL;

const HistoryPaymentPrint: React.FC = () => {
    const location = useLocation();
    const searchParams = new URLSearchParams(location.search);
    const printRef = useRef<HTMLDivElement>(null);

    const [printData, setPrintData] = useState<PrintData[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const leaseNos = searchParams.get("lease_no")?.split(",") || [];
    const sumber = searchParams.get("sumber") || "";
    const printBy = searchParams.get("print_by") || "";
    const username = localStorage.getItem("username") || "";

    const fetchPrintData = useCallback(async () => {
        if (leaseNos.length === 0) {
            setError("No contract numbers selected");
            setLoading(false);
            return;
        }

        try {
            const results = await Promise.all(
                leaseNos.map(async (leaseNo) => {
                    const customerRes = await fetch(`${API_URL}/Report/api/payment-history/${leaseNo}`, {
                        headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
                    });
                    const customer = await customerRes.json();

                    const girosRes = await fetch(`${API_URL}/Report/api/payment-history/${leaseNo}/giros`, {
                        headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
                        method: "POST",
                        body: JSON.stringify({ username }),
                    });
                    const giros = await girosRes.json();

                    const totals = giros.reduce(
                        (acc, giro: GiroRecord) => ({
                            totalAmount: acc.totalAmount + giro.nominal,
                            totalPenalty: acc.totalPenalty + giro.penalty,
                            totalShortage: acc.totalShortage + giro.shortage,
                            totalInkaso: acc.totalInkaso + giro.inkaso * 25000,
                            penaltyPayment: giro.penalty_payment || acc.penaltyPayment,
                            shortagePay: giro.ShortagePay || acc.shortagePay,
                            inkasoPay: giro.InkasoPay || acc.inkasoPay,
                        }),
                        {
                            totalAmount: 0,
                            totalPenalty: 0,
                            totalShortage: 0,
                            totalInkaso: 0,
                            penaltyPayment: 0,
                            shortagePay: 0,
                            inkasoPay: 0,
                        }
                    );

                    return {
                        leaseNo,
                        customer,
                        giros,
                        totals,
                    };
                })
            );

            setPrintData(results);
        } catch (err) {
            console.error("Failed to fetch print data:", err);
            setError("Failed to load payment history. Please try again.");
        } finally {
            setLoading(false);
        }
    }, [leaseNos, username]);

    useEffect(() => {
        fetchPrintData();
    }, [fetchPrintData]);

    useEffect(() => {
        if (!loading && printData.length > 0) {
        setTimeout(() => {
            window.print();
        }, 500);
        }
    }, [loading, printData]);

    const handlePrint = () => {
        window.print();
    };

    const formatCurrency = (value: number): string => {
        return new Intl.NumberFormat("id-ID").format(value);
    };

    const formatDate = (dateStr: string): string => {
        if (!dateStr) return "";
        const [year, month, day] = dateStr.split("-");
        return `${day}-${month}-${year}`;
    };

    const calculateOddays = (girodt: string, payment: string): number => {
        if (!girodt || !payment) return 0;
        const date1 = new Date(payment);
        const date2 = new Date(girodt);
        const diffTime = date2.getTime() - date1.getTime();
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        return diffDays < 0 ? 0 : diffDays;
    };

    if (loading) {
        return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50">
            <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-600 border-t-transparent mx-auto mb-4"></div>
                <p className="text-gray-600">Loading payment history...</p>
            </div>
        </div>
        );
    }

    if (error) {
        return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50">
            <div className="text-center p-6 bg-red-50 rounded-lg border border-red-200">
                <p className="text-red-700 mb-4">{error}</p>
                <button
                    onClick={() => window.close()}
                    className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
                >
                    Close Window
                </button>
            </div>
        </div>
        );
    }

    return (
        <div className="min-h-screen bg-white">
            {/* Print Button - Hidden when printing */}
            <div className="no-print fixed top-4 right-4 z-50">
                <button
                onClick={handlePrint}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg shadow hover:bg-blue-700 flex items-center gap-2"
                >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" />
                </svg>
                Print
                </button>
            </div>

            {/* Print Content */}
            <div ref={printRef} className="p-6 print:p-0">
                {printData.map((data, pageIndex) => (
                <div key={data.leaseNo} className="page-break print:page-break-after-always mb-8 print:mb-0">
                    {/* Header */}
                    <div className="flex justify-between items-start mb-4 border-b pb-2">
                        <div className="text-sm">
                            <span className="font-semibold">PT Genie Finance Indonesia</span>
                            <br />
                            {data.customer.BRANCH_NAME} Branch
                        </div>
                        <div className="text-right text-sm">
                            <div>Date: {new Date().toLocaleDateString("id-ID")}</div>
                            <div>Page: {pageIndex + 1}</div>
                        </div>
                    </div>

                    {/* Title */}
                    <div className="text-center mb-6">
                        <h1 className="text-lg font-bold underline">CUSTOMER HISTORY PAYMENT REPORT</h1>
                        <p className="text-sm">As of {new Date().toLocaleDateString("id-ID", { day: "numeric", month: "long", year: "numeric" })}</p>
                    </div>

                        {/* Customer Info */}
                        <table className="w-full text-sm mb-4">
                            <tbody>
                                <tr>
                                    <td className="w-1/6 font-medium">Transaction Code</td>
                                    <td className="w-1/3">: {data.customer.TRANS_CODE}</td>
                                    <td className="w-1/6 font-medium" rowSpan={2}>Address</td>
                                    <td className="w-1/3" rowSpan={2}>: {data.customer.ADDRESS}</td>
                                </tr>
                                <tr>
                                    <td className="font-medium">Customer No.</td>
                                    <td>: {data.customer.LESSEE_NO}</td>
                                </tr>
                                <tr>
                                    <td className="font-medium">Contract No.</td>
                                    <td>: {data.leaseNo} / {data.customer.LESSEE_NM}</td>
                                    <td className="font-medium">Telp</td>
                                    <td>: {[data.customer.PHONE1, data.customer.PHONE2, data.customer.PHONE3].filter(Boolean).join(", ")}</td>
                                </tr>
                            </tbody>
                        </table>

                        {/* Payment History Table */}
                        <table className="w-full text-xs border-collapse mb-4">
                            <thead>
                                <tr className="bg-gray-100 print:bg-transparent">
                                    <th className="border border-black px-2 py-1 text-center">No.</th>
                                    <th className="border border-black px-2 py-1 text-center">Cheque No.</th>
                                    <th className="border border-black px-2 py-1 text-center">Date Due</th>
                                    <th className="border border-black px-2 py-1 text-center">Bank</th>
                                    <th className="border border-black px-2 py-1 text-right">Amount</th>
                                    <th className="border border-black px-2 py-1 text-center">OD Days</th>
                                    <th className="border border-black px-2 py-1 text-center">Sts</th>
                                    <th className="border border-black px-2 py-1 text-center">Payment Date</th>
                                    <th className="border border-black px-2 py-1 text-right">Penalty Charge</th>
                                    <th className="border border-black px-2 py-1 text-right">Shortage</th>
                                    <th className="border border-black px-2 py-1 text-right">Inkaso</th>
                                    <th className="border border-black px-2 py-1 text-center">Remark</th>
                                </tr>
                            </thead>
                            <tbody>
                                {data.giros.map((giro, idx) => {
                                const oddays = calculateOddays(giro.girodt, giro.payment);
                                    return (
                                        <tr key={idx} className={idx % 2 === 0 ? "bg-gray-50 print:bg-transparent" : ""}>
                                            <td className="border border-black px-2 py-1 text-center">{idx + 1}</td>
                                            <td className="border border-black px-2 py-1 text-center">{giro.girono}</td>
                                            <td className="border border-black px-2 py-1 text-center">{formatDate(giro.girodt)}</td>
                                            <td className="border border-black px-2 py-1">{giro.bank}</td>
                                            <td className="border border-black px-2 py-1 text-right">{formatCurrency(giro.nominal)}</td>
                                            <td className="border border-black px-2 py-1 text-center">{oddays}</td>
                                            <td className="border border-black px-2 py-1 text-center">{giro.status}</td>
                                            <td className="border border-black px-2 py-1 text-center">{formatDate(giro.payment)}</td>
                                            <td className="border border-black px-2 py-1 text-right">{formatCurrency(giro.penalty)}</td>
                                            <td className="border border-black px-2 py-1 text-right">{formatCurrency(giro.shortage)}</td>
                                            <td className="border border-black px-2 py-1 text-right">{formatCurrency(giro.inkaso * 25000)}</td>
                                            <td className="border border-black px-2 py-1">{giro.reject_description}</td>
                                        </tr>
                                    );
                                    })}
                                    {/* Totals Row */}
                                    <tr className="font-semibold">
                                        <td className="border border-black px-2 py-1 text-right" colSpan={4}>TOTAL</td>
                                        <td className="border border-black px-2 py-1 text-right">{formatCurrency(data.totals.totalAmount)}</td>
                                        <td className="border border-black px-2 py-1" colSpan={3}></td>
                                        <td className="border border-black px-2 py-1 text-right">{formatCurrency(data.totals.totalPenalty)}</td>
                                        <td className="border border-black px-2 py-1 text-right">{formatCurrency(data.totals.totalShortage)}</td>
                                        <td className="border border-black px-2 py-1 text-right">{formatCurrency(data.totals.totalInkaso)}</td>
                                        <td className="border border-black px-2 py-1"></td>
                                    </tr>
                                    {/* Payment Totals Row */}
                                    <tr className="font-semibold">
                                        <td className="border border-black px-2 py-1 text-right" colSpan={8}>TOTAL PAYMENT</td>
                                        <td className="border border-black px-2 py-1 text-right">{formatCurrency(data.totals.penaltyPayment)}</td>
                                        <td className="border border-black px-2 py-1 text-right">{formatCurrency(data.totals.shortagePay)}</td>
                                        <td className="border border-black px-2 py-1 text-right">{formatCurrency(data.totals.inkasoPay)}</td>
                                        <td className="border border-black px-2 py-1"></td>
                                    </tr>
                            </tbody>
                        </table>

                        {/* Vehicle Info */}
                        <table className="w-full text-sm">
                            <tbody>
                                <tr>
                                    <td className="w-1/6 font-medium">Supplier</td>
                                    <td className="w-1/3">: {data.customer.SUPPNAME}</td>
                                    <td className="w-1/6 font-medium">Chasis</td>
                                    <td className="w-1/3">: {data.customer.CHASIS}</td>
                                    <td className="w-1/6 font-medium">Blocking Date</td>
                                    <td className="w-1/3">: {formatDate(data.customer.DATEBLOKIR)}</td>
                                </tr>
                                <tr>
                                    <td className="font-medium">BPKB A/N</td>
                                    <td>: {data.customer.BPKB_AN}</td>
                                    <td className="font-medium">Engine</td>
                                    <td>: {data.customer.ENGINE}</td>
                                    <td className="font-medium">No. Blocking</td>
                                    <td>: {data.customer.NOPOLBLOKIR}</td>
                                </tr>
                                <tr>
                                    <td className="font-medium">Police No.</td>
                                    <td>: {data.customer.POLICENO}</td>
                                    <td className="font-medium">Year</td>
                                    <td>: {data.customer.TAHUN}</td>
                                    <td className="font-medium">Contract Status</td>
                                    <td>: {data.customer.STATUS_KONTRAK} {data.customer.JFG}</td>
                                </tr>
                                <tr>
                                    <td className="font-medium">Type</td>
                                    <td>: {data.customer.BRAND_NM} {data.customer.TYPE_NM}</td>
                                    <td className="font-medium">Colour</td>
                                    <td colSpan={3}>: {data.customer.COLOUR}</td>
                                </tr>
                                <tr>
                                    <td className="font-medium">Model</td>
                                    <td>: {data.customer.MODEL_NM}</td>
                                    <td></td>
                                    <td colSpan={3}></td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                ))}
            </div>

            {/* Print Styles */}
            <style>{`
                @media print {
                    @page {
                        margin: 1cm;
                        size: A4;
                    }
                    
                    body {
                        -webkit-print-color-adjust: exact;
                        print-color-adjust: exact;
                        font-family: Tahoma, sans-serif;
                        font-size: 10px;
                    }
                    
                    .no-print {
                        display: none !important;
                    }
                    
                    .page-break {
                        page-break-after: always;
                    }
                    
                    table {
                        font-family: Tahoma, sans-serif;
                        font-size: 10px;
                    }
                    
                    h1 {
                        font-size: 13px;
                    }
                    
                    .judul {
                        font-size: 11px;
                    }
                }
                
                @media screen {
                    body {
                        font-family: Tahoma, sans-serif;
                        font-size: 12px;
                        background: url('../images/new_logo_genie.svg') center center repeat;
                        background-size: 220px;
                        opacity: 0.035;
                    }
                    
                    table {
                        font-family: Tahoma, sans-serif;
                        font-size: 12px;
                    }
                    
                    h1 {
                        font-size: 15px;
                    }
                    
                    .judul {
                        font-size: 13px;
                    }
                }
            `}</style>
        </div>
    );
};

export default HistoryPaymentPrint;