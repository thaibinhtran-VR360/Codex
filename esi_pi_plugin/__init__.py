# -*- coding: utf-8 -*-
"""QGIS plugin entry point for ESI/PI Mapper."""


def classFactory(iface):
    from .main_plugin import EsiPiPlugin

    return EsiPiPlugin(iface)
