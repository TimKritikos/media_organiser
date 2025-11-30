import math
import gpxpy
import requests
from PIL import Image, ImageDraw
from io import BytesIO
from datetime import datetime
import sqlite3

HEADERS = {
    "User-Agent": "media-organiser/1.0"
}

def deg2tile(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2.0 * n)
    return xtile, ytile

def deg2pixel(lat_deg, lon_deg, zoom, tile_origin_x, tile_origin_y):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    x = (lon_deg + 180.0) / 360.0 * n * 256
    y = (1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2.0 * n * 256
    # convert to stitched image pixel (subtract origin tile)
    return int(x - tile_origin_x * 256), int(y - tile_origin_y * 256)

def get_gpx_data(gpx_filename):
    gpx = gpxpy.parse(open(gpx_filename))

    lats = []
    lons = []
    for track in gpx.tracks:
        for segment in track.segments:
            for p in segment.points:
                lats.append(p.latitude)
                lons.append(p.longitude)

    return {
        "min_lat": min(lats),
        "max_lat": max(lats),
        "min_lon": min(lons),
        "max_lon": max(lons),
        "points": [(p.latitude, p.longitude, p.time) for track in gpx.tracks
                   for seg in track.segments
                   for p in seg.points]
    }


def download_tiles(min_x, max_x, min_y, max_y, zoom, force_offline, map_database):
    tiles = {}
    for x in range(min_x, max_x + 1):
        for y in range(min_y, max_y + 1):
            tile=None
            if force_offline == False:
                url = f"https://tile.openstreetmap.org/{zoom}/{x}/{y}.png"
                r = requests.get(url, headers=HEADERS)
                r.raise_for_status()
                tile = Image.open(BytesIO(r.content))

            if tile==None and map_database != None:
                db_connection = sqlite3.connect(map_database)
                db_cursor = db_connection.cursor()

                try:
                    db_cursor.execute("SELECT t.tile_image FROM tiles t WHERE t.zoom=? AND t.x=? AND t.y=? AND t.server=?;",
                                      (zoom, x, y, "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png"))
                    result = db_cursor.fetchone()

                    if result is not None:
                        tile = Image.open(BytesIO(result[0]))

                except sqlite3.OperationalError:
                        pass

            if tile==None:
                tile=Image.new("RGB", (256,256), (0x99,0xff,0x99))
            tiles[(x, y)]=tile
    return tiles

def stitch_tiles(tiles, min_x, max_x, min_y, max_y):
    width = (max_x - min_x + 1) * 256
    height = (max_y - min_y + 1) * 256
    map_img = Image.new("RGB", (width, height))

    for (x, y), tile in tiles.items():
        map_img.paste(tile, ((x - min_x) * 256, (y - min_y) * 256))

    return map_img

def calculate_zoom(bounds, max_tiles_x=2, max_tiles_y=2, max_zoom=19, min_zoom=2):

    for zoom in range(max_zoom, min_zoom - 1, -1):
        x1, y1 = deg2tile(bounds["max_lat"], bounds["min_lon"], zoom)
        x2, y2 = deg2tile(bounds["min_lat"], bounds["max_lon"], zoom)

        tiles_x = abs(x2 - x1) + 1
        tiles_y = abs(y2 - y1) + 1

        if tiles_x <= max_tiles_x and tiles_y <= max_tiles_y:
            return zoom

    return min_zoom  # fallback

def gnss_thumbnail_and_timestamp(gpx_file, max_tiles=2, max_zoom=19, force_offline=False, map_database=None):
    data = get_gpx_data(gpx_file)

    zoom = calculate_zoom(data,max_tiles_x=max_tiles,max_tiles_y=max_tiles,max_zoom=max_zoom)

    # determine tile range
    min_x, min_y = deg2tile(data["max_lat"], data["min_lon"], zoom)
    max_x, max_y = deg2tile(data["min_lat"], data["max_lon"], zoom)

    tiles = download_tiles(min_x, max_x, min_y, max_y, zoom, force_offline, map_database)
    map_img = stitch_tiles(tiles, min_x, max_x, min_y, max_y)

    # draw track
    draw = ImageDraw.Draw(map_img)
    pixel_points = [
        deg2pixel(lat, lon, zoom, min_x, min_y)
        for lat, lon, _ in data["points"]
    ]

    draw.line(pixel_points, fill="red", width=4)

    return map_img, data["points"][0][2].timestamp()
