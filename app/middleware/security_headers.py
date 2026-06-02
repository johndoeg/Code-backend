class SecurityHeadersMiddleware:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        def custom_start_response(status, headers, exc_info=None):
            security_headers = [
                ("X-Content-Type-Options",   "nosniff"),
                ("X-Frame-Options",          "DENY"),
                ("X-XSS-Protection",         "1; mode=block"),
                ("Strict-Transport-Security","max-age=31536000; includeSubDomains"),
                ("Content-Security-Policy",  "default-src 'self'"),
                ("Referrer-Policy",          "strict-origin-when-cross-origin"),
            ]
            headers.extend(security_headers)
            return start_response(status, headers, exc_info)

        return self.app(environ, custom_start_response)