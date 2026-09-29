export interface MaintenanceInfo {
    error: "maintenance";
    message: string;
    retry_after: number;
    app_name?: string;
}

declare global {
    interface WindowEventMap {
        "app:maintenance": CustomEvent<MaintenanceInfo>;
    }
}