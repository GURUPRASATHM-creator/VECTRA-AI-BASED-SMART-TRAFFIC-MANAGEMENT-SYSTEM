import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
// https://vitejs.dev/config/
export default defineConfig({
    plugins: [react()],
    server: {
        port: 5173,
        proxy: {
            // lets `npm run dev` talk to the backend on :8000 with no CORS setup —
            // the same relative /api/v1 path also works in production via nginx
            // (see nginx.conf), so src/api.ts never needs to know which mode it's in
            "/api": {
                target: "http://localhost:8000",
                changeOrigin: true,
            },
            "/ws": {
                target: "ws://localhost:8000",
                ws: true,
            },
        },
    },
});
