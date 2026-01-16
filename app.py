import streamlit as st
import streamlit.components.v1 as components
import os, json, base64, time
from deep_translator import GoogleTranslator
from groq import Groq

# --- 1. SOZLAMALAR ---
st.set_page_config(page_title="Neon Karaoke Pro", layout="centered", initial_sidebar_state="collapsed")

# --- 2. HTML GENERATSIYA FUNKSIYASI (Xatolikni oldini olish uchun alohida) ---
def get_player_html(audio_b64, json_data):
    # Bu HTML sizning index.html faylingiz asosida yaratilgan
    return f"""
    <!DOCTYPE html>
    <html lang="uz">
    <head>
    <style>
        body {{ background-color: #000; color: #fff; font-family: sans-serif; overflow: hidden; }}
        #main-player-box {{
            background: #080808; 
            border: 2px solid #00e5ff; 
            border-radius: 20px; 
            padding: 20px; 
            box-shadow: 0 0 20px rgba(0,229,255,0.2); 
            margin-top: 10px;
        }}
        audio {{ width: 100%; filter: invert(1); margin-bottom: 20px; }}
        #lyrics {{ 
            height: 450px; 
            overflow-y: auto; 
            padding: 10px; 
            scroll-behavior: smooth; 
        }}
        /* Scrollbar */
        #lyrics::-webkit-scrollbar {{ width: 8px; }}
        #lyrics::-webkit-scrollbar-track {{ background: #111; }}
        #lyrics::-webkit-scrollbar-thumb {{ background: #00e5ff; border-radius: 4px; }}
        
        .lyric-line {{
            padding: 15px;
            margin-bottom: 12px;
            border-left: 4px solid #333;
            background: rgba(255,255,255,0.02);
            border-radius: 0 10px 10px 0;
            cursor: pointer;
            transition: all 0.3s;
        }}
        .lyric-line:hover {{ background: rgba(255,255,255,0.05); }}
        .original {{ font-size: 20px; color: #fff; font-weight: 500; }}
        .translation {{ font-size: 16px; color: #888; margin-top: 5px; font-style: italic; }}
        
        /* Active line style */
        .active {{
            background: linear-gradient(90deg, rgba(0, 229, 255, 0.15), transparent) !important;
            border-left-color: #00e5ff !important;
            transform: scale(1.02);
        }}
        .active .original {{ color: #00e5ff !important; text-shadow: 0 0 10px rgba(0,229,255,0.5); }}
        .active .translation {{ color: #00ffff !important; }}
    </style>
    </head>
    <body>
        <div id="main-player-box">
            <audio id="player" controls>
                <source src="data:audio/mp3;base64,{audio_b64}" type="audio/mp3">
            </audio>
            <div id="lyrics"></div>
        </div>
        
        <script>
            const data = {json_data};
            const container = document.getElementById('lyrics');
            const audio = document.getElementById('player');
            
            // 1. Matnlarni chizish
            data.forEach((line, i) => {{
                const div = document.createElement('div');
                div.id = 'line-' + i;
                div.className = 'lyric-line';
                div.innerHTML = `<div class="original">${{line.text}}</div>` + 
                                (line.tr ? `<div class="translation">${{line.tr}}</div>` : '');
                
                div.onclick = () => {{ audio.currentTime = line.start; audio.play(); }};
                container.appendChild(div);
            }});

            // 2. Avto-Scroll (Sahifa yuklanganda playerga tushish)
            setTimeout(() => {{
                const box = document.getElementById('main-player-box');
                if(box) box.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
            }}, 500);

            // 3. Vaqt bo'yicha yurish
            audio.ontimeupdate = () => {{
                const t = audio.currentTime;
                // Hozirgi vaqtga mos keladigan indexni topish
                let idx = data.findIndex(x => t >= x.start && t < x.end);
                
                // Barcha active klasslarni olib tashlash
                document.querySelectorAll('.lyric-line').forEach(el => el.classList.remove('active'));

                if(idx !== -1) {{
                    const active = document.getElementById('line-' + idx);
                    active.classList.add('active');
                    active.scrollIntoView({{behavior: 'smooth', block: 'center'}});
                }}
            }};
        </script>
    </body>
    </html>
    """

# --- 3. SESSION STATE ---
if 'page' not in st.session_state:
    st.session_state.page = 'upload'
if 'player_html' not in st.session_state:
    st.session_state.player_html = ""

# --- 4. DIZAYN (CSS) ---
st.markdown("""
    <style>
        /* Streamlit elementlarini yashirish */
        #MainMenu, footer, header, .stDeployButton {display: none;}
        div[data-testid="stDecoration"] {display: none;}
        div[data-testid="stStatusWidget"] {visibility: hidden;}
        .block-container {padding-top: 0rem !important; margin-top: 20px !important;}
        
        /* Asosiy fon */
        .stApp { background-color: #000000; color: white; }
        
        /* Matnlar */
        h1, h2, h3, p { 
            color: #fff !important; 
            text-align: center;
            text-shadow: 0 0 10px #00e5ff;
        }

        /* Uploader va Tugmalar */
        [data-testid="stFileUploader"] {
            background-color: #050505;
            border: 2px dashed #00e5ff;
            border-radius: 20px;
            padding: 20px;
        }
        .stButton > button {
            background: linear-gradient(45deg, #00e5ff, #00ff88);
            color: black !important;
            font-weight: bold;
            border: none;
            border-radius: 15px;
            height: 50px;
            width: 100%;
            margin-top: 10px;
        }
        .stButton > button:hover { transform: scale(1.02); box-shadow: 0 0 20px #00ff88; }
        
        /* Progress Bar */
        .stProgress > div > div > div > div {
            background-image: linear-gradient(to right, #00e5ff, #00ff88);
        }
    </style>
""", unsafe_allow_html=True)

