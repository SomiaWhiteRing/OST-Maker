# config.py
import os
import tempfile

# --- 核心配置 ---
# 在这里调整最大同时导出的任务数量
MAX_CONCURRENT_EXPORTS = 8

# --- 文件系统路径 ---
WORK_DIR = os.path.dirname(os.path.abspath(__file__))
MUSIC_DIR = os.path.join(WORK_DIR, "Music")
MOVIE_DIR = os.path.join(WORK_DIR, "Movie")
SOUNDFONT_PATH = os.path.join(WORK_DIR, "soundfont.sf2")

# --- 临时文件路径 ---
TEMP_DIR = os.path.join(tempfile.gettempdir(), "game_music_video_maker")
os.makedirs(TEMP_DIR, exist_ok=True)