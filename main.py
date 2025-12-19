import os
import json
import datetime
import smtplib
import random
import gspread 
from google.oauth2.service_account import Credentials
from google.oauth2.credentials import Credentials as UserCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from yt_dlp import YoutubeDL
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, vfx
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
    print(f"환경변수 로드 실패: {e}가 설정되지 않았습니다. GitHub Secrets를 확인해주세요.")
    exit(1)

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
        print("이메일 발송 성공")
    except Exception as e:
        print(f"이메일 발송 실패: {e}")

def cleanup_files(files):
    """작업이 끝난 파일을 삭제하여 디스크 공간을 확보합니다."""
    print("🧹 임시 파일 청소 중...")
    for file in files:
        try:
            if os.path.exists(file):
                os.remove(file)
                print(f"삭제 완료: {file}")
        except Exception as e:
            print(f"삭제 실패 ({file}): {e}")

def get_target_link():
    print("스프레드시트 확인 중...")
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(GCP_SA_KEY, scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_url(SHEET_URL).sheet1
        data = sheet.get_all_records()
        
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        print(f"오늘 날짜 기준: {today}")
        
        for row in data:
            row_date = str(row.get('날짜', '') or row.get('Date', '') or row.get('date', ''))
            if today in row_date:
                link = row.get('링크', '') or row.get('Link', '') or row.get('link', '')
                if link:
                    return link
        return None
    except Exception as e:
        print(f"스프레드시트 읽기 에러: {e}")
        return None

def download_video(url):
    print(f"영상 다운로드 시작: {url}")
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': 'input_video.%(ext)s',
        'noplaylist': True,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return "input_video.mp4", info.get('title', 'Unknown Title')

def create_lofi_content(input_path, original_title):
    print("Lofi 스타일 변환 시작 (무료 모드)...")
    
    clip = VideoFileClip(input_path)
    if clip.duration > 180:
        clip = clip.subclip(0, 180)
        
    new_audio = clip.audio.fx(vfx.speedx, 0.85).volumex(0.8)
    
    new_clip = clip.fx(vfx.speedx, 0.85)
    new_clip = new_clip.fx(vfx.colorx, 0.8) 
    new_clip = new_clip.fx(vfx.lum_contrast, lum=-10, contrast=0.1) 
    new_clip = new_clip.set_audio(new_audio)

    try:
        display_title = original_title[:30] + "..." if len(original_title) > 30 else original_title
        text_content = f"Now Playing:\n{display_title}\n\nLofi Remixed"
        
        txt_clip = TextClip(text_content, fontsize=30, color='white', font='DejaVu-Sans-Bold')
        txt_clip = txt_clip.set_pos(('center', 'bottom')).set_duration(new_clip.duration)
        txt_clip = txt_clip.set_opacity(0.7)
        
        final_video = CompositeVideoClip([new_clip, txt_clip])
    except Exception as e:
        print(f"텍스트 생성 중 오류 (영상만 제작): {e}")
        final_video = new_clip

    output_filename = "output_lofi.mp4"
    final_video.write_videofile(output_filename, codec='libx264', audio_codec='aac', threads=4)
    
    return output_filename

def upload_to_youtube(file_path, title):
    print("유튜브 업로드 시작...")
    creds = UserCredentials(
        None,
        refresh_token=YT_REFRESH_TOKEN,
        client_id=YT_CLIENT_ID,
        client_secret=YT_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token"
    )
    
    youtube = build('youtube', 'v3', credentials=creds)
    
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    
    request_body = {
        'snippet': {
            'title': f"[Lofi Mix] {title} - {today_str}",
            'description': f'Relaxing Lofi Remix of {title}.\nUploaded via Automated Python Script.',
            'tags': ['lofi', 'remix', 'relaxing'],
            'categoryId': '10' 
        },
        'status': {
            'privacyStatus': 'private', # 테스트 성공 후 'public'으로 변경 고려
            'selfDeclaredMadeForKids': False,
        }
    }
    
    media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=request_body, media_body=media)
    response = request.execute()
    print(f"업로드 완료! Video ID: {response.get('id')}")
    return response.get('id')

if __name__ == "__main__":
    downloaded_file = "input_video.mp4"
    output_file = "output_lofi.mp4"
    
    try:
        url = get_target_link()
        if url:
            print(f"타겟 URL 발견: {url}")
            downloaded_file, original_title = download_video(url)
            output_file = create_lofi_content(downloaded_file, original_title)
            vid_id = upload_to_youtube(output_file, original_title)
            
            send_email(
                "[성공] Lofi 영상 자동 업로드 완료", 
                f"영상 제목: {original_title}\n결과 확인: https://youtu.be/{vid_id}\n(현재 비공개 상태입니다)"
            )
            
            # --- 마지막 단계: 파일 삭제 ---
            cleanup_files([downloaded_file, output_file])
            
        else:
            print("오늘 날짜의 처리할 영상 링크가 없습니다. (정상 종료)")
    except Exception as e:
        print(f"치명적 에러 발생: {e}")
        try:
            send_email("[실패] 영상 생성 중 에러 발생", str(e))
        except:
            pass
        
        # 에러가 나도 파일이 남아있다면 삭제 시도
        cleanup_files([downloaded_file, output_file])
        exit(1)
