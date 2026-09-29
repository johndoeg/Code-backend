import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";

export default defineConfig({
	plugins: [react()],

	server: {
		proxy: {
			"/CAM": {
				target: "http://localhost:5000",
				changeOrigin: true,
				secure: false,
			},

			"/Prechecking": {
				target: "http://localhost:5000",
				changeOrigin: true,
				secure: false,
			},
		},
	},
});