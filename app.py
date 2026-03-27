from flask import Flask, request, send_file, jsonify, send_from_directory
from flask_cors import CORS
from groq import Groq
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
import json, io, os, re, uuid

app = Flask(__name__)

# ✅ CORS FIX
CORS(app)

@app.after_request
def after(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response

# ✅ ENV API KEY (IMPORTANT)
API_KEY = os.environ.get("GROQ_API_KEY")

# FOLDER
GENERATED_SITES_DIR = os.path.join(os.path.dirname(__file__), "generated_sites")
os.makedirs(GENERATED_SITES_DIR, exist_ok=True)

# COLORS
WHITE = RGBColor(255,255,255)
BLACK = RGBColor(0,0,0)

# ═════════════════════════════════════════════════════
# PPT DESIGN
# ═════════════════════════════════════════════════════

def add_text(slide, text, size, x, y):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(10), Inches(2))
    p = box.text_frame.paragraphs[0]
    run = p.add_run()
    run.text = str(text)
    run.font.size = Pt(size)
    run.font.color.rgb = WHITE

def build_pptx(slides):
    prs = Presentation()

    for s in slides:
        slide = prs.slides.add_slide(prs.slide_layouts[6])

        # background
        bg = slide.background.fill
        bg.solid()
        bg.fore_color.rgb = BLACK

        # title
        add_text(slide, s.get("title","Title"), 40, 0.5, 0.5)

        # explanation
        add_text(slide, s.get("explanation",""), 18, 0.5, 2)

        # bullets
        y = 5
        for i,b in enumerate(s.get("bullets",[])[:5]):
            add_text(slide, f"{i+1}. {b}", 16, 0.5, y)
            y += 0.6

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf.read()

# ═════════════════════════════════════════════════════
# GROQ PPT
# ═════════════════════════════════════════════════════

def gen_ppt_content(prompt, n):
    if not API_KEY:
        raise Exception("GROQ_API_KEY missing")

    try:
        client = Groq(api_key=API_KEY)

        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role":"system","content":"Return ONLY JSON array"},
                {"role":"user","content":f"Create {n} slides about {prompt}"}
            ]
        )

        raw = res.choices[0].message.content.strip()

        if "```" in raw:
            raw = raw.split("```")[1]

        try:
            return json.loads(raw)
        except Exception:
            print("BAD JSON:", raw)
            raise Exception("Invalid AI JSON")

    except Exception as e:
        print("GROQ ERROR:", e)

        # fallback
        slides = []
        for i in range(n):
            slides.append({
                "title": f"{prompt} - Slide {i+1}",
                "explanation": "Auto generated content",
                "bullets": ["Point 1","Point 2","Point 3"]
            })
        return slides

# ═════════════════════════════════════════════════════
# GROQ WEBSITE
# ═════════════════════════════════════════════════════

def gen_website(prompt):
    if not API_KEY:
        return {
            "html": f"<h1>{prompt}</h1><p>No API key</p>",
            "site_title": prompt,
            "description": "fallback"
        }

    try:
        client = Groq(api_key=API_KEY)

        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role":"system","content":"Return JSON with html"},
                {"role":"user","content":prompt}
            ]
        )

        raw = res.choices[0].message.content.strip()

        if "```" in raw:
            raw = raw.split("```")[1]

        try:
            return json.loads(raw)
        except Exception:
            print("WEBSITE JSON ERROR:", raw)
            raise Exception("Invalid website JSON")

    except Exception as e:
        print("WEBSITE ERROR:", e)
        return {
            "html": f"<h1>{prompt}</h1><p>Error generating</p>",
            "site_title": prompt,
            "description": "error fallback"
        }

# ═════════════════════════════════════════════════════
# ROUTES
# ═════════════════════════════════════════════════════

@app.route("/")
def home():
    return jsonify({"message":"API Running"})

@app.route("/health")
def health():
    return jsonify({"status":"ok"})

# PPT
@app.route("/generate", methods=["POST","OPTIONS"])
def generate_ppt():
    if request.method == "OPTIONS":
        return jsonify({"ok": True})

    data = request.get_json()
    prompt = data.get("prompt","").strip()
    n = int(data.get("num_slides",12))

    if not prompt:
        return jsonify({"error":"Enter topic"}),400

    try:
        slides = gen_ppt_content(prompt,n)
        ppt = build_pptx(slides)

        return send_file(
            io.BytesIO(ppt),
            as_attachment=True,
            download_name="presentation.pptx",
            mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )

    except Exception as e:
        return jsonify({"error":str(e)}),500

# WEBSITE
@app.route("/generate-website", methods=["POST","OPTIONS"])
def generate_website():
    if request.method == "OPTIONS":
        return jsonify({"ok": True})

    data = request.get_json()
    prompt = data.get("prompt","").strip()

    if not prompt:
        return jsonify({"error":"Enter prompt"}),400

    try:
        result = gen_website(prompt)
        html = result.get("html","")

        filename = f"site_{uuid.uuid4().hex[:6]}.html"
        path = os.path.join(GENERATED_SITES_DIR, filename)

        with open(path,"w",encoding="utf-8") as f:
            f.write(html)

        return jsonify({
            "html": html,
            "filename": filename,
            "site_title": result.get("site_title",""),
            "description": result.get("description","")
        })

    except Exception as e:
        return jsonify({"error":str(e)}),500

@app.route("/download-site/<f>")
def download(f):
    return send_from_directory(GENERATED_SITES_DIR, f, as_attachment=True)

# RUN
if __name__ == "__main__":
    port = int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0", port=port)
