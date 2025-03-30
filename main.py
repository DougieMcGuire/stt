import os
import whisper
from flask import Flask, request, send_file
from pydub import AudioSegment
from werkzeug.utils import secure_filename
import subprocess

app = Flask(__name__)

# Initialize the Whisper model
model = whisper.load_model("base")  # You can choose 'small', 'medium', or 'large' models

# Allowed audio formats
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'm4a', 'caf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Convert audio file to wav if necessary
def convert_audio_to_wav(audio_file):
    # If it's already WAV, just return the file
    if audio_file.lower().endswith(".wav"):
        return audio_file
    
    # For other audio formats like MP3, M4A, CAF, convert them to WAV using ffmpeg
    wav_file = "temp_audio.wav"
    if audio_file.lower().endswith(".caf"):
        # If the file is a .caf file, we use ffmpeg to convert it to .wav
        subprocess.run(["ffmpeg", "-i", audio_file, wav_file])
    else:
        audio = AudioSegment.from_file(audio_file)
        audio.export(wav_file, format="wav")
    return wav_file

# Generate SRT from transcription
def generate_srt(transcription):
    srt = ""
    segment_index = 1
    for segment in transcription['segments']:
        start_time = segment['start']
        end_time = segment['end']
        text = segment['text']

        # Format time as SRT requires (HH:MM:SS,MMM --> HH:MM:SS,MMM)
        start_time_str = f"{int(start_time // 3600):02}:{int((start_time % 3600) // 60):02}:{int(start_time % 60):02},{int((start_time * 1000) % 1000):03}"
        end_time_str = f"{int(end_time // 3600):02}:{int((end_time % 3600) // 60):02}:{int(end_time % 60):02},{int((end_time * 1000) % 1000):03}"

        srt += f"{segment_index}\n{start_time_str} --> {end_time_str}\n{text}\n\n"
        segment_index += 1
    
    return srt

# Route to upload audio and get the SRT output
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "No file part", 400
    
    file = request.files['file']
    if file.filename == '':
        return "No selected file", 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join('uploads', filename)
        file.save(filepath)

        # Convert audio to wav if it's not already
        wav_filepath = convert_audio_to_wav(filepath)
        
        # Perform transcription using Whisper
        transcription = model.transcribe(wav_filepath)

        # Generate SRT from the transcription
        srt_output = generate_srt(transcription)

        # Save SRT file
        srt_filepath = "output.srt"
        with open(srt_filepath, 'w') as f:
            f.write(srt_output)
        
        # Clean up temporary wav file
        os.remove(wav_filepath)

        # Return the generated SRT file as response
        return send_file(srt_filepath, as_attachment=True)

    return "Invalid file format. Only MP3, WAV, M4A, and CAF are supported.", 400

if __name__ == '__main__':
    # Create uploads directory if it doesn't exist
    if not os.path.exists('uploads'):
        os.makedirs('uploads')

    # Run Flask app
    app.run(debug=True, host='0.0.0.0', port=5000)
