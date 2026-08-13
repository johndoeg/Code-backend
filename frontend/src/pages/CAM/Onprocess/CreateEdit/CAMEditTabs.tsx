import React, { useEffect, useMemo, useState } from 'react';

import CAMCustomerDetailPage from './Customer/CAMCustomerDetailPage';
import CAMCustomerAddressPage from './Customer/CAMCustomerAddressPage';
import CAMFinancialInfoPage from './Customer/CAMFinancialInfoPage';
import CAMBusinessHistoryPage from './Customer/CAMBusinessHistoryPage';
import CAMSurveyFilePage from './Customer/CAMSurveyFilePage';
import CAMCustomerDocument from './Customer/CAMCustomerDocumentPage';
import CAMReferencesPage from './Customer/CAMReferencesPage';

import CAMEquipmentDetailPage from './Equipment/CAMEquipmentDetailPage';
import CAMEquipmentBpkbPage from './Equipment/CAMEquipmentBpkbPage';
import CAMEquipmentSurveyFilePage from './Equipment/CAMEquipmentSurveyFilePage';
import CAMCrossCollateralPage from './Equipment/CAMCrossCollateralPage';

import CAMFinancingPage from './Financing/CAMFinancingPage';
import CAMFinancingInsurancePage from './Financing/CAMFinancingInsurancePage';
import CAMFinancingDisbursementPage from './Financing/CAMFinancingDisbursementPage';
import CAMFinancingOutstandingPage from './Financing/CAMFinancingOutstandingPage';
import CAMFinancingCommissionPage from './Financing/CAMFinancingCommissionCamPage.tsx';
import CAMFinancingCommissionCamPage from './Financing/CAMFinancingCommissionCamPage.tsx';

import CAMSurveyPage from './Survey/CAMSurveyPage';

import CAMAPUPPTPage from './APUPPT/CAMAPUPPTPage';

import CAMNotesPage from './Other/CAMNotesPage';
import CAMCustomerNotesPage from './Other/CAMCustomerNotesPage';
import CAMRevisionNotesPage from './Other/CAMRevisionNotesPage';

export interface CamMenuCtx {
	finType: string;
	indCor: string;
	guarantor: string;
	newCar: string;
	status: string;
	c2c: string;
	boa: string;
	bot: string;
	akseskhusus?: boolean;
}

export interface CamSubmenuItem {
	key: number;
	label: string;
	page: string;
}

export interface CamMenuItem {
	key: number;
	label: string;
	submenus: CamSubmenuItem[];
}

