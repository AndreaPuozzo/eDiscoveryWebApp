from app import app, db
from flask import render_template, flash, redirect, url_for, request
from app.forms import LoginForm, RegistrationForm
from flask_login import current_user, login_user, logout_user, login_required
import sqlalchemy as sa
from app.models import User, Case, File, FileAnnotation
from urllib.parse import urlsplit
from datetime import datetime, timezone
import os
from app.process_files import process_file
from flask import send_from_directory

@app.route('/')
@app.route('/index')
@login_required

def index():
    return render_template('index.html', title='Benvenuto')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(sa.select(User).where(User.username == form.username.data))
        if user is None or not user.check_password(form.password.data):
            flash('Nome o Password non Validi')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or urlsplit(next_page).netloc != '':
            next_page = url_for('index')
        return redirect(url_for('index'))
    return render_template('login.html', title='Sign In', form=form)

@app.route('/logout')
def logout():
    #funzione importata dal pcchetto flask_login
    logout_user()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulazioni, ora sei un utente registrato!')
        return redirect(url_for('login'))
    return render_template('register.html',title='Register', form=form)

#componente dinamica
@app.route('/user/<username>')
#questo è da flask_login
@login_required
def user(username):
    #funziona come scalar(), ma se non ci sono risultati, al posto di none, restituisce error 404
    user = db.first_or_404(sa.select(User).where(User.username == username))
    return render_template('user.html', user=user)

@app.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.now(timezone.utc)
        db.session.commit()

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        return redirect(request.url)
    if file:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
        file_info = process_file(filepath)
        return render_template('file_info.html', info=file_info)

    
#VECCHIO ENDPOINT (ELIMINABILE!)
@app.route('/analyze_directory/', methods=['POST'])
@login_required
def analyze_directory():
    directory = request.form.get('directory_path')
    if not directory:
        flash('Il percorso della directory manca o non è valido')
        return redirect(url_for('index'))
    
    #recupera i file caricati
    files = request.files.getlist('file')

    #processa ciascun file all'interno della directory
    files_info = []
    for file in files:
        #salva temporaneamente ogni file
        temp_filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        
        #crea la directory se non esiste
        temp_dir = os.path.dirname(temp_filepath)
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)       
        
        #salva il file nella directory configurata
        file.save(temp_filepath)

        #processa il file e aggiungi il percorso assoluto ai metadati
        file_info = process_file(temp_filepath, file.filename)
        file_info['filename'] = os.path.basename(file.filename) #per estrarre solo il nome base
        files_info.append(file_info)

    if not files_info:
        flash("non sono stati processati file")
        return redirect(url_for('index'))

    return render_template('directory_analysis.html', files=files_info)

#route per creare un nuovo caso
@app.route('/create_case', methods=['GET','POST'])
@login_required
def create_case():         #modificato da create_case_form CONTROLLARE
    if request.method == 'POST':
        #recupera il nome del caso, il percorso della directory e i file caricati dall'utente
        #case_name = request.form.get('case_name')
        case_name = request.form['case_name']
        directory_path = request.form['directory_path']
        files = request.files.getlist('file')

        if not case_name or not directory_path or not files:
            flash('Tutti i campi sono Obbligatori!')
            return redirect(url_for('create_case'))
        
        if Case.query.filter_by(name=case_name).first():
            flash('Esiste già un caso con questo nome!')
            return redirect(url_for('create_case'))
        
        case = Case(name=case_name)
        db.session.add(case)
        db.session.commit()

        for file in files:
            temp_filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            temp_dir = os.path.dirname(temp_filepath)
            os.makedirs(temp_dir, exist_ok=True)
            file.save(temp_filepath)

            file_info = process_file(temp_filepath, file.filename)

            db_file = File(
                case_id = case.id,
                filename = file.filename,
                relative_path = temp_filepath,
                file_metadata = file_info['metadata']
            )
            db.session.add(db_file)
            
        db.session.commit()
        flash('Caso creato con successo!')
        return redirect(url_for('cases'))
        
    return render_template('create_case.html')

#route per visualizzare i casi
@app.route('/cases')
@login_required
def cases():    
    #se non filtro nulla torno tutti i casi
    all_cases = Case.query.all()
    return render_template('cases.html', cases=all_cases, search_query=None)

def get_case_annotation_counts(case):
    counts = {}
    for file in case.files:
        for annotation in file.annotations:
            if annotation.label in counts:
                counts[annotation.label] += 1
            else:
                counts[annotation.label] = 1
    return counts

app.jinja_env.globals.update(get_case_annotation_counts=get_case_annotation_counts)     

