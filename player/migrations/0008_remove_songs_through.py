# Manually created migration to remove through relationship

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('player', '0007_playlist_playlistsong_playlist_songs'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='playlist',
            name='songs',
        ),
        migrations.DeleteModel(
            name='PlaylistSong',
        ),
    ]
