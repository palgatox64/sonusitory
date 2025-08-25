/**
 * Initializes drag-and-drop sorting functionality for playlist songs
 * Loads SortableJS library and sets up drag handles with save functionality
 */
async function initializePlaylistSorting() {
    const sortableList = document.getElementById('sortable-song-list');
    if (!sortableList) return;

    // Prevent duplicate initialization
    if (sortableList.dataset.sortableInit === '1') return;
    sortableList.dataset.sortableInit = '1';

    try {
        // Load SortableJS library from CDN with fallback
        await loadScriptOnce('https://cdn.jsdelivr.net/npm/sortablejs@1.15.0/Sortable.min.js')
            .catch(() => loadScriptOnce('https://unpkg.com/sortablejs@1.15.0/Sortable.min.js'));
    } catch (e) {
        console.error('No se pudo cargar SortableJS:', e);
        delete sortableList.dataset.sortableInit;
        return;
    }

    // Initialize sortable with drag handle and visual feedback
    const sortable = new Sortable(sortableList, {
        handle: '.song-drag-handle',  // Only allow dragging from handle
        animation: 150,               // Smooth animation duration
        ghostClass: 'sortable-ghost', // Class for drag preview
        chosenClass: 'sortable-chosen', // Class for selected item
        dragClass: 'sortable-drag',     // Class while dragging
        onEnd: function() {
            // Save new order to server when drag ends
            const playlistId = sortableList.dataset.playlistId;
            const songOrders = Array.from(sortableList.children).map(li => li.dataset.songId);

            // Show saving notification
            const Toast = Swal.mixin({ toast: true, position: 'top-end', showConfirmButton: false, timer: 2000, timerProgressBar: true });
            Toast.fire({ icon: 'info', title: 'Guardando nuevo orden...' });

            // Prepare form data with new order
            const formData = new FormData();
            formData.append('csrfmiddlewaretoken', getCsrfToken());
            songOrders.forEach(songId => formData.append('song_orders[]', songId));

            // Send new order to server
            fetch(`/reorder-playlist/${playlistId}/`, { method: 'POST', body: formData })
                .then((r) => {
                    if (r.ok) {
                        Toast.fire({ icon: 'success', title: 'Orden actualizado' });
                    } else {
                        throw new Error('Error al actualizar orden');
                    }
                })
                .catch(err => {
                    console.error('Error:', err);
                    Toast.fire({ icon: 'error', title: 'Error al guardar el orden' });
                });
        }
    });

    // Store sortable instance for cleanup
    sortableList.sortableInstance = sortable;
}

/**
 * Handles removing a song from a playlist with confirmation dialog
 * Includes smooth animation and UI updates
 * @param {HTMLElement} buttonEl - The remove button element that was clicked
 */
