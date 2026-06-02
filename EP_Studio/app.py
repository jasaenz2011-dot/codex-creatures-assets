import os
import json
import threading
from pathlib import Path

import requests
import streamlit as st

# ── pyttsx3 is optional — fails gracefully if not available ──
try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

# ── Config ────────────────────────────────────────────────
APP_DIR    = Path(__file__).parent
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
MODEL      = os.getenv("OLLAMA_MODEL", "gemma4:31b")

# ── Goddess & Lucifer — Hardcoded Interview Script ────────
INTERVIEW_QUESTIONS = [
    (
        "Welcome to the Executive Producer's Desk. "
        "Regarding the 'Genie Lamp' artifacts — should the manifested anime villains "
        "be 1:1 perfect replicas of their source material, or should they carry a "
        "glitchy, automaton-style visual signature to show they aren't truly real?"
    ),
    (
        "Understood. Now let's talk about the Goddess herself. "
        "Is her power set rooted in divine law — immovable, ancient, inevitable — "
        "or is it more personal, shaped by emotion and relationship with Lucifer?"
    ),
    (
        "Interesting. For the tone: are we leaning into operatic tragedy, "
        "or does this universe carry dark humor underneath the mythology?"
    ),
    (
        "Last foundational question: does Lucifer want redemption, "
        "or has he fully embraced what he is — and finds the Goddess compelling precisely "
        "because she hasn't given up on him?"
    ),
]

SYSTEM_PROMPT = """You are the creative AI partner inside an Executive Producer's studio
for the 'Goddess & Lucifer' animated universe. Your role is to help develop lore,
character arcs, visual language, and story structure. You are direct, imaginative,
and treat every idea as raw material to be shaped — not judged. When the producer
gives you a creative answer, build on it, push it further, and surface implications
they may not have considered."""

