#!/usr/bin/env python3

import os
import sys
import logging
from pathlib import Path
from typing import List, Optional
from pydub import AudioSegment
from google.cloud import speech, storage
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables at startup
load_dotenv()

# Set Google Cloud credentials path
credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
if credentials_path:
    # Convert to absolute path if it's relative
    if not os.path.isabs(credentials_path):
        credentials_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), credentials_path)
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
    logger.info(f"Using Google Cloud credentials from: {credentials_path}")
else:
    logger.error("GOOGLE_APPLICATION_CREDENTIALS not found in .env file")
    print("Please create a .env file with GOOGLE_APPLICATION_CREDENTIALS=path/to/your/credentials.json")
    sys.exit(1)

class AudioTranscriber:
    def __init__(self, chunk_duration_ms: int = 300000):  # 5 minute chunks by default
        """Initialize the transcriber with configuration."""
        self.chunk_duration_ms = chunk_duration_ms
        self.speech_client = speech.SpeechClient()
        self.storage_client = storage.Client()
        self.bucket_name = "transcription-chunks"
        self._ensure_bucket_exists()
        
    def _ensure_bucket_exists(self):
        """Ensure the GCS bucket exists."""
        try:
            self.bucket = self.storage_client.get_bucket(self.bucket_name)
        except Exception:
            logger.info(f"Creating bucket {self.bucket_name}")
            self.bucket = self.storage_client.create_bucket(self.bucket_name, location="us-central1")
        
    def split_audio(self, input_file: str) -> List[str]:
        """
        Split the input audio file into smaller chunks.
        Returns a list of paths to the chunk files.
        """
        logger.info(f"Loading audio file: {input_file}")
        audio = AudioSegment.from_mp3(input_file)
        
        # Create chunks directory if it doesn't exist
        chunks_dir = Path("chunks")
        chunks_dir.mkdir(exist_ok=True)
        
        chunk_files = []
        for i, start in enumerate(range(0, len(audio), self.chunk_duration_ms)):
            chunk = audio[start:start + self.chunk_duration_ms]
            # Reduce audio quality to decrease file size
            chunk = chunk.set_frame_rate(16000).set_channels(1)
            chunk_path = chunks_dir / f"chunk_{i}.mp3"
            chunk.export(str(chunk_path), format="mp3", bitrate="64k")
            chunk_files.append(str(chunk_path))
            logger.info(f"Created chunk {i+1} at {chunk_path}")
            
        return chunk_files

    def transcribe_chunk(self, audio_file: str) -> Optional[str]:
        """
        Transcribe a single audio chunk using Google Cloud Speech-to-Text.
        Returns the transcribed text or None if transcription fails.
        """
        try:
            # Convert MP3 to FLAC with reduced quality
            audio = AudioSegment.from_mp3(audio_file)
            flac_path = audio_file.replace('.mp3', '.flac')
            # Ensure audio is mono and 16kHz for optimal transcription
            audio = audio.set_frame_rate(16000).set_channels(1)
            audio.export(flac_path, format="flac", parameters=["-compression_level", "0"])
            
            # Upload to GCS
            blob_name = f"chunks/{os.path.basename(flac_path)}"
            blob = self.bucket.blob(blob_name)
            blob.upload_from_filename(flac_path)
            gcs_uri = f"gs://{self.bucket_name}/{blob_name}"
            
            # Configure transcription
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.FLAC,
                sample_rate_hertz=16000,
                language_code="en-US",
                enable_automatic_punctuation=True,
            )
            audio = speech.RecognitionAudio(uri=gcs_uri)

            # Use long-running recognition
            operation = self.speech_client.long_running_recognize(config=config, audio=audio)
            logger.info(f"Waiting for operation to complete...")
            response = operation.result(timeout=90)

            transcript = ""
            for result in response.results:
                transcript += result.alternatives[0].transcript + " "
            
            # Clean up files
            os.remove(flac_path)
            blob.delete()
            return transcript.strip()
            
        except Exception as e:
            logger.error(f"Error transcribing {audio_file}: {str(e)}")
            if os.path.exists(flac_path):
                os.remove(flac_path)
            try:
                blob.delete()
            except:
                pass
            return None

    def transcribe_file(self, input_file: str, output_file: str) -> bool:
        """
        Main method to transcribe a large audio file.
        Returns True if successful, False otherwise.
        """
        try:
            # Split the audio file into chunks
            chunk_files = self.split_audio(input_file)
            logger.info(f"Split audio into {len(chunk_files)} chunks")

            # Transcribe each chunk
            transcripts = []
            for i, chunk_file in enumerate(chunk_files, 1):
                logger.info(f"Transcribing chunk {i}/{len(chunk_files)}")
                transcript = self.transcribe_chunk(chunk_file)
                if transcript:
                    transcripts.append(transcript)
                else:
                    logger.error(f"Failed to transcribe chunk {i}")

            # Combine all transcripts
            if transcripts:
                full_transcript = " ".join(transcripts)
                
                # Write to output file
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(full_transcript)
                
                logger.info(f"Successfully transcribed to {output_file}")
                return True
            else:
                logger.error("No successful transcriptions")
                return False

        except Exception as e:
            logger.error(f"Error during transcription process: {str(e)}")
            return False
        finally:
            # Clean up chunk files
            try:
                for chunk_file in chunk_files:
                    os.remove(chunk_file)
                os.rmdir("chunks")
                logger.info("Cleaned up temporary chunk files")
            except Exception as e:
                logger.warning(f"Error cleaning up chunk files: {str(e)}")

def main():
    # Check command line arguments
    if len(sys.argv) != 2:
        print("Usage: python transcribe.py <path_to_mp3_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    if not os.path.exists(input_file):
        print(f"Error: File {input_file} does not exist")
        sys.exit(1)

    # Generate output filename
    output_file = Path(input_file).stem + "_transcript.txt"
    
    # Create transcriber and process file
    transcriber = AudioTranscriber()
    success = transcriber.transcribe_file(input_file, output_file)
    
    if success:
        print(f"\nTranscription completed successfully!")
        print(f"Output saved to: {output_file}")
    else:
        print("\nTranscription failed. Check the logs for details.")
        sys.exit(1)

if __name__ == "__main__":
    main() 