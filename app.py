import streamlit as st
import streamlit.components.v1 as components
import os, json, base64, time, pytz
from datetime import datetime
from deep_translator import GoogleTranslator
from groq import Groq

# --- 1. SOZLAMALAR ---
st.set_page_config(page_title="Neon Karaoke Pro", layout="centered")

# --- 2. DIZAYN (INDEX.HTML dan olindi va Streamlitga moslandi) ---
st.markdown("""
<style>
    /* 1. Umumiy Fon (Qora) */
    .stApp {
        background-color: #000000;
        color: white;
    }

    /* 2. Sarlavhalar (Neon effekti) */
    h1, h2, h3, p {
        color: #fff !important;
        text-align: center;
        text-shadow: 0 0 10px #00e5ff, 0 0 20px #00e5ff;
        font-family: sans-serif;
    }

    /* 3. Fayl yuklash qutisi (Upload Box) */
    [data-testid="stFileUploader"] {
        background-color: #050505;
        border: 2px dashed #00e5ff;
        border-radius: 20px;
        padding: 20px;
        transition: 0.3s;
    }
    [data-testid="stFileUploader"]:hover {
        box-shadow: 0 0 20px rgba(0, 229, 255, 0.3);
    }
    /* "Drag and drop file here" yozuvini oq qilish */
    [data-testid="stFileUploader"] section > div {
        color: #00e5ff !important;
    }
    /* Kichik "Browse files" tugmasini yashirib, o'zimiznikiga o'xshatish */
    [data-testid="stFileUploader"] button {
        background-color: #000;
        color: #00e5ff;
        border: 1px solid #00e5ff;
        border-radius: 10px;
    }

    /* 4. Asosiy Tugmalar (Gradient Neon) */
    .stButton > button {
        background: linear-gradient(45deg, #00e5ff, #00ff88);
        color: black !important;
        font-weight: bold;
        border: none;
        border-radius: 15px;
        padding: 10px 20px;
        width: 100%;
        box-shadow: 0 0 15px #00e5ff;
        transition: 0.3s;
        height: 50px;
        font-size: 18px;
    }
    .stButton > button:hover {
        transform: scale(1.02);
        box-shadow: 0 0 25px #00ff88;
        color: black !important;
    }

    /* 5. Selectbox (Til tanlash) */
    [data-testid="stSelectbox"] label {
        color: #00e5ff !important;
    }
    div[data-baseweb="select"] > div {
        background-color: #111;
        border: 1px solid #00e5ff;
        color: white;
    }

    /* 6. Spinner (Kutish vaqtidagi aylanuvchi narsa) */
    .stSpinner > div {
        border-color: #00e5ff #000000 #00ff88 #000000;
    }
</style>
""", unsafe_allow_html=True)

# API Kalitni olish
api_key = st.secrets.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
client = Groq(api_key=api_key) if api_key else None

# --- 3. INTERFEYS VA MANTIQ ---

st.title("🎧 NEON KARAOKE PRO")
st.markdown("<p style='margin-bottom: 30px;'>Streamlit Neon Edition</p>", unsafe_allow_html=True)

# Fayl yuklash (Streamlitning o'z elementi, lekin Neon dizaynda)
uploaded_file = st.file_uploader("Musiqani tanlang (MP3/WAV)", type=['mp3', 'wav'])

# Til tanlash
col1, col2 = st.columns([2, 1])
with col1:
    lang = st.selectbox("Tarjima tili:", ["🇺🇿 O'zbek", "🇷🇺 Rus", "🇬🇧 Ingliz", "Original"])
with col2:
    st.write("") # Bo'sh joy
    st.write("") 
    # Bu yerda tugma bo'ladi

