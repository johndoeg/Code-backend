import React, { useEffect, useState } from 'react';
import api from '../../../../api/axiosInstance';
import type { CamCtx } from './CamViewTabs';

interface FileEntry { file_name: string; aws_key: string; }

interface AllFilesData {
	ind_cor: string;
	lessee_cat: string;
	citizen: string;
	spouse_citizen: string;
	customer_documents: Record<string, FileEntry[]>;
	bank_statement: FileEntry[];
	has_guarantor: boolean;
	guarantor_type_pr: string | null;
	guarantor_type_pt: string | null;
	guarantor_documents: Record<string, FileEntry[]>;
	guarantor_bank_statement: FileEntry[];
	cust_survey: Record<string, FileEntry[]>;
	eq_survey: Record<string, FileEntry[]>;
	is_approved: string;
	applno: string;
	apless: string;
}

const dlHref = (awsKey: string, fileName: string) =>
	`/CAM/api/files/download?aws_key=${encodeURIComponent(awsKey)}&file_name=${encodeURIComponent(fileName)}`;

function filesFor(docs: Record<string, FileEntry[]>, ...keys: string[]): FileEntry[] {
	return keys.flatMap(k => docs[k] ?? []);
}

function dynamicKeys(docs: Record<string, FileEntry[]>, prefix: string): string[] {
	return Object.keys(docs).filter(k => k.startsWith(prefix)).sort();
}

function FileTable({ files }: { files: FileEntry[] }) {
	if (!files.length)
		return <span className="text-xs italic text-slate-400">No files uploaded</span>;
	return (
		<div className="space-y-1">
			{files.map((f, i) => (
				<div key={i} className="flex items-center gap-3 rounded border border-slate-100 bg-slate-50 px-2 py-1">
					<span className="w-5 shrink-0 text-xs text-slate-400">{i + 1}</span>
					<span className="flex-1 break-all text-xs">{f.file_name}</span>
					{f.aws_key ? (
						<a
							href={dlHref(f.aws_key, f.file_name)}
							target="_blank"
							rel="noopener noreferrer"
							className="shrink-0 rounded bg-orange-500 px-3 py-1 text-xs font-bold text-white hover:bg-orange-600"
						>
							Download
						</a>
					) : (
						<span className="shrink-0 rounded bg-slate-200 px-3 py-1 text-xs font-bold text-slate-400 cursor-not-allowed">
							Download
						</span>
					)}
				</div>
			))}
		</div>
	);
}

function FieldRow({ label, files }: { label: string; files: FileEntry[] }) {
	return (
		<div className="flex gap-4 border-b border-slate-100 py-2.5 last:border-0">
			<div className="w-1/4 shrink-0 pt-1 text-xs text-slate-500">{label}</div>
			<div className="flex-1"><FileTable files={files} /></div>
		</div>
	);
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
	return (
		<div className="mb-4 overflow-hidden rounded-2xl bg-white shadow">
			<div className="border-b border-slate-100 bg-slate-50 px-5 py-3">
				<h2 className="text-sm font-semibold text-slate-700">{title}</h2>
			</div>
			<div className="px-5 pb-3 pt-1">{children}</div>
		</div>
	);
}

function Sub({ title }: { title: string }) {
	return <p className="mb-1 mt-3 text-xs font-bold uppercase tracking-wide text-slate-500">{title}</p>;
}


