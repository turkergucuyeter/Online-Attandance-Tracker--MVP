import csv
import io
from typing import Dict, List

import pandas as pd
import pdfplumber


REQUIRED_HEADERS = {'ad', 'soyad', 'okul_numarasi', 'sinif'}


def parse_csv(file_storage) -> List[Dict[str, str]]:
    """Parse a CSV file and return normalized student dictionaries."""
    file_storage.stream.seek(0)
    data = file_storage.read().decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(data))
    headers = {h.strip().lower() for h in reader.fieldnames or []}
    if not REQUIRED_HEADERS.issubset(headers):
        raise ValueError(
            'CSV başlıkları eksik. Gerekli başlıklar: ad, soyad, okul_numarasi, sinif',
        )

    students: List[Dict[str, str]] = []
    for row_index, row in enumerate(reader, start=2):
        students.append(
            {
                'full_name': f"{row.get('ad', '').strip()} {row.get('soyad', '').strip()}".strip(),
                'student_number': str(row.get('okul_numarasi', '')).strip(),
                'class_name': row.get('sinif', '').strip(),
                'source_row': row_index,
            }
        )
    return students


def parse_pdf(file_storage) -> List[Dict[str, str]]:
    """Parse a PDF table and return normalized student dictionaries."""
    file_storage.stream.seek(0)
    students: List[Dict[str, str]] = []
    with pdfplumber.open(file_storage) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if not table:
                continue
            headers = [c.strip().lower() for c in table[0]]
            df = pd.DataFrame(table[1:], columns=headers).fillna('')
            if not REQUIRED_HEADERS.issubset(set(df.columns)):
                continue
            for row_index, row in enumerate(df.to_dict(orient='records'), start=2):
                students.append(
                    {
                        'full_name': f"{str(row.get('ad', '')).strip()} {str(row.get('soyad', '')).strip()}".strip(),
                        'student_number': str(row.get('okul_numarasi', '')).strip(),
                        'class_name': str(row.get('sinif', '')).strip(),
                        'source_row': row_index,
                    }
                )
    if not students:
        raise ValueError('PDF içeriği okunamadı. Lütfen tablo formatında olduğundan emin olun.')
    return students


def parse_excel(file_storage) -> List[Dict[str, str]]:
    """Parse an Excel file (.xls/.xlsx) and return normalized student dictionaries."""
    file_storage.stream.seek(0)
    try:
        data = file_storage.read()
        dataframe = pd.read_excel(io.BytesIO(data), dtype=str)
    except ValueError as exc:  # noqa: BLE001
        raise ValueError('Excel dosyası okunamadı. Lütfen geçerli bir dosya yükleyin.') from exc

    dataframe.columns = [str(col).strip().lower() for col in dataframe.columns]
    if not REQUIRED_HEADERS.issubset(set(dataframe.columns)):
        raise ValueError(
            'Excel başlıkları eksik. Gerekli başlıklar: ad, soyad, okul_numarasi, sinif',
        )

    dataframe = dataframe.fillna('')

    students: List[Dict[str, str]] = []
    for row_index, row in enumerate(dataframe.to_dict(orient='records'), start=2):
        students.append(
            {
                'full_name': f"{str(row.get('ad', '')).strip()} {str(row.get('soyad', '')).strip()}".strip(),
                'student_number': str(row.get('okul_numarasi', '')).strip(),
                'class_name': str(row.get('sinif', '')).strip(),
                'source_row': row_index,
            }
        )

    if not students:
        raise ValueError('Excel dosyasında öğrenci verisi bulunamadı.')
    return students
