import sys

from PyQt6.QtWidgets import QApplication

from gui import VideoAnalyzerApp
from model_loader import preload_all_models

if __name__ == "__main__":
    preload_all_models()
    app = QApplication(sys.argv)
    window = VideoAnalyzerApp()
    window.show()
    sys.exit(app.exec())