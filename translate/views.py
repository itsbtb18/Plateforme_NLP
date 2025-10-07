


from django.shortcuts import redirect
from django.utils import translation
from django.conf import settings
from django.utils.translation import activate
from django.http import HttpResponseRedirect


def switch_language(request):
    lang_code = request.GET.get('language')
    next_url = request.META.get('HTTP_REFERER', '/')

    if lang_code in dict(settings.LANGUAGES).keys():
        # Active la langue immédiatement
        translation.activate(lang_code)

        # Crée une réponse de redirection
        response = HttpResponseRedirect(next_url)

        # Sauvegarde la langue dans la session
        if hasattr(request, 'session'):
            request.session[settings.LANGUAGE_COOKIE_NAME] = lang_code

        # Sauvegarde aussi dans le cookie pour que le middleware le retrouve
        response.set_cookie(settings.LANGUAGE_COOKIE_NAME, lang_code)

        return response

    return HttpResponseRedirect(next_url)