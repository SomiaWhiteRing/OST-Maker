# workers.py
import os
import subprocess
from PyQt6.QtCore import QObject, pyqtSignal
from config import SOUNDFONT_PATH, TEMP_DIR

class MidiRenderWorker(QObject):
    """使用QThread在后台渲染MIDI以供预览，避免UI冻结。"""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, midi_path):
        super().__init__()
        self.midi_path = midi_path

    def run(self):
        try:
            base_name = os.path.basename(self.midi_path)
            temp_wav_path = os.path.join(TEMP_DIR, f"{base_name}.wav")
            
            command = [
                'fluidsynth', '-ni', SOUNDFONT_PATH, self.midi_path,
                '-F', temp_wav_path, '-r', '44100'
            ]
            # 编码修复: 指定encoding和errors
            result = subprocess.run(
                command, capture_output=True, text=True, 
                encoding='utf-8', errors='ignore',
                creationflags=subprocess.CREATE_NO_WINDOW, check=False
            )
            if result.returncode != 0:
                raise RuntimeError(f"FluidSynth渲染失败: {result.stderr}")

            self.finished.emit(temp_wav_path)
        except Exception as e:
            self.error.emit(str(e))

def run_export_process(music_path, image_path, output_path):
    """
    一个独立的函数，用于在进程池中执行视频导出。
    """
    try:
        is_midi = music_path.lower().endswith('.mid')
        temp_wav_path = None
        
        if is_midi:
            temp_wav_path = os.path.join(os.path.dirname(output_path), f"_temp_export_{os.path.basename(music_path)}.wav")
            command = [
                'fluidsynth', '-ni', SOUNDFONT_PATH, music_path,
                '-F', temp_wav_path, '-r', '44100'
            ]
            result = subprocess.run(
                command, capture_output=True, text=True, 
                encoding='utf-8', errors='ignore',
                creationflags=subprocess.CREATE_NO_WINDOW, check=False
            )
            if result.returncode != 0:
                raise RuntimeError(f"FluidSynth渲染失败: {result.stderr}")
            audio_input_path = temp_wav_path
        else:
            audio_input_path = music_path

        command = [
            'ffmpeg', '-y', '-loop', '1', '-i', image_path,
            '-i', audio_input_path, '-c:v', 'libx264', '-tune', 'stillimage',
            '-c:a', 'aac', '-b:a', '192k', '-pix_fmt', 'yuv420p', '-shortest',
            output_path
        ]
        result = subprocess.run(
            command, capture_output=True, text=True, 
            encoding='utf-8', errors='ignore',
            creationflags=subprocess.CREATE_NO_WINDOW, check=False
        )
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg合成失败: {result.stderr}")

        return output_path
    finally:
        if temp_wav_path and os.path.exists(temp_wav_path):
            os.remove(temp_wav_path)