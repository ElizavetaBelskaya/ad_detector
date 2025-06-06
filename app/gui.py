import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import List, Tuple, Optional

import cv2
import matplotlib
import matplotlib.pyplot as plt
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QLabel, QFileDialog, QHBoxLayout, QPushButton, QScrollArea,
    QMessageBox, QWidget, QVBoxLayout, QSplitter, QSizePolicy)

from app import model_loader
from frame_classifier import detect_ad_scenes_from_segments_and_get_all_results, detect_scenes
from player import VLCPlayer, format_time
from styles import (
    MAIN_STYLE, VIDEO_LABEL_STYLE, VIDEO_INFO_LABEL_STYLE,
    get_html_style, get_button_style
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

matplotlib.use("QtAgg")
plt.ioff()


class ClickableLabel(QLabel):
    clicked = pyqtSignal(int)

    def mousePressEvent(self, event):
        self.clicked.emit(event.pos().x())


class Worker(QThread):
    finished = pyqtSignal()
    result = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(int)

    def __init__(self, classify_func, *args, **kwargs):
        super().__init__()
        self.classify_func = classify_func
        self.args = args
        self.kwargs = kwargs
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        try:
            if not self._is_running:
                return

            res = self.classify_func(*self.args, **self.kwargs)
            if self._is_running:
                self.result.emit(res)
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            if self._is_running:
                self.error.emit(str(e))
        finally:
            if self._is_running:
                self.finished.emit()


class VideoAnalyzerApp(QWidget):

    def __init__(self):
        super().__init__()
        self.video_path: Optional[str] = None
        self.timecodes: Optional[List[Tuple[float, float]]] = None
        self.duration: float = 0
        self.vlc_player: Optional[VLCPlayer] = None
        self.worker: Optional[Worker] = None
        self._init_ui()

    def _init_ui(self):
        self.setGeometry(100, 100, 900, 700)
        self.setWindowTitle("Video Ad Detector")
        self.setStyleSheet(MAIN_STYLE)

        self.left_panel = QWidget()
        policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.left_panel.setSizePolicy(policy)

        self.left_layout = QVBoxLayout(self.left_panel)
        self.left_layout.setContentsMargins(4, 4, 4, 4)
        self.left_layout.setSpacing(6)

        self.video_label = QLabel("Select video for analysis")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet(VIDEO_LABEL_STYLE)

        self.video_info_label = QLabel("No video selected")
        self.video_info_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.video_info_label.setWordWrap(True)
        self.video_info_label.setStyleSheet(VIDEO_INFO_LABEL_STYLE)

        self.video_info_container = QWidget()
        video_info_layout = QVBoxLayout(self.video_info_container)
        video_info_layout.setContentsMargins(0, 0, 0, 0)
        video_info_layout.addWidget(self.video_info_label)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.video_info_container)
        self.scroll_area.setWidgetResizable(True)

        self.btn_select = QPushButton("Select Video")
        self.btn_select.clicked.connect(self._load_video)
        self.btn_analyse = QPushButton("Analyze Video")
        self.btn_analyse.clicked.connect(self._start_analysis)

        self.left_layout.addWidget(self.video_label)
        self.left_layout.addWidget(self.scroll_area)
        self.left_layout.addWidget(self.btn_select)
        self.left_layout.addWidget(self.btn_analyse)
        self.left_layout.addStretch()

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.left_panel)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.layout.setSpacing(6)
        self.layout.addWidget(self.splitter)
        self.setLayout(self.layout)

    def _load_video(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video",
            "",
            "Video Files (*.mp4 *.avi *.mkv)"
        )

        if not file_path:
            return

        try:
            self.video_path = file_path
            self.timecodes = None
            self.video_label.setText(f"Selected: {file_path}")
            cap = cv2.VideoCapture(file_path)
            if not cap.isOpened():
                raise RuntimeError("Failed to open video file")

            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)

            if fps <= 0:
                raise RuntimeError("Invalid video FPS")

            self.duration = frame_count / fps
            cap.release()

            minutes = int(self.duration // 60)
            seconds = int(self.duration % 60)
            duration_str = f"{minutes} min {seconds} sec"
            file_name = os.path.basename(file_path)

            self.video_info_label.setText(
                f"Video: {file_name}\nDuration: {duration_str}"
            )

        except Exception as e:
            logger.error(f"Error loading video: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to load video: {str(e)}"
            )
            self.video_path = None
            self.video_label.setText("Select video for analysis")
            self.video_info_label.setText("No video selected")


    def _analyze_video(self) -> List[Tuple[float, float]]:
        try:
            model_swin = model_loader.load_model("Swin")
            scenes = detect_scenes(self.video_path)
            if not scenes:
                return []

            with ThreadPoolExecutor(max_workers=min(os.cpu_count() or 4, 4)) as executor:
                futures = []
                for scene in scenes:
                    if not self.worker._is_running:
                        break
                    futures.append(
                        executor.submit(
                            detect_ad_scenes_from_segments_and_get_all_results,
                            self.video_path,
                            [scene],
                            model_swin
                        )
                    )

                preds = {}
                for future in futures:
                    if not self.worker._is_running:
                        break
                    preds.update(future.result())

            if not preds:
                return []

            scores = [preds[(start, end)] for (start, end) in scenes]
            base_thresh = 12.5
            boost = 10

            preds_final = []
            for i, score in enumerate(scores):
                if not self.worker._is_running:
                    break

                prev_ad = i > 0 and scores[i - 1] >= base_thresh
                next_ad = i < len(scores) - 1 and scores[i + 1] >= base_thresh
                is_isolated = not prev_ad and not next_ad

                is_ad = self._is_advertisement(
                    score,
                    base_thresh=base_thresh,
                    boost=boost,
                    is_isolated=is_isolated
                )

                if is_ad:
                    preds_final.append(scenes[i])

            return preds_final

        except Exception as e:
            logger.error(f"Analysis error: {e}")
            raise

    def _is_advertisement(
            self,
            model_score: float,
            base_thresh: float,
            boost: float,
            is_isolated: bool
    ) -> bool:
        adjusted_thresh = base_thresh if is_isolated else base_thresh - boost
        return model_score >= adjusted_thresh

    def _start_analysis(self):
        if not self.video_path:
            self.video_label.setText("⚠️ Please select a video first!")
            return

        self._disable_controls()

        self.worker = Worker(self._analyze_video)
        self.worker.result.connect(self._on_analysis_result)
        self.worker.error.connect(self._on_analysis_error)
        self.worker.finished.connect(self._on_analysis_finished)
        self.worker.start()

    def _on_analysis_result(self, result: List[Tuple[float, float]]):
        if not result:
            self._show_no_ads_message()
            return

        self.timecodes = result
        self._update_results_display()
        self._setup_video_player()

    def _show_no_ads_message(self):
        self.video_info_label.setText(f"""
            <div style='{get_html_style("container")}'>
                <h2 style='{get_html_style("header")}'>No Ads Detected</h2>
                <p style='{get_html_style("text")}'>No ad segments found in this video.</p>
            </div>
        """)
        self.video_info_label.setTextFormat(Qt.TextFormat.RichText)

        if self.vlc_player is not None:
            self.splitter.widget(1).deleteLater()
            self.splitter.insertWidget(1, QWidget())
            self.vlc_player = None

    def _update_results_display(self):
        text_result = f"""
            <div style='{get_html_style("container")}'>
                <h2 style='{get_html_style("header")}'>
                    Ad Detection Report
                </h2>
        """

        total_duration = sum(end - start for start, end in self.timecodes)
        minutes = int(total_duration // 60)
        seconds = int(total_duration % 60)

        text_result += f"""
            <div style='{get_html_style("segment")}'>
                <p style='{get_html_style("text")}'>Total ad duration: {minutes} min {seconds} sec</p>
            </div>
        """

        for i, (start, end) in enumerate(self.timecodes, 1):
            start_str = format_time(start)
            end_str = format_time(end)

            text_result += f"""
                <div style='{get_html_style("segment")}'>
                    <p style='{get_html_style("text")}'>
                        Ad segment #{i}: {start_str} – {end_str}
                    </p>
                </div>
            """

        text_result += "</div>"

        self.video_info_label.setText(text_result)
        self.video_info_label.setTextFormat(Qt.TextFormat.RichText)
        self.video_info_label.setWordWrap(True)
        self.video_info_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.verticalScrollBar().setValue(0)

    def _setup_video_player(self):
        if self.vlc_player is not None:
            self.splitter.widget(1).deleteLater()

        self.vlc_player = VLCPlayer(self.video_path, self.timecodes)
        policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.vlc_player.setSizePolicy(policy)
        self.vlc_player.error_occurred.connect(self._on_player_error)
        if self.splitter.count() > 1:
            self.splitter.insertWidget(1, self.vlc_player)
        else:
            self.splitter.addWidget(self.vlc_player)

    def _on_player_error(self, error_msg: str):
        logger.error(f"Player error: {error_msg}")
        QMessageBox.warning(
            self,
            "Player Error",
            error_msg
        )

    def _on_analysis_error(self, error_msg: str):
        logger.error(f"Analysis error: {error_msg}")
        QMessageBox.critical(
            self,
            "Analysis Error",
            f"Failed to analyze video: {error_msg}"
        )

    def _on_analysis_finished(self):
        self._enable_controls()
        self.worker = None

    def _disable_controls(self):
        self.btn_select.setEnabled(False)
        self.btn_analyse.setEnabled(False)
        self.btn_analyse.setStyleSheet(get_button_style('disabled'))

    def _enable_controls(self):
        self.btn_select.setEnabled(True)
        self.btn_analyse.setEnabled(True)
        self.btn_analyse.setStyleSheet(get_button_style('normal'))

    def closeEvent(self, event):
        if self.worker is not None:
            self.worker.stop()
            self.worker.wait()

        if self.vlc_player is not None:
            self.vlc_player.close()
        event.accept()
