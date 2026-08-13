import React, { useEffect, useState } from 'react';
import api from '../../../../../api/axiosInstance';
import type { CamCtx } from '../CamViewTabs';

interface LiabilityRow {
	category: string;
	description: string;
	amount: number;
}

interface IncomeItem {
	label: string;
	amount: number;
}

interface AssetRow {
	description: string;
	amount: number;
	notes: string;
}

interface IndividualFinance {
	no_data: boolean;
	period_label?: string;
	currency?: string;
	liabilities?: { rows: LiabilityRow[]; total: number };
	income?: {
		income_items: IncomeItem[];
		total_income: number;
		expense_items: IncomeItem[];
		liabilities_total: number;
		net_saving: number;
	};
	dscr?: string;
	assets?: { rows: AssetRow[]; total: number };
}

interface BalanceSheetRow {
	label: string;
	amount_a: number;
	amount_b: number;
}

interface BalanceSheetSection {
	header: string;
	rows: BalanceSheetRow[];
	subtotal_a: number;
	subtotal_b: number;
	show_subtotal: boolean;
}

interface ProfitLossRow {
	fs_code: string;
	label: string;
	amount: number;
	bold: boolean;
	section_header: boolean;
}

interface CorporateFinance {
	no_data: boolean;
	balance_sheet?: {
		period_label_1: string;
		period_label_2: string;
		asset_sections: BalanceSheetSection[];
		asset_total1: number;
		asset_total2: number;
		liability_sections: BalanceSheetSection[];
		liability_total1: number;
		liability_total2: number;
	};
	profit_loss?: { period_label: string; rows: ProfitLossRow[] };
	dscr?: string;
}

interface BankStatementRow {
	period_label: string;
	beginning_balance: number;
	debet: number;
	credit: number;
	ending_balance: number;
	notes: string;
}

interface BankAccount {
	bank_name: string;
	branch: string;
	account_no: string;
	account_name: string;
	currency: string;
	notes: string;
	statements: BankStatementRow[];
}

interface BankFile {
	id: number;
	name: string;
	download_url: string | null;
}

interface FinancialInfo {
	ind_cor: string;
	individual: IndividualFinance | null;
	corporate: CorporateFinance | null;
	bank_accounts: BankAccount[];
	bank_statement_files: BankFile[];
}

function fmt(n: number | undefined | null): string {
	if (n === undefined || n === null || Number.isNaN(n)) return '0';
	return Math.round(n).toLocaleString('en-US');
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
	return (
		<div className="mb-4 overflow-hidden rounded-2xl bg-white shadow">
			<div className="border-b border-slate-100 bg-slate-50 px-5 py-3">
				<h2 className="text-sm font-semibold text-slate-700">{title}</h2>
			</div>
			<div className="overflow-x-auto p-5">{children}</div>
		</div>
	);
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
	return (
		<div className="border-b border-slate-100 py-2 last:border-0">
			<dt className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</dt>
			<dd className="mt-0.5 text-sm text-slate-700">{value || '-'}</dd>
		</div>
	);
}

function NoDataCard() {
	return (
		<div className="rounded-2xl bg-white p-12 text-center shadow">
			<p className="text-2xl font-bold text-red-600">NO DATA</p>
		</div>
	);
}

