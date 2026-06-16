from flask import Flask, render_template, request, send_file
import yt_dlp
from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip
import os

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        url = request.form['url']
        start = int(request.form['start'])
        end = int(request.form['end'])
        
        # Download video
        ydl_opts = {'outtmpl': 'temp_video.mp4'}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
        # Potong video
        ffmpeg_extract_subclip("temp_video.mp4", start, end, targetname="clipped.mp4")
        
        return send_file("clipped.mp4", as_attachment=True)
        
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)    flow.redirect_uri = "https://" + request.host + "/auth/youtube/callback"
    authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')
    session['state'] = state
    return redirect(authorization_url)

@app.route('/auth/youtube/callback')
def youtube_callback():
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES, state=session['state'])
    flow.redirect_uri = "https://" + request.host + "/auth/youtube/callback"
    flow.fetch_token(authorization_response=request.url)
    
    credentials = flow.credentials
    session['credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }
    return "<script>window.close();</script>"

@app.route('/api/share-youtube', methods=['POST'])
def share_youtube():
    if 'credentials' not in session:
        return jsonify({"status": "need_auth", "auth_url": "/auth/youtube"})
        
    data = request.json
    judul = data.get('title', 'AI Auto Shorts Video')
    deskripsi = data.get('description', '#shorts #aiclipper')
    
    from google.oauth2.credentials import Credentials
    creds = Credentials(**session['credentials'])
    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=creds)
    
    body = {
        "snippet": {
            "title": judul,
            "description": deskripsi,
            "tags": ["shorts", "ai", "clipper"],
            "categoryId": "22"
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }
    
    try:
        media = MediaFileUpload("static/output_short.mp4", chunksize=-1, resumable=True, mimetype="video/mp4")
        request_upload = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        
        response = None
        while response is None:
            status, response = request_upload.next_chunk()
            
        return jsonify({"status": "success", "video_id": response["id"]})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/share-tiktok', methods=['POST'])
def share_tiktok():
    return jsonify({
        "status": "success", 
        "message": "Fitur Share TikTok berhasil disimulasikan! Integrasi penuh memerlukan akun bisnis TikTok Developer terverifikasi."
    })

if __name__ == '__main__':
    os.makedirs('static', exist_ok=True)
    app.run(port=5000, debug=True)
