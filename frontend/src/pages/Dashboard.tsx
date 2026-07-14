import { useEffect, useRef } from "react";
import { useAuth } from "../contexts/AuthContext";

const IS_INSIDE_IFRAME = window.self !== window.top;

export default function Dashboard() {
	const { user } = useAuth();
	const iframeRef = useRef<HTMLIFrameElement>(null);

	useEffect(() => {
		if (iframeRef.current) {
			iframeRef.current.src = "about:blank";
		}
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