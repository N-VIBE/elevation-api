from flask import Flask, request, jsonify
from elevation import get_elevation_laz

app = Flask(__name__)

@app.route("/elevation", methods=["GET"])
def elevation():
    try:
        lat = float(request.args.get("lat"))
        lon = float(request.args.get("lon"))
        radius = float(request.args.get("radius", 10.0))
    except Exception:
        return jsonify({"status": "error", "message": "Invalid or missing parameters"}), 400

    laz_folder = "./data"
    elevation, message = get_elevation_laz(laz_folder, lat, lon, radius)

    if elevation is None:
        return jsonify({"status": "error", "message": message}), 404

    return jsonify({
        "status": "success",
        "latitude": lat,
        "longitude": lon,
        "elevation": elevation
    })
