import streamlit as st
import openai
import tempfile
import os
from datetime import datetime
from audio_recorder_streamlit import audio_recorder
from dotenv import load_dotenv
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportModuleError:
    pass
api_key = os.getenv("OPENAI_API_KEY")

# ─── Page Config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="EM Clinical Note Assistant",
    page_icon="🏥",
    layout="wide",
)
# ─── 초기 세션 상태 설정 (보강된 버전) ───────────────────────────────────────
# 리스트에 있는 모든 키가 session_state에 없으면 초기값으로 설정합니다.
initial_states = {
    "raw_transcript": "",
    "clinical_summary": "",
    "audio_path": None,
    "audio_bytes_raw": None,
    "form_submitted": False
}

for key, value in initial_states.items():
    if key not in st.session_state:
        st.session_state[key] = value

# ─── API Key 설정 ─────────────────────────────────────────────────────────────
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")

# ─── Custom CSS (의료용 다크 테마 & UI 개선) ────────────────────────────────────
with st.sidebar:
    st.markdown("### 📋 Template Selection")
    
    # 1. 프롬프트 템플릿 정의
    templates = {
        "의학적 요약 (General)": """"너는 숙련된 응급의학과 전문의의 비서다. 의학과 전문의가 환자 진찰하는 대화문(History Taking)을 읽고, 의학적 용어(English preferred)를 사용하여 Clinical Summary로 정리한다"
1. 너는 입력된 [Dialogue] 섹션의 텍스트만 분석하는 전문 비서이다.
2. 절대 대화문에 없는 질환(DM, HTN 등)이나 증상을 추측하거나 예시 데이터를 출력에 포함하지 마라.
3. 중요) [DIalogue] 에 없는 내용은 추론하여 입력하지 않는다.
4. EMR 기록 양식 중 Prev Hx>, Current Hx>, ROS>, PE> 부분을 기록 한다.
4.1 이전 특이병력 없으면 Prev Hx> 대신 Prev healthy.  로 기술한다.
5-1 Current Hx> 를 기술할때는 환자와의  진단명이 아닌 General weakness 같은 증상에 대한 용어는 약자를 사용하지 않는다.
5-2 첫 문장은 환자의 주 호소를 기술하며, ~일 전 부터 시작된 ~ 증상으로 내원. 으로 기술하며 dialogue 에서 환자의 호소를 자세히 기술한다. (환자의 언어로 ROS 도 Current Hx 에 기술한다). 
5-3 주호소에 대한 내용 기술 후 줄바꿈을 하고, 이후에도 주요 내용 (현재 주호소의 자세한 경과, 이전에 유사한 증상, 기타 생활에 대한 내용 등) 이 바뀔때 줄 바꿈을 한다. 첫줄에 * 등의 표시자는 쓰지 않는다.
5-4  환자의 주증상에 대한 기술은 환자가 이야기한 언어를 그대로 이야기하되, 의학용어는 영어 약자를 사용한다 (한글 병용은 불필요) 여러 단어로 이루어진 진단명은 약자로 사용 (예, IBD), 단일 단어 진단명 및 ROS는 전체질환명 기술 (예 pneumonia, dyspnea)한다.
5-5 반복되는 이야기는 정리하여 기술한다.
5-6 주증상이 외상 (trauma) 의 경우에는 [Dialogue]의 사고 기전을 자세하게 기록 하며  (누가/ 어디서/ 어떻게), 환자가 이야기한 언어와 단어를 그대로 살려서 기술한다.
5-7 주 증상이 마비, 의식 저하등의 경우에는 LNT(Last normal time), FAT (First abnormal time) 을 기록하고, 발견 장소, 발견자 등을 기록한다.
5-8 의사가 환자에게 이야기한 plan은 기입하지 않는다.
5-9 식사, 생활, 환경 등의 일상 생활용어는 스크립트에 있는데로, 한글으로 옮긴다.
5-10 환자의 이름은 비식별처리 (OOO씨/ OOO님) 으로 한차례 filtering한 내용으로, hx 안에 환자이름 대신, "상환" 이라고 표시한다
5-11 한글 음성 인식으로 인해 오타가 있을 수 있으니, 문맥에 맞게 의학 용어로 교정 한다 (숨절이 괜찮으세요? -> Lung sound); 현재까지 자주 틀린 trascription error의 예는 아래와 같으며, 일상언어 기반의 STT 사용에 기반한 의학용어의 일상언어 치환에 따른 오류릉 동반 할 수 있다.
5-12 각 문장은 "~함", "하였음" 과 같은 개조식으로 작성할것
6. ROS> F/C -/- C/S/R -/-/- 과 같은 약자로 이루어진 양식을 사용한다.
7. P/E> 는 청진을 시행한 경우 Chest : Both lung sound clear / rale / crackle, 과 같은 양식, 복부 검진을 시행한 경우 Abdomen : No focal Td 와 같은 양식을 사용하며, 신경학적 검진을 시행한 경우 NE> Motor> V/V , V/V ( = Rt upper/Lt upper, Rt Lower/Lt lower) 와 같은 양식으로 출력하며,  마비 증상이 동반된 경우 추정되는 NIHSS 점수를 출력한다 (ex NIHSS 4- (Rt arm weakness: 2, Rt leg weakness: 2) (검사하지 않은 항목은 정상으로 간주한다 
7-1. 이외 문맥상 추론할 수 있는 신체검진 "목 들어볼때 아프세요? - Neck stiffness" 역시 표기한다.
8. 출력은 예시의 순서에 맞추어 하며  각 세부항목간 구분은 Prev Hx> 형식의 ** 기호없는 섹션 제목 아래에 작성한다

[ 출력형식 (예시) ]
Prev hx>
# disease 1
# disease 2(n YA) 

 상환 xx 부터 발생한 xx 로 내원함. xx 는 xx 한 양상으로 현재는 xx 하다 함. ~
[Dialogue]""",

        "119 Triage": """너는 응급실 Triage 간호사의 전담비서로 119와의 통화 내용을 듣고, 환자의 상태를 요약하여 정리하여야 한다.
        1. 너는 입력된 [Dialogue] 섹션의 텍스트만 분석하는 전문 비서이다.
        2. 절대 대화문에 없는 질환이나 증상을 추측하거나 예시 데이터를 출력에 포함하지 마라.
        3. 중요) [DIalogue] 에 없는 내용은 추론하여 입력하지 않는다.
        4. 이송요청을 한 119 구급대원의 소속과 이름을 기술한다 (예, OO소방서 OOO 구급대원)
        5. 환자의 상태를 간단히 요약하여 기술한다. (예, 50대 남성, 의식 저하, 호흡곤란) 
        6. 환자의 vital sign이 언급된 경우, 해당 수치를 기술한다 (예, BP 90/60 mmHg, HR 120 bpm, RR 30/min, SpO2 88% on room air)
        7. 환자의 주요 증상과 사고 기전이 언급된 경우, 해당 내용을 기술한다 (예, 교통사고로 인한 다발성 외상, 심한 복통과 호흡곤란) 

        """,

        "자유 입력 (Custom)": "자유롭게 프롬프트를 입력하세요..."
    }

    # 2. 템플릿 선택 셀렉트박스
    selected_template_name = st.selectbox(
        "사용할 템플릿을 선택하세요",
        list(templates.keys())
    )

    # 3. 선택된 템플릿 내용을 텍스트 영역에 표시 (수정 가능)
    st.markdown("---")
    st.markdown("### ⚙️ Edit Prompt")
    user_prompt = st.text_area(
        "AI 페르소나 및 규칙", 
        value=templates[selected_template_name], 
        height=400
    )

    if st.button("초기 설정으로 복구"):
        st.rerun()

