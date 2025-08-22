from django.shortcuts import render, redirect, get_object_or_404
from django.http import StreamingHttpResponse, HttpResponse, Http404
from django.contrib.auth.decorators import login_required
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from .models import UserProfile, GoogleCredential, Artist, Album, Song, LikedSong
from django.http import JsonResponse
from .tasks import scan_user_library
from celery.result import AsyncResult
from django.templatetags.static import static
import os
import io
import json
import requests


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
    query = "mimeType='application/vnd.google-apps.folder' and 'root' in parents and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    folders = results.get('files', [])
    
    base_template = "base.html" if not request.htmx or request.htmx.history_restore_request else "_base_empty.html"
    
    context = {'folders': folders, 'base_template': base_template}
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
    try:
        profile = UserProfile.objects.get(user=request.user)
        if not profile.google_drive_root_id:
            return redirect('select_folder')
    except UserProfile.DoesNotExist:
        return redirect('select_folder')
    artists = Artist.objects.filter(user=request.user).order_by('name')
    
    base_template = "base.html" if not request.htmx or request.htmx.history_restore_request else "_base_empty.html"

    context = {'artists': artists, 'base_template': base_template}
    return render(request, 'player/artist_list.html', context)

@login_required
def artist_detail(request, artist_id):
    artist = Artist.objects.get(id=artist_id, user=request.user)
    albums = Album.objects.filter(artist=artist, user=request.user).order_by('name')
    
    base_template = "base.html" if not request.htmx or request.htmx.history_restore_request else "_base_empty.html"
    
    context = {
        'artist': artist,
        'albums': albums,
        'base_template': base_template
    }
    return render(request, 'player/artist_detail.html', context)

@login_required
def album_detail(request, album_id):
    album = Album.objects.get(id=album_id, user=request.user)
    songs = Song.objects.filter(album=album, user=request.user).order_by('track_number', 'name')
    
    base_template = "base.html" if not request.htmx or request.htmx.history_restore_request else "_base_empty.html"
    
    context = {'album': album, 'songs': songs, 'base_template': base_template}
    return render(request, 'player/album_detail.html', context)


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
    task = scan_user_library.delay(request.user.id, scan_mode='full') # <-- MODIFICADO
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
            liked_song, created = LikedSong.objects.get_or_create(
                user=request.user,
                song=song
            )
            
            if not created:
                liked_song.delete()
                liked = False
            else:
                liked = True
                
            return JsonResponse({'liked': liked})
        except Song.DoesNotExist:
            return JsonResponse({'error': 'Canción no encontrada'}, status=404)
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)