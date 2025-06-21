# Create a basic Streamlit app with a title and instructions for uploading a document
import streamlit as st
import pytesseract
from PIL import Image
from pdf2image import convert_from_bytes
from pdfminer.high_level import extract_text as extract_pdf_text
import io
import re
from datetime import datetime
import urllib.parse

def extract_text_from_image(image_bytes):
    image = Image.open(io.BytesIO(image_bytes))
    return pytesseract.image_to_string(image)

def extract_text_from_pdf(pdf_bytes):
    # Try extracting text directly (for text-based PDFs)
    text = extract_pdf_text(io.BytesIO(pdf_bytes))
    if text.strip():
        return text
    # If no text found, fallback to OCR on images
    images = convert_from_bytes(pdf_bytes)
    ocr_text = ''
    for i, img in enumerate(images):
        ocr_text += f'--- Page {i+1} ---\n'
        ocr_text += pytesseract.image_to_string(img)
        ocr_text += '\n'
    return ocr_text

def normalize_expiry_date(date_str):
    # Convert all to mm/dd/yyyy if possible, else mm/yyyy
    parts = date_str.split('/')
    if len(parts) == 3:
        mm, dd, yyyy = parts
    elif len(parts) == 2:
        mm, yyyy = parts
        dd = None
    else:
        return None
    if len(yyyy) == 2:
        yyyy = str(datetime.now().year)[:2] + yyyy
    if dd:
        return f"{mm.zfill(2)}/{dd.zfill(2)}/{yyyy}"
    else:
        return f"{mm.zfill(2)}/{yyyy}"

def extract_expiry_dates(text):
    expiry_keywords = r'(exp(?:iry|iration)?\s*date|exp\s*date|exp\.|expires|valid\s*thru|valid\s*until|exp|good\s*thru|good\s*until|validity|exp)'  # expanded
    date_patterns = [
        r'(0[1-9]|1[0-2])[\/\-](0[1-9]|[12][0-9]|3[01])[\/\-](\d{2,4})',  # mm/dd/yyyy or mm-dd-yyyy or mm/dd/yy
        r'(0[1-9]|1[0-2])[\/\-](\d{2,4})',                                  # mm/yyyy or mm-yy
    ]
    candidates = set()
    current_century = str(datetime.now().year)[:2]
    lines = text.splitlines()
    # 1. Look for expiry keyword and date on the same line
    for line in lines:
        if re.search(expiry_keywords, line, re.IGNORECASE):
            for pattern in date_patterns:
                found = re.findall(pattern, line)
                for match in found:
                    if len(match) == 3:
                        year = match[2]
                        if len(year) == 2:
                            year = current_century + year
                        candidates.add(f"{match[0]}/{match[1]}/{year}")
                    elif len(match) == 2:
                        year = match[1]
                        if len(year) == 2:
                            year = current_century + year
                        candidates.add(f"{match[0]}/{year}")
    # 2. If not found, look for a line where the keyword is immediately followed by a date (e.g., 'EXP 08-30-2028')
    if not candidates:
        for i, line in enumerate(lines):
            if re.search(expiry_keywords, line, re.IGNORECASE):
                # Check next line for a date
                if i+1 < len(lines):
                    next_line = lines[i+1]
                    for pattern in date_patterns:
                        found = re.findall(pattern, next_line)
                        for match in found:
                            if len(match) == 3:
                                year = match[2]
                                if len(year) == 2:
                                    year = current_century + year
                                candidates.add(f"{match[0]}/{match[1]}/{year}")
                            elif len(match) == 2:
                                year = match[1]
                                if len(year) == 2:
                                    year = current_century + year
                                candidates.add(f"{match[0]}/{year}")
    # 3. As a last resort, pick the most likely date pattern in the whole text
    if not candidates:
        for pattern in date_patterns:
            found = re.findall(pattern, text)
            for match in found:
                if len(match) == 3:
                    year = match[2]
                    if len(year) == 2:
                        year = current_century + year
                    candidates.add(f"{match[0]}/{match[1]}/{year}")
                elif len(match) == 2:
                    year = match[1]
                    if len(year) == 2:
                        year = current_century + year
                    candidates.add(f"{match[0]}/{year}")
    # Normalize and pick the latest expiry date, prefer mm/dd/yyyy if available
    normalized = set()
    for c in candidates:
        norm = normalize_expiry_date(c)
        if norm:
            normalized.add(norm)
    if not normalized:
        return []
    def date_key(d):
        parts = d.split('/')
        if len(parts) == 3:
            mm, dd, yyyy = parts
        else:
            mm, yyyy = parts
            dd = '01'  # fallback for sorting
        return int(yyyy)*10000 + int(mm)*100 + int(dd)
    sorted_dates = sorted(normalized, key=date_key, reverse=True)
    for d in sorted_dates:
        if len(d.split('/')) == 3:
            return [d]
    return [sorted_dates[0]]

def create_google_calendar_link(expiry_date_str):
    # expiry_date_str: mm/dd/yyyy or mm/dd/yyyy
    from datetime import datetime, timedelta
    try:
        if len(expiry_date_str.split('/')) == 3:
            dt = datetime.strptime(expiry_date_str, "%m/%d/%Y")
        else:
            dt = datetime.strptime(expiry_date_str, "%m/%Y")
    except Exception:
        return None
    reminder_date = dt - timedelta(days=30)
    start = reminder_date.strftime("%Y%m%d")
    end = (reminder_date + timedelta(hours=1)).strftime("%Y%m%d")
    title = urllib.parse.quote("Document Expiry Reminder")
    details = urllib.parse.quote(f"Your document expires on {expiry_date_str}. Renew soon!")
    link = f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={title}&dates={start}/{end}&details={details}"
    return link

def main():
    st.title("Document Upload App")
    st.write("Upload an image or PDF to extract expiry dates using OCR.")
    uploaded_file = st.file_uploader("Choose an image or PDF file", type=["pdf", "png", "jpg", "jpeg"])
    if uploaded_file is not None:
        st.success("File uploaded successfully!")
        file_bytes = uploaded_file.read()
        if uploaded_file.type == "application/pdf":
            text = extract_text_from_pdf(file_bytes)
        else:
            text = extract_text_from_image(file_bytes)
        expiry_dates = extract_expiry_dates(text)
        st.subheader("Extracted Expiry Dates:")
        if expiry_dates:
            for date in expiry_dates:
                st.write(f"- {date}")
                cal_link = create_google_calendar_link(date)
                if cal_link:
                    st.markdown(f"[Add 30-day reminder to Google Calendar]({cal_link})", unsafe_allow_html=True)
        else:
            st.write("No expiry dates found.")
        with st.expander("Show Full Extracted Text"):
            st.text_area("Text", text, height=200)

if __name__ == "__main__":
    main()






