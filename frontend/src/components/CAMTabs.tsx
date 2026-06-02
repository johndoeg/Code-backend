import { useState, useEffect } from 'react';
import { useNavigate, useParams, useLocation } from 'react-router-dom';
import { useCamContext } from '../contexts/CamContext';

interface Tab {
    id: string;
    label: string;
    path: string;
}

interface SubTab {
    id: string;
    label: string;
    path: string;
}

export default function CAMTabs() {
    const context = useCamContext();
    const navigate = useNavigate();
    const location = useLocation();
    const params = useParams();

    // Main tabs
    const mainTabs: Tab[] = [
        { id: 'customer', label: 'Customer', path: '/cam/customer/detail' },
        { id: 'equipment', label: 'Equipment', path: '/cam/equipment' },
        { id: 'financing', label: 'Financing', path: '/cam/financing' },
        { id: 'deviation', label: 'Deviation', path: '/cam/deviation' },
        { id: 'survey', label: 'Survey', path: '/cam/survey' },
        { id: 'apu-ppt', label: 'APU PPT', path: '/cam/apu-ppt' },
        { id: 'other', label: 'Other', path: '/cam/other' },
        { id: 'history-payment', label: 'History Payment', path: '/cam/history-payment' },
        { id: 'report-cam', label: 'Report CAM', path: '/cam/report-cam' },
        { id: 'all-files', label: 'All Files', path: '/cam/all-files' },
        { id: 'approval', label: 'Approval', path: '/cam/approval' }
    ];

    // Sub-tabs based on main tab
    const getSubTabs = (mainTabId: string): SubTab[] => {
        switch (mainTabId) {
            case 'customer':
                return [
                    { id: 'detail', label: 'Detail', path: '/cam/customer/detail' },
                    { id: 'financial-info', label: 'Financial Information', path: '/cam/customer/financial-info' },
                    { id: 'business-history', label: 'Business/ Job History', path: '/cam/customer/business-history' },
                    { id: 'survey-file', label: 'Survey File', path: '/cam/customer/survey-file' }
                ];
            case 'equipment':
                return [
                    { id: 'equipment', label: 'Equipment', path: '/cam/equipment' },
                    { id: 'bpkb', label: 'BPKB', path: '/cam/equipment/bpkb' },
                    { id: 'ctoc', label: 'C to C', path: '/cam/equipment/ctoc' },
                    { id: 'survey', label: 'Survey File', path: '/cam/equipment/survey' },
                    { id: 'cross', label: 'Cross Collateral', path: '/cam/equipment/cross' }
                ];
            case 'financing':
                return [
                    { id: 'financing', label: 'Financing', path: '/cam/financing' },
                    { id: 'insurance', label: 'Insurance', path: '/cam/financing/insurance' },
                    { id: 'commission', label: 'Commission', path: '/cam/financing/commission' },
                    { id: 'disbursement', label: 'Disbursement', path: '/cam/financing/disbursement' },
                    { id: 'outstanding', label: 'Outstanding', path: '/cam/financing/outstanding' }
                ];
            case 'survey':
                return [
                    { id: 'survey', label: 'Survey', path: '/cam/survey' }
                ];
            case 'apu-ppt':
                return [
                    { id: 'apu-ppt', label: 'APU PPT', path: '/cam/apu-ppt' }
                ];
            case 'other':
                return [
                    { id: 'cam-notes', label: 'CAM Notes', path: '/cam/other/cam-notes' },
                    { id: 'customer-notes', label: 'Customer Notes', path: '/cam/other/customer-notes' },
                    { id: 'revision-notes', label: 'Revision Notes', path: '/cam/other/revision-notes' }
                ];
            default:
                return [];
        }
    };

    // Determine active main tab
    const [activeMainTab, setActiveMainTab] = useState<string>('');
    const [activeSubTab, setActiveSubTab] = useState<string>('');

    useEffect(() => {
        // Determine active tab based on current URL
        const path = location.pathname;

        // Find active main tab
        const mainTab = mainTabs.find(tab => path.startsWith(tab.path));
        if (mainTab) {
            setActiveMainTab(mainTab.id);

            // Find active sub-tab
            const subTabs = getSubTabs(mainTab.id);
            const subTab = subTabs.find(tab => path === tab.path || path.startsWith(`${tab.path}/`));
            if (subTab) {
                setActiveSubTab(subTab.id);
            } else {
                setActiveSubTab(subTabs[0]?.id || '');
            }
        }
    }, [location.pathname]);

    const handleMainTabClick = (tabId: string) => {
        const tab = mainTabs.find(t => t.id === tabId);
        if (tab) {
            navigate(tab.path);
        }
    };

    const handleSubTabClick = (subTabId: string) => {
        const subTabs = getSubTabs(activeMainTab);
        const subTab = subTabs.find(t => t.id === subTabId);
        if (subTab) {
            navigate(subTab.path);
        }
    };

    const subTabs = getSubTabs(activeMainTab);

    return (
        <div className="bg-white border-b">
            {/* Main Tabs */}
            <div className="flex bg-gray-100 p-2">
                {mainTabs.map((tab) => (
                    <button
                        key={tab.id}
                        onClick={() => handleMainTabClick(tab.id)}
                        className={`px-4 py-2 font-medium text-sm ${activeMainTab === tab.id
                                ? 'bg-orange-500 text-white'
                                : 'text-gray-700 hover:bg-gray-200'
                            }`}
                    >
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* Sub Tabs */}
            {subTabs.length > 0 && (
                <div className="bg-blue-800 text-white p-2">
                    {subTabs.map((subTab) => (
                        <button
                            key={subTab.id}
                            onClick={() => handleSubTabClick(subTab.id)}
                            className={`px-4 py-2 font-medium text-sm ${activeSubTab === subTab.id
                                    ? 'bg-blue-600 text-white'
                                    : 'text-white hover:bg-blue-700'
                                }`}
                        >
                            {subTab.label}
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}