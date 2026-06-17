from TTS.api import TTS
import os
import sounddevice as sd
import soundfile as sf

class TextToSpeech:
    def __init__(self):
        self.tts = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC", progress_bar=False, gpu=False)
        self.output_path = "voice_output.wav"

    def speak(self, text):
        """Generates and plays speech from text."""
        print("[TTS] Generating voice...")
        self.tts.tts_to_file(text=text, file_path=self.output_path)

        # Play audio
        print("[TTS] Playing audio...")
        data, samplerate = sf.read(self.output_path)
        sd.play(data, samplerate)
        sd.wait()

if __name__ == "__main__":
    tts = TextToSpeech()
    tts.speak("Hello! I am your assistant speaking from Coqui TTS.")