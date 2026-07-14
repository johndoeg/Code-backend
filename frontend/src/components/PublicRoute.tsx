import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";

export default function PublicRoute({ children }: { children: ReactNode }) {
	const { isAuthenticated, loading } = useAuth();

	if (loading) return null;

	return isAuthenticated ? <Navigate to="/" replace /> : <>{children}</>;
}