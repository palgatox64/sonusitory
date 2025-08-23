from django.shortcuts import render, redirect, get_object_or_404
from django.http import StreamingHttpResponse, HttpResponse, Http404
from django.contrib.auth.decorators import login_required
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from .models import UserProfile, GoogleCredential, Artist, Album, Song, LikedSong, Playlist, PlaylistSong
from django.http import JsonResponse
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


CLIENT_SECRETS_FILE = os.path.join(os.path.dirname(__file__), '..', 'credentials', 'client_secret.json')
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'


@login_required
def google_login(request):
    if GoogleCredential.objects.filter(user=request.user).exists():
        return render(request, 'player/already_linked.html')

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri='http://localhost:8000/callback'
    )
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    context = {'auth_url': authorization_url}
    
    if request.htmx:
        return render(request, 'player/partials/cloud_login_content.html', context)
        
    return render(request, 'player/cloud_login.html', context)

@login_required
def account(request):
    has_credentials = GoogleCredential.objects.filter(user=request.user).exists()
    context = {
        'has_credentials': has_credentials
    }
    
    if request.htmx:
        return render(request, 'player/partials/account_content.html', context)
        
    return render(request, 'player/account.html', context)

@login_required
def upload_avatar(request):
    if request.method == 'POST' and request.FILES.get('avatar'):
        client_id = os.environ.get('IMGUR_CLIENT_ID')
        if not client_id:
            return JsonResponse({'error': 'Imgur client ID not configured'}, status=500)

        image = request.FILES['avatar']
        
        headers = {'Authorization': f'Client-ID {client_id}'}
        
        response = requests.post(
            'https://api.imgur.com/3/image',
            headers=headers,
            files={'image': image}
        )
        
        if response.status_code == 200:
            data = response.json()
            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            profile.avatar_url = data['data']['link']
            profile.save()
            return JsonResponse({'avatar_url': profile.avatar_url})
        else:
            return JsonResponse({'error': 'Failed to upload image to Imgur'}, status=500)

    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def unlink_service(request):
    user = request.user

    Song.objects.filter(user=user).delete()
    Album.objects.filter(user=user).delete()
    Artist.objects.filter(user=user).delete()
    
    GoogleCredential.objects.filter(user=user).delete()
    
    try:
        profile = UserProfile.objects.get(user=user)
        profile.google_drive_root_id = None
        profile.save()
    except UserProfile.DoesNotExist:
        pass

    return redirect('google_login')

@login_required
def google_callback(request):

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri='http://localhost:8000/callback'
    )
    flow.fetch_token(authorization_response=request.build_absolute_uri())
    credentials = flow.credentials
    GoogleCredential.objects.update_or_create(
        user=request.user,
        defaults={'token_json': credentials.to_json()}
    )
    return redirect('select_folder')


@login_required
def select_folder(request):
    try:
        creds_model = GoogleCredential.objects.get(user=request.user)
        creds = Credentials.from_authorized_user_info(json.loads(creds_model.token_json))
    except GoogleCredential.DoesNotExist:
        return redirect('google_login')
        
    service = build('drive', 'v3', credentials=creds)
    
    folder_query = "mimeType='application/vnd.google-apps.folder' and 'root' in parents and trashed=false"
    folder_results = service.files().list(q=folder_query, fields="files(id, name)").execute()
    real_folders = folder_results.get('files', [])
    
    shortcut_query = "mimeType='application/vnd.google-apps.shortcut' and 'root' in parents and trashed=false"
    shortcut_results = service.files().list(q=shortcut_query, fields="files(id, name, shortcutDetails)").execute()
    shortcuts = shortcut_results.get('files', [])
    
    processed_folders = []
    for folder in real_folders:
        processed_folders.append({
            'id': folder['id'],
            'name': folder['name'],
            'type': 'folder'
        })
    
    for shortcut in shortcuts:
        try:
            
            target_id = shortcut['shortcutDetails']['targetId']
            target_info = service.files().get(fileId=target_id, fields="id, name, mimeType").execute()
            
            if target_info.get('mimeType') == 'application/vnd.google-apps.folder':
                processed_folders.append({
                    'id': target_id,
                    'name': shortcut['name'],
                    'type': 'shortcut'
                })
        except Exception as e:
            print(f"Error procesando shortcut {shortcut['name']}: {e}")
    
    base_template = "base.html" if not request.htmx or request.htmx.history_restore_request else "_base_empty.html"
    
    context = {'folders': processed_folders, 'base_template': base_template}
    return render(request, 'player/select_folder.html', context)

@login_required
def set_folder(request, folder_id):

    profile, created = UserProfile.objects.get_or_create(user=request.user)
    profile.google_drive_root_id = folder_id
    profile.save()

    return redirect('scan_prompt')

@login_required
def scan_prompt(request):
    has_songs = Song.objects.filter(user=request.user).exists()
    return render(request, 'player/scan_prompt.html', {'has_songs': has_songs})