function IndividualDocSection({
	docs, citizen, spouseCitizen,
}: { docs: Record<string, FileEntry[]>; citizen: string; spouseCitizen: string }) {
	const isWNA = citizen === 'WNA';
	const spouseIsWNA = spouseCitizen === 'WNA';
	return (
		<Section title="Customer's Document">
			{isWNA ? (
				<>
					<Sub title="WNA" />
					<FieldRow label="KITAS/KITAP a/n Pelanggan" files={filesFor(docs, 'cust-kitas')} />
					<FieldRow
						label="KITAS/KITAP a/n Suami/Istri Pelanggan"
						files={filesFor(docs, spouseIsWNA ? 'cust-spouse-kitas' : 'cust-wna-spouse-ktp')}
					/>
					<FieldRow label="SK. Susunan Keluarga Pendatang (SKSP) WNA" files={filesFor(docs, 'cust-family-tree')} />
					<FieldRow label="Surat Referensi Kerja dari Perusahaan WNA Bekerja" files={filesFor(docs, 'cust-reference')} />
				</>
			) : (
				<>
					<Sub title="WNI" />
					<FieldRow label="Customer's Spouse Family Card" files={filesFor(docs, 'cust-spouse-kk')} />
				</>
			)}
			<Sub title="Additional Document" />
			<FieldRow label="Salary Receipt" files={filesFor(docs, 'cust-salary-receipt')} />
			<Sub title="BPKB Document" />
			<FieldRow label="BPKB ID" files={filesFor(docs, 'cust-ktp-bpkb')} />
			<FieldRow label="BPKB Family Card" files={filesFor(docs, 'cust-kk-bpkb')} />
			<FieldRow label="Other" files={filesFor(docs, 'cust-other')} />
			<Sub title="Individual Document" />
			<FieldRow label="ID Card" files={filesFor(docs, 'cust-ktp')} />
			<FieldRow
				label="Spouse ID Card"
				files={filesFor(docs, spouseIsWNA ? 'cust-spouse-kitas' : 'cust-spouse-ktp')}
			/>
			<FieldRow label="KK" files={filesFor(docs, 'cust-kk')} />
			<FieldRow label="NPWP" files={filesFor(docs, 'cust-npwp')} />
			<FieldRow label="SPK" files={filesFor(docs, 'cust-spk')} />
			<FieldRow label="Marriage/Death/Divorce/Prenuptial Statement" files={filesFor(docs, 'cust-marriage-or-death-statement')} />
		</Section>
	);
}

function KoperasiDocSection({ docs }: { docs: Record<string, FileEntry[]> }) {
	const dynKtp = dynamicKeys(docs, 'corp-ocr-ktp_');
	const dynWna = dynamicKeys(docs, 'wna-corp-board_');
	return (
		<Section title="Customer's Document">
			<Sub title="Customer Type: KOPERASI" />
			<FieldRow label="Susunan Pengurus & Pengawas Koperasi" files={filesFor(docs, 'corp-structure')} />
			<FieldRow label="KTP a/n Pengawas Penanda Tangan Kontrak" files={filesFor(docs, 'corp-ktp-pengawas')} />
			<FieldRow label="SIUP" files={filesFor(docs, 'corp-siup')} />
			<FieldRow label="NIB" files={filesFor(docs, 'corp-nib')} />
			<Sub title="Dokumen BPKB" />
			<FieldRow label="KTP an. BPKB" files={filesFor(docs, 'corp-ktp-bpkb')} />
			<FieldRow label="Kartu Keluarga an. BPKB" files={filesFor(docs, 'corp-kk-bpkb')} />
			<FieldRow label="Other" files={filesFor(docs, 'corp-other')} />
			<Sub title="Dokumen Data Perusahaan" />
			<FieldRow label="Akta Pendirian" files={filesFor(docs, 'corp-akta')} />
			<FieldRow label="SK Kemenkumham Akta Pendirian" files={filesFor(docs, 'corp-sk-akta')} />
			<FieldRow label="Akta Perubahan Terakhir" files={filesFor(docs, 'corp-akta-terakhir')} />
			<FieldRow label="SK Kemenkumham atas Akta Perubahan Terakhir" files={filesFor(docs, 'corp-sk-akta-terakhir')} />
			<FieldRow label="KTP Pengurus pada Akta Perubahan Terakhir" files={filesFor(docs, 'corp-ktp-akta-terakhir')} />
			{dynKtp.map((k, i) => <React.Fragment key={k}><FieldRow label={`KTP Pengurus ${i + 1}`} files={docs[k] ?? []} /></React.Fragment>)}
			{dynWna.map((k, i) => <React.Fragment key={k}><FieldRow label={`WNA Board Document ${i + 1}`} files={docs[k] ?? []} /></React.Fragment>)}
			<FieldRow label="NPWP Perusahaan" files={filesFor(docs, 'corp-npwp')} />
			<FieldRow label="SPK" files={filesFor(docs, 'corp-spk')} />
		</Section>
	);
}

