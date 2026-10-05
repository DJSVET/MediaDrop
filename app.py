import glob
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import traceback
import uuid
import threading
import time
from urllib.parse import urlparse

from flask import Flask, jsonify, request, send_file, send_from_directory
from flask_cors import CORS
import requests
import yt_dlp

logging.basicConfig(
    format="[%(asctime)s] %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Папка для временных файлов
TEMP_FOLDER = tempfile.gettempdir()
# Хранилище состояния загрузок
DOWNLOADS = {}
DOWNLOADS_LOCK = threading.Lock()
print(f"Временные файлы будут сохраняться в: {TEMP_FOLDER}")


# --- ФУНКЦИЯ ДЛЯ ПОИСКА ТРЕКА НА YOUTUBE ---
def search_youtube_for_track(track_name, artist_name):
    """Ищет трек на YouTube по названию и исполнителю"""
    search_query = f"{artist_name} - {track_name} official audio"
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'default_search': 'ytsearch1',
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_results = ydl.extract_info(f"ytsearch1:{search_query}", download=False)
            if search_results and 'entries' in search_results and len(search_results['entries']) > 0:
                return search_results['entries'][0].get('url')
    except Exception as e:
        logger.error(f"Ошибка поиска на YouTube: {e}")
    return None


# --- ФУНКЦИЯ ДЛЯ ПОЛУЧЕНИЯ ИНФОРМАЦИИ О ТРЕКЕ SPOTIFY ---
def get_spotify_track_info(url):
    """Получает информацию о треке Spotify и данные источника YouTube."""
    try:
        parsed = urlparse(url)
        path_parts = parsed.path.split('/')

        track_id = None
        for i, part in enumerate(path_parts):
            if part == 'track' and i + 1 < len(path_parts):
                track_id = path_parts[i + 1].split('?')[0]
                break

        if not track_id:
            return {'error': 'Не удалось определить ID трека Spotify'}

        embed_url = f"https://open.spotify.com/embed/track/{track_id}"
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/128.0 Safari/537.36'
            )
        }

        response = requests.get(embed_url, headers=headers, timeout=15)
        response.raise_for_status()
        html = response.text

        # Spotify embed содержит OpenGraph-метаданные, которые стабильнее
        # внутренних JSON-полей страницы.
        def get_meta(property_name):
            match = re.search(
                rf'<meta[^>]+property=["\']{re.escape(property_name)}["\'][^>]+content=["\']([^"\']+)["\']',
                html,
                re.IGNORECASE
            )
            if not match:
                match = re.search(
                    rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']{re.escape(property_name)}["\']',
                    html,
                    re.IGNORECASE
                )
            return match.group(1) if match else ''

        title = get_meta('og:title')
        artist = get_meta('og:description')
        thumbnail = get_meta('og:image')

        # Дополнительный разбор JSON Spotify, если OG-поля не сработали.
        if not title:
            match = re.search(r'"name":"((?:\\.|[^"\\])*)"', html)
            if match:
                title = json.loads(f'"{match.group(1)}"')

        if not artist:
            match = re.search(r'"artists":\[\{"name":"((?:\\.|[^"\\])*)"', html)
            if match:
                artist = json.loads(f'"{match.group(1)}"')

        if not thumbnail:
            # В разных версиях embed встречается albumOfTrack -> coverArt.
            match = re.search(r'"url":"(https://i\.scdn\.co/[^"]+)"', html)
            if match:
                thumbnail = match.group(1).replace('\\u0026', '&')

        # og:description иногда содержит служебный текст.
        if artist and 'Spotify' in artist:
            artist = artist.replace('Spotify', '').strip(' -')

        # Длительность.
        duration_match = re.search(r'"duration_ms":(\d+)', html)
        duration_ms = int(duration_match.group(1)) if duration_match else 0
        duration_sec = duration_ms // 1000 if duration_ms > 0 else 0

        # Ищем соответствующий источник на YouTube.
        youtube_url = search_youtube_for_track(title, artist) if title and artist else None

        if not youtube_url and title:
            youtube_url = search_youtube_for_track(title, f"{artist} topic" if artist else "official audio")

        # Если YouTube найден, подтягиваем реальные технические характеристики.
        youtube_info = {}
        if youtube_url:
            try:
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'extract_flat': False,
                    'skip_download': True,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    youtube_info = ydl.extract_info(youtube_url, download=False) or {}
            except Exception as e:
                logger.warning(f"Не удалось получить технические данные YouTube: {e}")

        # Spotify-обложка имеет приоритет. Если Spotify её не отдал,
        # используем превью найденного YouTube-видео.
        if not thumbnail:
            thumbnail = youtube_info.get('thumbnail', '')

        actual_duration = duration_sec or youtube_info.get('duration', 0) or 0
        # На выходе backend всегда конвертирует Spotify-источник в MP3 320 kbps.
        # Поэтому размер можно показать как расчётный размер готового MP3.
        bitrate = "320 kbps"
        filesize = round(actual_duration * 320000 / 8) if actual_duration else 0

        return {
            'title': title or youtube_info.get('title', 'Неизвестный трек'),
            'artist': artist or youtube_info.get('uploader', 'Неизвестный исполнитель'),
            'uploader': artist or youtube_info.get('uploader', 'Исполнитель'),
            'thumbnail': thumbnail,
            'youtube_thumbnail': youtube_info.get('thumbnail', ''),
            'duration': actual_duration,
            'filesize': filesize,
            'bitrate': bitrate,
            'resolution': 'MP3 320 kbps',
            'formats': [],
            'youtube_url': youtube_url,
            'platform': 'spotify',
            'is_track': True,
            'audio_only': True
        }

    except Exception as e:
        logger.exception("Ошибка при получении информации о Spotify треке")
        return {'error': str(e)}


