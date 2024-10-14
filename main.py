import asyncio
import speech_recognition as sr
import pyttsx3
import google.generativeai as genai
import os
from dotenv import load_dotenv
import logging
from datetime import datetime

# 환경 변수 로드
load_dotenv()

# 로그 설정
logging.basicConfig(
    filename='app.log',
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# TTS 엔진 초기화
tts_engine = pyttsx3.init()

# TTS 음성 속도 조절 함수
def my_tts(text):
    # 음성 속도 조절 (기본값은 200)
    rate = tts_engine.getProperty('rate')
    tts_engine.setProperty('rate', 150)  # 속도를 느리게 설정
    tts_engine.say(text)
    tts_engine.runAndWait()
    # 원래 속도로 되돌리기
    tts_engine.setProperty('rate', rate)

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
    # 추가 명령어는 여기서 처리
    return None

def update_conversation_history(user_input, ai_response):
    conversation_history.append({"user": user_input, "ai": ai_response})
    # 대화 이력을 파일에 저장 (옵션)
    with open("conversation_history.txt", "a", encoding="utf-8") as f:
        f.write(f"User: {user_input}\nAI: {ai_response}\n\n")

def log_interaction(user_input, ai_response):
    logging.info(f"User: {user_input}")
    logging.info(f"AI: {ai_response}")

async def my_stt():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("무슨 말이라도? : ")
        audio = r.listen(source)

    try:
        mySpeech = r.recognize_google(audio, language='ko', show_all=True)
        return mySpeech
    except sr.UnknownValueError:
        print("인식하지 못했습니다. 다시 시도해 주세요.")
        return None
    except sr.RequestError as e:
        print(f"Google 음성 서비스에 문제가 발생했습니다: {e}")
        return None

async def generate_ai_response(prompt):
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
        
        # 비동기적으로 API 요청
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: model.generate_content(concise_prompt, generation_config=config))
        
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

async def main():
    while True:
        recognition_result = await my_stt()
        if recognition_result:
            transcript = recognition_result.get('alternative', [{}])[0].get('transcript', '')
            print(f"인식된 텍스트: {transcript}")
            
            # 명령어 처리
            command_response = handle_command(transcript)
            if command_response:
                print(f"명령어 응답: {command_response}")
                my_tts(command_response)
                log_interaction(transcript, command_response)
                continue

            if "종료" in transcript:
                print("프로그램을 종료합니다.")
                my_tts("프로그램을 종료합니다.")
                break
            else:
                # AI 모델에게 질문 보내고 응답 받기
                ai_response = await generate_ai_response(transcript)
                print(f"Gemini 응답: {ai_response}")
                # TTS로 응답 듣기
                my_tts(ai_response)

if __name__ == "__main__":
    asyncio.run(main())
