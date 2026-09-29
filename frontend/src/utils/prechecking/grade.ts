export interface GradeResult {
	grade: string;
	scoreError?: string;
}

const PR_RANGES: [number, number, string][] = [
	[200, 569, 'Very High Risk'],
	[570, 629, 'High Risk'],
	[630, 653, 'Average Risk'],
	[654, 677, 'Low Risk'],
	[678, 1000, 'Very Low Risk'],
];

const PT_RANGES: [number, number, string][] = [
	[200, 569, 'Very High Risk'],
	[570, 660, 'High Risk'],
	[661, 700, 'Average Risk'],
	[701, 715, 'Low Risk'],
	[716, 1000, 'Very Low Risk'],
];

function gradeFromRanges(score: number, ranges: [number, number, string][]): string {
	for (const [min, max, label] of ranges) {
		if (score >= min && score <= max) return label;
	}
	return '';
}

export function computeGrade(
	creditBureau: string,
	scoreRaw: string,
	subject: string,
	type: string,
	customerType: 'PR' | 'PT' = 'PR',
): GradeResult {
	if (creditBureau !== 'PBK') {
		return { grade: '' };
	}
	if (scoreRaw === '') {
		return { grade: '' };
	}

	const score = Number(scoreRaw);
	if (Number.isNaN(score)) {
		return { grade: '' };
	}

	if (score > 0 && (score < 200 || score > 1000)) {
		return { grade: '', scoreError: 'Your score is out of specified range!' };
	}

	if (score === 0) {
		return { grade: 'No Score' };
	}

	const effectiveType = subject === 'RP' ? type : customerType;
	if (effectiveType === 'PR') return { grade: gradeFromRanges(score, PR_RANGES) };
	if (effectiveType === 'PT') return { grade: gradeFromRanges(score, PT_RANGES) };
	return { grade: '' };
}
