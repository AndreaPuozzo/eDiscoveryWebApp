import os, re
from datetime import datetime
import docx
from pptx import Presentation
import pandas as pd
from pdf2image import convert_from_path
import openpyxl
import exiftool
from io import BytesIO
import tempfile
from PIL import Image, ImageDraw, ImageFont
import subprocess
from werkzeug.utils import secure_filename
import uuid
import base64
from flask import url_for

def extract_metadata(filepath):       
    with exiftool.ExifTool() as et:
        metadata = et.execute_json(filepath)
    if not metadata:
        return {}
    filtered_metadata = {}

    #mappatura dinamica delle chiavi per ogni tipo di file
    keys_to_keep = {
        "File:Directory": "posizione",
        "File:FileSize": "dimensione",
        "File:FilePermission": "permessi dei file",
        "File:FileType": "tipo di file",
        "File:FileTypeExtension": "estensione del file",
        "ZIP:ZipModifyDate": "data modifica zip",
        "XML:CreateDate": "data di creazione",
        "XML:ModifyDate": "data ultima modifica",
        "XML:Pages": "numero di pagine",  # Solo per DOCX e PPTX
        "XML:Words": "numero di parole",  # Solo per DOCX
        "XML:Characters": "numero di caratteri",  # Solo per DOCX
        "XML:CharactersWithSpaces": "numero di caratteri compresi gli spazi",  # Solo per DOCX
        "XML:Paragraphs": "numero di paragrafi",  # Solo per DOCX
        "XML:TotalEditTime": "modificato ... volte",  # Solo per PPTX
        "XMP:Language": "lingua"
    }

    #filtrare e ridenominare i metadati
    for key, label in keys_to_keep.items():
        if key in metadata[0]:
            value = metadata[0][key]
            if label == "modificato ... volte" and value: #personalizzazione per il numero di modifiche
                value = f"modificato {value} volte"
            filtered_metadata[label] = value
    
    #correzione del percorso reale
    if "posizione" in filtered_metadata:

        #ricava il path completo
        full_path = os.path.abspath(filepath)

        dir_path = os.path.dirname(full_path)

        #rimuovo tramite regex le parti che non voglio per la posizione
        pattern = r'(.*?)[\\/]e-discovery[\\/]uploads[\\/](.*)'

        match = re.match(pattern, dir_path)
        
        if match:
            
            base_path = match.group(1) #tutto quello che viene prima di "e-discovery"
            remaining_path = match.group(2) #tutto quello che viene dopo "uploads"
            original_path = os.path.join(base_path, remaining_path)
            filtered_metadata["posizione"] = original_path

        #fallback
        else:
            filtered_metadata["posizione"] = dir_path

    return filtered_metadata


def process_file(filepath, filename):
    #usa il filepath solo per operazioni che richiedono un percorso fisico
    if isinstance(filepath, str): #verifica se è un percorso fisico
        #calcolo della dimensione del file
        size_in_bytes = os.path.getsize(filepath)

        if size_in_bytes < 1024 * 1024:
            file_size = f"{round(size_in_bytes / 1024, 2)} KB"
        else:
            file_size = f"{round(size_in_bytes / (1024 * 1024), 2)} MB" 
    else:
        #gestione dello stream se necessario
        file_size = "indefinito"

    preview_gen = PreviewGenerator()
    
    file_info = {
        'filename': filename,
        'size': file_size,
        'metadata': extract_metadata(filepath), #estrae tutti i metadati
        'preview_images': [],
        'count': 0,
        'count_label': '' #etichetta dinamica per il conteggio (es. "parole" o "diapositive")
    }

    #estraggo estensione per determinare tipo e metodo estrazione metadati
    ext = os.path.splitext(filename)[1].lower()

    if ext == '.docx':
        doc = docx.Document(filepath)
        file_info['count'] = len(doc.element.body.xpath('.//w:p'))
        file_info['count_label'] = "Numero di parole"
        file_info['preview_images'] = preview_gen.generate_docx_preview(filepath)

    elif ext == '.pptx':
        ppt = Presentation(filepath)
        file_info['count'] = len(ppt.slides)
        file_info['count_label'] = "Numero di diapositive"
        file_info['preview_images'] = preview_gen.generate_pptx_preview(filepath)

    elif ext == '.xlsx':
        wb = openpyxl.load_workbook(filepath)
        file_info['count'] = len(wb.sheetnames)
        file_info['count_label'] = "Numero di fogli"
        file_info['preview_images'] = preview_gen.generate_xlsx_preview(filepath)

    return file_info

