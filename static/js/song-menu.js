function initializeSongMenuListeners() {
    if (window.songMenuListenersInitialized) return;
    window.songMenuListenersInitialized = true;

    document.body.addEventListener('click', function(event) {
        const likeButton = event.target.closest('.like-btn');
        if (likeButton) {
            event.stopPropagation();
            const songId = likeButton.dataset.songId;
            window.handleLikeClick(songId, likeButton);
            return;
        }

        const removeBtn = event.target.closest('.remove-from-playlist-btn');
        if (removeBtn) {
            event.stopPropagation();
            handleRemoveFromPlaylist(removeBtn);
            return;
        }

        const menuButton = event.target.closest('.song-menu-btn');
        if (menuButton) {
            event.preventDefault();
            event.stopPropagation();

            const parentLi = menuButton.closest('li');
            const dropdown = menuButton.nextElementSibling;
            const isAlreadyOpen = parentLi.classList.contains('menu-open');

            document.querySelectorAll('#song-list li.menu-open').forEach(openLi => {
                openLi.classList.remove('menu-open');
                const menuDropdown = openLi.querySelector('.song-menu-dropdown');
                const menuBtn = openLi.querySelector('.song-menu-btn');
                if (menuDropdown) menuDropdown.classList.remove('show');
                if (menuBtn) menuBtn.classList.remove('is-visible');
            });

            if (!isAlreadyOpen && dropdown) {
                parentLi.classList.add('menu-open');
                dropdown.classList.add('show');
                menuButton.classList.add('is-visible');

                setTimeout(() => {
                    const rect = dropdown.getBoundingClientRect();
                    const windowHeight = window.innerHeight;
                    const playerHeight = 120;

                    if (rect.bottom > windowHeight - playerHeight - 10) {
                        dropdown.classList.add('show-above');
                    } else {
                        dropdown.classList.remove('show-above');
                    }
                }, 10);
            }
            return;
        }

        const addToPlaylistButton = event.target.closest('.add-to-playlist-btn');
        if (addToPlaylistButton) {
            event.stopPropagation();
            const songId = addToPlaylistButton.dataset.songId;
            const songName = addToPlaylistButton.dataset.songName;
            openPlaylistModal(songId, songName);
        }

        const queueButton = event.target.closest('.queue-add-btn');
        if (queueButton) {
            event.stopPropagation();
            const songId = queueButton.dataset.songId;
            const songName = queueButton.dataset.songName;

            if (songId && songName) {
                window.songQueue.push({ id: songId, name: songName });

                const Toast = Swal.mixin({
                    toast: true, position: 'top-end', showConfirmButton: false, timer: 3500, timerProgressBar: true,
                    didOpen: (toast) => {
                        toast.onmouseenter = Swal.stopTimer;
                        toast.onmouseleave = Swal.resumeTimer;
                    }
                });
                Toast.fire({ icon: 'success', title: `'${songName}' añadida a la cola` });
            }
            return;
        }

        const songItem = event.target.closest('li[data-song-id]');
        if (songItem && !event.target.closest('.song-menu-container')) {
            const songId = songItem.dataset.songId;
            const songName = songItem.dataset.songName;
            if (songId && songName) {
                playSong(songId, songName);
            }
        }

        if (!event.target.closest('.song-menu-container')) {
            document.querySelectorAll('#song-list li.menu-open').forEach(openLi => {
                openLi.classList.remove('menu-open');
                const menuDropdown = openLi.querySelector('.song-menu-dropdown');
                const menuBtn = openLi.querySelector('.song-menu-btn');
                if (menuDropdown) menuDropdown.classList.remove('show');
                if (menuBtn) menuBtn.classList.remove('is-visible');
            });
        }
    });
}