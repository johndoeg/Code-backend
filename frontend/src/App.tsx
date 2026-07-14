import "react-datepicker/dist/react-datepicker.css";
import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";

import { AuthProvider } from "./contexts/AuthContext";
import { CamProvider } from "./contexts/CamContext";
import CAMTabs from "./components/CAMTabs";
import Dashboard from "./pages/Dashboard";
import LoginPage from "./pages/LoginPage";
import NotFound from "./pages/NotFound";
import ProtectedRoute from "./components/ProtectedRoute";
import PublicRoute from "./components/PublicRoute";
import Sidebar from "./components/Sidebar";
import MaintenancePage from "./components/MaintenancePage";
import MaintenanceGate from "./components/MaintenanceGate";

function makeRoute(path, importFn, props = {}) {
	const Component = lazy(importFn);
	return { path, importFn, element: <Component {...props} />, Component };
}

const CAM_CORE_ROUTES = [
	makeRoute("/index", () => import("./pages/CAM/Add CAM/AddCAMCustomerForm")),
	makeRoute("/index-guarantor", () => import("./pages/CAM/Add CAM/AddCAMGuarantorForm")),
	makeRoute("/CAMForm", () => import("./pages/CAM/CAMForm"), {
		apless: "", precheckingId: "", lesseeTp: "PR",
	}),
	makeRoute("/cam-onhand", () => import("./pages/CAM/Onprocess/View/CAMOnhandPage")),
	makeRoute("/cam-inprogress", () => import("./pages/CAM/Onprocess/View/CAMInProgressPage")),
	makeRoute("/cam-approved", () => import("./pages/CAM/Onprocess/View/CAMApprovedPage")),
];

const CAM_PRECHECKING_ROUTES = [
	makeRoute("/PrecheckingIndividuPage", () => import("./pages/CAM/Prechecking/PrecheckingIndividuPage")),
	makeRoute("/PrecheckingCorporatePage", () => import("./pages/CAM/Prechecking/PrecheckingCorporatePage")),
	makeRoute("/PrecheckingGuarantorIndividuPage", () => import("./pages/CAM/Prechecking/PrecheckingGuarantorIndividuPage")),
	makeRoute("/PrecheckingGuarantorCorporatePage", () => import("./pages/CAM/Prechecking/PrecheckingGuarantorCorporatePage")),
	makeRoute("/cam-request-onhand", () => import("./pages/CAM/Prechecking/PrecheckingOnhandPage")),
	makeRoute("/cam-request-inprogress", () => import("./pages/CAM/Prechecking/PrecheckingInProgressPage")),
	makeRoute("/cam-request-approved", () => import("./pages/CAM/Prechecking/PrecheckingApprovedPage")),
	makeRoute("/cam-request-rejected", () => import("./pages/CAM/Prechecking/PrecheckingRejectedPage")),
	makeRoute("/view-prechecking", () => import("./pages/CAM/Prechecking/ViewPrecheckingPage")),
	makeRoute("/cam-request-approval", () => import("./pages/CAM/Prechecking/ApprovalPrecheckingPage")),
];

const CAM_REPORT_ROUTES = [
	makeRoute("/rpt-in-progress-cam", () => import("./pages/CAM/ReportView/ListApprovedCAM/ListInprogressCAMPage")),
	makeRoute("/report-nett-booking-appi", () => import("./pages/CAM/ReportView/Others/NettBookingAPPIPage")),
	makeRoute("/undisbursecontract", () => import("./pages/CAM/ReportView/Others/UndisbursedContractPage")),
	makeRoute("/report-list-cont-del-by-system", () => import("./pages/CAM/ReportView/Others/PendingContractWillBeDeletedBySystemPage")),
	makeRoute("/report-his-bpkb-submit", () => import("./pages/CAM/ReportView/Others/HistoryBPKBSubmissionPage")),
	makeRoute("/report-summary-cam-bycmo", () => import("./pages/CAM/ReportView/Others/MonthlySummaryCAMApprovedPage")),
	makeRoute("/report-f6pd", () => import("./pages/CAM/ReportView/Others/F6PDReportPage")),
	makeRoute("/rpt-top-customer", () => import("./pages/CAM/ReportView/Others/Top20CustomerPage")),
	makeRoute("/prechecking-and-cam-sla", () => import("./pages/CAM/ReportView/Others/PrecheckingAndCAMSLAPage")),
	makeRoute("/customer-outstanding", () => import("./pages/CAM/ReportView/Others/CustomerOustandingPage")),
	makeRoute("/summary-rundownosp", () => import("./pages/CAM/ReportView/Others/SummaryRunDownOSPPage")),
	makeRoute("/history-mrp", () => import("./pages/CAM/ReportView/Others/HistoryMRPPage")),
];

