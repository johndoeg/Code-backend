export async function unwrapApiError<T>(call: () => Promise<T>): Promise<T> {
    try {
        return await call();
    } catch (err) {
        const body = (err as { response?: { data?: T } })?.response?.data;
        if (body !== undefined) return body;
        throw err;
    }
}

export function extractErrorMessage(err: unknown, fallback: string): string {
    const maybeAxiosError = err as {
        response?: { status?: number; data?: { message?: string; error?: string } };
    };
    const serverMessage = maybeAxiosError?.response?.data?.message || maybeAxiosError?.response?.data?.error;
    const status = maybeAxiosError?.response?.status;
    // eslint-disable-next-line no-console
    return serverMessage ? `${serverMessage}${status ? ` (HTTP ${status})` : ''}` : fallback;
}