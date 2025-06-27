from flask import Flask, request, render_template, session
import os
from dotenv import load_dotenv
import openai

load_dotenv()
app = Flask(__name__)
app.secret_key = 'your-secret-key'

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.route('/', methods=['GET', 'POST'])
def index():
    if 'prompt_count' not in session:
        session['prompt_count'] = 0

    image_url = None
    message = None

    if request.method == 'POST':
        if session['prompt_count'] >= 3:
            message = "You've reached the maximum of 3 prompts."
        else:
            prompt = request.form['prompt']
            if any(word in prompt.lower() for word in ['image', 'draw', 'picture']):
                try:
                    response = client.images.generate(
                        model="dall-e-3",
                        prompt=prompt,
                        n=1,
                        size="1024x1024"
                    )
                    image_url = response.data[0].url
                except Exception as e:
                    message = f"Error: {str(e)}"
            else:
                message = "Prompt doesn't request an image. Nothing done."
            session['prompt_count'] += 1

    return render_template("index.html", image_url=image_url, message=message, count=session['prompt_count'])

if __name__ == '__main__':
    app.run(debug=True)
