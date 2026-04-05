from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QGridLayout,
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
    QScrollArea,
    QSplitter,
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

        screen_rect = QApplication.primaryScreen().availableGeometry()
        self.resize(int(screen_rect.width() * 0.7), int(screen_rect.height() * 0.8))
        self.setMinimumSize(900, 600)

        self.yaml_path = yaml_path
        self.config_data = {}
        self.widgets = {}

        self.main_layout = QVBoxLayout(self)

        # --- Left side: QGridLayout ---
        self.left_grid = QGridLayout()
        self.left_grid.setColumnStretch(0, 0)  # label column: don't stretch
        self.left_grid.setColumnStretch(1, 1)  # field column: take remaining space
        self.left_grid.setColumnMinimumWidth(1, 160)
        self.left_grid.setHorizontalSpacing(12)
        self.left_grid.setVerticalSpacing(8)
        self.left_row = 0  # track current row

        # --- Right side: QFormLayout ---
        self.right_form = QFormLayout()
        self.right_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )
        self.right_form.setHorizontalSpacing(12)
        self.right_form.setVerticalSpacing(8)

        # --- Wrap in containers ---
        left_container = QWidget()
        left_container.setLayout(self.left_grid)
        left_container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        right_container = QWidget()
        right_container.setLayout(self.right_form)
        right_container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        # --- Splitter ---
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_container)
        splitter.addWidget(right_container)
        splitter.setSizes([600, 350])
        splitter.setChildrenCollapsible(False)

        # --- Scroll area around splitter ---
        scroll = QScrollArea()
        scroll.setWidget(splitter)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.main_layout.addWidget(scroll, stretch=1)

        self.load_yaml()
        self.build_form()

        # --- Buttons ---
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.cancel_btn = QPushButton("Cancel")
        self.save_btn.clicked.connect(self.save_config)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        self.main_layout.addLayout(btn_layout)

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

        def add_widget_with_help(label_text, widget, help_text=None, column="left"):
            if column == "left":
                label = QLabel(f"{label_text}:")
                label.setAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                if help_text:
                    help_btn = QPushButton("?")
                    help_btn.setFixedWidth(20)
                    help_btn.setToolTip(help_text)
                    help_btn.pressed.connect(
                        lambda t=help_text: QMessageBox.information(
                            self, "Help", t, QMessageBox.StandardButton.Ok
                        )
                    )
                    field_layout = QHBoxLayout()
                    field_layout.setContentsMargins(0, 0, 0, 0)
                    field_layout.addWidget(widget)
                    field_layout.addWidget(help_btn)
                    field_container = QWidget()
                    field_container.setLayout(field_layout)
                    self.left_grid.addWidget(label, self.left_row, 0)
                    self.left_grid.addWidget(field_container, self.left_row, 1)
                else:
                    self.left_grid.addWidget(label, self.left_row, 0)
                    self.left_grid.addWidget(widget, self.left_row, 1)
                self.left_row += 1
            else:
                field_layout = QHBoxLayout()
                field_layout.setContentsMargins(0, 0, 0, 0)
                field_layout.addWidget(widget)
                if help_text:
                    help_btn = QPushButton("?")
                    help_btn.setFixedWidth(20)
                    help_btn.setToolTip(help_text)
                    help_btn.pressed.connect(
                        lambda t=help_text: QMessageBox.information(
                            self, "Help", t, QMessageBox.StandardButton.Ok
                        )
                    )
                    field_layout.addWidget(help_btn)
                field_container = QWidget()
                field_container.setLayout(field_layout)
                self.right_form.addRow(f"{label_text}:", field_container)

        def add_dropdown(key, options, help_text=None, column=None):
            combo = QComboBox()
            combo.addItems(options)
            combo.setCurrentText(str(cfg.get(key, options[0])))
            combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.widgets[key] = combo
            add_widget_with_help(key, combo, help_text, column)

        def add_checkbox(key, help_text=None, column=None):
            cb = QCheckBox()
            cb.setChecked(bool(cfg.get(key, False)))
            self.widgets[key] = cb
            add_widget_with_help(key, cb, help_text, column)

        def add_float(key, default=0.0, help_text=None, column=None):
            spin = QDoubleSpinBox()
            spin.setRange(-1e9, 1e9)
            spin.setDecimals(6)
            spin.setValue(float(cfg.get(key, default)))
            spin.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
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
            spin.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.widgets[key] = spin
            add_widget_with_help(key, spin, help_text, column)

        def add_date(key, help_text=None, column=None):
            date_edit = QDateEdit()
            date_edit.setCalendarPopup(True)
            date_edit.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
            )
            val = cfg.get(key, "01/01/2020")
            try:
                dt = datetime.strptime(val, "%m/%d/%Y")
                date_edit.setDate(QDate(dt.year, dt.month, dt.day))
            except Exception:
                date_edit.setDate(QDate.currentDate())
            self.widgets[key] = date_edit
            add_widget_with_help(key, date_edit, help_text, column)

        def add_list(key, items_list=None, help_text=None, column=None):
            lst_widget = QListWidget()
            lst_widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
            lst_widget.setMaximumHeight(150)
            lst_widget.setMinimumHeight(80)
            lst_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            items = items_list if items_list is not None else cfg.get(key, [])
            if not isinstance(items, list):
                items = []
            selected_items = set(
                cfg.get(key, []) if isinstance(cfg.get(key, []), list) else []
            )
            for v in items:
                item = QListWidgetItem(v)
                lst_widget.addItem(item)
                if v in selected_items:
                    item.setSelected(True)
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
            help_text="LP is faster but MILP gives better commitment decisions",
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
            help_text="How many ancillary services can ESS participate in one time-period",
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
                help_text="fixed and percentage are extracted from reserves_default_DA.csv and reserves_default_RT.csv, timeseries from reserves_timeseries folder",
                column="left",
            )

        add_checkbox(
            "plotly_plots",
            help_text="Generate html plots for better illustration (takes longer time)",
            column="right",
        )
        add_dropdown(
            "output_interval",
            ["at_once", "daily", "weekly", "monthly"],
            help_text="How often to generate plots and json output",
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
