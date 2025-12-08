from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    full_name: str
    status: str
    is_verified: bool
    is_email_verified: bool
    id: int
    
    def get_status_display(self) -> str: ...
