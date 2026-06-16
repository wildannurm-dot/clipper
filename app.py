import os
from flask import Flask, request, jsonify, render_template, session, redirect
import yt_dlp
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
import whisper

# Pustaka Resmi Google API untuk Upload ke YouTube
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from googleapiclient.http import MediaFileUpload

app = Flask(__name__)
app.secret_key = "KUNCI_RAHASIA_BEBAS_SAYA" # Bisa diganti dengan teks acak apa saja

# Inisialisasi AI Whisper (Model 'base' seimbang antara akurasi dan kecepatan)
model = whisper.load_model("base")

# Konfigurasi OAuth 2.0 YouTube API
CLIENT_SECRETS_FILE = "client_secret.json"
SCOPES = ["https://googleapis.com"]
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1" # Izinkan HTTP untuk pengembangan awal

def download_and_process_video(url, start_time, end_time):
    video_raw = "downloaded_video.mp4"
    video_out = "static/output_short.mp4"
    
    # 1. Unduh Video YouTube kualitas terbaik dalam bentuk MP4
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
        'outtmpl': video_raw,
        'overwrites': True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    
    # 2. Potong Durasi Video & Ubah ke Rasio Vertikal 9:16
    clip = VideoFileClip(video_raw).subclip(start_time, end_time)
    w, h = clip.size
    target_w = int(h * 9 / 16)
    x1 = (w - target_w) // 2
    clip_vertical = clip.crop(x1=x1, y1=0, width=target_w, height=h)
    
    # Simpan video mentah vertikal untuk dianalisis oleh AI Whisper
    clip_vertical.write_videofile(video_out, fps=30, codec="libx264", audio_codec="aac")
    clip.close()
    
    # 3. Jalankan Transkripsi AI Whisper untuk Mendapatkan Teks
    result = model.transcribe(video_out, language="id")
    segments = result.get("segments", [])
    
    # 4. Tempelkan Teks Otomatis ke Atas Video (Hardsub Gaya TikTok)
    clips_with_text = [clip_vertical]
    for seg in segments:
        text = seg['text'].strip()
        t_start = seg['start']
        t_end = seg['end']
        
        # Membuat elemen teks bergaya media sosial (Font Arial, Kuning, dengan latar belakang hitam tipis)
        txt_clip = TextClip(text, fontsize=28, color='yellow', font='Arial', stroke_color='black', stroke_width=1)
        txt_clip = txt_clip.set_pos(('center', 'center')).set_start(t_start).set_end(t_end)
        clips_with_text.append(txt_clip)
    
    # Render akhir penggabungan video dan teks teks otomatis
    final_video = CompositeVideoClip(clips_with_text)
    final_video.write_videofile(video_out, fps=30, codec="libx264", audio_codec="aac")
    final_video.close()
    
    # Hapus file mentah untuk menghemat ruang penyimpanan server
    if os.path.exists(video_raw):
        os.remove(video_raw)
        
    return segments

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/create-shorts', methods=['POST'])
def create_shorts():
    data = request.json
    url = data.get('url')
    start = int(data.get('start', 0))
    end = int(data.get('end', 15))
    
    try:
        segments = download_and_process_video(url, start, end)
        return jsonify({
            "status": "success",
            "video_url": "/static/output_short.mp4",
            "transcription": segments
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ================= INTEGRASI API UNTUK UNGGAH OTOMATIS =================

@app.route('/auth/youtube')
def auth_youtube():
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES)
    flow.redirect_uri = "https://" + request.host + "/auth/youtube/callback"
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
