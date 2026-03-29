import streamlit as st
import ollama
from gtts import gTTS
import speech_recognition as sr
import tempfile
import time
import re
import base64

# --- הגדרות דף ועיצוב RTL ---
st.set_page_config(page_title="איה - עוזרת אישית", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Assistant:wght@300;400;700&display=swap');
    html, body, [data-testid="stSidebar"], .stMarkdown, .stChatMessage {
        direction: rtl; text-align: right; font-family: 'Assistant', sans-serif;
    }
    .stChatInputContainer { direction: rtl; }
    .status-box { 
        padding: 10px; border-radius: 8px; border-right: 4px solid #28a745; 
        background-color: #f1f3f4; margin-bottom: 8px; font-size: 14px;
    }
    .stAlert { direction: rtl; }
    </style>
    """, unsafe_allow_html=True)

# --- ניהול זיכרון (State) ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "chat_phase" not in st.session_state:
    st.session_state.chat_phase = "discovery"  # discovery, scheduling
if "lead_data" not in st.session_state:
    st.session_state.lead_data = {"שם": "", "מייל": "", "תאריך": "", "נושא": ""}

FREE_DATES = ["יום שני ב-10:00", "יום רביעי ב-16:00"]

# --- Sidebar: Lead Card & Voice Switch ---
with st.sidebar:
    st.header("📋 נתוני פגישה")
    for key, value in st.session_state.lead_data.items():
        val = value if value else "---"
        st.markdown(f'<div class="status-box"><b>{key}:</b> {val}</div>', unsafe_allow_html=True)
    
    st.divider()
    st.header("⚙️ הגדרות")
    voice_active = st.toggle("🔊 שמע פעיל", value=False, help="הפעל כדי לשמוע את איה. דורש לחיצה אחת על המסך להפעלה ב-Chrome.")
    voice_gender = st.radio("קול המערכת:", ["נשי", "גברי"], index=0)
    
    if st.button("🗑️ איפוס שיחה"):
        st.session_state.clear()
        st.rerun()

# --- פונקציות שמע (Base64 Injection) ---
def play_audio(file_path):
    if not voice_active: return  # If the audio is off, don't play anything
    try:
        with open(file_path, "rb") as f:
            data = f.read()
            b64 = base64.b64encode(data).decode()
            audio_html = f"""
                <audio autoplay="true">
                    <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
                </audio>
            """
            st.components.v1.html(audio_html, height=0)
    except Exception as e:
        st.error(f"Error playing audio: {e}")

def speak(text):
    try:
        clean_text = re.sub(r'[*#:_]', '', text)
        tts = gTTS(text=clean_text, lang='he', slow=(voice_gender == "גברי"))
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            tts.save(fp.name)
            play_audio(fp.name)  # Play the audio
        time.sleep(1)  # Add sleep to ensure the audio plays fully
    except Exception as e:
        st.error(f"Error in text-to-speech: {e}")

def listen():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        st.toast("🎤 מקשיבה...", icon="👂")
        try:
            audio = r.listen(source, timeout=5)
            return r.recognize_google(audio, language="he-IL")
        except: return None

# --- הנחיות המערכת (System Prompt) ---
missing_fields = [k for k, v in st.session_state.lead_data.items() if not v]

SYSTEM_PROMPT = f"""שמך איה. את עוזרת אדיבה.
1. אם המשתמש שואל שאלה מחוץ לנושא, עני בקצרה ובנימוס, אך החזירי אותו מיד להשלמת הפרטים לפגישה.
2. בשלב התיאום (scheduling), עליך לאסוף: {', '.join(missing_fields)}.
3. שאל על כל פרט בנפרד. אל תמשיך לפרט הבא עד שאישרת את הנוכחי.
4. כדי לעדכן את המערכת, עליך לומר מפורשות: "רשמתי את ה[שם השדה]".
5. תאריכים מותרים בלבד: {', '.join(FREE_DATES)}.
6. אינך מחפשת דירות בעצמך, רק קובעת פגישה עם סוכן."""

# --- תצוגת צ'אט ---
st.title("🤝 איה - תיאום פגישות חכם")

if not voice_active:
    st.info("שימו לב: השמע כבוי. הפעילו את המפסק בצידנית כדי לשמוע את איה.")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.markdown(msg["content"])

# קלט משתמש
u_input = None
c1, c2 = st.columns([0.1, 0.9])
with c1: 
    if st.button("🎤"): u_input = listen()
txt_in = st.chat_input("כתבו לאיה...")
if txt_in: u_input = txt_in

if u_input:
    st.session_state.messages.append({"role": "user", "content": u_input})
    with st.chat_message("user"): st.markdown(u_input)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_res = ""
        # הזרקת מצב השדות למודל
        ctx = f"\n[סטטוס נתונים: {st.session_state.lead_data}]"
        history = [{"role": "system", "content": SYSTEM_PROMPT + ctx}] + st.session_state.messages
        
        try:
            for chunk in ollama.chat(model='aya-expanse:8b', messages=history, stream=True):
                full_res += chunk['message']['content']
                placeholder.markdown(full_res + "▌")
            placeholder.markdown(full_res)

            # --- לוגיקת עדכון Sidebar (מבוססת אישור AI) ---
            if any(word in full_res for word in ["רשמתי", "עודכן", "אישרתי"]):
                # חילוץ מייל
                mail = re.search(r'[\w\.-]+@[\w\.-]+', full_res)
                if mail: st.session_state.lead_data["מייל"] = mail.group(0)
                
                # חילוץ תאריך
                for d in FREE_DATES:
                    if d in full_res: st.session_state.lead_data["תאריך"] = d
                
                # חילוץ נושא (אם השדה ריק)
                if st.session_state.lead_data["נושא"] == "" and len(full_res) > 8:
                    st.session_state.lead_data["נושא"] = full_res[:30]
                
                # חילוץ שם (אם הקלט קצר ולא מייל/תאריך)
                elif st.session_state.lead_data["שם"] == "" and len(u_input.split()) < 4:
                    st.session_state.lead_data["שם"] = u_input

            st.session_state.messages.append({"role": "assistant", "content": full_res})
            speak(full_res)  # Speak the assistant's response
            st.rerun()

        except Exception as e: 
            st.error(f"שגיאה: {e}")