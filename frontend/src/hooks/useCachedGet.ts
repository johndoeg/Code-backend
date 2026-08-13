import { useCallback, useEffect, useState } from "react";
import api from "../api/axiosInstance";
import { cachedGet, makeCacheKey, invalidateCache } from "../utils/requestCache";

interface Options {
	ttlMs?: number;
	enabled?: boolean;
}

export function useCachedGet<T>(url: string, params: Record<string, unknown>, opts: Options = {}) {
	const { ttlMs = 30_000, enabled = true } = opts;
	const [data, setData] = useState<T | null>(null);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const key = makeCacheKey(url, params);

	const run = useCallback(
		async (force = false) => {
			if (!enabled) return;
			if (force) invalidateCache(key);
			setLoading(true);
			setError(null);
			try {
				const result = await cachedGet<T>(
					() => api.get(url, { params }).then(res => res.data),
					key,
					ttlMs,
				);
				setData(result);
			} catch (err) {
				console.error(err);
				setError("Failed to load data. Please try again.");
			} finally {
				setLoading(false);
			}
		},
		// eslint-disable-next-line react-hooks/exhaustive-deps
		[key, enabled, ttlMs],
	);

	useEffect(() => {
		run();
	}, [run]);

	return { data, loading, error, refetch: () => run(true) };
}