const MASTER_DATA_ROUTES = [
	makeRoute("/sales", () => import("./pages/MasterData/Sales/SalesPage")),
	makeRoute("/sales-entry", () => import("./pages/MasterData/Sales/SalesEntryPage")),
	makeRoute("/rpt-list-sales", () => import("./pages/MasterData/Sales/ListOfSalesPage")),
	makeRoute("/supplier", () => import("./pages/MasterData/Dealer/SupplierPage")),
	makeRoute("/supplier-entry", () => import("./pages/MasterData/Dealer/SupplierEntryPage")),
	makeRoute("/rpt-list-supplier", () => import("./pages/MasterData/Dealer/ListOfSupplierPage")),
	makeRoute("/report-delete-dealer", () => import("./pages/MasterData/Dealer/DealerDeletedReportPage")),
	makeRoute("/brand-entry", () => import("./pages/MasterData/CollateralObject/Brand/BrandPage")),
	makeRoute("/brand-vehicle", () => import("./pages/MasterData/CollateralObject/Brand/BrandVehiclePage")),
	makeRoute("/rpt-list-vehicle", () => import("./pages/MasterData/CollateralObject/Brand/ListBrandPage")),
	makeRoute("/model-entry", () => import("./pages/MasterData/CollateralObject/Model/ModelEntryPage")),
	makeRoute("/rpt-list-model", () => import("./pages/MasterData/CollateralObject/Model/ListModelPage")),
	makeRoute("/karoseri-entry", () => import("./pages/MasterData/CollateralObject/Karoseri/KaroseriPage")),
	makeRoute("/rpt-list-karoseri", () => import("./pages/MasterData/CollateralObject/Karoseri/ListKaroseriPage")),
	makeRoute("/group-entry", () => import("./pages/MasterData/Group/GroupPage")),
	makeRoute("/group-member", () => import("./pages/MasterData/Group/GroupMemberPage")),
	makeRoute("/rpt-group", () => import("./pages/MasterData/Group/GroupReportPage")),
	makeRoute("/insurance", () => import("./pages/MasterData/Insurance/InsurancePage")),
	makeRoute("/ins-company", () => import("./pages/MasterData/Insurance/InsuranceCompanyPage")),
	makeRoute("/rpt-list-insurance", () => import("./pages/MasterData/Insurance/ListOfInsuranceReportPage")),
	makeRoute("/wlist-entry", () => import("./pages/MasterData/Watchlist/WatchListEntryPage")),
	makeRoute("/wlist-edit", () => import("./pages/MasterData/Watchlist/WatchListEditPage")),
	makeRoute("/blacklist-entry", () => import("./pages/MasterData/Blacklist/BlackListEntryPage")),
	makeRoute("/master-data-threshold-level", () => import("./pages/MasterData/RatioAndDeviation/MasterDataThresholdLevelPage")),
	makeRoute("/master-data-ratio", () => import("./pages/MasterData/RatioAndDeviation/MasterDataRatioPage")),
	makeRoute("/master-data-ratio-view-edit", () => import("./pages/MasterData/RatioAndDeviation/MasterDataRatioViewEditPage")),
	makeRoute("/master-data-npf-range", () => import("./pages/MasterData/RatioAndDeviation/MasterDataNPFRangePage")),
	makeRoute("/master-data-deviation-dp", () => import("./pages/MasterData/RatioAndDeviation/MasterDataDeviationDPPage")),
	makeRoute("/master-data-deviation-dp-view", () => import("./pages/MasterData/RatioAndDeviation/MasterDataDeviationDPViewPage")),
	makeRoute("/industrial-code", () => import("./pages/MasterData/IndustryCode/IndustrialCodePage")),
];

const REPORT_ROUTES = [
	makeRoute("/rpt-his-pmt", () => import("./pages/HistoryPayment/HistoryPaymentReportPage")),
	makeRoute("/rpt-amortization", () => import("./pages/HistoryPayment/AmortizationReportPage")),
	makeRoute("/report-aging-detail", () => import("./pages/HistoryPayment/DetailAgingReportPage")),
	makeRoute("/report-aging-summary", () => import("./pages/HistoryPayment/SummaryAgingReportPage")),
	makeRoute("/rpt-jurnal-financing", () => import("./pages/Disbursement/JurnalFinancingPage")),
	makeRoute("/rpt-print-his-pmt", () => import("./pages/HistoryPayment/PrintHistoryPaymentPage")),
];

const INSURANCE_INVOICE_ROUTES = [
	makeRoute("/insurance-entry", () => import("./pages/Insurance/InsuranceEntryPage")),
	makeRoute("/insurance-report", () => import("./pages/Insurance/InsuranceReportPage")),
	makeRoute("/invoice-raksa", () => import("./pages/Insurance/InvoiceRaksaPage")),
	makeRoute("/invoice-simas", () => import("./pages/Insurance/InvoiceSimasPage")),
	makeRoute("/invoice-gps", () => import("./pages/GPS/InvoiceGPSPage")),
	makeRoute("/va-list", () => import("./pages/ESPAY/VAListPage")),
	makeRoute("/invoice", () => import("./pages/Delima/InvoicePage")),
	makeRoute("/report-list-fiducia", () => import("./pages/Delima/FiduciaReportPage")),
];

