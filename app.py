import streamlit as st
import streamlit.components.v1 as components
import os
import json
import base64
from deep_translator import GoogleTranslator
from groq import Groq

# 1. Sozlamalar va Dizaynni yashirish
st.set_page_config(page_title="Neon Karaoke", layout="wide", initial_sidebar_state="collapsed")

# Streamlitning o'zini menyularini yashiramiz, shunda faqat sizning HTML ko'rinadi
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
        .stApp {
            background-color: black;
            margin: 0;
            padding: 0;
        }
        /* Fayl yuklash tugmasini markazga olamiz va chiroyli qilamiz */
        [data-testid="stFileUploader"] {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            z-index: 999;
            background: rgba(0, 0, 0, 0.8);
            padding: 20px;
            border: 2px solid #00e5ff;
            border-radius: 15px;
            width: 300px;
        }
    </style>
""", unsafe_allow_html=True)

# API Kalitni olish
api_key = os.environ.get("GROQ_API_KEY")
if "GROQ_API_KEY" in st.secrets:
    api_key = st.secrets["GROQ_API_KEY"]

client = Groq(api_key=api_key) if api_key else None

# 2. HTML Faylni o'qish funksiyasi
def load_html(audio_data=None, json_data=None):
    with open("index.html", "r", encoding="utf-8") as f:
        html_content = f.read()

    # Agar ma'lumotlar tayyor bo'lsa, ularni HTML ichiga "inyeksiya" qilamiz
    if audio_data and json_data:
        # Python ma'lumotlarini JS o'zgaruvchilariga aylantiramiz
        js_injection = f"""
        <script>
            // Python'dan kelgan ma'lumotlar
            const B64_AUDIO = "data:audio/mp3;base64,{audio_data}";
            const LYRICS_DATA = {json.dumps(json_data)};

            // Sahifa yuklangach, avtomatik Player oynasini ochamiz
            window.addEventListener('load', function() {{
                // Login va Upload oynalarini yashirish
                document.querySelector('.login-page').classList.add('hidden');
                document.querySelector('.upload-page').classList.add('hidden');
                
                // Player oynasini ochish
                const playerPage = document.querySelector('.player-page');
                playerPage.classList.remove('hidden');
                playerPage.classList.add('active');

                // Musiqani yuklash
                const audioPlayer = document.getElementById('audioPlayer');
                audioPlayer.src = B64_AUDIO;
                
                // Matnlarni generatsiya qilish
                const lyricsContainer = document.querySelector('.lyrics-container');
                lyricsContainer.innerHTML = '';
                
                LYRICS_DATA.forEach((line, i) => {{
                    const div = document.createElement('div');
                    div.className = 'lyric-line';
                    div.dataset.start = line.start;
                    div.dataset.end = line.end;
                    div.innerHTML = `<div class="original">${{line.text}}</div>` + 
                                    (line.tr ? `<div class="translation" style="font-size:14px; color:#888">${{line.tr}}</div>` : '');
                    
                    div.onclick = () => {{ audioPlayer.currentTime = line.start; audioPlayer.play(); }};
                    lyricsContainer.appendChild(div);
                }});

                // Vaqt bo'yicha yurish
                audioPlayer.ontimeupdate = () => {{
                    const t = audioPlayer.currentTime;
                    document.querySelectorAll('.lyric-line').forEach(l => {{
                        if (t >= l.dataset.start && t < l.dataset.end) {{
                            document.querySelector('.active')?.classList.remove('active');
                            l.classList.add('active');
                            l.scrollIntoView({{behavior: 'smooth', block: 'center'}});
                        }}
                    }});
                }};
            }});
        </script>
        """
        html_content = html_content.replace("</body>", js_injection + "</body>")
    
    return html_content

# --- ASOSIY MANTIQ ---

if 'data_ready' not in st.session_state:
    st.session_state.data_ready = False
    st.session_state.html = load_html() # Boshlanishiga toza HTML

# Agar ma'lumot tayyor bo'lmasa, Streamlit uploaderini ko'rsatamiz
if not st.session_state.data_ready:
    # Ekranda faqat Streamlit uploaderi va HTML foni ko'rinadi
    components.html(st.session_state.html, height=1000, scrolling=False)
    
    uploaded_file = st.file_uploader(" ", type=['mp3', 'wav'], label_visibility="collapsed")
    lang = st.selectbox("Tilni tanlang:", ["🇺🇿 O'zbek", "🇷🇺 Rus", "🇬🇧 Ingliz", "Original"])
    
    if uploaded_file and st.button("🚀 BOSHLASH"):
        if not client:
            st.error("API kalit yo'q!")
        else:
            with st.spinner("AI tahlil qilmoqda..."):
                # 1. Faylni vaqtincha saqlash
                bytes_data = uploaded_file.getvalue()
                with open("temp.mp3", "wb") as f: f.write(bytes_data)
                
                # 2. Groq
                with open("temp.mp3", "rb") as file:
                    trans = client.audio.transcriptions.create(
                        file=("temp.mp3", file.read()),
                        model="whisper-large-v3-turbo",
                        response_format="verbose_json"
                    )
                
                # 3. Qayta ishlash
                segments = []
                t_code = {"🇺🇿 O'zbek":"uz","🇷🇺 Rus":"ru","🇬🇧 Ingliz":"en"}.get(lang)
                
                for s in trans.segments:
                    words = s['text'].split()
                    dur = (s['end'] - s['start']) / len(words) if words else 0
                    for i in range(0, len(words), 3):
                        chunk = words[i:i+3]
                        txt = " ".join(chunk)
                        start = s['start'] + (i * dur)
                        end = start + (len(chunk) * dur)
                        tr = GoogleTranslator(source='auto', target=t_code).translate(txt) if t_code else None
                        segments.append({"start": start, "end": end, "text": txt, "tr": tr})

                # 4. Tayyor ma'lumotni HTML ichiga joylash
                b64_audio = base64.b64encode(bytes_data).decode()
                st.session_state.html = load_html(b64_audio, segments)
                st.session_state.data_ready = True
                st.rerun()

# Agar ma'lumot tayyor bo'lsa, faqat HTML Player ko'rinadi
else:
    components.html(st.session_state.html, height=1000, scrolling=False)
    if st.button("🔄 Yangi fayl"):
        st.session_state.data_ready = False
        st.session_state.html = load_html()
        st.rerun()
