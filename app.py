import sqlite3
import time
from checks import (
    run_dns_check,
    run_http_check,
    run_icmp_check,
    run_tcp_check,
)
from flask import Flask, abort, jsonify, render_template

app = Flask(__name__)
DB_NAME = "connectivity.db"

# Data catalogs (To be integrated into DB tables in upcoming phase)
SAFRAN_COMPANIES = {
    "SLS": {
        "id": "SLS",
        "name": "Safran Landing Systems",
        "desc": "Landing gears, wheels, and braking systems",
    },
    "SG": {
        "id": "SSA",
        "name": "Safran Group",
        "desc": "Corporate central systems and shared services",
    },
    "SAE": {
        "id": "SAE",
        "name": "Safran Aircraft Engines",
        "desc": "Commercial & military aircraft propulsion engines",
    },
    "SEP": {
        "id": "SEP",
        "name": "Safran Electrical & Power",
        "desc": "Electrical wiring interconnect systems and power",
    },
    "SHE": {
        "id": "SHE",
        "name": "Safran Helicopter Engines",
        "desc": "Turboshaft engines for civil and defense helicopters",
    },
    "SPU": {
        "id": "SPU",
        "name": "Safran Power Units",
        "desc": "Auxiliary power units (APU) and starting systems",
    },
}

PLACEHOLDER_SIDS = [
    {
        "sid": "PR1",
        "instance": "00",
        "hostType": "PAS",
        "desc": "Primary Application Server",
    },
    {
        "sid": "PR1",
        "instance": "01",
        "hostType": "AAS",
        "desc": "Additional Application Server",
    },
    {
        "sid": "PR1",
        "instance": "02",
        "hostType": "AAS",
        "desc": "Batch & Background Jobs",
    },
    {
        "sid": "PR1",
        "instance": "00",
        "hostType": "CS",
        "desc": "Central Services (ASCS/ERS)",
    },
    {
        "sid": "PR1",
        "instance": "00",
        "hostType": "GW",
        "desc": "Standalone RFC Gateway",
    },
    {
        "sid": "PR1",
        "instance": "00",
        "hostType": "DB",
        "desc": "HANA Primary Host",
    },
]


def get_db_connection():
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    return conn


def init_db():
    conn = get_db_connection()
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


# ----------------- Page View Routes -----------------


@app.route("/")
def home():
    """Level 1: Displays the 6 Safran Company Tiles."""
    return render_template(
        "companies.html", companies=list(SAFRAN_COMPANIES.values())
    )


@app.route("/company/<company_id>")
def show_sids(company_id):
    """Level 2: Displays SID selection tiles for the chosen company."""
    company = SAFRAN_COMPANIES.get(company_id.upper())
    if not company:
        abort(404)
    return render_template("sids.html", company=company, sids=PLACEHOLDER_SIDS)


@app.route("/company/<company_id>/sid/<sid>/<host_type>")
def show_dashboard(company_id, sid, host_type):
    """Level 3: Live Connectivity Dashboard for the target SID."""
    company = SAFRAN_COMPANIES.get(company_id.upper())
    if not company:
        # Fallback if unknown ID is passed
        company = {"id": company_id, "name": company_id, "desc": ""}

    return render_template(
        "dashboard.html",
        company=company,
        sid=sid,
        host_type=host_type,
    )


# ----------------- Probing API Endpoints -----------------


@app.route("/api/targets", methods=["GET"])
def get_targets():
    conn = get_db_connection()
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
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, dest_host, port, check_type FROM server_targets")
    targets = cursor.fetchall()
    conn.close()

    results = []
    history_records = []

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

        history_records.append((target_id, status, latency, details))
        results.append({
            "target_id": target_id,
            "status": status,
            "latency_ms": latency,
            "details": details,
        })

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.executemany(
        """
        INSERT INTO connectivity_history (target_id, status, latency_ms, details)
        VALUES (?, ?, ?, ?)
    """,
        history_records,
    )
    conn.commit()
    conn.close()

    return jsonify(
        {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "data": results}
    )


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5050, debug=True)