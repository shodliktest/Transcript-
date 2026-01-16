import streamlit as st
import streamlit.components.v1 as components
import os, json, base64, time, pytz
from datetime import datetime
from deep_translator import GoogleTranslator
from groq import Groq

# --- 1. SOZLAMALAR ---
st.set_page_config(page_title="Neon Karaoke Pro", layout="wide", initial_sidebar_state="collapsed")
uz_tz = pytz.timezone('Asia/Tashkent')

# Streamlit interfeysini butunlay yashirish
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
        .stApp { background-color: black; }
        /* Uploader va tugmalarni yashirish, lekin ular orqada ishlaydi */
        div[data-testid="stFileUploader"], div.stButton {
            position: fixed;
            top: -100px;
        }
    </style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_groq_client():
    api_key = st.secrets.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
    return Groq(api_key=api_key) if api_key else None

client = get_groq_client()

# --- 2. HTML VA JS INYEKSIYA ---
def load_and_inject_html(audio_b64=None, segments=None, is_loading=False):
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()

    # JavaScript orqali Streamlit bilan bog'lanish (Bridge)
    bridge_script = f"""
    <script>
        // Sahifadagi "TANLASH" tugmasini Streamlit uploaderiga bog'lash
        document.addEventListener('click', function(e) {{
            if (e.target.classList.contains('upload-box') || e.target.closest('.upload-box')) {{
                window.parent.document.querySelector('input[type="file"]').click();
            }}
            if (e.target.id === 'startBtn') {{
                // Streamlit tugmasini bosish simulyatsiyasi
                const buttons = window.parent.document.querySelectorAll('button');
                buttons.forEach(btn => {{
                    if(btn.innerText.includes('RUN_ANALYSIS')) btn.click();
                }});
            }}
        }});

        // Python'dan ma'lumot kelsa, pleyerni ochish
        const audioData = "{audio_b64 if audio_b64 else ''}";
        const lyricsData = {json.dumps(segments) if segments else '[]'};
        
        if (audioData && lyricsData.length > 0) {{
            window.addEventListener('load', () => {{
                // Sahifalarni almashtirish
                document.querySelector('.upload-page').classList.add('hidden');
                const playerPage = document.querySelector('.player-page');
                playerPage.classList.add('active');
                
                // Audioni yuklash
                const audio = document.getElementById('audioPlayer');
                audio.src = "data:audio/mp3;base64," + audioData;
                
                // Matnlarni chiqarish
                const container = document.querySelector('.lyrics-container');
                container.innerHTML = '';
                lyricsData.forEach((line, i) => {{
                    const div = document.createElement('div');
                    div.className = 'lyric-line';
                    div.id = 'L-' + i;
                    div.innerHTML = `<div class="original">${{line.text}}</div>` + 
                                    (line.tr ? `<div class="translation">${{line.tr}}</div>` : '');
                    div.onclick = () => {{ audio.currentTime = line.start; audio.play(); }};
                    container.appendChild(div);
                }});

                // Sinxronizatsiya
                audio.ontimeupdate = () => {{
                    let idx = lyricsData.findIndex(x => audio.currentTime >= x.start && audio.currentTime < x.end);
                    document.querySelectorAll('.lyric-line').forEach(el => el.classList.remove('active'));
                    if(idx !== -1) {{
                        const activeEl = document.getElementById('L-' + idx);
                        activeEl.classList.add('active');
                        activeEl.scrollIntoView({{behavior:'smooth', block:'center'}});
                    }}
                }};
            }});
        }}
    </script>
    """
    return html.replace("</body>", bridge_script + "</body>")

# --- 3. ASOSIY MANTIQ ---

if 'status' not in st.session_state:
    st.session_state.status = 'idle' # idle, processing, ready

# Yashirin elementlar
up = st.file_uploader("UPLOAD", type=['mp3', 'wav'], key="actual_uploader")
# Bu tugma JS orqali bosiladi
run_btn = st.button("RUN_ANALYSIS")

if up:
    # Fayl tanlanganda index.html dagi "fileName" ni yangilash uchun kichik hiyla
    st.markdown(f"<script>window.parent.document.querySelector('.file-name').innerText = '{up.name}';</script>", unsafe_allow_html=True)

if run_btn and up:
    st.session_state.status = 'processing'
    
    with st.spinner(""): # Streamlit spinnerini yashirin saqlaymiz
        try:
            temp_path = f"temp_{time.time()}.mp3"
            with open(temp_path, "wb") as f:
                f.write(up.getbuffer())
            
            with open(temp_path, "rb") as f:
                trans = client.audio.transcriptions.create(
                    file=(temp_path, f.read()),
                    model="whisper-large-v3-turbo",
                    response_format="verbose_json",
                )
            
            # Matnni bo'laklash (Basic Style)
            all_words = []
            for seg in trans.segments:
                words = seg['text'].strip().split()
                dur = (seg['end'] - seg['start']) / len(words) if words else 0
                for i, w in enumerate(words):
                    all_words.append({
                        "text": w,
                        "start": seg['start'] + (i * dur),
                        "end": seg['start'] + ((i + 1) * dur)
                    })
            
            # Tarjima va guruhlash
            final_segments = []
            translator = GoogleTranslator(source='auto', target='uz') # Standart o'zbekcha
            
            for i in range(0, len(all_words), 3):
                chunk = all_words[i:i+3]
                txt = " ".join([w['text'] for w in chunk])
                tr = translator.translate(txt)
                final_segments.append({
                    "start": chunk[0]['start'],
                    "end": chunk[-1]['end'],
                    "text": txt,
                    "tr": tr
                })
            
            st.session_state.audio_b64 = base64.b64encode(up.getvalue()).decode()
            st.session_state.segments = final_segments
            st.session_state.status = 'ready'
            os.remove(temp_path)
            st.rerun()
            
        except Exception as e:
            st.error(f"Xato: {e}")

# --- 4. EKRANGA CHIQARISH ---

if st.session_state.status == 'ready':
    html_to_show = load_and_inject_html(st.session_state.audio_b64, st.session_state.segments)
else:
    html_to_show = load_and_inject_html()

components.html(html_to_show, height=1000, scrolling=False)
