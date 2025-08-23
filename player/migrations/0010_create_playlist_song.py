# Generated migration for PlaylistSong
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('player', '0009_playlist_created_at_playlist_songs_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlaylistSong',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_added', models.DateTimeField(auto_now_add=True)),
                ('order', models.IntegerField(default=0)),
                ('playlist', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='player.playlist')),
                ('song', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='player.song')),
            ],
            options={
                'ordering': ['order', 'date_added'],
                'unique_together': {('playlist', 'song')},
            },
        ),
    ]
