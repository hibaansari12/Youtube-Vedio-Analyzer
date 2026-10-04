# YouTube Video Analyzer

A Streamlit app that gets captions (or transcribes audio), cleans the transcript,
and creates a concise report locally with BART. Reports can be written in
English or Hindi.

## Setup on Windows

1. From the project folder, create and activate a Python environment, then
   install the project dependencies:

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. Start the app:

   ```powershell
   streamlit run app.py
   ```

   Open the local URL printed by Streamlit, usually `http://localhost:8501`.

The first report may take longer while the `facebook/bart-large-cnn` model
downloads. Report generation then runs on this device and does not require an
API key or send the transcript to a cloud model.

## What it does

- Enter a YouTube link. The app tries English captions (including regional
  English captions), then Hindi captions, then local speech recognition if
  captions cannot be fetched.
- Reports can be written in English or Hindi. BART summarizes English text, so
  Hindi transcripts and Hindi output use local translation models, which
  download the first time they are needed.
- Key points are shown as plain text without labels such as “Claim” or
  “Proposal.” BART summaries can still make mistakes, so review important
  details against the downloaded transcript.
- Download the cleaned transcript as a readable `.txt` file with timestamped
  paragraphs. Common fillers such as “uh” and “um” and caption artifacts such
  as `>>` are removed; meaningful words such as “oh” are kept.
- Consecutive identical caption segments are removed. Long transcripts are split
  into word-sized sections, summarized locally in batches, and combined into one
  report.

The About page lists suitable video types and explains limitations. Captions
and audio still need to be accessible through YouTube; private videos and live
streams may not work. The app does not join live meetings or identify speakers
by name.

## Privacy and limitations

Speech recognition, report generation, and translation run on this device.
The BART and translation models download from their model repositories the first
time they are used, so internet access is needed for initial setup. YouTube
caption and audio retrieval also requires an internet connection. Generated
summaries can make mistakes, so review important details against the transcript.
