# Piattaforma prototipale per attività di e-Discovery

> Progetto di tesi: piattaforma web per la gestione, consultazione e annotazione di evidenze informatiche in ambito e-Discovery.

## Descrizione

Questa applicazione è stata sviluppata come progetto di tesi triennale presso l’Università degli Studi di Milano.  
L’obiettivo era creare una **piattaforma accessibile e personalizzabile** che consentisse il caricamento di directory contenenti file digitali, l’analisi automatica dei metadati, e la consultazione dei documenti per finalità legali o investigative.

Si tratta di un prototipo ispirato a software professionali di e-discovery, come Logikcull, con un focus su **usabilità, visualizzazione delle evidenze** e **annotazione collaborativa**.

## Funzionalità principali

- Registrazione e Login utente tramite autenticazione sicura
- Creazione di casi di analisi
- Caricamento di directory con analisi automatica dei file
- Estrazione dei metadati principali 
- Supporto a vari formati (DOC/DOCX, XLS/XLSX, PPT/PPTX)
- Visualizzazione documenti con anteprime grafiche o testuali
- Sistema di annotazioni: commenti liberi e tag predefiniti
- Gestione casi e filtri dinamici sui file caricati

## Tecnologie utilizzate

- **Backend**: Python + Flask
- **Frontend**: HTML, CSS, Jinja2
- **Database**: SQLite (via SQLAlchemy)
- **Librerie**: ExifTool, python-docx, openpyxl, python-pptx, Flask-WTF, Flask-Login
- **Versionamento del codice**: Git, GitHub

## Struttura del progetto

- `app/` – Moduli principali e logica dell'applicazione
- `templates/` – Template HTML dinamici con Jinja2
- `uploads/` – File utente caricati
- `app.py` – Entry point
- `config.py` – Configurazioni globali

## Tesi

Questo progetto è stato presentato come tesi triennale in **Sicurezza dei Sistemi e delle Reti Informatiche**.  
**Titolo:** *Progettazione e implementazione di un’interfaccia web per la consultazione di evidenze informatiche per finalità di e-Discovery*  
**Anno accademico:** 2023/2024

📄 [Clicca qui per leggere la tesi completa (PDF)](link)

## Autore

Andrea Puozzo  
Università degli Studi di Milano
