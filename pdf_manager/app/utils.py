"""Utility functions for PDF watermarking and security."""
import io
import os
import uuid
from datetime import datetime, timedelta
from PIL import Image

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import Color
from PyPDF2 import PdfReader, PdfWriter


def add_watermark_to_pdf(input_pdf_path, output_pdf_path, user_email, download_id, app_name='PDF Manager'):
    """
    Add watermark to PDF with user information.

    Args:
        input_pdf_path: Path to original PDF
        output_pdf_path: Path to save watermarked PDF
        user_email: User's email for watermark
        download_id: Unique download ID
        app_name: Application name for watermark

    Returns:
        Path to watermarked PDF
    """
    # Create watermark text
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M')
    year = datetime.now().year

    # Create watermark PDF
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)

    # Set semi-transparent gray color
    watermark_color = Color(0.5, 0.5, 0.5, alpha=0.3)
    can.setFillColor(watermark_color)
    can.setFont("Helvetica", 8)

    # Top right corner - user info
    can.drawString(350, 780, f"POUFNE - TYLKO DLA: {user_email}")
    can.drawString(350, 768, f"Pobranie: {current_time}")

    # Bottom left corner - ID and legal notice
    can.drawString(50, 50, f"ID: {download_id}")
    can.drawString(50, 38, "Nieautoryzowane rozpowszechnianie zabronione")
    can.drawString(50, 26, f"© {year} {app_name}")

    # Diagonal watermark in center (larger, very faint)
    can.saveState()
    can.setFillColor(Color(0.7, 0.7, 0.7, alpha=0.1))
    can.setFont("Helvetica", 40)
    can.translate(300, 400)
    can.rotate(45)
    can.drawCentredString(0, 0, "POUFNE")
    can.restoreState()

    can.save()
    packet.seek(0)

    # Read the watermark PDF
    watermark_pdf = PdfReader(packet)
    watermark_page = watermark_pdf.pages[0]

    # Read the input PDF
    input_pdf = PdfReader(input_pdf_path)
    output_pdf = PdfWriter()

    # Apply watermark to each page
    for page in input_pdf.pages:
        page.merge_page(watermark_page)
        output_pdf.add_page(page)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_pdf_path), exist_ok=True)

    # Save watermarked PDF
    with open(output_pdf_path, 'wb') as f:
        output_pdf.write(f)

    return output_pdf_path


def generate_download_id():
    """Generate a unique short download ID."""
    return str(uuid.uuid4())[:8].upper()


def check_suspicious_activity(user_id, file_id, threshold=5, hours=1):
    """
    Check if user is downloading a file suspiciously often.

    Args:
        user_id: User ID
        file_id: File ID
        threshold: Number of downloads to consider suspicious
        hours: Time window in hours

    Returns:
        True if suspicious, False otherwise
    """
    from app.models import FileDownload

    recent_downloads = FileDownload.get_recent_downloads(user_id, file_id, hours)
    return recent_downloads >= threshold


def send_suspicious_activity_alert(user, file, download_count, hours=1):
    """
    Send alert to admins about suspicious download activity.

    Args:
        user: User object
        file: File object
        download_count: Number of recent downloads
        hours: Time window
    """
    from app.models import User
    from app.email import send_email

    admins = User.query.filter_by(is_admin=True).all()

    subject = "⚠️ Podejrzana aktywność - nadmierne pobieranie"
    body = f"""<p>Wykryto podejrzaną aktywność:</p>

<p><strong>Użytkownik:</strong> {user.email}<br>
<strong>Plik:</strong> {file.original_filename}<br>
<strong>Liczba pobrań:</strong> {download_count} razy w ciągu ostatniej godziny</p>

<p>Możliwa próba masowego pobierania/udostępniania plików.</p>

<hr>
<p><small>Wiadomość wygenerowana automatycznie przez PDF Manager</small></p>"""

    for admin in admins:
        try:
            send_email(admin.email, subject, body)
        except Exception as e:
            # Log error but don't fail
            print(f"Failed to send alert to {admin.email}: {e}")


def resize_logo(input_path, output_path, max_width=200):
    """
    Resize logo image to maximum width while maintaining aspect ratio.

    Args:
        input_path: Path to original image
        output_path: Path to save resized image
        max_width: Maximum width in pixels

    Returns:
        Path to resized image
    """
    with Image.open(input_path) as img:
        # Convert to RGB if necessary (for PNG with transparency)
        if img.mode in ('RGBA', 'P'):
            # Create white background
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'RGBA':
                background.paste(img, mask=img.split()[3])  # Use alpha channel as mask
            else:
                background.paste(img)
            img = background

        # Calculate new size
        if img.width > max_width:
            ratio = max_width / img.width
            new_size = (max_width, int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Save
        img.save(output_path, quality=95)

    return output_path


def validate_hex_color(color):
    """
    Validate that a string is a valid hex color.

    Args:
        color: Color string to validate

    Returns:
        True if valid hex color, False otherwise
    """
    if not color:
        return False
    if not color.startswith('#'):
        return False
    if len(color) != 7:
        return False
    try:
        int(color[1:], 16)
        return True
    except ValueError:
        return False


def cleanup_temp_file(filepath):
    """
    Remove a temporary file if it exists.

    Args:
        filepath: Path to file to remove
    """
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
    except Exception:
        pass  # Ignore cleanup errors
