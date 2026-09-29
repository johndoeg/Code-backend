class SecurityHeadersMiddleware:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        is_docs_path = path.startswith(("/apidocs", "/flasgger_static", "/apispec"))

        def custom_start_response(status, headers, exc_info=None):
            if is_docs_path:
                csp = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
            else:
                csp = "default-src 'self'"

            security_headers = [
                ("X-Content-Type-Options",   "nosniff"),
                ("X-Frame-Options",          "DENY"),
                ("X-XSS-Protection",         "1; mode=block"),
                ("Strict-Transport-Security","max-age=31536000; includeSubDomains"),
                ("Content-Security-Policy",  csp),
                ("Referrer-Policy",          "strict-origin-when-cross-origin"),
            ]
            headers.extend(security_headers)
            return start_response(status, headers, exc_info)

        return self.app(environ, custom_start_response)