export function buildCamMenu(ctx: CamMenuCtx): CamMenuItem[] {
	const { finType, indCor, guarantor, newCar, c2c, boa, bot, akseskhusus } = ctx;

	const hasBo = boa === "2";
	const equipmentIsSpecial = finType === "S";

	const equipmentLabel = equipmentIsSpecial ? "Financing Object" : "Equipment";
	const bpkbLabel = equipmentIsSpecial ? "Financing Object BPKB" : "BPKB";

	const equipmentSubmenus: CamSubmenuItem[] = c2c === "1"
		? [
			{ key: 1, label: equipmentLabel, page: "eq_equipment" },
			{ key: 2, label: bpkbLabel, page: "eq_bpkb" },
			{ key: 3, label: "C to C", page: "eq_ctoc" },
			{ key: 4, label: "Survey File", page: "eq_survey_file" },
		]
		: [
			{ key: 1, label: equipmentLabel, page: "eq_equipment" },
			{ key: 2, label: bpkbLabel, page: "eq_bpkb" },
			{ key: 3, label: "Survey File", page: "eq_survey_file" },
			{ key: 4, label: "Cross Collateral", page: "eq_cross" },
		];

	const financingSubmenus: CamSubmenuItem[] = [
		{ key: 1, label: "Financing", page: "fin_financing" },
		{ key: 2, label: "Insurance", page: "insurance" },
		akseskhusus
			? { key: 3, label: "Commission", page: "fin_commission_cam" }
			: { key: 3, label: "Commission (Detail)", page: "fin_commission" },
		{ key: 4, label: "Disbursement", page: "fin_disbursement" },
		{ key: 5, label: "Outstanding", page: "fin_outstanding" },
	];

	const custDetailPage = indCor === "1" ? "cust_detail" : "corp_detail";
	const custAddressPage = indCor === "1" ? "cust_address" : "corp_address";
	const custBusinessLabel = indCor === "1" ? "Business/ Job History" : "Business Profile";
	const custBusinessPage = indCor === "1" ? "cust_business_history" : "corp_business_profile";

	const customerSubmenus: CamSubmenuItem[] = guarantor === "2"
		? [
			{ key: 1, label: "Detail", page: custDetailPage },
			{ key: 2, label: "Address", page: custAddressPage },
			{ key: 3, label: "Guarantor", page: "cust_guarantor" },
			{ key: 4, label: "Financial Information", page: "cust_finance_info" },
			{ key: 5, label: custBusinessLabel, page: custBusinessPage },
			{ key: 6, label: "Survey File", page: "cust_survey_file" },
			{ key: 7, label: "Customer's Document", page: "cust_document" },
			{ key: 8, label: "References", page: "cust_references" },
		]
		: [
			{ key: 1, label: "Detail", page: custDetailPage },
			{ key: 2, label: "Address", page: custAddressPage },
			{ key: 3, label: "Financial Information", page: "cust_finance_info" },
			{ key: 4, label: custBusinessLabel, page: custBusinessPage },
			{ key: 5, label: "Survey File", page: "cust_survey_file" },
			{ key: 6, label: "Customer's Document", page: "cust_document" },
			{ key: 7, label: "References", page: "cust_references" },
		];

	const beneficialOwnerSubmenus: CamSubmenuItem[] = [
		{ key: 1, label: "Detail", page: bot === "1" ? "ind_beneficial_detail" : "corp_beneficial_detail" },
	];

	const surveySubmenus: CamSubmenuItem[] = [{ key: 1, label: "Survey", page: "survey" }];
	const apuPptSubmenus: CamSubmenuItem[] = [{ key: 1, label: "APU PPT", page: "edit_apu_ppt" }];
	const otherSubmenus: CamSubmenuItem[] = [
		{ key: 1, label: "CAM Notes", page: "cam_notes" },
		{ key: 2, label: "Customer Notes", page: "other_notes" },
		{ key: 3, label: "Revision Notes", page: "revision_notes" },
	];

	if (!hasBo) {
		return [
			{ key: 1, label: "Customer", submenus: customerSubmenus },
			{ key: 2, label: "Equipment", submenus: equipmentSubmenus },
			{ key: 3, label: "Financing", submenus: financingSubmenus },
			{ key: 4, label: "Survey", submenus: surveySubmenus },
			{ key: 5, label: "APU PPT", submenus: apuPptSubmenus },
			{ key: 6, label: "Other", submenus: otherSubmenus },
		];
	}

	return [
		{ key: 1, label: "Customer", submenus: customerSubmenus },
		{ key: 2, label: "Beneficial Owner", submenus: beneficialOwnerSubmenus },
		{ key: 3, label: "Equipment", submenus: equipmentSubmenus },
		{ key: 4, label: "Financing", submenus: financingSubmenus },
		{ key: 5, label: "Survey", submenus: surveySubmenus },
		{ key: 6, label: "APU PPT", submenus: apuPptSubmenus },
		{ key: 7, label: "Other", submenus: otherSubmenus },
	];
}

export function findMenuPositionByPage(menu: CamMenuItem[], page: string): { menu: number; submenu: number } | null {
	for (const m of menu) {
		for (const s of m.submenus) {
			if (s.page === page) return { menu: m.key, submenu: s.key };
		}
	}
	return null;
}

export function flattenCamMenu(menu: CamMenuItem[]): { menu: number; submenu: number; page: string }[] {
	const flat: { menu: number; submenu: number; page: string }[] = [];
	for (const m of menu) {
		for (const s of m.submenus) {
			flat.push({ menu: m.key, submenu: s.key, page: s.page });
		}
	}
	return flat;
}

