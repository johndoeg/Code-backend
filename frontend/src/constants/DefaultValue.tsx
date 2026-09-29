export const DEFAULT_PAGE_LIMIT = 25;
export const DEFAULT_PAGE = 1;
export const MAX_EXPORT_ROWS = 10000;
export const MAX_FILE_LIMIT = 2 * 1024 * 1024;

export const IMAGE_EXTS = new Set(["png", "jpg", "jpeg", "gif", "bmp", "heic", "heif", "tiff", "tif", "webp",]);

export const getFileExtension = (filename = "") =>
	filename.split(".").pop()?.toLowerCase() ?? "";

export const isImageFile = (filename = "") =>
	IMAGE_EXTS.has(getFileExtension(filename));

export const getAcceptedImageTypes = () =>
	[...IMAGE_EXTS].map((ext) => `image/${ext}`).join(",");

export const resolveExt = (doc) => {
	try {
		const qs = new URLSearchParams(doc.viewUrl?.split("?")[1] ?? "");
		const fn = qs.get("file_name") ?? qs.get("aws_key") ?? "";
		const ext = fn.split(".").pop()?.toLowerCase() ?? "";
		if (ext && ext.length <= 5 && /^[a-z0-9]+$/.test(ext)) return ext;
	} catch { }

	const nameExt = doc.name.split("?")[0].split(".").pop()?.toLowerCase() ?? "";
	return nameExt.length <= 5 ? nameExt : "";
};