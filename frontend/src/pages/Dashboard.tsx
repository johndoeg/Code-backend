import { useEffect, useRef } from "react";

export default function Dashboard() {
	const iframeRef = useRef<HTMLIFrameElement>(null);

	useEffect(() => {
		if (iframeRef.current) {
			iframeRef.current.src = "about:blank";
		}
	}, []);

	return (
		<main className="flex-1 bg-white overflow-auto h-full">
			<iframe
				ref={iframeRef}
				name="main1"
				id="main1"
				className="border-none w-full h-full"
			/>
		</main>
	);
}