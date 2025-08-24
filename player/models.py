from django.db import models
from django.contrib.auth.models import User

# Model to store Google Drive API credentials for each user
class GoogleCredential(models.Model):
    # One-to-one relationship with Django's User model
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    # JSON token data for Google Drive API authentication
    token_json = models.TextField() 

    def __str__(self):
        return f"Credenciales de {self.user.username}"


# Extended user profile with additional information
class UserProfile(models.Model):
    # One-to-one relationship with Django's User model
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    # Google Drive root folder ID for music scanning
    google_drive_root_id = models.CharField(max_length=100, null=True, blank=True)
    # User's avatar image URL
    avatar_url = models.URLField(null=True, blank=True)

    def __str__(self):
        return f"Perfil de {self.user.username}"


# Music artist model - each user can have their own artists
class Artist(models.Model):
    # Artist belongs to a specific user (multi-tenancy)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)

    class Meta:
        # Ensure unique artist names per user
        unique_together = ('user', 'name')

    def __str__(self):
        return self.name

# Music album model
class Album(models.Model):
    # Album belongs to a specific user (multi-tenancy)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    # Album belongs to an artist
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name='albums')
    # Google Drive file ID for album cover image
    cover_image_id = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f'{self.name} by {self.artist.name}'

# Main song model representing music files from Google Drive
class Song(models.Model):
    # Song belongs to a specific user (multi-tenancy)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    # Google Drive file ID for the audio file
    google_file_id = models.CharField(max_length=100)
    name = models.CharField(max_length=255) # name of the file
    title = models.CharField(max_length=255, null=True, blank=True) # title from metadata
    track_number = models.PositiveIntegerField(null=True, blank=True) # track number
    # MIME type of the audio file (e.g., audio/mpeg)
    mime_type = models.CharField(max_length=100)
    # Optional relationships to artist and album
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name='songs', null=True, blank=True)
    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name='songs', null=True, blank=True)
    # Timestamps for tracking when songs were added/updated
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Many-to-many relationship for users who liked this song
    liked_by = models.ManyToManyField(User, related_name='liked_songs', through='LikedSong')
    
# User-created playlists model
class Playlist(models.Model):
    # Playlist belongs to a specific user
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    # Many-to-many relationship with songs through intermediate model
    songs = models.ManyToManyField(Song, through='PlaylistSong', blank=True)
    # Optional cover image URL for the playlist
    cover_image_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

# Intermediate model for playlist-song relationship with ordering
class PlaylistSong(models.Model):
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE)
    song = models.ForeignKey(Song, on_delete=models.CASCADE)
    # When the song was added to the playlist
    date_added = models.DateTimeField(auto_now_add=True)
    # Order position within the playlist for custom sorting
    order = models.IntegerField(default=0)

    class Meta:
        # Prevent duplicate songs in the same playlist
        unique_together = ('playlist', 'song')
        # Default ordering by custom order, then by date added
        ordering = ['order', 'date_added']

    def __str__(self):
        return f"{self.playlist.name} - {self.song.title}"

    
# Intermediate model for user-song likes relationship
class LikedSong(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    song = models.ForeignKey(Song, on_delete=models.CASCADE)
    # When the user liked the song
    created_at = models.DateTimeField(auto_now_add=True)
    # Optional field to preserve original like timestamp during migrations
    original_created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        # Prevent users from liking the same song multiple times
        unique_together = ('user', 'song')

    def __str__(self):
        return f"{self.user.username} likes {self.song.title or self.song.name}"