import streamlit as st
import streamlit.components.v1 as components
import os, json, base64, time
from deep_translator import GoogleTranslator
from groq import Groq

# --- 1. SOZLAMALAR ---
st.set_page_config(page_title="Neon Karaoke Pro", layout="centered", initial_sidebar_state="collapsed")

# --- 2. HTML GENERATSIYA (Player Dizayni) ---
def get_player_html(audio_b64, json_data):
    return f"""
    <!DOCTYPE html>
    <html lang="uz">
    <head>
    <style>
        body {{ background-color: #000; color: #fff; font-family: sans-serif; overflow: hidden; margin: 0; padding: 0; }}
        
        /* PLAYER QUTISI */
        #main-player-box {{
            background: #080808; 
            border: 2px solid #00e5ff; 
            border-bottom: none; /* Pastki chiziqni olib tashlaymiz */
            border-radius: 20px 20px 0 0; /* Faqat tepa burchaklar yumaloq */
            padding: 20px; 
            box-shadow: 0 -5px 20px rgba(0,229,255,0.2); /* Soya faqat tepaga va yonlarga */
            margin: 2px; /* Chetlari kesilmasligi uchun */
        }}
        
        audio {{ width: 100%; filter: invert(1); margin-bottom: 20px; }}
        
        #lyrics {{ 
            height: 400px; /* Balandlikni biroz kamaytirdik */
            overflow-y: auto; 
            padding: 10px; 
            scroll-behavior: smooth; 
        }}
        
        /* Scrollbar */
        #lyrics::-webkit-scrollbar {{ width: 6px; }}
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
        
        /* Active style */
        .active {{
            background: linear-gradient(90deg, rgba(0, 229, 255, 0.15), transparent) !important;
            border-left-color: #00e5ff !important;
            transform: scale(1.01);
        }}
        .active .original {{ color: #00e5ff !important; }}
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

            // 2. Avto-scroll (Playerga tushirish)
            setTimeout(() => {{
                const box = document.getElementById('main-player-box');
                if(box) box.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
            }}, 500);

            // 3. Vaqt bo'yicha yurish
            audio.ontimeupdate = () => {{
                const t = audio.currentTime;
                let idx = data.findIndex(x => t >= x.start && t < x.end);
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

# --- 4. UMUMIY DIZAYN ---
st.markdown("""
    <style>
        /* Streamlit elementlarini yashirish */
        #MainMenu, footer, header, .stDeployButton {display: none;}
        div[data-testid="stDecoration"] {display: none;}
        div[data-testid="stStatusWidget"] {visibility: hidden;}
        .block-container {padding-top: 0rem !important; margin-top: 20px !important;}
        
        /* Fon */
        .stApp { background-color: #000000; color: white; }
        
        /* Matnlar */
        h1, h2, h3, p { color: #fff !important; text-align: center; text-shadow: 0 0 10px #00e5ff; }

        /* Uploader */
        [data-testid="stFileUploader"] {
            background-color: #050505;
            border: 2px dashed #00e5ff;
            border-radius: 20px;
            padding: 20px;
        }
        
        /* Button (Umumiy) */
        .stButton > button {
            background: linear-gradient(45deg, #00e5ff, #00ff88);
            color: black !important;
            font-weight: bold;
            border: none;
            border-radius: 15px;
            height: 50px;
            width: 100%;
            margin-top: 10px;
            transition: 0.3s;
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
                    with open(temp_path, "wb") as f: f.write(uploaded_file.getbuffer())
                    
                    # 2. Transkripsiya
                    my_bar.progress(40, text="AI tahlil qilmoqda...")
                    with open(temp_path, "rb") as file:
                        trans = client.audio.transcriptions.create(
                            file=(temp_path, file.read()),
                            model="whisper-large-v3-turbo",
                            response_format="verbose_json",
                        )
                    
                    # 3. Mantiq (So'z ajratish)
                    my_bar.progress(70, text="Gaplar tuzilmoqda...")
                    all_words = []
                    for seg in trans.segments:
                        words = seg['text'].strip().split()
                        if not words: continue
                        dur = (seg['end'] - seg['start']) / len(words)
                        for i, w in enumerate(words):
                            all_words.append({
                                "text": w, "start": seg['start'] + (i * dur), "end": seg['start'] + ((i + 1) * dur)
                            })
                    
                    # 4. Katta harf mantiqi
                    final_lines = []
                    current_line = []
                    start_t = 0.0
                    if all_words: start_t = all_words[0]['start']

                    t_code = {"📄 Original": None, "🇺🇿 O'zbek":"uz","🇷🇺 Rus":"ru","🇬🇧 Ingliz":"en"}.get(lang)

                    for i, item in enumerate(all_words):
                        w = item['text']
                        clean = w.strip().replace('"','').replace('(','')
                        
                        if i > 0 and clean and clean[0].isupper():
                            full_txt = " ".join([x['text'] for x in current_line])
                            tr = GoogleTranslator(source='auto', target=t_code).translate(full_txt) if t_code else None
                            final_lines.append({"start": start_t, "end": item['start'], "text": full_txt, "tr": tr})
                            current_line = [item]
                            start_t = item['start']
                        else:
                            current_line.append(item)
                    
                    if current_line:
                        full_txt = " ".join([x['text'] for x in current_line])
                        tr = GoogleTranslator(source='auto', target=t_code).translate(full_txt) if t_code else None
                        final_lines.append({"start": start_t, "end": current_line[-1]['end'], "text": full_txt, "tr": tr})

                    # Tayyor
                    my_bar.progress(100, text="Tayyor!")
                    time.sleep(0.5)
                    my_bar.empty()

                    # HTML yaratish
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
    
    # Maxsus CSS: Buttonni Playerga yopishtirish uchun
    st.markdown("""
        <style>
            /* Iframe (Player) pastki qismini to'g'irlash */
            .element-container iframe {
                margin-bottom: -7px !important; /* Player va Button orasidagi masofani yo'qotish */
                display: block;
            }
            
            /* Yangi musiqa tugmasini Playerning davomi qilish */
            .stButton > button {
                border-radius: 0 0 20px 20px !important; /* Faqat pastki burchaklar yumaloq */
                border-top: none !important; /* Tepa chiziq yo'q (Player bilan ulanadi) */
                background: #080808 !important; /* Player foni bilan bir xil */
                border: 2px solid #00e5ff;
                color: #00e5ff !important; /* Yozuv rangi neon */
                box-shadow: 0 5px 20px rgba(0,229,255,0.2); /* Soya pastga */
                margin-top: 0 !important;
                height: 50px;
                text-transform: uppercase;
                letter-spacing: 2px;
            }
            .stButton > button:hover {
                background: #00e5ff !important;
                color: #000 !important;
                box-shadow: 0 0 20px #00e5ff;
            }
            /* Tepada ortiqcha joy qolmasligi uchun */
            .block-container { padding-top: 0 !important; margin-top: 10px !important; }
        </style>
    """, unsafe_allow_html=True)

    # HTML Playerni chiqarish (Height biroz kamaytirildi moslashish uchun)
    components.html(st.session_state.player_html, height=580)
    
    # Tugma (endi u playerga yopishib turadi)
    if st.button("🔄 YANGI MUSIQA YUKLASH"):
        st.session_state.page = 'upload'
        st.session_state.player_html = ""
        st.rerun()
                        
