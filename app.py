from flask import Flask, request, redirect, url_for, render_template_string, send_file
import os, math
from datetime import datetime
import pandas as pd

# ---------------- CONFIG ----------------
PRICE_PER_HOUR = 100
DATABASE_URL = os.environ.get("DATABASE_URL")  # ใช้ตอน deploy cloud

app = Flask(__name__)
app.secret_key = "enterprise_secret"

# ---------------- DATABASE ----------------
if DATABASE_URL:
    import psycopg2
    def get_conn():
        return psycopg2.connect(DATABASE_URL)
else:
    import sqlite3
    DB="pos.db"
    def get_conn():
        return sqlite3.connect(DB)

# ---------------- INIT ----------------
conn=get_conn()
cur=conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS sessions(
id SERIAL PRIMARY KEY,
start_time TEXT,
end_time TEXT,
hours INTEGER,
total REAL
)
""")
conn.commit()
conn.close()

# ---------------- HOME ----------------
@app.route("/")
def home():
    return redirect("/pos")

# ---------------- POS ----------------
@app.route("/pos", methods=["GET","POST"])
def pos():
    global PRICE_PER_HOUR
    message=""
    conn=get_conn()
    cur=conn.cursor()

    if request.method=="POST":
        PRICE_PER_HOUR=int(request.form.get("price",PRICE_PER_HOUR))

        if request.form["action"]=="start":
            cur.execute("INSERT INTO sessions(start_time) VALUES (%s)" if DATABASE_URL else
                        "INSERT INTO sessions(start_time) VALUES (?)",
                        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))
            message="เริ่มเวลาแล้ว"

        if request.form["action"]=="end":
            cur.execute("SELECT id,start_time FROM sessions WHERE end_time IS NULL ORDER BY id DESC LIMIT 1")
            s=cur.fetchone()
            if s:
                start=datetime.strptime(s[1],"%Y-%m-%d %H:%M:%S")
                hours=math.ceil((datetime.now()-start).total_seconds()/3600)
                total=hours*PRICE_PER_HOUR
                cur.execute(
                    "UPDATE sessions SET end_time=%s,hours=%s,total=%s WHERE id=%s" if DATABASE_URL else
                    "UPDATE sessions SET end_time=?,hours=?,total=? WHERE id=?",
                    (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),hours,total,s[0])
                )
                message=f"คิดเงิน {hours} ชม = {total} บาท"

        conn.commit()

    today=datetime.now().strftime("%Y-%m-%d")
    cur.execute("SELECT SUM(total) FROM sessions WHERE start_time LIKE %s" if DATABASE_URL else
                "SELECT SUM(total) FROM sessions WHERE start_time LIKE ?",
                (f"{today}%",))
    total_today=cur.fetchone()[0] or 0
    conn.close()

    return render_template_string("""
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>POS Enterprise</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
body{background:#111;color:white;text-align:center;font-family:Arial}
button{font-size:28px;padding:20px;margin:10px;border-radius:12px;border:none}
.start{background:#00c853}
.end{background:#d50000}
input{font-size:26px;padding:10px;text-align:center}
.box{background:#222;padding:20px;margin:20px;border-radius:15px}
</style>
</head>
<body>
<h1>SPORTS SHOP POS</h1>

<form method="post">
<input name="price" value="{{price}}"> บาท/ชม<br>
<button class="start" name="action" value="start">เริ่ม</button>
<button class="end" name="action" value="end">คิดเงิน</button>
</form>

<h2>{{message}}</h2>

<div class="box">
<h2>ยอดวันนี้</h2>
<h1>{{total_today}} บาท</h1>
</div>

<a href="/dashboard">Dashboard</a> |
<a href="/report">Report</a>

</body>
</html>
""",price=PRICE_PER_HOUR,total_today=total_today,message=message)

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    conn=get_conn()
    df=pd.read_sql_query("""
    SELECT substr(start_time,1,10) as day,
    SUM(total) as total
    FROM sessions
    WHERE end_time IS NOT NULL
    GROUP BY day ORDER BY day
    """,conn)
    conn.close()

    return render_template_string("""
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <h2>Dashboard รายได้</h2>
    <canvas id="c"></canvas>
    <script>
    new Chart(document.getElementById("c"),{
        type:"bar",
        data:{
            labels:{{labels|safe}},
            datasets:[{label:"รายได้",data:{{values|safe}}}]
        }
    })
    </script>
    <br><a href="/pos">กลับ</a>
    """,labels=df["day"].tolist(),values=df["total"].tolist())

# ---------------- REPORT ----------------
@app.route("/report")
def report():
    conn=get_conn()
    df=pd.read_sql_query("SELECT * FROM sessions",conn)
    conn.close()
    return df.to_html()+"<br><a href='/export'>Export Excel</a><br><a href='/pos'>กลับ</a>"

@app.route("/export")
def export():
    conn=get_conn()
    df=pd.read_sql_query("SELECT * FROM sessions",conn)
    df.to_excel("report.xlsx",index=False)
    conn.close()
    return send_file("report.xlsx",as_attachment=True)

# ---------------- RUN ----------------
if __name__=="__main__":
    app.run(host="0.0.0.0",port=5000)