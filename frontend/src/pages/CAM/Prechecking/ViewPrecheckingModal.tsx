import React, { useEffect } from "react";
import ViewPrecheckingPage from "./ViewPrecheckingPage";

export interface PrecheckingViewModalProps {
	open: boolean;
	apless: string;
	precheckingId: string;
	onClose: () => void;
}

/**
 * Modal wrapper around ViewPrecheckingPage — same pattern as the CAM detail
 * modal: wide panel, no close-on-backdrop-click, scroll lock while open.
 * The only way to dismiss it is the "Close" button inside the page header.
 */
const PrecheckingViewModal: React.FC<PrecheckingViewModalProps> = ({
	open,
	apless,
	precheckingId,
	onClose,
}) => {
	useEffect(() => {
		if (!open) return;
		const original = document.body.style.overflow;
		document.body.style.overflow = "hidden";
		return () => {
			document.body.style.overflow = original;
		};
	}, [open]);

	if (!open) return null;

	return (
		<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
			{/*
				No onClick on this backdrop — on purpose. Clicking outside the
				panel must NOT dismiss this modal. The only way out is the
				"Close" button inside ViewPrecheckingPage's header, wired to
				onClose below.
			*/}
			<div
				role="dialog"
				aria-modal="true"
				aria-label={`Prechecking ${precheckingId} detail`}
				className="flex max-h-[90vh] w-[90vw] flex-col overflow-hidden rounded-2xl bg-white shadow-2xl"
			>
				<div className="min-h-0 flex-1 overflow-y-auto">
					<ViewPrecheckingPage
						apless={apless}
						precheckingId={precheckingId}
						onClose={onClose}
					/>
				</div>
			</div>
		</div>
	);
};

export default PrecheckingViewModal;