import sqlite3
import time
from checks import (
    run_dns_check,
    run_http_check,
    run_icmp_check,
    run_tcp_check,
)
from flask import Flask, jsonify, render_template

app = Flask(__name__)
DB_NAME = "connectivity.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS server_targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_host TEXT NOT NULL,
            dest_host TEXT NOT NULL,
            port INTEGER,
            check_type TEXT NOT NULL,
            label TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS connectivity_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_id INTEGER,
            checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL,
            latency_ms REAL,
            details TEXT,
            FOREIGN KEY(target_id) REFERENCES server_targets(id)
        )
    """)

    cursor.execute("SELECT COUNT(*) FROM server_targets")
    if cursor.fetchone()[0] == 0:
        sample_servers = [
            (
                "DU_PROD_NODE01",
                "10.20.30.40",
                3300,
                "TCP_PORT",
                "SAP Gateway (sapgw00)",
            ),
            (
                "DU_PROD_NODE01",
                "10.20.30.40",
                3600,
                "TCP_PORT",
                "SAP Message Server (sapmsPRD)",
            ),
            (
                "DU_PROD_NODE01",
                "10.20.30.40",
                None,
                "PING",
                "SAP PAS Host OS Ping",
            ),
            (
                "DU_PROD_NODE01",
                "sap-prd-app01.corp.local",
                None,
                "DNS",
                "SAP Host DNS & Reverse PTR",
            ),
            (
                "DU_PROD_NODE01",
                "10.20.30.40",
                8000,
                "HTTP_ICM",
                "SAP ICM Ping (/sap/public/ping)",
            ),
            (
                "SAP_PAS_HOST",
                "10.20.30.10",
                10600,
                "TCP_PORT",
                "Dollar Universe IO Engine (DUAS)",
            ),
            (
                "SAP_PAS_HOST",
                "10.20.30.10",
                4184,
                "TCP_PORT",
                "Univiewer Management Server (UVMS)",
            ),
        ]
        cursor.executemany(
            """
            INSERT INTO server_targets (source_host, dest_host, port, check_type, label)
            VALUES (?, ?, ?, ?, ?)
        """,
            sample_servers,
        )

    conn.commit()
    conn.close()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/targets", methods=["GET"])
def get_targets():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, source_host, dest_host, port, check_type, label FROM"
        " server_targets"
    )
    rows = cursor.fetchall()
    conn.close()
    return jsonify([
        {
            "id": r[0],
            "source": r[1],
            "dest": r[2],
            "port": r[3],
            "type": r[4],
            "label": r[5],
        }
        for r in rows
    ])


@app.route("/api/check-connectivity", methods=["POST"])
def check_connectivity():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, dest_host, port, check_type FROM server_targets")
    targets = cursor.fetchall()

    results = []
    for target_id, dest_host, port, check_type in targets:
        if check_type == "PING":
            status, latency, details = run_icmp_check(dest_host)
        elif check_type == "TCP_PORT":
            status, latency, details = run_tcp_check(dest_host, port)
        elif check_type == "DNS":
            status, latency, details = run_dns_check(dest_host)
        elif check_type == "HTTP_ICM":
            status, latency, details = run_http_check(dest_host, port)
        else:
            status, latency, details = "UNKNOWN", None, "Unrecognized test type"

        cursor.execute(
            """
            INSERT INTO connectivity_history (target_id, status, latency_ms, details)
            VALUES (?, ?, ?, ?)
        """,
            (target_id, status, latency, details),
        )

        results.append({
            "target_id": target_id,
            "status": status,
            "latency_ms": latency,
            "details": details,
        })

    conn.commit()
    conn.close()
    return jsonify(
        {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "data": results}
    )


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)