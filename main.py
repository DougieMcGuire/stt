from flask import Flask, request, render_template, send_file
import os
import speech_recognition as sr
from pydub import AudioSegment
import tempfile
import datetime
import uuid

app = Flask(__name__)

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def convert_time_to_srt_format(seconds):
    """Convert seconds to SRT time format (HH:MM:SS,mmm)"""
    td = datetime.timedelta(seconds=seconds)
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = round(td.microseconds / 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

def audio_to_srt(audio_path):
    """Convert audio file to SRT format"""
    # Convert audio to a format that speech_recognition can handle
    audio = None
    
    # Convert CAF or other formats to WAV using pydub
    if audio_path.lower().endswith('.caf'):
        audio = AudioSegment.from_file(audio_path, format="caf")
    else:
        # Handle other formats
        file_extension = os.path.splitext(audio_path)[1][1:].lower()
        audio = AudioSegment.from_file(audio_path, format=file_extension)
    
    # Create a temporary WAV file
    temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp_wav_path = temp_wav.name
    temp_wav.close()
    
    audio.export(temp_wav_path, format="wav")
    
    # Initialize recognizer
    r = sr.Recognizer()
    
    # Use recognizer to split audio into chunks and transcribe
    with sr.AudioFile(temp_wav_path) as source:
        # Adjust for ambient noise
        r.adjust_for_ambient_noise(source)
        
        # Get audio duration
        audio_duration = len(audio) / 1000  # Convert ms to seconds
        
        # Create chunks (5 seconds each)
        chunk_size = 5  # seconds
        srt_entries = []
        
        for i in range(0, int(audio_duration), chunk_size):
            end_time = min(i + chunk_size, audio_duration)
            
            # Get audio segment
            audio_data = r.record(source, duration=min(chunk_size, end_time - i))
            
            try:
                # Transcribe audio
                text = r.recognize_google(audio_data)
                
                if text:
                    # Add entry to SRT
                    entry_id = len(srt_entries) + 1
                    start_time_str = convert_time_to_srt_format(i)
                    end_time_str = convert_time_to_srt_format(end_time)
                    
                    srt_entries.append(f"{entry_id}\n{start_time_str} --> {end_time_str}\n{text}\n")
            except sr.UnknownValueError:
                # Speech not understood
                pass
            except sr.RequestError as e:
                # API error
                print(f"API error: {e}")
    
    # Clean up temporary file
    os.unlink(temp_wav_path)
    
    # Combine all entries into SRT format
    srt_content = "\n".join(srt_entries)
    
    # Save SRT content to file
    srt_path = os.path.splitext(audio_path)[0] + ".srt"
    with open(srt_path, "w", encoding="utf-8") as srt_file:
        srt_file.write(srt_content)
    
    return srt_path

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return render_template('index.html', error='No file part')
        
        file = request.files['file']
        
        if file.filename == '':
            return render_template('index.html', error='No selected file')
        
        if file:
            # Generate unique filename
            original_filename = file.filename
            file_extension = os.path.splitext(original_filename)[1]
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
            
            # Save the uploaded file
            file.save(file_path)
            
            try:
                # Convert audio to SRT
                srt_path = audio_to_srt(file_path)
                
                # Send the SRT file to user
                return send_file(
                    srt_path,
                    as_attachment=True,
                    download_name=os.path.basename(srt_path),
                    mimetype='text/plain'
                )
            except Exception as e:
                return render_template('index.html', error=f"Error processing audio: {str(e)}")
    
    return render_template('index.html')

@app.route('/health', methods=['GET'])
def health_check():
    return "Service is running"

# Simple HTML template
@app.route('/template')
def template():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Audio to SRT Converter</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
            }
            .container {
                border: 1px solid #ddd;
                padding: 20px;
                border-radius: 5px;
            }
            .error {
                color: red;
                margin-bottom: 15px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Audio to SRT Converter</h1>
            <p>Upload an audio file (.mp3, .wav, .caf, etc.) to convert it to SRT subtitle format.</p>
            {% if error %}
            <div class="error">{{ error }}</div>
            {% endif %}
            <form method="post" enctype="multipart/form-data">
                <input type="file" name="file" accept="audio/*">
                <button type="submit">Convert to SRT</button>
            </form>
        </div>
    </body>
    </html>
    """

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
