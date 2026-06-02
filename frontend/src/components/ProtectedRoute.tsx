import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";

const API_URL = import.meta.env.VITE_API_URL;

export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
	const [status, setStatus] = useState<"checking" | "auth" | "unauth">("checking");

	useEffect(() => {
		fetch(`${API_URL}/auth/user-info`, { credentials: "include" })
			.then((res) => setStatus(res.ok ? "auth" : "unauth"))
			.catch(() => setStatus("unauth"));
	}, []);

	if (status === "checking") {
		return (
			<div className="min-h-screen flex items-center justify-center bg-gray-100">
				<svg className="animate-spin h-8 w-8 text-blue-600" fill="none" viewBox="0 0 24 24">
					<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
					<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
				</svg>
			</div>
		);
	}

	return status === "auth" ? <>{children}</> : <Navigate to="/login" replace />;
}