const CORP_LABELS: Record<string, string> = {
	'corp-structure': 'Susunan Pengurus',
	'corp-ktp-pengawas': 'KTP a/n Pengawas',
	'corp-siup': 'SIUP',
	'corp-nib': 'NIB',
	'corp-ktp-bpkb': 'KTP an. BPKB',
	'corp-kk-bpkb': 'Kartu Keluarga an. BPKB',
	'corp-other': 'Other',
	'corp-akta': 'Akta Pendirian',
	'corp-sk-akta': 'SK Kemenkumham Akta Pendirian',
	'corp-akta-terakhir': 'Akta Perubahan Terakhir',
	'corp-sk-akta-terakhir': 'SK Kemenkumham atas Akta Perubahan Terakhir',
	'corp-ktp-akta-terakhir': 'KTP Pengurus pada Akta Perubahan Terakhir',
	'corp-npwp': 'NPWP Perusahaan',
	'corp-spk': 'SPK',
};

function GenericCorpDocSection({ docs, lesseeCat }: { docs: Record<string, FileEntry[]>; lesseeCat: string }) {
	const typeLabel = ({ CV: 'CV', FD: 'YAYASAN', PT: 'PT' } as Record<string, string>)[lesseeCat] ?? lesseeCat;
	const dynKtp = dynamicKeys(docs, 'corp-ocr-ktp_');
	const dynWna = dynamicKeys(docs, 'wna-corp-board_');
	const knownKeys = Object.keys(CORP_LABELS);
	const otherKeys = Object.keys(docs).filter(
		k => !knownKeys.includes(k) && !k.startsWith('corp-ocr-ktp_') && !k.startsWith('wna-corp-board_')
	);
	return (
		<Section title="Customer's Document">
			<Sub title={`Customer Type: ${typeLabel}`} />
			{knownKeys.filter(k => docs[k]?.length).map(k => (
				<React.Fragment key={k}><FieldRow label={CORP_LABELS[k]} files={docs[k]} /></React.Fragment>
			))}
			{dynKtp.map((k, i) => <React.Fragment key={k}><FieldRow label={`KTP Pengurus ${i + 1}`} files={docs[k] ?? []} /></React.Fragment>)}
			{dynWna.map((k, i) => <React.Fragment key={k}><FieldRow label={`WNA Board Document ${i + 1}`} files={docs[k] ?? []} /></React.Fragment>)}
			{otherKeys.map(k => (
				<React.Fragment key={k}><FieldRow label={k.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())} files={docs[k]} /></React.Fragment>
			))}
		</Section>
	);
}

function ManagementDetailSection({ docs }: { docs: Record<string, FileEntry[]> }) {
	const files = [
		...dynamicKeys(docs, 'corp-ocr-ktp_').flatMap(k => docs[k] ?? []),
		...dynamicKeys(docs, 'wna-corp-board_').flatMap(k => docs[k] ?? []),
	];
	if (!files.length) return null;
	return (
		<Section title="Management Detail">
			<FileTable files={files} />
		</Section>
	);
}

function GuarantorCorpSection({ docs }: { docs: Record<string, FileEntry[]> }) {
	const dynKtp = dynamicKeys(docs, 'corp-guarantor-ocr-ktp_');
	const dynWna = dynamicKeys(docs, 'corp-guarantor-wna-corp-board_');
	return (
		<Section title="Guarantor's Corporate Document">
			<FieldRow label="KK a/n Pemegang Saham (jika ada)" files={filesFor(docs, 'corp-guarantor-kk')} />
			<FieldRow label="Akta Pendirian" files={filesFor(docs, 'corp-guarantor-akta')} />
			<FieldRow label="SK Kemenkumham Akta Pendirian" files={filesFor(docs, 'corp-guarantor-sk-akta')} />
			<FieldRow label="Akta Perubahan Terakhir" files={filesFor(docs, 'corp-guarantor-akta-terakhir')} />
			<FieldRow label="SK Kemenkumham atas Akta Perubahan Terakhir" files={filesFor(docs, 'corp-guarantor-sk-akta-terakhir')} />
			<FieldRow label="KTP Pengurus atas Akta Perubahan Terakhir" files={filesFor(docs, 'corp-guarantor-ktp-akta-terakhir')} />
			{dynKtp.map((k, i) => <React.Fragment key={k}><FieldRow label={`KTP Pengurus Penjamin ${i + 1}`} files={docs[k] ?? []} /></React.Fragment>)}
			{dynWna.map((k, i) => <React.Fragment key={k}><FieldRow label={`WNA Board Penjamin ${i + 1}`} files={docs[k] ?? []} /></React.Fragment>)}
			<FieldRow label="NPWP" files={filesFor(docs, 'corp-guarantor-npwp')} />
		</Section>
	);
}