def get_video_info(url):
    """Получает информацию о видео (название, превью, длительность)"""
    # Проверяем, является ли ссылка ссылкой на Spotify
    if 'spotify.com' in url.lower():
        return get_spotify_track_info(url)
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'ignoreerrors': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Получаем список форматов
            formats = []
            if 'formats' in info:
                for f in info.get('formats', []):
                    if f.get('vcodec') != 'none' and f.get('height'):
                        format_note = f.get('format_note', 'Unknown')
                        # Фильтруем дубликаты по качеству
                        if format_note and format_note not in [x.get('quality') for x in formats]:
                            formats.append({
                                'format_id': f['format_id'],
                                'ext': f.get('ext', 'mp4'),
                                'quality': format_note,
                                'height': f.get('height', 0),
                                'width': f.get('width', 0)
                            })
            
            return {
                'title': info.get('title', 'Без названия'),
                'uploader': info.get('uploader', 'Автор'),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration', 0),
                'formats': formats,
                'resolution': f"{info.get('height', 1080)}p",
                'filesize': info.get('filesize', 0),
                'bitrate': f"{info.get('bitrate', 4500000) // 1000} kbps",
                'platform': 'youtube'
            }
    except Exception as e:
        traceback.print_exc()
        return {'error': str(e)}


@app.route('/', methods=['GET'])
def index():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), 'index.html')


@app.route('/info', methods=['POST'])
def info():
    data = request.json
    url = data.get('url')
    if not url:
        return jsonify({'error': 'Нет ссылки'}), 400
    
    result = get_video_info(url)
    if 'error' in result:
        return jsonify({'error': result['error']}), 400
    return jsonify(result)


def update_download_progress(job_id, **data):
    with DOWNLOADS_LOCK:
        if job_id in DOWNLOADS:
            DOWNLOADS[job_id].update(data)


