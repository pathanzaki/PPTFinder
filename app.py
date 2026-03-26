from flask import Flask, request, send_file, jsonify, send_from_directory
from flask_cors import CORS
from groq import Groq
from pptx import Presentation
import json, io, os, uuid

# ─────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────
app = Flask(__name__)

# ✅ CORS (FIXED PROPERLY)
CORS(app, supports_credentials=True)

@app.after_request
def after_request(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────
API_KEY = os.environ.get("GROQ_API_KEY")
SITES_FOLDER = "generated_sites"
os.makedirs(SITES_FOLDER, exist_ok=True)

# ─────────────────────────────────────────
# PPT GENERATION
# ─────────────────────────────────────────
def build_ppt(slides_data):
    prs = Presentation()

    for slide_data in slides_data:
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = slide_data["title"]

        content = slide.placeholders[1]
        text = slide_data["explanation"] + "\n\n"

        for b in slide_data["bullets"]:
            text += f"• {b}\n"

        content.text = text

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf

def generate_slides(prompt, num):
    try:
        client = Groq(api_key=API_KEY)

        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Return JSON slides"},
                {"role": "user", "content": prompt}
            ]
        )

        data = res.choices[0].message.content.strip()

        if "```" in data:
            data = data.split("```")[1]

        return json.loads(data)

    except Exception as e:
        print("GROQ ERROR:", str(e))
        return [{
            "title": "Error",
            "explanation": "AI failed",
            "bullets": ["Try again"]
        }]

# ─────────────────────────────────────────
# WEBSITE GENERATION
# ─────────────────────────────────────────
def generate_website_code(prompt):
    client = Groq(api_key=API_KEY)

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "Return ONLY full HTML page."},
            {"role": "user", "content": prompt}
        ]
    )

    html = response.choices[0].message.content.strip()

    if "```" in html:
        html = html.split("```")[1]

    if not html.lower().startswith("<!doctype"):
        html = "<!DOCTYPE html>\n" + html

    return html

# ─────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────

@app.route("/")
def home():
    return jsonify({"message": "PPTFinder API is running 🚀"})

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

# ✅ HANDLE PREFLIGHT REQUESTS (CORS FIX)
@app.route('/generate', methods=['OPTIONS'])
@app.route('/generate-website', methods=['OPTIONS'])
def handle_options():
    return '', 200

@app.route("/generate", methods=["POST"])
def generate_ppt():
    try:
        data = request.get_json(force=True)

        prompt = data.get("prompt", "")
        num = int(data.get("num_slides", 10))

        slides = generate_slides(prompt, num)
        ppt = build_ppt(slides)

        return send_file(
            ppt,
            as_attachment=True,
            download_name="presentation.pptx",
            mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )

    except Exception as e:
        print("ERROR:", str(e))   # 👈 VERY IMPORTANT
        return jsonify({"error": str(e)}), 500


@app.route("/generate-website", methods=["POST"])
def generate_site():
    try:
        data = request.get_json(force=True)
        prompt = data.get("prompt", "")

        html = generate_website_code(prompt)

        filename = f"site_{uuid.uuid4().hex[:6]}.html"
        filepath = os.path.join(SITES_FOLDER, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)

        return jsonify({
            "success": True,
            "preview_url": f"/preview/{filename}",
            "download_url": f"/download-site/{filename}"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/preview/<filename>")
def preview_site(filename):
    return send_from_directory(SITES_FOLDER, filename)


@app.route("/download-site/<filename>")
def download_site(filename):
    return send_from_directory(
        SITES_FOLDER,
        filename,
        as_attachment=True,
        download_name=filename.replace("site_", "website_")
    )

# ─────────────────────────────────────────
# RUN
# ─────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Running on port {port}")
    app.run(host="0.0.0.0", port=port)
