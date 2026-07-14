import type { MaintenanceInfo } from "../types/maintenance";

interface MaintenancePageProps {
	info: MaintenanceInfo;
}

const GEAR_PATH =
	"M12 8a4 4 0 100 8 4 4 0 000-8zm9.4 4a7.97 7.97 0 00-.15-1.5l2.1-1.63a.5.5 0 00.12-.64l-2-3.46a.5.5 0 00-.6-.22l-2.47 1a8.03 8.03 0 00-1.3-.75l-.38-2.65a.5.5 0 00-.5-.42h-4a.5.5 0 00-.5.42l-.37 2.65c-.47.2-.9.45-1.3.75l-2.48-1a.5.5 0 00-.6.22l-2 3.46a.5.5 0 00.12.64l2.1 1.63A7.97 7.97 0 002.6 12c0 .5.05 1 .15 1.5l-2.1 1.63a.5.5 0 00-.12.64l2 3.46c.14.24.42.32.6.22l2.48-1c.4.3.83.55 1.3.75l.37 2.65c.05.24.26.42.5.42h4c.24 0 .45-.18.5-.42l.38-2.65c.47-.2.9-.45 1.3-.75l2.47 1c.24.1.5 0 .6-.22l2-3.46a.5.5 0 00-.12-.64l-2.1-1.63c.1-.5.15-1 .15-1.5z";

export default function MaintenancePage({ info }: MaintenancePageProps) {
	return (
		<div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-indigo-500 to-purple-700 p-4">
			<div className="bg-white rounded-xl shadow-2xl max-w-md w-full text-center p-8">
				<div className="relative w-20 h-16 mx-auto mb-4">
					<svg
						viewBox="0 0 24 24"
						fill="currentColor"
						className="absolute w-11 h-11 text-indigo-500 animate-spin-cw"
						style={{ top: 0, left: 2 }}
					>
						<path d={GEAR_PATH} />
					</svg>
					<svg
						viewBox="0 0 24 24"
						fill="currentColor"
						className="absolute w-7 h-7 text-purple-400 animate-spin-ccw"
						style={{ top: 26, left: 38 }}
					>
						<path d={GEAR_PATH} />
					</svg>
				</div>

				<h1 className="text-xl font-semibold text-gray-800 mb-2">Under Maintenance</h1>
				<p className="text-gray-600 mb-1">
					{info?.message || "We're currently performing scheduled maintenance."}
				</p>
				<p className="text-gray-600">Our team is working hard to bring you a better experience.</p>

				<div className="mt-8 pt-4 border-t border-gray-100 text-xs text-gray-400">
					<p>Need urgent assistance? Contact support@geniefinance.com</p>
				</div>
			</div>

			<style>{`
				@keyframes spin-cw {
					from { transform: rotate(0deg); }
					to { transform: rotate(360deg); }
				}
				@keyframes spin-ccw {
					from { transform: rotate(0deg); }
					to { transform: rotate(-360deg); }
				}
				.animate-spin-cw {
					animation: spin-cw 4s linear infinite;
				}
				.animate-spin-ccw {
					animation: spin-ccw 2.8s linear infinite;
				}
			`}</style>
		</div>
	);
}