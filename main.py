from flask import Flask, jsonify, request
import subprocess
import requests
import os
import logging
from dotenv import dotenv_values

config = dotenv_values(".env")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VULTR_API_KEY = os.environ.get("VULTR_API_KEY")
if not VULTR_API_KEY:
    logger.critical("VULTR_API_KEY environment var not found. Did you export VULTR_API_KEY=...?")
    exit(1)

TERRAFORM_DIR = "../vultr_deployment"  # Ruta al directorio donde está el estado de Terraform

def get_server_id():
    try:
        server_id = subprocess.check_output(["terraform", "-chdir=" + TERRAFORM_DIR, "output", "-raw", "server_id"]).decode().strip()
        return server_id
    except subprocess.CalledProcessError as e:
        logger.error("Error getting server_id: %s", e)
        return None

def vultr_request(method, url_path, **kwargs):
    headers = {
        "Authorization": f"Bearer {VULTR_API_KEY}",
        "Content-Type": "application/json"
    }
    url = f"https://api.vultr.com/v2{url_path}"
    return requests.request(method, url, headers=headers, **kwargs)

def authorize(req):
    token = req.headers.get("Authorization", "")
    return token == f"Bearer {VULTR_API_KEY}"

@app.route('/status', methods=['GET'])
def status():
    server_id = get_server_id()
    if not server_id:
        return jsonify({"status": "error", "detail": "Server ID not found"}), 500

    response = vultr_request("GET", f"/instances/{server_id}")
    if response.status_code == 200:
        power_status = response.json().get("instance", {}).get("power_status")
        return jsonify({"status": "online" if power_status == "running" else "offline"})
    return jsonify({"status": "error", "detail": response.text}), response.status_code

@app.route('/start', methods=['POST'])
def start():
    if not authorize(request):
        return jsonify({"error": "Invalid API token"}), 403

    server_id = get_server_id()
    if not server_id:
        return jsonify({"status": "error", "detail": "Server ID not found"}), 500

    response = vultr_request("POST", f"/instances/{server_id}/start")
    if response.status_code == 204:
        return jsonify({"status": "started"})
    return jsonify({"status": "error", "detail": response.text}), response.status_code

@app.route('/shutdown', methods=['POST'])
def shutdown():
    if not authorize(request):
        return jsonify({"error": "Invalid API token"}), 403

    server_id = get_server_id()
    if not server_id:
        return jsonify({"status": "error", "detail": "Server ID not found"}), 500

    response = vultr_request("POST", f"/instances/{server_id}/halt")
    if response.status_code == 204:
        return jsonify({"status": "shutdown initiated"})
    return jsonify({"status": "error", "detail": response.text}), response.status_code

@app.route('/apply', methods=['POST'])
def apply():
    try:
        subprocess.check_call(["terraform", f"-chdir={TERRAFORM_DIR}","apply", "-auto-approve"])
        return jsonify({"status": "applied"})
    except subprocess.CalledProcessError as e:
        return jsonify({"status": "error", "detail": str(e)}), 500

@app.route('/destroy', methods=['POST'])
def destroy():
    try:
        subprocess.check_call(["terraform", f"-chdir={TERRAFORM_DIR}","destroy","-auto-approve"])
        return jsonify({"status": "destroyed"})
    except:
        return jsonify({"status": "error", "detaul": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)

