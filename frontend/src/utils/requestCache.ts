type CacheEntry<T> = { data: T; expiresAt: number };

const cache = new Map<string, CacheEntry<unknown>>();
const inFlight = new Map<string, Promise<unknown>>();

export function makeCacheKey(url: string, params?: Record<string, unknown>): string {
	return params ? `${url}?${JSON.stringify(params)}` : url;
}

export async function cachedGet<T>(
	fetcher: () => Promise<T>,
	key: string,
	ttlMs = 30_000,
): Promise<T> {
	const hit = cache.get(key) as CacheEntry<T> | undefined;
	if (hit && hit.expiresAt > Date.now()) return hit.data;

	const pending = inFlight.get(key) as Promise<T> | undefined;
	if (pending) return pending;

	const promise = fetcher()
		.then(data => {
			cache.set(key, { data, expiresAt: Date.now() + ttlMs });
			inFlight.delete(key);
			return data;
		})
		.catch(err => {
			inFlight.delete(key);
			throw err;
		});

	inFlight.set(key, promise);
	return promise;
}

export function invalidateCache(prefix: string): void {
	for (const key of cache.keys()) {
		if (key.startsWith(prefix)) cache.delete(key);
	}
}

export function clearRequestCache(): void {
	cache.clear();
	inFlight.clear();
}