export function getAdjacentMenuPosition(
	menu: CamMenuItem[],
	currentMenu: number,
	currentSubmenu: number,
	direction: 1 | -1
): { menu: number; submenu: number } | null {
	const flat = flattenCamMenu(menu);
	const idx = flat.findIndex(f => f.menu === currentMenu && f.submenu === currentSubmenu);
	if (idx === -1) return null;
	const targetIdx = idx + direction;
	if (targetIdx < 0 || targetIdx >= flat.length) return null;
	return { menu: flat[targetIdx].menu, submenu: flat[targetIdx].submenu };
}

export interface CamEditCtx extends CamMenuCtx {
	purpoffinc: string;
	contType: string;
	apless: string;
	applno: string;
	repeat?: string;
	restructuringChange?: string;
	goPublic?: string;
}

type EditComponent = React.FC<{
	ctx: CamEditCtx;
	onSaved: (result: { apless: string; applno: string }) => void;
}>;

const IMPLEMENTED_EDIT_PAGES: Partial<Record<string, EditComponent>> = {
	'cust_detail': ({ ctx, onSaved }) => (
		<CAMCustomerDetailPage
			apless={ctx.apless}
			applNo={ctx.applno}
			finType={ctx.finType}
			guarantor={ctx.guarantor}
			newCar={ctx.newCar}
			purpoffinc={ctx.purpoffinc}
			contType={ctx.contType}
			restructuringChange={ctx.restructuringChange || ''}
			onSaved={onSaved}
		/>
	),
	'cust_address': ({ ctx, onSaved }) => (
		<CAMCustomerAddressPage apless={ctx.apless} applNo={ctx.applno} onSaved={onSaved} />
	),
	'corp_address': ({ ctx, onSaved }) => (
		<CAMCustomerAddressPage apless={ctx.apless} applNo={ctx.applno} onSaved={onSaved} />
	),
	'cust_finance_info': ({ ctx, onSaved }) => (
		<CAMFinancialInfoPage apless={ctx.apless} applNo={ctx.applno} indCor={ctx.indCor} onSaved={onSaved} />
	),
	'cust_business_history': ({ ctx, onSaved }) => (
		<CAMBusinessHistoryPage apless={ctx.apless} applNo={ctx.applno} onSaved={onSaved} />
	),
	'cust_survey_file': ({ ctx, onSaved }) => (
		<CAMSurveyFilePage apless={ctx.apless} applNo={ctx.applno} status={ctx.status} onSaved={onSaved} />
	),
	'cust_document': ({ ctx, onSaved }) => (
		<CAMCustomerDocument apless={ctx.apless} applNo={ctx.applno} indCor={ctx.indCor} onSaved={onSaved} />
	),
	'cust_references': ({ ctx, onSaved }) => (
		<CAMReferencesPage apless={ctx.apless} applNo={ctx.applno} onSaved={onSaved} />
	),
	'eq_equipment': ({ ctx, onSaved }) => (
		<CAMEquipmentDetailPage
			apless={ctx.apless}
			applNo={ctx.applno}
			finType={ctx.finType}
			purpoffinc={ctx.purpoffinc}
			newCar={ctx.newCar}
			onSaved={onSaved}
		/>
	),
	'eq_bpkb': ({ ctx, onSaved }) => (
		<CAMEquipmentBpkbPage
			apless={ctx.apless}
			applNo={ctx.applno}
			finType={ctx.finType}
			newCar={ctx.newCar}
			onSaved={onSaved}
		/>
	),
	'eq_survey_file': ({ ctx, onSaved }) => (
		<CAMEquipmentSurveyFilePage
			apless={ctx.apless}
			applNo={ctx.applno}
			status={ctx.status}
			onSaved={onSaved}
		/>
	),
	'eq_cross': ({ ctx, onSaved }) => (
		<CAMCrossCollateralPage
			apless={ctx.apless}
			applNo={ctx.applno}
			onSaved={onSaved} />
	),
	'fin_financing': ({ ctx, onSaved }) => (
		<CAMFinancingPage
			apless={ctx.apless}
			applNo={ctx.applno}
			finType={ctx.finType}
			purpoffinc={ctx.purpoffinc}
			contType={ctx.contType}
			newCar={ctx.newCar}
			onSaved={onSaved}
		/>
	),
	'insurance': ({ ctx, onSaved }) => (
		<CAMFinancingInsurancePage
			apless={ctx.apless}
			applNo={ctx.applno}
			finType={ctx.finType}
			onSaved={onSaved}
		/>
	),
	'fin_commission': ({ ctx, onSaved }) => (
		<CAMFinancingCommissionPage
			apless={ctx.apless}
			applNo={ctx.applno}
			onSaved={onSaved}
		/>
	),
	'fin_commission_cam': ({ ctx, onSaved }) => (
		<CAMFinancingCommissionCamPage
			apless={ctx.apless}
			applNo={ctx.applno}
			contType={ctx.contType}
			onSaved={onSaved}
		/>
	),
	'fin_disbursement': ({ ctx, onSaved }) => (
		<CAMFinancingDisbursementPage
			apless={ctx.apless}
			applNo={ctx.applno}
			finType={ctx.finType}
			contType={ctx.contType}
			onSaved={onSaved}
		/>
	),
	'fin_outstanding': ({ ctx, onSaved }) => (
		<CAMFinancingOutstandingPage
			apless={ctx.apless}
			applNo={ctx.applno}
			onSaved={onSaved}
		/>
	),
	'survey': ({ ctx, onSaved }) => (
		<CAMSurveyPage
			apless={ctx.apless}
			applNo={ctx.applno}
			indCor={ctx.indCor === '2' ? '2' : '1'}
			onSaved={onSaved}
		/>
	),
	'edit_apu_ppt': ({ ctx, onSaved }) => (
		<CAMAPUPPTPage
			apless={ctx.apless}
			applNo={ctx.applno}
			onSaved={onSaved}
		/>
	),
	'cam_notes': ({ ctx, onSaved }) => (
		<CAMNotesPage
			apless={ctx.apless}
			applNo={ctx.applno}
			onSaved={onSaved}
		/>
	),
	'other_notes': ({ ctx, onSaved }) => (
		<CAMCustomerNotesPage
			apless={ctx.apless}
			applNo={ctx.applno}
			onSaved={onSaved}
		/>
	),
	'revision_notes': ({ ctx, onSaved }) => (
		<CAMRevisionNotesPage
			apless={ctx.apless}
			applNo={ctx.applno}
			onSaved={onSaved}
		/>
	),
};
export interface CamEditTabsProps {
	ctx: CamEditCtx;
	initialMenu?: number;
	initialSubmenu?: number;
	onHome?: () => void;
}

