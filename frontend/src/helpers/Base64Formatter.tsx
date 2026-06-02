export const getBase64ImageSrc = (base64String: string | null | undefined): string => {
	if (!base64String) return '';

	if (base64String.startsWith('data:image')) {
		return base64String;
	}

	return `data:image/jpeg;base64,${base64String}`;
};

export default {
	getBase64ImageSrc
};