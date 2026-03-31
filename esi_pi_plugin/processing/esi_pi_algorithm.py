# -*- coding: utf-8 -*-
import json
import os
import tempfile

from osgeo import gdal

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransformContext,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingOutputRasterLayer,
    QgsProcessingOutputVectorLayer,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterNumber,
    QgsProcessingParameterString,
    QgsRasterLayer,
    QgsVectorLayer,
)
import processing


gdal.UseExceptions()


class EsiPiAlgorithm(QgsProcessingAlgorithm):
    INPUT_SPECS = "INPUT_SPECS"
    BUFFER_WIDTH = "BUFFER_WIDTH"
    RESOLUTION = "RESOLUTION"
    SIMPLIFY_TOL = "SIMPLIFY_TOL"
    OUTPUT_RASTER = "OUTPUT_RASTER"
    OUTPUT_VECTOR = "OUTPUT_VECTOR"

    def tr(self, string):
        return QCoreApplication.translate("EsiPiAlgorithm", string)

    def createInstance(self):
        return EsiPiAlgorithm()

    def name(self):
        return "compute_index"

    def displayName(self):
        return self.tr("Compute ESI/PI weighted index")

    def group(self):
        return self.tr("ESI PI Mapper")

    def groupId(self):
        return "esipimapper"

    def shortHelpString(self):
        return self.tr(
            "Rasterizes weighted vector layers (ESI/PI), sums aligned rasters, "
            "polygonizes and simplifies the result."
        )

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterString(
                self.INPUT_SPECS,
                self.tr("Input layer specs as JSON"),
                multiLine=True,
            )
        )
        self.addParameter(QgsProcessingParameterNumber(self.BUFFER_WIDTH, self.tr("Buffer width (m)"), defaultValue=200))
        self.addParameter(QgsProcessingParameterNumber(self.RESOLUTION, self.tr("Raster resolution (m)"), defaultValue=30))
        self.addParameter(QgsProcessingParameterNumber(self.SIMPLIFY_TOL, self.tr("Simplify tolerance (m)"), defaultValue=5))
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.OUTPUT_RASTER,
                self.tr("Output weighted raster"),
                fileFilter="GeoTIFF (*.tif)",
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.OUTPUT_VECTOR,
                self.tr("Output vector (GPKG)"),
                fileFilter="GeoPackage (*.gpkg)",
            )
        )

        self.addOutput(QgsProcessingOutputRasterLayer(self.OUTPUT_RASTER, self.tr("Output raster")))
        self.addOutput(QgsProcessingOutputVectorLayer(self.OUTPUT_VECTOR, self.tr("Output vector")))

    def processAlgorithm(self, parameters, context, feedback):
        specs_raw = self.parameterAsString(parameters, self.INPUT_SPECS, context)
        try:
            input_specs = json.loads(specs_raw)
        except json.JSONDecodeError as exc:
            raise QgsProcessingException(f"Invalid INPUT_SPECS JSON: {exc}") from exc

        if not input_specs:
            raise QgsProcessingException("No input layers provided")

        resolution = self.parameterAsDouble(parameters, self.RESOLUTION, context)
        buffer_width = self.parameterAsDouble(parameters, self.BUFFER_WIDTH, context)
        simplify_tol = self.parameterAsDouble(parameters, self.SIMPLIFY_TOL, context)
        out_raster = self.parameterAsFileOutput(parameters, self.OUTPUT_RASTER, context)
        out_vector = self.parameterAsFileOutput(parameters, self.OUTPUT_VECTOR, context)

        temp_dir = tempfile.mkdtemp(prefix="esi_pi_")
        transform_context = QgsCoordinateTransformContext()

        # Use first layer CRS as target CRS.
        first_layer = QgsVectorLayer(input_specs[0]["source"], "base", "ogr")
        if not first_layer.isValid():
            raise QgsProcessingException("First input layer is invalid")

        target_crs = first_layer.crs()
        if not target_crs.isValid():
            target_crs = QgsCoordinateReferenceSystem("EPSG:4326")

        raster_paths = []
        for idx, spec in enumerate(input_specs):
            if feedback.isCanceled():
                break

            layer = QgsVectorLayer(spec["source"], spec.get("layer_name", f"layer_{idx}"), "ogr")
            if not layer.isValid():
                raise QgsProcessingException(f"Invalid layer source: {spec['source']}")

            index_field = spec.get("index_field")
            weight = float(spec.get("weight", 1.0))
            if index_field not in [f.name() for f in layer.fields()]:
                raise QgsProcessingException(f"Field '{index_field}' not found in layer '{layer.name()}'")

            prepared_layer = layer
            if layer.crs() != target_crs:
                reprojected = processing.run(
                    "native:reprojectlayer",
                    {
                        "INPUT": layer,
                        "TARGET_CRS": target_crs,
                        "OUTPUT": "memory:",
                    },
                    context=context,
                    feedback=feedback,
                )["OUTPUT"]
                prepared_layer = reprojected

            if buffer_width > 0 and idx == 0:
                prepared_layer = processing.run(
                    "native:buffer",
                    {
                        "INPUT": prepared_layer,
                        "DISTANCE": buffer_width,
                        "SEGMENTS": 8,
                        "END_CAP_STYLE": 0,
                        "JOIN_STYLE": 0,
                        "MITER_LIMIT": 2,
                        "DISSOLVE": False,
                        "OUTPUT": "memory:",
                    },
                    context=context,
                    feedback=feedback,
                )["OUTPUT"]

            extent = prepared_layer.extent()
            raster_path = os.path.join(temp_dir, f"raster_{idx}.tif")
            rasterized = processing.run(
                "gdal:rasterize",
                {
                    "INPUT": prepared_layer,
                    "FIELD": index_field,
                    "BURN": 0,
                    "UNITS": 1,
                    "WIDTH": resolution,
                    "HEIGHT": resolution,
                    "EXTENT": extent,
                    "NODATA": 0,
                    "OPTIONS": "COMPRESS=LZW",
                    "DATA_TYPE": 5,
                    "INIT": 0,
                    "INVERT": False,
                    "EXTRA": "",
                    "OUTPUT": raster_path,
                },
                context=context,
                feedback=feedback,
            )["OUTPUT"]

            weighted_path = os.path.join(temp_dir, f"weighted_{idx}.tif")
            processing.run(
                "gdal:rastercalculator",
                {
                    "INPUT_A": rasterized,
                    "BAND_A": 1,
                    "FORMULA": f"A*{weight}",
                    "NO_DATA": 0,
                    "RTYPE": 5,
                    "OPTIONS": "COMPRESS=LZW",
                    "EXTRA": "",
                    "OUTPUT": weighted_path,
                },
                context=context,
                feedback=feedback,
            )
            raster_paths.append(weighted_path)

        if not raster_paths:
            raise QgsProcessingException("No raster layers generated")

        if len(raster_paths) == 1:
            gdal.Translate(out_raster, raster_paths[0], creationOptions=["COMPRESS=LZW"])
        else:
            processing.run(
                "native:cellstatistics",
                {
                    "INPUT": raster_paths,
                    "STATISTIC": 0,
                    "IGNORE_NODATA": True,
                    "REFERENCE_LAYER": raster_paths[0],
                    "OUTPUT_NODATA_VALUE": 0,
                    "OUTPUT": out_raster,
                },
                context=context,
                feedback=feedback,
            )

        polygonized = processing.run(
            "gdal:polygonize",
            {
                "INPUT": out_raster,
                "BAND": 1,
                "FIELD": "index_val",
                "EIGHT_CONNECTEDNESS": False,
                "EXTRA": "",
                "OUTPUT": "memory:",
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        simplified = processing.run(
            "native:simplifygeometries",
            {
                "INPUT": polygonized,
                "METHOD": 0,
                "TOLERANCE": simplify_tol,
                "OUTPUT": out_vector,
            },
            context=context,
            feedback=feedback,
        )["OUTPUT"]

        # validate result can load
        if not QgsRasterLayer(out_raster, "check").isValid():
            raise QgsProcessingException("Output raster is invalid")
        if not QgsVectorLayer(simplified, "check", "ogr").isValid():
            raise QgsProcessingException("Output vector is invalid")

        return {
            self.OUTPUT_RASTER: out_raster,
            self.OUTPUT_VECTOR: simplified,
        }
