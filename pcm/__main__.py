import sys
import logging
import multiprocessing
import os
import yaml
from datetime import datetime
from queue import Empty
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QPushButton, QListView, 
    QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox, QSpacerItem, 
    QSizePolicy, QListWidget, QListWidgetItem, QDateEdit, QMessageBox,  
    QApplication, QMainWindow, QWidget, QLabel, QTextEdit, QFileDialog
)
from PySide6.QtCore import QTimer, Qt, QDate
from PySide6.QtGui import QPixmap, QFont, QPalette, QColor
from PySide6.QtWidgets import QDialog, QMessageBox
from pcm.worker import run_simulation_process


class ConfigEditorDialog(QDialog):
    """
    Popup dialog to edit simulation YAML config with widgets instead of raw text.
    """
    def __init__(self, yaml_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit YAML Config")
        # Get available screen geometry
        screen_rect = QApplication.primaryScreen().availableGeometry()
        screen_width = screen_rect.width()
        screen_height = screen_rect.height()

        # Resize dialog to 80% of screen width/height
        self.resize(int(screen_width * 0.6), int(screen_height * 0.6))
        self.setMinimumSize(600, 400)  # Minimum reasonable size

        self.yaml_path = yaml_path
        self.config_data = {}
        self.widgets = {}  # key -> widget

        self.main_layout = QVBoxLayout()
        self.left_form = QFormLayout()
        self.right_form = QFormLayout()
        columns_layout = QHBoxLayout()
        columns_layout.addLayout(self.left_form)
        columns_layout.addSpacerItem(QSpacerItem(20, 0, QSizePolicy.Fixed, QSizePolicy.Minimum))
        columns_layout.addLayout(self.right_form)

        self.main_layout.addLayout(columns_layout) 

        self.load_yaml()
        self.build_form()
        #self.main_layout.addLayout(self.form_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.cancel_btn = QPushButton("Cancel")
        self.save_btn.clicked.connect(self.save_config)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        self.main_layout.addLayout(btn_layout)

        self.setLayout(self.main_layout)
    # -------------------------------
    # Load YAML
    # -------------------------------
    def load_yaml(self):
        if not os.path.exists(self.yaml_path):
            QMessageBox.warning(self, "Error", f"YAML file not found:\n{self.yaml_path}")
            return
        with open(self.yaml_path, "r") as f:
            self.config_data = yaml.safe_load(f)
    # -------------------------------
    # Build form widgets
    # -------------------------------
    def build_form(self):
        cfg = self.config_data
        # -------------------------------
        # Helper to add widget + help button
        # -------------------------------
        def add_widget_with_help(label_text, widget, help_text=None, column="left"):
            layout = QHBoxLayout()
            layout.addWidget(widget)
            if help_text:
                help_btn = QPushButton("?")
                help_btn.setFixedWidth(20)
                help_btn.setToolTip(help_text)
                layout.addWidget(help_btn)
            if column == "left":
                self.left_form.addRow(f"{label_text}:", layout)
            else:
                self.right_form.addRow(f"{label_text}:", layout)
        # -------------------------------
        # Dropdowns
        # -------------------------------
        def add_dropdown(key, options, help_text = None, column = None):
            combo = QComboBox()
            combo.addItems(options)
            combo.setCurrentText(str(cfg.get(key, options[0])))
            self.widgets[key] = combo
            add_widget_with_help(key, combo, help_text, column)
        # -------------------------------
        # Booleans
        # -------------------------------
        def add_checkbox(key, help_text = None, column = None):
            cb = QCheckBox()
            cb.setChecked(bool(cfg.get(key, False)))
            self.widgets[key] = cb
            add_widget_with_help(key, cb, help_text, column)
        # -------------------------------
        # Numeric
        # -------------------------------
        def add_float(key, default=0.0, help_text = None, column = None):
            spin = QDoubleSpinBox()
            spin.setRange(-1e9, 1e9)
            spin.setDecimals(6)
            spin.setValue(float(cfg.get(key, default)))
            self.widgets[key] = spin
            add_widget_with_help(key, spin, help_text, column)

        def add_int(key, default=0, min_val=0, max_val=100000, step = 1, help_text = None, column = None):
            spin = QSpinBox()
            spin.setRange(min_val, max_val)
            spin.setValue(int(cfg.get(key, default)))
            spin.setSingleStep(step)
            self.widgets[key] = spin
            add_widget_with_help(key, spin, help_text, column)
        # -------------------------------
        # Dates
        # -------------------------------
        def add_date(key, help_text = None, column = None):
            date_edit = QDateEdit()
            date_edit.setCalendarPopup(True)
            val = cfg.get(key, "01/01/2020")
            try:
                dt = datetime.strptime(val, "%m/%d/%Y")
                date_edit.setDate(QDate(dt.year, dt.month, dt.day))
            except Exception:
                date_edit.setDate(QDate.currentDate())
            self.widgets[key] = date_edit
            add_widget_with_help(key, date_edit, help_text, column)
        # -------------------------------
        # Lists (multi-select)
        # -------------------------------
        def add_list(key, items_list=None, help_text=None, column = None):
            lst_widget = QListWidget()
            lst_widget.setSelectionMode(QListWidget.MultiSelection)  # allow multiple selection
            lst_widget.setMaximumHeight(150)  # adjust as needed
            lst_widget.setMinimumHeight(80)   # optional
            lst_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            # Determine items to display
            items = items_list if items_list is not None else cfg.get(key, [])
            if not isinstance(items, list):
                items = []

            # Pre-selected items from YAML
            selected_items = set(cfg.get(key, []) if isinstance(cfg.get(key, []), list) else [])

            # Add items to widget and pre-select if in YAML
            for v in items:
                item = QListWidgetItem(v)
                lst_widget.addItem(item)
                if v in selected_items:
                    item.setSelected(True)  # select the item

            self.widgets[key] = lst_widget
            add_widget_with_help(key, lst_widget, help_text, column)

        add_dropdown("solver",  ["cplex", "gurobi", "glpk", "cbc", "xpress", "knitro"], help_text="Select the solver to use for optimization. Recommended 'cplex' or 'gurobi'", column="left")
        add_float("baseMVA", 100.0, help_text="Base MVA for the system", column="left")
        add_date("start_date", help_text = "Simulation start date in MM/DD/YYYY format", column="left")
        add_date("end_date", help_text = "Simulation end date in MM/DD/YYYY format", column="left")
        add_int("DA_lookahead_periods", 12, 6, 24, help_text="How many hours to look ahead in day-ahead SCUC (6-24 hours)", column="left")
        add_int("RT_resolution", 60, 5, 60, 5, help_text="Resolution of real-time SCED (5-60 minutes in 5 minute intervals).", column="left")
        add_int("RT_lookahead_periods", 1, 1, 100, help_text="How many periods to look ahead in real-time SCED", column="left")
        add_float("mipgap", 0.01, help_text = "MIP gap for the solver", column="left")
        add_dropdown("run_RTSCED_as", ["LP", "MILP"], help_text = "LP is faster (as all commitment variables from DA are fixed) but MILP gives better commitment decisions (can schedule fast start generators)", column="left")
        add_dropdown("load_timeseries_aggregation_level", ["node", "area"], help_text = "How your load_timeseries data is arranged columnwise", column="left")
        add_int("storage_AS_participation_level", 4, 0, 4, help_text = "how many ancillary services can ESS participate in one time-period", column="left")
        add_checkbox("branch_contingency", help_text = "Enable N-1 transmission security constraints", column="left")
        add_list("thermal_generator_types", 
                items_list = ["CT", "CC", "STEAM", "NUCLEAR"],
                help_text = "Select the thermal unit types in gen.csv file", column="right")
        add_list("renewable_generator_types", 
                 items_list = ["PV", "RTPV", "CSP", "HYDRO", "WIND"],
                 help_text = "Select all renewable unit types in gen.csv file", column="right")
        add_list("fixed_renewable_types", 
                 items_list = ["RTPV"],
                 help_text = "Select all fixed-output renewable unit types in gen.csv file", column="right")
        # -------------------------------
        # Reserves (dropdowns)
        # -------------------------------
        reserve_options = ["None", "fixed", "percentage", "timeseries"]
        reserve_keys = [
            "System Reserve", "Regulation Up", "Regulation Down",
            "Spinning Reserve", "NonSpinning Reserve",
            "Supplemental Reserve", "Flexible Ramp Up", "Flexible Ramp Down"
        ]
        for key in reserve_keys:
            add_dropdown(key, reserve_options, help_text = "fixed and percentage are are extracted from reserves_default_DA.csv and reserves_default_RT.csv file and timeseries are extracted from reserves_timeseries folder", column="left")
        
        add_checkbox("plotly_plots", help_text = "generate html plots for better illustration (takes longer time)" , column="right")
        add_dropdown("output_interval", ["at_once", "daily", "weekly", "monthly"], help_text = "how often to generate plots and json output", column="right")
    # -------------------------------
    # Save config back to YAML
    # -------------------------------
    def save_config(self):
        new_cfg = {}
        for key, widget in self.widgets.items():
            if isinstance(widget, QComboBox):
                new_cfg[key] = widget.currentText()
            elif isinstance(widget, QCheckBox):
                new_cfg[key] = widget.isChecked()
            elif isinstance(widget, QDoubleSpinBox):
                new_cfg[key] = widget.value()
            elif isinstance(widget, QSpinBox):
                new_cfg[key] = widget.value()
            elif isinstance(widget, QDateEdit):
                new_cfg[key] = widget.date().toString("MM/dd/yyyy")
            elif isinstance(widget, QListWidget):
                new_cfg[key] = [item.text() for item in widget.selectedItems()]
            else:
                new_cfg[key] = str(widget.text())
        # Validate YAML before saving
        try:
            yaml.safe_load(yaml.dump(new_cfg))
        except Exception as e:
            QMessageBox.critical(self, "Invalid YAML", f"Cannot save: {e}")
            return
        try:
            with open(self.yaml_path, "w") as f:
                yaml.dump(new_cfg, f)
            QMessageBox.information(self, "Saved", "YAML config saved successfully!")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save YAML:\n{e}")

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
        pixmap = QPixmap(os.path.join(self.BASE_DIR, "Images", "PCM_logo.png"))  # your logo file
        if not pixmap.isNull():
            pixmap = pixmap.scaledToWidth(250, Qt.SmoothTransformation)
            logo_label.setPixmap(pixmap)
            logo_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo_label)
        # --- Description ---
        desc_label = QLabel("Production Cost Modeling tool with High-Fidelity Energy Storage Models")
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        # --- Increase font size ---
        font = QFont()
        font.setPointSize(14)  # Adjust the number as needed
        font.setBold(True)      # Optional: make it bold
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
        images_layout.setSpacing(20)        # space between images
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
        ack_label = QLabel("This material is based upon work supported by the U.S. Department of Energy, Office of Electricity (OE), Energy Storage Division.")
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
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if folder:
            self.data_input.setText(folder)

    def select_yaml_file(self):
        file, _ = QFileDialog.getOpenFileName(
            self,
            "Select YAML File",
            os.path.join(self.BASE_DIR, "config"),  
            "YAML Files (*.yaml *.yml)"
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
            args=(data_path, yaml_path, os.path.join(self.BASE_DIR, "Results"), self.log_queue)
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
        if self.results_path and os.path.exists(self.results_path):
            os.startfile(self.results_path)  # Windows only
        else:
            self.log("⚠️ Results folder not found!")

    # --- Helper log ---
    def log(self, message):
        self.log_box.append(message)
        self.log_box.verticalScrollBar().setValue(self.log_box.verticalScrollBar().maximum())

def main():
    multiprocessing.set_start_method("spawn")
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()