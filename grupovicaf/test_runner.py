"""
Test runner del proyecto: los tests de las apps `web_*` corren siempre contra
`urls_web.py`, sea cual sea el `SITE_ROLE` del proceso (specs/VCF-INFRA,
REQ-INFRA-01).

Sin esto, `SITE_ROLE=lab python manage.py test` carga `urls_lab.py`, donde no
están registrados los namespaces públicos (`web_catalogo`, `web_contacto`...),
y cada `reverse()` de esos tests falla con `NoReverseMatch`. Se resuelve aquí y
no clase por clase para que también cubra los tests que se añadan después.
"""
from django.test import SimpleTestCase, override_settings
from django.test.runner import DiscoverRunner
from django.test.utils import iter_test_cases

URLCONF_WEB = 'grupovicaf.urls_web'


class SiteRoleTestRunner(DiscoverRunner):

    def build_suite(self, *args, **kwargs):
        suite = super().build_suite(*args, **kwargs)
        clases = {type(test) for test in iter_test_cases(suite)}
        for cls in clases:
            if not cls.__module__.startswith('web_') or not issubclass(cls, SimpleTestCase):
                continue
            # Una clase que fija su propio ROOT_URLCONF manda sobre el runner.
            if 'ROOT_URLCONF' in (cls._overridden_settings or {}):
                continue
            override_settings(ROOT_URLCONF=URLCONF_WEB)(cls)
        return suite
