import json
import re
from celery import shared_task
from django.contrib.auth.models import User
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from .models import Song, Artist, Album, UserProfile, GoogleCredential

import json
import re
from celery import shared_task
from django.contrib.auth.models import User
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from .models import Song, Artist, Album, UserProfile, GoogleCredential

def clean_and_extract_metadata(filename):
    """
    Extract track number and clean title from filename
    Handles various filename formats with track numbers and separators
    
    Args:
        filename (str): Original filename from Google Drive
        
    Returns:
        tuple: (track_number, clean_title) where track_number can be None
    """
    name_without_ext = filename.rsplit('.', 1)[0]
    track_num = None
    clean_title = name_without_ext
    
    # Extract track number from beginning of filename (e.g., "01 - Song Title")
    match = re.match(r'^\s*(\d+)\s*[-._]*\s*(.*)', name_without_ext)
    if match:
        track_num = int(match.group(1))
        clean_title = match.group(2)
    
    # Clean up separators and extra whitespace
    clean_title = re.sub(r'[-_]', ' ', clean_title)
    clean_title = ' '.join(clean_title.split())
    return track_num, clean_title

def should_skip_folder(folder_name):
    """
    Determine if a folder should be skipped during scanning
    Skips system folders, hidden folders, and temporary directories
    
    Args:
        folder_name (str): Name of the folder to evaluate
        
    Returns:
        bool: True if folder should be skipped, False otherwise
    """
    skip_patterns = [
        r'^\..*',  # Hidden folders (starting with dot)
        r'^__.*',  # Python cache folders
        r'^temp.*',  # Temporary folders
        r'^cache.*',  # Cache directories
        r'^backup.*',  # Backup folders
        r'^old.*',  # Old/archive folders
        r'trash|recycle|papelera',  # Trash/recycle bins
        r'system|windows|program',  # System directories
    ]
    folder_lower = folder_name.lower().strip()
    return any(re.search(pattern, folder_lower) for pattern in skip_patterns)

def get_folder_path_from_root(service, folder_id, root_folder_id, folder_cache=None):
    """
    Build the full path from a folder to the root folder in Google Drive
    Uses caching to minimize API calls for repeated folder lookups
    
    Args:
        service: Google Drive API service instance
        folder_id (str): Starting folder ID
        root_folder_id (str): Root folder ID to stop traversal
        folder_cache (dict): Cache for folder metadata to reduce API calls
        
    Returns:
        list: List of folder names from root to target folder
    """
    if folder_cache is None:
        folder_cache = {}
    
    path = []
    current_folder_id = folder_id
    
    # Traverse up the folder hierarchy until reaching root
    while current_folder_id and current_folder_id != root_folder_id:
        try:
            # Use cache to avoid repeated API calls
            if current_folder_id not in folder_cache:
                folder_cache[current_folder_id] = service.files().get(
                    fileId=current_folder_id, 
                    fields='id, name, parents'
                ).execute()
            
            folder_info = folder_cache[current_folder_id]
            folder_name = folder_info.get('name', '')
            path.insert(0, folder_name)
            
            # Move to parent folder
            parents = folder_info.get('parents', [])
            if parents:
                current_folder_id = parents[0]
            else:
                break
                
        except Exception as e:
            print(f"Error obteniendo ruta para carpeta {current_folder_id}: {e}")
            break
    
    return path

def create_hierarchical_structure(path_parts, user):
    """
    Create Artist and Album objects from folder path hierarchy
    Implements intelligent mapping based on folder depth:
    - 1 folder: Use same name for both artist and album
    - 2 folders: First is artist, second is album
    - 3+ folders: Second-to-last is artist, last is album
    
    Args:
        path_parts (list): List of folder names from root to song location
        user: Django User instance for ownership
        
    Returns:
        tuple: (Artist instance, Album instance) or (None, None) if creation fails
    """
    if not path_parts:
        return None, None
    
    # Filter out empty folder names
    filtered_parts = [part.strip() for part in path_parts if part.strip()]
    
    if len(filtered_parts) == 0:
        return None, None
    elif len(filtered_parts) == 1:
        # Single folder: use as both artist and album name
        artist_name = filtered_parts[0]
        album_name = filtered_parts[0]
    elif len(filtered_parts) == 2:
        # Two folders: first is artist, second is album
        artist_name = filtered_parts[0]
        album_name = filtered_parts[1]
    else:
        # Multiple folders: assume artist/album are the last two
        artist_name = filtered_parts[-2]
        album_name = filtered_parts[-1]
    
    # Create or get existing Artist and Album instances
    artist_obj, _ = Artist.objects.get_or_create(name=artist_name, user=user)
    album_obj, _ = Album.objects.get_or_create(name=album_name, artist=artist_obj, user=user)
    
    return artist_obj, album_obj

