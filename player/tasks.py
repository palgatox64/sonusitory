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
        try:
            results = service.files().list(q=q, fields="files(id)").execute()
            folders = results.get('files', [])
            for folder in folders:
                all_folder_ids.append(folder.get('id'))
                find_folders_recursive(folder.get('id'))
        except Exception as e:
            print(f"Error buscando subcarpetas en {folder_id}: {e}")

    print("Iniciando búsqueda de carpetas...")
    find_folders_recursive(root_folder_id)
    print(f"Se encontraron {len(all_folder_ids)} carpetas.")

    folder_cache = {}
    songs_created_count = 0
    album_folders_with_songs = set()

    print("Buscando y procesando archivos de audio...")
    total_folders = len(all_folder_ids)
    batch_size = 20
    total_song_batches = (total_folders + batch_size - 1) // batch_size
    
    for i in range(0, total_folders, batch_size):
        current_batch_num = (i // batch_size) + 1
        self.update_state(state='PROGRESS', meta={'step': 'songs', 'current': current_batch_num, 'total': total_song_batches})
        
        batch_ids = all_folder_ids[i:i + batch_size]
        parent_queries = ' or '.join([f"'{folder_id}' in parents" for folder_id in batch_ids])
        audio_query = f"({parent_queries}) and (mimeType='audio/mpeg' or mimeType='audio/flac' or mimeType='audio/wav') and trashed=false"
        
        page_token = None
        while True:
            try:
                results = service.files().list(q=audio_query, pageSize=1000, fields="nextPageToken, files(id, name, mimeType, parents)", pageToken=page_token).execute()
                for file_data in results.get('files', []):
                    try:
                        album_folder_id = file_data['parents'][0]
                        album_folders_with_songs.add(album_folder_id)
                        
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
                        track_num, clean_title = clean_and_extract_metadata(file_data.get('name'))

                        _, created = Song.objects.update_or_create(
                            google_file_id=file_data.get('id'), user=user,
                            defaults={
                                'name': file_data.get('name'), 
                                'title': clean_title, 
                                'track_number': track_num, 
                                'mime_type': file_data.get('mime_type', 'application/octet-stream'), # <-- FIX: Added default value
                                'artist': artist_obj, 
                                'album': album_obj
                            }
                        )
                        if created: songs_created_count += 1
                    except Exception as e:
                        print(f"Error procesando archivo {file_data.get('name')}: {e}")
                
                page_token = results.get('nextPageToken', None)
                if not page_token: break
            except Exception as e:
                print(f"Error de API en lote de audio {current_batch_num}: {e}")
                break

    print(f"Buscando portadas en {len(album_folders_with_songs)} carpetas de álbumes...")
    covers_found_count = 0
    total_album_folders = len(album_folders_with_songs)
    
    for index, album_folder_id in enumerate(list(album_folders_with_songs)):
        self.update_state(state='PROGRESS', meta={'step': 'covers', 'current': index + 1, 'total': total_album_folders})
        try:
            image_query = f"'{album_folder_id}' in parents and (mimeType='image/jpeg' or mimeType='image/png') and trashed=false"
            results = service.files().list(q=image_query, pageSize=10, fields="files(id, name)").execute()
            images = results.get('files', [])
            if images:
                cover_file = next((f for f in images if f.get('name', '').lower() in ['cover.jpg', 'cover.png', 'folder.jpg']), images[0])
                album_meta = folder_cache.get(album_folder_id, {})
                Album.objects.filter(user=user, name=album_meta.get('name')).update(cover_image_id=cover_file.get('id'))
                covers_found_count += 1
        except Exception as e:
            print(f"Error buscando portada en carpeta {album_folder_id}: {e}")

    return f"¡Escaneo completado! Se crearon {songs_created_count} canciones nuevas y se encontraron {covers_found_count} portadas."