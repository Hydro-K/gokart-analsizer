"""EV Kart Data Analyzer — entry point."""

import sys
import os

# Ensure src/ is importable from the repo root
sys.path.insert(0, os.path.dirname(__file__))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from src.gui.main_window import MainWindow


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("EV Kart Data Analyzer")
    app.setOrganizationName("Purdue EV Grand Prix")

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