@shared_task(bind=True)
def scan_user_library(self, user_id, scan_mode='full'):
    """
    Celery task to scan user's Google Drive library for music files
    Supports multiple scan modes: full, quick, and covers_only
    
    Args:
        self: Celery task instance for state updates
        user_id (int): ID of the user whose library to scan
        scan_mode (str): Scanning mode - 'full', 'quick', or 'covers_only'
        
    Returns:
        str: Success message with statistics about files processed
    """
    try:
        # Initialize user credentials and Google Drive service
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
    folder_cache = {}
    songs_created_count = 0
    covers_found_count = 0
    album_folders_with_songs = set()

    # FULL SCAN MODE: Complete library scan including all audio files
    if scan_mode == 'full':
        self.update_state(state='PROGRESS', meta={'step': 'searching_audio_files'})
        
        # Get existing file IDs to avoid duplicates
        existing_file_ids = set(Song.objects.filter(user=user).values_list('google_file_id', flat=True))
        
        # Query for all audio files in Google Drive
        audio_query = f"(mimeType='audio/mpeg' or mimeType='audio/flac' or mimeType='audio/wav') and trashed=false"
        
        page_token = None
        files_processed = 0
        
        # Process files in paginated batches
        while True:
            try:
                self.update_state(state='PROGRESS', meta={'step': 'processing_audio_files', 'current': files_processed})
                
                results = service.files().list(
                    q=audio_query, 
                    pageSize=500,
                    fields="nextPageToken, files(id, name, mimeType, parents)", 
                    pageToken=page_token
                ).execute()
                
                for file_data in results.get('files', []):
                    files_processed += 1
                    
                    # Skip files already in database
                    if file_data.get('id') in existing_file_ids:
                        continue
                    
                    try:
                        parents = file_data.get('parents', [])
                        if not parents:
                            continue
                        
                        immediate_parent_id = parents[0]
                        
                        # Build folder path from root to file location
                        folder_path = get_folder_path_from_root(
                            service, immediate_parent_id, root_folder_id, folder_cache
                        )
                        
                        if not folder_path:
                            continue
                        
                        # Create artist and album from folder structure
                        artist_obj, album_obj = create_hierarchical_structure(folder_path, user)
                        
                        if not artist_obj or not album_obj:
                            print(f"No se pudo crear estructura para {file_data.get('name')} en ruta: {' / '.join(folder_path)}")
                            continue
                        
                        # Track folders that contain songs for cover art search
                        album_folders_with_songs.add(immediate_parent_id)
                        
                        # Extract metadata from filename
                        track_num, clean_title = clean_and_extract_metadata(file_data.get('name'))

                        # Create or update song record
                        _, created = Song.objects.update_or_create(
                            google_file_id=file_data.get('id'), 
                            user=user,
                            defaults={
                                'name': file_data.get('name'), 
                                'title': clean_title, 
                                'track_number': track_num, 
                                'mime_type': file_data.get('mimeType', 'application/octet-stream'), 
                                'artist': artist_obj, 
                                'album': album_obj
                            }
                        )
                        
                        if created:
                            songs_created_count += 1
                            
                    except Exception as e:
                        print(f"Error procesando archivo {file_data.get('name')}: {e}")
                
                page_token = results.get('nextPageToken', None)
                if not page_token: 
                    break
                    
            except Exception as e:
                print(f"Error de API en búsqueda de archivos: {e}")
                break
                
    # QUICK SCAN MODE: Only scan for new files not in database
    elif scan_mode == 'quick':
        self.update_state(state='PROGRESS', meta={'step': 'getting_existing_files'})
        existing_file_ids = set(Song.objects.filter(user=user).values_list('google_file_id', flat=True))
        
        self.update_state(state='PROGRESS', meta={'step': 'searching_new_files'})
        
        # Same audio query but with smaller page size for faster processing
        audio_query = f"(mimeType='audio/mpeg' or mimeType='audio/flac' or mimeType='audio/wav') and trashed=false"
        
        page_token = None
        files_processed = 0
        
        while True:
            try:
                results = service.files().list(
                    q=audio_query, 
                    pageSize=200,  # Smaller batch size for quicker response
                    fields="nextPageToken, files(id, name, mimeType, parents)", 
                    pageToken=page_token
                ).execute()
                
                for file_data in results.get('files', []):
                    files_processed += 1
                    if files_processed % 100 == 0:
                        self.update_state(state='PROGRESS', meta={'step': 'processing_new_files', 'current': files_processed})
                    
                    # Skip existing files (main difference from full scan)
                    if file_data.get('id') in existing_file_ids:
                        continue
                        
                    try:
                        parents = file_data.get('parents', [])
                        if not parents:
                            continue
                        
                        immediate_parent_id = parents[0]
                        
                        folder_path = get_folder_path_from_root(
                            service, immediate_parent_id, root_folder_id, folder_cache
                        )
                        
                        if not folder_path:
                            continue
                        
                        artist_obj, album_obj = create_hierarchical_structure(folder_path, user)
                        
                        if not artist_obj or not album_obj:
                            continue
                        
                        album_folders_with_songs.add(immediate_parent_id)
                        
                        track_num, clean_title = clean_and_extract_metadata(file_data.get('name'))

                        _, created = Song.objects.update_or_create(
                            google_file_id=file_data.get('id'), 
                            user=user,
                            defaults={
                                'name': file_data.get('name'), 
                                'title': clean_title, 
                                'track_number': track_num, 
                                'mime_type': file_data.get('mimeType', 'application/octet-stream'), 
                                'artist': artist_obj, 
                                'album': album_obj
                            }
                        )
                        
                        if created:
                            songs_created_count += 1
                            
                    except Exception as e:
                        print(f"Error procesando archivo {file_data.get('name')}: {e}")
                
                page_token = results.get('nextPageToken', None)
                if not page_token: 
                    break
                    
            except Exception as e:
                print(f"Error de API en búsqueda rápida: {e}")
                break
                
    # COVERS ONLY MODE: Only scan for album cover images
    elif scan_mode == 'covers_only':
        self.update_state(state='PROGRESS', meta={'step': 'getting_existing_albums'})
        albums_without_covers = Album.objects.filter(user=user, cover_image_id__isnull=True)
        
        # Create mapping of album names to album objects
        album_name_mapping = {}
        for album in albums_without_covers:
            album_name_mapping[album.name] = album
        
        # Find folder IDs for albums that need covers
        album_folder_ids = []
        album_names = list(album_name_mapping.keys())
        
        # Process album names in batches to avoid query length limits
        for i in range(0, len(album_names), 10):
            batch_names = album_names[i:i + 10]
            # Escape single quotes in album names for Google Drive query
            name_queries = ' or '.join([f"name='{name.replace(chr(39), chr(39)+chr(39))}'" for name in batch_names])
            folder_query = f"mimeType='application/vnd.google-apps.folder' and ({name_queries}) and trashed=false"
            
            try:
                results = service.files().list(q=folder_query, pageSize=100, fields="files(id, name)").execute()
                for folder in results.get('files', []):
                    if folder['name'] in album_name_mapping:
                        album_folder_ids.append(folder['id'])
                        folder_cache[folder['id']] = folder
            except Exception as e:
                print(f"Error buscando carpetas de álbumes: {e}")
        
        album_folders_with_songs = set(album_folder_ids)

    # COVER ART SEARCH: Search for album cover images in album folders
    if album_folders_with_songs:
        total_album_folders = len(album_folders_with_songs)
        
        for index, album_folder_id in enumerate(list(album_folders_with_songs)):
            self.update_state(state='PROGRESS', meta={'step': 'covers', 'current': index + 1, 'total': total_album_folders})
            try:
                # Get folder metadata if not cached
                if album_folder_id not in folder_cache:
                    folder_cache[album_folder_id] = service.files().get(fileId=album_folder_id, fields='id, name').execute()

                # Search for image files in the album folder
                image_query = f"'{album_folder_id}' in parents and (mimeType='image/jpeg' or mimeType='image/png') and trashed=false"
                results = service.files().list(q=image_query, pageSize=10, fields="files(id, name)").execute()
                images = results.get('files', [])
                
                if images:
                    # Prioritize common cover art filenames, fallback to first image found
                    cover_file = next((f for f in images if f.get('name', '').lower() in ['cover.jpg', 'cover.png', 'folder.jpg', 'albumart.jpg']), images[0])
                    album_meta = folder_cache.get(album_folder_id, {})
                    
                    # Update album with cover image ID
                    Album.objects.filter(user=user, name=album_meta.get('name')).update(cover_image_id=cover_file.get('id'))
                    covers_found_count += 1
            except Exception as e:
                print(f"Error buscando portada en carpeta {album_folder_id}: {e}")
    
    # Return appropriate success message based on scan mode
    if scan_mode == 'quick':
        songs_text = "canción nueva" if songs_created_count == 1 else "canciones nuevas"
        songs_verb = "añadió" if songs_created_count == 1 else "añadieron"
        covers_text = "portada nueva" if covers_found_count == 1 else "portadas nuevas"
        covers_verb = "encontró" if covers_found_count == 1 else "encontraron"
        return f"¡Búsqueda rápida completada! Se {songs_verb} {songs_created_count} {songs_text} y se {covers_verb} {covers_found_count} {covers_text}."
    elif scan_mode == 'covers_only':
        covers_text = "portada nueva" if covers_found_count == 1 else "portadas nuevas"
        covers_verb = "encontró" if covers_found_count == 1 else "encontraron"
        return f"¡Búsqueda de portadas completada! Se {covers_verb} {covers_found_count} {covers_text}."
    else:
        songs_text = "canción nueva" if songs_created_count == 1 else "canciones nuevas"
        songs_verb = "añadió" if songs_created_count == 1 else "añadieron"
        covers_text = "portada nueva" if covers_found_count == 1 else "portadas nuevas"
        covers_verb = "encontró" if covers_found_count == 1 else "encontraron"
        return f"¡Escaneo completo! Se {songs_verb} {songs_created_count} {songs_text} y se {covers_verb} {covers_found_count} {covers_text}."