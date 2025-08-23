
let songQueue = [];
let songMenuListenersInitialized = false;


function playSong(songId, songName) {
    const songUrl = `/play/${songId}/`;
    const nowPlayingElem = document.getElementById('now-playing');
    const audioPlayer = document.getElementById('main-audio-player');

    if (nowPlayingElem && audioPlayer) {
        nowPlayingElem.textContent = `Reproduciendo: ${songName}`;
        audioPlayer.src = songUrl;
        audioPlayer.load();
        audioPlayer.play().catch(e => console.error("Error al reproducir:", e));
    }
}


function initializeAvatarUpload() {
    const changeAvatarButton = document.getElementById('change-avatar-button');
    if (!changeAvatarButton) return;

    const avatarInput = document.getElementById('avatar-input');
    const avatarPreview = document.getElementById('avatar-preview');
    let originalAvatarSrc = avatarPreview.src;

    changeAvatarButton.replaceWith(changeAvatarButton.cloneNode(true));
    const newChangeAvatarButton = document.getElementById('change-avatar-button');

    // Clonar primero el input y usar SIEMPRE la nueva referencia
    avatarInput.replaceWith(avatarInput.cloneNode(true));
    const newAvatarInput = document.getElementById('avatar-input');

    newChangeAvatarButton.addEventListener('click', () => {
        originalAvatarSrc = avatarPreview.src;
        newAvatarInput.click();
    });

    newAvatarInput.addEventListener('change', () => {
        const file = newAvatarInput.files[0];
        if (!file) return;

        if (!file.type.startsWith('image/')) {
            Swal.fire('Error', 'Por favor selecciona un archivo de imagen válido.', 'error');
            return;
        }

        if (file.size > 5 * 1024 * 1024) {
            Swal.fire('Error', 'La imagen es demasiado grande. Máximo 5MB.', 'error');
            return;
        }

        const reader = new FileReader();
        reader.onload = (e) => {
            avatarPreview.src = e.target.result;
            Swal.fire({
                title: "¿Quieres guardar este cambio?",
                imageUrl: e.target.result,
                imageHeight: 150,
                imageAlt: 'Previsualización',
                showCancelButton: true,
                confirmButtonText: "Guardar",
                cancelButtonText: "Cancelar",
                confirmButtonColor: '#3085d6',
                cancelButtonColor: '#d33',
            }).then((result) => {
                if (result.isConfirmed) {
                    const formData = new FormData();
                    formData.append('avatar', file);
                    const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
                    Swal.fire({ title: 'Subiendo...', allowOutsideClick: false, didOpen: () => Swal.showLoading() });

                    const uploadUrl = window.uploadAvatarUrl || '/upload-avatar/';

                    fetch(uploadUrl, {
                        method: 'POST',
                        body: formData,
                        headers: {
                            'X-CSRFToken': csrfToken,
                            'Accept': 'application/json'
                        },
                        credentials: 'same-origin'
                    })
                    .then(async (response) => {
                        let data = null;
                        try { data = await response.json(); }
                        catch { throw new Error(`Error ${response.status}: respuesta no válida del servidor`); }
                        if (!response.ok) throw new Error(data?.error || data?.detail || `Error ${response.status}`);
                        return data;
                    })
                    .then(data => {
                        Swal.close();
                        if (data.avatar_url) {
                            avatarPreview.src = data.avatar_url;
                            const userAvatarInNav = document.querySelector('.user-avatar');
                            if (userAvatarInNav) userAvatarInNav.src = data.avatar_url;
                            Swal.fire('¡Guardado!', 'Tu nueva foto de perfil ha sido guardada.', 'success');
                        } else {
                            throw new Error(data.error || 'No se pudo subir la imagen.');
                        }
                    })
                    .catch((err) => {
                        Swal.close();
                        avatarPreview.src = originalAvatarSrc;
                        Swal.fire('¡Error!', err.message || 'Ocurrió un error de red.', 'error');
                    });

                } else {
                    avatarPreview.src = originalAvatarSrc;
                    Swal.fire("Cancelado", "Tu foto de perfil no ha cambiado.", "info");
                }
            });
        };
        reader.readAsDataURL(file);
        newAvatarInput.value = '';
    });
}

function updateUserMenuVisibility() {
    const userMenuDropdown = document.querySelector('.dropdown');
    if (userMenuDropdown) {
        if (window.location.pathname === '/account/') {
            userMenuDropdown.style.display = 'none';
        } else {
            userMenuDropdown.style.display = 'inline-block';
        }
    }
}