class PreviewGenerator:
    def __init__(self):
        self.max_preview_size = (800, 1000)

    def get_base64_image(self, img):
        #converte immagini PIL in stringhe base64, per essere leggibili da html ed essere renderizzate

        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return f"data:image/png;base64, {base64.b64encode(buffered.getvalue()).decode()}"
    
    def create_text_image(self, text, size=(800, 200), font_size=12, background_color="white"):
        #crea un'immagine dal testo con una formattazione migliore

        img = Image.new("RGB", size, background_color)
        draw = ImageDraw.Draw(img)

        #imposto arial come font altrimenti fallback
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        
        except:
            font = ImageFont.load_default()

        margin_x = 40 #margine orizzontale
        margin_y = 30 #margine verticale
        max_width = size[0] - 2 * margin_x

        #divido il testo in paragrafi
        paragraphs = text.split('\n')
        y = margin_y

        for paragraph in paragraphs:
            if not paragraph.strip():
                y += font_size #aggiungo spazio per i paragrafi vuoti
                continue

            words = paragraph.split()
            current_line = []


            for word in words:
                current_line.append(word)
                line_width = draw.textlength(" ".join(current_line), font=font)

                if line_width > max_width:
                    if len(current_line) > 1:
                        current_line.pop()
                        line_text = " ".join(current_line)
                        draw.text((margin_x, y), line_text, fill="black", font=font)
                        y += font_size + 4
                        current_line = [word]
                    else:
                        draw.text((margin_x, y), word, fill="black", font=font)
                        y += font_size + 4
                        current_line = []

            #disegno le parole rimanenti sulla riga
            if current_line:
                line_text = " ".join(current_line)
                draw.text((margin_x, y), line_text, fill="black", font=font)
                y += font_size + 12



        return img
    
    def generate_docx_preview(self, filepath):
        try:
            doc = docx.Document(filepath)
            previews = []

            #unisco paragrafi in pagine
            current_height = 0
            current_texts = []
            page_height = 1000

            for paragraph in doc.paragraphs:
                
                text = paragraph.text.strip()

                #calcolo approssimativo per l'altezza del paragrafo (assumo 80 caratteri per linea)
                estimated_lines = (len(text) / 80) + 1
                #moltiplico ogni linea per un'altezza stimata
                estimated_height = estimated_lines * 16 + 20 #altezza di ogni linea (16 pixel) + padding (20 pixel)

                #se supero la grandezza della pagina, creo l'immagine e resetto per le successiva
                if current_height + estimated_height > page_height and current_texts:

                    img = self.create_text_image(
                        "\n\n".join(current_texts),
                        size=(800, page_height),
                        font_size=12,
                        background_color="white"
                    )
                    previews.append(self.get_base64_image(img))
                    current_texts = []
                    current_height = 0

                current_texts.append(text)
                current_height += estimated_height

            #gestisco il testo rimanente
            if current_texts:
                img = self.create_text_image(
                    "\n\n".join(current_texts),
                    size=(800, page_height),
                    font_size=12,
                    background_color="white"
                )
                previews.append(self.get_base64_image(img))
            
            return previews
        
        except Exception as e:
            print(f"errore nella generazione dell'anteprima: {e}")
            return []

    def generate_pptx_preview(self, filepath):
        try:
            prs = Presentation(filepath)
            previews = []
            
            for slide in prs.slides:
                #crea diapositive da 16:9
                img = Image.new("RGB", (800, 450), "white")
                draw = ImageDraw.Draw(img)
                
                #parto con 20 pixel dall'alto
                y_offset = 20
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        text_img = self.create_text_image(shape.text, 
                                                        size=(760, 100), 
                                                        font_size=14)
                        img.paste(text_img, (20, y_offset))
                        y_offset += 110

                previews.append(self.get_base64_image(img))
            
            return previews
        except Exception as e:
            print(f"errore di generazione dell'anteprima: {e}")
            return []

    def generate_xlsx_preview(self, filepath):
        try:
            wb = openpyxl.load_workbook(filepath, data_only=True)
            previews = []
            
            for sheet_name in wb.sheetnames:
                sheet = wb[sheet_name]
                
                #calcola la dimensione del foglio
                max_row = min(sheet.max_row, 20)  #imposta un limite di 20 righe
                max_col = min(sheet.max_column, 10)  #imposta un limite di 10 colonne

                cell_width = 80
                cell_height = 25
                img_width = (max_col * cell_width) + 50 #aggiungo un padding ch esi imposta automaticamente a destra/sinistra, sopra/sotto
                img_height = (max_row * cell_height) + 50
                
                img = Image.new("RGB", (img_width, img_height), "white")
                draw = ImageDraw.Draw(img)
                
                #disegna la griglia (linee orizzontali e verticali)
                for row in range(max_row + 1):
                    y = row * cell_height
                    draw.line([(0, y), (img_width, y)], fill="gray")
                
                for col in range(max_col + 1):
                    x = col * cell_width
                    draw.line([(x, 0), (x, img_height)], fill="gray")
                
                #disegna il contenuto delle celle
                for row in range(1, max_row + 1):
                    for col in range(1, max_col + 1):
                        value = sheet.cell(row=row, column=col).value
                        if value is not None:
                            #testo nelle celle
                            x = (col - 1) * cell_width + 5
                            y = (row - 1) * cell_height + 5
                            draw.text((x, y), str(value)[:10], fill="black")
                
                previews.append(self.get_base64_image(img))
            
            return previews
        except Exception as e:
            print(f"errore nella generazione dell'anteprima: {e}")
            return []
