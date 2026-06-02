import { useState } from "react";
import { useNavigate } from "react-router-dom";

export default function LoginPage() {
	const navigate = useNavigate();
	const [username, setUsername] = useState("");
	const [password, setPassword] = useState("");
	const [error, setError] = useState("");
	const [loading, setLoading] = useState(false);

	const API_VERSION = import.meta.env.VITE_API_VERSION || "v1";
	const API_URL = import.meta.env.VITE_API_URL;

	const handleLogin = async (e: React.FormEvent) => {
		e.preventDefault();
		setError("");
		setLoading(true);

		try {
			const response = await fetch(`${API_URL}/auth/login`, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ username, password }),
				credentials: "include",
			});

			const data = await response.json();
			if (!response.ok) {
				if (data.maintenance) {
					throw new Error(data.message || "System under maintenance");
				}
				throw new Error(data.message || "Login failed");
			}

			// window.location.href = "/dashboard";
			navigate("/");
		} catch (err: any) {
			setError(err.message);
		} finally {
			setLoading(false);
		}
	};

	return (
		<div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 via-white to-purple-100 p-4">
			<div className="w-full max-w-md backdrop-blur-xl bg-white/40 border border-white/60 rounded-3xl shadow-2xl p-8 animate-fadeIn">

				<h2 className="text-3xl font-extrabold text-center mb-8 bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
					Welcome Back
				</h2>

				<form onSubmit={handleLogin} className="space-y-5">
					<div>
						<label className="block text-sm font-semibold text-gray-700 mb-1">
							Username
						</label>
						<input
							type="text"
							value={username}
							onChange={(e) => setUsername(e.target.value)}
							disabled={loading}
							className="w-full px-4 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all shadow-sm disabled:bg-gray-100 disabled:cursor-not-allowed"
							required
							autoComplete="username"
						/>
					</div>

					<div>
						<label className="block text-sm font-semibold text-gray-700 mb-1">
							Password
						</label>
						<input
							type="password"
							value={password}
							onChange={(e) => setPassword(e.target.value)}
							disabled={loading}
							className="w-full px-4 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all shadow-sm disabled:bg-gray-100 disabled:cursor-not-allowed"
							required
							autoComplete="current-password"
						/>
					</div>

					{error && (
						<p className="text-red-500 text-sm bg-red-50 border border-red-200 p-2 rounded-lg animate-shake">
							{error}
						</p>
					)}

					<button
						type="submit"
						disabled={loading || !username || !password}
						className={`w-full py-3 rounded-xl bg-gradient-to-r from-blue-600 to-purple-600 text-white font-semibold shadow-lg transition-all active:scale-95 disabled:opacity-70 disabled:cursor-not-allowed disabled:active:scale-100 ${loading ? "animate-pulse" : "hover:opacity-90"
							}`}
					>
						{loading ? (
							<span className="flex items-center justify-center gap-2">
								<svg className="animate-spin h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
									<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
									<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
								</svg>
								Signing in...
							</span>
						) : (
							"Login"
						)}
					</button>
				</form>

				{/* Footer */}
				<div className="mt-6 text-center text-xs text-gray-500">
					<p>© {new Date().getFullYear()} PT Genie Finance Indonesia</p>
					<p className="mt-1">Version {import.meta.env.VITE_APP_VERSION || "1.0.0"}</p>
				</div>
			</div>
		</div>
	);
}