from flask import jsonify
import os

class MaintenanceMiddleware:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        if os.environ.get("MAINTENANCE_MODE") == "true":
            response = jsonify({
                "error": "maintenance",
                "message": "Service is under maintenance. Please try again later.",
                "retry_after": 3600
            })
            response.status_code = 503
            response.headers["Retry-After"] = "3600"
            return response(environ, start_response)

        return self.app(environ, start_response)