function IndividualFinanceSection({ data }: { data: IndividualFinance }) {
	return (
		<Card title={`Financial Information Review — ${data.currency} ${data.period_label}`}>
			<h3 className="mb-2 text-sm font-semibold text-slate-600">Liabilities</h3>
			<table className="mb-4 w-full text-sm">
				<thead>
					<tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-400">
						<th className="py-2">Category</th>
						<th className="py-2">Description</th>
						<th className="py-2 text-right">Amount</th>
					</tr>
				</thead>
				<tbody>
					{data.liabilities?.rows.map((r, i) => (
						<tr key={i} className="border-b border-slate-100">
							<td className="py-2">{r.category}</td>
							<td className="py-2">{r.description}</td>
							<td className="py-2 text-right">{fmt(r.amount)}</td>
						</tr>
					))}
					<tr className="font-semibold">
						<td className="py-2" colSpan={2}>
							Total
						</td>
						<td className="py-2 text-right">{fmt(data.liabilities?.total)}</td>
					</tr>
				</tbody>
			</table>

			<h3 className="mb-2 text-sm font-semibold text-slate-600">Estimated Monthly Income</h3>
			<table className="mb-4 w-full text-sm">
				<tbody>
					{data.income?.income_items.map((it, i) => (
						<tr key={`inc-${i}`} className="border-b border-slate-100">
							<td className="py-2">{it.label}</td>
							<td className="py-2 text-right">{fmt(it.amount)}</td>
						</tr>
					))}
					<tr className="border-b border-slate-100 font-semibold">
						<td className="py-2">Total Income</td>
						<td className="py-2 text-right">{fmt(data.income?.total_income)}</td>
					</tr>
					{data.income?.expense_items.map((it, i) => (
						<tr key={`exp-${i}`} className="border-b border-slate-100">
							<td className="py-2">{it.label}</td>
							<td className="py-2 text-right">{fmt(it.amount)}</td>
						</tr>
					))}
					<tr className="border-b border-slate-100">
						<td className="py-2">Liabilities</td>
						<td className="py-2 text-right">{fmt(data.income?.liabilities_total)}</td>
					</tr>
					<tr className="font-semibold">
						<td className="py-2">Net Saving</td>
						<td className="py-2 text-right">{fmt(data.income?.net_saving)}</td>
					</tr>
				</tbody>
			</table>

			<div className="mb-4 flex items-center justify-between rounded-lg bg-slate-50 px-4 py-2 text-sm">
				<span className="font-medium text-slate-600">DSCR</span>
				<span className="font-semibold text-slate-800">{data.dscr}</span>
			</div>

			<h3 className="mb-2 text-sm font-semibold text-slate-600">Customer Asset Ownership</h3>
			<table className="w-full text-sm">
				<thead>
					<tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-400">
						<th className="py-2">Description</th>
						<th className="py-2 text-right">Amount Estimated</th>
						<th className="py-2">Notes</th>
					</tr>
				</thead>
				<tbody>
					{data.assets?.rows.map((r, i) => (
						<tr key={i} className="border-b border-slate-100">
							<td className="py-2">{r.description}</td>
							<td className="py-2 text-right">{fmt(r.amount)}</td>
							<td className="py-2">{r.notes}</td>
						</tr>
					))}
					<tr className="font-semibold">
						<td className="py-2">Total Assets</td>
						<td className="py-2 text-right">{fmt(data.assets?.total)}</td>
						<td />
					</tr>
				</tbody>
			</table>
		</Card>
	);
}

function BalanceSheetTable({
	title,
	sections,
	total1,
	total2,
	totalLabel,
}: {
	title: string;
	sections: BalanceSheetSection[];
	total1: number;
	total2: number;
	totalLabel: string;
}) {
	return (
		<table className="mb-4 w-full text-sm">
			<thead>
				<tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-400">
					<th className="py-2">{title}</th>
					<th className="py-2 text-right" />
					<th className="py-2 text-right" />
				</tr>
			</thead>
			<tbody>
				{sections.map((sec, si) => (
					<React.Fragment key={si}>
						<tr>
							<td colSpan={3} className="py-2 text-center font-semibold text-slate-700">
								{sec.header}
							</td>
						</tr>
						{sec.rows.map((row, ri) => (
							<tr key={ri} className="border-b border-slate-100">
								<td className="py-1.5">{row.label}</td>
								<td className="py-1.5 text-right">Rp. {fmt(row.amount_a)}</td>
								<td className="py-1.5 text-right">Rp. {fmt(row.amount_b)}</td>
							</tr>
						))}
						{sec.show_subtotal && (
							<tr className="border-b border-slate-100 font-semibold">
								<td className="py-1.5">TOTAL {sec.header}</td>
								<td className="py-1.5 text-right">Rp. {fmt(sec.subtotal_a)}</td>
								<td className="py-1.5 text-right">Rp. {fmt(sec.subtotal_b)}</td>
							</tr>
						)}
					</React.Fragment>
				))}
				<tr className="font-semibold">
					<td className="py-2">{totalLabel}</td>
					<td className="py-2 text-right">Rp. {fmt(total1)}</td>
					<td className="py-2 text-right">Rp. {fmt(total2)}</td>
				</tr>
			</tbody>
		</table>
	);
}

function CorporateFinanceSection({ data }: { data: CorporateFinance }) {
	const bs = data.balance_sheet;
	const pl = data.profit_loss;
	return (
		<>
			{bs && (
				<Card title="Neraca (Balance Sheet)">
					<div className="mb-2 flex justify-end gap-8 text-xs font-semibold uppercase tracking-wide text-slate-400">
						<span>{bs.period_label_1}</span>
						<span>{bs.period_label_2}</span>
					</div>
					<BalanceSheetTable
						title="Assets"
						sections={bs.asset_sections}
						total1={bs.asset_total1}
						total2={bs.asset_total2}
						totalLabel="TOTAL ASSET"
					/>
					<BalanceSheetTable
						title="Liabilities & Net Worth"
						sections={bs.liability_sections}
						total1={bs.liability_total1}
						total2={bs.liability_total2}
						totalLabel="TOTAL LIABILITIES AND NET WORTH"
					/>
				</Card>
			)}

			{pl && (
				<Card title={`Laporan Laba/Rugi (Profit/Loss) — ${pl.period_label}`}>
					<table className="w-full text-sm">
						<tbody>
							{pl.rows.map((r, i) =>
								r.section_header ? (
									<tr key={i}>
										<td colSpan={2} className="py-2 text-center font-bold text-slate-700">
											{r.label}
										</td>
									</tr>
								) : (
									<tr key={i} className={`border-b border-slate-100 ${r.bold ? 'font-semibold' : ''}`}>
										<td className="py-1.5">{r.label}</td>
										<td className="py-1.5 text-right">Rp. {fmt(r.amount)}</td>
									</tr>
								)
							)}
						</tbody>
					</table>
				</Card>
			)}

			<Card title="DSCR">
				<div className="flex items-center justify-between rounded-lg bg-slate-50 px-4 py-2 text-sm">
					<span className="font-medium text-slate-600">DSCR</span>
					<span className="font-semibold text-slate-800">{data.dscr}</span>
				</div>
			</Card>
		</>
	);
}

