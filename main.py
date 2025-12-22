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
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, vfx, concatenate_videoclips, ColorClip
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- 환경 변수 로드 및 검증 ---
try:
    GCP_SA_KEY = json.loads(os.environ['GCP_SA_KEY'])
    SHEET_URL = os.environ['SHEET_URL']
    YT_CLIENT_ID = os.environ['YOUTUBE_CLIENT_ID']
    YT_CLIENT_SECRET = os.environ['YOUTUBE_CLIENT_SECRET']
    YT_REFRESH_TOKEN = os.environ['YOUTUBE_REFRESH_TOKEN']
    EMAIL_USER = os.environ['EMAIL_USER']
    EMAIL_PASS = os.environ['EMAIL_PASS']
except KeyError as e:
    print(f"❌ [설정 오류] 환경변수 {e}가 없습니다. GitHub Secrets를 확인하세요.")
    exit(1)

# --- 설정값 ---
TARGET_DURATION_MIN = 10  # 목표 영상 길이 (분). 최소 이 시간보다 길게 만듭니다.
LOFI_SPEED = 0.85         # Lofi 특유의 늘어지는 속도 (0.8~0.9 추천)
RESOLUTION_HEIGHT = 720   # 처리 속도를 위해 720p로 고정 (FHD는 무료 서버에서 너무 오래 걸림)

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
                print(f" - 삭제 완료: {file}")
        except Exception as e:
            print(f" - 삭제 실패 ({file}): {e}")

