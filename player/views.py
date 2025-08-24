# Django core imports
from django.shortcuts import render, redirect, get_object_or_404
from django.http import StreamingHttpResponse, HttpResponse, Http404
from django.contrib.auth.decorators import login_required
# Google OAuth and Drive API imports
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
# Local model imports
from .models import UserProfile, GoogleCredential, Artist, Album, Song, LikedSong, Playlist, PlaylistSong
from django.http import JsonResponse
# Celery task imports for background processing
from .tasks import scan_user_library
from celery.result import AsyncResult
from django.templatetags.static import static
import os
import io
import json
import requests
import requests
from django.utils import timezone
from django.db import models

# Google OAuth configuration
CLIENT_SECRETS_FILE = os.path.join(os.path.dirname(__file__), '..', 'credentials', 'client_secret.json')
# Read-only access to Google Drive files
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
# Allow insecure transport for development (localhost)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'


@login_required
def google_login(request):
    """
    Initiates Google OAuth flow for Drive API access.
    Redirects to already_linked page if user already has credentials.
    """
    if GoogleCredential.objects.filter(user=request.user).exists():
        return render(request, 'player/already_linked.html')

    # Create OAuth flow with Google Drive read-only scope
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri='http://localhost:8000/callback'
    )
    # Generate authorization URL with offline access for refresh tokens
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'  # Force consent screen to ensure refresh token
    )
    context = {'auth_url': authorization_url}
    
    # Return partial template for HTMX requests
    if request.htmx:
        return render(request, 'player/partials/cloud_login_content.html', context)
        
    return render(request, 'player/cloud_login.html', context)

@login_required
def account(request):
    """
    Displays user account page showing Google Drive connection status.
    """
    has_credentials = GoogleCredential.objects.filter(user=request.user).exists()
    context = {
        'has_credentials': has_credentials
    }
    
    # Return partial template for HTMX requests
    if request.htmx:
        return render(request, 'player/partials/account_content.html', context)
        
    return render(request, 'player/account.html', context)

@login_required
def upload_avatar(request):
    """
    Handles avatar image upload to Imgur service.
    Updates user profile with the returned image URL.
    """
    if request.method == 'POST' and request.FILES.get('avatar'):
        # Get Imgur client ID from environment variables
        client_id = os.environ.get('IMGUR_CLIENT_ID')
        if not client_id:
            return JsonResponse({'error': 'Imgur client ID not configured'}, status=500)

        image = request.FILES['avatar']
        
        # Prepare headers for Imgur API authentication
        headers = {'Authorization': f'Client-ID {client_id}'}
        
        # Upload image to Imgur
        response = requests.post(
            'https://api.imgur.com/3/image',
            headers=headers,
            files={'image': image}
        )
        
        if response.status_code == 200:
            data = response.json()
            # Update or create user profile with new avatar URL
            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            profile.avatar_url = data['data']['link']
            profile.save()
            return JsonResponse({'avatar_url': profile.avatar_url})
        else:
            return JsonResponse({'error': 'Failed to upload image to Imgur'}, status=500)

    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def unlink_service(request):
    """
    Completely removes user's Google Drive connection and all associated data.
    Deletes all songs, albums, artists, playlists, and credentials.
    """
    user = request.user

    # Delete user's playlists and playlist songs
    try:
        PlaylistSong.objects.filter(playlist__user=user).delete()
        Playlist.objects.filter(user=user).delete()
    except Exception as e:
        print(f"Error eliminando playlists del usuario durante unlink_service: {e}")

    # Delete all user's music library data
    Song.objects.filter(user=user).delete()
    Album.objects.filter(user=user).delete()
    Artist.objects.filter(user=user).delete()
    
    # Remove Google credentials
    GoogleCredential.objects.filter(user=user).delete()
    
    # Reset Google Drive root folder ID
    try:
        profile = UserProfile.objects.get(user=user)
        profile.google_drive_root_id = None
        profile.save()
    except UserProfile.DoesNotExist:
        pass

    return redirect('google_login')

