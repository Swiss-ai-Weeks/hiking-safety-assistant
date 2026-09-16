"""Swiss coordinates.

swisstopo's services answer only in the Swiss grid — `profile.json` rejects WGS84 outright and
`MapServer/identify` silently returns nothing for it — while everything the app shows is lat/lng.
The two transformers are built once here because constructing one is not free and several sources
need them on every request.
"""

from pyproj import Transformer

# LV95, the Swiss national grid. `always_xy` so calls read (easting, northing) / (lng, lat).
LV95 = "EPSG:2056"
WGS84 = "EPSG:4326"

TO_LV95 = Transformer.from_crs(WGS84, LV95, always_xy=True)
TO_WGS84 = Transformer.from_crs(LV95, WGS84, always_xy=True)
