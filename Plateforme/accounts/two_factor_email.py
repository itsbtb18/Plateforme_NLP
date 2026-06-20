"""
2FA Email Utilities - Send OTP via Gmail
"""
import logging

from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


def send_otp_email(user_email, user_name, otp_code):
    """
    Send OTP code via email to the user
    
    Args:
        user_email: Email address to send to
        user_name: User's full name for personalization
        otp_code: The OTP code to send
    
    Returns:
        bool: True if sent successfully
    """
    
    subject = '🔐 Your Security Code - Plateforme NLP'
    
    html_message = f"""
    <html>
        <head>
            <style>
                body {{ font-family: 'Poppins', Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 20px; }}
                .container {{ max-width: 500px; margin: 0 auto; background: white; border-radius: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); overflow: hidden; }}
                .header {{ background: linear-gradient(135deg, #1a73e8 0%, #4285f4 100%); padding: 30px; text-align: center; }}
                .header h1 {{ color: white; margin: 0; font-size: 24px; }}
                .content {{ padding: 30px; }}
                .greeting {{ color: #202124; font-size: 16px; margin-bottom: 20px; }}
                .otp-box {{ background: linear-gradient(135deg, rgba(26, 115, 232, 0.1) 0%, rgba(52, 168, 83, 0.1) 100%); border: 2px solid #1a73e8; border-radius: 12px; padding: 20px; text-align: center; margin: 20px 0; }}
                .otp-code {{ font-size: 32px; font-weight: 700; color: #1a73e8; letter-spacing: 4px; margin: 10px 0; font-family: 'Courier New', monospace; }}
                .timer {{ color: #5f6368; font-size: 14px; margin-top: 10px; }}
                .warning {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 12px; margin: 20px 0; border-radius: 4px; font-size: 14px; color: #856404; }}
                .footer {{ background: #f8f9fa; padding: 20px; text-align: center; font-size: 12px; color: #80868b; border-top: 1px solid #e8eaed; }}
                a {{ color: #1a73e8; text-decoration: none; }}
                a:hover {{ text-decoration: underline; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔐 Security Code</h1>
                </div>
                <div class="content">
                    <p class="greeting">Hi {user_name},</p>
                    
                    <p>Your Plateforme NLP security code is:</p>
                    
                    <div class="otp-box">
                        <div class="otp-code">{otp_code}</div>
                        <div class="timer">⏱️ Valid for 5 minutes</div>
                    </div>
                    
                    <p style="color: #202124; line-height: 1.6;">
                        If you didn't request this code, please ignore this email. Your account remains secure.
                    </p>
                    
                    <div class="warning">
                        <strong>🛡️ Security Tip:</strong> Never share this code with anyone. We will never ask for this code via email.
                    </div>
                </div>
                <div class="footer">
                    <p>© 2026 Plateforme NLP. All rights reserved.</p>
                    <p><a href="https://plateforme-nlp.com">Visit Our Platform</a></p>
                </div>
            </div>
        </body>
    </html>
    """
    
    plain_message = f"""
    Hi {user_name},
    
    Your Plateforme NLP security code is:
    
    {otp_code}
    
    Valid for 5 minutes.
    
    If you didn't request this code, please ignore this email.
    
    Security Tip: Never share this code with anyone.
    
    © 2026 Plateforme NLP
    """
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL or 'noreply@plateforme-nlp.com',
            recipient_list=[user_email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        logger.error("Error sending OTP email: %s", e, exc_info=True)
        return False