@login_required
def google_callback(request):
    """
    Handles the OAuth callback from Google.
    Exchanges authorization code for access tokens and stores credentials.
    """

    # Recreate the flow to exchange the authorization code
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri='http://localhost:8000/callback'
    )
    # Exchange authorization code for credentials
    flow.fetch_token(authorization_response=request.build_absolute_uri())
    credentials = flow.credentials
    # Store credentials in database for future use
    GoogleCredential.objects.update_or_create(
        user=request.user,
        defaults={'token_json': credentials.to_json()}
    )
    return redirect('select_folder')


@login_required
def select_folder(request):
    """
    Displays Google Drive folders for user to select as music library root.
    Shows both regular folders and shortcuts to folders.
    """
    try:
        # Get user's Google Drive credentials
        creds_model = GoogleCredential.objects.get(user=request.user)
        creds = Credentials.from_authorized_user_info(json.loads(creds_model.token_json))
    except GoogleCredential.DoesNotExist:
        return redirect('google_login')
        
    service = build('drive', 'v3', credentials=creds)
    
    # Query for regular folders in root directory
    folder_query = "mimeType='application/vnd.google-apps.folder' and 'root' in parents and trashed=false"
    folder_results = service.files().list(q=folder_query, fields="files(id, name)").execute()
    real_folders = folder_results.get('files', [])
    
    # Query for shortcuts to folders in root directory
    shortcut_query = "mimeType='application/vnd.google-apps.shortcut' and 'root' in parents and trashed=false"
    shortcut_results = service.files().list(q=shortcut_query, fields="files(id, name, shortcutDetails)").execute()
    shortcuts = shortcut_results.get('files', [])
    
    # Process regular folders
    processed_folders = []
    for folder in real_folders:
        processed_folders.append({
            'id': folder['id'],
            'name': folder['name'],
            'type': 'folder'
        })
    
    # Process shortcuts that point to folders
    for shortcut in shortcuts:
        try:
            # Get the target folder that the shortcut points to
            target_id = shortcut['shortcutDetails']['targetId']
            target_info = service.files().get(fileId=target_id, fields="id, name, mimeType").execute()
            
            # Only include shortcuts that point to folders
            if target_info.get('mimeType') == 'application/vnd.google-apps.folder':
                processed_folders.append({
                    'id': target_id,
                    'name': shortcut['name'],
                    'type': 'shortcut'
                })
        except Exception as e:
            print(f"Error procesando shortcut {shortcut['name']}: {e}")
    
    # Choose appropriate base template for HTMX requests
    base_template = "base.html" if not request.htmx or request.htmx.history_restore_request else "_base_empty.html"
    
    context = {'folders': processed_folders, 'base_template': base_template}
    return render(request, 'player/select_folder.html', context)

@login_required
def set_folder(request, folder_id):
    """
    Sets the selected Google Drive folder as the user's music library root.
    """

    profile, created = UserProfile.objects.get_or_create(user=request.user)
    profile.google_drive_root_id = folder_id
    profile.save()

    return redirect('scan_prompt')

@login_required
def scan_prompt(request):
    """
    Displays the scan prompt page with options for different scan types.
    Shows whether user already has songs in their library.
    """
    has_songs = Song.objects.filter(user=request.user).exists()
    return render(request, 'player/scan_prompt.html', {'has_songs': has_songs})

@login_required
def start_quick_scan_task(request):
    """
    Starts a quick scan task that only processes new songs.
    Returns task ID for status monitoring.
    """
    task = scan_user_library.delay(request.user.id, scan_mode='quick')
    return JsonResponse({'task_id': task.id})

@login_required
def start_cover_scan_task(request):
    """
    Starts a scan task that only looks for album cover images.
    Returns task ID for status monitoring.
    """
    task = scan_user_library.delay(request.user.id, scan_mode='covers_only')
    return JsonResponse({'task_id': task.id})

@login_required
def artist_list(request):
    """
    Legacy redirect to folder browser.
    """

    return redirect('folder_browser')

