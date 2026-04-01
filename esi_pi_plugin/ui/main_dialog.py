# -*- coding: utf-8 -*-
import json
from pathlib import Path

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qgis.core import (
    Qgis,
    QgsMessageLog,
    QgsProject,
    QgsVectorLayer,
)
import processing


class EsiPiDialog(QDialog):
    """Main dialog that collects parameters and runs processing."""

    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.setWindowTitle("ESI/PI Mapper")
        self.resize(900, 550)
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        info = QLabel(
            "Add vector layers, set ESI/PI field and weight coefficient (k). "
            "Then run weighted raster synthesis."
        )
        info.setWordWrap(True)
        main_layout.addWidget(info)

        self.layer_table = QTableWidget(0, 4)
        self.layer_table.setHorizontalHeaderLabels(["Layer", "Index Field", "Weight (k)", "Group"])
        self.layer_table.horizontalHeader().setStretchLastSection(True)
        main_layout.addWidget(self.layer_table)

        button_row = QHBoxLayout()
        self.btn_add_layers = QPushButton("Add selected layers")
        self.btn_remove_row = QPushButton("Remove row")
        self.btn_save_cfg = QPushButton("Save config")
        self.btn_load_cfg = QPushButton("Load config")
        button_row.addWidget(self.btn_add_layers)
        button_row.addWidget(self.btn_remove_row)
        button_row.addWidget(self.btn_save_cfg)
        button_row.addWidget(self.btn_load_cfg)
        main_layout.addLayout(button_row)

        settings_widget = QWidget()
        settings_form = QFormLayout(settings_widget)

        self.spin_buffer = QSpinBox()
        self.spin_buffer.setRange(0, 20000)
        self.spin_buffer.setValue(200)
        self.spin_buffer.setSuffix(" m")

        self.spin_res = QSpinBox()
        self.spin_res.setRange(1, 5000)
        self.spin_res.setValue(30)
        self.spin_res.setSuffix(" m")

        self.spin_simplify = QSpinBox()
        self.spin_simplify.setRange(0, 1000)
        self.spin_simplify.setValue(5)
        self.spin_simplify.setSuffix(" m")

        settings_form.addRow("Shoreline buffer width", self.spin_buffer)
        settings_form.addRow("Raster resolution", self.spin_res)
        settings_form.addRow("Simplify tolerance", self.spin_simplify)
        main_layout.addWidget(settings_widget)

        output_row = QHBoxLayout()
        self.cmb_output_mode = QComboBox()
        self.cmb_output_mode.addItems(["Load to project", "Keep file only"])
        output_row.addWidget(QLabel("Output handling:"))
        output_row.addWidget(self.cmb_output_mode)
        main_layout.addLayout(output_row)

        action_row = QHBoxLayout()
        self.btn_refresh = QPushButton("Refresh layers")
        self.btn_run = QPushButton("Run")
        self.btn_cancel = QPushButton("Cancel")
        action_row.addWidget(self.btn_refresh)
        action_row.addStretch(1)
        action_row.addWidget(self.btn_run)
        action_row.addWidget(self.btn_cancel)
        main_layout.addLayout(action_row)

        self.btn_add_layers.clicked.connect(self.add_selected_layers)
        self.btn_remove_row.clicked.connect(self.remove_selected_row)
        self.btn_refresh.clicked.connect(self.refresh_layers)
        self.btn_save_cfg.clicked.connect(self.save_config)
        self.btn_load_cfg.clicked.connect(self.load_config)
        self.btn_run.clicked.connect(self.run_processing)
        self.btn_cancel.clicked.connect(self.reject)

    def refresh_layers(self):
        self.available_layers = [
            layer
            for layer in QgsProject.instance().mapLayers().values()
            if isinstance(layer, QgsVectorLayer) and layer.isValid()
        ]

    def add_selected_layers(self):
        selected = self.iface.layerTreeView().selectedLayers()
        vector_layers = [lyr for lyr in selected if isinstance(lyr, QgsVectorLayer)]
        if not vector_layers:
            QMessageBox.warning(self, "No vector layers", "Select one or more vector layers in Layers panel first.")
            return

        for layer in vector_layers:
            row = self.layer_table.rowCount()
            self.layer_table.insertRow(row)

            layer_item = QTableWidgetItem(layer.name())
            layer_item.setData(Qt.UserRole, layer.id())
            self.layer_table.setItem(row, 0, layer_item)

            field_name = ""
            fields = [f.name() for f in layer.fields()]
            for candidate in ("ESI", "PI", "index", "score"):
                if candidate in fields:
                    field_name = candidate
                    break
            self.layer_table.setItem(row, 1, QTableWidgetItem(field_name))
            self.layer_table.setItem(row, 2, QTableWidgetItem("1.0"))
            self.layer_table.setItem(row, 3, QTableWidgetItem("default"))

    def remove_selected_row(self):
        row = self.layer_table.currentRow()
        if row >= 0:
            self.layer_table.removeRow(row)

    def save_config(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save configuration", "", "JSON (*.json)")
        if not path:
            return

        cfg = {
            "buffer_m": self.spin_buffer.value(),
            "resolution_m": self.spin_res.value(),
            "simplify_m": self.spin_simplify.value(),
            "rows": [],
        }
        for row in range(self.layer_table.rowCount()):
            cfg["rows"].append(
                {
                    "layer_id": self.layer_table.item(row, 0).data(Qt.UserRole),
                    "layer_name": self.layer_table.item(row, 0).text(),
                    "index_field": self.layer_table.item(row, 1).text(),
                    "weight": self.layer_table.item(row, 2).text(),
                    "group": self.layer_table.item(row, 3).text(),
                }
            )

        with open(path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=2)

    def load_config(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load configuration", "", "JSON (*.json)")
        if not path:
            return

        with open(path, "r", encoding="utf-8") as fh:
            cfg = json.load(fh)

        self.spin_buffer.setValue(int(cfg.get("buffer_m", 200)))
        self.spin_res.setValue(int(cfg.get("resolution_m", 30)))
        self.spin_simplify.setValue(int(cfg.get("simplify_m", 5)))

        self.layer_table.setRowCount(0)
        for saved in cfg.get("rows", []):
            layer = QgsProject.instance().mapLayer(saved.get("layer_id", ""))
            if not layer:
                continue
            row = self.layer_table.rowCount()
            self.layer_table.insertRow(row)

            layer_item = QTableWidgetItem(layer.name())
            layer_item.setData(Qt.UserRole, layer.id())
            self.layer_table.setItem(row, 0, layer_item)
            self.layer_table.setItem(row, 1, QTableWidgetItem(saved.get("index_field", "")))
            self.layer_table.setItem(row, 2, QTableWidgetItem(str(saved.get("weight", 1.0))))
            self.layer_table.setItem(row, 3, QTableWidgetItem(saved.get("group", "default")))

    def run_processing(self):
        if self.layer_table.rowCount() == 0:
            QMessageBox.warning(self, "Empty layer list", "Add at least one input layer.")
            return

        vector_specs = []
        for row in range(self.layer_table.rowCount()):
            layer_id = self.layer_table.item(row, 0).data(Qt.UserRole)
            field = self.layer_table.item(row, 1).text().strip()
            weight_text = self.layer_table.item(row, 2).text().strip()
            group = self.layer_table.item(row, 3).text().strip() or "default"

            layer = QgsProject.instance().mapLayer(layer_id)
            if not layer or not field:
                QMessageBox.warning(self, "Invalid row", f"Row {row + 1} has invalid layer or index field.")
                return

            try:
                weight = float(weight_text)
            except ValueError:
                QMessageBox.warning(self, "Invalid weight", f"Row {row + 1}: weight must be numeric.")
                return

            vector_specs.append(
                {
                    "layer": layer,
                    "index_field": field,
                    "weight": weight,
                    "group": group,
                }
            )

        tmp_dir = Path(QgsProject.instance().homePath() or str(Path.home())) / "esi_pi_outputs"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        params = {
            "INPUT_SPECS": json.dumps(
                [
                    {
                        "source": spec["layer"].source(),
                        "layer_name": spec["layer"].name(),
                        "index_field": spec["index_field"],
                        "weight": spec["weight"],
                        "group": spec["group"],
                    }
                    for spec in vector_specs
                ]
            ),
            "BUFFER_WIDTH": self.spin_buffer.value(),
            "RESOLUTION": self.spin_res.value(),
            "SIMPLIFY_TOL": self.spin_simplify.value(),
            "OUTPUT_RASTER": str(tmp_dir / "esi_pi_result.tif"),
            "OUTPUT_VECTOR": str(tmp_dir / "esi_pi_result.gpkg"),
        }

        try:
            result = processing.run("esipimapper:compute_index", params)
        except Exception as exc:  # pragma: no cover
            QgsMessageLog.logMessage(str(exc), "ESI/PI Mapper", level=Qgis.Critical)
            QMessageBox.critical(self, "Processing failed", str(exc))
            return

        if self.cmb_output_mode.currentIndex() == 0:
            self.iface.addRasterLayer(result["OUTPUT_RASTER"], "ESI_PI_Raster")
            self.iface.addVectorLayer(result["OUTPUT_VECTOR"], "ESI_PI_Vector", "ogr")

        self.accept()
