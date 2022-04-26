from django.contrib import admin

from .models import RawPokeData, Evolution

admin.site.register(RawPokeData)
admin.site.register(Evolution)