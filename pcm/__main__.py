import sys
import logging
import multiprocessing
import subprocess
import os
import platform
import yaml
from datetime import datetime
from queue import Empty
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QPushButton,
    QListView,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QComboBox,
    QSpacerItem,
    QSizePolicy,
    QListWidget,
    QListWidgetItem,
    QDateEdit,
    QMessageBox,
    QApplication,
    QMainWindow,
    QWidget,
    QLabel,
    QTextEdit,
    QFileDialog,
)
from PySide6.QtCore import QTimer, Qt, QDate
from PySide6.QtGui import QPixmap, QFont, QPalette, QColor
from PySide6.QtWidgets import QDialog, QMessageBox
from pcm.worker import run_simulation_process
from pcm.ui.config_editor import ConfigEditorDialog


# --- Main GUI ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QuESt_PCM_simulator")
        self.resize(1000, 600)
        layout = QVBoxLayout()
        # --- Logo ---
        self.BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        logo_label = QLabel()
        pixmap = QPixmap(
            os.path.join(self.BASE_DIR, "Images", "PCM_logo.png")
        )  # your logo file
        if not pixmap.isNull():
            pixmap = pixmap.scaledToWidth(250, Qt.SmoothTransformation)
            logo_label.setPixmap(pixmap)
            logo_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo_label)
        # --- Description ---
        desc_label = QLabel(
            "Production Cost Modeling tool with High-Fidelity Energy Storage Models"
        )
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        # --- Increase font size ---
        font = QFont()
        font.setPointSize(14)  # Adjust the number as needed
        font.setBold(True)  # Optional: make it bold
        desc_label.setFont(font)
        layout.addWidget(desc_label)
        # --- Data path ---
        data_layout = QHBoxLayout()
        self.data_input = QLineEdit()
        data_btn = QPushButton("Browse Data Folder")
        data_btn.clicked.connect(self.select_data_folder)
        data_layout.addWidget(QLabel("Data Path:"))
        data_layout.addWidget(self.data_input)
        data_layout.addWidget(data_btn)
        # --- YAML path ---
        yaml_layout = QHBoxLayout()
        self.yaml_input = QLineEdit()
        yaml_btn = QPushButton("Browse YAML")
        yaml_btn.clicked.connect(self.select_yaml_file)
        yaml_layout.addWidget(QLabel("YAML Config:"))
        yaml_layout.addWidget(self.yaml_input)
        yaml_layout.addWidget(yaml_btn)
        # Add a button near your YAML selection
        self.edit_yaml_btn = QPushButton("Edit YAML")
        self.edit_yaml_btn.clicked.connect(self.open_yaml_editor)
        yaml_layout.addWidget(self.edit_yaml_btn)
        # --- Run button ---
        self.run_btn = QPushButton("Run Simulation")
        self.run_btn.clicked.connect(self.start_simulation)
        # --- Log box ---
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        # --- Open Results button ---
        self.open_results_btn = QPushButton("Open Results Folder")
        self.open_results_btn.setVisible(False)
        self.open_results_btn.clicked.connect(self.open_results_folder)
        self.results_path = None
        # --- Footer layout ---
        footer_layout = QVBoxLayout()
        # --- Images side by side ---
        images_layout = QHBoxLayout()
        images_layout.setSpacing(20)  # space between images
        images_layout.setAlignment(Qt.AlignCenter)  # center both images
        # Image A
        img1_label = QLabel()
        pix1 = QPixmap(os.path.join(self.BASE_DIR, "Images/SNL_Logo.jpg"))
        if not pix1.isNull():
            pix1 = pix1.scaledToWidth(150, Qt.SmoothTransformation)
            img1_label.setPixmap(pix1)
            img1_label.setAlignment(Qt.AlignCenter)
        images_layout.addWidget(img1_label)
        # Image B
        img2_label = QLabel()
        pix2 = QPixmap(os.path.join(self.BASE_DIR, "Images/DOE_Logo.jpg"))
        if not pix2.isNull():
            pix2 = pix2.scaledToWidth(150, Qt.SmoothTransformation)
            img2_label.setPixmap(pix2)
            img2_label.setAlignment(Qt.AlignCenter)
        images_layout.addWidget(img2_label)
        footer_layout.addLayout(images_layout)
        # Acknowledgment label
        ack_label = QLabel(
            "This material is based upon work supported by the U.S. Department of Energy, Office of Electricity (OE), Energy Storage Division."
        )
        ack_label.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(10)  # small font
        ack_label.setFont(font)
        footer_layout.addWidget(ack_label)
        # --- Assemble main layout ---
        layout.addLayout(data_layout)
        layout.addLayout(yaml_layout)
        layout.addWidget(self.run_btn)
        layout.addWidget(QLabel("Logs:"))
        layout.addWidget(self.log_box)
        layout.addWidget(self.open_results_btn)
        layout.addLayout(footer_layout)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        # --- Timer for logs ---
        self.timer = QTimer()
        self.timer.timeout.connect(self.poll_logs)
        self.process = None
        self.log_queue = None

    # --- File dialogs ---
    def select_data_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Data Folder",
            os.path.join(self.BASE_DIR, "Data"),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if folder:
            self.data_input.setText(folder)

    def select_yaml_file(self):
        file, _ = QFileDialog.getOpenFileName(
            self,
            "Select YAML File",
            os.path.join(self.BASE_DIR, "config"),
            "YAML Files (*.yaml *.yml)",
        )
        if file:
            self.yaml_input.setText(file)

    def open_yaml_editor(self):
        yaml_path = self.yaml_input.text()
        if not yaml_path or not os.path.exists(yaml_path):
            self.log("⚠️ Please select a valid YAML file first.")
            return
        dialog = ConfigEditorDialog(yaml_path, self)
        if dialog.exec():
            self.log("✅ YAML updated!")

    # --- Start simulation ---
    def start_simulation(self):
        data_path = self.data_input.text()
        yaml_path = self.yaml_input.text()
        if not data_path or not yaml_path:
            self.log("⚠️ Please select both data folder and YAML file.")
            return
        self.run_btn.setEnabled(False)
        self.open_results_btn.setVisible(False)
        self.log_box.clear()
        self.results_path = None
        self.log("Starting simulation...")
        self.log_queue = multiprocessing.Queue()
        self.process = multiprocessing.Process(
            target=run_simulation_process,
            args=(
                data_path,
                yaml_path,
                os.path.join(self.BASE_DIR, "Results"),
                self.log_queue,
            ),
        )
        self.process.start()
        self.timer.start(200)

    # --- Poll logs ---
    def poll_logs(self):
        if self.log_queue:
            try:
                while True:
                    msg = self.log_queue.get_nowait()
                    if msg.startswith("__RESULTS__:"):
                        self.results_path = msg.replace("__RESULTS__:", "")
                        self.open_results_btn.setVisible(True)
                    elif msg == "__DONE__":
                        self.run_btn.setEnabled(True)
                        self.timer.stop()
                        return
                    else:
                        self.log(msg)
            except Empty:
                pass

    # --- Open results folder ---
    def open_results_folder(self):
        os_name = platform.system()
        if self.results_path and os.path.exists(self.results_path):
            # os.startfile(self.results_path)  # Windows only
            if sys.platform == "win32":
                os.startfile(self.results_path)
            elif sys.platform == "darwin":  # macOS
                subprocess.run(["open", self.results_path])
            else:  # Linux
                subprocess.run(["xdg-open", self.results_path])
        else:
            self.log("⚠️ Results folder not found!")

    # --- Helper log ---
    def log(self, message):
        self.log_box.append(message)
        self.log_box.verticalScrollBar().setValue(
            self.log_box.verticalScrollBar().maximum()
        )


def main():
    multiprocessing.set_start_method("spawn")
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
