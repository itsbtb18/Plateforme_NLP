

import re

from django.shortcuts import redirect
from django.utils import translation
from django.conf import settings
from django.utils.translation import activate
from django.http import HttpResponseRedirect


def switch_language(request):
    lang_code = request.GET.get('language')
    next_url = request.META.get('HTTP_REFERER', '/')

    if lang_code in dict(settings.LANGUAGES).keys():
        translation.activate(lang_code)

        # Replace the language prefix in the URL so i18n_patterns picks up the new language
        lang_codes = '|'.join(dict(settings.LANGUAGES).keys())
        next_url = re.sub(r'^(https?://[^/]+)?/(' + lang_codes + r')/', r'\1/' + lang_code + '/', next_url)

        response = HttpResponseRedirect(next_url)

        if hasattr(request, 'session'):
            request.session[settings.LANGUAGE_COOKIE_NAME] = lang_code

        response.set_cookie(settings.LANGUAGE_COOKIE_NAME, lang_code)

        return response

    return HttpResponseRedirect(next_url)