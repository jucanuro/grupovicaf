from django.apps import AppConfig


class WebCatalogoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "web_catalogo"

    def ready(self):
        from . import signals  # noqa: F401
