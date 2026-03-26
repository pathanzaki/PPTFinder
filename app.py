from flask import Flask, request, send_file, jsonify, send_from_directory
from flask_cors import CORS
from groq import Groq
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
import json, io, os, uuid, requests

app = Flask(__name__)

# ✅ FIXED CORS (IMPORTANT)
CORS(app, supports_credentials=True)

from flask_cors import CORS

CORS(app)

@app.before_request
def handle_options():
    if request.method == "OPTIONS":
        response = app.make_response("")
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        return response

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response

# CONFIG
API_KEY = os.environ.get("GROQ_API_KEY")
SITES_FOLDER = os.path.join(os.path.dirname(__file__), "generated_sites")
os.makedirs(SITES_FOLDER, exist_ok=True)

# COLORS
C_BG = RGBColor(10, 10, 24)
C_WHITE = RGBColor(255, 255, 255)

# ---------------- PPT DESIGN ---------------- #

def add_text(slide, text, size, x, y):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(10), Inches(2))
    p = box.text_frame.paragraphs[0]
    run = p.add_run()
    run.text = str(text)
    run.font.size = Pt(size)
    run.font.color.rgb = C_WHITE

def add_image(slide, query, x, y, w, h):
    try:
        url = f"https://source.unsplash.com/800x600/?{query}"
        img_data = requests.get(url, timeout=5).content
        img_path = "temp.jpg"

        with open(img_path, "wb") as f:
            f.write(img_data)

        slide.shapes.add_picture(img_path, Inches(x), Inches(y), Inches(w), Inches(h))
    except:
        pass

def build_pptx(slides):
    prs = Presentation()

    for s in slides:
        slide = prs.slides.add_slide(prs.slide_layouts[6])

        bg = slide.background.fill
        bg.solid()
        bg.fore_color.rgb = C_BG

        add_text(slide, s.get("title", "Title"), 40, 0.5, 0.5)
        add_text(slide, s.get("explanation",""), 18, 0.5, 2)

        add_image(slide, s.get("title","presentation"), 8, 1.5, 4, 3)

        bullets = s.get("bullets", [])
        y = 5

        for idx, b in enumerate(bullets[:5]):
            add_text(slide, f"{idx+1}. {b}", 18, 0.5, y)
            y += 0.6

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf.read()

# ---------------- AI PPT ---------------- #

def generate_slide_content(prompt, n):
    if not API_KEY:
        raise Exception("GROQ_API_KEY missing")

    try:
        client = Groq(api_key=API_KEY)

        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Return ONLY valid JSON array"},
                {"role": "user", "content": prompt}
            ]
        )

        raw = res.choices[0].message.content.strip()

        # clean markdown
        if "```" in raw:
            raw = raw.split("```")[1]

        return json.loads(raw)

    except Exception as e:
        print("GROQ ERROR:", str(e))

        # ✅ FALLBACK (VERY IMPORTANT)
        slides = []
        for i in range(n):
            slides.append({
                "title": f"{prompt} - Slide {i+1}",
                "explanation": "Auto-generated content",
                "bullets": ["Point 1", "Point 2", "Point 3"]
            })

        return slides

# ---------------- AI WEBSITE ---------------- #

def generate_website_code(prompt):
    if not API_KEY:
        return "<h1>API key missing</h1>"

    try:
        client = Groq(api_key=API_KEY)

        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role":"system","content":"Return ONLY HTML"},
                {"role":"user","content":prompt}
            ]
        )

        html = res.choices[0].message.content.strip()

        if "```" in html:
            html = html.split("```")[1]

        if not html.lower().startswith("<!doctype"):
            html = "<!DOCTYPE html>\n" + html

        return html

    except Exception as e:
        print("WEBSITE ERROR:", str(e))
        return f"<h1>Error generating website</h1><p>{str(e)}</p>"

# ---------------- ROUTES ---------------- #

@app.route("/")
def home():
    return jsonify({"message":"API running"})

@app.route("/health")
def health():
    return jsonify({"status":"ok"})

# ✅ PPT ROUTE WITH OPTIONS FIX
@app.route("/generate", methods=["POST", "OPTIONS"])
def generate_ppt():
    if request.method == "OPTIONS":
        return jsonify({"ok": True})

    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error":"Invalid JSON"}), 400

        slides = generate_slide_content(data["prompt"], data["num_slides"])
        ppt = build_pptx(slides)

        return send_file(
            io.BytesIO(ppt),
            as_attachment=True,
            download_name="presentation.pptx",
            mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ WEBSITE ROUTE WITH OPTIONS FIX
@app.route("/generate-website", methods=["POST", "OPTIONS"])
def generate_website():
    if request.method == "OPTIONS":
        return jsonify({"ok": True})

    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error":"Invalid JSON"}), 400

        html = generate_website_code(data["prompt"])

        name = f"site_{uuid.uuid4().hex[:6]}.html"
        path = os.path.join(SITES_FOLDER, name)

        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

        return jsonify({
            "preview_url": f"/preview/{name}",
            "download_url": f"/download-site/{name}"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/preview/<f>")
def preview(f):
    return send_from_directory(SITES_FOLDER, f)

@app.route("/download-site/<f>")
def download(f):
    return send_from_directory(SITES_FOLDER, f, as_attachment=True)

# ---------------- RUN ---------------- #

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
