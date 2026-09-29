import { useEffect, useRef, useState, type ReactNode } from "react";
import MaintenancePage from "./MaintenancePage";
import type { MaintenanceInfo } from "../types/maintenance";

interface MaintenanceGateProps {
	children: ReactNode;
}

export default function MaintenanceGate({ children }: MaintenanceGateProps) {
	const [info, setInfo] = useState<MaintenanceInfo | null>(null);
	const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

	useEffect(() => {
		function handleMaintenance(e: CustomEvent<MaintenanceInfo>) {
			setInfo(e.detail);
		}
		window.addEventListener("app:maintenance", handleMaintenance);
		return () => window.removeEventListener("app:maintenance", handleMaintenance);
	}, []);

	useEffect(() => {
		if (!info) return;
		const ms = (info.retry_after || 600) * 1000;
		timeoutRef.current = setTimeout(() => window.location.reload(), ms);
		return () => {
			if (timeoutRef.current) clearTimeout(timeoutRef.current);
		};
	}, [info]);

	if (info) {
		return <MaintenancePage info={info} />;
	}

	return <>{children}</>;
}