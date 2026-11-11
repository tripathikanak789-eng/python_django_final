from django.urls import path
from .views import lex_ai_view

urlpatterns = [
    path("", lex_ai_view, name="lex_ai"),
]
