import React, { useEffect, useMemo, useState } from 'react';
import CustomerDetailView from './CustomerDetailView';
import FinancialInfoView from './FinancialInfoView';
import BusinessHistoryView from './BusinessHistoryView';
import CustomerSurveyFileView from './CustomerSurveyFileView';
import EquipmentView from './EquipmentView';
import EquipmentSurveyFileView from './EquipmentSurveyFileView';
import FinancingView from './FinancingView';
import DeviationView from './DeviationView';
import SurveyView from './SurveyView';
import { CamNotesView, OtherNotesView } from './NotesView';
import ApuPptView from './ApuPptView';
import HistoryPaymentView from './HistoryPaymentView';
import AllFilesView from './AllFilesView';
import ApprovalView from './ApprovalView';
import ReportCamView from './ReportCamView';

export interface CamCtx {
	finType: string;
	indCor: string;
	repeat: string;
	guarantor: string;
	newCar: string;
	status: string;
	purpoffinc: string;
	c2c: string;
	contType: string;
	apless: string;
	applno: string;
}

type ViewKey =
	| 'customer_detail'
	| 'corp_detail'
	| 'guarantor'
	| 'financial_info'
	| 'business_history'
	| 'business_profile'
	| 'survey_file_customer'
	| 'equipment'
	| 'used_car_checklist'
	| 'survey_file_equipment'
	| 'financing'
	| 'deviation'
	| 'survey'
	| 'notes'
	| 'other_notes'
	| 'apu_ppt'
	| 'history_payment'
	| 'report_cam'
	| 'all_files'
	| 'approval';

interface SubmenuItem {
	key: string;
	label: string;
	view: ViewKey;
}

const TOP_MENU: { key: number; label: string }[] = [
	{ key: 1, label: 'Customer' },
	{ key: 2, label: 'Equipment' },
	{ key: 3, label: 'Financing' },
	{ key: 4, label: 'Deviation' },
	{ key: 5, label: 'Survey' },
	{ key: 6, label: 'Other' },
	{ key: 7, label: 'History Payment' },
	{ key: 8, label: 'Report CAM' },
	{ key: 9, label: 'All Files' },
	{ key: 10, label: 'Approval' },
];

function getSubmenu(menu: number, ctx: CamCtx): SubmenuItem[] {
	switch (menu) {
		case 1: {
			const items: SubmenuItem[] = [
				ctx.indCor === '2'
					? { key: 'detail', label: 'Detail', view: 'corp_detail' }
					: { key: 'detail', label: 'Detail', view: 'customer_detail' },
			];
			if (ctx.guarantor === '2') {
				items.push({ key: 'guarantor', label: 'Guarantor', view: 'guarantor' });
			}
			items.push({ key: 'finance', label: 'Financial Information', view: 'financial_info' });
			items.push(
				ctx.indCor === '2'
					? { key: 'history', label: 'Business Profile', view: 'business_profile' }
					: { key: 'history', label: 'Business/ Job History', view: 'business_history' }
			);
			items.push({ key: 'survey', label: 'Survey File', view: 'survey_file_customer' });
			return items;
		}
		case 2: {
			const items: SubmenuItem[] = [{ key: 'equipment', label: 'Equipment', view: 'equipment' }];
			if (ctx.newCar === '1') {
				items.push({ key: 'usedcar', label: 'Used Car Checklist', view: 'used_car_checklist' });
			}
			items.push({ key: 'survey', label: 'Survey File', view: 'survey_file_equipment' });
			return items;
		}
		case 3:
			return [{ key: 'financing', label: 'Financing', view: 'financing' }];
		case 4:
			return [{ key: 'deviation', label: 'Deviation', view: 'deviation' }];
		case 5:
			return [{ key: 'survey', label: 'Survey', view: 'survey' }];
		case 6:
			return [
				{ key: 'notes', label: 'Notes', view: 'notes' },
				{ key: 'other_notes', label: 'Other Notes', view: 'other_notes' },
				{ key: 'apu_ppt', label: 'APU PPT', view: 'apu_ppt' },
			];
		case 7:
			return [{ key: 'history_payment', label: 'History Payment', view: 'history_payment' }];
		case 8:
			return [{ key: 'report', label: 'Report CAM', view: 'report_cam' }];
		case 9:
			return [{ key: 'files', label: 'All Files', view: 'all_files' }];
		case 10:
			return [{ key: 'approval', label: 'Approval', view: 'approval' }];
		default:
			return [];
	}
}

const IMPLEMENTED_VIEWS: Partial<Record<ViewKey, React.FC<{ ctx: CamCtx }>>> = {
	customer_detail: CustomerDetailView,
	financial_info: FinancialInfoView,
	business_history: BusinessHistoryView,
	survey_file_customer: CustomerSurveyFileView,
	equipment: EquipmentView,
	survey_file_equipment: EquipmentSurveyFileView,
	financing: FinancingView,
	deviation: DeviationView,
	survey: SurveyView,
	notes: CamNotesView,
	other_notes: OtherNotesView,
	apu_ppt: ApuPptView,
	history_payment: HistoryPaymentView,
	all_files: AllFilesView,
	approval: ApprovalView,
	report_cam: ReportCamView,
};

