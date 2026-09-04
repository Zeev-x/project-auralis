import ctypes
import os
import random
import sys
from io import BytesIO

from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import QEvent, QSize, Qt, QTimer, QUrl
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtSvg import QSvgRenderer
from mutagen.id3 import ID3
from mutagen.mp3 import MP3


class AccentPolicy(ctypes.Structure):
    _fields_ = [
        ("accent_state", ctypes.c_int),
        ("flags", ctypes.c_int),
        ("gradient_color", ctypes.c_uint32),
        ("animation_id", ctypes.c_int),
    ]


class WindowCompositionAttributeData(ctypes.Structure):
    _fields_ = [
        ("attribute", ctypes.c_int),
        ("data", ctypes.c_void_p),
        ("data_size", ctypes.c_size_t),
    ]


class MusicPlayer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Project Auralis | MP3 Player")
        self.setMinimumSize(900, 620)
        self.resize(1080, 700)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAutoFillBackground(False)
        self.setWindowIcon(self.app_icon())
        self.setStyleSheet(self.app_style())
        self._drag_position = None
        self._switching_window_mode = False

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(18)

        self.title_bar = QFrame()
        self.title_bar.setObjectName("titleBar")
        header = QHBoxLayout(self.title_bar)
        header.setContentsMargins(12, 8, 12, 8)
        brand = QVBoxLayout()
        brand.setSpacing(2)
        title = QLabel("PROJECT AURALIS")
        title.setObjectName("brandTitle")
        subtitle = QLabel("YOUR PERSONAL SOUNDSPACE")
        subtitle.setObjectName("eyebrow")
        brand.addWidget(title)
        brand.addWidget(subtitle)
        header.addLayout(brand)
        header.addStretch()
        self.scan_btn = QPushButton()
        self.scan_btn.setObjectName("primaryButton")
        self.scan_btn.setIcon(self.icon("folder-add.svg"))
        self.scan_btn.setIconSize(QSize(21, 21))
        self.scan_btn.setToolTip("Tambah folder musik")
        self.scan_btn.clicked.connect(self.scan_folder)
        header.addWidget(self.scan_btn)
        header.addSpacing(14)
        self.brand_widgets = (title, subtitle)
        self.minimize_btn = QPushButton("−")
        self.minimize_btn.setObjectName("windowButton")
        self.minimize_btn.setToolTip("Minimize window")
        self.minimize_btn.clicked.connect(self.showMinimized)
        header.addWidget(self.minimize_btn)
        self.maximize_btn = QPushButton()
        self.maximize_btn.setObjectName("windowButton")
        self.maximize_btn.setIcon(self.icon("maximize.svg"))
        self.maximize_btn.setIconSize(QSize(14, 14))
        self.maximize_btn.setToolTip("Maximize window")
        self.maximize_btn.clicked.connect(self.toggle_maximize)
        header.addWidget(self.maximize_btn)
        self.close_btn = QPushButton()
        self.close_btn.setObjectName("windowButton")
        self.close_btn.setIcon(self.icon("close.svg"))
        self.close_btn.setIconSize(QSize(15, 15))
        self.close_btn.setToolTip("Close")
        self.close_btn.clicked.connect(self.close)
        header.addWidget(self.close_btn)
        root.addWidget(self.title_bar)

        content = QHBoxLayout()
        content.setSpacing(18)

        self.now_playing = QFrame()
        self.now_playing.setObjectName("nowPlaying")
        now_layout = QVBoxLayout(self.now_playing)
        now_layout.setContentsMargins(24, 24, 24, 24)
        now_layout.setSpacing(14)
        self.table = QTableWidget()
        self.table.setColumnCount(1)
        self.table.setHorizontalHeaderLabels(["TRACK"])
        self.table.setColumnWidth(0, 190)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setWordWrap(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setFixedHeight(34)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.verticalHeader().setMinimumSectionSize(38)
        self.table.verticalHeader().setVisible(False)
        self.table.cellDoubleClicked.connect(lambda row, _column: self.start_row(row))
        now_layout.addWidget(self.table)
        content.addWidget(self.now_playing, 3)

        self.details = QFrame()
        self.details.setObjectName("details")
        self.details_layout = QVBoxLayout(self.details)
        self.details_layout.setContentsMargins(24, 24, 24, 24)
        self.details_layout.setSpacing(14)
        self.thumbnail = QLabel("NO COVER")
        self.thumbnail.setObjectName("thumbnail")
        self.thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail.setScaledContents(False)
        self.thumbnail.setMinimumSize(280, 280)
        self.thumbnail.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.details_layout.addWidget(self.thumbnail)
        self.cover_pixmap = self.app_icon().pixmap(QSize(512, 512))
        self.render_thumbnail()
        self.metadata_label = QLabel("Pilih lagu untuk mulai mendengarkan")
        self.metadata_label.setObjectName("metadata")
        self.metadata_label.setWordWrap(True)
        self.details_layout.addWidget(self.metadata_label)
        content.addWidget(self.details, 2)
        root.addLayout(content, 1)

        progress_row = QHBoxLayout()
        self.elapsed_label = QLabel("00:00")
        self.elapsed_label.setObjectName("timeLabel")
        self.progress = QSlider(Qt.Orientation.Horizontal)
        self.progress.setRange(0, 0)
        self.progress.sliderMoved.connect(self.seek_song)
        self.duration_label = QLabel("00:00")
        self.duration_label.setObjectName("timeLabel")
        progress_row.addWidget(self.elapsed_label)
        progress_row.addWidget(self.progress, 1)
        progress_row.addWidget(self.duration_label)
        root.addLayout(progress_row)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        self.prev_btn = QPushButton()
        self.prev_btn.setObjectName("controlButton")
        self.prev_btn.setIcon(self.icon("previous.svg"))
        self.prev_btn.setIconSize(QSize(21, 21))
        self.prev_btn.setToolTip("Previous Song")
        self.prev_btn.clicked.connect(self.prev_song)
        self.play_btn = QPushButton()
        self.play_btn.setObjectName("playButton")
        self.play_btn.setIcon(self.icon("play.svg"))
        self.play_btn.setIconSize(QSize(24, 24))
        self.play_btn.setToolTip("Play or Pause")
        self.play_btn.clicked.connect(self.play_song)
        self.next_btn = QPushButton()
        self.next_btn.setObjectName("controlButton")
        self.next_btn.setIcon(self.icon("next.svg"))
        self.next_btn.setIconSize(QSize(21, 21))
        self.next_btn.setToolTip("Next Song")
        self.next_btn.clicked.connect(self.next_song)
        self.loop_btn = QPushButton()
        self.loop_btn.setObjectName("controlButton")
        self.loop_btn.setIcon(self.icon("repeat.svg"))
        self.loop_btn.setIconSize(QSize(20, 20))
        self.loop_btn.setCheckable(True)
        self.loop_btn.setToolTip("Loop")
        self.loop_btn.clicked.connect(self.toggle_loop)
        self.shuffle_btn = QPushButton()
        self.shuffle_btn.setObjectName("controlButton")
        self.shuffle_btn.setIcon(self.icon("shuffle.svg"))
        self.shuffle_btn.setIconSize(QSize(20, 20))
        self.shuffle_btn.setCheckable(True)
        self.shuffle_btn.setToolTip("Shuffle")
        self.shuffle_btn.clicked.connect(self.toggle_shuffle)
        controls.addStretch()
        controls.addWidget(self.prev_btn)
        controls.addWidget(self.play_btn)
        controls.addWidget(self.next_btn)
        controls.addSpacing(16)
        controls.addWidget(self.loop_btn)
        controls.addWidget(self.shuffle_btn)
        controls.addStretch()
        root.addLayout(controls)
        self.controls = controls
        self.progress_row = progress_row
        self.music_controls = (
            self.prev_btn,
            self.play_btn,
            self.next_btn,
            self.loop_btn,
            self.shuffle_btn,
        )
        self.compact_transport = QWidget()
        compact_transport_layout = QHBoxLayout(self.compact_transport)
        compact_transport_layout.setContentsMargins(0, 0, 0, 0)
        compact_transport_layout.setSpacing(8)
        for button in (self.prev_btn, self.play_btn, self.next_btn):
            controls.removeWidget(button)
            compact_transport_layout.addWidget(button)
        self.compact_transport.setVisible(False)
        self.details_layout.addWidget(self.compact_transport)
        self.set_compact_mode(False)
        self.set_native_mode()

        self.player = QMediaPlayer()
        self.audio = QAudioOutput()
        self.player.setAudioOutput(self.audio)
        self.audio.setVolume(0.75)
        self.player.durationChanged.connect(self.update_duration)
        self.player.positionChanged.connect(self.update_position)
        self.player.playbackStateChanged.connect(self.update_play_button)

        self.songs = []
        self.current_index = -1
        self.loop_mode = 0
        self.shuffle_mode = False
        self.player.mediaStatusChanged.connect(self.handle_end)

    @staticmethod
    def resource_path(*parts):
        bases = [
            getattr(sys, "_MEIPASS", ""),
            os.path.dirname(os.path.abspath(__file__)),
            os.path.dirname(os.path.abspath(sys.executable)),
            os.getcwd(),
        ]
        for base in bases:
            if base:
                candidate = os.path.join(base, *parts)
                if os.path.exists(candidate):
                    return candidate
        return os.path.join(bases[0] or bases[1], *parts)

    @classmethod
    def icon(cls, filename):
        path = cls.resource_path("assets", "icons", filename)
        if filename.lower().endswith(".svg"):
            renderer = QSvgRenderer(path)
            if renderer.isValid():
                pixmap = QPixmap(64, 64)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()
                return QIcon(pixmap)
        return QIcon(path)

    @staticmethod
    def app_icon():
        return QIcon(MusicPlayer.resource_path("icon", "icon.ico"))

    @staticmethod
    def app_style():
        return """
            QWidget { color: #e8f0f2; font-family: 'Segoe UI'; font-size: 13px; }
            MusicPlayer { background: rgba(7, 16, 20, 1); }
            QFrame#nowPlaying, QFrame#details { background: rgba(20, 39, 46, 155);
                border: 1px solid rgba(170, 224, 226, 45); border-radius: 18px; }
            QLabel#brandTitle { color: #dffcff; font-size: 28px; font-weight: 700; letter-spacing: 3px; }
            QLabel#eyebrow { color: #70cfd1; font-size: 10px; letter-spacing: 2px; }
            QLabel#metadata { color: #a9c2c5; font-size: 14px; line-height: 1.4; }
            QLabel#timeLabel { color: #78b8bb; font-family: Consolas; font-size: 11px; }
            QPushButton { background: rgba(30, 58, 65, 175); border: 1px solid #3c6970; border-radius: 8px; color: #cde6e7; padding: 11px 14px; font-size: 11px; font-weight: 600; letter-spacing: 1px; }
            QPushButton:hover { background: #2b6268; border-color: #7edadd; }
            QPushButton#controlButton:checked { background: #78d7d5; border-color: #a0efeb; }
            QPushButton#primaryButton, QPushButton#playButton { background: #78d7d5; color: #092126; border: none; }
            QPushButton#primaryButton:hover, QPushButton#playButton:hover { background: #a0efeb; }
            QPushButton#primaryButton { min-width: 42px; max-width: 42px; font-size: 21px; padding: 6px; }
            QPushButton#windowButton { min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px; border: none; background: rgba(30, 58, 65, 110); padding: 0; font-size: 18px; }
            QPushButton#windowButton:hover { background: rgba(120, 215, 213, 190); color: #092126; }
            QPushButton#windowButton:last-child:hover { background: #d76f76; color: #ffffff; }
            QPushButton#controlButton { min-width: 42px; max-width: 42px; min-height: 42px; max-height: 42px; padding: 4px; font-size: 19px; }
            QPushButton#playButton { min-width: 52px; max-width: 52px; min-height: 52px; max-height: 52px; padding: 4px; font-size: 22px; border-radius: 26px; }
            QTableWidget { background: transparent; border: none; gridline-color: transparent; alternate-background-color: rgba(119, 215, 213, 12); }
            QTableWidget::item { padding: 0 10px; border-bottom: 1px solid rgba(150, 210, 211, 20); }
            QTableWidget::item:selected { background: rgba(104, 205, 204, 85); color: #ffffff; border-radius: 6px; }
            QHeaderView::section { background: transparent; border: none; border-bottom: 1px solid #31545a; color: #70cfd1; padding: 8px 10px; font-size: 10px; letter-spacing: 1px; }
            QSlider::groove:horizontal { height: 4px; background: #29474d; border-radius: 2px; }
            QSlider::sub-page:horizontal { background: #78d7d5; border-radius: 2px; }
            QSlider::handle:horizontal { width: 13px; margin: -5px 0; background: #d7fffb; border-radius: 6px; }
        """

    def apply_acrylic(self):
        if sys.platform != "win32":
            return
        try:
            hwnd = int(self.winId())
            accent_policy = AccentPolicy(3, 1, 0x0016272E, 0)
            composition_data = WindowCompositionAttributeData(
                19,
                ctypes.cast(ctypes.pointer(accent_policy), ctypes.c_void_p),
                ctypes.sizeof(accent_policy),
            )
            set_composition = ctypes.windll.user32.SetWindowCompositionAttribute
            set_composition.argtypes = [ctypes.c_void_p, ctypes.POINTER(WindowCompositionAttributeData)]
            set_composition.restype = ctypes.c_int
            set_composition(hwnd, ctypes.byref(composition_data))
            dark_mode = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 20, ctypes.byref(dark_mode), ctypes.sizeof(dark_mode)
            )
        except (AttributeError, OSError):
            pass

    def clear_acrylic(self):
        if sys.platform != "win32":
            return
        try:
            hwnd = int(self.winId())
            accent_policy = AccentPolicy(0, 0, 0, 0)
            composition_data = WindowCompositionAttributeData(
                19,
                ctypes.cast(ctypes.pointer(accent_policy), ctypes.c_void_p),
                ctypes.sizeof(accent_policy),
            )
            set_composition = ctypes.windll.user32.SetWindowCompositionAttribute
            set_composition.argtypes = [ctypes.c_void_p, ctypes.POINTER(WindowCompositionAttributeData)]
            set_composition.restype = ctypes.c_int
            set_composition(hwnd, ctypes.byref(composition_data))
        except (AttributeError, OSError):
            pass

    def set_native_mode(self):
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.minimize_btn.show()
        self.maximize_btn.show()
        self.close_btn.show()

    def set_frameless_mode(self):
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.minimize_btn.show()
        self.maximize_btn.show()
        self.close_btn.show()
        self.show()

    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
            self.set_compact_mode(True)
            self.clear_acrylic()
        else:
            self.showMaximized()
            self.set_compact_mode(False)
            self.apply_acrylic()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange and not self._switching_window_mode:
            if self.isMaximized():
                self.set_compact_mode(False)
                self.apply_acrylic()
            elif not self.isMinimized():
                self.set_compact_mode(True)
                self.clear_acrylic()

    def start_row(self, row):
        self.current_index = row
        self.play_current()

    def scan_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Pilih Folder Musik")
        if folder:
            self.songs = []
            for root, _, files in os.walk(folder):
                for file in files:
                    if file.lower().endswith(".mp3"):
                        self.songs.append(os.path.join(root, file))
            self.songs.sort(key=str.lower)
            self.table.setRowCount(len(self.songs))
            for i, path in enumerate(self.songs):
                title = os.path.basename(path)
                self.table.setItem(i, 0, QTableWidgetItem(title))

    def play_song(self):
        row = self.table.currentRow()
        if row >= 0:
            self.current_index = row
            state = self.player.playbackState()
            if state == QMediaPlayer.PlaybackState.PlayingState:
                self.player.pause()
            elif state == QMediaPlayer.PlaybackState.PausedState:
                self.player.play()
            else:
                self.play_current()

    def next_song(self):
        if self.songs:
            if self.shuffle_mode:
                self.current_index = random.randint(0, len(self.songs) - 1)
            elif self.current_index < len(self.songs) - 1:
                self.current_index += 1
            else:
                self.current_index = 0
            self.play_current()

    def prev_song(self):
        if not self.songs:
            return
        if self.shuffle_mode:
            self.current_index = random.randint(0, len(self.songs) - 1)
        elif self.current_index > 0:
            self.current_index -= 1
        else:
            self.current_index = len(self.songs) - 1
        self.play_current()

    def play_current(self):
        path = self.songs[self.current_index]
        self.table.selectRow(self.current_index)
        self.player.setSource(QUrl.fromLocalFile(path))
        self.player.play()
        self.show_thumbnail(path)
        self.show_metadata(path)

    def toggle_loop(self):
        self.loop_mode = (self.loop_mode + 1) % 3
        if self.loop_mode == 0:
            self.loop_btn.setIcon(self.icon("repeat.svg"))
            self.loop_btn.setChecked(False)
            self.loop_btn.setToolTip("Loop: nonaktif")
        elif self.loop_mode == 1:
            self.loop_btn.setIcon(self.icon("repeat-one-active.svg"))
            self.loop_btn.setChecked(True)
            self.loop_btn.setToolTip("Loop satu lagu")
        elif self.loop_mode == 2:
            self.loop_btn.setIcon(self.icon("repeat-all-active.svg"))
            self.loop_btn.setChecked(True)
            self.loop_btn.setToolTip("Loop semua lagu")

    def toggle_shuffle(self):
        self.shuffle_mode = not self.shuffle_mode
        self.shuffle_btn.setChecked(self.shuffle_mode)
        self.shuffle_btn.setIcon(self.icon(
            "shuffle-active.svg" if self.shuffle_mode else "shuffle.svg"
        ))
        self.shuffle_btn.setToolTip("Shuffle: aktif" if self.shuffle_mode else "Shuffle: nonaktif")

    def handle_end(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self.loop_mode == 1:
                self.play_current()
            elif self.loop_mode == 2 or self.shuffle_mode:
                self.next_song()
            elif self.current_index < len(self.songs) - 1:
                self.next_song()
            else:
                self.player.stop()

    def update_duration(self, duration):
        self.progress.setRange(0, max(0, duration))
        self.duration_label.setText(self.format_time(duration))

    def update_position(self, position):
        if not self.progress.isSliderDown():
            self.progress.setValue(position)
        self.elapsed_label.setText(self.format_time(position))

    def seek_song(self, position):
        self.player.setPosition(position)

    def update_play_button(self, state):
        icon_name = "pause.svg" if state == QMediaPlayer.PlaybackState.PlayingState else "play.svg"
        self.play_btn.setIcon(self.icon(icon_name))

    @staticmethod
    def format_time(milliseconds):
        seconds = max(0, milliseconds // 1000)
        return f"{seconds // 60:02d}:{seconds % 60:02d}"

    def toggle_maximize(self):
        if self.isMaximized() or self.isFullScreen():
            self.showNormal()
            self.set_compact_mode(True)
        else:
            self.showMaximized()
            self.set_compact_mode(False)
        self.update_window_state(self.windowState())

    def set_compact_mode(self, enabled):
        for widget in self.brand_widgets:
            widget.setVisible(not enabled)
        self.scan_btn.setVisible(not enabled)
        self.now_playing.setVisible(not enabled)
        self.metadata_label.setVisible(True)
        self.progress.setVisible(not enabled)
        self.elapsed_label.setVisible(not enabled)
        self.duration_label.setVisible(not enabled)
        self.loop_btn.setVisible(not enabled)
        self.shuffle_btn.setVisible(not enabled)
        if enabled:
            self.setMinimumSize(620, 250)
            self.resize(620, 250)
            self.details_layout.setContentsMargins(16, 16, 16, 16)
            self.details_layout.setDirection(QVBoxLayout.Direction.LeftToRight)
            self.thumbnail.setFixedSize(190, 190)
            self.thumbnail.setProperty("compact", True)
            self.thumbnail.style().unpolish(self.thumbnail)
            self.thumbnail.style().polish(self.thumbnail)
            QTimer.singleShot(0, self.render_thumbnail)
            self.compact_transport.setVisible(True)
            for button in (self.prev_btn, self.play_btn, self.next_btn):
                button.setVisible(True)
            self.details.setMinimumSize(0, 0)
            QTimer.singleShot(0, self.restore_compact_geometry)
        else:
            self.setMinimumSize(900, 620)
            self.details_layout.setContentsMargins(24, 24, 24, 24)
            self.details_layout.setDirection(QVBoxLayout.Direction.TopToBottom)
            self.compact_transport.setVisible(False)
            for index, button in enumerate((self.prev_btn, self.play_btn, self.next_btn), start=1):
                self.controls.insertWidget(index, button)
                button.setVisible(True)
            self.thumbnail.setProperty("compact", False)
            self.thumbnail.style().unpolish(self.thumbnail)
            self.thumbnail.style().polish(self.thumbnail)
            self.thumbnail.setMinimumSize(280, 280)
            self.thumbnail.setMaximumSize(QSize(16777215, 16777215))
            QTimer.singleShot(0, self.render_thumbnail)

    def restore_compact_geometry(self):
        if not self.isMaximized() and not self.isMinimized():
            self.resize(620, 250)

    def update_window_state(self, state):
        is_expanded = bool(state & Qt.WindowState.WindowMaximized)
        self.maximize_btn.setIcon(self.icon("restore.svg" if is_expanded else "maximize.svg"))
        self.maximize_btn.setToolTip(
            "Kembalikan ukuran window" if is_expanded else "Maksimalkan window"
        )

    def mousePressEvent(self, event):
        if (
            not self.isMaximized()
            and not self.isFullScreen()
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        else:
            self._drag_position = None
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self._drag_position is not None
            and not self.isMaximized()
            and not self.isFullScreen()
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            self.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_position = None
        super().mouseReleaseEvent(event)

    def show_thumbnail(self, path):
        try:
            audio = MP3(path, ID3=ID3)
            if audio.tags is not None:
                for tag in audio.tags.values():
                    if tag.FrameID == "APIC":  # cover art
                        img_data = BytesIO(tag.data)
                        self.cover_pixmap = QPixmap()
                        self.cover_pixmap.loadFromData(img_data.read())
                        self.render_thumbnail()
                        return
            self.cover_pixmap = QPixmap()
            self.thumbnail.clear()
            self.cover_pixmap = self.app_icon().pixmap(QSize(512, 512))
            self.render_thumbnail()
        except Exception:
            self.cover_pixmap = QPixmap()
            self.thumbnail.clear()
            self.cover_pixmap = self.app_icon().pixmap(QSize(512, 512))
            self.render_thumbnail()

    def render_thumbnail(self):
        if not self.cover_pixmap.isNull() and self.thumbnail.size().isValid():
            self.thumbnail.setPixmap(self.cover_pixmap.scaled(
                self.thumbnail.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self.render_thumbnail)

    def show_metadata(self, path):
        filename_title = os.path.splitext(os.path.basename(path))[0]
        folder_album = os.path.basename(os.path.dirname(path)) or "Unknown Album"
        try:
            audio = MP3(path, ID3=ID3)
            title_value = str(audio.get("TIT2", "")).strip()
            artist_value = str(audio.get("TPE1", "")).strip()
            album_value = str(audio.get("TALB", "")).strip()
            title = title_value or filename_title
            artist = artist_value or "Unknown Artist"
            album = album_value or folder_album
            self.metadata_label.setText(f"Judul: {title}\nArtis: {artist}\nAlbum: {album}")
        except Exception:
            self.metadata_label.setText(
                f"Judul: {filename_title}\nArtis: Unknown Artist\nAlbum: {folder_album}"
            )

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(MusicPlayer.app_icon())
    window = MusicPlayer()
    window.showMaximized()
    window.update_window_state(window.windowState())
    window.apply_acrylic()
    sys.exit(app.exec())
