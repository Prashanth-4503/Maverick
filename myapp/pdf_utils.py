# myapp/pdf_utils.py
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from math import sin, cos, pi, radians
import os

def register_fonts():
    """Register custom fonts with fallback to default fonts"""
    try:
        # Try to register elegant font
        font_path = os.path.join(os.path.dirname(__file__), 'fonts/GreatVibes-Regular.ttf')
        pdfmetrics.registerFont(TTFont('GreatVibes', font_path))
    except:
        # Fallback to similar font
        pdfmetrics.registerFont(TTFont('GreatVibes', 'Helvetica'))
    
    try:
        # Try to register modern font
        font_path = os.path.join(os.path.dirname(__file__), 'fonts/Montserrat-Regular.ttf')
        pdfmetrics.registerFont(TTFont('Montserrat', font_path))
        pdfmetrics.registerFont(TTFont('Montserrat-Bold', os.path.join(os.path.dirname(__file__), 'fonts/Montserrat-Bold.ttf')))
        pdfmetrics.registerFont(TTFont('Montserrat-Italic', os.path.join(os.path.dirname(__file__), 'fonts/Montserrat-Italic.ttf')))
    except:
        # Fallback to similar fonts
        pdfmetrics.registerFont(TTFont('Montserrat', 'Helvetica'))
        pdfmetrics.registerFont(TTFont('Montserrat-Bold', 'Helvetica-Bold'))
        pdfmetrics.registerFont(TTFont('Montserrat-Italic', 'Helvetica-Oblique'))

# Call this when your app starts (e.g., in apps.py)
register_fonts()

# Rest of your drawing functions...