@login_required
def start_quick_scan_task(request):
    task = scan_user_library.delay(request.user.id, scan_mode='quick')
    return JsonResponse({'task_id': task.id})

@login_required
def start_cover_scan_task(request):
    task = scan_user_library.delay(request.user.id, scan_mode='covers_only')
    return JsonResponse({'task_id': task.id})

@login_required
def artist_list(request):

    return redirect('folder_browser')

@login_required
def folder_browser(request, folder_id=None):
    try:
        creds_model = GoogleCredential.objects.get(user=request.user)
        creds = Credentials.from_authorized_user_info(json.loads(creds_model.token_json))
        profile = UserProfile.objects.get(user=request.user)
        root_folder_id = profile.google_drive_root_id
        
        if not root_folder_id:
            return redirect('select_folder')
            
    except (GoogleCredential.DoesNotExist, UserProfile.DoesNotExist):
        return redirect('google_login')
    
    service = build('drive', 'v3', credentials=creds)
    
    current_folder_id = folder_id or root_folder_id
    
    try:
        current_folder = service.files().get(fileId=current_folder_id, fields='id, name, parents').execute()
    except Exception as e:
        return redirect('folder_browser')
    
    breadcrumb = []
    temp_folder_id = current_folder_id
    
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
    
    folder_query = f"mimeType='application/vnd.google-apps.folder' and '{current_folder_id}' in parents and trashed=false"
    folder_results = service.files().list(
        q=folder_query, 
        fields="files(id, name)",
        orderBy="name"
    ).execute()
    subfolders = folder_results.get('files', [])
    
    songs_query = f"(mimeType='audio/mpeg' or mimeType='audio/flac' or mimeType='audio/wav') and '{current_folder_id}' in parents and trashed=false"
    songs_results = service.files().list(
        q=songs_query, 
        fields="files(id, name)",
        pageSize=5
    ).execute()
    has_songs = len(songs_results.get('files', [])) > 0
    
    album = None
    songs = []
    liked_songs_ids = set()
    if has_songs:
        folder_path = []
        temp_folder_id = current_folder_id
        
        while temp_folder_id and temp_folder_id != root_folder_id:
            try:
                folder_info = service.files().get(fileId=temp_folder_id, fields='id, name, parents').execute()
                folder_path.insert(0, folder_info['name'])
                parents = folder_info.get('parents', [])
                temp_folder_id = parents[0] if parents else None
            except:
                break
        
        if len(folder_path) >= 2:
            artist_name = folder_path[-2]
            album_name = folder_path[-1]
            
            try:
                artist = Artist.objects.get(name=artist_name, user=request.user)
                album = Album.objects.get(name=album_name, artist=artist, user=request.user)
                songs = Song.objects.filter(album=album, user=request.user).order_by('track_number', 'name')
                

                from .models import LikedSong
                liked_songs_ids = set(LikedSong.objects.filter(
                    user=request.user, 
                    song__in=songs
                ).values_list('song_id', flat=True))
                
            except (Artist.DoesNotExist, Album.DoesNotExist):
                pass

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

    return redirect('folder_browser')

@login_required
def album_cover(request, album_id):
    album = get_object_or_404(Album, id=album_id, user=request.user)
    
    if not album.cover_image_id:
        return redirect(static('images/default_cover.png'))

    try:
        creds_model = GoogleCredential.objects.get(user=request.user)
        creds = Credentials.from_authorized_user_info(json.loads(creds_model.token_json))
        service = build('drive', 'v3', credentials=creds)
        
        file_metadata = service.files().get(
            fileId=album.cover_image_id, 
            fields='thumbnailLink'
        ).execute()

        thumbnail_link = file_metadata.get('thumbnailLink')
        
        if thumbnail_link:
            return redirect(thumbnail_link)
        else:
            request_download = service.files().get_media(fileId=album.cover_image_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request_download)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            fh.seek(0)
            return HttpResponse(fh.read(), content_type='image/jpeg')

    except Exception:
        return redirect(static('images/default_cover.png'))


@login_required
def play_song(request, file_id):
    try:
        song = Song.objects.get(google_file_id=file_id, user=request.user)
        creds_model = GoogleCredential.objects.get(user=request.user)
        creds = Credentials.from_authorized_user_info(json.loads(creds_model.token_json))
    except (Song.DoesNotExist, GoogleCredential.DoesNotExist):
        raise Http404("No se encontró la canción o las credenciales.")
        
    service = build('drive', 'v3', credentials=creds)
    file_metadata = service.files().get(fileId=file_id, fields='mimeType, size').execute()
    mime_type = file_metadata.get('mimeType', 'audio/mpeg')
    request_download = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request_download, chunksize=1024*1024)

    def stream_content_generator():
        done = False
        while not done:
            status, done = downloader.next_chunk()
            chunk = fh.getvalue()
            fh.seek(0)
            fh.truncate(0)
            yield chunk

    response = StreamingHttpResponse(stream_content_generator(), content_type=mime_type)
    response['Content-Length'] = file_metadata.get('size')
    return response

