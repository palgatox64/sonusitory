
from django.db import models
from django.contrib.auth.models import User

class GoogleCredential(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    token_json = models.TextField() 

    def __str__(self):
        return f"Credenciales de {self.user.username}"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    google_drive_root_id = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f"Perfil de {self.user.username}"


class Artist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)

    class Meta:
        unique_together = ('user', 'name')

    def __str__(self):
        return self.name

class Album(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name='albums')
    cover_image_id = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f'{self.name} by {self.artist.name}'

class Song(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    google_file_id = models.CharField(max_length=100)
    name = models.CharField(max_length=255) # name of the file
    title = models.CharField(max_length=255, null=True, blank=True) # title from metadata
    track_number = models.PositiveIntegerField(null=True, blank=True) # track number
    mime_type = models.CharField(max_length=100)
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name='songs', null=True, blank=True)
    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name='songs', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('user', 'google_file_id')

    def __str__(self):
        return self.name