#route per mostrare i dettagli del caso
@app.route('/case/<int:case_id>')
@login_required
def case_details(case_id):
    case = Case.query.get_or_404(case_id)
    label_filter = request.args.get('label_filter', '').strip()
    comment_search = request.args.get('comment_search', '').strip()

    #query di base
    query = File.query.filter(File.case_id == case_id)

    if label_filter:
        if label_filter == 'unlabeled':
            
            #subquery per trovare i file con qualsiasi annotazione
            files_with_annotations = db.session.query(FileAnnotation.file_id).distinct()

            #subquery per trovare i file con nessuna annotazione
            query = query.filter(~File.id.in_(files_with_annotations))
        else:
            #filtra per una label specifica
            query = query.join(FileAnnotation).filter(FileAnnotation.label == label_filter)

    if comment_search:
        query = query.join(FileAnnotation).filter(FileAnnotation.comment.ilike(f'%{comment_search}%'))
    
    #esegue la query e restituisce i risultati
    files = query.distinct().all()

    return render_template('case_details.html', case=case, files=files, label_filter=label_filter, comment_search=comment_search)

#route per eliminare i casi
@app.route('/delete_case/<int:case_id>', methods=['POST'])
@login_required
def delete_case(case_id):
    case = Case.query.get_or_404(case_id)
    
    #cancella tutti i file associati
    for file in case.files:
        #controllo se i file sono presenti in altri casi (se si, non li cancello dal db ma li deferenzio solamente)
        other_cases_count = File.query.filter_by(
            filename = file.filename
        ).filter(File.case_id != case_id).count()

        if other_cases_count == 0 and os.path.exists(file.relative_path):
            try:
                os.remove(file.relative_path)
            except OSError:
                pass
        
        #cancella il record dal database
        db.session.delete(file)

    db.session.delete(case)
    db.session.commit()
    flash('Caso eliminato con successo!')
    return redirect(url_for('cases'))

#route per gestire l'aggiunta di file dopo aver creato un caso
@app.route('/case/<int:case_id>/add_files', methods=['POST'])
@login_required
def add_files_to_case(case_id):
    case = Case.query.get_or_404(case_id)
    files = request.files.getlist('file')

    if not files:
        flash('Nessun file selezionato!')
        return redirect(url_for('case_details', case_id=case_id))
    
    for file in files:
        temp_filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        os.makedirs(os.path.dirname(temp_filepath), exist_ok=True)
        file.save(temp_filepath)

        file_info = process_file(temp_filepath, file.filename)

        db_file = File(
            case_id=case.id,
            filename=file.filename,
            relative_path=temp_filepath,
            file_metadata=file_info['metadata']
        )
        db.session.add(db_file)

    db.session.commit()
    flash('File aggiunti con successo!')
    return redirect(url_for('case_details', case_id=case_id))

#route per cancellare i file presenti in un caso dopo la sua creazione
@app.route('/delete_file/<int:file_id>', methods=['POST'])
@login_required
def delete_file(file_id):
    file = File.query.get_or_404(file_id)
    case_id = file.case_id
    
    if os.path.exists(file.relative_path):
        try:
            os.remove(file.relative_path)
        except OSError:
            pass
    
    db.session.delete(file)
    db.session.commit()
    flash('File eliminato con successo!')
    return redirect(url_for('case_details', case_id=case_id))

@app.route('/file_info/<int:file_id>')
@login_required
def file_info(file_id):
    file = File.query.get_or_404(file_id)
    file_info = process_file(file.relative_path, file.filename)
    return render_template('file_info.html', info=file_info, file=file)

    
@app.route('/add_file_annotation/<int:file_id>', methods=['POST'])
@login_required
def add_file_annotation(file_id):
    file = File.query.get_or_404(file_id)
    label = request.form.get('label')
    comment = request.form.get('comment')

    if not label:
        flash('Una label è obbligatoria')
        return redirect(url_for('file_info', file_id=file_id))
    
    annotation = FileAnnotation(
        file_id=file_id,
        label=label,
        comment=comment,
        created_by=current_user.id
    )

    db.session.add(annotation)
    db.session.commit()
    flash('Annotazione aggiunta con successo!')
    return redirect(url_for('file_info', file_id=file_id))


@app.route('/delete_file_annotation/<int:annotation_id>', methods=['POST'])
@login_required
def delete_file_annotation(annotation_id):
    annotation = FileAnnotation.query.get_or_404(annotation_id)
    file_id = annotation.file_id

    if annotation.created_by != current_user.id:
        flash('Puoi solo cancellare commenti fatti da te!')
        return redirect(url_for('file_info', file_id=file_id))
    
    db.session.delete(annotation)
    db.session.commit()
    flash('Commento eliminato con successo!')
    return redirect(url_for('file_info', file_id=file_id))