# ── Page config ───────────────────────────────────────────
st.set_page_config(
    page_title="EP Studio — Goddess & Lucifer",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom dark theme CSS ─────────────────────────────────
st.markdown("""
<style>
  /* Base */
  [data-testid="stAppViewContainer"] { background: #080810; }
  [data-testid="stSidebar"]          { background: #0f0f1a; border-right: 1px solid #1e1e30; }
  .main .block-container             { padding-top: 1.5rem; max-width: 860px; }

  /* Typography */
  h1, h2, h3 { color: #c8a8ff; font-family: 'Georgia', serif; letter-spacing: 1px; }
  p, label, .stMarkdown { color: #b0b0c8; }

  /* Chat bubbles */
  .ep-bubble {
    background: #13132a;
    border-left: 3px solid #7040c0;
    border-radius: 4px;
    padding: 14px 18px;
    margin: 10px 0;
    color: #c8a8ff;
    font-style: italic;
    font-size: 15px;
    line-height: 1.7;
  }
  .user-bubble {
    background: #0f1a0f;
    border-left: 3px solid #40a060;
    border-radius: 4px;
    padding: 12px 18px;
    margin: 10px 0;
    color: #a0c8a0;
    font-size: 15px;
    line-height: 1.7;
  }
  .ai-bubble {
    background: #1a1020;
    border-left: 3px solid #9050e0;
    border-radius: 4px;
    padding: 14px 18px;
    margin: 10px 0;
    color: #d0b8f0;
    font-size: 15px;
    line-height: 1.7;
  }
  .status-bar {
    font-size: 11px;
    color: #404060;
    text-align: right;
    margin-top: -8px;
    margin-bottom: 12px;
    letter-spacing: 1px;
  }

  /* Input */
  .stTextArea textarea {
    background: #0f0f1e !important;
    color: #e0e0f0 !important;
    border: 1px solid #2a2a4a !important;
    border-radius: 6px !important;
  }
  .stButton > button {
    background: #2a1050;
    color: #c8a8ff;
    border: 1px solid #5030a0;
    border-radius: 6px;
    font-size: 13px;
    letter-spacing: 1px;
  }
  .stButton > button:hover { background: #3a1a70; }
</style>
""", unsafe_allow_html=True)


# ── TTS helper ────────────────────────────────────────────
def speak(text: str):
    """Fire TTS in a daemon thread so Streamlit doesn't block."""
    if not TTS_AVAILABLE:
        return
    def _speak():
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", 165)
            engine.setProperty("volume", 0.9)
            engine.say(text)
            engine.runAndWait()
        except Exception:
            pass
    threading.Thread(target=_speak, daemon=True).start()


# ── Ollama streaming call ─────────────────────────────────
def ollama_stream(messages: list):
    """Yield text chunks from Ollama streaming response."""
    payload = {
        "model":    MODEL,
        "messages": messages,
        "stream":   True,
    }
    try:
        with requests.post(OLLAMA_URL, json=payload, stream=True, timeout=120) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                token = chunk.get("message", {}).get("content", "")
                if token:
                    yield token
                if chunk.get("done"):
                    break
    except requests.exceptions.ConnectionError:
        yield "\n\n⚠ Cannot reach Ollama. Make sure it's running: `ollama serve`"
    except Exception as e:
        yield f"\n\n⚠ Error: {e}"


# ── Session state init ────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

if "q_index" not in st.session_state:
    st.session_state.q_index = 0

if "spoken_indices" not in st.session_state:
    st.session_state.spoken_indices = set()

if "ref_images" not in st.session_state:
    st.session_state.ref_images = []


# ── Sidebar ───────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎬 EP Studio")
    st.markdown("**Goddess & Lucifer Universe**")
    st.markdown(f"<div class='status-bar'>MODEL: {MODEL}</div>", unsafe_allow_html=True)
    st.divider()

    st.markdown("### Reference Art")
    uploaded = st.file_uploader(
        "Drop inspiration images",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        label_visibility="collapsed"
    )
    if uploaded:
        st.session_state.ref_images = uploaded
        for img in uploaded:
            st.image(img, use_container_width=True)

    st.divider()

    # ComfyUI integration point (future)
    st.markdown("### ComfyUI")
    comfy_url = st.text_input(
        "ComfyUI URL",
        value="http://127.0.0.1:8188",
        label_visibility="collapsed"
    )
    st.caption("Image generation — connect when ready")

    st.divider()
    if st.button("🔄 Reset Interview"):
        st.session_state.messages   = [{"role": "system", "content": SYSTEM_PROMPT}]
        st.session_state.q_index    = 0
        st.session_state.spoken_indices = set()
        st.rerun()

    tts_label = "🔊 Voice ON" if TTS_AVAILABLE else "🔇 Voice unavailable"
    st.caption(tts_label)


# ── Main header ───────────────────────────────────────────
st.markdown("# Executive Producer's Desk")
st.markdown("*Goddess & Lucifer — Creative Development Studio*")
st.divider()

# ── Render chat history ───────────────────────────────────
for msg in st.session_state.messages:
    if msg["role"] == "system":
        continue
    if msg["role"] == "assistant":
        st.markdown(f"<div class='ai-bubble'>{msg['content']}</div>", unsafe_allow_html=True)
    elif msg["role"] == "ep":
        st.markdown(f"<div class='ep-bubble'>{msg['content']}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='user-bubble'>{msg['content']}</div>", unsafe_allow_html=True)

# ── Current interview question ────────────────────────────
q_idx = st.session_state.q_index

if q_idx < len(INTERVIEW_QUESTIONS):
    question = INTERVIEW_QUESTIONS[q_idx]

    # Display EP question
    st.markdown(f"<div class='ep-bubble'>🎙 {question}</div>", unsafe_allow_html=True)

    # Speak once per question
    if q_idx not in st.session_state.spoken_indices:
        speak(question)
        st.session_state.spoken_indices.add(q_idx)

    # Producer response input
    with st.form(key=f"q_{q_idx}", clear_on_submit=True):
        answer = st.text_area(
            "Your answer",
            placeholder="Type your creative direction here...",
            height=100,
            label_visibility="collapsed"
        )
        submitted = st.form_submit_button("→ Send")

    if submitted and answer.strip():
        # Add to history
        st.session_state.messages.append({"role": "ep",   "content": question})
        st.session_state.messages.append({"role": "user", "content": answer.strip()})

        # Get AI response
        with st.spinner("Thinking..."):
            response_placeholder = st.empty()
            full_response = ""
            for token in ollama_stream(st.session_state.messages):
                full_response += token
                response_placeholder.markdown(
                    f"<div class='ai-bubble'>{full_response}▌</div>",
                    unsafe_allow_html=True
                )
            response_placeholder.markdown(
                f"<div class='ai-bubble'>{full_response}</div>",
                unsafe_allow_html=True
            )

        st.session_state.messages.append({"role": "assistant", "content": full_response})
        st.session_state.q_index += 1
        st.rerun()

else:
    # Interview complete — open creative chat
    st.markdown("---")
    st.markdown("### 🎬 Open Development Session")
    st.caption("Interview complete. Continue developing the universe freely.")

    with st.form(key="open_chat", clear_on_submit=True):
        prompt = st.text_area(
            "Message",
            placeholder="Explore a scene, character arc, visual concept...",
            height=100,
            label_visibility="collapsed"
        )
        send = st.form_submit_button("→ Send")

    if send and prompt.strip():
        st.session_state.messages.append({"role": "user", "content": prompt.strip()})
        st.markdown(f"<div class='user-bubble'>{prompt.strip()}</div>", unsafe_allow_html=True)

        with st.spinner(""):
            response_placeholder = st.empty()
            full_response = ""
            for token in ollama_stream(st.session_state.messages):
                full_response += token
                response_placeholder.markdown(
                    f"<div class='ai-bubble'>{full_response}▌</div>",
                    unsafe_allow_html=True
                )
            response_placeholder.markdown(
                f"<div class='ai-bubble'>{full_response}</div>",
                unsafe_allow_html=True
            )

        st.session_state.messages.append({"role": "assistant", "content": full_response})
        st.rerun()
