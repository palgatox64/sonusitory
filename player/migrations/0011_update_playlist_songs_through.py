# Migration to update playlist songs field to use through
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('player', '0010_create_playlist_song'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='playlist',
            name='songs',
        ),
        migrations.AddField(
            model_name='playlist',
            name='songs',
            field=models.ManyToManyField(blank=True, through='player.PlaylistSong', to='player.song'),
        ),
    ]
