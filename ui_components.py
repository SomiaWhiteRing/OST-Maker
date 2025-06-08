# ui_components.py
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QLabel,
    QPushButton, QSlider, QFileDialog, QMessageBox, QMainWindow, QStatusBar,
    QSplitter
)
from PyQt6.QtGui import QPixmap, QIcon, QGuiApplication
from PyQt6.QtCore import Qt, QUrl, QThread, pyqtSignal
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

from config import MUSIC_DIR, MOVIE_DIR, TEMP_DIR
from workers import MidiRenderWorker

class ClickableSlider(QSlider):
    """一个可以响应鼠标点击事件的QSlider子类。"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            value = self.minimum() + (self.maximum() - self.minimum()) * event.pos().x() / self.width()
            self.setValue(int(value))
            self.sliderMoved.emit(int(value))
        super().mousePressEvent(event)

class VideoMakerWindow(QWidget):
    """视频制作界面，现在只负责UI和用户交互。"""
    statusUpdate = pyqtSignal(str, int)

    def __init__(self, project_name, export_manager, parent=None):
        super().__init__(parent)
        self.project_name = project_name
        self.export_manager = export_manager
        
        self.project_music_path = os.path.join(MUSIC_DIR, self.project_name)
        self.project_movie_path = os.path.join(MOVIE_DIR, self.project_name)
        
        self.current_music_path = None
        self.pixmap = None
        self.is_midi_rendering = False
        self.total_duration = 0
        self.currently_playing_name = "未选择音乐"

        self.init_ui()
        self.init_player()
        
        # 连接到导出管理器的信号
        self.export_manager.task_submitted.connect(self._on_task_submitted)
        self.export_manager.task_finished.connect(self._on_task_finished)
        self.export_manager.task_failed.connect(self._on_task_failed)

        # 初始时刷新音乐列表和任务队列
        self.refresh_music_list()
        self.refresh_task_queue()

    def _on_task_submitted(self, music_path):
        """当一个新任务被提交时，更新队列显示。"""
        task_name = os.path.basename(music_path)
        # 仅当任务属于当前项目时才添加到队列
        if self.project_music_path in os.path.normpath(music_path):
            self.task_queue_widget.addItem(f"⏳ {task_name}")

    def _on_task_finished(self, output_path):
        """当任何一个导出任务完成时，更新列表和队列。"""
        if self.project_movie_path in os.path.normpath(output_path):
            self.refresh_music_list()
            self.refresh_task_queue()

    def _on_task_failed(self, music_file, error_message):
        """当任何一个导出任务失败时，更新队列并显示错误。"""
        if self.project_music_path in os.path.normpath(music_file):
            self.refresh_task_queue()
            QMessageBox.warning(self, "导出失败", f"制作视频 '{os.path.basename(music_file)}' 时出错:\n\n{error_message}")

    def refresh_task_queue(self):
        """用当前活跃的任务刷新队列显示。"""
        self.task_queue_widget.clear()
        for task_path in self.export_manager.active_tasks:
            if self.project_music_path in os.path.normpath(task_path):
                self.task_queue_widget.addItem(f"⏳ {os.path.basename(task_path)}")
    
    def start_export(self):
        if not self.current_music_path:
            QMessageBox.warning(self, "缺少信息", "请先在左侧选择一首音乐。")
            return
        if not self.current_image_path:
            QMessageBox.warning(self, "缺少信息", "请先选择一张封面图片。")
            return
            
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()

        success = self.export_manager.submit_task(
            music_path=self.current_music_path,
            image_path=self.current_image_path
        )

        if not success:
            QMessageBox.information(self, "任务已存在", "该音乐的导出任务已经在队列中或正在进行。")
    
    def init_ui(self):
        self.setWindowTitle(f"项目: {self.project_name}")
        self.setGeometry(200, 200, 1000, 600)
        self.setAcceptDrops(True)

        main_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # ... 左侧和右侧面板UI无改动 ...
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("待处理音乐列表:"))
        self.music_list_widget = QListWidget()
        self.music_list_widget.itemClicked.connect(self.on_music_selected)
        self.music_list_widget.itemDoubleClicked.connect(self.on_music_double_clicked)
        left_layout.addWidget(self.music_list_widget)
        
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        title_label = QLabel("封面图片:")
        title_label.setFixedHeight(20)
        self.image_label = QLabel("将图片拖到此处\n或点击下方按钮选择\n或按Ctrl+V粘贴")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(400, 225)
        self.image_label.setStyleSheet("border: 2px dashed #aaa; color: #888;")
        image_buttons_layout = QHBoxLayout()
        select_image_btn = QPushButton("选择图片...")
        select_image_btn.clicked.connect(self.select_image_file)
        remove_image_btn = QPushButton("移除图片")
        remove_image_btn.clicked.connect(self.remove_image)
        image_buttons_layout.addWidget(select_image_btn)
        image_buttons_layout.addWidget(remove_image_btn)
        right_layout.addWidget(title_label)
        right_layout.addWidget(self.image_label, 1)
        right_layout.addLayout(image_buttons_layout)
        
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 700])
        main_layout.addWidget(splitter)
        
        # --- 下方面板UI修改 ---
        bottom_panel = QWidget()
        bottom_panel.setMaximumHeight(80) # 稍微增加高度以容纳队列
        bottom_layout = QHBoxLayout(bottom_panel)

        # 左侧播放器区域
        player_group = QWidget()
        player_layout = QVBoxLayout(player_group)
        player_layout.setContentsMargins(0,0,0,0)

        self.music_name_label = QLabel(self.currently_playing_name)
        self.music_name_label.setFixedWidth(350)
        self.music_name_label.setToolTip(self.currently_playing_name)
        player_layout.addWidget(self.music_name_label)
        
        player_controls = QHBoxLayout()
        self.play_pause_btn = QPushButton("▶")
        self.play_pause_btn.setFixedWidth(40)
        self.play_pause_btn.clicked.connect(self.toggle_play_pause)
        self.progress_slider = ClickableSlider(Qt.Orientation.Horizontal)
        self.progress_slider.sliderMoved.connect(self.set_player_position)
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setFixedWidth(100)
        player_controls.addWidget(self.play_pause_btn)
        player_controls.addWidget(self.progress_slider)
        player_controls.addWidget(self.time_label)
        player_layout.addLayout(player_controls)

        bottom_layout.addWidget(player_group)
        bottom_layout.addStretch()

        # 中间导出队列区域
        queue_group = QWidget()
        queue_layout = QVBoxLayout(queue_group)
        queue_layout.setContentsMargins(10, 0, 10, 0)
        self.task_queue_widget = QListWidget()
        # 样式调整使其紧凑
        self.task_queue_widget.setStyleSheet("QListWidget { font-size: 11px; }")
        self.task_queue_widget.setMaximumHeight(60) # 限制高度，大约3行
        self.task_queue_widget.setFixedWidth(250)
        queue_layout.addWidget(self.task_queue_widget)
        bottom_layout.addWidget(queue_group)

        # 右侧导出按钮
        self.export_btn = QPushButton("导出视频")
        self.export_btn.setIcon(QIcon.fromTheme("document-save"))
        self.export_btn.setMinimumSize(120, 40)
        self.export_btn.clicked.connect(self.start_export)
        bottom_layout.addWidget(self.export_btn)
        
        main_layout.addWidget(bottom_panel)

    # ... (其余所有方法保持原样) ...
    def init_player(self):
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.positionChanged.connect(self.update_slider_and_time)
        self.player.durationChanged.connect(self.update_slider_range_and_time)
        self.player.playbackStateChanged.connect(self.update_button_state)

    def refresh_music_list(self):
        self.music_list_widget.clear()
        if not os.path.exists(self.project_music_path): return
        os.makedirs(self.project_movie_path, exist_ok=True)
        music_files = [f for f in os.listdir(self.project_music_path) if f.lower().endswith(('.wav', '.mp3', '.mid'))]
        for music_file in music_files:
            base_name, _ = os.path.splitext(music_file)
            video_file_path = os.path.join(self.project_movie_path, f"{base_name}.mp4")
            if not os.path.exists(video_file_path):
                self.music_list_widget.addItem(music_file)

    def format_time(self, ms):
        if ms is None or ms < 0: return "00:00"
        total_seconds = int(ms / 1000)
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    def reset_player_ui(self):
        self.progress_slider.setValue(0)
        self.update_slider_and_time(0)

    def on_music_selected(self, item):
        self.current_music_path = os.path.join(self.project_music_path, item.text())
    
    def on_music_double_clicked(self, item):
        self.on_music_selected(item)
        self.play_music()

    def play_music(self):
        if not self.current_music_path or self.is_midi_rendering: return
        self.currently_playing_name = os.path.basename(self.current_music_path)
        self.music_name_label.setText(self.currently_playing_name)
        self.music_name_label.setToolTip(self.currently_playing_name)
        self.player.stop()
        self.total_duration = 0
        self.reset_player_ui()
        if self.current_music_path.lower().endswith(('.wav', '.mp3')):
            source = QUrl.fromLocalFile(self.current_music_path)
            self.player.setSource(source)
            self.player.play()
        elif self.current_music_path.lower().endswith('.mid'):
            self.is_midi_rendering = True
            self.statusUpdate.emit("正在渲染MIDI以供预览...", 2000)
            self.play_pause_btn.setEnabled(False)
            self.render_thread = QThread()
            self.render_worker = MidiRenderWorker(self.current_music_path)
            self.render_worker.moveToThread(self.render_thread)
            self.render_thread.started.connect(self.render_worker.run)
            self.render_worker.finished.connect(self.on_midi_rendered)
            self.render_worker.error.connect(self.on_midi_render_error)
            self.render_thread.start()

    def on_midi_rendered(self, wav_path):
        source = QUrl.fromLocalFile(wav_path)
        self.player.setSource(source)
        self.player.play()
        self.is_midi_rendering = False
        self.play_pause_btn.setEnabled(True)
        self.statusUpdate.emit("", 1)
        self.render_thread.quit()
        self.render_thread.wait()

    def on_midi_render_error(self, error_msg):
        QMessageBox.critical(self, "MIDI渲染失败", f"无法渲染MIDI文件进行预览:\n{error_msg}")
        self.is_midi_rendering = False
        self.play_pause_btn.setEnabled(True)
        self.statusUpdate.emit("", 1)
        self.render_thread.quit()
        self.render_thread.wait()

    def toggle_play_pause(self):
        if self.player.source().isEmpty() and self.current_music_path:
            self.play_music()
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def update_button_state(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState: self.play_pause_btn.setText("❚❚")
        else: self.play_pause_btn.setText("▶")
        if state == QMediaPlayer.PlaybackState.StoppedState: self.update_slider_and_time(0)

    def update_slider_and_time(self, position):
        self.progress_slider.blockSignals(True)
        self.progress_slider.setValue(position)
        self.progress_slider.blockSignals(False)
        current_time_str = self.format_time(position)
        total_time_str = self.format_time(self.total_duration)
        self.time_label.setText(f"{current_time_str} / {total_time_str}")

    def update_slider_range_and_time(self, duration):
        self.progress_slider.setRange(0, duration)
        self.total_duration = duration
        current_time_str = self.format_time(self.player.position())
        total_time_str = self.format_time(duration)
        self.time_label.setText(f"{current_time_str} / {total_time_str}")
    
    def set_player_position(self, position):
        self.player.setPosition(position)
    
    def set_image(self, image_path):
        self.current_image_path = image_path
        self.pixmap = QPixmap(image_path)
        if self.pixmap.isNull():
            self.remove_image()
            return
        self.update_image_display()

    def update_image_display(self):
        if self.pixmap and not self.pixmap.isNull():
            scaled_pixmap = self.pixmap.scaled(self.image_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.image_label.setPixmap(scaled_pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_image_display()

    def remove_image(self):
        self.current_image_path = None
        self.pixmap = None
        self.image_label.clear()
        self.image_label.setText("将图片拖到此处\n或点击下方按钮选择\n或按Ctrl+V粘贴")

    def select_image_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择一张图片", "", "图片文件 (*.png *.jpg *.jpeg *.bmp)")
        if file_path: self.set_image(file_path)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            url = event.mimeData().urls()[0].toLocalFile()
            if url.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')): event.acceptProposedAction()

    def dropEvent(self, event):
        url = event.mimeData().urls()[0].toLocalFile()
        self.set_image(url)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_V and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            clipboard = QGuiApplication.clipboard()
            image = clipboard.image()
            if not image.isNull():
                temp_path = os.path.join(TEMP_DIR, "_clipboard_temp.png")
                image.save(temp_path, "PNG")
                self.set_image(temp_path)
        else: super().keyPressEvent(event)
    
    def closeEvent(self, event):
        self.player.stop()
        super().closeEvent(event)

class MainWindow(QMainWindow):
    # ... (此类无需修改) ...
    def __init__(self, export_manager):
        super().__init__()
        self.export_manager = export_manager
        self.setWindowTitle("游戏音乐视频制作工具")
        self.setGeometry(300, 300, 400, 500)
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        layout = QVBoxLayout(self.central_widget)
        layout.addWidget(QLabel("<h2>请选择一个项目:</h2>"))
        self.project_list = QListWidget()
        self.project_list.itemDoubleClicked.connect(self.open_project)
        layout.addWidget(self.project_list)
        self.setStatusBar(QStatusBar())
        self.load_projects()
        self.video_maker_windows = {}

    def load_projects(self):
        self.project_list.clear()
        if not os.path.exists(MUSIC_DIR): return
        projects = [d for d in os.listdir(MUSIC_DIR) if os.path.isdir(os.path.join(MUSIC_DIR, d))]
        if not projects:
            self.project_list.addItem("Music文件夹中没有找到项目文件夹")
            self.project_list.setEnabled(False)
        else:
            self.project_list.addItems(projects)
            self.statusBar().showMessage(f"发现 {len(projects)} 个项目。双击打开。")

    def open_project(self, item):
        project_name = item.text()
        if project_name in self.video_maker_windows and self.video_maker_windows[project_name].isVisible():
            self.video_maker_windows[project_name].activateWindow()
            return
        video_maker_window = VideoMakerWindow(project_name, self.export_manager, self)
        video_maker_window.statusUpdate.connect(self.statusBar().showMessage)
        video_maker_window.setWindowFlag(Qt.WindowType.Window)
        video_maker_window.show()
        self.video_maker_windows[project_name] = video_maker_window