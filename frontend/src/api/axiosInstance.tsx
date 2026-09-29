import axios from "axios";
import type { MaintenanceInfo } from "../types/maintenance";

const api = axios.create({
	baseURL: import.meta.env.VITE_API_URL,
	withCredentials: true,
	timeout: 15000,
});

api.interceptors.response.use(
	(response) => response,
	(error) => {
		const url: string = error.config?.url ?? "";
		const status: number | undefined = error.response?.status;
		const data = error.response?.data;

		const isAuthEndpoint = url.includes("/auth/");

		if (status === 503 && data?.error === "maintenance") {
			window.dispatchEvent(
				new CustomEvent<MaintenanceInfo>("app:maintenance", { detail: data })
			);
			return Promise.reject(error);
		}

		if (status === 401 && !isAuthEndpoint) {
			window.location.href = "/login";
		}

		return Promise.reject(error);
	}
);

export default api;