function readCtxFromUrl(): CamCtx {
	const params = new URLSearchParams(window.location.search);
	return {
		finType: params.get('id1') || '',
		indCor: params.get('id2') || '',
		repeat: params.get('id3') || '',
		guarantor: params.get('id4') || '',
		newCar: params.get('id5') || '',
		status: params.get('id6') || '',
		purpoffinc: params.get('id7') || '',
		c2c: params.get('id8') || '',
		contType: params.get('id9') || '',
		apless: params.get('apless') || '',
		applno: params.get('applno') || '',
	};
}

export interface CamViewTabsProps {
	ctx?: CamCtx;
	initialMenu?: number;
	initialSubmenu?: number;
	onHome?: () => void;
}

export default function CamViewTabs({ ctx: ctxProp, initialMenu, initialSubmenu, onHome }: CamViewTabsProps = {}) {
	const embedded = ctxProp !== undefined;
	const [ctx] = useState<CamCtx>(() => ctxProp ?? readCtxFromUrl());
	const [menu, setMenu] = useState<number>(() => {
		if (initialMenu) return initialMenu;
		const params = new URLSearchParams(window.location.search);
		return Number(params.get('menu')) || 1;
	});
	const [submenuIndex, setSubmenuIndex] = useState<number>(() => {
		if (initialSubmenu) return initialSubmenu;
		const params = new URLSearchParams(window.location.search);
		return Number(params.get('submenu')) || 1;
	});

	const submenuItems = useMemo(() => getSubmenu(menu, ctx), [menu, ctx]);

	useEffect(() => {
		if (submenuIndex < 1 || submenuIndex > submenuItems.length) {
			setSubmenuIndex(1);
		}
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [menu]);

	useEffect(() => {
		if (embedded) return;
		const params = new URLSearchParams(window.location.search);
		params.set('menu', String(menu));
		params.set('submenu', String(submenuIndex));
		window.history.replaceState(null, '', `${window.location.pathname}?${params.toString()}`);
	}, [embedded, menu, submenuIndex]);

	const activeSubmenu = submenuItems[submenuIndex - 1];
	const ActiveComponent = activeSubmenu ? IMPLEMENTED_VIEWS[activeSubmenu.view] : undefined;

	const goHome = () => {
		if (onHome) {
			onHome();
		} else {
			window.location.href = '/cam_onhand';
		}
	};

	return (
		<div className={`bg-slate-100 p-6 ${embedded ? '' : 'min-h-screen'}`}>
			<div className={embedded ? 'w-full' : 'mx-auto max-w-6xl'}>
				<div className="mb-4 flex items-center justify-between rounded-2xl bg-gradient-to-r from-blue-600 to-blue-700 px-6 py-4 text-white shadow">
					<div>
						<h1 className="text-lg font-semibold">CAM Review</h1>
						<p className="text-sm text-blue-100">
							APLESS {ctx.apless || '-'} &middot; Application {ctx.applno || '-'}
						</p>
					</div>
					<button
						type="button"
						onClick={goHome}
						aria-label="Close"
						className="rounded-lg bg-white/10 px-3 py-1.5 text-sm font-medium transition hover:bg-white/20"
					>
						{embedded ? '✕ Close' : 'Home'}
					</button>
				</div>

				<div className="mb-3 flex flex-wrap gap-1 rounded-2xl bg-white p-2 shadow">
					{TOP_MENU.map((item) => (
						<button
							key={item.key}
							type="button"
							onClick={() => setMenu(item.key)}
							className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${menu === item.key ? 'bg-blue-600 text-white' : 'text-slate-600 hover:bg-slate-100'
								}`}
						>
							{item.label}
						</button>
					))}
				</div>

				<div className="mb-4 flex flex-wrap gap-1 rounded-2xl bg-white p-2 shadow">
					{submenuItems.map((item, idx) => (
						<button
							key={item.key}
							type="button"
							onClick={() => setSubmenuIndex(idx + 1)}
							className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${submenuIndex === idx + 1 ? 'bg-orange-500 text-white' : 'text-slate-600 hover:bg-slate-100'
								}`}
						>
							{item.label}
						</button>
					))}
				</div>

				<div>
					{ActiveComponent ? (
						<ActiveComponent ctx={ctx} />
					) : (
						<div className="rounded-2xl bg-white p-8 text-center shadow">
							<p className="text-base font-medium text-slate-700">
								{activeSubmenu?.label || 'This tab'} hasn&apos;t been migrated yet
							</p>
							<p className="mt-1 text-sm text-slate-500">
								The legacy source for this tab wasn&apos;t part of this conversion, so there&apos;s nothing to
								render here yet.
							</p>
						</div>
					)}
				</div>
			</div>
		</div>
	);
}