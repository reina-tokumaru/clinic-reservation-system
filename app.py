from flask import Flask, render_template, request, redirect, session, jsonify
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = Flask(__name__)
app.secret_key = "dev-secret-key"

reservations = []

CLINICS = [
    {"id": 1, "name": "赤羽中央総合病院"},
    {"id": 2, "name": "順天堂医院"},
    {"id": 3, "name": "北区クリニック"},
    {"id": 4, "name": "東京医科大学病院"},
    {"id": 5, "name": "板橋メディカルセンター"},
]

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # フォームからデータを取得
        name = request.form.get("patient_name")
        date = request.form.get("reservation_date")
        time = request.form.get("time_slot")

        reservations.append({
            "name": name,
            "date": date,
            "time": time,
            "status": "予約済み"
        })

        return redirect("/")

    return render_template("index.html", reservations=reservations)

#検索
@app.route("/search", methods=["GET", "POST"])
def search():
    if request.method == "POST":
        session["clinic"] = request.form.get("clinic")
        return redirect("/schedule")
    clinic = request.args.get("clinic")
    results = []
    if clinic:
        results = [
            {"id": 1, "name": f"{clinic}内科"},
            {"id": 2, "name": f"{clinic}クリニック"},
            {"id": 3, "name": f"{clinic}総合病院"},
        ]
    return render_template("search.html", clinic=clinic, results=results, step=1)


#日時
@app.route("/schedule", methods=["GET", "POST"])
def schedule():
    clinic_name = session.get("clinic")
    clinic_id = session.get("clinic_id")

    dept_q = request.args.get("dept")
    clinic_id_q = request.args.get("clinic_id")
    if clinic_id_q:
        session["clinic_id"] = clinic_id_q
    if dept_q:
        session["department"] = dept_q

    if request.method == "POST":
        dept_f = request.form.get("dept")
        if dept_f:
            session["department"] = dept_f
            return redirect("/schedule") 

        date = request.form.get("date")
        if date:
            session["date"] = date
            return redirect("/patient")

    return render_template(
        "schedule.html",
        step=2,
        clinic={"id": clinic_id, "name": clinic_name} if clinic_name else None,
        department=session.get("department"),
        date=session.get("date"),
    )


#病院詳細ページ
@app.route("/schedule/<int:id>", methods=["GET", "POST"])
def schedule_with_id(id):
    clinics = [
        {"id": 1, "name": "赤羽中央総合病院"},
        {"id": 2, "name": "順天堂医院"},
        {"id": 3, "name": "北区クリニック"},
        {"id": 4, "name": "東京医科大学病院"},
        {"id": 5, "name": "板橋メディカルセンター"},
    ]
    clinic = next((c for c in clinics if c["id"] == id), None)
    if request.method == "POST":
        date = request.form.get("date")
        time = request.form.get("time")
        return render_template("reserve_complete.html", clinic=clinic, date=date, time=time)
    return render_template("schedule.html", clinic=clinic, step=2)

#最終確認
@app.route("/confirm")
def confirm():
    return render_template(
        "confirm.html", step=4,
        clinic=session.get("clinic"),
        date=session.get("date"),
        patient=session.get("patient")
    )

#患者
@app.route("/patient", methods=["GET", "POST"])
def patient():
    if request.method == "POST":
        session["patient"] = {
            "name": request.form.get("name"),
            "email": request.form.get("email")
        }
        return redirect("/confirm")

    return render_template(
        "patient.html", step=3,
        patient=session.get("patient")
    )

#予約完了
@app.route("/complete", methods=["POST"])
def complete():
    # 本来はここでDB保存・メール送信
    session.clear()
    return render_template("complete.html", step=5)

@app.route("/suggest")
def suggest():
    q = request.args.get("q", "")
    results = [c["name"] for c in CLINICS if q.lower() in c["name"].lower()]
    return jsonify(results[:5])

DEPARTMENTS = [
    "内科", "外科", "小児科", "耳鼻咽喉科", "皮膚科", "眼科",
    "整形外科", "婦人科", "泌尿器科", "精神科", "心療内科",
    "脳神経外科", "循環器内科", "消化器内科", "呼吸器内科"
]

#病院確定
@app.route("/clinic/<int:id>")
def clinic_detail(id):
    name = request.args.get("name")
    clinic = {"id": id, "name": name}
    session["clinic"] = name

    return render_template(
        "clinic_detail.html",
        clinic=clinic,
        departments=DEPARTMENTS,
        step=1
    )

@app.route("/chat")
def chat():
    return render_template("chat.html", step=1)
    
@app.route("/api/chat", methods=["POST"])
def chat_api():
    data = request.get_json(silent=True) or {}
    user_message = (data.get("message") or "").strip()
    if not user_message:
        return jsonify({"error": "empty message"}), 400

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "あなたは医療トリアージAIです。"
                    "以下の診療科リストの中から、最も適切な診療科を必ず1つだけ選んでください。"
                    "【診療科リスト】"
                    "内科、外科、小児科、耳鼻咽喉科、皮膚科、眼科、整形外科、婦人科、泌尿器科、精神科、心療内科、脳神経外科、循環器内科、消化器内科、呼吸器内科。"
                    "出力は必ず JSON のみ。形式は {\"department\":\"string\",\"reason\":\"string\",\"note\":\"string\"}。"
                    "department には診療科リストの中の名称のみを入れること。"
                    "前置き・説明・余計な文章は禁止。"
                )
            },
            {"role": "user", "content": user_message}
        ],
        temperature=0.3
    )

    msg = response.choices[0].message
    if isinstance(msg.content, list):
        raw = "".join([c.text for c in msg.content if hasattr(c, "text")])
    else:
        raw = msg.content or ""

    import re, json
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        return jsonify({"error": "invalid json format", "raw": raw}), 500

    parsed = json.loads(match.group(0))
    return jsonify(parsed)
                                        
if __name__ == "__main__":
    app.run(debug=True)