export default function CamEditTabs({ ctx: ctxProp, initialMenu, initialSubmenu, onHome }: CamEditTabsProps) {
	const [ctx, setCtx] = useState<CamEditCtx>(ctxProp);
	const [menu, setMenu] = useState<number>(initialMenu || 1);
	const [submenuIndex, setSubmenuIndex] = useState<number>(initialSubmenu || 1);

	const menuTree = useMemo(
		() =>
			buildCamMenu({
				finType: ctx.finType,
				indCor: ctx.indCor,
				guarantor: ctx.guarantor,
				newCar: ctx.newCar,
				status: ctx.status,
				c2c: ctx.c2c,
				boa: ctx.boa || '1',
				bot: ctx.bot || '',
				akseskhusus: ctx.akseskhusus,
			}),
		[ctx.finType, ctx.indCor, ctx.guarantor, ctx.newCar, ctx.status, ctx.c2c, ctx.boa, ctx.bot, ctx.akseskhusus]
	);

	const activeTopMenu = menuTree.find(m => m.key === menu) ?? menuTree[0];
	const submenuItems = activeTopMenu?.submenus ?? [];

	useEffect(() => {
		if (submenuIndex < 1 || submenuIndex > submenuItems.length) {
			setSubmenuIndex(1);
		}
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [menu]);

	const activeSubmenu = submenuItems[submenuIndex - 1];
	const ActiveComponent = activeSubmenu ? IMPLEMENTED_EDIT_PAGES[activeSubmenu.page] : undefined;

	const handleSaved = ({ apless, applno }: { apless: string; applno: string }) => {
		setCtx(prev => ({ ...prev, apless, applno }));
		if (submenuIndex < submenuItems.length) {
			setSubmenuIndex(submenuIndex + 1);
		} else {
			const menuIdx = menuTree.findIndex(m => m.key === menu);
			const nextMenu = menuTree[menuIdx + 1];
			if (nextMenu) {
				setMenu(nextMenu.key);
				setSubmenuIndex(1);
			}
		}
	};

	const prevPosition = useMemo(
		() => getAdjacentMenuPosition(menuTree, menu, submenuIndex, -1),
		[menuTree, menu, submenuIndex]
	);
	const nextPosition = useMemo(
		() => getAdjacentMenuPosition(menuTree, menu, submenuIndex, 1),
		[menuTree, menu, submenuIndex]
	);

	const goTo = (pos: { menu: number; submenu: number } | null) => {
		if (!pos) return;
		setMenu(pos.menu);
		setSubmenuIndex(pos.submenu);
	};

	return (
		<div className="fixed inset-0 z-50 w-screen h-screen overflow-y-auto bg-slate-100 p-6">
			<div className="w-full">
				<div className="mb-4 flex items-center justify-between rounded-2xl bg-gradient-to-r from-orange-500 to-orange-600 px-6 py-4 text-white shadow">

					<div>
						<h1 className="text-lg font-semibold">CAM Edit</h1>
						<p className="text-sm text-orange-100">
							APLESS {ctx.apless || '-'} &middot; Application {ctx.applno || '-'}
						</p>
					</div>
					<button
						type="button"
						onClick={() => onHome?.()}
						aria-label="Close"
						className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-red-900"
					>
						✕ Close
					</button>
				</div>

				<div className="mb-3 flex flex-wrap gap-1 rounded-2xl bg-white p-2 shadow">
					{menuTree.map(item => (
						<button
							key={item.key}
							type="button"
							onClick={() => { setMenu(item.key); setSubmenuIndex(1); }}
							className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${menu === item.key ? 'bg-orange-500 text-white' : 'text-slate-600 hover:bg-slate-100'
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
							className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${submenuIndex === idx + 1 ? 'bg-blue-600 text-white' : 'text-slate-600 hover:bg-slate-100'
								}`}
						>
							{item.label}
						</button>
					))}
				</div>

				<div>
					{ActiveComponent ? (
						<ActiveComponent ctx={ctx} onSaved={handleSaved} />
					) : (
						<div className="rounded-2xl bg-white p-8 text-center shadow">
							<p className="text-base font-medium text-slate-700">
								{activeSubmenu?.label || 'This tab'} hasn&apos;t been migrated yet
							</p>
							<p className="mt-1 text-sm text-slate-500">
								No editable component has been wired up for this tab yet.
							</p>
						</div>
					)}
				</div>

				<div className="mt-4 rounded-2xl bg-white p-3 shadow">
					<div className="grid grid-cols-2 gap-3">
						<div className="mt-4 grid grid-cols-2 gap-3">
							<div>
								{prevPosition && (
									<button
										type="button"
										onClick={() => goTo(prevPosition)}
										className="flex items-center gap-1 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-red-700"
									>
										<span aria-hidden>‹</span> Prev
									</button>
								)}
							</div>

							<div className="flex justify-end">
								{!ActiveComponent && nextPosition && (
									<button
										type="button"
										onClick={() => goTo(nextPosition)}
										className="flex items-center gap-1 rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-green-700"
									>
										Next <span aria-hidden>›</span>
									</button>
								)}
							</div>
						</div>
					</div>
				</div>

			</div>
		</div>
	);
}