function initializeUserMenuToggle() {
    const userMenuToggle = document.getElementById('user-menu-toggle');
    const userMenu = document.getElementById('user-menu');
    
    if (userMenuToggle && userMenu) {
        userMenuToggle.addEventListener('click', function(e) {
            e.stopPropagation();
            userMenu.classList.toggle('show');
        });

        document.addEventListener('click', function(e) {
            if (!userMenuToggle.contains(e.target) && !userMenu.contains(e.target)) {
                userMenu.classList.remove('show');
            }
        });
    }
}


function initializeAccountButtonListener() {
    const accountUnlinkButton = document.getElementById('account-unlink-button');
    if (accountUnlinkButton) {
        accountUnlinkButton.addEventListener('click', function(event) {
            event.preventDefault();
            const hasCredentials = event.target.dataset.hasCredentials === 'true';

            if (hasCredentials) {
                Swal.fire({
                    title: '¿Estás seguro?',
                    text: "Se borrarán todos tus datos de la librería (canciones, álbumes, artistas) y se desvinculará tu nube. ¡Pero puedes volver a vincular tu nube más tarde!",
                    icon: 'warning',
                    showCancelButton: true,
                    confirmButtonColor: '#d33',
                    cancelButtonColor: '#3085d6',
                    confirmButtonText: 'Sí, ¡bórralo todo!',
                    cancelButtonText: 'Cancelar'
                }).then((result) => {
                    if (result.isConfirmed) {
                        window.location.href = event.target.href;
                    }
                });
            } else {
                Swal.fire({
                    title: '¡No hay nada que desvincular!',
                    text: 'Actualmente no tienes ninguna cuenta de nube vinculada.',
                    icon: 'info',
                    confirmButtonText: 'Entendido'
                });
            }
        });
    }
}


function openPlaylistModal(songId, songName) {
    console.log('Abriendo modal para canción:', songId, songName);
    
    fetch('/get-user-playlists/')
        .then(response => {
            console.log('Respuesta del servidor:', response.status);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Datos recibidos:', data);
            
            let playlistOptions = '';
            
            if (data.error) {
                console.error('Error del servidor:', data.error);
                playlistOptions = '<p style="text-align: center; color: #ff6b6b; margin: 20px 0;">Error al cargar playlists</p>';
            } else if (data.playlists && data.playlists.length === 0) {
                playlistOptions = '<p style="text-align: center; color: #b3b3b3; margin: 20px 0;">No tienes playlists creadas. <br><a href="/playlists/" style="color: #bb86fc;">Crear una nueva playlist</a></p>';
            } else if (data.playlists) {
                playlistOptions = data.playlists.map(playlist => 
                    `<div class="playlist-option" 
                          style="display: flex; align-items: center; gap: 15px; padding: 15px; background-color: #282828; margin-bottom: 10px; border-radius: 8px; cursor: pointer; transition: all 0.2s ease; border: 2px solid transparent;"
                      data-playlist-id="${playlist.id}"
                      onmouseover="this.style.backgroundColor='#404040'; this.style.borderColor='#bb86fc';"
                      onmouseout="this.style.backgroundColor='#282828'; this.style.borderColor='transparent';">
                        <img src="${playlist.cover_image_url || '/static/images/default_cover.png'}" 
                             alt="${playlist.name}" 
                             style="width: 50px; height: 50px; border-radius: 5px; object-fit: cover;">
                        <div>
                            <div style="color: #ffffff; font-weight: 600; font-size: 1rem;">${playlist.name}</div>
                            <div style="color: #b3b3b3; font-size: 0.9rem;">${playlist.song_count || 0} canción${(playlist.song_count || 0) !== 1 ? 'es' : ''}</div>
                        </div>
                    </div>`
                ).join('');
            } else {
                playlistOptions = '<p style="text-align: center; color: #ff6b6b; margin: 20px 0;">Error inesperado al cargar playlists</p>';
            }

            Swal.fire({
                title: 'Añadir a playlist',
                html: `
                    <div style="text-align: left;">
                        <p style="margin-bottom: 15px; color: #e0e0e0; font-size: 1rem;">Selecciona una playlist para "${songName}":</p>
                        <div style="max-height: 300px; overflow-y: auto; background-color: #1a1a1a; border-radius: 8px; padding: 10px;">
                            ${playlistOptions}
                        </div>
                    </div>
                `,
                showCancelButton: true,
                showConfirmButton: false,
                cancelButtonText: 'Cancelar',
                background: '#181818',
                color: '#ffffff',
                confirmButtonColor: '#bb86fc',
                cancelButtonColor: '#666666',
                customClass: {
                    popup: 'dark-modal',
                    title: 'dark-modal-title',
                    htmlContainer: 'dark-modal-content'
                },
                didOpen: () => {
                    document.querySelectorAll('.playlist-option').forEach(option => {
                        option.addEventListener('click', function() {
                            const playlistId = this.dataset.playlistId;
                            const playlistName = this.querySelector('div div').textContent;
                            
                            addSongToPlaylist(songId, playlistId, songName, playlistName);
                            Swal.close();
                        });
                    });
                }
            });
        })
        .catch(error => {
            console.error('Error obteniendo playlists:', error);
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'No se pudieron cargar las playlists. Revisa la consola para más detalles.',
                background: '#181818',
                color: '#ffffff'
            });
        });
}

