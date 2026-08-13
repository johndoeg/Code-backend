import React from "react";
import IndividualFinancialStatementPage from "./IndividualFinancialStatementPage";
import CorporateBalanceSheetPage from "./CorporateBalanceSheetPage";

export interface CAMFinancialInfoPageProps {
	apless: string;
	applNo: string;
	indCor: string;
	onSaved: (result: { apless: string; applno: string }) => void;
}

const CAMFinancialInfoPage: React.FC<CAMFinancialInfoPageProps> = ({ apless, applNo, indCor, onSaved }) => {
	if (indCor === "2") {
		return <CorporateBalanceSheetPage apless={apless} applNo={applNo} onSaved={onSaved} />;
	}
	return <IndividualFinancialStatementPage apless={apless} applNo={applNo} onSaved={onSaved} />;
};

export default CAMFinancialInfoPage;