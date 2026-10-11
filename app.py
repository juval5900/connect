import os
import platform
import sqlite3
import subprocess
import time
from flask import Flask, jsonify, render_template

app = Flask(__name__)
DB_NAME = "connectivity.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Table 1: Inventory of Dollar Universe and SAP hosts
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS server_targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_host TEXT NOT NULL,
            dest_host TEXT NOT NULL,
            label TEXT NOT NULL
        )
    """)

    # Table 2: History log of ping checks
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ping_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_id INTEGER,
            checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL,
            latency_ms REAL,
            FOREIGN KEY(target_id) REFERENCES server_targets(id)
        )
    """)

    # Seed sample hosts if empty
    cursor.execute("SELECT COUNT(*) FROM server_targets")
    if cursor.fetchone()[0] == 0:
        sample_servers = [
            ("DU_PROD_NODE01", "10.20.30.40", "DU Node 1 -> SAP PAS (PRD)"),
            ("DU_PROD_NODE01", "10.20.30.41", "DU Node 1 -> SAP AAS (PRD)"),
            ("DU_DEV_NODE01", "10.20.30.50", "DU Dev -> SAP Sandbox"),
            ("DU_PROD_NODE02", "8.8.8.8", "DU Node 2 -> External Test"),
        ]
        cursor.executemany(
            """
            INSERT INTO server_targets (source_host, dest_host, label)
            VALUES (?, ?, ?)
        """,
            sample_servers,
        )

    conn.commit()
    conn.close()


def run_ping(host):
    # Ping command parameters based on OS (Windows uses -n, Linux/macOS uses -c)
    param = "-n" if platform.system().lower() == "windows" else "-c"
    timeout_param = "-w" if platform.system().lower() == "windows" else "-W"
    command = ["ping", param, "1", timeout_param, "2", host]

    start_time = time.time()
    try:
        output = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        latency = round((time.time() - start_time) * 1000, 2)
        if output.returncode == 0:
            return "UP", latency
        else:
            return "DOWN", None
    except Exception:
        return "ERROR", None


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/targets", methods=["GET"])
def get_targets():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, source_host, dest_host, label FROM server_targets")
    rows = cursor.fetchall()
    conn.close()
    return jsonify([
        {"id": r[0], "source": r[1], "dest": r[2], "label": r[3]} for r in rows
    ])


@app.route("/api/check-connectivity", methods=["POST"])
def check_connectivity():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT id, dest_host FROM server_targets")
    targets = cursor.fetchall()

    results = []
    for target_id, dest_host in targets:
        status, latency = run_ping(dest_host)
        cursor.execute(
            """
            INSERT INTO ping_history (target_id, status, latency_ms)
            VALUES (?, ?, ?)
        """,
            (target_id, status, latency),
        )

        results.append({
            "target_id": target_id,
            "host": dest_host,
            "status": status,
            "latency_ms": latency,
        })

    conn.commit()
    conn.close()
    return jsonify({"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "data": results})


@app.route("/api/history/<int:target_id>", methods=["GET"])
def get_history(target_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT checked_at, status, latency_ms 
        FROM ping_history 
        WHERE target_id = ? 
        ORDER BY checked_at DESC LIMIT 10
    """,
        (target_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return jsonify([
        {"checked_at": r[0], "status": r[1], "latency_ms": r[2]} for r in rows
    ])


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)