from django.urls import path
from . import views

urlpatterns = [

    path('connect/', views.google_login, name='google_login'),
    path('callback', views.google_callback, name='google_callback'),
    
    path('select-folder/', views.select_folder, name='select_folder'),
    path('set-folder/<str:folder_id>/', views.set_folder, name='set_folder'),
    path('scan-prompt/', views.scan_prompt, name='scan_prompt'),
    
    path('play/<str:file_id>/', views.play_song, name='play_song'),
    
    path('', views.artist_list, name='artist_list'),
    path('artist/<int:artist_id>/', views.artist_detail, name='artist_detail'),
    path('album/<int:album_id>/', views.album_detail, name='album_detail'),
    path('album/<int:album_id>/cover/', views.album_cover, name='album_cover'),
    path('start-scan/', views.start_scan_task, name='start_scan_task'),
    path('start-quick-scan/', views.start_quick_scan_task, name='start_quick_scan_task'),
     path('start-cover-scan/', views.start_cover_scan_task, name='start_cover_scan_task'),
    path('task-status/<str:task_id>/', views.task_status, name='task_status'),
    
    path('account/', views.account, name='account'),
    path('upload-avatar/', views.upload_avatar, name='upload_avatar'),
    path('unlink-service/', views.unlink_service, name='unlink_service'),
    
]