/**
 * Initialize event listeners for song menu interactions
 * Prevents duplicate initialization using a global flag
 * Handles all song menu related events through event delegation
 */
function initializeSongMenuListeners() {
    if (window.songMenuListenersInitialized) return;
    window.songMenuListenersInitialized = true;

    /**
     * Main event listener using event delegation for efficient handling
     * Processes all song menu related clicks from a single listener
     */
    document.body.addEventListener('click', function(event) {
        // Handle like button clicks
        const likeButton = event.target.closest('.like-btn');
        if (likeButton) {
            event.stopPropagation();
            const songId = likeButton.dataset.songId;
            window.handleLikeClick(songId, likeButton);
            return;
        }

        // Handle remove from playlist button clicks
        const removeBtn = event.target.closest('.remove-from-playlist-btn');
        if (removeBtn) {
            event.stopPropagation();
            handleRemoveFromPlaylist(removeBtn);
            return;
        }

        // Handle song menu button clicks (three dots menu)
        const menuButton = event.target.closest('.song-menu-btn');
        if (menuButton) {
            event.preventDefault();
            event.stopPropagation();

            const parentLi = menuButton.closest('li');
            const dropdown = menuButton.nextElementSibling;
            const isAlreadyOpen = parentLi.classList.contains('menu-open');

            // Close all other open menus before opening new one
            document.querySelectorAll('#song-list li.menu-open').forEach(openLi => {
                openLi.classList.remove('menu-open');
                const menuDropdown = openLi.querySelector('.song-menu-dropdown');
                const menuBtn = openLi.querySelector('.song-menu-btn');
                if (menuDropdown) menuDropdown.classList.remove('show');
                if (menuBtn) menuBtn.classList.remove('is-visible');
            });

            // Open the clicked menu if it wasn't already open
            if (!isAlreadyOpen && dropdown) {
                parentLi.classList.add('menu-open');
                dropdown.classList.add('show');
                menuButton.classList.add('is-visible');

                // Adjust dropdown position based on screen space
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

        // Handle add to playlist button clicks
        const addToPlaylistButton = event.target.closest('.add-to-playlist-btn');
        if (addToPlaylistButton) {
            event.stopPropagation();
            const songId = addToPlaylistButton.dataset.songId;
            const songName = addToPlaylistButton.dataset.songName;
            openPlaylistModal(songId, songName);
        }

        // Handle add to queue button clicks
        const queueButton = event.target.closest('.queue-add-btn');
        if (queueButton) {
            event.stopPropagation();
            const songId = queueButton.dataset.songId;
            const songName = queueButton.dataset.songName;

            // Add song to the global queue and show confirmation toast
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

        // Handle song item clicks (play song when clicking outside menu)
        const songItem = event.target.closest('li[data-song-id]');
        if (songItem && !event.target.closest('.song-menu-container')) {
            const songId = songItem.dataset.songId;
            const songName = songItem.dataset.songName;
            if (songId && songName) {
                playSong(songId, songName);
            }
        }

        // Close all open menus when clicking outside menu containers
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