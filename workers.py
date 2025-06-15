# workers.py
import os
import shutil
import uuid
import subprocess
from PyQt6.QtCore import QObject, pyqtSignal
from config import SOUNDFONT_PATH, TEMP_DIR

def _render_midi_to_wav_internal(input_midi_path, output_wav_path):
    """
    内部核心函数：将一个MIDI文件渲染成WAV。
    使用安全的临时文件副本策略来处理特殊字符路径。
    """
    safe_input_midi_path = None
    safe_output_wav_path = None
    try:
        # 1. 为输入MIDI创建安全的临时副本
        safe_input_midi_path = os.path.join(TEMP_DIR, f"render_in_{uuid.uuid4()}.mid")
        shutil.copy(input_midi_path, safe_input_midi_path)
        
        # 2. 为输出WAV创建安全的临时路径
        safe_output_wav_path = os.path.join(TEMP_DIR, f"render_out_{uuid.uuid4()}.wav")

        command = [
            'fluidsynth', '-ni', SOUNDFONT_PATH, safe_input_midi_path,
            '-F', safe_output_wav_path, '-r', '44100'
        ]
        
        result = subprocess.run(
            command, capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW, check=False
        )

        if result.returncode != 0 or not os.path.exists(safe_output_wav_path):
            error_message = result.stderr.decode('utf-8', 'ignore')
            raise RuntimeError(f"FluidSynth渲染失败，无法创建输出文件。\n错误信息: {error_message}")
        
        # 3. 将安全的临时输出文件重命名为最终的缓存文件名
        if os.path.exists(output_wav_path):
            os.remove(output_wav_path)
        os.rename(safe_output_wav_path, output_wav_path)

    finally:
        # 4. 清理所有临时文件
        if safe_input_midi_path and os.path.exists(safe_input_midi_path):
            os.remove(safe_input_midi_path)
        if safe_output_wav_path and os.path.exists(safe_output_wav_path):
            os.remove(safe_output_wav_path)

class MidiRenderWorker(QObject):
    """用于【单个文件】点击播放时的实时渲染。"""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, midi_path):
        super().__init__()
        self.midi_path = midi_path

    def run(self):
        try:
            final_cached_wav_path = os.path.join(TEMP_DIR, f"{os.path.basename(self.midi_path)}.wav")
            _render_midi_to_wav_internal(self.midi_path, final_cached_wav_path)
            self.finished.emit(final_cached_wav_path)
        except Exception as e:
            self.error.emit(str(e))

class MidiPreRenderWorker(QObject):
    """用于【项目打开时】批量预渲染所有未缓存的MIDI文件。"""
    progress_update = pyqtSignal(str, int, int) # filename, current, total
    finished = pyqtSignal()
    
    def __init__(self, midi_files_to_render):
        super().__init__()
        self.midi_files = midi_files_to_render

    def run(self):
        total = len(self.midi_files)
        for i, midi_path in enumerate(self.midi_files):
            try:
                base_name = os.path.basename(midi_path)
                self.progress_update.emit(base_name, i + 1, total)
                final_cached_wav_path = os.path.join(TEMP_DIR, f"{base_name}.wav")
                _render_midi_to_wav_internal(midi_path, final_cached_wav_path)
            except Exception as e:
                # 预渲染失败不应中断整个流程，只在控制台打印错误
                print(f"预渲染文件失败 '{midi_path}': {e}")
        self.finished.emit()


def run_export_process(music_path, image_path, output_path):
    """用于视频导出的进程池函数。"""
    safe_input_midi_path = None
    temp_wav_path = None
    try:
        is_midi = music_path.lower().endswith('.mid')
        
        if is_midi:
            safe_input_midi_path = os.path.join(TEMP_DIR, f"export_in_{uuid.uuid4()}.mid")
            shutil.copy(music_path, safe_input_midi_path)
            temp_wav_path = os.path.join(os.path.dirname(output_path), f"_temp_export_{uuid.uuid4()}.wav")
            
            _render_midi_to_wav_internal(safe_input_midi_path, temp_wav_path)
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
            command, capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW, check=False
        )
        if result.returncode != 0:
            error_message = result.stderr.decode('utf-8', 'ignore')
            raise RuntimeError(f"FFmpeg合成失败: {error_message}")

        return output_path
    finally:
        if safe_input_midi_path and os.path.exists(safe_input_midi_path):
            os.remove(safe_input_midi_path)
        if temp_wav_path and os.path.exists(temp_wav_path):
            os.remove(temp_wav_path)