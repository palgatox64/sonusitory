// Global variables for music playback functionality
let songQueue = [];  // Array to store queued songs for continuous playback
let songMenuListenersInitialized = false;  // Flag to prevent duplicate event listener initialization


/**
 * Plays a song by setting up the audio player and updating the UI
 * @param {string} songId - The ID of the song to play
 * @param {string} songName - The display name of the song
 */
function playSong(songId, songName) {
    const songUrl = `/play/${songId}/`;
    const nowPlayingElem = document.getElementById('now-playing');
    const audioPlayer = document.getElementById('main-audio-player');

    if (nowPlayingElem && audioPlayer) {
        // Update the "now playing" display
        nowPlayingElem.textContent = `Reproduciendo: ${songName}`;
        // Set the audio source and start playback
        audioPlayer.src = songUrl;
        audioPlayer.load();
        audioPlayer.play().catch(e => console.error("Error al reproducir:", e));
    }
}


/**
 * Initializes avatar upload functionality with file validation and preview
 * Handles image upload to Imgur service with user confirmation dialog
 */
function initializeAvatarUpload() {
    const changeAvatarButton = document.getElementById('change-avatar-button');
    if (!changeAvatarButton) return;

    const avatarInput = document.getElementById('avatar-input');
    const avatarPreview = document.getElementById('avatar-preview');
    let originalAvatarSrc = avatarPreview.src;

    // Remove existing event listeners by cloning elements
    changeAvatarButton.replaceWith(changeAvatarButton.cloneNode(true));
    const newChangeAvatarButton = document.getElementById('change-avatar-button');

    avatarInput.replaceWith(avatarInput.cloneNode(true));
    const newAvatarInput = document.getElementById('avatar-input');

    // Handle avatar change button click
    newChangeAvatarButton.addEventListener('click', () => {
        originalAvatarSrc = avatarPreview.src;
        newAvatarInput.click();
    });

    // Handle file selection and validation
    newAvatarInput.addEventListener('change', () => {
        const file = newAvatarInput.files[0];
        if (!file) return;

        // Validate file type
        if (!file.type.startsWith('image/')) {
            Swal.fire('Error', 'Por favor selecciona un archivo de imagen válido.', 'error');
            return;
        }

        // Validate file size (5MB limit)
        if (file.size > 5 * 1024 * 1024) {
            Swal.fire('Error', 'La imagen es demasiado grande. Máximo 5MB.', 'error');
            return;
        }

        // Preview the image and show confirmation dialog
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
                    // Upload image to Imgur
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
                            // Update avatar preview and navigation avatar
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
                        // Restore original avatar on error
                        avatarPreview.src = originalAvatarSrc;
                        Swal.fire('¡Error!', err.message || 'Ocurrió un error de red.', 'error');
                    });

                } else {
                    // Restore original avatar on cancel
                    avatarPreview.src = originalAvatarSrc;
                    Swal.fire("Cancelado", "Tu foto de perfil no ha cambiado.", "info");
                }
            });
        };
        reader.readAsDataURL(file);
        newAvatarInput.value = '';
    });
}

/**
 * Updates user menu visibility based on current page
 * Hides the dropdown menu on the account page to avoid redundancy
 */
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

/**
 * Initializes user menu dropdown toggle functionality
 * Handles click events for showing/hiding the dropdown menu
 */
function initializeUserMenuToggle() {
    const userMenuToggle = document.getElementById('user-menu-toggle');
    const userMenu = document.getElementById('user-menu');
    
    if (userMenuToggle && userMenu) {
        // Toggle menu on button click
        userMenuToggle.addEventListener('click', function(e) {
            e.stopPropagation();
            userMenu.classList.toggle('show');
        });

        // Close menu when clicking outside
        document.addEventListener('click', function(e) {
            if (!userMenuToggle.contains(e.target) && !userMenu.contains(e.target)) {
                userMenu.classList.remove('show');
            }
        });
    }
}


/**
 * Initializes the account unlink button with confirmation dialog
 * Shows different messages based on whether user has credentials
 */
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


/**
 * Opens a modal dialog to select a playlist for adding a song
 * Fetches user's playlists and displays them in a selectable format
 * @param {string} songId - The ID of the song to add to playlist
 * @param {string} songName - The display name of the song
 */
