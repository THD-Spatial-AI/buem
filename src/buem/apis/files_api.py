import os

from flask import Blueprint, current_app, jsonify, send_from_directory

bp = Blueprint("files_api", __name__, url_prefix="/api/files")

# directory to store/download large results (set via env BUEM_RESULTS_DIR or fallback)
RESULTS_DIR = os.environ.get("BUEM_RESULTS_DIR", r"D:\test\buem\src\buem\results")

@bp.route("/<path:filename>", methods=["GET"])
def download_file(filename):
    if not os.path.isdir(RESULTS_DIR):
        try:
            os.makedirs(RESULTS_DIR, exist_ok=True)
        except Exception:
            current_app.logger.exception("Failed to create results dir")
            return jsonify({"error": "server_error"}), 500
    # For .gz files, explicitly set mimetype to application/gzip so that
    # Flask does NOT add a Content-Encoding: gzip header.  Without this,
    # Python's mimetypes returns ('application/json', 'gzip') for .json.gz
    # which causes Flask to set Content-Encoding: gzip — the browser then
    # transparently decompresses the response, corrupting the download.
    mimetype = "application/gzip" if filename.endswith(".gz") else None
    return send_from_directory(
        RESULTS_DIR, filename, as_attachment=True, mimetype=mimetype,
    )