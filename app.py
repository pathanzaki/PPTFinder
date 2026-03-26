from flask import Flask, request, send_file, render_template, jsonify, send_from_directory
from flask_cors import CORS
from groq import Groq
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
import json, io, os, re, uuid

app = Flask(__name__)
CORS(app)

# 🔥 IMPORTANT: ENV VARIABLE USE (DON'T HARDCODE KEY)
API_KEY = os.environ.get("GROQ_API_KEY")

GENERATED_SITES_DIR = os.path.join(os.path.dirname(__file__), "generated_sites")
os.makedirs(GENERATED_SITES_DIR, exist_ok=True)

# ---------------- SAFE GROQ PPT ---------------- #

def gen_ppt_content(prompt, num_slides):
    try:
        if not API_KEY:
            raise Exception("Missing GROQ_API_KEY")

        client = Groq(api_key=API_KEY)

        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role":"system","content":"Return ONLY JSON array"},
                {"role":"user","content":prompt}
            ]
        )

        raw = res.choices[0].message.content.strip()

        if "```" in raw:
            raw = raw.split("```")[1]

        return json.loads(raw)

    except Exception as e:
        print("🔥 GROQ ERROR:", str(e))

        # ✅ FALLBACK (NO CRASH)
        slides = []
        for i in range(num_slides):
            slides.append({
                "title": f"{prompt} - Slide {i+1}",
                "slide_type": "content",
                "explanation": "Auto generated content",
                "bullets": ["Point 1","Point 2","Point 3","Point 4","Point 5"]
            })

        if slides:
            slides[0]["slide_type"] = "title"
            slides[-1]["slide_type"] = "conclusion"

        return slides

# ---------------- SIMPLE PPT BUILDER ---------------- #

def build_pptx(slides):
    prs = Presentation()

    for s in slides:
        slide = prs.slides.add_slide(prs.slide_layouts[1])

        title = slide.shapes.title
        body = slide.placeholders[1]

        title.text = s.get("title","Title")

        content = s.get("explanation","") + "\n\n"
        for b in s.get("bullets", []):
            content += f"• {b}\n"

        body.text = content

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf.read()

# ---------------- SAFE WEBSITE ---------------- #

def gen_website(prompt):
    try:
        if not API_KEY:
            raise Exception("Missing API key")

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
        print("🔥 WEBSITE ERROR:", str(e))
        return f"<h1>Error</h1><p>{str(e)}</p>"

# ---------------- ROUTES ---------------- #

@app.route("/")
def index():
    return "API running 🚀"

@app.route("/health")
def health():
    return jsonify({"status":"ok"})

@app.route("/generate", methods=["POST"])
def generate_ppt():
    try:
        data = request.get_json(force=True)

        prompt = data.get("prompt","").strip()
        num_slides = int(data.get("num_slides", 10))

        if not prompt:
            return jsonify({"error":"Enter topic"}), 400

        slides = gen_ppt_content(prompt, num_slides)
        ppt = build_pptx(slides)

        return send_file(
            io.BytesIO(ppt),
            as_attachment=True,
            download_name="presentation.pptx",
            mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )

    except Exception as e:
        print("🔥 ERROR:", str(e))
        return jsonify({"error": str(e)}), 500

@app.route("/generate-website", methods=["POST"])
def generate_website():
    try:
        data = request.get_json(force=True)
        prompt = data.get("prompt","")

        html = gen_website(prompt)

        filename = f"site_{uuid.uuid4().hex[:6]}.html"
        path = os.path.join(GENERATED_SITES_DIR, filename)

        with open(path,"w",encoding="utf-8") as f:
            f.write(html)

        return jsonify({
            "preview_url": f"/preview/{filename}",
            "download_url": f"/download-site/{filename}"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/preview/<f>")
def preview(f):
    return send_from_directory(GENERATED_SITES_DIR, f)

@app.route("/download-site/<f>")
def download(f):
    return send_from_directory(GENERATED_SITES_DIR, f, as_attachment=True)

# ---------------- RUN ---------------- #

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
