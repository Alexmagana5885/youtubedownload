import os
import platform
import yt_dlp
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import urllib.parse
import time
import cgi

class CustomHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            try:
                with open('templates/index.html', 'r', encoding='utf-8') as file:
                    html_content = file.read()
                self.wfile.write(html_content.encode())
            except Exception as e:
                self.wfile.write(f"Error loading HTML file: {e}".encode())
        
        elif self.path.startswith('/static/'):
            # Handle static files like CSS, JS, images, etc.
            file_path = self.path.lstrip('/')
            if os.path.exists(file_path):
                self.send_response(200)
                
                # Set the appropriate Content-Type header based on file type
                if file_path.endswith('.css'):
                    self.send_header('Content-type', 'text/css')
                elif file_path.endswith('.js'):
                    self.send_header('Content-type', 'application/javascript')
                elif file_path.endswith('.png'):
                    self.send_header('Content-type', 'image/png')
                elif file_path.endswith('.jpg') or file_path.endswith('.jpeg'):
                    self.send_header('Content-type', 'image/jpeg')
                elif file_path.endswith('.gif'):
                    self.send_header('Content-type', 'image/gif')
                else:
                    self.send_header('Content-type', 'application/octet-stream')
                
                self.end_headers()
                with open(file_path, 'rb') as file:
                    self.wfile.write(file.read())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"File not found")
        
        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"Page not found")

    def do_POST(self):
        if self.path == '/download':
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
                print(f"Received URL: {video_url}")
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()

                # Send the first response to indicate the download is starting
                self.wfile.write(b"Download started. Check the server console for details.")

                # Call the function to download the video with progress
                self.download_youtube_video_with_progress(video_url)
            else:
                self.send_response(400)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b"Invalid video URL")
        else:
            self.send_response(404)
            self.end_headers()

    def send_progress(self, progress):
        """Send the progress update via SSE"""
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.end_headers()

        # Format the progress as a JSON object
        progress_data = json.dumps({'progress': progress})
        self.wfile.write(f"data: {progress_data}\n\n".encode())

    def download_youtube_video_with_progress(self, video_url):
        """Downloads a YouTube video and sends progress updates to the frontend."""
        try:
            ydl_opts = {
                'outtmpl': f'{get_youtube_download_folder()}/%(title)s.%(ext)s',
                'format': 'best',
                'progress_hooks': [self.progress_hook],
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                print(f"Downloading video from: {video_url}")
                ydl.download([video_url])

            print("Download complete.")
        except Exception as e:
            print(f"An error occurred: {e}")

    def progress_hook(self, progress_info):
        """This is the progress hook for yt-dlp"""
        if 'download' in progress_info and 'total_bytes' in progress_info:
            downloaded = progress_info['downloaded_bytes']
            total = progress_info['total_bytes']
            percent = downloaded / total * 100
            print(f"Progress: {percent:.2f}%")

            # Send progress update to the frontend
            self.send_progress(percent)

def get_default_download_path():
    """Returns the system's default Downloads directory path for Windows, macOS, and Linux."""
    if platform.system() == "Windows":
        download_path = os.path.join(os.path.expanduser("~"), "Downloads")
    elif platform.system() in ["Darwin", "Linux"]:
        download_path = os.path.join(os.path.expanduser("~"), "Downloads")
    else:
        raise Exception("Unsupported Operating System")
    
    return download_path

def get_youtube_download_folder():
    """Create and return the path to the YouTubeDownloads folder inside the system's Downloads directory."""
    download_path = get_default_download_path()
    youtube_download_path = os.path.join(download_path, "YouTubeDownloads")
    
    if not os.path.exists(youtube_download_path):
        os.makedirs(youtube_download_path)
    
    return youtube_download_path

def run_server():
    port = 8000
    server_address = ('', port)
    httpd = HTTPServer(server_address, CustomHTTPRequestHandler)
    print(f"Server running on http://localhost:{port}")
    httpd.serve_forever()

if __name__ == "__main__":
    run_server()