# ─── 메인 화면 구성 ───────────────────────────────────────────────────────────
st.markdown("<p class='main-header'>🎙️ EM Clinical Note Assistant</p>", unsafe_allow_html=True)
st.write("진료 대화를 녹음하면 Whisper가 전사하고 GPT가 Clinical Summary를 작성합니다.")

col1, col2 = st.columns([1, 1])

with col1:
    st.markdown("### #1. 녹음 및 전사")
    
    # 안내 메시지 가변 처리
    if "is_recording" not in st.session_state:
        st.session_state.is_recording = False

    # 녹음 중일 때 보여줄 시각적 피드백
    if st.session_state.get("audio_bytes_raw"):
         st.info("🎙️ 녹음 데이터가 존재합니다. 전사 버튼을 누르세요.")
    
    # 녹음 컴포넌트
    # 핵심: 실시간으로 bytes를 계속 업데이트하도록 설정
    audio_bytes = audio_recorder(
        text="녹음 시작/종료",
        recording_color="#ff4b4b",
        neutral_color="#00d4ff",
        icon_size="3x",
        pause_threshold=120.0, # 충분히 길게 설정
        key="recorder"
    )

    # 녹음 데이터가 생성되면(버튼을 눌러 종료했거나, 데이터가 들어오면) 세션에 저장
    if audio_bytes:
            # 녹음 파일 재생 및 임시 저장
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
                tmp_file.write(audio_bytes)
                st.session_state.audio_path = tmp_file.name
            
            st.audio(audio_bytes, format="audio/wav")
            
            # ✅ 추가: WAV 파일 다운로드 버튼
            st.download_button(
                label="💾 녹음 파일(.wav) 다운로드",
                data=audio_bytes,
                file_name=f"VOICE_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav",
                mime="audio/wav",
                use_container_width=True
            )
            st.success("✅ 녹음 완료")
            
    st.markdown("---")

    # ─── 개선된 [전사] 버튼 로직 ───
    if st.button("⚡ 전사 및 Summary 생성 (녹음 중이면 즉시 중단)", use_container_width=True, type="primary"):
        
        # 1. 만약 녹음 버튼을 안 눌러서 audio_bytes가 None인 경우 대응
        if not audio_bytes and not st.session_state.get("audio_path"):
            st.error("⚠️ 녹음된 데이터가 없습니다. 먼저 마이크 버튼을 눌러주세요.")
        else:
            # 처리 시작
            with st.spinner("처리 중입니다..."):
                try:
                    client = openai.OpenAI(api_key=OPENAI_API_KEY)
                    
                    # 현재 세션에 저장된 파일 경로 사용
                    if st.session_state.audio_path:
                        with open(st.session_state.audio_path, "rb") as f:
                            # [1단계] Whisper 전사
                            transcript = client.audio.transcriptions.create(
                                model="whisper-1", 
                                file=f, 
                                language="ko"
                            )
                            st.session_state.raw_transcript = transcript.text
                        
                        # [2단계] GPT 요약
                        response = client.chat.completions.create(
                            model="gpt-4o",
                            messages=[
                                {"role": "system", "content": user_prompt},
                                {"role": "user", "content": f"[Dialogue]\n{st.session_state.raw_transcript}"}
                            ],
                            temperature=0
                        )
                        st.session_state.clinical_summary = response.choices[0].message.content
                        st.success("✅ 처리가 완료되었습니다.")
                except Exception as e:
                    st.error(f"오류 발생: {e}")

