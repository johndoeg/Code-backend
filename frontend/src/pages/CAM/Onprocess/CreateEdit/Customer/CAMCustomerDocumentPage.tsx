import React from "react";
import CustIndividualDocumentPage from "./CustIndividualDocumentPage";

export interface CAMCustomerDocumentPageProps {
	apless: string;
	applNo: string;
	indCor: string;
	onSaved: (result: { apless: string; applno: string }) => void;
}

const CAMCustomerDocumentPage: React.FC<CAMCustomerDocumentPageProps> = ({ apless, applNo, indCor, onSaved }) => {
	if (indCor === "1") {
		return <CustIndividualDocumentPage apless={apless} applNo={applNo} onSaved={onSaved} />;
	}

	return (
		<div>
			<h2 className="text-xl font-bold text-slate-800 mb-1">Customer's Document</h2>
			<p className="text-sm text-slate-500 mb-4">Customer No. {apless || "(new)"}</p>
			<div className="rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
				<p className="text-base font-medium text-slate-700">
					Corporate document upload hasn't been migrated yet
				</p>
				<p className="mt-1 text-sm text-slate-500">
					The legacy app has four corporate variants (koperasi, CV, yayasan, PT) for this tab —
					none of their source has been provided yet, so none are wired up here.
				</p>
			</div>
		</div>
	);
};

export default CAMCustomerDocumentPage;