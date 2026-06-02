import { useState } from "react";

const API_URL = import.meta.env.VITE_API_URL;

export default function LoginForm() {
	const [username, setUsername] = useState("");
	const [password, setPassword] = useState("");
	const [error, setError] = useState("");
	const [loading, setLoading] = useState(false);

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		setLoading(true);
		setError("");

		try {
			const res = await fetch(`${API_URL}/auth/login`, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				credentials: "include",
				body: JSON.stringify({ username, password }),
			});

			const data = await res.json();

			if (!res.ok) {
				setError(data.error || "Login failed");
			} else {
				alert(`Welcome, ${data.username}`);
			}
		} catch (err) {
			console.error(err);
			setError("Server error");
		} finally {
			setLoading(false);
		}
	};

	return (
		<div className="flex justify-center items-center h-screen bg-gray-100">
			<form
				onSubmit={handleSubmit}
				className="bg-white p-8 rounded-2xl shadow-md w-full max-w-sm"
			>
				<h2 className="text-2xl font-bold mb-6 text-center">Login</h2>
				<input
					type="text"
					placeholder="Username"
					value={username}
					onChange={(e) => setUsername(e.target.value)}
					className="w-full p-2 mb-4 border rounded-md"
					required
				/>
				<input
					type="password"
					placeholder="Password"
					value={password}
					onChange={(e) => setPassword(e.target.value)}
					className="w-full p-2 mb-4 border rounded-md"
					required
				/>
				<button
					type="submit"
					disabled={loading}
					className="w-full bg-blue-600 text-white py-2 rounded-md hover:bg-blue-700"
				>
					{loading ? "Logging in..." : "Login"}
				</button>
				{error && <p className="text-red-500 text-center mt-4">{error}</p>}
			</form>
		</div>
	);
}
