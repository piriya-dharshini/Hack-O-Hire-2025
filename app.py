from lib import *

load_dotenv()  # Load environment variables from .env

openai_api_key = "your openai api key"
client = OpenAI(api_key=openai_api_key)

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['UPLOAD_FOLDER'] = 'uploads'

app.secret_key = 'your app secret key'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc', 'eml', 'xlsx', 'xls', 'jpg', 'jpeg', 'png', 'tiff'}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Login required to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = users_collection.find_one({"username": username})
        if user and check_password_hash(user['password'], password):
            session['username'] = user['username']
            return redirect(url_for('dashboard'))
        return "Invalid credentials", 401
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        if users_collection.find_one({"username": username}):
            return "Username already exists", 400
        users_collection.insert_one({"username": username, "password": password})
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    user_filter = {"uploaded_by": session['username']}
    total_validations = files_collection.count_documents(user_filter)
    completed = files_collection.count_documents({**user_filter, "status": "Valid"})
    failed = files_collection.count_documents({**user_filter, "status": "Invalid"})
    pending = files_collection.count_documents({**user_filter, "status": "Pending"})
    recent_files = list(files_collection.find(user_filter).sort("upload_time", -1).limit(5))
    all_users = users_collection.find()
    users = {user["username"]: user.get("display_name", user["username"]) for user in all_users}

    return render_template('dashboard.html',
                           total=total_validations,
                           completed=completed,
                           failed=failed,
                           pending=pending,
                           recent_files=recent_files,
                           users=users)

@app.route('/files_check')
@login_required
def files_check():
    files = list(files_collection.find({"uploaded_by": session['username']}))
    return render_template('upload.html', files=files)

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    if 'file' not in request.files:
        return "No file part", 400
    file = request.files['file']
    if file.filename == '':
        return "No selected file", 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(upload_path)

        logger.info(f"File uploaded: {filename}")

        try:
            content = process_document(upload_path)
            reducted=anonymize_text_with_presidio(content)
            status = "Valid" if "bar" in content.lower() else "Invalid"

            files_collection.insert_one({
                "filename": filename,
                "upload_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "status": status,
                "extracted_text": content,
                "reducted_text": reducted,
                "reviewer": None,
                "processing_time": None,
                "confidence": None,
                "uploaded_by": session['username']  # Link file to user
            })
            return redirect(url_for('files_check'))
        except Exception as e:
            logger.error(f"Extraction error: {str(e)}")
            return f"Error processing file: {e}", 500
    else:
        return "Unsupported file type", 400

@app.route('/validation_result/<filename>', methods=['GET', 'POST'])
@login_required
def validation_result(filename):
    file_record = files_collection.find_one({
        "filename": filename,
        "uploaded_by": session['username']
    })
    if not file_record or "reducted_text" not in file_record:
        return "Redcuted text not found", 404

    reducted_text = file_record["reducted_text"]

    if request.method == 'POST':
        recap_file = request.files.get('recap_file')
        if not recap_file:
            return "No recap file uploaded", 400

        try:
            df = pd.read_excel(recap_file)
            
            recap_values = {}
            for _, row in df.iterrows():
                param = str(row[0]).strip()
                val = str(row[1]).strip()
                recap_values[param] = val

            files = {
                'file': (f"{filename}_extracted.txt", reducted_text.encode('utf-8'), 'text/plain')
            }
            data = {
                "recap_values": json.dumps(recap_values),
                "human_prompt": ""
            }

            start_time = time.time()
            response = requests.post("http://localhost:8000/validate/", files=files, data=data)
            response.raise_for_status()

            result_data = response.json()
            recap_result = result_data.get("validation_result", "")
            compliance_result = result_data.get("compliance_result", "")

            elapsed = time.time() - start_time
            processing_time = f"{elapsed:.2f} seconds"

            cleaned_json = re.sub(r"```(?:json)?\n?", "", recap_result).strip("` \n")
            validation_result = json.loads(cleaned_json)
            print("recap result",recap_result)
            print(validation_result)
            scores = [float(match) for match in re.findall(r"Score:\s*([0-9.]+)", recap_result + compliance_result)]
            # Normalize if score looks like a decimal (e.g., 0.92), otherwise assume it's already in percentage
            normalized_scores = [
                s * 100 if s <= 1.0 else s
                for s in scores
            ]
            average_confidence = round(sum(normalized_scores) / len(normalized_scores), 2) if normalized_scores else None

            status = "Valid" if "OVERALL COMPLIANT: YES" in compliance_result else "Invalid"

            files_collection.update_one(
                {"filename": filename, "uploaded_by": session['username']},
                {"$set": {
                    "status": status,
                    "reviewer": session['username'],
                    "processing_time": processing_time,
                    "confidence": average_confidence,
                    "validation_result": validation_result,
                    "compliance_result": compliance_result
                }}
            )

            return render_template(
                "validation_result.html",
                filename=filename,
                validation_result=validation_result,
                compliance_result=compliance_result,
                confidence=average_confidence,
                processing_time=processing_time,
                status=status
            )

        except Exception as e:
            return f"Error processing recap Excel file or validation: {e}", 500

    # GET: Display upload form only
    return render_template(
        "validation_result.html",
        filename=filename,
        validation_result=None,
        compliance_result=None,
        confidence=None,
        processing_time=None,
        status=None
    )


@app.route('/extracted/<filename>')
@login_required
def extracted(filename):
    file_record = files_collection.find_one({
        "filename": filename,
        "uploaded_by": session['username']
    })
    if not file_record:
        return "File not found", 404

    reducted_text = file_record.get("reducted_text", "No extracted text available.")
    return render_template('extract.html', filename=filename, extracted_text=reducted_text)

@app.route('/chat_with/<filename>')
@login_required
def chat_with(filename):
    return render_template('chat.html', filename=filename)

@app.route('/api/chat/<filename>', methods=['POST'])
@login_required
def chat_api(filename):
    data = request.json
    query = data.get('query', '')

    if not query:
        return jsonify({'error': 'Query is required'}), 400

    file_record = files_collection.find_one({
        "filename": filename,
        "uploaded_by": session['username']
    })

    if not file_record or "reducted_text" not in file_record:
        return jsonify({"error": "Reducted text missing."}), 404

    term_sheet_json = file_record["reducted_text"]

    system_prompt = """
    You are a financial term sheet assistant...
    """

    context_message = f"""
    Here is the structured data extracted from the term sheet:
    ```json
    {term_sheet_json}
    ```

    The user's query is about this term sheet. Please provide an accurate, helpful response based on the information available.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context_message},
                {"role": "user", "content": query}
            ],
            temperature=0.2,
            max_tokens=1000
        )
        assistant_reply = response.choices[0].message.content
        return jsonify({"response": assistant_reply})
    except Exception as e:
        logger.error(f"OpenAI chat error: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)