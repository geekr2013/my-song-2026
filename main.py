import os
import json
import datetime
import smtplib
import random
import time
import gspread
from google.oauth2.service_account import Credentials
from google.oauth2.credentials import Credentials as UserCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from yt_dlp import YoutubeDL
# afx는 오디오 효과(페이드아웃 등)를 위해 필요합니다
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, vfx, afx, concatenate_videoclips
from moviepy.config import change_settings
# 리눅스 환경(GitHub Actions)을 위한 ImageMagick 경로 설정
change_settings({"IMAGEMAGICK_BINARY": "/usr/bin/convert"})

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- 환경 변수 로드 ---
try:
    GCP_SA_KEY = json.loads(os.environ['GCP_SA_KEY'])
    SHEET_URL = os.environ['SHEET_URL']
    YT_CLIENT_ID = os.environ['YOUTUBE_CLIENT_ID']
    YT_CLIENT_SECRET = os.environ['YOUTUBE_CLIENT_SECRET']
    YT_REFRESH_TOKEN = os.environ['YOUTUBE_REFRESH_TOKEN']
    EMAIL_USER = os.environ['EMAIL_USER']
    EMAIL_PASS = os.environ['EMAIL_PASS']
except KeyError as e:
    print(f"❌ [설정 오류] {e}가 없습니다. GitHub Secrets를 확인하세요.")
    exit(1)

# --- ⚙️ 사용자 설정 (여기만 바꾸면 됩니다) ---
TARGET_DURATION_MIN = 15   # 목표 영상 길이 (분). 예: 60으로 하면 1시간짜리 영상 생성
LOFI_SPEED = 0.85          # 속도 조절 (0.8 ~ 0.9 추천)
RESOLUTION_HEIGHT = 720    # 해상도 (720p 권장, 1080p는 렌더링 오래 걸림)
PRIVACY_STATUS = 'public'  # 공개 설정 ('private', 'unlisted', 'public')

def send_email(subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = EMAIL_USER
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, EMAIL_USER, msg.as_string())
        server.quit()
        print("📧 이메일 발송 성공")
    except Exception as e:
        print(f"⚠️ 이메일 발송 실패: {e}")

def cleanup_files(files):
    print("🧹 임시 파일 청소 중...")
    for file in files:
        try:
            if os.path.exists(file):
                os.remove(file)
        except:
            pass

def get_random_link():
    print("📋 스프레드시트 조회 중...")
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(GCP_SA_KEY, scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_url(SHEET_URL).sheet1
        
        all_values = sheet.get_all_values()
        if len(all_values) < 2: return None, "데이터 없음"
        
        # 유튜브 링크가 포함된 셀만 추출
        valid_links = [cell for row in all_values[1:] for cell in row if "youtube.com" in cell or "youtu.be" in cell]
        
        if not valid_links: return None, "링크 없음"
            
        selected_link = random.choice(valid_links)
        print(f"🎲 랜덤 선택된 링크: {selected_link}")
        return selected_link, "성공"
        
    except Exception as e:
        return None, str(e)

def download_video(url):
    print(f"⬇️ 다운로드 시작: {url}")
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': 'downloaded_video.%(ext)s',
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'cookiefile': 'cookies.txt', 
        'retries': 10,
        'http_headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'},
    }
    
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return "downloaded_video.mp4", info.get('title', 'Unknown Title')