function openPlaylistModal(songId, songName) {
    console.log('Abriendo modal para canción:', songId, songName);
    
    // Fetch user's playlists from the server
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
            
            // Handle different response scenarios
            if (data.error) {
                console.error('Error del servidor:', data.error);
                playlistOptions = '<p style="text-align: center; color: #ff6b6b; margin: 20px 0;">Error al cargar playlists</p>';
            } else if (data.playlists && data.playlists.length === 0) {
                // No playlists found - show create new playlist link
                playlistOptions = '<p style="text-align: center; color: #b3b3b3; margin: 20px 0;">No tienes playlists creadas. <br><a href="/playlists/" style="color: #bb86fc;">Crear una nueva playlist</a></p>';
            } else if (data.playlists) {
                // Generate HTML for each playlist with cover image and song count
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

            // Display the playlist selection modal
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
                    // Add click event listeners to playlist options
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

/**
 * Adds a song to the specified playlist
 * @param {string} songId - The ID of the song to add
 * @param {string} playlistId - The ID of the target playlist
 * @param {string} songName - The display name of the song
 * @param {string} playlistName - The display name of the playlist
 */
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
            // Show success toast notification
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


/**
 * Handles song like/unlike functionality with undo support
 * Updates UI immediately and provides undo option for unlike actions
 * @param {string} songId - The ID of the song to like/unlike
 * @param {HTMLElement} likeButton - The like button element that was clicked
 */
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
                // Song was liked - update UI and show success toast
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
                // Song was unliked - update UI and show undo option
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
                        // Handle undo action - restore the like with original timestamp
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

                                // Reload page if song was removed from liked songs page
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

                // Remove song from liked songs page with animation
                if (isInLikedSongsPage && songLi) {
                    setTimeout(() => {
                        if (!likeButton.classList.contains('liked')) {
                            songLi.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                            songLi.style.opacity = '0';
                            songLi.style.transform = 'translateX(-20px)';

                            setTimeout(() => {
                                if (!likeButton.classList.contains('liked')) {
                                    songLi.remove();

                                    // Show empty message if no songs left
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

/**
 * Initializes like button event listeners
 * Removes existing listeners to prevent duplicates and adds new ones
 */
function initializeLikeButtons() {
    console.log('Inicializando botones de like...');

    // Remove existing event listeners by cloning buttons
    document.querySelectorAll('.like-btn').forEach(button => {
        const newButton = button.cloneNode(true);
        button.parentNode.replaceChild(newButton, button);
    });
    
    // Add fresh event listeners to all like buttons
    document.querySelectorAll('.like-btn').forEach(button => {
        button.addEventListener('click', function(e) {
            e.stopPropagation();
            const songId = this.dataset.songId;
            window.handleLikeClick(songId, this);
        });
    });
    
    console.log('Botones de like inicializados:', document.querySelectorAll('.like-btn').length);
}


/**
 * Retrieves CSRF token from various sources (meta tag, form input, or cookie)
 * @returns {string|null} The CSRF token or null if not found
 */
function getCsrfToken() {
    // Try to get CSRF token from meta tag first
    let csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
    // Fallback to form input
    if (!csrfToken) csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
    // Fallback to cookie
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

/**
 * Loads a script only once by checking if it's already loaded or loading
 * @param {string} src - The source URL of the script to load
 * @returns {Promise} Promise that resolves when script is loaded
 */
function loadScriptOnce(src) {
    return new Promise((resolve, reject) => {
        // Check if the library is already available
        if (window.Sortable) return resolve();
        // Check if script is already loading
        if (document.querySelector(`script[data-key="${src}"]`)) {
            document.querySelector(`script[data-key="${src}"]`).addEventListener('load', resolve, { once: true });
            document.querySelector(`script[data-key="${src}"]`).addEventListener('error', reject, { once: true });
            return;
        }
        // Load the script
        const s = document.createElement('script');
        s.src = src;
        s.async = true;
        s.dataset.key = src;
        s.onload = resolve;
        s.onerror = reject;
        document.head.appendChild(s);
    });
}


/**
 * Main DOM Content Loaded event listener
 * Initializes all components when the page is fully loaded
 */
document.addEventListener('DOMContentLoaded', function() {
    const audioPlayer = document.getElementById('main-audio-player');
    const nowPlayingElem = document.getElementById('now-playing');

    if (audioPlayer && nowPlayingElem) {
        // Handle audio player events for queue functionality
        audioPlayer.addEventListener('play', () => {
            const songList = document.getElementById('song-list');
            if (songList) songList.classList.add('playback-active');
        });

        audioPlayer.addEventListener('pause', () => {
            const songList = document.getElementById('song-list');
            if (songList) songList.classList.remove('playback-active');
        });

        // Auto-play next song when current song ends
        audioPlayer.addEventListener('ended', () => {
            console.log('Canción terminada. Cola actual:', songQueue.map(song => song.name));
            if (songQueue.length > 0) {
                const nextSong = songQueue.shift();
                console.log('Reproduciendo siguiente:', nextSong.name);
                playSong(nextSong.id, nextSong.name);
            } else {
                // No more songs in queue - reset UI
                const songList = document.getElementById('song-list');
                if (songList) songList.classList.remove('playbook-active');
                nowPlayingElem.textContent = 'Selecciona una canción';
            }
        });
    }

    // Initialize all UI components
    updateUserMenuVisibility();
    initializeAccountButtonListener();
    initializeAvatarUpload();
    initializeSongMenuListeners();
    initializeUserMenuToggle();
    initializeLikeButtons();
});


/**
 * HTMX beforeRequest event handler
 * Shows loading spinner for non-scan button requests
 */
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

/**
 * HTMX afterRequest event handler
 * Handles scan task initiation and re-initializes components after HTMX requests
 */
document.body.addEventListener('htmx:afterRequest', function(event) {
    Swal.close();
    // Re-initialize components after HTMX content updates
    initializeLikeButtons();
    initializeAvatarUpload();
    initializeAccountButtonListener();
    updateUserMenuVisibility();
    
    try {
        const srcEl = event?.detail?.elt;
        if (!srcEl || !srcEl.id) return;
        
        // Handle scan button responses
        const scanButtons = new Set(['scan-button', 'quick-scan-button', 'cover-scan-button']);
        if (!scanButtons.has(srcEl.id)) return;

        const xhr = event?.detail?.xhr;
        if (!xhr) return;
        
        // Check for HTTP errors
        if (typeof xhr.status === 'number' && xhr.status >= 400) {
            Swal.fire({
                icon: 'error',
                title: 'No se pudo iniciar el escaneo',
                text: 'Inténtalo nuevamente en unos segundos.'
            });
            return;
        }
        
        // Parse response to get task ID
        let data = null;
        try { data = JSON.parse(xhr.responseText); } catch (_) { /* noop */ }
        const taskId = data?.task_id;
        if (!taskId) return;

        // Map scan button IDs to user-friendly labels
        const scanLabels = {
            'scan-button': 'Escaneo completo de librería',
            'quick-scan-button': 'Búsqueda rápida de nuevas canciones',
            'cover-scan-button': 'Búsqueda de portadas'
        };

        // Start monitoring the scan progress
        showScanProgress(taskId, scanLabels[srcEl.id] || 'Proceso en ejecución');
    } catch (e) {
        console.error('Error gestionando progreso de escaneo:', e);
    }
});

/**
 * Debug function to show current song queue
 */
window.showQueue = function() {
    console.log('Cola actual:', songQueue.map(song => song.name));
};

/**
 * Shows scan progress modal and starts polling for task status
 * @param {string} taskId - The Celery task ID to monitor
 * @param {string} title - The title to display in the progress modal
 */
function showScanProgress(taskId, title) {
    Swal.fire({
        title: title,
        html: renderScanHtml({ status: 'PENDING', info: { step: 'queued' } }),
        allowOutsideClick: false,
        showConfirmButton: false,
        didOpen: () => {
            pollTaskUntilDone(taskId, title);
        }
    });
}

/**
 * Renders HTML content for scan progress display
 * @param {Object} payload - Task status payload with status and info
 * @returns {string} HTML string for the progress display
 */
function renderScanHtml(payload) {
    const status = payload?.status || 'PENDING';
    const info = payload?.info || {};
    const lines = [];

    if (status === 'PENDING') {
        lines.push('En cola para iniciar...');
    } else if (status === 'STARTED' || status === 'PROGRESS') {
        const step = (info.step || '').toString();
        const current = info.current;
        const total = info.total;

        lines.push(formatStep(step, current, total));
        
        // Show progress bar if we have current/total numbers
        if (typeof current === 'number' && typeof total === 'number' && total > 0) {
            const pct = Math.max(0, Math.min(100, Math.round((current / total) * 100)));
            lines.push(`<div style="margin:8px auto 0; height:8px; width:80%; background:#333; border-radius:4px; overflow:hidden;">
                <div style="height:100%; width:${pct}%; background:#bb86fc;"></div>
            </div>`);
        } else {
            // Show indeterminate progress bar
            lines.push('<div class="swal2-timer-progress-bar" style="display:block; width:80%; margin:8px auto 0; opacity:1; background:#333; height:4px;"></div>');
        }
    } else if (status === 'SUCCESS') {
        const msg = typeof info === 'string' ? info : 'Proceso completado correctamente.';
        lines.push(`<span style="color:#000;">${escapeHtml(msg)}</span>`);
    } else if (status === 'FAILURE') {
        const err = info?.exc_message || info?.message || 'Ocurrió un error en el proceso.';
        lines.push(`<span style="color:#ff6b6b;">${escapeHtml(err)}</span>`);
    } else {
        lines.push(`Estado: ${escapeHtml(status)}`);
    }

    // Show spinner for active states
    const showSpinner = status === 'PENDING' || status === 'STARTED' || status === 'PROGRESS';
    const spinnerHtml = showSpinner
        ? '<span class="spinner" style="width:14px; height:14px; border:2px solid #bbb; border-top-color:#bb86fc; border-radius:50%; display:inline-block; animation:spin 0.8s linear infinite;"></span>'
        : '';

    return `
        <div style="text-align:center;">
            <div style="display:flex; flex-direction:column; align-items:center; gap:12px;">
                ${spinnerHtml}
                <div class="scan-lines" style="max-width: 520px;">${lines.join('<br>')}</div>
            </div>
        </div>
        <style>
            @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg);} }
        </style>
    `;
}

/**
 * Formats scan step messages with progress information
 * @param {string} step - The current step identifier
 * @param {number} current - Current progress count
 * @param {number} total - Total items to process
 * @returns {string} Formatted step message
 */
function formatStep(step, current, total) {
    // Map of step identifiers to user-friendly messages
    const map = {
        searching_audio_files: 'Buscando archivos de audio en tu Drive...',
        processing_audio_files: (c) => `Procesando archivos de audio${typeof c === 'number' ? ` (procesados: ${c})` : ''}...`,
        getting_existing_files: 'Consultando canciones existentes...',
        searching_new_files: 'Buscando nuevas canciones...',
        getting_existing_albums: 'Buscando álbumes sin portada...',
        covers: (c, t) => `Buscando portadas${typeof c === 'number' && typeof t === 'number' ? ` (${c} de ${t})` : ''}...`,
        queued: 'En cola...'
    };

    if (typeof map[step] === 'function') {
        return map[step](current, total);
    }

    return step ? `Procesando: ${step} ${typeof current === 'number' && typeof total === 'number' ? `(${current}/${total})` : ''}` : 'Procesando...';
}

/**
 * Polls task status until completion and updates the progress modal
 * @param {string} taskId - The Celery task ID to monitor
 * @param {string} title - The title for the progress modal
 */
function pollTaskUntilDone(taskId, title) {
    let stopped = false;
    const controller = new AbortController();

    const tick = () => {
        if (stopped) return;
        
        // Fetch current task status
        fetch(`/task-status/${taskId}/`, { signal: controller.signal })
            .then(r => r.json())
            .then(data => {
                const status = data?.status;
                const info = data?.info;

                if (status === 'SUCCESS') {
                    // Task completed successfully
                    Swal.update({
                        title: title,
                        html: renderScanHtml({ status, info }),
                        showConfirmButton: true,
                        confirmButtonText: 'Ir a inicio',
                        confirmButtonColor: '#bb86fc',
                        showCancelButton: false,
                        allowOutsideClick: true,
                        icon: 'success'
                    });
                    stopped = true;
                    // Navigate to home page when user clicks confirm
                    Swal.getConfirmButton()?.addEventListener('click', () => {
                        window.location.href = 'http://localhost:8000/';
                    });
                } else if (status === 'FAILURE') {
                    // Task failed
                    Swal.update({
                        title: 'Error en el proceso',
                        html: renderScanHtml({ status, info }),
                        showConfirmButton: true,
                        confirmButtonText: 'Cerrar',
                        confirmButtonColor: '#d33',
                        icon: 'error'
                    });
                    stopped = true;
                } else {
                    // Task still in progress - update display and poll again
                    Swal.update({
                        title: title,
                        html: renderScanHtml({ status: status || 'PROGRESS', info })
                    });
                    setTimeout(tick, 2000);
                }
            })
            .catch(err => {
                console.error('Error consultando estado de tarea:', err);
                // Continue polling on error with longer delay
                if (!stopped) setTimeout(tick, 2500);
            });
    };

    tick();
}

/**
 * Escapes HTML characters to prevent XSS attacks
 * @param {string} text - Text to escape
 * @returns {string} HTML-safe text
 */
function escapeHtml(text) {
    if (typeof text !== 'string') return text;
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}