import "react-datepicker/dist/react-datepicker.css";
import { BrowserRouter, Routes, Route, Navigate, Outlet } from "react-router-dom";
import { lazy, Suspense } from "react";

// Auth & Core
import LoginPage from "./pages/LoginPage";
import Dashboard from "./pages/Dashboard";
import NotFound from "./pages/NotFound";

// Guards
import ProtectedRoute from "./components/ProtectedRoute";
import PublicRoute from "./components/PublicRoute";

// CAM
import AddCAM from "./pages/CAM/AddCAM";
import PrecheckingIndividuPage from "./pages/CAM/PrecheckingIndividuPage";
import PrecheckingCorporatePage from "./pages/CAM/PrecheckingCorporatePage";
import CAMForm from "./pages/CAM/CAMForm";
import CAMOnhandPage from "./pages/CAM/Onprocess/CAMOnhandPage";
import PrecheckingOnHandPage from "./pages/CAM/Prechecking/PrecheckingOnhandPage";
import PrecheckingRejectedPage from "./pages/CAM/Prechecking/PrecheckingRejectedPage";

// Master Data — Sales
import SalesPage from "./pages/MasterData/Sales/SalesPage";
import ListOfSalesPage from "./pages/MasterData/Sales/ListOfSalesPage";
import SalesEntryPage from "./pages/MasterData/Sales/SalesEntryPage";

// Master Data — Dealer/Supplier
import SupplierPage from "./pages/MasterData/Dealer/SupplierPage";
import ListOfSupplierPage from "./pages/MasterData/Dealer/ListOfSupplierPage";
import DealerDeletedReportPage from "./pages/MasterData/Dealer/DealerDeletedReportPage";

// Master Data — Collateral Object
import ModelEntryPage from "./pages/MasterData/CollateralObject/ModelEntryPage";
import KaroseriPage from "./pages/MasterData/CollateralObject/KaroseriPage";
import BrandPage from "./pages/MasterData/CollateralObject/Brand/BrandPage";
import BrandVehiclePage from "./pages/MasterData/CollateralObject/Brand/BrandVehiclePage";
import ListBrandPage from "./pages/MasterData/CollateralObject/ListBrandPage";
import ListModelPage from "./pages/MasterData/CollateralObject/ListModelPage";
import ListKaroseriPage from "./pages/MasterData/CollateralObject/ListKaroseriPage";

// Master Data — Group
import GroupPage from "./pages/MasterData/Group/GroupPage";
import GroupReportPage from "./pages/MasterData/Group//GroupReportPage";

// Master Data — Insurance
import InsurancePage from "./pages/MasterData/Insurance/InsurancePage";
import ListOfInsuranceReportPage from "./pages/MasterData/Insurance/ListOfInsuranceReportPage";

// Master Data — Watchlist
import WatchListEntryPage from "./pages/MasterData/watchlist/WatchListEntryPage";
import WatchListEditPage from "./pages/MasterData/watchlist/WatchListEditPage";

// Master Data — Blacklist
import BlackListEntryPage from "./pages/MasterData/Blacklist/BlackListEntryPage";

// Master Data — Industrial
import IndustrialCodePage from "./pages/MasterData/IndustryCode/IndustrialCodePage";

// Reports
import HistoryPaymentReportPage from "./pages/HistoryPayment/HistoryPaymentReportPage";
import AmortizationReportPage from "./pages/HistoryPayment/AmortizationReportPage";
import DetailAgingReportPage from "./pages/HistoryPayment/DetailAgingReportPage";
import JurnalFinancingPage from "./pages/Disbursement/JurnalFinancingPage";
import PrintHistoryPaymentPage from "./pages/HistoryPayment/PrintHistoryPaymentPage";
import SummaryAgingReportPage from "./pages/HistoryPayment/SummaryAgingReportPage";

// Admin / Settings
import MenuEntryPage from "./pages/Menu/MenuEntryPage";
import UserAccessPage from "./pages/Menu/UserAccessPage";
import UsersPage from "./pages/Menu/UsersPage";

// OJK
import Form10Page from "./pages/OJK/SILARAS/Form10Page";
import SLIKPage from "./pages/OJK/SLIKPage";
import SipesatPage from "./pages/OJK/SipesatPage";

// Insurance
import InsuranceEntryPage from "./pages/Insurance/InsuranceEntryPage";
import InsuranceReportPage from "./pages/Insurance/InsuranceReportPage";
import InvoiceRaksaPage from "./pages/Insurance/InvoiceRaksaPage";
import InvoiceSimasPage from "./pages/Insurance/InvoiceSimasPage";

// GPS & Payments
import InvoiceGPSPage from "./pages/GPS/InvoiceGPSPage";
import VAListPage from "./pages/ESPAY/VAListPage";

// Delima
import DelimaInvoicePage from "./pages/Delima/InvoicePage";
import FiduciaReportPage from "./pages/Delima/FiduciaReportPage";

// Employee
import EmployeeDataPage from "./pages/Employee/EmployeeDataPage";
import EmployeeMemoPage from "./pages/Employee/EmployeeMemoPage";

// CAM Context & Layout
import { CamProvider } from "./contexts/CamContext";
import CAMTabs from "./components/CAMTabs";
import Sidebar from "./components/Sidebar";

// Lazy-loaded CAM sub-pages
const CustomerDetail = lazy(() => import("./pages/Customer/CustomerDetail"));

