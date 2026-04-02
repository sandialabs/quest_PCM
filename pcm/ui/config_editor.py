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
import yaml
from datetime import datetime
import os


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
        columns_layout.addSpacerItem(
            QSpacerItem(20, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        )
        columns_layout.addLayout(self.right_form)

        self.main_layout.addLayout(columns_layout)

        self.load_yaml()
        self.build_form()
        # self.main_layout.addLayout(self.form_layout)

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
            QMessageBox.warning(
                self, "Error", f"YAML file not found:\n{self.yaml_path}"
            )
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
        def add_dropdown(key, options, help_text=None, column=None):
            combo = QComboBox()
            combo.addItems(options)
            combo.setCurrentText(str(cfg.get(key, options[0])))
            self.widgets[key] = combo
            add_widget_with_help(key, combo, help_text, column)

        # -------------------------------
        # Booleans
        # -------------------------------
        def add_checkbox(key, help_text=None, column=None):
            cb = QCheckBox()
            cb.setChecked(bool(cfg.get(key, False)))
            self.widgets[key] = cb
            add_widget_with_help(key, cb, help_text, column)

        # -------------------------------
        # Numeric
        # -------------------------------
        def add_float(key, default=0.0, help_text=None, column=None):
            spin = QDoubleSpinBox()
            spin.setRange(-1e9, 1e9)
            spin.setDecimals(6)
            spin.setValue(float(cfg.get(key, default)))
            self.widgets[key] = spin
            add_widget_with_help(key, spin, help_text, column)

        def add_int(
            key,
            default=0,
            min_val=0,
            max_val=100000,
            step=1,
            help_text=None,
            column=None,
        ):
            spin = QSpinBox()
            spin.setRange(min_val, max_val)
            spin.setValue(int(cfg.get(key, default)))
            spin.setSingleStep(step)
            self.widgets[key] = spin
            add_widget_with_help(key, spin, help_text, column)

        # -------------------------------
        # Dates
        # -------------------------------
        def add_date(key, help_text=None, column=None):
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
        def add_list(key, items_list=None, help_text=None, column=None):
            lst_widget = QListWidget()
            lst_widget.setSelectionMode(
                QListWidget.MultiSelection
            )  # allow multiple selection
            lst_widget.setMaximumHeight(150)  # adjust as needed
            lst_widget.setMinimumHeight(80)  # optional
            lst_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            # Determine items to display
            items = items_list if items_list is not None else cfg.get(key, [])
            if not isinstance(items, list):
                items = []

            # Pre-selected items from YAML
            selected_items = set(
                cfg.get(key, []) if isinstance(cfg.get(key, []), list) else []
            )

            # Add items to widget and pre-select if in YAML
            for v in items:
                item = QListWidgetItem(v)
                lst_widget.addItem(item)
                if v in selected_items:
                    item.setSelected(True)  # select the item

            self.widgets[key] = lst_widget
            add_widget_with_help(key, lst_widget, help_text, column)

        add_dropdown(
            "solver",
            ["cplex", "gurobi", "glpk", "cbc", "xpress", "knitro"],
            help_text="Select the solver to use for optimization. Recommended 'cplex' or 'gurobi'",
            column="left",
        )
        add_float("baseMVA", 100.0, help_text="Base MVA for the system", column="left")
        add_date(
            "start_date",
            help_text="Simulation start date in MM/DD/YYYY format",
            column="left",
        )
        add_date(
            "end_date",
            help_text="Simulation end date in MM/DD/YYYY format",
            column="left",
        )
        add_int(
            "DA_lookahead_periods",
            12,
            6,
            24,
            help_text="How many hours to look ahead in day-ahead SCUC (6-24 hours)",
            column="left",
        )
        add_int(
            "RT_resolution",
            60,
            5,
            60,
            5,
            help_text="Resolution of real-time SCED (5-60 minutes in 5 minute intervals).",
            column="left",
        )
        add_int(
            "RT_lookahead_periods",
            1,
            1,
            100,
            help_text="How many periods to look ahead in real-time SCED",
            column="left",
        )
        add_float("mipgap", 0.01, help_text="MIP gap for the solver", column="left")
        add_dropdown(
            "run_RTSCED_as",
            ["LP", "MILP"],
            help_text="LP is faster (as all commitment variables from DA are fixed) but MILP gives better commitment decisions (can schedule fast start generators)",
            column="left",
        )
        add_dropdown(
            "load_timeseries_aggregation_level",
            ["node", "area"],
            help_text="How your load_timeseries data is arranged columnwise",
            column="left",
        )
        add_int(
            "storage_AS_participation_level",
            4,
            0,
            4,
            help_text="how many ancillary services can ESS participate in one time-period",
            column="left",
        )
        add_checkbox(
            "branch_contingency",
            help_text="Enable N-1 transmission security constraints",
            column="left",
        )
        add_list(
            "thermal_generator_types",
            items_list=["CT", "CC", "STEAM", "NUCLEAR"],
            help_text="Select the thermal unit types in gen.csv file",
            column="right",
        )
        add_list(
            "renewable_generator_types",
            items_list=["PV", "RTPV", "CSP", "HYDRO", "WIND"],
            help_text="Select all renewable unit types in gen.csv file",
            column="right",
        )
        add_list(
            "fixed_renewable_types",
            items_list=["RTPV"],
            help_text="Select all fixed-output renewable unit types in gen.csv file",
            column="right",
        )
        # -------------------------------
        # Reserves (dropdowns)
        # -------------------------------
        reserve_options = ["None", "fixed", "percentage", "timeseries"]
        reserve_keys = [
            "System Reserve",
            "Regulation Up",
            "Regulation Down",
            "Spinning Reserve",
            "NonSpinning Reserve",
            "Supplemental Reserve",
            "Flexible Ramp Up",
            "Flexible Ramp Down",
        ]
        for key in reserve_keys:
            add_dropdown(
                key,
                reserve_options,
                help_text="fixed and percentage are are extracted from reserves_default_DA.csv and reserves_default_RT.csv file and timeseries are extracted from reserves_timeseries folder",
                column="left",
            )

        add_checkbox(
            "plotly_plots",
            help_text="generate html plots for better illustration (takes longer time)",
            column="right",
        )
        add_dropdown(
            "output_interval",
            ["at_once", "daily", "weekly", "monthly"],
            help_text="how often to generate plots and json output",
            column="right",
        )

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
