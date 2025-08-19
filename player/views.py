
from django.shortcuts import render, redirect
from django.http import StreamingHttpResponse, HttpResponse, Http404
from django.contrib.auth.decorators import login_required
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from .models import UserProfile, GoogleCredential, Artist, Album, Song
from django.http import JsonResponse
from .tasks import scan_user_library
from celery.result import AsyncResult
import os
import io
import json


CLIENT_SECRETS_FILE = os.path.join(os.path.dirname(__file__), '..', 'credentials', 'client_secret.json')
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'


@login_required
def google_login(request):

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
    return render(request, 'player/google_login.html', context)

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
    context = {'folders': folders}
    return render(request, 'player/select_folder.html', context)

@login_required
def set_folder(request, folder_id):

    profile, created = UserProfile.objects.get_or_create(user=request.user)
    profile.google_drive_root_id = folder_id
    profile.save()

    return redirect('scan_prompt')

@login_required
def scan_prompt(request):
    return render(request, 'player/scan_prompt.html')



@login_required
def artist_list(request):
    try:
        profile = UserProfile.objects.get(user=request.user)
        if not profile.google_drive_root_id:
            return redirect('select_folder')
    except UserProfile.DoesNotExist:
        return redirect('select_folder')
    artists = Artist.objects.filter(user=request.user).order_by('name')
    context = {'artists': artists}
    return render(request, 'player/artist_list.html', context)

@login_required
def artist_detail(request, artist_id):
    artist = Artist.objects.get(id=artist_id, user=request.user)
    albums = Album.objects.filter(artist=artist, user=request.user).order_by('name')
    
    context = {
        'artist': artist,
        'albums': albums
    }
    return render(request, 'player/artist_detail.html', context)

@login_required
def album_detail(request, album_id):

    album = Album.objects.get(id=album_id, user=request.user)

    songs = Song.objects.filter(album=album, user=request.user).order_by('track_number', 'name')
    context = {'album': album, 'songs': songs}
    return render(request, 'player/album_detail.html', context)



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
def start_scan_task(request):
    task = scan_user_library.delay(request.user.id)
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