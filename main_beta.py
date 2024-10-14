import threading
import speech_recognition as sr
import pyttsx3
import google.generativeai as genai
import os
from dotenv import load_dotenv
import logging
import sqlite3
from datetime import datetime
import tkinter as tk
from tkinter import scrolledtext
import time

# 환경 변수 로드
load_dotenv()

# SQLite 데이터베이스 연결 및 테이블 생성
conn = sqlite3.connect('conversation_history.db', check_same_thread=False)
c = conn.cursor()
c.execute('''
    CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_input TEXT,
        ai_response TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')
conn.commit()

# 로그 설정
logging.basicConfig(
    filename='app.log',
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# TTS 엔진 초기화
tts_engine = pyttsx3.init()

# tkinter GUI 설정
root = tk.Tk()
root.title("Voice Interface-based Conversational AI System")

# 대화 창
conversation_window = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=60, height=20)
conversation_window.pack(pady=10)

def display_message(message):
    conversation_window.insert(tk.END, message + "\n")
    conversation_window.see(tk.END)

def display_and_tts(text):
    display_message(f"AI: {text}")
    my_tts(text)

# 상태 플래그 초기화
speaking_event = threading.Event()

# TTS 음성 속도 조절 함수
def my_tts(text):
    speaking_event.set()  # TTS 시작
    # 음성 속도 조절 (기본값은 200)
    rate = tts_engine.getProperty('rate')
    tts_engine.setProperty('rate', 150)  # 속도를 느리게 설정
    tts_engine.say(text)
    tts_engine.runAndWait()
    tts_engine.setProperty('rate', rate)
    speaking_event.clear()  # TTS 종료

# Gemini API 설정
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    print("API 키가 설정되지 않았습니다. .env 파일을 확인하세요.")
    exit(1)

genai.configure(api_key=API_KEY)

# 대화 이력 저장 리스트 초기화
conversation_history = []

def handle_command(transcript):
    if "날씨" in transcript:
        return "현재 날씨 정보는 제공되지 않습니다. 다른 질문을 해주세요."
    elif "시간" in transcript:
        current_time = datetime.now().strftime("%H:%M:%S")
        return f"현재 시간은 {current_time}입니다."
    elif "날짜" in transcript:
        current_date = datetime.now().strftime("%Y-%m-%d")
        return f"오늘은 {current_date}입니다."
    elif "뉴스" in transcript:
        return "현재 뉴스 정보를 제공하지 않습니다. 다른 질문을 해주세요."
    elif "계산" in transcript:
        return "간단한 계산을 도와드릴 수 있습니다. 계산할 내용을 말씀해 주세요."
    # 추가 명령어는 여기서 처리
    return None

def update_conversation_history(user_input, ai_response):
    conversation_history.append({"user": user_input, "ai": ai_response})
    # 데이터베이스에 대화 이력 저장
    c.execute('INSERT INTO conversations (user_input, ai_response) VALUES (?, ?)', (user_input, ai_response))
    conn.commit()
    # 대화 이력을 파일에 저장 (옵션)
    with open("conversation_history.txt", "a", encoding="utf-8") as f:
        f.write(f"User: {user_input}\nAI: {ai_response}\n\n")

def log_interaction(user_input, ai_response):
    logging.info(f"User: {user_input}")
    logging.info(f"AI: {ai_response}")

def generate_ai_response(prompt):
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        # 생성 설정 정의
        config = genai.GenerationConfig(
            max_output_tokens=100,        # 더 짧은 응답
            temperature=0.3              # 일관된 응답
        )
        
        # 대화 이력을 포함한 프롬프트 생성
        history = "\n".join([f"User: {entry['user']}\nAI: {entry['ai']}" for entry in conversation_history])
        concise_prompt = f"{history}\nUser: {prompt}\nAI: 간결하고 대화형으로 대답해 주세요. 이모티콘은 사용하지 말아 주세요."
        
        response = model.generate_content(
            concise_prompt,              # 수정된 프롬프트 전달
            generation_config=config     # 생성 설정 전달
        )
        
        # 응답 텍스트 추출
        ai_text = response.text.strip()
        
        # 대화 이력 업데이트
        update_conversation_history(prompt, ai_text)
        
        # 로그 기록
        log_interaction(prompt, ai_text)
        
        return ai_text
    except Exception as e:
        logging.error(f"Gemini API 요청 오류: {e}")
        print(f"Gemini API 요청 오류: {e}")
        return "응답을 받을 수 없습니다."

def stt_and_ai():
    r = sr.Recognizer()
    while True:
        if not speaking_event.is_set():
            with sr.Microphone() as source:
                print("무슨 말이라도? : ")
                audio = r.listen(source)
            try:
                mySpeech = r.recognize_google(audio, language='ko', show_all=True)
                if mySpeech:
                    transcript = mySpeech.get('alternative', [{}])[0].get('transcript', '')
                    print(f"인식된 텍스트: {transcript}")
                    # GUI 업데이트
                    root.after(0, lambda: display_message(f"User: {transcript}"))
                    
                    # 명령어 처리
                    command_response = handle_command(transcript)
                    if command_response:
                        print(f"명령어 응답: {command_response}")
                        root.after(0, lambda: display_and_tts(command_response))
                        log_interaction(transcript, command_response)
                        continue

                    if "종료" in transcript:
                        print("프로그램을 종료합니다.")
                        root.after(0, lambda: my_tts("프로그램을 종료합니다."))
                        root.after(0, lambda: root.quit())
                        break
                    else:
                        # AI 모델에게 질문 보내고 응답 받기
                        ai_response = generate_ai_response(transcript)
                        print(f"Gemini 응답: {ai_response}")
                        root.after(0, lambda: display_and_tts(ai_response))
            except sr.UnknownValueError:
                print("인식하지 못했습니다. 다시 시도해 주세요.")
                root.after(0, lambda: display_message("AI: 인식하지 못했습니다. 다시 시도해 주세요."))
            except sr.RequestError as e:
                print(f"Google 음성 서비스에 문제가 발생했습니다: {e}")
                root.after(0, lambda: display_message(f"AI: Google 음성 서비스에 문제가 발생했습니다: {e}"))
        else:
            # AI가 말하는 동안 대기
            time.sleep(0.1)

def start_thread():
    # 음성 인식 및 AI 응답 처리 스레드 시작
    start_button.config(state=tk.DISABLED)  # 버튼 비활성화
    threading.Thread(target=stt_and_ai, daemon=True).start()

# GUI 시작 버튼
start_button = tk.Button(root, text="대화 시작", command=start_thread)
start_button.pack(pady=10)

def on_closing():
    # 프로그램 종료 시 데이터베이스 연결 종료
    conn.close()
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_closing)

# tkinter 메인 루프 시작
root.mainloop()
