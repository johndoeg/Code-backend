import { useState } from "react";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";

export default function Layout() {
	const [sidebarOpen, setSidebarOpen] = useState(true);
	const [mini, setMini] = useState(false);

	return (
		<div className="flex flex-col h-screen overflow-hidden">
			<TopBar
				onToggle={() => setSidebarOpen((v) => !v)}
				onMiniToggle={() => setMini((v) => !v)}
			/>

			<div className="flex flex-1 pt-14 bg-gray-100 overflow-hidden">
				<Sidebar
					open={sidebarOpen}
					mini={mini}
					onClose={() => setSidebarOpen(false)}
				/>

				{/* Mobile overlay */}
				{sidebarOpen && (
					<div
						onClick={() => setSidebarOpen(false)}
						className="fixed inset-0 bg-black/40 backdrop-blur-sm z-30 md:hidden"
					/>
				)}

				<main className="flex-1 overflow-y-auto">
					<iframe
						name="main1"
						className="w-full h-full border-none bg-white"
					/>
				</main>
			</div>
		</div>
	);
}