@login_required
def folder_browser(request, folder_id=None):
    """
    Main folder browser view that displays Google Drive folder contents.
    Shows subfolders, detects albums based on folder structure (Artist/Album),
    and displays songs with metadata if available.
    """
    try:
        # Get user's Google Drive credentials and root folder
        creds_model = GoogleCredential.objects.get(user=request.user)
        creds = Credentials.from_authorized_user_info(json.loads(creds_model.token_json))
        profile = UserProfile.objects.get(user=request.user)
        root_folder_id = profile.google_drive_root_id
        
        if not root_folder_id:
            return redirect('select_folder')
            
    except (GoogleCredential.DoesNotExist, UserProfile.DoesNotExist):
        return redirect('google_login')
    
    service = build('drive', 'v3', credentials=creds)
    
    # Use provided folder_id or default to root
    current_folder_id = folder_id or root_folder_id
    
    # Get current folder information
    try:
        current_folder = service.files().get(fileId=current_folder_id, fields='id, name, parents').execute()
    except Exception as e:
        return redirect('folder_browser')
    
    # Build breadcrumb navigation
    breadcrumb = []
    temp_folder_id = current_folder_id
    
    # Traverse up the folder hierarchy to build breadcrumb
    while temp_folder_id and temp_folder_id != root_folder_id:
        try:
            folder_info = service.files().get(fileId=temp_folder_id, fields='id, name, parents').execute()
            breadcrumb.insert(0, {
                'id': folder_info['id'],
                'name': folder_info['name']
            })
            parents = folder_info.get('parents', [])
            temp_folder_id = parents[0] if parents else None
        except:
            break
    
    # Get subfolders in current directory
    folder_query = f"mimeType='application/vnd.google-apps.folder' and '{current_folder_id}' in parents and trashed=false"
    folder_results = service.files().list(
        q=folder_query, 
        fields="files(id, name)",
        orderBy="name"
    ).execute()
    subfolders = folder_results.get('files', [])
    
    # Check if current folder contains audio files (limited query for performance)
    songs_query = f"(mimeType='audio/mpeg' or mimeType='audio/flac' or mimeType='audio/wav') and '{current_folder_id}' in parents and trashed=false"
    songs_results = service.files().list(
        q=songs_query, 
        fields="files(id, name)",
        pageSize=5  # Just check if any songs exist
    ).execute()
    has_songs = len(songs_results.get('files', [])) > 0
    
    # Initialize album and song data
    album = None
    songs = []
    liked_songs_ids = set()
    
    # If folder has songs, try to match with existing album data
    if has_songs:
        # Build folder path to determine artist/album structure
        folder_path = []
        temp_folder_id = current_folder_id
        
        # Get full path from root to current folder
        while temp_folder_id and temp_folder_id != root_folder_id:
            try:
                folder_info = service.files().get(fileId=temp_folder_id, fields='id, name, parents').execute()
                folder_path.insert(0, folder_info['name'])
                parents = folder_info.get('parents', [])
                temp_folder_id = parents[0] if parents else None
            except:
                break
        
        # Expect Artist/Album folder structure (at least 2 levels deep)
        if len(folder_path) >= 2:
            artist_name = folder_path[-2]  # Parent folder = Artist
            album_name = folder_path[-1]   # Current folder = Album
            
            # Try to find existing album in database
            try:
                artist = Artist.objects.get(name=artist_name, user=request.user)
                album = Album.objects.get(name=album_name, artist=artist, user=request.user)
                songs = Song.objects.filter(album=album, user=request.user).order_by('track_number', 'name')
                
                # Get IDs of songs that user has liked
                from .models import LikedSong
                liked_songs_ids = set(LikedSong.objects.filter(
                    user=request.user, 
                    song__in=songs
                ).values_list('song_id', flat=True))
                
            except (Artist.DoesNotExist, Album.DoesNotExist):
                pass  # Album not yet scanned into database

    # Get user's playlists for the add-to-playlist functionality
    playlists = Playlist.objects.filter(user=request.user)
    
    context = {
        'current_folder': current_folder,
        'subfolders': subfolders,
        'breadcrumb': breadcrumb,
        'has_songs': has_songs,
        'album': album,
        'songs': songs,
        'liked_songs_ids': liked_songs_ids,
        'is_root': current_folder_id == root_folder_id,
        'playlists': playlists,
    }
    
    return render(request, 'player/folder_browser.html', context)

@login_required
def artist_detail(request, artist_id):
    """
    Legacy redirect to folder browser.
    """

    return redirect('folder_browser')

