import os
from io import BytesIO
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, Frame
from reportlab.lib.units import inch
from reportlab.lib import colors
from django.conf import settings

def generate_certificate_pdf(certificate):
    """Generate a PDF certificate with dynamic content"""
    buffer = BytesIO()
    width, height = landscape(letter)  # Use landscape orientation
    c = canvas.Canvas(buffer, pagesize=(width, height))
    
    # Set up styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=36,
        leading=42,
        alignment=1,  # Center aligned
        spaceAfter=24,
        textColor=colors.navy
    )
    
    # Background (optional)
    if os.path.exists(settings.BASE_DIR / 'static/images/certificate_bg.jpg'):
        c.drawImage(
            str(settings.BASE_DIR / 'static/images/certificate_bg.jpg'),
            0, 0, width=width, height=height
        )
    
    # Main content
    elements = []
    
    # Certificate title
    elements.append(Paragraph("CERTIFICATE OF COMPLETION", title_style))
    
    # Award text
    award_text = f"""
    <para align=center spaceb=3>
    This is to certify that<br/>
    <font size=18><b>{certificate.user.get_full_name()}</b></font><br/>
    has successfully completed the<br/>
    <font size=16><b>{certificate.module.name}</b></font><br/>
    on {certificate.date_issued.strftime('%B %d, %Y')}
    </para>
    """
    elements.append(Paragraph(award_text, styles['Normal']))
    
    # Draw all elements
    frame = Frame(
        1*inch, 2*inch,  # x, y position
        width-2*inch, height-4*inch,  # width, height
        showBoundary=0  # hide frame boundary
    )
    frame.addFromList(elements, c)
    
    # Verification info
    c.setFont("Helvetica", 10)
    c.drawRightString(
        width-0.5*inch, 0.5*inch,
        f"Certificate ID: {certificate.certificate_id}"
    )
    
    # Save the PDF
    c.save()
    buffer.seek(0)
    return buffer