const OJK_ROUTES = [
	makeRoute("/form-10", () => import("./pages/OJK/SILARAS/Form10Page")),
	makeRoute("/slik", () => import("./pages/OJK/SLIKPage")),
	makeRoute("/sipesat", () => import("./pages/OJK/SipesatPage")),
];

const ADMIN_ROUTES = [
	makeRoute("/menu-entry", () => import("./pages/Menu/MenuEntryPage")),
	makeRoute("/menu-edit", () => import("./pages/Menu/MenuEditPage")),
	makeRoute("/uacc-entry", () => import("./pages/Menu/UserAccessPage")),
	makeRoute("/users", () => import("./pages/Menu/UsersPage")),
	makeRoute("/user-entry", () => import("./pages/Menu/UserEntryPage")),
	makeRoute("/employee-data", () => import("./pages/Employee/EmployeeDataPage")),
	makeRoute("/memo-employee", () => import("./pages/Employee/EmployeeMemoPage")),
];

const ALL_PROTECTED_ROUTES = [
	...CAM_CORE_ROUTES,
	...CAM_PRECHECKING_ROUTES,
	...CAM_REPORT_ROUTES,
	...MASTER_DATA_ROUTES,
	...REPORT_ROUTES,
	...INSURANCE_INVOICE_ROUTES,
	...OJK_ROUTES,
	...ADMIN_ROUTES,
];

const prefetchedPaths = new Set();
const routePrefetchMap = new Map(
	ALL_PROTECTED_ROUTES.map(({ path, importFn }) => [path, importFn]),
);

export function prefetchRoute(path) {
	if (prefetchedPaths.has(path)) return;
	const importFn = routePrefetchMap.get(path);

	if (!importFn) return;
	prefetchedPaths.add(path);
	importFn().catch(() => { });
}

function PageLoader() {
	return (
		<div className="flex items-center justify-center h-full min-h-[60vh]">
			<div className="flex flex-col items-center gap-3 text-gray-400">
				<div className="w-8 h-8 border-4 border-gray-200 border-t-blue-500 rounded-full animate-spin" />
				<span className="text-sm">Loading…</span>
			</div>
		</div>
	);
}

function AppLayout() {
	return (
		<div className="flex h-screen bg-gray-100">
			<Sidebar />
			<div className="flex-1 flex flex-col overflow-y-auto">
				<Suspense fallback={<PageLoader />}>
					<Outlet />
				</Suspense>
			</div>
		</div>
	);
}

function CAMLayout() {
	return (
		<CamProvider>
			<div className="flex h-screen bg-gray-100">
				<div className="flex-1 overflow-auto">
					<CAMTabs />
					<div className="p-6">
						<div className="bg-white rounded shadow min-h-[80vh]">
							<Suspense fallback={<PageLoader />}>
								<Outlet />
							</Suspense>
						</div>
					</div>
				</div>
			</div>
		</CamProvider>
	);
}


const AddCAMModal = lazy(() => import("./pages/CAM/Add CAM/AddCAMModal"));
const AddCAMGuarantorModal = lazy(() => import("./pages/CAM/Add CAM/AddCAMGuarantorModal"));

function AppRoutes() {
	const location = useLocation();
	const background = location.state && location.state.background;

	return (
		<>
			<Routes location={background || location}>
				<Route
					path="/maintenance"
					element={
						<MaintenancePage
							info={{
								error: "maintenance",
								message: "We're currently performing scheduled maintenance.",
								retry_after: 600,
								app_name: "GenieFinance",
							}}
						/>
					}
				/>
				<Route
					path="/login"
					element={<PublicRoute><LoginPage /></PublicRoute>}
				/>

				<Route element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
					<Route path="/" element={<Dashboard />} />
					{ALL_PROTECTED_ROUTES.map(({ path, element }) => (
						<Route key={path} path={path} element={element} />
					))}
					<Route path="/cam" element={<CAMLayout />}>
						<Route index element={<Navigate to="customer/detail" replace />} />
						<Route path="*" element={<Navigate to="customer/detail" replace />} />
					</Route>
					<Route path="*" element={<NotFound />} />
				</Route>
			</Routes>

			{background && (
				<Routes>
					<Route
						path="/index"
						element={
							<ProtectedRoute>
								<Suspense fallback={<PageLoader />}>
									<AddCAMModal />
								</Suspense>
							</ProtectedRoute>
						}
					/>
					<Route
						path="/index-guarantor"
						element={
							<ProtectedRoute>
								<Suspense fallback={<PageLoader />}>
									<AddCAMGuarantorModal />
								</Suspense>
							</ProtectedRoute>
						}
					/>
				</Routes>
			)}
		</>
	);
}

function App() {
	return (
		<MaintenanceGate>
			<AuthProvider>
				<BrowserRouter>
					<AppRoutes />
				</BrowserRouter>
			</AuthProvider>
		</MaintenanceGate>
	);
}

export default App;