import re
import spacy
from django.shortcuts import render
from django.core.files.storage import FileSystemStorage
from pypdf import PdfReader
from docx import Document
from PIL import Image
import pytesseract

# Load local spaCy model once at startup
nlp = spacy.load("en_core_web_sm")


def extract_text_from_file(file_obj, filename):
    ext = filename.lower().split(".")[-1]
    text = ""

    if ext == "txt":
        text = file_obj.read().decode("utf-8", errors="ignore")

    elif ext == "pdf":
        reader = PdfReader(file_obj)
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"

    elif ext == "docx":
        doc = Document(file_obj)
        text = "\n".join([para.text for para in doc.paragraphs])

    elif ext in ["jpg", "jpeg"]:
        image = Image.open(file_obj)
        text = pytesseract.image_to_string(image)

    return text.strip()


def analyze_legal_text(text):
    doc = nlp(text[:100000])  # Cap length for fast local processing

    # 1. Extract Entities (Parties, Dates, Money, Laws)
    entities = {
        "Parties / Organizations": list(
            set([ent.text for ent in doc.ents if ent.label_ in ["ORG", "PERSON"]])
        ),
        "Dates & Deadlines": list(
            set([ent.text for ent in doc.ents if ent.label_ == "DATE"])
        ),
        "Financial Terms": list(
            set([ent.text for ent in doc.ents if ent.label_ == "MONEY"])
        ),
        "Jurisdictions / Locations": list(
            set([ent.text for ent in doc.ents if ent.label_ == "GPE"])
        ),
    }

    # 2. Detect Common Legal Clauses via Keyword Matching
    clause_patterns = {
        "Confidentiality / NDA": r"\b(confidential|non-disclosure|proprietary information)\b",
        "Termination": r"\b(terminate|termination|breach of contract|notice period)\b",
        "Indemnification & Liability": r"\b(indemnify|indemnification|hold harmless|liability)\b",
        "Governing Law": r"\b(governing law|jurisdiction|arbitration|dispute resolution)\b",
        "Payment Terms": r"\b(payment|invoice|compensation|fee|remuneration)\b",
    }

    detected_clauses = []
    for clause_name, pattern in clause_patterns.items():
        if re.search(pattern, text, re.IGNORECASE):
            detected_clauses.append(clause_name)

    # 3. Simple Extractive Summary (First 3 substantive sentences)
    sentences = [
        sent.text.strip() for sent in doc.sents if len(sent.text.strip()) > 40
    ]
    summary = (
        " ".join(sentences[:3])
        if sentences
        else "Document too short to summarize."
    )

    return {
        "word_count": len(text.split()),
        "summary": summary,
        "entities": entities,
        "clauses": detected_clauses,
    }


def lex_ai_view(request):
    context = {}
    if request.method == "POST" and request.FILES.get("legal_doc"):
        uploaded_file = request.FILES["legal_doc"]
        filename = uploaded_file.name
        ext = filename.lower().split(".")[-1]

        if ext not in ["pdf", "txt", "docx", "jpg", "jpeg"]:
            context["error"] = (
                "Unsupported file format. Please upload PDF, TXT, DOCX, or JPEG."
            )
            return render(request, "index4.html", context)

        try:
            raw_text = extract_text_from_file(uploaded_file, filename)
            if not raw_text:
                context["error"] = (
                    "No readable text could be extracted from this file."
                )
            else:
                analysis = analyze_legal_text(raw_text)
                context["filename"] = filename
                context["raw_text"] = (
                    raw_text[:2000] + "..." if len(raw_text) > 2000 else raw_text
                )
                context["analysis"] = analysis
        except Exception as e:
            context["error"] = f"Error processing document: {str(e)}"

    return render(request, "index4.html", context)