function addSongToPlaylist(songId, playlistId, songName, playlistName) {
    let csrfToken = getCsrfToken();

    const formData = new FormData();
    formData.append('csrfmiddlewaretoken', csrfToken);

    fetch(`/add-to-playlist/${songId}/${playlistId}/`, {
        method: 'POST',
        body: formData
    })
    .then(response => {
        if (response.ok) {
            const Toast = Swal.mixin({
                toast: true,
                position: 'top-end',
                showConfirmButton: false,
                timer: 3000,
                timerProgressBar: true
            });
            Toast.fire({
                icon: 'success',
                title: `"${songName}" añadida a "${playlistName}"`
            });
        } else {
            throw new Error('Error al añadir a playlist');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        Swal.fire({
            icon: 'error',
            title: 'Error',
            text: 'No se pudo añadir la canción a la playlist'
        });
    });
}


window.handleLikeClick = function(songId, likeButton) {
    const songName = likeButton.closest('li').dataset.songName;
    const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
    const songLi = likeButton.closest('li');
    const isInLikedSongsPage = window.location.pathname === '/liked/' || window.location.pathname.includes('/liked/');

    const formData = new FormData();
    formData.append('csrfmiddlewaretoken', csrfToken);

    fetch(`/toggle-like/${songId}/`, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.liked !== undefined) {
            if (data.liked) {
                likeButton.classList.add('liked');
                const Toast = Swal.mixin({
                    toast: true,
                    position: 'top-end',
                    showConfirmButton: false,
                    timer: 3000,
                    timerProgressBar: true,
                    didOpen: (toast) => {
                        toast.onmouseenter = Swal.stopTimer;
                        toast.onmouseleave = Swal.resumeTimer;
                    }
                });
                Toast.fire({
                    icon: 'success',
                    title: `'${songName}' añadida a tus Me Gusta`
                });
            } else {
                likeButton.classList.remove('liked');

                const Toast = Swal.mixin({
                    toast: true,
                    position: 'top-end',
                    showConfirmButton: true,
                    confirmButtonText: 'Deshacer',
                    timer: 5000,
                    timerProgressBar: true,
                    didOpen: (toast) => {
                        toast.onmouseenter = Swal.stopTimer;
                        toast.onmouseleave = Swal.resumeTimer;
                    }
                });

                Toast.fire({
                    icon: 'info',
                    title: `'${songName}' eliminada de tus Me Gusta`
                }).then((result) => {
                    if (result.isConfirmed) {
                        const undoFormData = new FormData();
                        undoFormData.append('csrfmiddlewaretoken', csrfToken);
                        undoFormData.append('undo', 'true');
                        undoFormData.append('original_date', data.original_date);

                        fetch(`/toggle-like/${songId}/`, {
                            method: 'POST',
                            body: undoFormData
                        })
                        .then(response => response.json())
                        .then(undoData => {
                            if (undoData.liked) {
                                likeButton.classList.add('liked');

                                if (isInLikedSongsPage && !document.contains(songLi)) {
                                    window.location.reload();
                                }

                                const UndoToast = Swal.mixin({
                                    toast: true,
                                    position: 'top-end',
                                    showConfirmButton: false,
                                    timer: 2500,
                                    timerProgressBar: true
                                });
                                UndoToast.fire({
                                    icon: 'success',
                                    title: `'${songName}' restaurada a tus Me Gusta`
                                });
                            }
                        })
                        .catch(error => {
                            console.error('Error al deshacer:', error);
                            const ErrorToast = Swal.mixin({
                                toast: true,
                                position: 'top-end',
                                showConfirmButton: false,
                                timer: 3000,
                                timerProgressBar: true
                            });
                            ErrorToast.fire({
                                icon: 'error',
                                title: 'Error al deshacer la acción'
                            });
                        });
                    }
                });

                if (isInLikedSongsPage && songLi) {
                    setTimeout(() => {
                        if (!likeButton.classList.contains('liked')) {
                            songLi.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                            songLi.style.opacity = '0';
                            songLi.style.transform = 'translateX(-20px)';

                            setTimeout(() => {
                                if (!likeButton.classList.contains('liked')) {
                                    songLi.remove();

                                    const songList = document.getElementById('song-list');
                                    if (songList && songList.children.length === 0) {
                                        songList.style.display = 'none';

                                        const emptyMessage = document.createElement('p');
                                        emptyMessage.textContent = 'No tienes canciones marcadas como "Me gusta" aún.';
                                        songList.parentNode.insertBefore(emptyMessage, songList.nextSibling);
                                    }
                                }
                            }, 300);
                        }
                    }, 100);
                }
            }
        }
    })
    .catch(error => {
        console.error('Error:', error);
        const Toast = Swal.mixin({
            toast: true,
            position: 'top-end',
            showConfirmButton: false,
            timer: 3000,
            timerProgressBar: true
        });
        Toast.fire({
            icon: 'error',
            title: 'Error al procesar Me Gusta'
        });
    });
};

