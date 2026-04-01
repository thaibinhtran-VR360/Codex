# -*- coding: utf-8 -*-
from pathlib import Path

from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.core import QgsApplication

from .ui.main_dialog import EsiPiDialog
from .processing.esi_pi_algorithm import EsiPiAlgorithm


class EsiPiPlugin:
    """Main plugin class for ESI/PI mapping workflow."""

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = Path(__file__).parent
        self.action = None
        self.dialog = None
        self.algorithm = None

    def tr(self, message):
        return QCoreApplication.translate("EsiPiPlugin", message)

    def initGui(self):
        icon_path = str(self.plugin_dir / "icon.svg")
        self.action = QAction(QIcon(icon_path), self.tr("ESI/PI Mapper"), self.iface.mainWindow())
        self.action.triggered.connect(self.run)

        self.iface.addPluginToMenu(self.tr("&ESI/PI Mapper"), self.action)
        self.iface.addToolBarIcon(self.action)

        self.algorithm = EsiPiAlgorithm()
        QgsApplication.processingRegistry().addAlgorithm(self.algorithm)

    def unload(self):
        if self.action:
            self.iface.removePluginMenu(self.tr("&ESI/PI Mapper"), self.action)
            self.iface.removeToolBarIcon(self.action)

        if self.algorithm:
            QgsApplication.processingRegistry().removeAlgorithm(self.algorithm.id())

    def run(self):
        if self.dialog is None:
            self.dialog = EsiPiDialog(self.iface)

        self.dialog.refresh_layers()
        result = self.dialog.exec_()
        if result:
            QMessageBox.information(
                self.iface.mainWindow(),
                self.tr("ESI/PI Mapper"),
                self.tr("Processing finished. Check the Layers panel for outputs."),
            )