@login_required
def album_cover(request, album_id):
    """
    Serves album cover images from Google Drive.
    Falls back to default cover if no image is available.
    """
    album = get_object_or_404(Album, id=album_id, user=request.user)
    
    # Return default cover if no cover image is set
    if not album.cover_image_id:
        return redirect(static('images/default_cover.png'))

    try:
        # Get user's Google Drive credentials
        creds_model = GoogleCredential.objects.get(user=request.user)
        creds = Credentials.from_authorized_user_info(json.loads(creds_model.token_json))
        service = build('drive', 'v3', credentials=creds)
        
        # Get file metadata to check for thumbnail
        file_metadata = service.files().get(
            fileId=album.cover_image_id, 
            fields='thumbnailLink'
        ).execute()

        thumbnail_link = file_metadata.get('thumbnailLink')
        
        # Use Google's thumbnail if available (faster)
        if thumbnail_link:
            return redirect(thumbnail_link)
        else:
            # Download full image if no thumbnail available
            request_download = service.files().get_media(fileId=album.cover_image_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request_download)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            fh.seek(0)
            return HttpResponse(fh.read(), content_type='image/jpeg')

    except Exception:
        # Return default cover on any error
        return redirect(static('images/default_cover.png'))


@login_required
def play_song(request, file_id):
    """
    Streams audio files from Google Drive.
    Validates user permissions and provides chunked streaming for large files.
    """
    try:
        # Verify song belongs to user and get credentials
        song = Song.objects.get(google_file_id=file_id, user=request.user)
        creds_model = GoogleCredential.objects.get(user=request.user)
        creds = Credentials.from_authorized_user_info(json.loads(creds_model.token_json))
    except (Song.DoesNotExist, GoogleCredential.DoesNotExist):
        raise Http404("No se encontró la canción o las credenciales.")
        
    service = build('drive', 'v3', credentials=creds)
    # Get file metadata for proper MIME type and size
    file_metadata = service.files().get(fileId=file_id, fields='mimeType, size').execute()
    mime_type = file_metadata.get('mimeType', 'audio/mpeg')
    request_download = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    # Use 1MB chunks for efficient streaming
    downloader = MediaIoBaseDownload(fh, request_download, chunksize=1024*1024)

    def stream_content_generator():
        """Generator function for streaming audio data in chunks."""
        done = False
        while not done:
            status, done = downloader.next_chunk()
            chunk = fh.getvalue()
            fh.seek(0)
            fh.truncate(0)
            yield chunk

    # Return streaming response with proper headers
    response = StreamingHttpResponse(stream_content_generator(), content_type=mime_type)
    response['Content-Length'] = file_metadata.get('size')
    return response

@login_required
def liked_songs(request):
    """
    Displays all songs that the user has liked.
    Ordered by most recently liked first.
    """
    liked_songs_through = LikedSong.objects.filter(user=request.user).order_by('-created_at')
    songs = [liked.song for liked in liked_songs_through]
    
    # Choose appropriate base template for HTMX requests
    base_template = "base.html" if not request.htmx or request.htmx.history_restore_request else "_base_empty.html"
    
    context = {'songs': songs, 'base_template': base_template}
    return render(request, 'player/liked_songs.html', context)

@login_required
def start_scan_task(request):
    """
    Starts a full library scan task that processes all music files.
    Returns task ID for status monitoring.
    """
    task = scan_user_library.delay(request.user.id, scan_mode='full')
    return JsonResponse({'task_id': task.id})

@login_required
def task_status(request, task_id):
    """
    Returns the current status of a Celery background task.
    Used for monitoring scan progress via AJAX.
    """
    task_result = AsyncResult(task_id)
    result = {
        'task_id': task_id,
        'status': task_result.status,
        'info': task_result.info,
    }
    return JsonResponse(result)

