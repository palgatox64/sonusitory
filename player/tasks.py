import json
import re 
from celery import shared_task
from django.contrib.auth.models import User
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from .models import Song, Artist, Album, UserProfile, GoogleCredential

def clean_and_extract_metadata(filename):

    name_without_ext = filename.rsplit('.', 1)[0]
    
    track_num = None
    clean_title = name_without_ext

    match = re.match(r'^\s*(\d+)\s*[-._]*\s*(.*)', name_without_ext)
    if match:
        track_num = int(match.group(1))
        clean_title = match.group(2)

    clean_title = re.sub(r'[-_]', ' ', clean_title)

    clean_title = ' '.join(clean_title.split())
    
    return track_num, clean_title

@shared_task(bind=True)
def scan_user_library(self, user_id):

    try:
        user = User.objects.get(id=user_id)
        creds_model = GoogleCredential.objects.get(user=user)
        creds = Credentials.from_authorized_user_info(json.loads(creds_model.token_json))
        profile = UserProfile.objects.get(user=user)
        root_folder_id = profile.google_drive_root_id
        if not root_folder_id:
            return f"Error: El usuario {user.username} no tiene una carpeta raíz configurada."
    except Exception as e:
        self.update_state(state='FAILURE', meta={'exc_type': type(e).__name__, 'exc_message': str(e)})
        return f"Error al iniciar: {e}"

    service = build('drive', 'v3', credentials=creds)

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

    folder_cache = {}
    songs_processed_count = 0
    total_folders = len(all_folder_ids)
    batch_size = 20
    total_batches = (total_folders // batch_size) + 1 if total_folders > 0 else 1
    
    for i in range(0, total_folders, batch_size):
        current_batch_num = (i // batch_size) + 1
        self.update_state(state='PROGRESS', meta={'current_batch': current_batch_num, 'total_batches': total_batches})
        
        batch_ids = all_folder_ids[i:i + batch_size]
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

                        track_num, clean_title = clean_and_extract_metadata(file_data.get('name'))
                        
                        artist_obj, _ = Artist.objects.get_or_create(name=artist_name, user=user)
                        album_obj, _ = Album.objects.get_or_create(name=album_name, artist=artist_obj, user=user)
                        
                        Song.objects.update_or_create(
                            google_file_id=file_data.get('id'),
                            user=user,
                            defaults={
                                'name': file_data.get('name'),
                                'title': clean_title,
                                'track_number': track_num,
                                'mime_type': file_data.get('mime_type', 'application/octet-stream'),
                                'artist': artist_obj,
                                'album': album_obj,
                            }
                        )
                        songs_processed_count += 1
                    except Exception as e:
                        print(f'Error procesando el archivo {file_data.get("name")}: {e}')

                page_token = results.get('nextPageToken', None)
                if page_token is None:
                    break
            except Exception as e:
                print(f'Error en la API en el lote {i // batch_size + 1}: {e}')
                break

    return f"¡Escaneo completado! Se procesaron {songs_processed_count} canciones."