@login_required
def liked_songs(request):
    liked_songs_through = LikedSong.objects.filter(user=request.user).order_by('-created_at')
    songs = [liked.song for liked in liked_songs_through]
    
    base_template = "base.html" if not request.htmx or request.htmx.history_restore_request else "_base_empty.html"
    
    context = {'songs': songs, 'base_template': base_template}
    return render(request, 'player/liked_songs.html', context)

@login_required
def start_scan_task(request):
    task = scan_user_library.delay(request.user.id, scan_mode='full')
    return JsonResponse({'task_id': task.id})

@login_required
def task_status(request, task_id):
    task_result = AsyncResult(task_id)
    result = {
        'task_id': task_id,
        'status': task_result.status,
        'info': task_result.info,
    }
    return JsonResponse(result)

@login_required
def toggle_like_song(request, song_id):
    if request.method == 'POST':
        try:
            song = Song.objects.get(google_file_id=song_id, user=request.user)
            
            is_undo = request.POST.get('undo') == 'true'
            original_date = request.POST.get('original_date')
            
            liked_song, created = LikedSong.objects.get_or_create(
                user=request.user,
                song=song
            )
            
            if not created:
                original_created_at = liked_song.created_at
                liked_song.delete()
                liked = False
                
                return JsonResponse({
                    'liked': liked,
                    'original_date': original_created_at.isoformat()
                })
            else:
                if is_undo and original_date:
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
    playlists = Playlist.objects.filter(user=request.user).prefetch_related('songs')
    return render(request, 'player/playlist_list.html', {'playlists': playlists})

@login_required
def playlist_detail(request, playlist_id):
    playlist = get_object_or_404(Playlist, id=playlist_id, user=request.user)
    # Ordenar canciones por orden y fecha de agregado
    playlist_songs = PlaylistSong.objects.filter(playlist=playlist).order_by('order', 'date_added')
    
    # Obtener IDs de canciones que le gustan al usuario
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
    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            playlist = Playlist.objects.create(user=request.user, name=name)
            
            # Manejar la imagen si se proporciona
            if request.FILES.get('cover_image'):
                client_id = os.environ.get('IMGUR_CLIENT_ID')
                if client_id:
                    try:
                        image = request.FILES['cover_image']
                        headers = {'Authorization': f'Client-ID {client_id}'}
                        
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
    if request.method == 'POST':
        try:
            playlist = get_object_or_404(Playlist, id=playlist_id, user=request.user)
            name = request.POST.get('name')
            
            if name:
                playlist.name = name
                
                # Manejar la imagen si se proporciona
                if request.FILES.get('cover_image'):
                    client_id = os.environ.get('IMGUR_CLIENT_ID')
                    if client_id:
                        try:
                            image = request.FILES['cover_image']
                            headers = {'Authorization': f'Client-ID {client_id}'}
                            
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
    if request.method == 'POST':
        try:
            playlist = Playlist.objects.get(id=playlist_id, user=request.user)
            song = Song.objects.get(google_file_id=song_id)
            
            # Verificar si la canción ya está en la playlist
            if PlaylistSong.objects.filter(playlist=playlist, song=song).exists():
                return JsonResponse({'error': 'La canción ya está en esta playlist'}, status=400)
            
            # Obtener el siguiente número de orden
            last_order = PlaylistSong.objects.filter(playlist=playlist).aggregate(
                max_order=models.Max('order')
            )['max_order'] or 0
            
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
    if request.method == 'POST':
        try:
            playlist = get_object_or_404(Playlist, id=playlist_id, user=request.user)
            song_orders = request.POST.getlist('song_orders[]')
            
            # Actualizar el orden de las canciones
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
    if request.method == 'POST':
        try:
            playlist = get_object_or_404(Playlist, id=playlist_id, user=request.user)
            song = get_object_or_404(Song, google_file_id=song_id)
            
            PlaylistSong.objects.filter(playlist=playlist, song=song).delete()
            
            # Reordenar las canciones restantes
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
    """Obtener las playlists del usuario para el modal de añadir a playlist"""
    try:
        playlists = Playlist.objects.filter(user=request.user).annotate(
            song_count=models.Count('songs')
        ).values('id', 'name', 'cover_image_url', 'song_count')
        
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
    if request.method == 'POST':
        try:
            playlist = get_object_or_404(Playlist, id=playlist_id, user=request.user)
            playlist_name = playlist.name
            playlist.delete()
            # Añadir URL de redirección
            from django.urls import reverse
            return JsonResponse({
                'success': True,
                'message': f'Playlist "{playlist_name}" eliminada correctamente',
                'redirect_url': reverse('playlist_list')
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Método no permitido'}, status=405)