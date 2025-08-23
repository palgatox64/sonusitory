from django.contrib import admin
from .models import UserProfile, GoogleCredential, Artist, Album, Song, Playlist

# Register your models here.

admin.site.register(UserProfile)
admin.site.register(GoogleCredential)
admin.site.register(Artist)
admin.site.register(Album)
admin.site.register(Song)
admin.site.register(Playlist)