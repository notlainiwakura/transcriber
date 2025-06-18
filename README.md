# MP3 Transcription Tool

This tool transcribes large MP3 files using Google Cloud Speech-to-Text API. It automatically splits large audio files into manageable chunks, transcribes them, and combines the results into a single text file.

## Prerequisites

1. Python 3.7 or higher
2. Google Cloud account with Speech-to-Text API enabled
3. Service account credentials with Speech-to-Text permissions

## Setup

1. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up Google Cloud:
   - Go to the [Google Cloud Console](https://console.cloud.google.com)
   - Create a new project or select an existing one
   - Enable the Speech-to-Text API
   - Create a service account and download the JSON key file
   - Set the environment variable for the service account:
     ```bash
     export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service-account-key.json"
     ```

## Usage

Run the script with the path to your MP3 file:

```bash
python transcribe.py path/to/your/audio.mp3
```

The script will:
1. Split the audio file into 1-minute chunks
2. Transcribe each chunk using Google Cloud Speech-to-Text
3. Combine all transcriptions into a single text file
4. Save the output as `[original_filename]_transcript.txt`

## Features

- Automatic chunking of large audio files
- Progress logging
- Error handling and recovery
- Automatic cleanup of temporary files
- Support for automatic punctuation
- UTF-8 encoded output

## Notes

- The default chunk size is 1 minute (60000 ms)
- The script uses English (US) as the default language
- Make sure you have sufficient Google Cloud credits
- The script requires ffmpeg to be installed on your system for audio processing 