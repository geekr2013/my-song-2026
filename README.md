🎧 YouTube Lofi Automation Bot (My-Song-2026)이 저장소는 유튜브 영상을 자동으로 다운로드하여 **Lofi 스타일(Slowed & Reverb)**로 변환하고, 15분 길이로 루프(Loop) 처리한 뒤, 감성적인 자막과 설명을 덧붙여 유튜브 채널에 자동 업로드하는 봇입니다.GitHub Actions를 통해 매일 한국 시간 오전 9시에 자동으로 실행됩니다.⚠️ 유지보수 가이드 (운영 시 필수 체크)봇이 멈추거나 에러가 날 때, 가장 먼저 확인해야 할 4가지입니다.1. 유튜브 쿠키 갱신 (가장 중요)증상: 로그에 Sign in to confirm you’re not a bot 또는 HTTP Error 429가 뜨며 다운로드 실패.원인: 유튜브 로그인 세션(쿠키)이 만료됨 (보통 1~3개월 주기).해결 방법:PC 크롬 브라우저에서 유튜브에 로그인합니다.Get cookies.txt LOCALLY 확장 프로그램을 사용하여 cookies.txt 내용을 복사합니다.GitHub Repo > Settings > Secrets and variables > Actions로 이동합니다.YOUTUBE_COOKIES 시크릿을 찾아 Update를 누르고 새 쿠키 값을 붙여넣습니다.2. 구글 스프레드시트 링크 충전증상: "링크 없음" 또는 "데이터 없음" 메일이 발송됨.해결: 연결된 구글 스프레드시트에 저작권 문제가 없는 유튜브 영상 링크를 주기적으로 채워 넣어주세요. (봇이 랜덤으로 하나씩 가져갑니다.)3. 한글 폰트 파일 (font.ttf)증상: 영상 자막이 □□□ (네모 박스)로 깨져서 나옴.해결: 저장소 최상위 경로(Root)에 font.ttf 파일이 존재하는지 확인하세요. (나눔고딕, 노토산스 등 무료 폰트 권장)4. 이메일 앱 비밀번호증상: 이메일 발송 실패 로그 (535 Username and Password not accepted).해결: 구글 계정 보안 설정에서 앱 비밀번호를 새로 발급받아 GitHub Secrets의 EMAIL_PASS를 갱신하세요.🛠 기능 및 특징완전 자동화: 소스 소싱(시트) → 다운로드 → 가공 → 업로드 → 알림 → 청소.Lofi 변환:Audio: 속도 0.85배 (Slowed), 피치 다운, 몽환적 분위기 연출.Video: 빈티지 컬러 필터(채도 감소, 대비 조절) 적용.자동 루프 (Loop): 원본 영상이 짧아도 설정된 시간(기본 15분)에 맞춰 자동으로 반복 연결합니다.자연스러운 마감: 영상이 끝날 때 오디오 페이드 아웃(Fade Out) 처리.봇 탐지 회피: Node.js, User-Agent, Cookie를 복합적으로 사용하여 유튜브 차단을 우회합니다.비용: 100% 무료 (GitHub Actions 무료 티어 활용).⚙️ 설정 변경 (main.py)main.py 파일 상단의 변수를 수정하여 채널 운영 정책을 바꿀 수 있습니다.Python# --- 설정값 ---
TARGET_DURATION_MIN = 15   # 목표 영상 길이 (분). 예: 60으로 하면 1시간
LOFI_SPEED = 0.85          # 속도 (낮을수록 느리고 몽환적)
RESOLUTION_HEIGHT = 720    # 해상도 (무료 서버 성능 고려 720p 권장)
PRIVACY_STATUS = 'public'  # 업로드 즉시 공개 ('private'로 변경 가능)
🔐 GitHub Secrets 설정이 프로젝트가 작동하기 위해서는 아래의 Repository Secrets가 등록되어 있어야 합니다.Secret 이름설명GCP_SA_KEY구글 스프레드시트 접근용 서비스 계정 JSONSHEET_URL소스 영상 링크가 들어있는 구글 시트 URLYOUTUBE_CLIENT_IDGCP OAuth 2.0 클라이언트 IDYOUTUBE_CLIENT_SECRETGCP OAuth 2.0 클라이언트 SecretYOUTUBE_REFRESH_TOKEN유튜브 업로드 권한 갱신 토큰YOUTUBE_COOKIES유튜브 봇 탐지 우회용 쿠키 텍스트EMAIL_USER알림을 보낼(받을) 지메일 주소 (전체 주소)EMAIL_PASS구글 계정 2단계 인증 앱 비밀번호 (16자리)📂 프로젝트 구조Plaintextmy-song-2026/
├── .github/
│   └── workflows/
│       └── run.yml      # 자동화 스케줄러 (매일 09:00 KST)
├── main.py              # 핵심 로직 (다운로드/변환/업로드)
├── requirements.txt     # 파이썬 라이브러리 목록
├── font.ttf             # 한글 자막용 폰트 파일 (사용자가 업로드 필요)
└── README.md            # 설명서
🚀 수동 실행 방법테스트가 필요하거나 즉시 업로드를 하고 싶을 때:GitHub 저장소 상단 메뉴의 Actions 클릭.좌측 Daily Lofi Maker 클릭.우측 Run workflow 버튼 클릭.Developed for Automated Lofi Channel Operation.
