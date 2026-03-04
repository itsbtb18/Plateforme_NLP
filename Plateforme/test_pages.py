import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'Plateforme.settings'
django.setup()

from django.conf import settings
settings.ALLOWED_HOSTS = ['*']

from django.test import Client
from django.contrib.auth import get_user_model

User = get_user_model()
admin = User.objects.filter(is_superuser=True).first()

c = Client()
c.force_login(admin)

pages = [
    ('dashboard', '/dashboard/'),
    ('users', '/admin/users/'),
    ('publications', '/admin/publications/'),
    ('corpora', '/admin/corpora/'),
    ('tools', '/admin/tools/'),
    ('projects', '/admin/projects/'),
    ('courses', '/admin/courses/'),
    ('forum', '/admin/forum/'),
    ('institutions', '/admin/institutions/'),
    ('news', '/admin/news/'),
    ('calls', '/admin/calls/'),
    ('statistics', '/admin/statistics/'),
    ('settings', '/admin/settings/'),
    ('security', '/admin/security/'),
    ('users_new', '/admin/users/new/'),
]

ok = 0
fail = 0
for name, url in pages:
    try:
        r = c.get(url, follow=True)
        status = r.status_code
        if status == 200:
            ok += 1
            print(f'OK   {name:20s} {url}')
        else:
            fail += 1
            print(f'FAIL {name:20s} {url} => {status}')
    except Exception as e:
        fail += 1
        print(f'ERR  {name:20s} {url} => {type(e).__name__}: {e}')

print(f'\n{ok}/{ok+fail} pages OK')
