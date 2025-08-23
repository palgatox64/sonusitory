from django.urls import path
from . import views

urlpatterns = [

    path('connect/', views.google_login, name='google_login'),
    path('callback', views.google_callback, name='google_callback'),
    

    path('select-folder/', views.select_folder, name='select_folder'),
    path('set-folder/<str:folder_id>/', views.set_folder, name='set_folder'),
    path('scan-prompt/', views.scan_prompt, name='scan_prompt'),
    

    path('', views.folder_browser, name='folder_browser'),
    path('browse/', views.folder_browser, name='folder_browser_root'),
    path('browse/<str:folder_id>/', views.folder_browser, name='folder_browser'),
    

    path('artists/', views.artist_list, name='artist_list'),
    path('artist/<int:artist_id>/', views.artist_detail, name='artist_detail'),
    

    path('album/<int:album_id>/cover/', views.album_cover, name='album_cover'),
    path('liked/', views.liked_songs, name='liked_songs'),
    
    path('playlists/', views.playlist_list, name='playlist_list'),
    path('playlist/<int:playlist_id>/', views.playlist_detail, name='playlist_detail'),
    path('playlist/create/', views.create_playlist, name='create_playlist'),
    path('get-user-playlists/', views.get_user_playlists, name='get_user_playlists'),
    path('add-to-playlist/<str:song_id>/<int:playlist_id>/', views.add_to_playlist, name='add_to_playlist'),

    
    
    path('play/<str:file_id>/', views.play_song, name='play_song'),
    

    path('start-scan/', views.start_scan_task, name='start_scan_task'),
    path('start-quick-scan/', views.start_quick_scan_task, name='start_quick_scan_task'),
    path('start-cover-scan/', views.start_cover_scan_task, name='start_cover_scan_task'),
    path('task-status/<str:task_id>/', views.task_status, name='task_status'),
    

    path('account/', views.account, name='account'),
    path('upload-avatar/', views.upload_avatar, name='upload_avatar'),
    path('unlink-service/', views.unlink_service, name='unlink_service'),
    path('toggle-like/<str:song_id>/', views.toggle_like_song, name='toggle_like_song'),
]