# Tahlil tugmasi
if uploaded_file:
    if st.button("🚀 TAHLILNI BOSHLASH"):
        if not client:
            st.error("API kalit topilmadi!")
        else:
            # --- 4. QAYTA ISHLASH (BACKEND) ---
            try:
                with st.spinner("Neon AI ishlamoqda..."):
                    # 1. Faylni vaqtincha saqlash
                    temp_path = f"temp_{int(time.time())}.mp3"
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    # 2. Transkripsiya (Whisper)
                    with open(temp_path, "rb") as file:
                        trans = client.audio.transcriptions.create(
                            file=(temp_path, file.read()),
                            model="whisper-large-v3-turbo",
                            response_format="verbose_json",
                        )
                    
                    # 3. Ma'lumotlarni tayyorlash
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
                    
                    # 3 tadan guruhlash va tarjima
                    final_segments = []
                    t_code = {"🇺🇿 O'zbek":"uz","🇷🇺 Rus":"ru","🇬🇧 Ingliz":"en"}.get(lang)
                    translator = GoogleTranslator(source='auto', target=t_code) if t_code else None

                    for i in range(0, len(all_words), 3):
                        chunk = all_words[i:i+3]
                        text = " ".join([w['text'] for w in chunk])
                        tr = translator.translate(text) if translator else None
                        
                        final_segments.append({
                            "start": chunk[0]['start'],
                            "end": chunk[-1]['end'],
                            "text": text,
                            "tr": tr
                        })
                    
                    # 4. NATIJA - NEON PLAYER (HTML Generatsiya)
                    # Natijani ko'rsatish uchun HTML ishlatamiz, chunki Streamlitning o'zida
                    # "Karaoke scrolling" funksiyasi yo'q. Lekin bu HTML ham app.py ichida turadi.
                    
                    audio_b64 = base64.b64encode(uploaded_file.getvalue()).decode()
                    json_data = json.dumps(final_segments)
                    
                    player_html = f"""
                    <div style="background: #080808; border: 2px solid #00e5ff; border-radius: 20px; padding: 20px; box-shadow: 0 0 20px rgba(0,229,255,0.2);">
                        <h3 style="color: #00e5ff; text-align: center; margin-bottom: 20px;">🎵 PLAYER</h3>
                        <audio id="player" controls style="width: 100%; filter: invert(1); margin-bottom: 20px;">
                            <source src="data:audio/mp3;base64,{audio_b64}" type="audio/mp3">
                        </audio>
                        <div id="lyrics" style="height: 400px; overflow-y: auto; padding: 10px; scroll-behavior: smooth;"></div>
                    </div>
                    
                    <script>
                        const data = {json_data};
                        const container = document.getElementById('lyrics');
                        const audio = document.getElementById('player');
                        
                        // Matnlarni chizish
                        data.forEach((line, i) => {{
                            const div = document.createElement('div');
                            div.id = 'line-' + i;
                            div.style.padding = '10px';
                            div.style.marginBottom = '5px';
                            div.style.borderLeft = '3px solid #333';
                            div.style.cursor = 'pointer';
                            div.style.transition = 'all 0.2s';
                            div.innerHTML = `<div style="font-size: 18px; color: #fff;">${{line.text}}</div>` + 
                                            (line.tr ? `<div style="font-size: 14px; color: #888;">${{line.tr}}</div>` : '');
                            
                            div.onclick = () => {{ audio.currentTime = line.start; audio.play(); }};
                            container.appendChild(div);
                        }});

                        // Vaqt bo'yicha yurish
                        audio.ontimeupdate = () => {{
                            const t = audio.currentTime;
                            let idx = data.findIndex(x => t >= x.start && t < x.end);
                            
                            // Barchasini tozalash
                            document.querySelectorAll('div[id^="line-"]').forEach(el => {{
                                el.style.background = 'transparent';
                                el.style.borderLeftColor = '#333';
                                el.children[0].style.color = '#fff';
                                if(el.children[1]) el.children[1].style.color = '#888';
                            }});

                            if(idx !== -1) {{
                                const active = document.getElementById('line-' + idx);
                                active.style.background = 'rgba(0, 229, 255, 0.1)';
                                active.style.borderLeftColor = '#00e5ff';
                                active.children[0].style.color = '#00e5ff';
                                if(active.children[1]) active.children[1].style.color = '#00ffff';
                                active.scrollIntoView({{behavior: 'smooth', block: 'center'}});
                            }}
                        }};
                    </script>
                    """
                    
                    # Natijani chiqaramiz
                    components.html(player_html, height=600)
                    os.remove(temp_path)

            except Exception as e:
                st.error(f"Xatolik: {e}")
