from flask import Flask, render_template, jsonify, request, session, redirect, url_for, flash, make_response
import json
import os
import base64
import gzip
import secrets
import datetime
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration
from werkzeug.utils import secure_filename
import fitz
import requests
from scripts.decrypt import decrypt_and_decompress, restore_keys, generate_reverse_mapping

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
ACCESS_LOG_FILE = 'access_log.json'

UPLOAD_FOLDER = os.path.join(app.root_path, 'Uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'doc', 'docx'}

BACKBONE_FILE = os.path.join(app.root_path, 'templates', 'backbone.json')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def load_data():
    if 'patient_data' in session:
        return session['patient_data']
    try:
        with open('data_cs.json', 'r', encoding='utf-8') as file:
            session['patient_data'] = json.load(file)
            return session['patient_data']
    except Exception as e:
        print(f"Error loading data: {e}")
        return {}

def decode_and_decompress(data):
    try:
        shortened_data = decrypt_and_decompress(data)
        with open(BACKBONE_FILE, 'r', encoding='utf-8') as f:
            backbone = json.load(f)
        reverse_mapping = generate_reverse_mapping(backbone)
        restored_data = restore_keys(shortened_data, reverse_mapping)
        return restored_data
    except Exception as e:
        print(f"Error decoding data: {e}")
        return None

def log_access(patient_id, icz):
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    access_record = {
        "timestamp": timestamp,
        "patient_id": patient_id,
        "icz": icz,
        "ip_address": request.remote_addr
    }
    records = []
    try:
        if os.path.exists(ACCESS_LOG_FILE):
            with open(ACCESS_LOG_FILE, 'r', encoding='utf-8') as file:
                records = json.load(file)
        records.append(access_record)
        with open(ACCESS_LOG_FILE, 'w', encoding='utf-8') as file:
            json.dump(records, file, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error writing access log: {e}")

@app.route('/')
def start():
    session.pop('patient_data', None)
    session.pop('authorized', None)
    session.pop('icz', None)
    return render_template('start.html')

@app.route('/verify', methods=['POST'])
def verify():
    if request.method == 'POST':
        qr_data = request.form.get('qr_data')
        pass_code = request.form.get('pass_code')
        icz = request.form.get('icz')
        if not qr_data or not pass_code or not icz:
            flash("Chybí QR kód, přístupový kód nebo IČZ", "error")
            return redirect(url_for('start'))
        if not icz.isalnum():
            flash("Neplatné IČZ. Zadejte platné identifikační číslo.", "error")
            return redirect(url_for('start'))
        patient_data = decode_and_decompress(qr_data)
        if not patient_data:
            return redirect(url_for('start'))
        patient_info = patient_data.get('Pacient', {})
        patient_id = patient_info.get('cisloPojistence', '')
        clean_pass_code = pass_code.replace('/', '').strip() if pass_code else ''
        if int(clean_pass_code) == int(patient_id):
            log_access(patient_id, icz)
            session['patient_data'] = patient_data
            session['authorized'] = True
            session['icz'] = icz
            return redirect(url_for('index'))
        else:
            flash("Nesprávný přístupový kód.", "error")
            return redirect(url_for('start'))

@app.route('/dashboard')
def index():
    if 'authorized' not in session or not session['authorized']:
        flash("Nejprve prosím naskenujte QR kód a zadejte přístupový kód", "error")
        return redirect(url_for('start'))
    data = load_data()
    return render_template('index.html', data=data)

@app.route('/data')
def get_data():
    if 'authorized' not in session or not session['authorized']:
        return jsonify({"error": "Unauthorized"}), 401
    data = load_data()
    return jsonify(data)

@app.route('/patient')
def patient():
    if 'authorized' not in session or not session['authorized']:
        flash("Nejprve prosím naskenujte QR kód a zadejte přístupový kód", "error")
        return redirect(url_for('start'))
    data = load_data()
    return render_template('patient.html', data=data)

@app.route('/diagnosis')
def diagnosis():
    if 'authorized' not in session or not session['authorized']:
        flash("Nejprve prosím naskenujte QR kód a zadejte přístupový kód", "error")
        return redirect(url_for('start'))
    data = load_data()
    return render_template('diagnosis.html', data=data)

@app.route('/treatment')
def treatment():
    if 'authorized' not in session or not session['authorized']:
        flash("Nejprve prosím naskenujte QR kód a zadejte přístupový kód", "error")
        return redirect(url_for('start'))
    data = load_data()
    return render_template('treatment.html', data=data)

@app.route('/export_pdf')
def export_pdf():
    if 'authorized' not in session or not session['authorized']:
        flash("Pro export PDF se prosím nejprve přihlaste.", "error")
        return redirect(url_for('start'))
    data = load_data()
    if not data:
        flash("Nelze exportovat PDF, data pacienta nebyla nalezena.", "error")
        return redirect(request.referrer or url_for('index'))
    icz = session.get('icz', None)
    now = datetime.datetime.now()
    try:
        html_string = render_template('export_template.html', data=data, icz=icz, now=now)
        static_folder = os.path.join(app.root_path, 'static')
        base_url = static_folder
        pdf_bytes = HTML(string=html_string, base_url=base_url).write_pdf(presentational_hints=True)
        patient_id = data.get('Pacient', {}).get('cisloPojistence', 'pacient')
        pdf_filename = f"OnkoPass_{patient_id}_{now.strftime('%Y%m%d')}.pdf"
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename="{pdf_filename}"'
        return response
    except Exception as e:
        print(f"Error generating PDF: {e}")
        flash(f"Nastala chyba při generování PDF: {e}", "error")
        return redirect(request.referrer or url_for('index'))

def run_to_llm(upload_file_path):
    try:
        doc = fitz.open(upload_file_path)
        pdf_text = "\n".join([page.get_text() for page in doc])
        doc.close()
    except Exception as e:
        return {"error": "Failed to read PDF", "details": str(e)}

    # Use environment variable for Ollama URL, default to localhost
    ollama_url = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
    endpoint = f"{ollama_url}/api/generate"
    print("🔍 Ollama API Response:")
    print(json_response)  # 
    prompt = f"""
       extract the most important information from the following PDF document.
        PDF content:
        \"\"\"
        {pdf_text}
        \"\"\"
        """
    try:
        response = requests.post(
            endpoint,
            json={
                "model": "llama2:latest",
                "prompt": prompt,
                "stream": False
            },
            timeout=30  # Add timeout to avoid hanging
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return {"error": "Ollama API request failed", "details": str(e)}

    if response.status_code == 200:
        return {
            "output": response.json().get("response", ""),
            "raw": response.json()
            
        }
    return {
        "error": f"Ollama returned status {response.status_code}",
        "details": response.text
    }



@app.route('/upload_page')
def upload_page():
    # If user is authorized, redirect them away from this specific upload page
    if session.get('authorized'): # Use .get() for safer access
        flash("Pro nahrávání souborů se prosím nejprve odhlaste.", "info")
        return redirect(url_for('index')) # Redirect to main dashboard

    # Otherwise, show the upload page
    return render_template('upload_page.html')

# Add the upload handler route
@app.route('/upload', methods=['POST'])
def upload_file():
    print("Upload endpoint called")  # Debug log
    
    # Check if the uploads directory exists, if not create it
    upload_folder = os.path.join(app.root_path, 'uploads')
    if not os.path.exists(upload_folder):
        try:
            os.makedirs(upload_folder)
            print(f"Created uploads folder at: {upload_folder}")  # Debug log
        except Exception as e:
            print(f"Failed to create uploads folder: {str(e)}")  # Debug log
            return jsonify({'success': False, 'message': f"Chyba při vytváření složky: {str(e)}"}), 500
    
    # Check if file is in the request
    if 'file' not in request.files:
        print("No file in request")  # Debug log
        return jsonify({'success': False, 'message': 'Žádný soubor nebyl poskytnut'}), 400
    
    file = request.files['file']
    print(f"Received file: {file.filename}")  # Debug log
    
    # Check if file has a name (empty file input)
    if file.filename == '':
        print("Empty filename")  # Debug log
        return jsonify({'success': False, 'message': 'Žádný soubor nebyl vybrán'}), 400
    
    # Check for allowed file types (optional security check)
    allowed_extensions = {'png', 'jpg', 'jpeg', 'pdf', 'doc', 'docx'}
    if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
        print(f"Invalid file type: {file.filename}")  # Debug log
        return jsonify({'success': False, 'message': 'Tento typ souboru není povolen'}), 400
    
    try:
        # Secure the filename to prevent directory traversal attacks
        from werkzeug.utils import secure_filename
        secure_name = secure_filename(file.filename)
        
        # Generate a unique filename by adding timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_")
        final_filename = timestamp + secure_name
        
        # Save the file
        filepath = os.path.join(upload_folder, final_filename)
        file.save(filepath)
        run_to_llm(filepath)  # Call the function to process the file
        
        print(f"File saved successfully at: {filepath}")  # Debug log
    except:
        return jsonify({'success': False, 'message': 'Chyba při ukládání souboru'}), 500
    return (render_template('upload_page.html'))



@app.route('/save')
def save():
    if 'authorized' not in session or not session['authorized']:
        flash("Pro uložení se prosím nejprve přihlaste.", "error")
        return redirect(url_for('start'))
    try:
        return render_template('save.html')
    except Exception as e:
        print(f"Error rendering save.html: {e}")
        flash("Chyba při načítání stránky uložení.", "error")
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    flash("Byli jste úspěšně odhlášeni.", "info")
    return redirect(url_for('start'))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)