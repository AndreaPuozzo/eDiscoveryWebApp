from datetime import datetime, timezone
from typing import Optional
import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db, login
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from hashlib import md5
import pytz

#ORM mi serve per gestire il db con entità ad alto livello
#come classi e oggetti, piuttosto che con tabelle e SQL
#orm con sqlalchemy si occuperà della traduzione da classi
#e oggetti in righe e colonne della mia tabella

#UserMixin serve per implementare i 4 metodi fondamentali
#per il login di un utente
class User(UserMixin, db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    username: so.Mapped[str] = so.mapped_column(sa.String(64), index=True, unique=True)
    email: so.Mapped[str] = so.mapped_column(sa.String(120), index=True, unique=True)
    password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))
    last_seen: so.Mapped[Optional[datetime]] = so.mapped_column(default=lambda: datetime.now(timezone.utc).astimezone(pytz.timezone("Europe/Rome")))

    def __repr__(self):
        return '<User {}>'.format(self.username)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)    
        
    @login.user_loader
    def load_user(id):
        return db.session.get(User, int(id))
    

class Case(db.Model):
    __tablename__ = 'cases'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    files = db.relationship('File', backref='case', lazy='dynamic')

    def __repr__(self):
        return f'<Case {self.name}>'
    

class File(db.Model):
    __tablename__ = 'files'

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('cases.id'), nullable=False)
    filename = db.Column(db.String(256), nullable=False)
    relative_path = db.Column(db.String(512), nullable=False)
    file_metadata = db.Column(db.JSON, nullable=False) #salviamo i metadati in formato JSON
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    annotations = db.relationship('FileAnnotation', backref='file', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<File {self.filename}>'
    

class FileAnnotation(db.Model):
    __tablename__ = 'file_annotations'

    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.Integer, db.ForeignKey('files.id'), nullable=False)
    label = db.Column(db.String(50), nullable=False)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref='file_annotations')

    def __repr__(self):
        return f'<FileAnnotation {self.label}>'



