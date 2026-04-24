from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0012_userprofile"),
    ]

    operations = [
        migrations.AddField(
            model_name="twofactorauth",
            name="method",
            field=models.CharField(
                choices=[("email_otp", "Email OTP"), ("totp", "TOTP Authenticator")],
                default="email_otp",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="twofactorauth",
            name="totp_secret",
            field=models.CharField(blank=True, max_length=64),
        ),
    ]
