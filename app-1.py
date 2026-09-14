import re
import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
    InvalidVideoId,
    RequestBlocked,
    IpBlocked,
    CouldNotRetrieveTranscript,
)
from youtube_transcript_api.proxies import WebshareProxyConfig


def get_api() -> YouTubeTranscriptApi:
    """Build the API client, routing through a Webshare proxy if credentials
    are configured in Streamlit secrets. Falls back to a direct connection
    (fine for local runs) if no secrets are set."""
    try:
        username = st.secrets["WEBSHARE_USERNAME"]
        password = st.secrets["WEBSHARE_PASSWORD"]
    except (KeyError, FileNotFoundError):
        return YouTubeTranscriptApi()

    return YouTubeTranscriptApi(
        proxy_config=WebshareProxyConfig(
            proxy_username=username,
            proxy_password=password,
        )
    )

st.set_page_config(page_title="YouTube Transcript Extractor", page_icon="📝", layout="centered")

st.title("📝 YouTube Transcript Extractor")
st.caption("Paste a YouTube link, get the full transcript — free, no API key needed.")

try:
    _ = st.secrets["WEBSHARE_USERNAME"]
    st.caption("🟢 Proxy configured — routing requests through Webshare.")
except (KeyError, FileNotFoundError):
    st.caption("🟡 No proxy configured — using a direct connection (fine for local runs).")


def extract_video_id(text: str) -> str | None:
    text = text.strip()
    # Already a bare video ID (11 chars, typical YouTube ID charset)
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", text):
        return text
    patterns = [
        r"(?:v=|/videos/|embed/|youtu\.be/|/shorts/|/live/)([A-Za-z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


def format_timestamp(seconds: float) -> str:
    seconds = int(seconds)
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


url_input = st.text_input(
    "YouTube URL or Video ID",
    placeholder="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
)

col1, col2 = st.columns([1, 1])
with col1:
    include_timestamps = st.checkbox("Include timestamps", value=True)
with col2:
    preferred_lang = st.text_input("Preferred language code (optional)", placeholder="e.g. en, es, hi")

fetch_clicked = st.button("Get Transcript", type="primary")

if fetch_clicked:
    if not url_input:
        st.warning("Please paste a YouTube URL or video ID first.")
    else:
        video_id = extract_video_id(url_input)
        if not video_id:
            st.error("Couldn't find a valid YouTube video ID in that input. Please check the URL.")
        else:
            with st.spinner("Fetching transcript..."):
                try:
                    api = get_api()
                    transcript_list = api.list(video_id)

                    # Pick transcript: preferred language if given, else any available
                    transcript = None
                    if preferred_lang:
                        try:
                            transcript = transcript_list.find_transcript([preferred_lang.strip()])
                        except NoTranscriptFound:
                            st.info(f"No transcript found for language '{preferred_lang}'. Falling back to default.")

                    if transcript is None:
                        # Prefer manually created, fall back to generated, fall back to first available
                        available = list(transcript_list)
                        manual = [t for t in available if not t.is_generated]
                        transcript = (manual or available)[0]

                    fetched = transcript.fetch()
                    entries = fetched.to_raw_data()

                    if include_timestamps:
                        lines = [f"[{format_timestamp(e['start'])}] {e['text']}" for e in entries]
                    else:
                        lines = [e["text"] for e in entries]

                    full_text = "\n".join(lines)

                    st.success(
                        f"Transcript retrieved ({transcript.language} — "
                        f"{'auto-generated' if transcript.is_generated else 'manual'}), "
                        f"{len(entries)} segments."
                    )

                    st.text_area("Transcript", full_text, height=400)

                    st.download_button(
                        "⬇️ Download as .txt",
                        data=full_text,
                        file_name=f"{video_id}_transcript.txt",
                        mime="text/plain",
                    )

                    with st.expander("Available languages for this video"):
                        for t in transcript_list:
                            kind = "auto-generated" if t.is_generated else "manual"
                            st.write(f"- {t.language} ({t.language_code}) — {kind}")

                except TranscriptsDisabled:
                    st.error("Transcripts are disabled for this video.")
                except NoTranscriptFound:
                    st.error("No transcript is available for this video.")
                except VideoUnavailable:
                    st.error("This video is unavailable (private, deleted, or region-locked).")
                except InvalidVideoId:
                    st.error("That doesn't look like a valid YouTube video ID.")
                except (RequestBlocked, IpBlocked):
                    st.error(
                        "YouTube blocked this request (common when running on cloud/shared IPs, "
                        "e.g. Streamlit Cloud). Try running locally, or configure a proxy — see the "
                        "youtube-transcript-api docs for proxy setup."
                    )
                except CouldNotRetrieveTranscript as e:
                    st.error(f"Could not retrieve transcript: {e}")
                except Exception as e:
                    st.error(f"Unexpected error: {e}")

st.divider()
st.caption(
    "Built with the free, open-source `youtube-transcript-api` library — reads YouTube's "
    "publicly available caption tracks, no API key or quota required."
)
