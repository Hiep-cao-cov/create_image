from flask import Flask, render_template, request, session
import os
import openai
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Initialize Flask
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "your-fallback-secret")

# Set OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route("/", methods=["GET", "POST"])
def index():
    if "attempts" not in session:
        session["attempts"] = 3
        if "prompt_history" not in session:
            session["prompt_history"] = []

    image_url = None
    error_message = None

    if request.method == "POST":
        if session["attempts"] <= 0:
            error_message = "⚠️ You have reached your 3-image limit."
        else:
            prompt = request.form["prompt"].lower()
            if any(kw in prompt for kw in ["image", "draw", "picture"]):
                try:
                    response = openai.images.generate(
                        model="dall-e-3",
                        prompt=prompt,
                        n=1,
                        size="1024x1024"
                    )
                    image_url = response.data[0].url
                    session["attempts"] -= 1
                    session["prompt_history"].append(prompt)
                except Exception as e:
                    error_message = f"Error: {str(e)}"
            else:
                error_message = "❗ Your prompt must contain one of the keywords: 'image', 'draw', or 'picture'."

    return render_template(
        "index.html", 
        image_url=image_url, 
        error_message=error_message, 
        attempts=session["attempts"],
        prompt_history=session["prompt_history"]
        )


if __name__ == '__main__':
    app.run(debug=True)
