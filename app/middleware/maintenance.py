import os
from flask import request, session, jsonify

class MaintenanceMiddleware:

    EXEMPT_PATH_PREFIXES = (
        "/static",
        "/health",
        "/maintenance",
        "/maintenance-bypass",
    )

    def __init__(self, wsgi_app, app):
        self.wsgi_app = wsgi_app
        self.app = app

    @staticmethod
    def is_maintenance_mode() -> bool:
        return os.environ.get("MAINTENANCE_MODE", "false").strip().lower() in (
            "1", "true", "yes", "on",
        )

    def _is_exempt(self, path: str) -> bool:
        return any(
            path == prefix or path.startswith(prefix + "/")
            for prefix in self.EXEMPT_PATH_PREFIXES
        )

    def _cors_headers(self, response):
       
        origin = request.headers.get("Origin")
        whitelist = self.app.config.get("CORS_ORIGIN_WHITELIST") or []
        if origin and (origin in whitelist or "*" in whitelist):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Vary"] = "Origin"
        return response

    def __call__(self, environ, start_response):
        with self.app.request_context(environ):
            path = request.path
            method = request.method

            if method == "OPTIONS":
                return self.wsgi_app(environ, start_response)

            if self._is_exempt(path):
                serve_maintenance = False
            elif session.get("maintenance_bypass"):
                serve_maintenance = False
            else:
                serve_maintenance = self.is_maintenance_mode()

            if serve_maintenance:
                payload = {
                    "error": "maintenance",
                    "message": os.environ.get(
                        "MAINTENANCE_MESSAGE",
                        "We're currently performing scheduled maintenance.",
                    ),
                    "retry_after": int(os.environ.get("MAINTENANCE_RETRY_AFTER", 600)),
                    "app_name": os.environ.get(
                        "APP_NAME", self.app.config.get("APP_NAME", "Our App")
                    ),
                }
                response = self.app.make_response((jsonify(payload), 503))
                response = self._cors_headers(response)
                return response(environ, start_response)

        return self.wsgi_app(environ, start_response)