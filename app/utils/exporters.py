import csv
import io
from datetime import datetime
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFError, TTFont
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from ..models import AttendanceRecord


STATUS_LABELS = {
    'present': 'Var',
    'excused': 'Mazeretli',
    'absent': 'Mazeretsiz',
}


def generate_csv(records: Iterable[AttendanceRecord]) -> io.BytesIO:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Ders', 'Sınıf', 'Öğretmen', 'Tarih', 'Öğrenci', 'Durum'])
    for record in records:
        for entry in record.entries:
            writer.writerow(
                [
                    record.course.name,
                    record.classroom.name,
                    record.teacher.full_name,
                    record.session_date.strftime('%d.%m.%Y %H:%M'),
                    entry.student.full_name,
                    STATUS_LABELS.get(entry.status, entry.status),
                ]
            )
    buffer = io.BytesIO()
    buffer.write(output.getvalue().encode('utf-8-sig'))
    buffer.seek(0)
    return buffer


def generate_pdf(records: Iterable[AttendanceRecord]) -> io.BytesIO:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    fonts_to_register = {
        'DejaVuSans': '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        'DejaVuSans-Bold': '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    }
    registered_fonts = set(pdfmetrics.getRegisteredFontNames())

    for font_name, font_path in fonts_to_register.items():
        if font_name in registered_fonts:
            continue
        try:
            pdfmetrics.registerFont(TTFont(font_name, font_path))
        except (TTFError, FileNotFoundError, OSError):
            continue
        registered_fonts.add(font_name)

    if 'DejaVuSans' in registered_fonts:
        styles['Normal'].fontName = 'DejaVuSans'
        styles['BodyText'].fontName = 'DejaVuSans'
    if 'DejaVuSans-Bold' in registered_fonts:
        styles['Heading3'].fontName = 'DejaVuSans-Bold'

    header_font = 'DejaVuSans-Bold' if 'DejaVuSans-Bold' in registered_fonts else 'Helvetica-Bold'
    body_font = 'DejaVuSans' if 'DejaVuSans' in registered_fonts else 'Helvetica'

    for record in records:
        story.append(Paragraph(f"Ders: {record.course.name} ({record.course.code})", styles['Heading3']))
        story.append(Paragraph(f"Sınıf: {record.classroom.name}", styles['Normal']))
        story.append(Paragraph(f"Öğretmen: {record.teacher.full_name}", styles['Normal']))
        story.append(Paragraph(f"Tarih: {record.session_date.strftime('%d.%m.%Y %H:%M')}", styles['Normal']))
        story.append(Spacer(1, 8))
        data = [['Öğrenci', 'Durum']]
        for entry in record.entries:
            data.append([entry.student.full_name, STATUS_LABELS.get(entry.status, entry.status)])
        table = Table(data, hAlign='LEFT')
        table.setStyle(
            TableStyle(
                [
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), header_font),
                    ('FONTNAME', (0, 1), (-1, -1), body_font),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ]
            )
        )
        story.append(table)
        story.append(Spacer(1, 16))

    doc.build(story)
    buffer.seek(0)
    return buffer