with col2:
    st.markdown("### #2. Processing Result")
    
    tab_summary, tab_raw = st.tabs(["📋 Clinical Summary", "📝 Raw Transcript"])
    
    with tab_summary:
        if st.session_state.clinical_summary:
            st.markdown(f"```text\n{st.session_state.clinical_summary}\n```")
            st.download_button(
                "Copy to EMR (Text)", 
                st.session_state.clinical_summary,
                file_name=f"EMR_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt" 
            )
        else:
            st.info("처리가 완료되면 요약된 결과가 여기에 표시됩니다.")

    with tab_raw:
        if st.session_state.raw_transcript:
            st.text_area("원본 전사 내용", st.session_state.raw_transcript, height=300)
        else:
            st.info("전사된 원본 데이터가 표시됩니다.")

# ─── 하단 히스토리 관리 ────────────────────────────────────────────────────────
st.markdown("---")
with st.expander("💡 사용 팁"):
    st.write("""
    - **초록색 파형**: `audio_recorder` 컴포넌트 내부에서 녹음 중 움직이는 바를 통해 음량 확인이 가능합니다.
    - **프롬프트 수정**: 오른쪽 사이드바에서 원하는 EMR 양식에 맞춰 자유롭게 수정하세요.
    - **용어 교정**: GPT-4o 모델을 사용하여 '숨절이'와 같은 STT 오타를 'Lung sound' 등으로 자동 교정하도록 설정되어 있습니다.
    """)