function handleRemoveFromPlaylist(buttonEl) {
    const songId = buttonEl.dataset.songId;
    const playlistId = buttonEl.dataset.playlistId;
    const songItem = buttonEl.closest('li');
    const songTitle = songItem?.querySelector('.song-title')?.textContent || 'la pista';

    // Show confirmation dialog
    Swal.fire({
        title: '¿Quitar canción?',
        text: `¿Estás seguro de que quieres quitar "${songTitle}" de esta playlist?`,
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'Sí, quitar',
        cancelButtonText: 'Cancelar',
        confirmButtonColor: '#dc3545'
    }).then((result) => {
        if (!result.isConfirmed) return;

        // Send removal request to server
        const formData = new FormData();
        formData.append('csrfmiddlewaretoken', getCsrfToken());

        fetch(`/remove-from-playlist/${playlistId}/${songId}/`, { method: 'POST', body: formData })
        .then(response => {
            if (!response.ok) throw new Error('Error al eliminar la pista');

            if (songItem) {
                // Animate song removal from UI
                songItem.style.transition = 'all 0.3s ease';
                songItem.style.opacity = '0';
                songItem.style.transform = 'translateX(-20px)';
                setTimeout(() => {
                    songItem.remove();
                    // Update song count in header
                    const countElement = document.querySelector('h2');
                    if (countElement) {
                        const currentCount = document.querySelectorAll('.sortable-song-item').length;
                        countElement.textContent = `${currentCount} pistas`;
                    }
                    // Show success notification
                    const Toast = Swal.mixin({ toast: true, position: 'top-end', showConfirmButton: false, timer: 3000, timerProgressBar: true });
                    Toast.fire({ icon: 'success', title: `"${songTitle}" eliminada de la playlist` });
                }, 300);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            Swal.fire({ icon: 'error', title: 'Error', text: 'No se pudo eliminar la pista de la playlist' });
        });
    });
}

/**
 * Función helper para manejar la selección de imagen con cropper
 */
function handleImageSelection(inputElement, previewElement, callback) {
    inputElement.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (!file) return;

        // Validar tipo de archivo
        if (!file.type.startsWith('image/')) {
            Swal.fire('Error', 'Por favor selecciona un archivo de imagen válido.', 'error');
            e.target.value = '';
            return;
        }

        // Validar tamaño (5MB)
        if (file.size > 5 * 1024 * 1024) {
            Swal.fire('Error', 'La imagen es demasiado grande. Máximo 5MB.', 'error');
            e.target.value = '';
            return;
        }

        // Usar el cropper
        if (window.imageCropper) {
            try {
                window.imageCropper.open(file, (croppedFile, previewUrl) => {
                    previewElement.src = previewUrl;
                    previewElement.style.border = '2px solid #bb86fc';
                    if (callback) callback(croppedFile);
                }, {
                    aspectRatio: 1, // Portada cuadrada
                    viewMode: 1,
                    autoCropArea: 0.9
                }).catch((error) => {
                    console.error('Error al abrir el cropper:', error);
                    // Fallback
                    const reader = new FileReader();
                    reader.onload = (e) => {
                        previewElement.src = e.target.result;
                        previewElement.style.border = '2px solid #bb86fc';
                        if (callback) callback(file);
                    };
                    reader.readAsDataURL(file);
                });
            } catch (error) {
                console.error('Error con el cropper:', error);
                // Fallback
                const reader = new FileReader();
                reader.onload = (e) => {
                    previewElement.src = e.target.result;
                    previewElement.style.border = '2px solid #bb86fc';
                    if (callback) callback(file);
                };
                reader.readAsDataURL(file);
            }
        } else {
            // Fallback
            const reader = new FileReader();
            reader.onload = (e) => {
                previewElement.src = e.target.result;
                previewElement.style.border = '2px solid #bb86fc';
                if (callback) callback(file);
            };
            reader.readAsDataURL(file);
        }

        e.target.value = '';
    });
}

/**
 * Initializes the create playlist button with modal dialog functionality
 * Handles name input, cover image upload, and form validation
 */
