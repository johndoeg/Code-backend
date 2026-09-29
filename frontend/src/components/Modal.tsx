import React, { useEffect } from "react";

interface ModalProps {
    onClose: () => void;
    children: React.ReactNode;
    maxWidthClass?: string;
}

export default function Modal({ onClose, children, maxWidthClass = "max-w-lg" }: ModalProps) {
    useEffect(() => {
        const original = document.body.style.overflow;
        document.body.style.overflow = "hidden";
        return () => { document.body.style.overflow = original; };
    }, []);

    return (
        <div
            className="fixed inset-0 z-[10000] flex items-start justify-center p-4 sm:p-8 pt-10 bg-black/50 backdrop-blur-[1px]"
        >
            <div className={`w-full ${maxWidthClass} relative`}>
                <button
                    type="button"
                    onClick={onClose}
                    aria-label="Close"
                    className="absolute -top-3 -right-3 z-10 w-8 h-8 rounded-full bg-white shadow-md border border-gray-200 flex items-center justify-center text-gray-500 hover:text-gray-700 hover:shadow-lg transition-all"
                >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                </button>
                {children}
            </div>
        </div>
    );
}