@login_required
def toggle_like_song(request, song_id):
    """
    Toggles the like status of a song for the current user.
    Supports undo functionality by preserving original like timestamp.
    """
    if request.method == 'POST':
        try:
            # Verify song belongs to user
            song = Song.objects.get(google_file_id=song_id, user=request.user)
            
            # Check if this is an undo operation
            is_undo = request.POST.get('undo') == 'true'
            original_date = request.POST.get('original_date')
            
            # Try to get or create the like relationship
            liked_song, created = LikedSong.objects.get_or_create(
                user=request.user,
                song=song
            )
            
            if not created:
                # Song was already liked - remove the like
                original_created_at = liked_song.created_at
                liked_song.delete()
                liked = False
                
                # Return original timestamp for potential undo
                return JsonResponse({
                    'liked': liked,
                    'original_date': original_created_at.isoformat()
                })
            else:
                # Song was not liked - add the like
                if is_undo and original_date:
                    # Restore original like timestamp if this is an undo
                    from datetime import datetime
                    liked_song.created_at = datetime.fromisoformat(original_date.replace('Z', '+00:00'))
                    liked_song.original_created_at = liked_song.created_at
                    liked_song.save()
                
                liked = True
                return JsonResponse({'liked': liked})
                
        except Song.DoesNotExist:
            return JsonResponse({'error': 'Canción no encontrada'}, status=404)
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)

@login_required
def playlist_list(request):
    """
    Displays all playlists belonging to the current user.
    Includes song count for each playlist.
    """
    playlists = Playlist.objects.filter(user=request.user).prefetch_related('songs')
    return render(request, 'player/playlist_list.html', {'playlists': playlists})

@login_required
def playlist_detail(request, playlist_id):
    """
    Displays detailed view of a specific playlist with all its songs.
    Shows which songs are liked by the user.
    """
    playlist = get_object_or_404(Playlist, id=playlist_id, user=request.user)

    # Get playlist songs in proper order
    playlist_songs = PlaylistSong.objects.filter(playlist=playlist).order_by('order', 'date_added')
    
    # Get IDs of songs that user has liked
    liked_songs_ids = set(LikedSong.objects.filter(
        user=request.user, 
        song__in=[ps.song for ps in playlist_songs]
    ).values_list('song_id', flat=True))
    
    return render(request, 'player/playlist_detail.html', {
        'playlist': playlist,
        'playlist_songs': playlist_songs,
        'liked_songs_ids': liked_songs_ids
    })

