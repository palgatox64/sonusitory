// Funciones de ordenamiento de playlist
async function initializePlaylistSorting() {
    const sortableList = document.getElementById('sortable-song-list');
    if (!sortableList) return;

    if (sortableList.dataset.sortableInit === '1') return;
    sortableList.dataset.sortableInit = '1';

    try {
        await loadScriptOnce('https://cdn.jsdelivr.net/npm/sortablejs@1.15.0/Sortable.min.js')
            .catch(() => loadScriptOnce('https://unpkg.com/sortablejs@1.15.0/Sortable.min.js'));
    } catch (e) {
        console.error('No se pudo cargar SortableJS:', e);
        delete sortableList.dataset.sortableInit;
        return;
    }

    const sortable = new Sortable(sortableList, {
        handle: '.song-drag-handle',
        animation: 150,
        ghostClass: 'sortable-ghost',
        chosenClass: 'sortable-chosen',
        dragClass: 'sortable-drag',
        onEnd: function() {
            const playlistId = sortableList.dataset.playlistId;
            const songOrders = Array.from(sortableList.children).map(li => li.dataset.songId);

            const Toast = Swal.mixin({ toast: true, position: 'top-end', showConfirmButton: false, timer: 2000, timerProgressBar: true });
            Toast.fire({ icon: 'info', title: 'Guardando nuevo orden...' });

            const formData = new FormData();
            formData.append('csrfmiddlewaretoken', getCsrfToken());
            songOrders.forEach(songId => formData.append('song_orders[]', songId));

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

    sortableList.sortableInstance = sortable;
}

function handleRemoveFromPlaylist(buttonEl) {
    const songId = buttonEl.dataset.songId;
    const playlistId = buttonEl.dataset.playlistId;
    const songItem = buttonEl.closest('li');
    const songTitle = songItem?.querySelector('.song-title')?.textContent || 'la canción';

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

        const formData = new FormData();
        formData.append('csrfmiddlewaretoken', getCsrfToken());

        fetch(`/remove-from-playlist/${playlistId}/${songId}/`, { method: 'POST', body: formData })
        .then(response => {
            if (!response.ok) throw new Error('Error al eliminar canción');

            if (songItem) {
                songItem.style.transition = 'all 0.3s ease';
                songItem.style.opacity = '0';
                songItem.style.transform = 'translateX(-20px)';
                setTimeout(() => {
                    songItem.remove();
                    const countElement = document.querySelector('h2');
                    if (countElement) {
                        const currentCount = document.querySelectorAll('.sortable-song-item').length;
                        countElement.textContent = `${currentCount} canciones`;
                    }
                    const Toast = Swal.mixin({ toast: true, position: 'top-end', showConfirmButton: false, timer: 3000, timerProgressBar: true });
                    Toast.fire({ icon: 'success', title: `"${songTitle}" eliminada de la playlist` });
                }, 300);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            Swal.fire({ icon: 'error', title: 'Error', text: 'No se pudo eliminar la canción de la playlist' });
        });
    });
}

function initializeCreatePlaylistButton() {
    const createPlaylistBtn = document.getElementById('create-playlist-btn');
    if (!createPlaylistBtn) return;

    createPlaylistBtn.replaceWith(createPlaylistBtn.cloneNode(true));
    const newBtn = document.getElementById('create-playlist-btn');
    
    newBtn.addEventListener('click', function() {
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
                const changeCoverButton = document.getElementById('change-playlist-cover-button');
                const coverInput = document.getElementById('playlist-cover');
                const coverPreview = document.getElementById('playlist-cover-preview');
                
                changeCoverButton.addEventListener('click', () => {
                    coverInput.click();
                });
                
                coverInput.addEventListener('change', (e) => {
                    const file = e.target.files[0];
                    if (file) {
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
                            coverPreview.src = e.target.result;
                            coverPreview.style.border = '2px solid #bb86fc';
                        };
                        reader.readAsDataURL(file);
                    }
                });
            },
            preConfirm: () => {
                const name = document.getElementById('playlist-name').value;
                const coverFile = document.getElementById('playlist-cover').files[0];
                
                if (!name || name.trim() === '') {
                    Swal.showValidationMessage('Debes ingresar un nombre para la playlist');
                    return false;
                }
                
                return { name: name.trim(), coverFile: coverFile };
            }
        }).then((result) => {
            if (result.isConfirmed) {
                const { name, coverFile } = result.value;
                
                if (coverFile) {
                    Swal.fire({
                        title: 'Creando playlist...',
                        text: 'Subiendo imagen, por favor espera.',
                        allowOutsideClick: false,
                        showConfirmButton: false,
                        didOpen: () => Swal.showLoading()
                    });
                }
                
                const formData = new FormData();
                formData.append('csrfmiddlewaretoken', getCsrfToken());
                formData.append('name', name);
                if (coverFile) {
                    formData.append('cover_image', coverFile);
                }
                
                fetch(window.createPlaylistUrl, {
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
                            title: `Playlist "${name}" creada exitosamente`
                        });
                        
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

function initializeEditPlaylistButton() {
    const editPlaylistBtn = document.getElementById('edit-playlist-btn');
    if (!editPlaylistBtn) return;

    editPlaylistBtn.replaceWith(editPlaylistBtn.cloneNode(true));
    const newBtn = document.getElementById('edit-playlist-btn');
    
    newBtn.addEventListener('click', function() {
        const playlistId = newBtn.dataset.playlistId;
        const currentName = newBtn.dataset.playlistName || '';
        const currentCover = newBtn.dataset.playlistCover || '/static/images/default_cover.png';

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
                const changeCoverButton = document.getElementById('change-playlist-cover-button');
                const coverInput = document.getElementById('playlist-cover');
                const coverPreview = document.getElementById('playlist-cover-preview');

                changeCoverButton.addEventListener('click', () => {
                    coverInput.click();
                });

                coverInput.addEventListener('change', (e) => {
                    const file = e.target.files[0];
                    if (file) {
                        if (!file.type.startsWith('image/')) {
                            Swal.fire('Error', 'Por favor selecciona un archivo de imagen válido.', 'error');
                            e.target.value = '';
                            return;
                        }
                        if (file.size > 5 * 1024 * 1024) {
                            Swal.fire('Error', 'La imagen es demasiado grande. Máximo 5MB.', 'error');
                            e.target.value = '';
                            return;
                        }
                        const reader = new FileReader();
                        reader.onload = (ev) => {
                            coverPreview.src = ev.target.result;
                            coverPreview.style.border = '2px solid #bb86fc';
                        };
                        reader.readAsDataURL(file);
                    }
                });
            },
            preConfirm: () => {
                const name = document.getElementById('playlist-name').value;
                const coverFile = document.getElementById('playlist-cover').files[0];

                if (!name || name.trim() === '') {
                    Swal.showValidationMessage('Debes ingresar un nombre para la playlist');
                    return false;
                }
                return { name: name.trim(), coverFile };
            }
        }).then((result) => {
            if (!result.isConfirmed) return;

            const { name, coverFile } = result.value;

            if (coverFile) {
                Swal.fire({
                    title: 'Guardando cambios...',
                    text: 'Subiendo imagen, por favor espera.',
                    allowOutsideClick: false,
                    showConfirmButton: false,
                    didOpen: () => Swal.showLoading()
                });
            }

            const formData = new FormData();
            formData.append('csrfmiddlewaretoken', getCsrfToken());
            formData.append('name', name);
            if (coverFile) formData.append('cover_image', coverFile);

            fetch(`/edit-playlist/${playlistId}/`, { method: 'POST', body: formData })
                .then(resp => {
                    if (!resp.ok) throw new Error('Error al editar la playlist');
                    const Toast = Swal.mixin({ toast: true, position: 'top-end', showConfirmButton: false, timer: 3000, timerProgressBar: true });
                    Toast.fire({ icon: 'success', title: `Playlist actualizada` });

                    // Refrescar la vista actual de detalle
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

function initializeDeletePlaylistButton() {
    const deletePlaylistBtn = document.getElementById('delete-playlist-btn');
    if (!deletePlaylistBtn) return;

    deletePlaylistBtn.replaceWith(deletePlaylistBtn.cloneNode(true));
    const newBtn = document.getElementById('delete-playlist-btn');
    
    newBtn.addEventListener('click', function() {
        const playlistId = newBtn.dataset.playlistId;
        const playlistName = newBtn.dataset.playlistName || 'esta playlist';

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

            const formData = new FormData();
            formData.append('csrfmiddlewaretoken', getCsrfToken());

            fetch(`/delete-playlist/${playlistId}/`, { method: 'POST', body: formData })
                .then(resp => {
                    if (!resp.ok) throw new Error('Error al eliminar la playlist');
                    const Toast = Swal.mixin({ toast: true, position: 'top-end', showConfirmButton: false, timer: 3000, timerProgressBar: true });
                    Toast.fire({ icon: 'success', title: `Playlist eliminada` });

                    // Volver al listado de playlists
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

function initializeRemoveFromPlaylist() {
    const buttons = document.querySelectorAll('.remove-from-playlist-btn');
    if (!buttons.length) return;

    // Desvincular listeners antiguos
    buttons.forEach(btn => btn.replaceWith(btn.cloneNode(true)));
    const freshButtons = document.querySelectorAll('.remove-from-playlist-btn');
    freshButtons.forEach(btn => {
        btn.addEventListener('click', () => handleRemoveFromPlaylist(btn));
    });
}

function cleanupPlaylistListeners() {
    const sortableLists = document.querySelectorAll('.song-list-sortable');
    sortableLists.forEach(list => {
        if (list.sortableInstance) {
            list.sortableInstance.destroy();
            list.sortableInstance = null;
        }
        delete list.dataset.sortableInit;
    });
}

document.body.addEventListener('htmx:beforeSwap', function() {
    cleanupPlaylistListeners();
});

document.body.addEventListener('htmx:afterRequest', function() {
    initializeCreatePlaylistButton();
    initializeEditPlaylistButton();
    initializeDeletePlaylistButton();
    initializePlaylistSorting();
    initializeRemoveFromPlaylist();
});

// Inicializar también en carga directa
document.addEventListener('DOMContentLoaded', function() {
    initializeCreatePlaylistButton();
    initializeEditPlaylistButton();
    initializeDeletePlaylistButton();
    initializePlaylistSorting();
    initializeRemoveFromPlaylist();
});