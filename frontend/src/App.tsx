import "react-datepicker/dist/react-datepicker.css";
import { lazy, Suspense, useMemo, useState } from "react";
import { MemoryRouter, Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";

import { AuthProvider, useAuth } from "./contexts/AuthContext";
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

import type { ComponentType, ReactElement, LazyExoticComponent } from "react";

type RouteImportFn = () => Promise<{ default: ComponentType<any> }>;

interface RouteDef {
	path: string;
	importFn: RouteImportFn;
	element: ReactElement;
	Component: LazyExoticComponent<ComponentType<any>>;
}

function makeRoute(path: string, importFn: RouteImportFn, props: Record<string, any> = {}): RouteDef {
	const Component = lazy(importFn);
	return { path, importFn, element: <Component {...props} />, Component };
}

const CAM_CORE_ROUTES = [
	makeRoute("/index", () => import("./pages/CAM/AddCAM/AddCAMCustomerForm")),
	makeRoute("/index-guarantor", () => import("./pages/CAM/AddCAM/AddCAMGuarantorForm")),
	makeRoute("/CAMForm", () => import("./pages/CAM/CAMForm"), {
		apless: "", precheckingId: "", lesseeTp: "PR",
	}),
	makeRoute("/cam-onhand", () => import("./pages/CAM/Onprocess/Onhand/CAMOnhandPage")),
	makeRoute("/cam-inprogress", () => import("./pages/CAM/Onprocess/Inprogress/CAMInProgressPage")),
	makeRoute("/cam-approved", () => import("./pages/CAM/Onprocess/Approved/CAMApprovedPage")),
];

const CAM_PRECHECKING_ROUTES = [
	makeRoute("/PrecheckingIndividuPage", () => import("./pages/CAM/Prechecking/Individu/PrecheckingIndividuPage")),
	makeRoute("/PrecheckingCorporatePage", () => import("./pages/CAM/Prechecking/Corporate/PrecheckingCorporatePage")),
	makeRoute("/PrecheckingGuarantorIndividuPage", () => import("./pages/CAM/Prechecking/Individu/PrecheckingGuarantorIndividuPage")),
	makeRoute("/PrecheckingGuarantorCorporatePage", () => import("./pages/CAM/Prechecking/Corporate/PrecheckingGuarantorCorporatePage")),
	makeRoute("/cam-request-onhand", () => import("./pages/CAM/Prechecking/PrecheckingOnhandPage")),
	makeRoute("/cam-request-inprogress", () => import("./pages/CAM/Prechecking/PrecheckingInProgressPage")),
	makeRoute("/cam-request-approved", () => import("./pages/CAM/Prechecking/PrecheckingApprovedPage")),
	makeRoute("/cam-request-rejected", () => import("./pages/CAM/Prechecking/PrecheckingRejectedPage")),
	makeRoute("/view-prechecking", () => import("./pages/CAM/Prechecking/ViewPrecheckingPage")),
	makeRoute("/cam-request-approval", () => import("./pages/CAM/Prechecking/ApprovalPrecheckingPage")),
	makeRoute("/cam-request-edit-pr", () => import("./pages/CAM/Prechecking/Individu/CamRequestEditPRPage")),
	makeRoute("/cam-request-onhand-detail", () => import("./pages/CAM/Prechecking/Approval/CamRequestOnhandDetailPage")),
];

const CAM_REPORT_ROUTES = [
	makeRoute("/report-nett-booking-appi", () => import("./pages/CAM/ReportView/Others/NettBookingAPPIPage")),
	makeRoute("/undisbursecontract", () => import("./pages/CAM/ReportView/Others/UndisbursedContractPage")),
	makeRoute("/report-list-cont-del-by-system", () => import("./pages/CAM/ReportView/Others/PendingContractWillBeDeletedBySystemPage")),
	makeRoute("/report-his-bpkb-submit", () => import("./pages/CAM/ReportView/Others/HistoryBPKBSubmissionPage")),
	makeRoute("/report-pelunasan-mobil", () => import("./pages/CAM/ReportView/Others/LaporanPelunasanMobilPage")),
	makeRoute("/report-summary-cam-bycmo", () => import("./pages/CAM/ReportView/Others/MonthlySummaryCAMApprovedPage")),
	makeRoute("/report-f6pd", () => import("./pages/CAM/ReportView/Others/F6PDReportPage")),
	makeRoute("/rpt-top-customer", () => import("./pages/CAM/ReportView/Others/Top20CustomerPage")),
	makeRoute("/prechecking-and-cam-sla", () => import("./pages/CAM/ReportView/Others/PrecheckingAndCAMSLAPage")),
	makeRoute("/customer-outstanding", () => import("./pages/CAM/ReportView/Others/CustomerOustandingPage")),
	makeRoute("/summary-rundownosp", () => import("./pages/CAM/ReportView/Others/SummaryRunDownOSPPage")),
	makeRoute("/history-mrp", () => import("./pages/CAM/ReportView/Others/HistoryMRPPage")),

	makeRoute("/cam-ma", () => import("./pages/CAM/EditCAM/ByMA/CamEditContainer")),
	makeRoute("/edit-insurance", () => import("./pages/CAM/EditCAM/Insurance/EditInsurancePage")),

	makeRoute("/rpt-in-progress-cam", () => import("./pages/CAM/ReportView/ApprovedCAM/ListInprogressCAMPage")),
	makeRoute("/rpt-cam-by-cust-group", () => import("./pages/CAM/ReportView/ApprovedCAM/ListCAMByCustomerGroupPage")),
	makeRoute("/rpt-cam-by-app-date", () => import("./pages/CAM/ReportView/ApprovedCAM/ListCAMByApprovalDatePage")),
	makeRoute("/rpt-cam-by-app", () => import("./pages/CAM/ReportView/ApprovedCAM/ListCAMByApproverPage")),
	makeRoute("/rpt-approved-cam-by-car-cond", () => import("./pages/CAM/ReportView/ApprovedCAM/ListCAMByCarConditionPage")),
	makeRoute("/rpt-cam-by-dealer", () => import("./pages/CAM/ReportView/ApprovedCAM/ListApprovedByDealerPerDisbursementDatePage")),
	makeRoute("/rpt-rjt-cam", () => import("./pages/CAM/ReportView/ApprovedCAM/ListRejectedCAMPage")),
	makeRoute("/rpt-sum-cam-by-month", () => import("./pages/CAM/ReportView/ApprovedCAM/SummaryApprovedCAMPage")),
	makeRoute("/rpt-all-cam-data", () => import("./pages/CAM/ReportView/ApprovedCAM/AllCAMDataPage")),
	makeRoute("/rpt-all-insurance-data", () => import("./pages/CAM/ReportView/ApprovedCAM/AllInsuranceDataPage")),
	makeRoute("/rpt-cam-by-disb-date", () => import("./pages/CAM/ReportView/ApprovedCAM/ListCAMByDisbursementDatePage")),

	makeRoute("/report-cmo-daily-productivity", () => import("./pages/CAM/ReportView/CMOReport/CmoDailyProductivityPage")),
	makeRoute("/report-cmo-daily-productivity-by-branch", () => import("./pages/CAM/ReportView/CMOReport/CmoDailyProductivityByBranchPage")),
	makeRoute("/report-cmo-daily-productivity-by-cmo", () => import("./pages/CAM/ReportView/CMOReport/CmoDailyProductivityByCmoPage")),

	makeRoute("/hiscomm-incentivepayment-company", () => import("./pages/CAM/ReportView/Commission/Company/HistoryCommissionReportPage")),
	makeRoute("/detcomm-incentivepayment-company", () => import("./pages/CAM/ReportView/Commission/Company/DetailCommissionReportPage")),

	makeRoute("/hiscomm-incentivepayment-individu", () => import("./pages/CAM/ReportView/Commission/Individu/HistoryCommissionReportPage")),
	makeRoute("/detcomm-incentivepayment-individu", () => import("./pages/CAM/ReportView/Commission/Individu/DetailCommissionReportPage")),

	makeRoute("/report-monthly", () => import("./pages/CAM/ReportView/Incentive/HistoryIncentive3rdPartyReportPage")),
	makeRoute("/detail-report-monthly", () => import("./pages/CAM/ReportView/Incentive/DetailIncentive3rdPartyReportPage")),
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
	makeRoute("/wlist-entry-by-corsec", () => import("./pages/MasterData/Watchlist/WatchListEntryByCorsec")),
	makeRoute("/rpt-wlist", () => import("./pages/MasterData/Watchlist/WatchListReportPage")),
	makeRoute("/blacklist-entry", () => import("./pages/MasterData/Blacklist/BlackListEntryPage")),
	makeRoute("/rpt-blacklist", () => import("./pages/MasterData/Blacklist/BlackListReportPage")),
	makeRoute("/blacklist-pel-ttot", () => import("./pages/MasterData/Blacklist/TtotReportPage")),
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

const PROTECTED_ROUTE_ELEMENTS = ALL_PROTECTED_ROUTES.map(({ path, element }) => (
	<Route key={path} path={path} element={element} />
));

const prefetchedPaths = new Set();
const routePrefetchMap = new Map(
	ALL_PROTECTED_ROUTES.map(({ path, importFn }) => [path, importFn]),
);
const prefetchPromises = new Map();

export function prefetchRoute(path: string) {
	if (prefetchedPaths.has(path)) return prefetchPromises.get(path);
	const importFn = routePrefetchMap.get(path);
	if (!importFn) return undefined;

	prefetchedPaths.add(path);
	const promise = importFn().catch(() => {
		prefetchedPaths.delete(path);
	});
	prefetchPromises.set(path, promise);
	return promise;
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

function TopHeader() {
	const { user } = useAuth();
	const dateOverride = new URLSearchParams(window.location.search).get("date");

	const today = useMemo(
		() =>
			dateOverride ||
			new Date().toLocaleDateString("id-ID", {
				timeZone: "Asia/Jakarta",
				weekday: "long",
				year: "numeric",
				month: "long",
				day: "numeric",
			}),
		[dateOverride],
	);

	return (
		<header className="flex justify-between items-center bg-white shadow p-4 border-b shrink-0">
			<div className="text-gray-700 font-medium">
				{user ? (
					<>
						Hello,{" "}
						<span className="font-semibold text-blue-800">{user.username}</span>
						{" — "}
						<span className="text-blue-700">{user.branch_name}</span>
						{" — "}
						<span className="text-gray-500">{today}</span>
					</>
				) : (
					"Loading..."
				)}
			</div>
		</header>
	);
}

function AppLayout() {
	const [sidebarOpen, setSidebarOpen] = useState(true);
	const [sidebarMini, setSidebarMini] = useState(false);

	return (
		<div className="flex h-screen bg-gray-100">
			<Sidebar
				open={sidebarOpen}
				mini={sidebarMini}
				onClose={() => setSidebarOpen(false)}
			/>
			<div className="flex-1 flex flex-col overflow-y-auto">
				<TopHeader />
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

const AddCAMModal = lazy(() => import("./pages/CAM/AddCAM/AddCAMModal"));
const AddCAMGuarantorModal = lazy(() => import("./pages/CAM/AddCAM/AddCAMGuarantorModal"));

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
					{PROTECTED_ROUTE_ELEMENTS}
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
				<MemoryRouter>
					<AppRoutes />
				</MemoryRouter>
			</AuthProvider>
		</MaintenanceGate>
	);
}

export default App;