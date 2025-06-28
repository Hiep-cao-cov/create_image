from flask import Flask, render_template, request, redirect, session, url_for, flash
from dotenv import load_dotenv
import os
import openai
import smtplib
from email.mime.text import MIMEText

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
openai.api_key = os.getenv("OPENAI_API_KEY")

valid_teams = ["team 1", "team 2", "team 3", "team 4", "team 5", "team 6"]

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip().lower()
        if username in valid_teams:
            session["username"] = username
            session["attempts"] = 3
            session["prompts"] = []
            session["images"] = []
            return redirect(url_for("index"))
        else:
            return render_template("login.html", error="Team name is not valid.")
    return render_template("login.html")

@app.route("/index", methods=["GET", "POST"])
def index():
    if "username" not in session:
        return redirect(url_for("login"))

    error = None
    image_url = None

    if request.method == "POST":
        if session["attempts"] <= 0:
            error = "You’ve reached your image creation limit (3)."
        else:
            prompt = request.form["prompt"].strip()
            if any(kw in prompt.lower() for kw in ["image", "draw", "picture"]):
                try:
                    response = openai.images.generate(
                        model="dall-e-3",
                        prompt=prompt,
                        n=1,
                        size="1024x1024"
                    )
                    image_url = response.data[0].url
                    session["attempts"] -= 1
                    session["prompts"].append(prompt)
                    session["images"].append(image_url)
                except Exception as e:
                    error = f"OpenAI error: {str(e)}"
            else:
                error = "Prompt must include: image, draw, or picture."

    return render_template("index.html",
                           username=session["username"],
                           attempts=session["attempts"],
                           prompts=session["prompts"],
                           images=session["images"],
                           error=error)

@app.route("/submit", methods=["POST"])
def submit():
    if "username" not in session:
        return redirect(url_for("login"))

    index = int(request.form.get("selected_image", -1))

    if index < 0 or index >= len(session["images"]):
        flash("Invalid image selected.")
        return redirect(url_for("index"))

    selected_image = session["images"][index]
    selected_prompt = session["prompts"][index]
    username = session["username"]

    send_email(username, selected_prompt, selected_image)
    session.clear()
    return render_template("submitted.html", username=username)

def send_email(username, prompt, image_url):
    sender = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")
    recipient = os.getenv("EMAIL_RECIPIENT")

    subject = f"[Image Submission] From {username}"
    body = f"Team: {username}\n\nPrompt:\n{prompt}\n\nImage URL:\n{image_url}"

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, recipient, msg.as_string())
            print("✅ Email sent.")
    except Exception as e:
        print("❌ Email failed:", e)

if __name__ == "__main__":
    app.run(debug=True)
