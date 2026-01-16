import streamlit as st
import streamlit.components.v1 as components
import os, json, base64, time, pytz
from datetime import datetime
from deep_translator import GoogleTranslator
from groq import Groq

# --- 1. SOZLAMALAR ---
st.set_page_config(page_title="Neon Karaoke Pro", layout="wide", initial_sidebar_state="collapsed")
uz_tz = pytz.timezone('Asia/Tashkent')

# Streamlit standart interfeysini butunlay yashirish
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
        .stApp { background-color: black; margin: 0; padding: 0; }
        /* Yashirin elementlar */
        div[data-testid="stFileUploader"], div.stButton { position: fixed; top: -100px; }
    </style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_groq_client():
    # Secrets-dan kalitni olish
    api_key = st.secrets.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
    return Groq(api_key=api_key) if api_key else None

client = get_groq_client()

# --- 2. HTML VA JS BOG'LIQLIGI ---
def get_ready_html(audio_b64=None, segments=None):
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()

    if audio_b64 and segments:
        # Python-dan kelgan natijani JS-ga o'tkazish
        injection = f"""
        <script>
        window.addEventListener('load', function() {{
            // 1. Sahifalarni almashtirish
            document.getElementById('uploadPage').classList.add('hidden');
            const playerPage = document.getElementById('playerPage');
            playerPage.classList.add('active');

            // 2. Musiqani yuklash
            const audio = document.getElementById('audioPlayer');
            audio.src = "data:audio/mp3;base64,{audio_b64}";
            
            // 3. Matnlarni (Lyrics) generatsiya qilish
            const container = document.getElementById('lyricsContainer');
            const data = {json.dumps(segments)};
            container.innerHTML = '';
            
            data.forEach((line, i) => {{
                const div = document.createElement('div');
                div.className = 'lyric-line';
                div.dataset.time = line.start;
                // Asl matn va tarjimani ko'rsatish
                let content = `<div>${{line.text}}</div>`;
                if(line.tr) content += `<div style="font-size: 0.7em; color: #00ffff; opacity: 0.6;">${{line.tr}}</div>`;
                div.innerHTML = content;
                
                div.onclick = () => {{ audio.currentTime = line.start; audio.play(); }};
                container.appendChild(div);
            }});

            // 4. Sinxronizatsiya logikasi
            audio.ontimeupdate = function() {{
                const currentTime = this.currentTime;
                const lines = document.querySelectorAll('.lyric-line');
                let activeIdx = data.findIndex((line, index) => {{
                    const nextTime = data[index + 1] ? data[index + 1].start : Infinity;
                    return currentTime >= line.start && currentTime < nextTime;
                }});

                lines.forEach(l => l.classList.remove('active'));
                if(activeIdx !== -1) {{
                    const el = lines[activeIdx];
                    el.classList.add('active');
                    el.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                }}
            }};
        }});
        </script>
        """
        html = html.replace("</body>", injection + "</body>")
    
    # Bridge: HTML tugmalarni Streamlit uploaderi bilan bog'lash
    bridge = """
    <script>
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('browse-btn')) {
            window.parent.document.querySelector('input[type="file"]').click();
        }
        if (e.target.id === 'startBtn') {
            const stButtons = window.parent.document.querySelectorAll('button');
            stButtons.forEach(btn => {
                if(btn.innerText.includes('ANALIZNI_BOSHLASH')) btn.click();
            });
        }
    });
    // Fayl tanlanganda ismini ko'rsatish
    window.parent.document.addEventListener('change', function(e) {
        if(e.target.type === 'file' && e.target.files.length > 0) {
            const fileName = e.target.files[0].name;
            const label = document.getElementById('fileName');
            label.textContent = "✅ " + fileName;
            label.classList.add('show');
        }
    });
    </script>
    """
    return html.replace("</body>", bridge + "</body>")

# --- 3. ASOSIY LOGIKA ---

if 'app_state' not in st.session_state:
    st.session_state.app_state = 'idle'

# Yashirin Streamlit elementlari
up = st.file_uploader("", type=['mp3', 'wav'], key="hidden_up")
run_btn = st.button("ANALIZNI_BOSHLASH")

if run_btn and up:
    try:
        with st.spinner(""):
            temp_path = f"t_{time.time()}.mp3"
            with open(temp_path, "wb") as f: f.write(up.getbuffer())
            
            # Groq AI
            with open(temp_path, "rb") as file:
                trans = client.audio.transcriptions.create(
                    file=(temp_path, file.read()),
                    model="whisper-large-v3-turbo",
                    response_format="verbose_json",
                )
            
            # Word-level timestamps va guruhlash (Basic Style)
            all_words = []
            for seg in trans.segments:
                words = seg['text'].strip().split()
                dur = (seg['end'] - seg['start']) / len(words) if words else 0
                for i, w in enumerate(words):
                    all_words.append({
                        "text": w,
                        "start": seg['start'] + (i * dur)
                    })
            
            # 3 tadan guruhlash va tarjima
            p_data = []
            lang_map = {"uzbek": "uz", "russian": "ru", "english": "en"}
            # Lang choice selectori hozircha index.html-da, biz u yerdan qiymat olish uchun 
            # soddalashtirilgan holda o'zbekchani tanlaymiz (yoki selector qo'shish mumkin)
            translator = GoogleTranslator(source='auto', target='uz')
            
            for i in range(0, len(all_words), 3):
                chunk = all_words[i:i+3]
                txt = " ".join([w['text'] for w in chunk])
                tr = translator.translate(txt)
                p_data.append({"start": chunk[0]['start'], "text": txt, "tr": tr})

            st.session_state.audio_b64 = base64.b64encode(up.getvalue()).decode()
            st.session_state.segments = p_data
            st.session_state.app_state = 'ready'
            os.remove(temp_path)
            st.rerun()
    except Exception as e:
        st.error(f"Xato: {e}")

# --- 4. EKRANGA CHIQARISH ---
if st.session_state.app_state == 'ready':
    current_html = get_ready_html(st.session_state.audio_b64, st.session_state.segments)
else:
    current_html = get_ready_html()

components.html(current_html, height=1000, scrolling=False)
