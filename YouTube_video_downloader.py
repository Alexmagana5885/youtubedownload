import os
import platform
import yt_dlp
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import urllib.parse
import time
import cgi
import threading
import queue  # For thread-safe progress sharing

class CustomHTTPRequestHandler(BaseHTTPRequestHandler):
    progress_queue = queue.Queue()  # Global queue to store progress updates

    def do_GET(self):
        if self.path == '/':
            self.handle_index()
        elif self.path.startswith('/static/'):
            self.serve_static_file()
        elif self.path == '/progress':
            self.handle_progress_stream()
        else:
            self.send_error(404, "File not found")

    def do_POST(self):
        if self.path == '/download':
            self.handle_download_request()

    def handle_index(self):
        """Serve the index.html page."""
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        try:
            with open('templates/index.html', 'r', encoding='utf-8') as file:
                html_content = file.read()
            self.wfile.write(html_content.encode())
        except Exception as e:
            self.wfile.write(f"Error loading HTML file: {e}".encode())

    def serve_static_file(self):
        """Serve static files like CSS, JS, and images."""
        file_path = self.path.lstrip('/')
        if os.path.exists(file_path):
            self.send_response(200)
            self.send_header('Content-type', self.get_file_type(file_path))
            self.end_headers()
            with open(file_path, 'rb') as file:
                self.wfile.write(file.read())
        else:
            self.send_error(404, "File not found")

    def handle_progress_stream(self):
        """Handle Server-Sent Events (SSE) for progress updates."""
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.end_headers()

        while True:
            try:
                # Wait for progress update from the queue
                progress_data = CustomHTTPRequestHandler.progress_queue.get(timeout=30)
                if progress_data:
                    self.wfile.write(f"data: {json.dumps(progress_data)}\n\n".encode())
            except queue.Empty:
                # If no new progress update is received, send a ping to keep the connection alive
                self.wfile.write(b"data: {}\n\n")

            time.sleep(1)  # Reduce CPU usage

    def handle_download_request(self):
        """Handle video download request."""
        content_type, pdict = cgi.parse_header(self.headers.get('content-type'))

        if content_type == 'multipart/form-data':
            form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={'REQUEST_METHOD': 'POST'})
            video_url = form.getvalue('downloadlink')
        else:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            data = urllib.parse.parse_qs(post_data)
            video_url = data.get('downloadlink', [None])[0]

        if video_url:
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"Download started. Check progress above.")

            # Call the function to download the video with progress tracking
            threading.Thread(target=self.download_youtube_video_with_progress, args=(video_url,)).start()
        else:
            self.send_error(400, "Invalid video URL")

    def download_youtube_video_with_progress(self, video_url):
        """Downloads a YouTube video and sends progress updates to the frontend."""
        try:
            ydl_opts = {
                'outtmpl': f'{get_youtube_download_folder()}/%(title)s.%(ext)s',
                'format': 'best',
                'progress_hooks': [self.progress_hook],
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])

            CustomHTTPRequestHandler.progress_queue.put({'status': 'completed', 'message': 'Download complete!'})
        except Exception as e:
            CustomHTTPRequestHandler.progress_queue.put({'status': 'error', 'message': f"An error occurred: {e}"})

    def progress_hook(self, progress_info):
        """Progress hook for yt-dlp to send updates to the client."""
        if progress_info.get('status') == 'downloading':
            total_bytes = progress_info.get('total_bytes', 1)
            downloaded_bytes = progress_info.get('downloaded_bytes', 0)
            percent = downloaded_bytes / total_bytes * 100
            progress_data = {'status': 'downloading', 'progress': round(percent, 2)}
            CustomHTTPRequestHandler.progress_queue.put(progress_data)

        elif progress_info.get('status') == 'finished':
            CustomHTTPRequestHandler.progress_queue.put({'status': 'completed', 'message': 'Download complete!'})

    def get_file_type(self, file_path):
        """Return the correct content type for the file."""
        if file_path.endswith('.css'):
            return 'text/css'
        elif file_path.endswith('.js'):
            return 'application/javascript'
        elif file_path.endswith(('.png', '.jpg', '.jpeg', '.gif')):
            return 'image/' + file_path.split('.')[-1]
        else:
            return 'application/octet-stream'

def get_default_download_path():
    """Get the default download folder for the user's system."""
    if platform.system() == "Windows":
        return os.path.join(os.path.expanduser("~"), "Downloads")
    elif platform.system() in ["Darwin", "Linux"]:
        return os.path.join(os.path.expanduser("~"), "Downloads")
    else:
        raise Exception("Unsupported Operating System")

def get_youtube_download_folder():
    """Get the folder where YouTube videos will be downloaded."""
    download_path = get_default_download_path()
    youtube_download_path = os.path.join(download_path, "YouTubeDownloads")
    if not os.path.exists(youtube_download_path):
        os.makedirs(youtube_download_path)
    return youtube_download_path

def run_server():
    """Start the HTTP server to handle requests."""
    port = 8000
    server_address = ('', port)
    httpd = HTTPServer(server_address, CustomHTTPRequestHandler)
    print(f"Server running on http://localhost:{port}")
    httpd.serve_forever()

if __name__ == "__main__":
    run_server()
