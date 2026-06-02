import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from '../api/axiosInstance';

interface UserInfo {
	username: string;
	branch_name: string;
}

const IS_INSIDE_IFRAME = window.self !== window.top;

export default function Dashboard() {
	const navigate = useNavigate();
	const [user, setUser] = useState<UserInfo | null>(null);
	const [isLoggingOut, setIsLoggingOut] = useState(false);
	const iframeRef = useRef<HTMLIFrameElement>(null);

	useEffect(() => {
		if (iframeRef.current) {
			iframeRef.current.src = "about:blank";
		}
	}, []);

	useEffect(() => {
		api.get('/auth/user-info')
			.then((res) => setUser(res.data))
			.catch((err) => {
				console.error("Using fallback user info:", err);
				setUser({ username: "User", branch_name: "Head Office" });
			});
	}, []);

	const today =
		new URLSearchParams(window.location.search).get("date") ||
		new Date().toLocaleDateString("id-ID", {
			timeZone: "Asia/Jakarta",
			weekday: "long",
			year: "numeric",
			month: "long",
			day: "numeric",
		});

	const handleLogout = async () => {
		if (isLoggingOut) return;
		if (!confirm("Are you sure you want to log out?")) return;

		setIsLoggingOut(true);
		try {
			await api.post('/auth/logout');
		} catch (err) {
			console.error("Logout request failed:", err);
		} finally {
			navigate("/login", { replace: true });
		}
	};

	if (IS_INSIDE_IFRAME) {
		return (
			<main className="w-full h-screen bg-white overflow-auto">
				<iframe
					ref={iframeRef}
					name="main1"
					id="main1"
					className="border-none w-full h-full"
				/>
			</main>
		);
	}

	return (
		<div className="flex h-screen bg-gray-100">
			<div className="flex-1 flex flex-col">

				<header className="flex justify-between items-center bg-white shadow p-4 border-b">
					<div className="text-gray-700 font-medium">
						{user ? (
							<>
								Hello,{" "}
								<span className="font-semibold text-blue-800">{user.username}</span>
								{" — "}
								<span className="text-blue-700">{user.branch_name}</span>
								{" — "}
								<span className="text-gray-500">{today}</span>
							</>
						) : (
							"Loading..."
						)}
					</div>

					<button
						onClick={handleLogout}
						disabled={isLoggingOut}
						className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium
                                    transition-all text-white shadow-md hover:shadow-lg ${isLoggingOut
								? "bg-red-400 cursor-not-allowed"
								: "bg-red-600 hover:bg-red-700 active:scale-95"
							}`}
						title="Logout"
					>
						{isLoggingOut ? (
							<>
								<svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
									<circle className="opacity-25" cx="12" cy="12" r="10"
										stroke="currentColor" strokeWidth="4" />
									<path className="opacity-75" fill="currentColor"
										d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962
                                             7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
								</svg>
								Logging out...
							</>
						) : (
							<>
								<svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
									<path fillRule="evenodd"
										d="M3 3a1 1 0 00-1 1v12a1 1 0 102 0V4a1 1 0 00-1-1zm10.293 9.293a1
                                             1 0 001.414 1.414l3-3a1 1 0 000-1.414l-3-3a1 1 0 10-1.414
                                             1.414L14.586 9H7a1 1 0 100 2h7.586l-1.293 1.293z"
										clipRule="evenodd" />
								</svg>
								Logout
							</>
						)}
					</button>
				</header>

				<main className="flex-1 bg-white overflow-auto">
					<iframe
						ref={iframeRef}
						name="main1"
						id="main1"
						className="border-none w-full h-full"
					/>
				</main>
			</div>
		</div>
	);
}