export default function FinancialInfoView({ ctx }: { ctx: CamCtx }) {
	const [data, setData] = useState<FinancialInfo | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		let active = true;
		setLoading(true);
		setError(null);
		api
			.get('/CAM/View/api/financial-info', {
				params: { apless: ctx.apless, applno: ctx.applno, ind_cor: ctx.indCor },
			})
			.then((res) => {
				if (active) setData(res.data);
			})
			.catch(() => {
				if (active) setError('Failed to load financial information.');
			})
			.finally(() => {
				if (active) setLoading(false);
			});
		return () => {
			active = false;
		};
	}, [ctx.apless, ctx.applno, ctx.indCor]);

	if (loading) {
		return (
			<div className="rounded-2xl bg-white p-8 text-center text-sm text-slate-500 shadow">
				Loading financial information…
			</div>
		);
	}
	if (error || !data) {
		return (
			<div className="rounded-2xl bg-white p-8 text-center text-sm text-red-500 shadow">
				{error || 'No data found.'}
			</div>
		);
	}

	const section = data.ind_cor === '1' ? data.individual : data.ind_cor === '2' ? data.corporate : null;

	if (section?.no_data) {
		return <NoDataCard />;
	}

	return (
		<div>
			{data.ind_cor === '1' && data.individual && <IndividualFinanceSection data={data.individual} />}
			{data.ind_cor === '2' && data.corporate && <CorporateFinanceSection data={data.corporate} />}

			{data.bank_accounts.length > 0 && (
				<Card title="Bank Statement">
					<div className="space-y-6">
						{data.bank_accounts.map((acc, i) => (
							<div key={i} className="rounded-xl border border-slate-100 p-4">
								<dl className="mb-3 grid grid-cols-1 gap-x-8 sm:grid-cols-2">
									<Field label="Bank" value={`${acc.bank_name} / ${acc.branch}`} />
									<Field label="Account Number" value={acc.account_no} />
									<Field label="Account Name" value={acc.account_name} />
									<Field label="Currency" value={acc.currency} />
									<Field label="Account Notes" value={acc.notes} />
								</dl>
								<table className="w-full text-sm">
									<thead>
										<tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-400">
											<th className="py-2 text-left">Month - Year</th>
											<th className="py-2 text-right">Beginning Balance</th>
											<th className="py-2 text-right">Debet</th>
											<th className="py-2 text-right">Credit</th>
											<th className="py-2 text-right">Ending Balance</th>
											<th className="py-2 text-left">Notes</th>
										</tr>
									</thead>
									<tbody>
										{acc.statements.map((s, si) => (
											<tr key={si} className="border-b border-slate-100 last:border-0">
												<td className="py-2">{s.period_label}</td>
												<td className="py-2 text-right">{fmt(s.beginning_balance)}</td>
												<td className="py-2 text-right">{fmt(s.debet)}</td>
												<td className="py-2 text-right">{fmt(s.credit)}</td>
												<td className="py-2 text-right">{fmt(s.ending_balance)}</td>
												<td className="py-2">{s.notes}</td>
											</tr>
										))}
									</tbody>
								</table>
							</div>
						))}
					</div>
				</Card>
			)}

			<Card title="Bank Statement Files">
				{data.bank_statement_files.length === 0 ? (
					<p className="text-sm text-slate-400">No files uploaded.</p>
				) : (
					<ul className="space-y-1">
						{data.bank_statement_files.map((f) => (
							<li key={f.id}>
								{f.download_url ? (
									<a href={f.download_url} className="text-sm text-blue-600 underline hover:text-blue-700">
										{f.name}
									</a>
								) : (
									<span className="text-sm text-slate-700">{f.name}</span>
								)}
							</li>
						))}
					</ul>
				)}
			</Card>
		</div>
	);
}