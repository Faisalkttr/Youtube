# YouTube Transcript Extractor (Streamlit)

Free, no API key needed — pulls captions directly using the open-source
`youtube-transcript-api` library.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open the local URL it prints (usually http://localhost:8501).

## Features
- Paste any YouTube URL (watch, youtu.be, shorts, embed) or just the video ID
- Optional timestamps
- Pick a preferred caption language (falls back automatically if unavailable)
- Download the transcript as a .txt file
- Shows which languages/tracks are available for the video

## Note on cloud deployment
YouTube sometimes blocks requests coming from shared cloud IPs (e.g. Streamlit
Community Cloud, Heroku, AWS). If you deploy there and get a "blocked" error,
running the app locally will usually work — or you can configure a proxy
(see the [youtube-transcript-api docs](https://github.com/jdepoix/youtube-transcript-api)
for proxy setup with `GenericProxyConfig` / `WebshareProxyConfig`).
