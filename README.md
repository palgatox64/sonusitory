# sonusitory

Sonusitory is a personal music streaming server that connects to your Google Drive account, allowing you to browse and play your music collection from anywhere. It's built with Django and designed to provide a seamless and personalized music listening experience.
> [!NOTE]
> At the moment, this app is designed for localhost.

<div align="center">
  <img src="https://imgur.com/uUvxzAi.png">
</div>

## Features

* **Google Drive Integration**: Securely connect your Google Drive account to scan and stream your music files.
* **Music Library Organization**: Automatically organizes your music by artists and albums based on your folder structure.
* **Sleek and Responsive Player**: A clean and modern web player that works on both desktop and mobile devices.
* **Playlist Management**: Create, edit, and manage your own custom playlists.
* **"Liked" Songs**: Mark your favorite tracks and access them easily in a dedicated "Liked Songs" list.
* **User Accounts**: Full user registration and authentication system.
* **Dynamic UI with HTMX**: A fast and modern user experience with minimal page reloads.
* **Background Scanning with Celery**: Efficiently scans your music library in the background without interrupting your listening.
* 
<div align="center">
  <img src="https://imgur.com/Zsx6N2q.png">
</div>

## Tech Stack

* **Backend**: Django, Celery, Redis
* **Frontend**: HTML5, CSS3, JavaScript, HTMX, SweetAlert2, Font Awesome
* **Database**: SQLite3 (default, but can be configured for other Django-supported databases)
* **APIs**: Google Drive API for file access, Imgur API for image hosting (avatars and playlist covers)

## Getting Started

To get a local copy up and running, follow these simple steps.

### Prerequisites

* Python 3.x
* Django
* Redis
* Google API Credentials
* Imgur API Client ID

### Installation

1.  **Clone the repo**
    ```sh
    git clone https://github.com/palgatox64/sonusitory
    ```
2.  **Install Python packages**
    ```sh
    pip install -r requirements.txt
    ```
3.  **Set up your environment variables**
    Create a `.env` file in the root directory and add the following:
    ```
    SECRET_KEY='your_django_secret_key'
    IMGUR_CLIENT_ID='your_imgur_client_id'
    ```
4.  **Set up your Google API credentials**
    - Go to the [Google Cloud Console](https://console.cloud.google.com/).
    - Create a new project.
    - Enable the Google Drive API.
    - Create credentials for an "OAuth client ID" (select "Web application").
    - Download the `client_secret.json` file and place it in a `credentials` directory in the root of the project.
5.  **Apply migrations**
    ```sh
    python manage.py migrate
    ```
6.  **Run the development server and Celery worker**
    ```sh
    python manage.py rundev
    ```
> [!WARNING]
>This application is intended for personal use and does not endorse piracy in any form. The purpose of Sonusitory is to provide a means to access and stream your own legally acquired music collection.
>
>We encourage you to use this software for:
>* Streaming digitized copies of music you have legally purchased (e.g., from CDs, vinyl, or cassettes).
>* Listening to copyright-free music or tracks under Creative Commons licenses.
>* Hosting your own personal audio projects, such as band demos or personal recordings.
>
>The responsibility for ensuring that you have the legal right to stream the content in your library rests entirely with you, the user.

## License

Distributed under the MIT License. See `LICENSE` for more information.

<div align="center">
  <img src="https://imgur.com/EMFiEIF.png">
</div>