@login_required
def create_playlist(request):
    """
    Creates a new playlist for the user.
    Optionally uploads cover image to Imgur.
    """
    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            playlist = Playlist.objects.create(user=request.user, name=name)
            
            # Handle cover image upload if provided
            if request.FILES.get('cover_image'):
                client_id = os.environ.get('IMGUR_CLIENT_ID')
                if client_id:
                    try:
                        image = request.FILES['cover_image']
                        headers = {'Authorization': f'Client-ID {client_id}'}
                        
                        # Upload to Imgur
                        response = requests.post(
                            'https://api.imgur.com/3/image',
                            headers=headers,
                            files={'image': image}
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            playlist.cover_image_url = data['data']['link']
                            playlist.save()
                    except Exception as e:
                        print(f"Error subiendo imagen: {e}")
            
            return JsonResponse({'success': True, 'playlist_id': playlist.id})
        return JsonResponse({'error': 'Nombre requerido'}, status=400)
    return JsonResponse({'error': 'Método no permitido'}, status=405)

@login_required
def edit_playlist(request, playlist_id):
    """
    Edits an existing playlist's name and optionally updates cover image.
    """
    if request.method == 'POST':
        try:
            playlist = get_object_or_404(Playlist, id=playlist_id, user=request.user)
            name = request.POST.get('name')
            
            if name:
                playlist.name = name
                
                # Handle cover image upload if provided
                if request.FILES.get('cover_image'):
                    client_id = os.environ.get('IMGUR_CLIENT_ID')
                    if client_id:
                        try:
                            image = request.FILES['cover_image']
                            headers = {'Authorization': f'Client-ID {client_id}'}
                            
                            # Upload to Imgur
                            response = requests.post(
                                'https://api.imgur.com/3/image',
                                headers=headers,
                                files={'image': image}
                            )
                            
                            if response.status_code == 200:
                                data = response.json()
                                playlist.cover_image_url = data['data']['link']
                        except Exception as e:
                            print(f"Error subiendo imagen: {e}")
                
                playlist.save()
                return JsonResponse({'success': True, 'playlist_id': playlist.id})
            return JsonResponse({'error': 'Nombre requerido'}, status=400)
        except Playlist.DoesNotExist:
            return JsonResponse({'error': 'Playlist no encontrada'}, status=404)
    return JsonResponse({'error': 'Método no permitido'}, status=405)

@login_required
def add_to_playlist(request, song_id, playlist_id):
    """
    Adds a song to a specific playlist.
    Prevents duplicate songs and maintains proper ordering.
    """
    if request.method == 'POST':
        try:
            playlist = Playlist.objects.get(id=playlist_id, user=request.user)
            song = Song.objects.get(google_file_id=song_id)
            
            # Check if song is already in playlist
            if PlaylistSong.objects.filter(playlist=playlist, song=song).exists():
                return JsonResponse({'error': 'La canción ya está en esta playlist'}, status=400)
            
            # Get the highest order number and add 1
            last_order = PlaylistSong.objects.filter(playlist=playlist).aggregate(
                max_order=models.Max('order')
            )['max_order'] or 0
            
            # Add song to end of playlist
            PlaylistSong.objects.create(
                playlist=playlist, 
                song=song, 
                order=last_order + 1
            )
            return JsonResponse({'success': True})
        except Playlist.DoesNotExist:
            return JsonResponse({'error': 'Playlist no encontrada'}, status=404)
        except Song.DoesNotExist:
            return JsonResponse({'error': 'Canción no encontrada'}, status=404)
    return JsonResponse({'error': 'Método no permitido'}, status=405)

@login_required
def reorder_playlist(request, playlist_id):
    """
    Reorders songs in a playlist based on new order array.
    Updates the order field for all songs in the playlist.
    """
    if request.method == 'POST':
        try:
            playlist = get_object_or_404(Playlist, id=playlist_id, user=request.user)
            song_orders = request.POST.getlist('song_orders[]')
            
            # Update order for each song based on new position
            for index, song_id in enumerate(song_orders):
                PlaylistSong.objects.filter(
                    playlist=playlist, 
                    song__google_file_id=song_id
                ).update(order=index + 1)
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Método no permitido'}, status=405)

@login_required
def remove_from_playlist(request, playlist_id, song_id):
    """
    Removes a song from a playlist and reorders remaining songs.
    Maintains sequential ordering after removal.
    """
    if request.method == 'POST':
        try:
            playlist = get_object_or_404(Playlist, id=playlist_id, user=request.user)
            song = get_object_or_404(Song, google_file_id=song_id)
            
            # Remove the song from playlist
            PlaylistSong.objects.filter(playlist=playlist, song=song).delete()
            
            # Reorder remaining songs to maintain sequential numbering
            remaining_songs = PlaylistSong.objects.filter(playlist=playlist).order_by('order')
            for index, playlist_song in enumerate(remaining_songs):
                playlist_song.order = index + 1
                playlist_song.save()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Método no permitido'}, status=405)

@login_required
def get_user_playlists(request):
    """
    Returns JSON data of all user's playlists with song counts.
    Used for AJAX requests to populate playlist dropdowns.
    """

    try:
        # Get playlists with song count annotation
        playlists = Playlist.objects.filter(user=request.user).annotate(
            song_count=models.Count('songs')
        ).values('id', 'name', 'cover_image_url', 'song_count')
        
        # Format playlist data for JSON response
        playlists_list = []
        for playlist in playlists:
            playlists_list.append({
                'id': playlist['id'],
                'name': playlist['name'],
                'cover_image_url': playlist['cover_image_url'] or '',
                'song_count': playlist['song_count']
            })
        
        return JsonResponse({'playlists': playlists_list})
    except Exception as e:
        print(f"Error en get_user_playlists: {e}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def delete_playlist(request, playlist_id):
    """
    Deletes a playlist and all its associations.
    Returns success message and redirect URL for frontend handling.
    """
    if request.method == 'POST':
        try:
            playlist = get_object_or_404(Playlist, id=playlist_id, user=request.user)
            playlist_name = playlist.name
            # Cascade delete will remove PlaylistSong entries automatically
            playlist.delete()
            from django.urls import reverse
            return JsonResponse({
                'success': True,
                'message': f'Playlist "{playlist_name}" eliminada correctamente',
                'redirect_url': reverse('playlist_list')
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Método no permitido'}, status=405)