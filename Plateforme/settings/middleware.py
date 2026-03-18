"""
Middleware for applying global settings
"""
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.html import escape
from .utils import is_maintenance_mode, get_global_settings


class MaintenanceModeMiddleware:
    """
    Middleware to handle maintenance mode
    Shows maintenance message to non-staff users
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Skip maintenance mode for staff/admin users
        if request.user.is_staff or request.user.is_superuser:
            return self.get_response(request)
        
        # Check if maintenance mode is enabled
        if is_maintenance_mode():
            settings = get_global_settings()
            
            # Create a simple maintenance response
            html = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Maintenance Mode</title>
                <style>
                    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        min-height: 100vh;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        padding: 20px;
                    }}
                    .container {{
                        text-align: center;
                        background: white;
                        padding: 40px;
                        border-radius: 10px;
                        box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                        max-width: 600px;
                    }}
                    h1 {{
                        color: #333;
                        margin-bottom: 20px;
                        font-size: 2em;
                    }}
                    .emoji {{
                        font-size: 4em;
                        margin-bottom: 20px;
                    }}
                    p {{
                        color: #666;
                        line-height: 1.6;
                        margin-bottom: 20px;
                        font-size: 1.1em;
                    }}
                    .info {{
                        background: #f5f5f5;
                        padding: 20px;
                        border-radius: 5px;
                        margin: 20px 0;
                        color: #555;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="emoji">🔧</div>
                    <h1>Maintenance in Progress</h1>
                    <p>We're working to improve your experience.</p>
                    <div class="info">
                        {escape(settings.maintenance_message) if settings.maintenance_message else 'The platform will be back online shortly.'}
                    </div>
                    <p style="color: #999; font-size: 0.9em; margin-top: 30px;">
                        If you have any questions, please contact us at {escape(settings.admin_email)}
                    </p>
                </div>
            </body>
            </html>
            """
            return HttpResponse(html, status=503)
        
        return self.get_response(request)


class SettingsCacheInvalidationMiddleware:
    """Middleware to invalidate settings cache on admin changes"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        return self.get_response(request)
