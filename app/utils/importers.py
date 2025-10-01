import csv
import io
from typing import List, Dict

import pandas as pd
import pdfplumber


REQUIRED_HEADERS = {'ad', 'soyad', 'okul_numarasi', 'sinif'}


def parse_csv(file_storage) -> List[Dict[str, str]]:
    data = file_storage.read().decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(data))
    headers = {h.strip().lower() for h in reader.fieldnames or []}
    if not REQUIRED_HEADERS.issubset(headers):
        raise ValueError('CSV başlıkları eksik. Gerekli başlıklar: ad, soyad, okul_numarasi, sinif')

    students = []
    for row in reader:
        students.append(
            {
                'full_name': f"{row.get('ad', '').strip()} {row.get('soyad', '').strip()}".strip(),
                'student_number': str(row.get('okul_numarasi', '')).strip(),
                'class_name': row.get('sinif', '').strip(),
            }
        )
    return students


def parse_pdf(file_storage) -> List[Dict[str, str]]:
    students: List[Dict[str, str]] = []
    with pdfplumber.open(file_storage) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if not table:
                continue
            df = pd.DataFrame(table[1:], columns=[c.strip().lower() for c in table[0]])
            if not REQUIRED_HEADERS.issubset(set(df.columns)):
                continue
            for _, row in df.iterrows():
                students.append(
                    {
                        'full_name': f"{str(row.get('ad', '')).strip()} {str(row.get('soyad', '')).strip()}".strip(),
                        'student_number': str(row.get('okul_numarasi', '')).strip(),
                        'class_name': str(row.get('sinif', '')).strip(),
                    }
                )
    if not students:
        raise ValueError('PDF içeriği okunamadı. Lütfen tablo formatında olduğundan emin olun.')
    return students
