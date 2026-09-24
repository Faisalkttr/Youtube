import re
import streamlit as st
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# --- UI Configuration ---
st.set_page_config(page_title="YouTube Transcript Extractor", page_icon="📝", layout="centered")
st.title("📝 YouTube Transcript Extractor")
st.caption("Paste a YouTube link, get the full transcript using the Official YouTube API.")

# Check for API Key
try:
    _ = st.secrets["YOUTUBE_API_KEY"]
    st.caption("🟢 Official YouTube API configured.")
except (KeyError, FileNotFoundError):
    st.error("🔴 Missing YOUTUBE_API_KEY in Streamlit secrets. Please add it to continue.")
    st.stop()

# --- Helper Functions ---

def get_youtube_client():
    """Initialize the YouTube Data API v3 client."""
    api_key = st.secrets["YOUTUBE_API_KEY"]
    return build('youtube', 'v3', developerKey=api_key)

def extract_video_id(text: str) -> str | None:
    text = text.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", text):
        return text
    patterns = [r"(?:v=|/videos/|embed/|youtu.be/|/shorts/|/live/)([A-Za-z0-9_-]{11})"]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None

def srt_time_to_seconds(time_str: str) -> float:
    """Convert SRT timestamp (e.g., 00:01:23,456) to seconds."""
    time_str = time_str.replace(',', '.')
    parts = time_str.split(':')
    if len(parts) == 3:
        h, m, s = parts
        s, ms = s.split('.')
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
    return 0.0

def parse_srt(srt_text: str) -> list:
    """Parse raw SRT text into a list of dictionaries with 'start' and 'text'."""
    # Remove HTML tags that YouTube sometimes includes in captions
    srt_text = re.sub(r'<[^>]+>', '', srt_text)
    
    # Split by double newlines to get individual caption blocks
    blocks = re.split(r'\n\s*\n', srt_text.strip())
    entries = []
    
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 3:
            time_range = lines[1]
            if '-->' in time_range:
                start_str = time_range.split(' --> ')[0].strip()
                # Join remaining lines in case the caption text spans multiple lines
                text = ' '.join(lines[2:]).strip()
                if text:
                    entries.append({
                        'start': srt_time_to_seconds(start_str),
                        'text': text
                    })
    return entries

def format_timestamp(seconds: float) -> str:
    seconds = int(seconds)
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def fetch_transcript_via_api(video_id: str, preferred_lang: str):
    """Fetch and parse captions using the Official YouTube Data API."""
    youtube = get_youtube_client()
    
    try:
        # 1. List available caption tracks
        request = youtube.captions().list(part='snippet', videoId=video_id)
        response = request.execute()
        tracks = response.get('items', [])
        
        if not tracks:
            return None, None, "No captions are available for this video."
            
        # 2. Score and select the best track
        def score_track(track):
            lang = track['snippet']['language']
            kind = track['snippet']['trackKind'] # 'standard' (manual) or 'ASR' (auto-generated)
            
            score = 0
            if preferred_lang and lang == preferred_lang.strip():
                score += 100
            elif lang == 'en':
                score += 50
                
            # Prefer manually created captions over auto-generated
            if kind == 'standard':
                score += 10
                
            return score

        tracks.sort(key=score_track, reverse=True)
        selected_track = tracks[0]
        
        # 3. Download the SRT file
        download_request = youtube.captions().download(
            id=selected_track['id'],
            tfmt='srt' # Request SubRip format for easy parsing
        )
        srt_content = download_request.execute()
        
        # The API client returns bytes for downloads
        if isinstance(srt_content, bytes):
            srt_content = srt_content.decode('utf-8')
            
        entries = parse_srt(srt_content)
        return entries, selected_track, None
        
    except HttpError as e:
        if e.resp.status == 404:
            return None, None, "Video not found or captions are disabled."
        elif e.resp.status == 403:
            return None, None, "Access forbidden. The video might be private, region-locked, or the API key lacks permissions."
        else:
            return None, None, f"YouTube API Error (Status {e.resp.status}): {e}"
    except Exception as e:
        return None, None, f"Unexpected error: {e}"

# --- Main UI Layout ---

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
            with st.spinner("Fetching transcript via Official API..."):
                entries, track_info, error_msg = fetch_transcript_via_api(video_id, preferred_lang)
                
                if error_msg:
                    st.error(error_msg)
                elif not entries:
                    st.warning("The caption track was found, but it contained no parseable text.")
                else:
                    # Format the output
                    if include_timestamps:
                        lines = [f"[{format_timestamp(e['start'])}] {e['text']}" for e in entries]
                    else:
                        lines = [e["text"] for e in entries]
                    
                    full_text = "\n".join(lines)
                    
                    # Determine track details for the success message
                    lang_name = track_info['snippet']['language']
                    is_auto = track_info['snippet']['trackKind'] == 'ASR'
                    track_type = "auto-generated" if is_auto else "manual"
                    
                    st.success(
                        f"Transcript retrieved via Official API ({lang_name} — {track_type}), "
                        f"{len(entries)} segments."
                    )
                    
                    st.text_area("Transcript", full_text, height=400)
                    
                    st.download_button(
                        "⬇️ Download as .txt",
                        data=full_text,
                        file_name=f"{video_id}_transcript.txt",
                        mime="text/plain",
                    )
                    
                    # Note: The official API doesn't easily let us list all languages without 
                    # making another API call, so we just show the one we fetched.
                    with st.expander("About this track"):
                        st.write(f"- **Language:** {lang_name} ({track_info['snippet']['language']})")
                        st.write(f"- **Type:** {track_type}")
                        st.write(f"- **Track ID:** `{track_info['id']}`")

st.divider()
st.caption(
    "Powered by the Official YouTube Data API v3. "
    "No IP blocks, no scraping. Quota: 10,000 units/day (approx. 100 videos)."
)
