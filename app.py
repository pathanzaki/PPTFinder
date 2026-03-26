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
C_BG_DARK = RGBColor(10,10,24)
C_BG_LIGHT = RGBColor(240,242,255)
C_WHITE = RGBColor(255,255,255)

# PPT HELPER
def add_text(slide, text, size=28, x=1, y=1):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(10), Inches(2))
    p = box.text_frame.paragraphs[0]
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.color.rgb = C_WHITE

def build_pptx(slides_data):
    prs = Presentation()

    for i, s in enumerate(slides_data):
        slide = prs.slides.add_slide(prs.slide_layouts[6])

        bg = slide.background.fill
        bg.solid()
        bg.fore_color.rgb = C_BG_DARK if i % 2 == 0 else C_BG_LIGHT

        add_text(slide, s["title"], 36, 0.8, 0.8)
        add_text(slide, s.get("explanation",""), 18, 0.8, 2)

        y = 4
        for b in s.get("bullets", [])[:5]:
            add_text(slide, f"• {b}", 16, 1, y)
            y += 0.6

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf.read()

# AI PPT
def generate_slide_content(prompt, n):
    client = Groq(api_key=API_KEY)

    system_prompt = f"""
Generate {n} professional slides.

Each slide must include:
- title
- explanation (3-4 lines)
- 5 bullet points

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

# AI WEBSITE (ONLY ONE FUNCTION)
def generate_website_code(prompt):
    client = Groq(api_key=API_KEY)

    system = """
You are an elite UI/UX designer.

Generate a modern SaaS website.

Include navbar, hero, features, stats, testimonials, contact form, footer.

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

# ROUTES
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

# RUN
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
