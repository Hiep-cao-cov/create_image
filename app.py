from flask import Flask, render_template, request, redirect, session, url_for, flash
# No need for dotenv.load_dotenv() on Render
import os
import openai
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart # Good practice for more complex emails (HTML/plain)

# No load_dotenv() when deploying to Render
# load_dotenv() # <--- REMOVE THIS LINE FOR RENDER DEPLOYMENT

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
openai.api_key = os.getenv("OPENAI_API_KEY")

# --- Email Configuration (from environment variables) ---
# It's better to get these directly where they are used or at app startup
MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com") # Default to Gmail, but allow override
MAIL_PORT = int(os.getenv("MAIL_PORT", 587)) # Default to 587, allow override
MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "True").lower() == "true" # Default TLS to True
MAIL_USE_SSL = os.getenv("MAIL_USE_SSL", "False").lower() == "true" # Default SSL to False

EMAIL_SENDER_CREDENTIALS = os.getenv("EMAIL_SENDER_CREDENTIALS") # This is your Gmail address for login
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD") # This is your Gmail App Password
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT") # The email address to send to

# Validate essential email config
if not all([EMAIL_SENDER_CREDENTIALS, EMAIL_PASSWORD, EMAIL_RECIPIENT]):
    print("WARNING: Email environment variables not fully set. Email sending might fail.")
    # You might want to raise an error or disable email features if critical.


# Allowed team names
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
            return render_template("login.html", error="Invalid team name.")
    return render_template("login.html")

@app.route("/index", methods=["GET", "POST"])
def index():
    if "username" not in session:
        return redirect(url_for("login"))

    error = None
    image_url = None

    if request.method == "POST":
        if session["attempts"] <= 0:
            error = "You have used all 3 prompt attempts."
        else:
            prompt = request.form["prompt"].strip()
            if any(keyword in prompt.lower() for keyword in ["image", "draw", "picture"]):
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
                    error = f"Image generation error: {str(e)}"
            else:
                error = "Prompt must include one of the keywords: image, draw, or picture."

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

    selected_index = int(request.form.get("selected_image", -1))
    if selected_index < 0 or selected_index >= len(session["images"]):
        flash("Invalid image selection.", "error") # Added category for flash
        return redirect(url_for("index"))

    selected_prompt = session["prompts"][selected_index]
    selected_image = session["images"][selected_index]
    username = session["username"]

    if send_email(username, selected_prompt, selected_image): # Check return value
        session.clear()
        return render_template("submitted.html", username=username)
    else:
        flash("Failed to send email. Please try again or contact support.", "error")
        return redirect(url_for("index"))


def send_email(username, prompt, image_url):
    # Use the variables defined globally from os.getenv
    sender_credentials = EMAIL_SENDER_CREDENTIALS # The Gmail address for login
    app_password = EMAIL_PASSWORD # The Gmail App Password
    recipient_email = EMAIL_RECIPIENT

    if not all([sender_credentials, app_password, recipient_email]):
        print("Email configuration is incomplete. Cannot send email.")
        flash("Email service not fully configured. Please contact administration.", "error")
        return False # Indicate failure

    # It's better to set the 'From' header to a human-readable name, but the actual sender
    # for SMTP authentication is sender_credentials.
    # For Gmail, the 'From' address must match the authenticated user.
    sender_display_name = f"{username} via Image App" # Example display name
    from_header = f"{sender_display_name} <{sender_credentials}>"

    subject = f"[Image Submission] From {username}"
    
    # Using MIMEMultipart for better email formatting (e.g., if you want HTML later)
    # For now, just plain text, but it's a good habit.
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_header # Set the From header
    msg["To"] = recipient_email

    # Plain text body
    body_text = f"""
Team Name: {username}

Selected Prompt:
----------------
{prompt}

Image URL:
----------
{image_url}
"""
    msg.attach(MIMEText(body_text, "plain"))

    # Optional: HTML body (more visually appealing)
    body_html = f"""
    <html>
        <body>
            <p><strong>Team Name:</strong> {username}</p>
            <p><strong>Selected Prompt:</strong></p>
            <p style="font-family: monospace; background-color: #f0f0f0; padding: 10px; border-radius: 5px;">{prompt}</p>
            <p><strong>Image URL:</strong></p>
            <p><a href="{image_url}" target="_blank">{image_url}</a></p>
            <p><img src="{image_url}" alt="Submitted Image" style="max-width: 100%; height: auto; display: block; margin-top: 10px;"></p>
        </body>
    </html>
    """
    msg.attach(MIMEText(body_html, "html"))


    try:
        # Determine whether to use TLS or SSL
        if MAIL_USE_TLS:
            server = smtplib.SMTP(MAIL_SERVER, MAIL_PORT)
            server.starttls()
        elif MAIL_USE_SSL:
            server = smtplib.SMTP_SSL(MAIL_SERVER, MAIL_PORT) # Use SMTP_SSL for direct SSL
        else:
            server = smtplib.SMTP(MAIL_SERVER, MAIL_PORT) # No encryption (not recommended for production)

        with server: # Use a with statement for automatic closing
            server.login(sender_credentials, app_password)
            server.sendmail(sender_credentials, recipient_email, msg.as_string())
            print("✅ Email sent successfully.")
            flash("Image submission successful! Email sent.", "success") # Added success flash
            return True # Indicate success
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Email failed - Authentication Error: {e}")
        flash("Email sending failed: Authentication error. Check sender email/password.", "error")
    except smtplib.SMTPConnectError as e:
        print(f"❌ Email failed - Connection Error: {e}")
        flash("Email sending failed: Could not connect to email server.", "error")
    except smtplib.SMTPRecipientsRefused as e:
        print(f"❌ Email failed - Recipient Refused: {e}")
        flash("Email sending failed: Recipient email address refused.", "error")
    except Exception as e:
        print(f"❌ Email failed - General Error: {e}")
        flash(f"Email sending failed: {e}", "error") # Show specific error to user (for debug)

    return False # Indicate failure

if __name__ == "__main__":
    app.run(debug=True)