function initializeLikeButtons() {
    console.log('Inicializando botones de like...');

    document.querySelectorAll('.like-btn').forEach(button => {
        const newButton = button.cloneNode(true);
        button.parentNode.replaceChild(newButton, button);
    });
    
    document.querySelectorAll('.like-btn').forEach(button => {
        button.addEventListener('click', function(e) {
            e.stopPropagation();
            const songId = this.dataset.songId;
            window.handleLikeClick(songId, this);
        });
    });
    
    console.log('Botones de like inicializados:', document.querySelectorAll('.like-btn').length);
}


function getCsrfToken() {
    let csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
    if (!csrfToken) csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
    if (!csrfToken) {
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [cookieName, value] = cookie.trim().split('=');
            if (cookieName === 'csrftoken') {
                csrfToken = value;
                break;
            }
        }
    }
    return csrfToken;
}

function loadScriptOnce(src) {
    return new Promise((resolve, reject) => {
        if (window.Sortable) return resolve();
        if (document.querySelector(`script[data-key="${src}"]`)) {
            document.querySelector(`script[data-key="${src}"]`).addEventListener('load', resolve, { once: true });
            document.querySelector(`script[data-key="${src}"]`).addEventListener('error', reject, { once: true });
            return;
        }
        const s = document.createElement('script');
        s.src = src;
        s.async = true;
        s.dataset.key = src;
        s.onload = resolve;
        s.onerror = reject;
        document.head.appendChild(s);
    });
}


document.addEventListener('DOMContentLoaded', function() {
    const audioPlayer = document.getElementById('main-audio-player');
    const nowPlayingElem = document.getElementById('now-playing');

    if (audioPlayer && nowPlayingElem) {
        audioPlayer.addEventListener('play', () => {
            const songList = document.getElementById('song-list');
            if (songList) songList.classList.add('playback-active');
        });

        audioPlayer.addEventListener('pause', () => {
            const songList = document.getElementById('song-list');
            if (songList) songList.classList.remove('playback-active');
        });

        audioPlayer.addEventListener('ended', () => {
            console.log('Canción terminada. Cola actual:', songQueue.map(song => song.name));
            if (songQueue.length > 0) {
                const nextSong = songQueue.shift();
                console.log('Reproduciendo siguiente:', nextSong.name);
                playSong(nextSong.id, nextSong.name);
            } else {
                const songList = document.getElementById('song-list');
                if (songList) songList.classList.remove('playbook-active');
                nowPlayingElem.textContent = 'Selecciona una canción';
            }
        });
    }

    updateUserMenuVisibility();
    initializeAccountButtonListener();
    initializeAvatarUpload();
    initializeSongMenuListeners();
    initializeUserMenuToggle();
    initializeLikeButtons();
});


document.body.addEventListener('htmx:beforeRequest', function(event) {
    if (event.detail.elt.id !== 'scan-button' && event.detail.elt.id !== 'quick-scan-button' && event.detail.elt.id !== 'cover-scan-button') {
        Swal.fire({
            title: 'Cargando...',
            allowOutsideClick: false,
            showConfirmButton: false,
            didOpen: () => Swal.showLoading()
        });
    }
});

document.body.addEventListener('htmx:afterRequest', function(event) {
    Swal.close();
    initializeLikeButtons();
    initializeAvatarUpload();
    updateUserMenuVisibility();
});

window.showQueue = function() {
    console.log('Cola actual:', songQueue.map(song => song.name));
};