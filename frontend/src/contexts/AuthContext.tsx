import { createContext, useContext, useState, useEffect } from "react";
import type { ReactNode } from "react";
import api from "../api/axiosInstance";

interface User {
	username: string;
	branch_name: string;
}

interface AuthContextType {
	user: User | null;
	isAuthenticated: boolean;
	loading: boolean;
	logout: () => Promise<void>;
	refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
	const [user, setUser] = useState<User | null>(null);
	const [loading, setLoading] = useState(true);

	useEffect(() => {
		refreshUser();
	}, []);

	const refreshUser = async () => {
		try {
			const res = await api.get("/auth/user-info");
			setUser(res.data);
		} catch {
			setUser(null);
		} finally {
			setLoading(false);
		}
	};

	const logout = async () => {
		try {
			await api.post("/auth/logout");
		} finally {
			setUser(null);
		}
	};

	return (
		<AuthContext.Provider value={{ user, isAuthenticated: !!user, loading, logout, refreshUser }}>
			{children}
		</AuthContext.Provider>
	);
}

export function useAuth() {
	const ctx = useContext(AuthContext);
	if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
	return ctx;
}