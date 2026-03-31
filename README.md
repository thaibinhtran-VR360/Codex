# ESI/PI Mapper Plugin for QGIS

A QGIS plugin scaffold for **Environmental Sensitivity Index (ESI)** / **Priority Index (PI)** mapping.

## Features implemented

- Manage multiple vector input layers with:
  - index field (ESI/PI)
  - weight coefficient `k`
  - grouping tag for reusable configs
- Save/load processing configuration as JSON.
- Processing algorithm `esipimapper:compute_index`:
  1. Reproject layers to common CRS.
  2. Optional shoreline buffer (applied to first layer).
  3. Rasterize index field at configurable resolution.
  4. Apply weight `k` per raster.
  5. Sum rasters pixel-by-pixel.
  6. Polygonize and simplify output geometry.
- Outputs:
  - GeoTIFF weighted index raster
  - GeoPackage vectorized result
  - Automatic loading to QGIS project (optional)

## Plugin structure

```text
esi_pi_plugin/
  __init__.py
  metadata.txt
  main_plugin.py
  icon.svg
  core/
  ui/
    main_dialog.py
  processing/
    esi_pi_algorithm.py
```

## Installation (QGIS 3.44)

1. Zip the `esi_pi_plugin` folder content (not parent directory).
2. In QGIS: **Plugins > Manage and Install Plugins > Install from ZIP**.
3. Select the ZIP file.
4. Enable plugin **ESI PI Mapper**.

> Alternative (development mode): copy `esi_pi_plugin` into your QGIS profile plugin folder.

## Example workflow

1. Prepare vector layers containing ESI/PI field values.
2. Add layers to QGIS project.
3. Open **ESI/PI Mapper** from plugin menu.
4. Click **Add selected layers**.
5. Set for each layer:
   - index field (`ESI`, `PI`, `index`, ...)
   - weight `k` (numeric)
   - group name
6. Set global parameters:
   - shoreline buffer width (m)
   - raster resolution (m)
   - simplify tolerance (m)
7. Click **Run**.
8. Result layers are generated in `<project_home>/esi_pi_outputs/` and loaded automatically.

## Notes on performance and data quality

- Use projected CRS with meter units for buffer and resolution correctness.
- Keep resolution as coarse as acceptable for faster processing on large areas.
- Ensure index fields are numeric and cleaned before processing.
- Large datasets should use local disk paths (avoid remote/network providers when possible).

## Limitations / future improvements

- Advanced index table editor (inline class-based mapping) can be added to UI.
- Layout composer generation (title, scale bar, grid, mainland/island map) can be scripted in next phase.
- Topology post-processing (`fixgeometries`, sliver removal) can be made configurable.
