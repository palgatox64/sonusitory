import os
import json
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from player.models import Song, Artist, Album, UserProfile, GoogleCredential

class Command(BaseCommand):
    help = 'Scans a specific user\'s Google Drive folder and updates the database.'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='The username of the user to scan for.')

    def handle(self, *args, **options):
        username = options['username']
        self.stdout.write(self.style.NOTICE(f'Starting intelligent library scan for user: {username}...'))

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User "{username}" not found.'))
            return

        try:
            creds_model = GoogleCredential.objects.get(user=user)
            creds = Credentials.from_authorized_user_info(json.loads(creds_model.token_json))
            profile = UserProfile.objects.get(user=user)
            root_folder_id = profile.google_drive_root_id
            if not root_folder_id:
                raise UserProfile.DoesNotExist # Para que el error sea el mismo
        except (GoogleCredential.DoesNotExist, UserProfile.DoesNotExist):
            self.stdout.write(self.style.ERROR(f'Google credentials or root folder not set for {username}. Please configure them through the web interface.'))
            return

        service = build('drive', 'v3', credentials=creds)

        self.stdout.write('Finding all folders...')
        all_folder_ids = [root_folder_id]
        def find_folders_recursive(folder_id):
            q = f"mimeType='application/vnd.google-apps.folder' and '{folder_id}' in parents and trashed=false"
            results = service.files().list(q=q, fields="files(id)").execute()
            folders = results.get('files', [])
            for folder in folders:
                folder_id = folder.get('id')
                all_folder_ids.append(folder_id)
                find_folders_recursive(folder_id)
        
        find_folders_recursive(root_folder_id)
        self.stdout.write(f'Found {len(all_folder_ids)} total folders.')

        folder_cache = {}
        songs_processed_count = 0
        
        self.stdout.write('Finding and processing audio files in batches...')
        batch_size = 20
        for i in range(0, len(all_folder_ids), batch_size):
            batch_ids = all_folder_ids[i:i + batch_size]
            self.stdout.write(f'--- Processing Batch {i // batch_size + 1} of {len(all_folder_ids) // batch_size + 1} ---')

            parent_queries = ' or '.join([f"'{folder_id}' in parents" for folder_id in batch_ids])
            audio_query = f"({parent_queries}) and (mimeType='audio/mpeg' or mimeType='audio/flac' or mimeType='audio/wav') and trashed=false"

            page_token = None
            while True:
                try:
                    results = service.files().list(
                        q=audio_query, pageSize=1000,
                        fields="nextPageToken, files(id, name, mimeType, parents)",
                        pageToken=page_token
                    ).execute()
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'API error in batch {i // batch_size + 1}: {e}'))
                    break
                
                audio_files_in_batch = results.get('files', [])
                
                for file_data in audio_files_in_batch:
                    try:
                        album_folder_id = file_data['parents'][0]
                        if album_folder_id not in folder_cache:
                            folder_cache[album_folder_id] = service.files().get(fileId=album_folder_id, fields='id, name, parents').execute()
                        album_folder_meta = folder_cache[album_folder_id]
                        album_name = album_folder_meta['name']

                        if 'parents' not in album_folder_meta: continue
                        artist_folder_id = album_folder_meta['parents'][0]
                        if artist_folder_id not in folder_cache:
                            folder_cache[artist_folder_id] = service.files().get(fileId=artist_folder_id, fields='id, name').execute()
                        artist_name = folder_cache[artist_folder_id]['name']

                        artist_obj, _ = Artist.objects.get_or_create(name=artist_name, user=user)
                        album_obj, _ = Album.objects.get_or_create(name=album_name, artist=artist_obj, user=user)
                        
                        Song.objects.update_or_create(
                            google_file_id=file_data.get('id'),
                            user=user,
                            defaults={
                                'name': file_data.get('name'),
                                'mime_type': file_data.get('mime_type', 'application/octet-stream'),
                                'artist': artist_obj,
                                'album': album_obj,
                            }
                        )
                        songs_processed_count += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'Could not process file {file_data.get("name")}: {e}'))

                page_token = results.get('nextPageToken', None)
                if page_token is None:
                    break

        self.stdout.write(self.style.SUCCESS(f'\nIntelligent scan complete! Processed {songs_processed_count} songs.'))