const camRoutes = [
    { path: "/index", element: <AddCAM /> },
    { path: "/PrecheckingIndividuPage", element: <PrecheckingIndividuPage /> },
    { path: "/PrecheckingCorporatePage", element: <PrecheckingCorporatePage /> },
    { path: "/CAMForm", element: <CAMForm apless="" precheckingId="" lesseeTp="PR" /> },
    { path: "/CustomerDetail", element: <CustomerDetail /> },
    { path: "/cam-onhand", element: <CAMOnhandPage /> },
    { path: "/cam-request-onhand", element: <PrecheckingOnHandPage /> },
    { path: "/cam-request-rejected", element: <PrecheckingRejectedPage /> },
];

const ojkRoutes = [
    { path: "/form-10", element: <Form10Page /> },
    { path: "/slik", element: <SLIKPage /> },
    { path: "/sipesat", element: <SipesatPage /> },
];

const masterDataRoutes = [
    { path: "/sales", element: <SalesPage /> },
    { path: "/rpt-list-sales", element: <ListOfSalesPage /> },
    { path: "/sales-entry", element: <SalesEntryPage /> },
    { path: "/supplier", element: <SupplierPage /> },
    { path: "/rpt-list-supplier", element: <ListOfSupplierPage /> },
    { path: "/report-delete-dealer", element: <DealerDeletedReportPage /> },
    { path: "/model-entry", element: <ModelEntryPage /> },
    { path: "/karoseri-entry", element: <KaroseriPage /> },
    { path: "/brand-entry", element: <BrandPage /> },
    { path: "/brand-vehicle", element: <BrandVehiclePage /> },
    { path: "/rpt-list-vehicle", element: <ListBrandPage /> },
    { path: "/rpt-list-model", element: <ListModelPage /> },
    { path: "/rpt-list-karoseri", element: <ListKaroseriPage /> },
    { path: "/insurance", element: <InsurancePage /> },
    { path: "/rpt-list-insurance", element: <ListOfInsuranceReportPage /> },
    { path: "/group-entry", element: <GroupPage /> },
    { path: "/rpt-group", element: <GroupReportPage /> },
    { path: "/wlist-entry", element: <WatchListEntryPage /> },
    { path: "/wlist-edit", element: <WatchListEditPage /> },
    { path: "/blacklist-entry", element: <BlackListEntryPage /> },
    { path: "/industrial-code", element: <IndustrialCodePage /> },
];

const reportRoutes = [
    { path: "/rpt-his-pmt", element: <HistoryPaymentReportPage /> },
    { path: "/rpt-amortization", element: <AmortizationReportPage /> },
    { path: "/report-aging-detail", element: <DetailAgingReportPage /> },
    { path: "/rpt-jurnal-financing", element: <JurnalFinancingPage /> },
    { path: "/rpt-print-his-pmt", element: <PrintHistoryPaymentPage /> },
    { path: "/report-aging-summary", element: <SummaryAgingReportPage /> },
];

const invoiceRoutes = [
    { path: "/insurance-entry", element: <InsuranceEntryPage /> },
    { path: "/insurance-report", element: <InsuranceReportPage /> },
    { path: "/invoice-raksa", element: <InvoiceRaksaPage /> },
    { path: "/invoice-simas", element: <InvoiceSimasPage /> },
    { path: "/invoice-gps", element: <InvoiceGPSPage /> },
    { path: "/va-list", element: <VAListPage /> },
    { path: "/invoice", element: <DelimaInvoicePage /> },
    { path: "/report-list-fiducia", element: <FiduciaReportPage /> },
];

const adminRoutes = [
    { path: "/menu-entry", element: <MenuEntryPage /> },
    { path: "/uacc-entry", element: <UserAccessPage /> },
    { path: "/users", element: <UsersPage /> },
    { path: "/employee-data", element: <EmployeeDataPage /> },
    { path: "/memo-employee", element: <EmployeeMemoPage /> },
];

const protectedFlatRoutes = [
    ...camRoutes,
    ...ojkRoutes,
    ...masterDataRoutes,
    ...reportRoutes,
    ...invoiceRoutes,
    ...adminRoutes,
];

function AppLayout() {
    return (
        <div className="flex h-screen bg-gray-100">
            <Sidebar />
            <div className="flex-1 flex flex-col overflow-y-auto">
                <Outlet />
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
                            <Suspense fallback={<div className="p-6">Loading...</div>}>
                                <Outlet />
                            </Suspense>
                        </div>
                    </div>
                </div>
            </div>
        </CamProvider>
    );
}

function App() {
    return (
        <BrowserRouter>
            <Routes>
                {/* Public */}
                <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />
                <Route element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>

                    <Route path="/" element={<Dashboard />} />

                    {protectedFlatRoutes.map(({ path, element }) => (
                        <Route key={path} path={path} element={element} />
                    ))}

                    <Route path="/cam" element={<CAMLayout />}>
                        <Route path="customer/detail" element={<CustomerDetail />} />
                        <Route index element={<Navigate to="customer/detail" replace />} />
                        <Route path="*" element={<Navigate to="customer/detail" replace />} />
                    </Route>

                    {/* Catch-all: any unknown URL renders NotFound inside AppLayout */}
                    <Route path="*" element={<NotFound />} />

                </Route>
            </Routes>
        </BrowserRouter>
    );
}

export default App;