def process_lofi_video(input_path, original_title):
    print(f"🎨 영상 변환 중 (목표: {TARGET_DURATION_MIN}분)...")
    
    clip = VideoFileClip(input_path)
    if not clip.audio: return input_path 

    # 1. 속도 및 색감 조절 (Lofi Vibe)
    slow_clip = clip.fx(vfx.speedx, LOFI_SPEED)
    styled_clip = slow_clip.fx(vfx.colorx, 0.7).fx(vfx.lum_contrast, lum=0, contrast=0.1)
    
    if styled_clip.h > RESOLUTION_HEIGHT:
        styled_clip = styled_clip.resize(height=RESOLUTION_HEIGHT)

    # 2. 루프(반복) 처리
    current_duration = styled_clip.duration
    target_duration = TARGET_DURATION_MIN * 60
    
    if current_duration < target_duration:
        repeat_count = int(target_duration // current_duration) + 1
        print(f" - 원본이 짧아 {repeat_count}회 반복 연결합니다.")
        final_clip = concatenate_videoclips([styled_clip] * repeat_count)
        final_clip = final_clip.subclip(0, target_duration)
    else:
        final_clip = styled_clip.subclip(0, target_duration)

    # 3. 오디오 페이드 아웃 (끝날 때 자연스럽게 소리 줄임 - 5초)
    final_clip = final_clip.audio_fadeout(5)

    # 4. 자막 오버레이
    print(" - 자막 작업 중...")
    try:
        display_title = original_title[:30] + "..." if len(original_title) > 30 else original_title
        text_content = f"{display_title}\nSlowed & Reverb Mix"
        
        txt_clip = TextClip(text_content, fontsize=24, color='white', font='DejaVu-Sans-Bold', align='center')
        txt_clip = txt_clip.set_pos(('center', 0.8), relative=True).set_duration(final_clip.duration)
        txt_clip = txt_clip.set_opacity(0.6)
        
        final_video = CompositeVideoClip([final_clip, txt_clip])
    except Exception as e:
        print(f"⚠️ 자막 생성 실패(폰트 등): {e}")
        final_video = final_clip

    output_filename = "output_final.mp4"
    final_video.write_videofile(
        output_filename, 
        codec='libx264', 
        audio_codec='aac', 
        preset='ultrafast', 
        threads=2, 
        fps=24 
    )
    return output_filename

def upload_to_youtube(file_path, title):
    print("⬆️ 유튜브 업로드 시작...")
    creds = UserCredentials(
        None,
        refresh_token=YT_REFRESH_TOKEN,
        client_id=YT_CLIENT_ID,
        client_secret=YT_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token"
    )
    
    youtube = build('youtube', 'v3', credentials=creds)
    today_str = datetime.datetime.now().strftime("%Y.%m.%d")
    
    # 제목 최적화
    clean_title = title.replace("Official Video", "").replace("MV", "").replace("Lyrics", "").strip()
    video_title = f"🎧 {clean_title} (Slowed & Reverb) | {TARGET_DURATION_MIN}분 반복"
    if len(video_title) > 100: video_title = video_title[:95] + "..."

    # 설명 최적화 (SEO)
    description = f"""
🎧 {clean_title} - Slowed & Reverb Loop ({TARGET_DURATION_MIN} Mins)

지친 하루 끝에 잠시 쉬어가세요.
공부할 때, 책 읽을 때, 혹은 멍하니 창밖을 바라볼 때 듣기 좋은 음악입니다.
{TARGET_DURATION_MIN}분 동안 반복되는 몽환적인 멜로디가 당신의 공간을 채워줍니다.

☁️ Vibe: Relaxing, Chill, Vintage
📅 Uploaded: {today_str}

[Credit]
Original Track: {title}
Remixed for relaxation purposes.

#Lofi #로파이 #공부할때듣는노래 #수면음악 #휴식 #Chill #SlowedAndReverb #Playlist #감성
    """
    
    request_body = {
        'snippet': {
            'title': video_title,
            'description': description,
            'tags': ['lofi', 'slowed', 'reverb', 'playlist', '공부음악', '수면음악', 'bgm'],
            'categoryId': '10' 
        },
        'status': {
            'privacyStatus': PRIVACY_STATUS, # public으로 설정됨
            'selfDeclaredMadeForKids': False,
        }
    }
    
    media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=request_body, media_body=media)
    response = request.execute()
    print(f"✅ 업로드 완료! Video ID: {response.get('id')}")
    return response.get('id')

if __name__ == "__main__":
    downloaded_file = "downloaded_video.mp4"
    output_file = "output_final.mp4"
    
    try:
        # 1. 링크 가져오기
        url, msg = get_random_link()
        if url:
            # 2. 다운로드
            downloaded_file, original_title = download_video(url)
            # 3. 변환 (설정된 시간만큼 루프 & 페이드아웃)
            output_file = process_lofi_video(downloaded_file, original_title)
            # 4. 업로드 (공개)
            vid_id = upload_to_youtube(output_file, original_title)
            
            # 성공 메일 (선택사항)
            try:
                send_email(
                    f"[성공] {original_title} 업로드 완료", 
                    f"영상 확인: https://youtu.be/{vid_id}\n(설정: {TARGET_DURATION_MIN}분, {PRIVACY_STATUS})"
                )
            except: pass
        else:
            print(f"작업할 링크 없음: {msg}")
    except Exception as e:
        print(f"❌ 프로세스 실패: {e}")
        try: send_email("[실패] 에러 발생", str(e))
        except: pass
    finally:
        # 파일 정리
        cleanup_files([downloaded_file, output_file, "cookies.txt"])