def download_worker(job_id, url, file_type, format_id):
    ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
    unique_filename = f"{uuid.uuid4().hex}"

    try:
        # ---------------------------------------------------------
        # REAL PROGRESS HOOK YT-DLP
        # ---------------------------------------------------------
        def progress_hook(d):
            status = d.get("status")

            if status == "downloading":
                downloaded = d.get("downloaded_bytes", 0) or 0
                total = (
                    d.get("total_bytes")
                    or d.get("total_bytes_estimate")
                    or 0
                )

                if total > 0:
                    percent = (downloaded / total) * 100
                    percent = max(0, min(percent, 99))

                    speed = d.get("speed") or 0
                    eta = d.get("eta")

                    update_download_progress(
                        job_id,
                        status="downloading",
                        percent=percent,
                        downloaded_bytes=downloaded,
                        total_bytes=total,
                        speed=speed,
                        eta=eta
                    )

            elif status == "finished":
                # yt-dlp завершил загрузку исходного файла.
                # Дальше может идти FFmpeg.
                update_download_progress(
                    job_id,
                    status="processing",
                    percent=98
                )

        # ---------------------------------------------------------
        # OPTIONS YT-DLP
        # ---------------------------------------------------------
        if file_type == "audio":
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(
                    TEMP_FOLDER,
                    unique_filename + '.%(ext)s'
                ),

                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320'
                }],

                'prefer_ffmpeg': True,
                'ffmpeg_location': ffmpeg_bin,
                'socket_timeout': 120,
                'noplaylist': True,

                'quiet': False,
                'no_warnings': False,
                'nocheckcertificate': True,

                # ВОТ ЭТО главное
                'progress_hooks': [progress_hook]
            }

        else:
            if format_id in ['best', 'bestvideo', None, '']:
                format_spec = (
                    'bv*[vcodec^=avc1]+ba[ext=m4a]/'
                    'bv*+ba/best'
                )
            else:
                format_spec = (
                    f'{format_id}+bestaudio/'
                    f'{format_id}+ba/best'
                )

            ydl_opts = {
                'format': format_spec,
                'outtmpl': os.path.join(
                    TEMP_FOLDER,
                    unique_filename + '.%(ext)s'
                ),
                'merge_output_format': 'mp4',

                'prefer_ffmpeg': True,
                'ffmpeg_location': ffmpeg_bin,
                'socket_timeout': 120,
                'noplaylist': True,

                'quiet': False,
                'no_warnings': False,
                'nocheckcertificate': True,

                # ВОТ ЭТО главное
                'progress_hooks': [progress_hook]
            }

        # ---------------------------------------------------------
        # DOWNLOAD
        # ---------------------------------------------------------
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

        video_title = info.get("title", "video")

        clean_title = re.sub(
            r'[<>:"/\\|?*\x00-\x1F]',
            '',
            str(video_title)
        )

        clean_title = re.sub(
            r'\s+',
            ' ',
            clean_title
        ).strip().rstrip('. ')

        if not clean_title:
            clean_title = "video"

        # ---------------------------------------------------------
        # VIDEO PROCESSING
        # ---------------------------------------------------------
        downloaded_file = None

        if file_type != "audio":

            source_candidates = glob.glob(
                os.path.join(
                    TEMP_FOLDER,
                    unique_filename + ".*"
                )
            )

            source_candidates = [
                f for f in source_candidates
                if os.path.splitext(f)[1].lower()
                in [".mp4", ".mkv", ".webm", ".mov"]
            ]

            if not source_candidates:
                raise Exception(
                    "Не найден исходный видеофайл для FFmpeg."
                )

            source_file = source_candidates[0]

            final_file = os.path.join(
                TEMP_FOLDER,
                unique_filename + "_final.mp4"
            )

            update_download_progress(
                job_id,
                status="processing",
                percent=98
            )

            ffmpeg_cmd = [
                ffmpeg_bin,
                "-y",
                "-i", source_file,
                "-map", "0:v:0",
                "-map", "0:a:0?",
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                "-ar", "48000",
                "-movflags", "+faststart",
                final_file
            ]

            result = subprocess.run(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if result.returncode != 0:
                logger.error(
                    "FFmpeg error:\n%s",
                    result.stderr
                )
                raise Exception(
                    "FFmpeg не смог собрать видео со звуком."
                )

            if not os.path.exists(final_file):
                raise Exception(
                    "FFmpeg не создал итоговый MP4."
                )

            try:
                if os.path.exists(source_file):
                    os.remove(source_file)
            except Exception:
                pass

            downloaded_file = final_file

        # ---------------------------------------------------------
        # AUDIO
        # ---------------------------------------------------------
        else:

            files = glob.glob(
                os.path.join(
                    TEMP_FOLDER,
                    unique_filename + ".*"
                )
            )

            for f in files:
                if os.path.splitext(f)[1].lower() == ".mp3":
                    downloaded_file = f
                    break

        if not downloaded_file or not os.path.exists(downloaded_file):
            raise Exception(
                "Не удалось найти скачанный файл."
            )

        user_filename = (
            clean_title +
            os.path.splitext(downloaded_file)[1]
        )

        # ---------------------------------------------------------
        # READY
        # ---------------------------------------------------------
        update_download_progress(
            job_id,
            status="ready",
            percent=100,
            file=downloaded_file,
            filename=user_filename,
            mimetype=(
                'audio/mpeg'
                if file_type == 'audio'
                else 'video/mp4'
            )
        )

        logger.info(
            "Загрузка завершена: %s",
            downloaded_file
        )

    except Exception as e:

        logger.exception(
            "Ошибка при скачивании"
        )

        update_download_progress(
            job_id,
            status="error",
            error=str(e),
            percent=0
        )

@app.route('/download', methods=['POST'])
def download():
    data = request.json or {}

    url = data.get('url')
    file_type = data.get('type', 'video')
    format_id = data.get('format_id', 'best')

    if not url:
        return jsonify({
            'error': 'Нет ссылки'
        }), 400

    # Spotify -> YouTube
    if 'spotify.com' in url.lower():

        track_info = get_spotify_track_info(url)

        if 'error' in track_info:
            return jsonify({
                'error': track_info['error']
            }), 400

        youtube_url = track_info.get('youtube_url')

        if not youtube_url:
            return jsonify({
                'error': (
                    'Трек не найден на YouTube. '
                    'Попробуйте другой сервис.'
                )
            }), 404

        url = youtube_url
        file_type = 'audio'

    # Уникальный ID задания
    job_id = uuid.uuid4().hex

    with DOWNLOADS_LOCK:
        DOWNLOADS[job_id] = {
            'status': 'starting',
            'percent': 0,
            'downloaded_bytes': 0,
            'total_bytes': 0,
            'speed': 0,
            'eta': None
        }

    # Запускаем скачивание отдельно
    thread = threading.Thread(
        target=download_worker,
        args=(
            job_id,
            url,
            file_type,
            format_id
        ),
        daemon=True
    )

    thread.start()

    return jsonify({
        'success': True,
        'job_id': job_id
    })

@app.route('/progress/<job_id>', methods=['GET'])
def progress(job_id):

    with DOWNLOADS_LOCK:
        job = DOWNLOADS.get(job_id)

        if not job:
            return jsonify({
                'error': 'Загрузка не найдена'
            }), 404

        return jsonify(job)

@app.route('/download/<job_id>/file', methods=['GET'])
def download_file(job_id):

    with DOWNLOADS_LOCK:
        job = DOWNLOADS.get(job_id)

        if not job:
            return jsonify({
                'error': 'Загрузка не найдена'
            }), 404

        if job.get('status') == 'error':
            return jsonify({
                'error': job.get(
                    'error',
                    'Ошибка скачивания'
                )
            }), 500

        if job.get('status') != 'ready':
            return jsonify({
                'error': 'Файл ещё не готов'
            }), 409

        downloaded_file = job.get('file')
        filename = job.get(
            'filename',
            'download'
        )
        mimetype = job.get(
            'mimetype',
            'application/octet-stream'
        )

    if not downloaded_file or not os.path.exists(downloaded_file):
        return jsonify({
            'error': 'Файл не найден'
        }), 404

    response = send_file(
        downloaded_file,
        as_attachment=True,
        download_name=filename,
        mimetype=mimetype
    )

    @response.call_on_close
    def cleanup():

        try:
            if os.path.exists(downloaded_file):
                os.remove(downloaded_file)

            with DOWNLOADS_LOCK:
                DOWNLOADS.pop(job_id, None)

            logger.info(
                "Удалён временный файл: %s",
                downloaded_file
            )

        except Exception as e:
            logger.error(
                "Ошибка удаления файла: %s",
                e
            )

    return response


if __name__ == '__main__':
    print("🚀 Сервер запущен на http://localhost:5000")
    app.run(debug=True, port=5000)