# API Kalit
api_key = st.secrets.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
client = Groq(api_key=api_key) if api_key else None

# --- 5. ASOSIY MANTIQ ---

# === YUKLASH SAHIFASI ===
if st.session_state.page == 'upload':
    st.title("🎧 NEON KARAOKE PRO")
    st.markdown("<p style='opacity:0.7'>AI Smart Synchronization</p>", unsafe_allow_html=True)

    uploaded_file = st.file_uploader("Musiqani tanlang (MP3/WAV)", type=['mp3', 'wav'])

    col1, col2 = st.columns([2, 1])
    with col1:
        lang = st.selectbox("Tarjima tili:", ["📄 Original", "🇺🇿 O'zbek", "🇷🇺 Rus", "🇬🇧 Ingliz"])
    with col2:
        st.write("")

    if uploaded_file:
        if st.button("🚀 TAHLILNI BOSHLASH"):
            if not client:
                st.error("API kalit topilmadi!")
            else:
                try:
                    my_bar = st.progress(0, text="Jarayon boshlanmoqda...")

                    # 1. Yuklash
                    my_bar.progress(10, text="Yuklanmoqda...")
                    temp_path = f"temp_{int(time.time())}.mp3"
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    # 2. Transkripsiya
                    my_bar.progress(40, text="AI tahlil qilmoqda...")
                    with open(temp_path, "rb") as file:
                        trans = client.audio.transcriptions.create(
                            file=(temp_path, file.read()),
                            model="whisper-large-v3-turbo",
                            response_format="verbose_json",
                        )
                    
                    # 3. So'zlarni ajratish
                    my_bar.progress(70, text="Gaplar tuzilmoqda...")
                    all_words = []
                    for seg in trans.segments:
                        words = seg['text'].strip().split()
                        if not words: continue
                        dur = (seg['end'] - seg['start']) / len(words)
                        for i, w in enumerate(words):
                            all_words.append({
                                "text": w,
                                "start": seg['start'] + (i * dur),
                                "end": seg['start'] + ((i + 1) * dur)
                            })
                    
                    # 4. Katta harf mantiqi
                    final_lines = []
                    current_line = []
                    start_t = 0.0
                    if all_words: start_t = all_words[0]['start']

                    for i, item in enumerate(all_words):
                        w = item['text']
                        clean = w.strip().replace('"','').replace('(','')
                        
                        # Katta harf bo'lsa yangi qator (lekin 1-so'z emas)
                        if i > 0 and clean and clean[0].isupper():
                            # Eski qatorni saqlash
                            full_txt = " ".join([x['text'] for x in current_line])
                            t_code = {"📄 Original": None, "🇺🇿 O'zbek":"uz","🇷🇺 Rus":"ru","🇬🇧 Ingliz":"en"}.get(lang)
                            tr = GoogleTranslator(source='auto', target=t_code).translate(full_txt) if t_code else None
                            
                            final_lines.append({
                                "start": start_t,
                                "end": item['start'],
                                "text": full_txt,
                                "tr": tr
                            })
                            current_line = [item]
                            start_t = item['start']
                        else:
                            current_line.append(item)
                    
                    # Oxirgi qator
                    if current_line:
                        full_txt = " ".join([x['text'] for x in current_line])
                        t_code = {"📄 Original": None, "🇺🇿 O'zbek":"uz","🇷🇺 Rus":"ru","🇬🇧 Ingliz":"en"}.get(lang)
                        tr = GoogleTranslator(source='auto', target=t_code).translate(full_txt) if t_code else None
                        final_lines.append({
                            "start": start_t,
                            "end": current_line[-1]['end'],
                            "text": full_txt,
                            "tr": tr
                        })

                    # Tayyorlash
                    my_bar.progress(100, text="Tayyor!")
                    time.sleep(0.5)
                    my_bar.empty()

                    # HTML ni yaratish
                    audio_b64 = base64.b64encode(uploaded_file.getvalue()).decode()
                    json_data = json.dumps(final_lines)
                    st.session_state.player_html = get_player_html(audio_b64, json_data)
                    
                    os.remove(temp_path)
                    st.session_state.page = 'player'
                    st.rerun()

                except Exception as e:
                    st.error(f"Xatolik: {e}")

# === PLAYER SAHIFASI ===
elif st.session_state.page == 'player':
    components.html(st.session_state.player_html, height=800)
    
    st.write("")
    if st.button("🔄 YANGI MUSIQA YUKLASH"):
        st.session_state.page = 'upload'
        st.session_state.player_html = ""
        st.rerun()
                    
