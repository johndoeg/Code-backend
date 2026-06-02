import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";

const API_URL = import.meta.env.VITE_API_URL;

export default function PublicRoute({ children }: { children: React.ReactNode }) {
	const [status, setStatus] = useState<"checking" | "auth" | "unauth">("checking");

	useEffect(() => {
		fetch(`${API_URL}/auth/user-info`, { credentials: "include" })
			.then((res) => setStatus(res.ok ? "auth" : "unauth"))
			.catch(() => setStatus("unauth"));
	}, []);

	if (status === "checking") return null;

	return status === "unauth" ? <>{children}</> : <Navigate to="/" replace />;
}