def get_random_link():
    print("📋 스프레드시트에서 랜덤 링크 추출 중...")
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(GCP_SA_KEY, scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_url(SHEET_URL).sheet1
        
        # 헤더를 제외한 모든 데이터 가져오기
        all_values = sheet.get_all_values()
        if len(all_values) < 2:
            return None, "데이터 없음"
            
        # 첫 줄(헤더) 제외하고 실제 데이터만 추출
        data_rows = all_values[1:] 
        
        # 링크가 있는 행만 필터링 (B열 혹은 C열 등 링크 위치 확인)
        valid_links = []
        for row in data_rows:
            # 행의 모든 셀을 검사해서 'http'가 포함된 셀을 찾음
            for cell in row:
                if "youtube.com" in cell or "youtu.be" in cell:
                    valid_links.append(cell)
                    break
        
        if not valid_links:
            return None, "유효한 링크 없음"
            
        selected_link = random.choice(valid_links)
        print(f"🎲 랜덤 선택된 링크: {selected_link}")
        return selected_link, "성공"
        
    except Exception as e:
        print(f"❌ 스프레드시트 에러: {e}")
        return None, str(e)

def download_video(url):
    print(f"⬇️ 영상 다운로드 시작: {url}")
    # 파일명 고정하지 않고 yt-dlp가 처리하게 한 뒤 이름 변경
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': 'downloaded_video.%(ext)s',
        'merge_output_format': 'mp4',  # <--- [중요] 이 옵션을 추가하여 무조건 mp4로 저장되게 함
        'noplaylist': True,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return "downloaded_video.mp4", info.get('title', 'Unknown Title')

def process_lofi_video(input_path, original_title):
    print("🎨 Lofi 스타일 비디오 제작 중 (시간이 다소 소요됩니다)...")
    
    # 1. 클립 로드 및 기본 설정
    clip = VideoFileClip(input_path)
    
    # 2. 오디오/비디오 속도 변환 (Slowed Effect)
    # 속도를 줄이면 피치가 낮아져서 Lofi 느낌이 남
    print(" - 속도 및 피치 조절 중...")
    slow_clip = clip.fx(vfx.speedx, LOFI_SPEED)
    
    # 3. 비디오 필터 적용 (빈티지/Cozy 느낌)
    # 채도를 낮추고(0.7), 대비를 약간 높임
    print(" - 빈티지 컬러 필터 적용 중...")
    styled_clip = slow_clip.fx(vfx.colorx, 0.7).fx(vfx.lum_contrast, lum=0, contrast=0.1)
    
    # 4. 해상도 조정 (720p) - 처리 속도 최적화
    if styled_clip.h > RESOLUTION_HEIGHT:
        styled_clip = styled_clip.resize(height=RESOLUTION_HEIGHT)

    # 5. 반복 재생 (Looping) 로직
    # 현재 길이가 목표 시간(예: 10분)보다 짧으면 반복
    current_duration = styled_clip.duration
    target_duration = TARGET_DURATION_MIN * 60
    
    if current_duration < target_duration:
        repeat_count = int(target_duration // current_duration) + 1
        print(f" - 영상 길이가 짧아 {repeat_count}회 반복합니다.")
        final_clip = concatenate_videoclips([styled_clip] * repeat_count)
        # 너무 길어지지 않게 목표 시간 + 약간의 여유에서 자름
        final_clip = final_clip.subclip(0, target_duration)
    else:
        final_clip = styled_clip.subclip(0, target_duration)

    # 6. 텍스트 오버레이 (제목 표시)
    print(" - 자막 생성 중...")
    try:
        display_title = original_title[:40] + "..." if len(original_title) > 40 else original_title
        text_content = f"Now Playing:\n{display_title}\n\nSlowed & Reverb Mix"
        
        # 텍스트 클립 (중앙 하단)
        txt_clip = TextClip(text_content, fontsize=24, color='white', font='DejaVu-Sans-Bold', align='center')
        txt_clip = txt_clip.set_pos(('center', 0.8), relative=True).set_duration(final_clip.duration)
        txt_clip = txt_clip.set_opacity(0.6)
        
        final_video = CompositeVideoClip([final_clip, txt_clip])
    except Exception as e:
        print(f"⚠️ 텍스트 생성 실패 (영상만 진행): {e}")
        final_video = final_clip

    output_filename = "output_final.mp4"
    # 렌더링 (preset='ultrafast'로 속도 향상, threads=2로 CPU 활용)
    print(f"🚀 최종 렌더링 시작 (약 {TARGET_DURATION_MIN}분 영상)...")
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
    
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # 제목과 설명에 Lofi 관련 키워드 풍부하게 추가
    video_title = f"[Lofi/Study] {title} (Slowed & Reverb) - 10min Loop"
    # 제목 길이 제한 100자
    if len(video_title) > 100:
        video_title = video_title[:97] + "..."

    description = f"""
    Relaxing Lofi/Jazz Vibe Remix of '{title}'.
    Perfect for Studying, Sleeping, and Coding.
    
    Original Track: {title}
    Remixed & Edited by AI Automation.
    
    #lofi #jazz #study #relaxing #remix #backgroundmusic
    """
    
    request_body = {
        'snippet': {
            'title': video_title,
            'description': description,
            'tags': ['lofi', 'slowed', 'reverb', 'study music', 'background music'],
            'categoryId': '10' 
        },
        'status': {
            'privacyStatus': 'private', # 테스트용: 비공개 / 실사용시: public
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
        # 1. 랜덤 링크 가져오기
        url, msg = get_random_link()
        
        if url:
            # 2. 영상 다운로드
            downloaded_file, original_title = download_video(url)
            
            # 3. Lofi 스타일 변환 및 루프 (10분 이상)
            output_file = process_lofi_video(downloaded_file, original_title)
            
            # 4. 유튜브 업로드
            vid_id = upload_to_youtube(output_file, original_title)
            
            # 5. 결과 메일 전송
            send_email(
                f"[성공] {original_title} - Lofi 업로드 완료", 
                f"랜덤 선택된 영상: {original_title}\n유튜브 링크: https://youtu.be/{vid_id}\n(10분 루프 버전으로 업로드됨)"
            )
        else:
            print(f"작업할 링크를 찾지 못했습니다: {msg}")
            
    except Exception as e:
        print(f"❌ 치명적 에러 발생: {e}")
        try:
            send_email("[실패] 자동화 스크립트 에러", str(e))
        except:
            pass
    finally:
        # 6. 파일 청소 (성공/실패 여부 상관없이 실행)
        cleanup_files([downloaded_file, output_file])
