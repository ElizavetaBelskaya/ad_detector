import logging
import os
import re
import sys
from typing import List, Tuple

import vlc
from PyQt6.QtCore import QTimer, QSize, pyqtSignal, QPointF, Qt, QRect
from PyQt6.QtGui import QColor, QPalette, QIcon, QPainter, QPen, QLinearGradient
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QStyle, QSlider, QStyleOptionSlider, QLineEdit,
    QGridLayout, QScrollArea, QGroupBox
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def format_time(seconds: float) -> str:
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"


class AdSlider(QSlider):
    def __init__(self, ad_timestamps, total_duration, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.ad_timestamps = ad_timestamps
        self.total_duration = total_duration
        self.setRange(0, 1000)

        self._segment_cache = None
        self._last_paint_rect = None
        self._last_paint_size = None

        self.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #4A5568;
                height: 8px;
                background: #2D3748;
                margin: 2px 0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #63B3ED;
                border: 1px solid #4299E1;
                width: 16px;
                margin: -4px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #90CDF4;
            }
            QSlider::sub-page:horizontal {
                background: transparent;
            }
        """)

    def _calculate_segments(self, groove_rect):
        if not self.ad_timestamps or not self.total_duration:
            return []

        segments = []
        groove_width = groove_rect.width()
        width_multiplier = groove_width / self.total_duration

        for start, end in self.ad_timestamps:
            start_pos = int(start * width_multiplier)
            end_pos = int(end * width_multiplier)

            segment_rect = QRect(groove_rect.x() + start_pos, groove_rect.y(),
                                 end_pos - start_pos, groove_rect.height())
            segments.append(segment_rect)
        return segments

    def paintEvent(self, event):
        super().paintEvent(event)

        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        groove_rect = self.style().subControlRect(QStyle.ComplexControl.CC_Slider, opt,
                                                  QStyle.SubControl.SC_SliderGroove, self)

        current_size = groove_rect.size()
        if (self._segment_cache is None or
                self._last_paint_size != current_size):
            self._segment_cache = self._calculate_segments(groove_rect)
            self._last_paint_size = current_size
            self._last_paint_rect = groove_rect

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        ad_color = QColor(191, 97, 106, 128)

        for segment_rect in self._segment_cache:
            gradient = QLinearGradient(
                QPointF(segment_rect.topLeft()),
                QPointF(segment_rect.topRight())
            )
            gradient.setColorAt(0, ad_color.lighter(120))
            gradient.setColorAt(1, ad_color.lighter(120))

            painter.fillRect(segment_rect, gradient)

            painter.setPen(QPen(ad_color.lighter(150), 1))
            painter.drawRect(segment_rect)


def parse_time(text):
    text = text.strip()
    if ':' in text:
        parts = text.split(':')
        try:
            parts = list(map(int, parts))
            if len(parts) == 2:
                minutes, seconds = parts
                return minutes * 60 + seconds
            elif len(parts) == 1:
                return int(parts[0])
        except ValueError:
            return None
    else:
        try:
            return int(text)
        except ValueError:
            return None
    return None


class VLCPlayer(QWidget):
    error_occurred = pyqtSignal(str)

    def __init__(self, video_path, ad_timestamps):
        super().__init__()
        self.buttons_layout = QVBoxLayout()
        self.setWindowTitle("Плеер с таймкодами")

        self.instance = vlc.Instance('--no-video-title-show --no-xlib')
        self.mediaplayer = self.instance.media_player_new()

        self.ad_timestamps = ad_timestamps
        self.total_duration = 0
        self.video_path = video_path
        self._last_position = 0
        self._update_threshold = 0.01
        self._is_playing = False

        self.position_slider = AdSlider(ad_timestamps, self.total_duration)
        self.position_slider.sliderPressed.connect(self.slider_pressed)
        self.position_slider.sliderReleased.connect(self.slider_released)
        self.position_slider.sliderMoved.connect(self.slider_moved)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("color: #E2E8F0; font-size: 14px;")

        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.update_ui)

        self.is_seeking = False
        self._media_loaded = False

        self.setup_ui()
        self.load_video(video_path)
        self.create_ad_section(ad_timestamps)

    def setup_ui(self):
        self.video_frame = QWidget()
        self.video_frame.setAutoFillBackground(True)
        palette = self.video_frame.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0))
        self.video_frame.setPalette(palette)

        self.play_btn = QPushButton()
        self.play_btn.setIcon(QIcon.fromTheme("media-playback-start") or self.style().standardIcon(
            QStyle.StandardPixmap.SP_MediaPlay))
        self.play_btn.setIconSize(QSize(32, 32))
        self.play_btn.clicked.connect(self.toggle_play)

        self.restart_btn = QPushButton()
        self.restart_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.restart_btn.setIconSize(QSize(32, 32))
        self.restart_btn.clicked.connect(self.restart_playback)
        self.restart_btn.setToolTip("Начать сначала")

        layout = QVBoxLayout()
        layout.addWidget(self.video_frame, stretch=1)

        play_layout = QHBoxLayout()
        play_layout.addStretch()
        play_layout.addWidget(self.restart_btn)
        play_layout.addWidget(self.play_btn)
        play_layout.addStretch()
        layout.addLayout(play_layout)

        slider_layout = QHBoxLayout()
        slider_layout.addWidget(self.position_slider)
        slider_layout.addWidget(self.time_label)
        layout.addLayout(slider_layout)

        layout.addLayout(self.buttons_layout)
        self.setLayout(layout)

    def load_video(self, video_path):
        try:
            if not os.path.exists(video_path):
                raise FileNotFoundError(f"Видео файл не найден: {video_path}")
            self.media = self.instance.media_new(video_path)
            self.mediaplayer.set_media(self.media)
            self.media.parse_async()
            self.media.event_manager().event_attach(
                vlc.EventType.MediaParsedChanged,
                self._on_media_parsed
            )

            if sys.platform.startswith("linux"):
                self.mediaplayer.set_xwindow(self.video_frame.winId())
            elif sys.platform == "win32":
                self.mediaplayer.set_hwnd(self.video_frame.winId())
            elif sys.platform == "darwin":
                self.mediaplayer.set_nsobject(int(self.video_frame.winId()))

        except Exception as e:
            self.error_occurred.emit(f"Ошибка загрузки видео: {str(e)}")

    def _on_media_parsed(self, event):
        self.total_duration = self.media.get_duration() / 1000
        self.position_slider.total_duration = self.total_duration
        self.position_slider._segment_cache = None
        self.position_slider.update()
        self._media_loaded = True

    def is_playing_safe(self):
        try:
            return self.mediaplayer.is_playing()
        except Exception:
            return False

    def get_position_safe(self):
        try:
            return self.mediaplayer.get_position()
        except Exception:
            return 0.0

    def get_time_safe(self):
        try:
            return self.mediaplayer.get_time() // 1000
        except Exception:
            return 0

    def get_length_safe(self):
        try:
            return self.mediaplayer.get_length() // 1000
        except Exception:
            return 0

    def update_ui(self):
        if not self._media_loaded or self.is_seeking:
            return

        try:
            is_playing = self.is_playing_safe()
            if not is_playing:
                if self._is_playing:
                    self.timer.stop()
                    self._is_playing = False
                return

            position = self.get_position_safe()

            if abs(position - self._last_position) >= self._update_threshold:
                self.position_slider.setValue(int(position * 1000))
                self._last_position = position

                current_time = self.get_time_safe()
                total_time = self.get_length_safe()
                self.time_label.setText(f"{format_time(current_time)} / {format_time(total_time)}")

        except Exception as e:
            self.error_occurred.emit(f"Ошибка обновления UI: {str(e)}")
            self.timer.stop()
            self._is_playing = False

    def toggle_play(self):
        if not self._media_loaded:
            return

        try:
            if self.is_playing_safe():
                self.mediaplayer.pause()
                self.timer.stop()
                self._is_playing = False
            else:
                self.mediaplayer.play()
                self.timer.start()
                self._is_playing = True
        except Exception as e:
            self.error_occurred.emit(f"Ошибка переключения воспроизведения: {str(e)}")
            self._is_playing = False

    def create_ad_section(self, ad_timestamps):
        self.all_ad_buttons = []

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Поиск по таймкодам...")
        self.search_input.textChanged.connect(self.filter_ad_buttons)

        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(6)

        max_columns = 3
        for i, (start, end) in enumerate(ad_timestamps):
            label = f"{format_time(start)} – {format_time(end)}"
            btn = QPushButton(label)
            btn.setToolTip(f"Перейти к рекламе: {label}")
            btn.clicked.connect(lambda _, s=start: self.seek_to(s))
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #BF616A;
                    color: white;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 10px;
                }
                QPushButton:hover {
                    background-color: #D08770;
                }
            """)

            row = i // max_columns
            col = i % max_columns
            self.grid_layout.addWidget(btn, row, col)
            self.all_ad_buttons.append((btn, start, end))

        container = QWidget()
        container.setLayout(self.grid_layout)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(container)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Таймкоды рекламы"))
        layout.addWidget(self.search_input)
        layout.addWidget(scroll_area)

        group = QGroupBox()
        group.setLayout(layout)
        self.buttons_layout.addWidget(group)

    def filter_ad_buttons(self, text):
        query = text.strip()
        if not query:
            for btn, _, _ in self.all_ad_buttons:
                btn.setVisible(True)
            return

        range_match = re.match(r'(.+)[–\-](.+)', query)
        if range_match:
            start_text, end_text = range_match.groups()
            start_sec = parse_time(start_text)
            end_sec = parse_time(end_text)
            if start_sec is not None and end_sec is not None:
                for btn, start, end in self.all_ad_buttons:
                    btn.setVisible(start_sec <= start <= end_sec or start_sec <= end <= end_sec)
                return

        target = parse_time(query)
        if target is not None:
            for btn, start, end in self.all_ad_buttons:
                btn.setVisible(start <= target <= end)
        else:
            q = query.lower()
            for btn, start, end in self.all_ad_buttons:
                label = f"{format_time(start)} – {format_time(end)}"
                btn.setVisible(q in label.lower())

    def closeEvent(self, event):
        try:
            if self.is_playing_safe():
                self.mediaplayer.stop()
        except Exception:
            pass

        try:
            self.mediaplayer.release()
        except Exception:
            pass

        try:
            self.media.release()
        except Exception:
            pass

        try:
            self.instance.release()
        except Exception:
            pass

        super().closeEvent(event)
        event.accept()

    def set_position(self, value):
        if not self._media_loaded:
            return
        try:
            self.mediaplayer.set_position(value)
        except Exception as e:
            self.error_occurred.emit(f"Ошибка установки позиции: {str(e)}")

    def slider_pressed(self):
        self.is_seeking = True
        self.timer.stop()

    def slider_released(self):
        self.is_seeking = False
        self.set_position(self.position_slider.value() / 1000)
        if self._is_playing:
            self.timer.start()

    def slider_moved(self, value):
        if self.is_seeking:
            total_time = self.mediaplayer.get_length() // 1000
            current_time = int(value * total_time / 1000)
            self.time_label.setText(f"{format_time(current_time)} / {format_time(total_time)}")

    def seek_to(self, seconds):
        if not self._media_loaded:
            return
        try:
            if not self.is_playing_safe():
                self.mediaplayer.play()
                self.timer.start()
                self._is_playing = True
            self.mediaplayer.set_time(int(seconds * 1000))
        except Exception as e:
            self.error_occurred.emit(f"Ошибка установки позиции: {str(e)}")

    def restart_playback(self):
        if not self._media_loaded:
            return
        try:
            self.mediaplayer.stop()
            self.mediaplayer.play()
            self.timer.start()
            self._is_playing = True
        except Exception as e:
            self.error_occurred.emit(f"Ошибка перезапуска воспроизведения: {str(e)}")
