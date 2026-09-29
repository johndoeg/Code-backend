from flask import request, jsonify, g, current_app, render_template
from datetime import datetime
import ipaddress

def maintenance_mode_middleware(app):
    
    @app.before_request
    def check_maintenance():
        if request.path in ['/health', '/api/health', '/', '/favicon.ico', '/static']:
            return
        
        if not request.path.startswith('/api'):
            return
        
        if not current_app.config['MAINTENANCE_MODE']:
            return
        
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if client_ip:
            try:
                client_ip_obj = ipaddress.ip_address(client_ip.split(',')[0].strip())
                for allowed in current_app.config['MAINTENANCE_WHITELIST']:
                    if '/' in allowed:
                        if client_ip_obj in ipaddress.ip_network(allowed, strict=False):
                            return
                    elif client_ip == allowed:
                        return
            except ValueError:
                pass
        
        bypass_token = request.headers.get('X-Maintenance-Bypass')
        if bypass_token and bypass_token == current_app.config['MAINTENANCE_BYPASS_TOKEN']:
            return
        
        if request.accept_mimetypes.accept_json:
            return jsonify({
                "success": False,
                "message": current_app.config['MAINTENANCE_MESSAGE'],
                "maintenance": True,
                "retry_after": current_app.config['MAINTENANCE_RETRY_AFTER'],
                "timestamp": datetime.utcnow().isoformat()
            }), 503
        
        return render_template('maintenance.html',
                            message=current_app.config['MAINTENANCE_MESSAGE'],
                            retry_after=current_app.config['MAINTENANCE_RETRY_AFTER'],
                            app_name=current_app.config['APP_NAME']), 503

def api_versioning_middleware(app):
    
    @app.before_request
    def validate_api_version():
        if not request.path.startswith('/api'):
            return
        
        path_parts = request.path.strip('/').split('/')
        version = None
        
        if len(path_parts) >= 2 and path_parts[0] == 'api' and path_parts[1].startswith('v'):
            version = path_parts[1]
        elif path_parts[0].startswith('v'):
            version = path_parts[0]
        
        header_version = request.headers.get('X-API-Version')
        if header_version and not version:
            version = header_version
        
        if version and version not in current_app.config['API_VERSIONS']:
            if version in current_app.config['DEPRECATED_VERSIONS']:
                current_app.logger.warning(f"Deprecated API version: {version}")
                response = jsonify({
                    "success": True,
                    "message": f"API version {version} is deprecated",
                    "deprecation": True,
                    "sunset": "2024-12-31"
                })
                response.headers['Deprecation'] = 'true'
                response.headers['Sunset'] = '2024-12-31'
                return response
            else:
                return jsonify({
                    "success": False,
                    "message": f"Unsupported API version: {version}"
                }), 400
        
        g.api_version = version or current_app.config['API_VERSION']
    
    @app.after_request
    def add_version_headers(response):
        if hasattr(g, 'api_version'):
            response.headers['X-API-Version'] = g.api_version
        response.headers['X-App-Version'] = current_app.config['APP_VERSION']
        return response