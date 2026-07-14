import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";

function FullPageSpinner() {
	return (
		<div className="flex h-screen items-center justify-center bg-gray-50">
			<div className="flex flex-col items-center gap-3 text-gray-400">
				<div className="w-8 h-8 border-4 border-gray-200 border-t-blue-500 rounded-full animate-spin" />
				<span className="text-sm">Loading…</span>
			</div>
		</div>
	);
}

export default function ProtectedRoute({ children }: { children: ReactNode }) {
	const { isAuthenticated, loading } = useAuth();
	const location = useLocation();

	if (loading) return <FullPageSpinner />;

	return isAuthenticated ? (
		<>{children}</>
	) : (
		<Navigate to="/login" state={{ from: location }} replace />
	);
}