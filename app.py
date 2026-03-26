from flask import Flask, request, send_file, jsonify, send_from_directory
from flask_cors import CORS
from groq import Groq
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
import json, io, os, uuid

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

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
    run.text = text
    run.font.size = Pt(size)
    run.font.color.rgb = C_WHITE

def build_pptx(slides):
    prs = Presentation()

    for i, s in enumerate(slides):
        slide = prs.slides.add_slide(prs.slide_layouts[6])

        # Background
        bg = slide.background.fill
        bg.solid()
        bg.fore_color.rgb = C_BG

        # Title
        add_text(slide, s["title"], 40, 0.5, 0.5)

        # Explanation
        add_text(slide, s.get("explanation",""), 18, 0.5, 2)

        bullets = s.get("bullets", [])
        y = 4

        for idx, b in enumerate(bullets[:5]):
            # Number style like your PPT
            add_text(slide, f"{idx+1}", 20, 0.5, y)
            add_text(slide, b, 18, 1.2, y)
            y += 0.7

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf.read()

# ---------------- AI PPT ---------------- #

def generate_slide_content(prompt, n):
    client = Groq(api_key=API_KEY)

    system_prompt = f"""
Create {n} slides EXACTLY like a professional course PPT.

Structure:
- Title slide
- Concept slides
- Numbered slides (1,2,3,4,5)
- KEY POINTS slide
- 01,02 format slide
- Conclusion with ✦

Each slide must have:
- title
- explanation
- bullets

Return ONLY JSON array.
"""

    res = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role":"system","content":system_prompt},
            {"role":"user","content":prompt}
        ]
    )

    raw = res.choices[0].message.content.strip()

    if "```" in raw:
        raw = raw.split("```")[1]

    return json.loads(raw)

# ---------------- AI WEBSITE ---------------- #

def generate_website_code(prompt):
    client = Groq(api_key=API_KEY)

    system = """
You are a senior frontend developer.

Generate a COMPLETE modern SaaS website.

STRICT:
- Full HTML
- CSS inside <style>
- Responsive
- Gradients, shadows, animations
- Use Google Fonts

Sections:
Navbar, Hero, Features, Stats, Testimonials, Contact, Footer

Return ONLY HTML.
"""

    res = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role":"system","content":system},
            {"role":"user","content":prompt}
        ]
    )

    html = res.choices[0].message.content.strip()

    if "```" in html:
        html = html.split("```")[1]

    if not html.lower().startswith("<!doctype"):
        html = "<!DOCTYPE html>\n" + html

    return html

# ---------------- ROUTES ---------------- #

@app.route("/")
def home():
    return jsonify({"message":"PPTFinder API running 🚀"})

@app.route("/health")
def health():
    return jsonify({"status":"ok"})

@app.route("/generate", methods=["POST"])
def generate_ppt():
    try:
        data = request.get_json(force=True)
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

@app.route("/generate-website", methods=["POST"])
def generate_website():
    try:
        data = request.get_json(force=True)
        html = generate_website_code(data["prompt"])

        name = f"site_{uuid.uuid4().hex[:6]}.html"
        path = os.path.join(SITES_FOLDER, name)

        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

        return jsonify({
            "success": True,
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