function initializeCreatePlaylistButton() {
    const createPlaylistBtn = document.getElementById('create-playlist-btn');
    if (!createPlaylistBtn) return;

    // Remove existing event listeners to prevent duplicates
    createPlaylistBtn.replaceWith(createPlaylistBtn.cloneNode(true));
    const newBtn = document.getElementById('create-playlist-btn');
    
    newBtn.addEventListener('click', function() {
        let selectedCoverFile = null;

        // Show create playlist modal with form
        Swal.fire({
            title: 'Crear Nueva Playlist',
            html: `
                <div style="text-align: left;">
                    <label for="playlist-name" style="display: block; margin-bottom: 0.5rem; font-weight: bold;">Nombre de la playlist:</label>
                    <input type="text" id="playlist-name" class="swal2-input" placeholder="Ingresa el nombre..." style="margin-bottom: 1rem;">
                    
                    <label style="display: block; margin-bottom: 0.5rem; font-weight: bold;">Imagen de portada (opcional):</label>
                    <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 1rem;">
                        <img id="playlist-cover-preview" 
                             src="/static/images/default_cover.png" 
                             alt="Vista previa" 
                             style="width: 80px; height: 80px; border-radius: 8px; object-fit: cover; border: 2px solid #ccc;">
                        <div>
                            <button type="button" id="change-playlist-cover-button" 
                                    style="background: linear-gradient(45deg, #bb86fc, #6200ea); color: white; border: none; padding: 10px 20px; border-radius: 25px; cursor: pointer; font-weight: 600; transition: all 0.3s ease; box-shadow: 0 4px 15px rgba(187, 134, 252, 0.3);"
                                    onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 6px 20px rgba(187, 134, 252, 0.4)'"
                                    onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 4px 15px rgba(187, 134, 252, 0.3)'">
                                Cambiar Imagen
                            </button>
                            <input type="file" id="playlist-cover" accept="image/*" style="display: none;">
                            <br>
                            <small style="color: #666; display: block; margin-top: 0.5rem;">Si no seleccionas una imagen, se usará la portada por defecto.</small>
                        </div>
                    </div>
                </div>
            `,
            showCancelButton: true,
            confirmButtonText: 'Crear',
            cancelButtonText: 'Cancelar',
            confirmButtonColor: '#bb86fc',
            cancelButtonColor: '#dc3545',
            didOpen: () => {
                // Set up cover image selection functionality
                const changeCoverButton = document.getElementById('change-playlist-cover-button');
                const coverInput = document.getElementById('playlist-cover');
                const coverPreview = document.getElementById('playlist-cover-preview');
                
                changeCoverButton.addEventListener('click', () => {
                    coverInput.click();
                });

                // Handle image selection with cropper
                handleImageSelection(coverInput, coverPreview, (croppedFile) => {
                    selectedCoverFile = croppedFile;
                });
            },
            preConfirm: () => {
                // Validate form before submission
                const name = document.getElementById('playlist-name').value;
                
                if (!name || name.trim() === '') {
                    Swal.showValidationMessage('Debes ingresar un nombre para la playlist');
                    return false;
                }
                
                return { name: name.trim(), coverFile: selectedCoverFile };
            }
        }).then((result) => {
            if (result.isConfirmed) {
                const { name, coverFile } = result.value;
                
                // Show loading state if uploading image
                if (coverFile) {
                    Swal.fire({
                        title: 'Creando playlist...',
                        text: 'Subiendo imagen, por favor espera.',
                        allowOutsideClick: false,
                        showConfirmButton: false,
                        didOpen: () => Swal.showLoading()
                    });
                }
                
                // Prepare form data for submission
                const formData = new FormData();
                formData.append('csrfmiddlewaretoken', getCsrfToken());
                formData.append('name', name);
                if (coverFile) {
                    formData.append('cover_image', coverFile);
                }
                
                // Submit playlist creation request
                fetch(window.createPlaylistUrl, {
                    method: 'POST',
                    body: formData
                })
                .then(response => {
                    if (response.ok) {
                        // Show success notification
                        const Toast = Swal.mixin({
                            toast: true,
                            position: 'top-end',
                            showConfirmButton: false,
                            timer: 3000,
                            timerProgressBar: true
                        });
                        Toast.fire({
                            icon: 'success',
                            title: `Playlist "${name}" creada exitosamente`
                        });
                        
                        // Refresh playlist list view
                        htmx.ajax('GET', window.playlistListUrl, {
                            target: '.main-content',
                            swap: 'innerHTML'
                        });
                        
                    } else {
                        throw new Error('Error al crear la playlist');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    Swal.fire({
                        icon: 'error',
                        title: 'Error',
                        text: 'No se pudo crear la playlist'
                    });
                });
            }
        });
    });
}

/**
 * Initializes the edit playlist button with modal dialog functionality
 * Pre-fills form with current playlist data and handles updates
 */
function initializeEditPlaylistButton() {
    const editPlaylistBtn = document.getElementById('edit-playlist-btn');
    if (!editPlaylistBtn) return;

    // Remove existing event listeners to prevent duplicates
    editPlaylistBtn.replaceWith(editPlaylistBtn.cloneNode(true));
    const newBtn = document.getElementById('edit-playlist-btn');
    
    newBtn.addEventListener('click', function() {
        // Get current playlist data from button attributes
        const playlistId = newBtn.dataset.playlistId;
        const currentName = newBtn.dataset.playlistName || '';
        const currentCover = newBtn.dataset.playlistCover || '/static/images/default_cover.png';
        let selectedCoverFile = null;

        // Show edit playlist modal with pre-filled data
        Swal.fire({
            title: 'Editar Playlist',
            html: `
                <div style="text-align: left;">
                    <label for="playlist-name" style="display: block; margin-bottom: 0.5rem; font-weight: bold;">Nombre de la playlist:</label>
                    <input type="text" id="playlist-name" class="swal2-input" placeholder="Ingresa el nombre..." value="${currentName.replace(/"/g, '&quot;')}" style="margin-bottom: 1rem;">
                    
                    <label style="display: block; margin-bottom: 0.5rem; font-weight: bold;">Imagen de portada:</label>
                    <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 1rem;">
                        <img id="playlist-cover-preview" 
                             src="${currentCover.replace(/"/g, '&quot;')}" 
                             alt="Vista previa" 
                             style="width: 80px; height: 80px; border-radius: 8px; object-fit: cover; border: 2px solid #ccc;">
                        <div>
                            <button type="button" id="change-playlist-cover-button" 
                                    style="background: linear-gradient(45deg, #bb86fc, #6200ea); color: white; border: none; padding: 10px 20px; border-radius: 25px; cursor: pointer; font-weight: 600; transition: all 0.3s ease; box-shadow: 0 4px 15px rgba(187, 134, 252, 0.3);"
                                    onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 6px 20px rgba(187, 134, 252, 0.4)'"
                                    onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 4px 15px rgba(187, 134, 252, 0.3)'">
                                Cambiar Imagen
                            </button>
                            <input type="file" id="playlist-cover" accept="image/*" style="display: none;">
                            <br>
                            <small style="color: #666; display: block; margin-top: 0.5rem;">Si no seleccionas una imagen, se mantendrá la actual.</small>
                        </div>
                    </div>
                </div>
            `,
            showCancelButton: true,
            confirmButtonText: 'Guardar',
            cancelButtonText: 'Cancelar',
            confirmButtonColor: '#bb86fc',
            cancelButtonColor: '#dc3545',
            didOpen: () => {
                // Set up cover image selection functionality
                const changeCoverButton = document.getElementById('change-playlist-cover-button');
                const coverInput = document.getElementById('playlist-cover');
                const coverPreview = document.getElementById('playlist-cover-preview');

                changeCoverButton.addEventListener('click', () => {
                    coverInput.click();
                });

                // Handle image selection with cropper
                handleImageSelection(coverInput, coverPreview, (croppedFile) => {
                    selectedCoverFile = croppedFile;
                });
            },
            preConfirm: () => {
                // Validate form before submission
                const name = document.getElementById('playlist-name').value;

                if (!name || name.trim() === '') {
                    Swal.showValidationMessage('Debes ingresar un nombre para la playlist');
                    return false;
                }
                return { name: name.trim(), coverFile: selectedCoverFile };
            }
        }).then((result) => {
            if (!result.isConfirmed) return;

            const { name, coverFile } = result.value;

            // Show loading state if uploading image
            if (coverFile) {
                Swal.fire({
                    title: 'Guardando cambios...',
                    text: 'Subiendo imagen, por favor espera.',
                    allowOutsideClick: false,
                    showConfirmButton: false,
                    didOpen: () => Swal.showLoading()
                });
            }

            // Prepare form data for submission
            const formData = new FormData();
            formData.append('csrfmiddlewaretoken', getCsrfToken());
            formData.append('name', name);
            if (coverFile) formData.append('cover_image', coverFile);

            // Submit playlist update request
            fetch(`/edit-playlist/${playlistId}/`, { method: 'POST', body: formData })
                .then(resp => {
                    if (!resp.ok) throw new Error('Error al editar la playlist');
                    // Show success notification
                    const Toast = Swal.mixin({ toast: true, position: 'top-end', showConfirmButton: false, timer: 3000, timerProgressBar: true });
                    Toast.fire({ icon: 'success', title: `Playlist actualizada` });

                    // Refresh current detail view
                    htmx.ajax('GET', window.location.pathname, {
                        target: '.main-content',
                        swap: 'innerHTML'
                    });
                })
                .catch(err => {
                    console.error(err);
                    Swal.fire({ icon: 'error', title: 'Error', text: 'No se pudo actualizar la playlist' });
                });
        });
    });
}

/**
 * Initializes the delete playlist button with confirmation dialog
 * Handles playlist deletion and navigation back to playlist list
 */
function initializeDeletePlaylistButton() {
    const deletePlaylistBtn = document.getElementById('delete-playlist-btn');
    if (!deletePlaylistBtn) return;

    // Remove existing event listeners to prevent duplicates
    deletePlaylistBtn.replaceWith(deletePlaylistBtn.cloneNode(true));
    const newBtn = document.getElementById('delete-playlist-btn');
    
    newBtn.addEventListener('click', function() {
        const playlistId = newBtn.dataset.playlistId;
        const playlistName = newBtn.dataset.playlistName || 'esta playlist';

        // Show confirmation dialog with warning
        Swal.fire({
            title: '¿Eliminar playlist?',
            text: `¿Seguro que deseas eliminar "${playlistName}"? Esta acción no se puede deshacer.`,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: 'Sí, eliminar',
            cancelButtonText: 'Cancelar',
            confirmButtonColor: '#dc3545'
        }).then((result) => {
            if (!result.isConfirmed) return;

            // Send deletion request to server
            const formData = new FormData();
            formData.append('csrfmiddlewaretoken', getCsrfToken());

            fetch(`/delete-playlist/${playlistId}/`, { method: 'POST', body: formData })
                .then(resp => {
                    if (!resp.ok) throw new Error('Error al eliminar la playlist');
                    // Show success notification
                    const Toast = Swal.mixin({ toast: true, position: 'top-end', showConfirmButton: false, timer: 3000, timerProgressBar: true });
                    Toast.fire({ icon: 'success', title: `Playlist eliminada` });

                    // Navigate back to playlist list
                    htmx.ajax('GET', window.playlistListUrl, {
                        target: '.main-content',
                        swap: 'innerHTML'
                    });
                })
                .catch(err => {
                    console.error(err);
                    Swal.fire({ icon: 'error', title: 'Error', text: 'No se pudo eliminar la playlist' });
                });
        });
    });
}

/**
 * Initializes remove from playlist buttons for all songs in the current playlist
 * Removes existing listeners and adds fresh ones to prevent duplicates
 */
function initializeRemoveFromPlaylist() {
    const buttons = document.querySelectorAll('.remove-from-playlist-btn');
    if (!buttons.length) return;

    // Remove existing event listeners by cloning buttons
    buttons.forEach(btn => btn.replaceWith(btn.cloneNode(true)));
    const freshButtons = document.querySelectorAll('.remove-from-playlist-btn');
    
    // Add fresh event listeners
    freshButtons.forEach(btn => {
        btn.addEventListener('click', () => handleRemoveFromPlaylist(btn));
    });
}

/**
 * Cleans up sortable instances and listeners before HTMX content swap
 * Prevents memory leaks and duplicate functionality
 */
function cleanupPlaylistListeners() {
    const sortableLists = document.querySelectorAll('.song-list-sortable');
    sortableLists.forEach(list => {
        // Destroy sortable instances if they exist
        if (list.sortableInstance) {
            list.sortableInstance.destroy();
            list.sortableInstance = null;
        }
        // Reset initialization flag
        delete list.dataset.sortableInit;
    });
}

// HTMX event listeners for proper cleanup and re-initialization

/**
 * Cleanup before HTMX swaps content to prevent conflicts
 */
document.body.addEventListener('htmx:beforeSwap', function() {
    cleanupPlaylistListeners();
});

/**
 * Re-initialize all playlist functionality after HTMX updates content
 */
document.body.addEventListener('htmx:afterRequest', function() {
    initializeCreatePlaylistButton();
    initializeEditPlaylistButton();
    initializeDeletePlaylistButton();
    initializePlaylistSorting();
    initializeRemoveFromPlaylist();
});


/**
 * Initialize all playlist functionality when page first loads
 */
document.addEventListener('DOMContentLoaded', function() {
    initializeCreatePlaylistButton();
    initializeEditPlaylistButton();
    initializeDeletePlaylistButton();
    initializePlaylistSorting();
    initializeRemoveFromPlaylist();
});