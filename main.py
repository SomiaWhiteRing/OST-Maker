# main.py
import sys
import os
import shutil
import atexit
from multiprocessing import Pool
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QObject, pyqtSignal

from config import MAX_CONCURRENT_EXPORTS, MUSIC_DIR, MOVIE_DIR, SOUNDFONT_PATH, TEMP_DIR
from workers import run_export_process
from ui_components import MainWindow

class ExportManager(QObject):
    _instance = None
    
    status_update = pyqtSignal(str, int)
    task_submitted = pyqtSignal(str)
    task_finished = pyqtSignal(str)
    task_failed = pyqtSignal(str, str)

    @staticmethod
    def get_instance():
        if ExportManager._instance is None:
            ExportManager._instance = ExportManager()
        return ExportManager._instance

    def __init__(self):
        if ExportManager._instance is not None:
            raise Exception("This class is a singleton!")
        else:
            super().__init__()
            self.pool = Pool(processes=MAX_CONCURRENT_EXPORTS)
            self.active_tasks = set()
            ExportManager._instance = self

    def submit_task(self, music_path, image_path):
        if music_path in self.active_tasks:
            return False

        self.active_tasks.add(music_path)
        base_name, _ = os.path.splitext(os.path.basename(music_path))
        project_name = os.path.basename(os.path.dirname(music_path))
        output_path = os.path.join(MOVIE_DIR, project_name, f"{base_name}.mp4")

        self.status_update.emit(f"任务已添加: {base_name}.mp4", 3000)
        self.task_submitted.emit(music_path)

        self.pool.apply_async(
            run_export_process,
            args=(music_path, image_path, output_path),
            callback=self._on_task_completed,
            error_callback=lambda e: self._on_task_failed(music_path, e)
        )
        return True

    def _on_task_completed(self, result_path):
        """
        任务移除修复: 重写此回调函数以正确地反向查找并移除任务。
        """
        try:
            # 1. 从结果路径分解出关键信息
            output_filename = os.path.basename(result_path)
            project_name = os.path.basename(os.path.dirname(result_path))
            base_name, _ = os.path.splitext(output_filename)

            # 2. 构造所有可能的原始音乐文件路径
            possible_extensions = ['.mid', '.mp3', '.wav']
            original_music_path = None
            for ext in possible_extensions:
                path_to_check = os.path.join(MUSIC_DIR, project_name, f"{base_name}{ext}")
                # 3. 检查哪个路径存在于我们的活跃任务集合中
                if path_to_check in self.active_tasks:
                    original_music_path = path_to_check
                    break
            
            # 4. 如果找到了匹配的路径，就移除它
            if original_music_path:
                self.active_tasks.remove(original_music_path)
                self.status_update.emit(f"制作完成: {output_filename}", 5000)
                self.task_finished.emit(result_path)
            else:
                # 这是一个异常情况，可能意味着任务状态不一致，但我们还是要通知UI
                # 只是可能无法从队列中正确移除
                print(f"警告: 无法在活跃任务中找到与 {result_path} 匹配的源文件。")
                self.task_finished.emit(result_path)

        except Exception as e:
            print(f"在处理任务完成回调时发生错误: {e}")
            # 即使回调出错，也尝试通知UI刷新
            self.task_finished.emit(result_path)


    def _on_task_failed(self, music_path, error):
        if music_path in self.active_tasks:
            self.active_tasks.remove(music_path)
        
        error_message = str(error)
        self.status_update.emit(f"制作失败: {os.path.basename(music_path)}", 5000)
        self.task_failed.emit(music_path, error_message)

    def shutdown(self):
        print("正在关闭进程池...")
        self.pool.close()
        self.pool.join()
        print("进程池已关闭。")

def check_dependencies():
    errors = []
    if not os.path.exists(MUSIC_DIR): os.makedirs(MUSIC_DIR); errors.append("'Music' 文件夹未找到，已自动创建。")
    if not os.path.exists(MOVIE_DIR): os.makedirs(MOVIE_DIR)
    if not os.path.exists(SOUNDFONT_PATH): errors.append("'soundfont.sf2' 未找到！")
    if not shutil.which("ffmpeg"): errors.append("'ffmpeg' 未找到，请安装并添加到系统PATH。")
    if not shutil.which("fluidsynth"): errors.append("'fluidsynth' 未找到，请安装并添加到系统PATH。")
    return errors

def cleanup_temp_files():
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
        print("临时文件已清理。")

if __name__ == '__main__':
    from multiprocessing import set_start_method
    try: set_start_method('spawn')
    except RuntimeError: pass

    app = QApplication(sys.argv)
    
    dep_errors = check_dependencies()
    if dep_errors:
        QMessageBox.critical(None, "依赖缺失", "\n- ".join(dep_errors))
        sys.exit(1)

    atexit.register(cleanup_temp_files)
    export_manager = ExportManager.get_instance()
    atexit.register(export_manager.shutdown)

    main_win = MainWindow(export_manager)
    export_manager.status_update.connect(main_win.statusBar().showMessage)
    
    main_win.show()
    sys.exit(app.exec())