export default function AllFilesView({ ctx }: { ctx: CamCtx }) {
	const [data, setData] = useState<AllFilesData | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		let active = true;
		setLoading(true);
		setError(null);
		api
			.get('/CAM/api/view/all-files', {
				params: { apless: ctx.apless, applno: ctx.applno, ind_cor: ctx.indCor },
			})
			.then(res => { if (active) setData(res.data); })
			.catch(() => { if (active) setError('Failed to load files.'); })
			.finally(() => { if (active) setLoading(false); });
		return () => { active = false; };
	}, [ctx.apless, ctx.applno, ctx.indCor]);

	if (loading) return <div className="p-8 text-center text-sm text-slate-500">Loading files…</div>;
	if (error || !data) return <div className="p-8 text-center text-sm text-red-500">{error || 'No data.'}</div>;

	const {
		ind_cor, lessee_cat, citizen, spouse_citizen,
		customer_documents, bank_statement,
		has_guarantor, guarantor_type_pr, guarantor_type_pt,
		guarantor_documents, guarantor_bank_statement,
		cust_survey, eq_survey, is_approved, applno,
	} = data;

	const isCorp = ind_cor === '2';

	return (
		<div>
			{!isCorp && (
				<IndividualDocSection docs={customer_documents} citizen={citizen} spouseCitizen={spouse_citizen} />
			)}
			{isCorp && lessee_cat === 'CO' && <KoperasiDocSection docs={customer_documents} />}
			{isCorp && lessee_cat !== 'CO' && (
				<GenericCorpDocSection docs={customer_documents} lesseeCat={lessee_cat} />
			)}

			<Section title="Bank Statement">
				<FieldRow label="Bank Statement Files" files={bank_statement} />
			</Section>

			{isCorp && <ManagementDetailSection docs={customer_documents} />}

			{has_guarantor && guarantor_type_pr && (
				<Section title="Guarantor's Individu Document">
					<FieldRow label="KK a/n Suami/Istri Penjamin" files={filesFor(guarantor_documents, 'guarantor-spouse-kk')} />
					<FieldRow label="KTP a/n Penjamin" files={filesFor(guarantor_documents, 'guarantor-ktp')} />
					<FieldRow label="KTP a/n Suami/Istri Penjamin" files={filesFor(guarantor_documents, 'guarantor-spouse-ktp')} />
					<FieldRow label="Kartu Keluarga a/n Penjamin" files={filesFor(guarantor_documents, 'guarantor-kk')} />
					<FieldRow label="NPWP a/n Penjamin" files={filesFor(guarantor_documents, 'guarantor-npwp')} />
					<FieldRow label="Akta Cerai/Mati a/n Penjamin" files={filesFor(guarantor_documents, 'guarantor-marriage-or-death-statement')} />
				</Section>
			)}

			{has_guarantor && guarantor_type_pt && <GuarantorCorpSection docs={guarantor_documents} />}

			{has_guarantor && (
				<Section title="Guarantor's Bank Statement">
					<FieldRow label="Bank Statement Files" files={guarantor_bank_statement} />
				</Section>
			)}

			<Section title="Customer Survey Files">
				<FieldRow label="Home Survey" files={cust_survey['home-survey'] ?? []} />
				<FieldRow label="Office Survey" files={cust_survey['office-survey'] ?? []} />
				<FieldRow label="Other Survey" files={cust_survey['other-survey'] ?? []} />
			</Section>

			<Section title="Vehicle Survey Files">
				<Sub title="Vehicle Photo" />
				<FieldRow label="Front only" files={eq_survey['vehicle-photo-front'] ?? []} />
				<FieldRow label="Vehicle Photo" files={eq_survey['vehicle-photo'] ?? []} />
				<Sub title="Vehicle Data" />
				<FieldRow label="BPKB, Faktur, Sertifikat NIK and/or Form A" files={eq_survey['vehicle-data-bpkb'] ?? []} />
				<FieldRow label="STNK" files={eq_survey['vehicle-data'] ?? []} />
			</Section>

			{is_approved === 'E' && (
				<Section title="Customer Analysis Result">
					<FieldRow
						label="Customer Analysis Result File"
						files={[{ file_name: `${applno}-CUSTOMER_ANALYSIS_RESULT.jpg`, aws_key: '' }]}
					/>
				</Section>
			)}
		</div>
	);
}