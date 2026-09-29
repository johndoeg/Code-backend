export default function TopBar({
	onToggle,
	onMiniToggle,
}: {
	onToggle: () => void;
	onMiniToggle: () => void;
}) {
	return (
		<div className="fixed top-0 left-0 right-0 h-14 bg-neutral-900 text-white flex items-center justify-between px-4 z-50 shadow">
			<div className="flex items-center gap-3">
				<img src="/images/new_logo_genie.png" className="w-8 h-8" />
				<span className="font-bold hidden sm:block">Genie</span>
			</div>

			<div className="flex items-center gap-2">
				<button
					onClick={onMiniToggle}
					className="p-2 rounded hover:bg-neutral-700 hidden md:block"
				>
				⇔
				</button>
				<button
					onClick={onToggle}
					className="p-2 rounded hover:bg-neutral-700"
				>
				☰
				</button>
			</div>
		</div>
	);
}
