"""
Asynchronous Celery tasks for billing, subscription lifecycle, and tax invoice generation.
Adheres strictly to BACKEND_ENGINEERING_RULES.md standards with typed signatures and full docstrings.
"""

import io
import logging
from decimal import Decimal
from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
from django.utils import timezone

from apps.billing.models import Payment, PaymentStatus

logger = logging.getLogger(__name__)


def generate_invoice_pdf(payment: Payment) -> bytes:
    """
    Generate a professional, high-fidelity PDF tax invoice and payment receipt using ReportLab.

    :param payment: The settled Payment model instance.
    :return: Binary PDF byte payload.
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        HRFlowable
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom typography styles
    brand_title_style = ParagraphStyle(
        'BrandTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#0F172A')
    )
    meta_style = ParagraphStyle(
        'MetaStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#475569')
    )
    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#FFFFFF')
    )
    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#1E293B')
    )
    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#0F172A')
    )
    footer_style = ParagraphStyle(
        'FooterStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=12,
        textColor=colors.HexColor('#94A3B8'),
        alignment=1
    )

    story = []

    # 1. Header with branding and invoice summary
    inv_number = f"INV-{str(payment.id).replace('-', '')[:8].upper()}"
    inv_date = payment.created_at.strftime("%d %b %Y") if payment.created_at else timezone.now().strftime("%d %b %Y")
    
    header_data = [
        [
            Paragraph("<b>INFLUENCERS.COM</b><br/><font size=9 color='#047857'>TAX INVOICE & PAYMENT RECEIPT</font>", brand_title_style),
            Paragraph(f"<font color='#047857'><b>STATUS: PAID</b></font><br/><b>Invoice No:</b> {inv_number}<br/><b>Date:</b> {inv_date}", ParagraphStyle('HRight', parent=meta_style, alignment=2))
        ]
    ]
    t_header = Table(header_data, colWidths=[330, 210])
    t_header.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(t_header)
    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#E2E8F0'), spaceAfter=14))

    # 2. Billed To & Platform Info
    user = payment.user
    company_name = ""
    contact_name = user.get_full_name() or user.username
    if hasattr(user, 'business_profile'):
        bp = user.business_profile
        company_name = bp.company_name
        if bp.contact_name:
            contact_name = bp.contact_name

    billed_to_html = f"<b>BILLED TO:</b><br/>"
    if company_name:
        billed_to_html += f"<b>{company_name}</b><br/>"
    billed_to_html += f"Attn: {contact_name}<br/>Email: {user.email}<br/>"

    pay_details_html = (
        f"<b>PAYMENT DETAILS:</b><br/>"
        f"<b>Method:</b> {payment.get_method_display() if hasattr(payment, 'get_method_display') else payment.method}<br/>"
        f"<b>Gateway Reference:</b> {payment.gateway_reference or 'N/A'}<br/>"
        f"<b>Currency:</b> {payment.currency.upper()}<br/>"
    )

    info_data = [
        [
            Paragraph(billed_to_html, meta_style),
            Paragraph(pay_details_html, meta_style)
        ]
    ]
    t_info = Table(info_data, colWidths=[270, 270])
    t_info.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
    ]))
    story.append(t_info)
    story.append(Spacer(1, 18))

    # 3. Itemized Services Table
    total_amount = Decimal(payment.amount_cents) / Decimal(100)
    base_amount = (total_amount / Decimal('1.18')).quantize(Decimal('0.01'))
    gst_amount = total_amount - base_amount

    # Try resolving plan name
    plan_name = "Platform Subscription"
    from apps.billing.models import Subscription
    sub = Subscription.objects.filter(user=user, is_deleted=False).select_related('plan').first()
    if sub and sub.plan:
        plan_name = f"{sub.plan.name} Plan ({sub.plan.get_interval_display() if hasattr(sub.plan, 'get_interval_display') else sub.plan.interval})"

    curr_sym = "₹" if payment.currency.upper() == 'INR' else "$"

    table_data = [
        [
            Paragraph("Item Description", table_header_style),
            Paragraph("Qty", table_header_style),
            Paragraph("Rate", table_header_style),
            Paragraph("Amount", table_header_style)
        ],
        [
            Paragraph(f"<b>Influencers.com {plan_name}</b><br/><font size=8 color='#64748B'>Full access to brand discovery, analytics, and collaboration workflows</font>", table_cell_style),
            Paragraph("1", table_cell_style),
            Paragraph(f"{curr_sym}{base_amount:,.2f}", table_cell_style),
            Paragraph(f"{curr_sym}{base_amount:,.2f}", table_cell_style)
        ],
        [
            Paragraph("Subtotal (excl. tax)", table_cell_style),
            Paragraph("", table_cell_style),
            Paragraph("", table_cell_style),
            Paragraph(f"{curr_sym}{base_amount:,.2f}", table_cell_style)
        ],
        [
            Paragraph("Goods and Services Tax (GST 18% Integrated)", table_cell_style),
            Paragraph("", table_cell_style),
            Paragraph("18%", table_cell_style),
            Paragraph(f"{curr_sym}{gst_amount:,.2f}", table_cell_style)
        ],
        [
            Paragraph("<b>Total Paid (Settled)</b>", table_cell_bold),
            Paragraph("", table_cell_style),
            Paragraph("", table_cell_style),
            Paragraph(f"<b>{curr_sym}{total_amount:,.2f}</b>", table_cell_bold)
        ]
    ]

    t_items = Table(table_data, colWidths=[290, 40, 100, 110])
    t_items.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, colors.HexColor('#E2E8F0')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#ECFDF5')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
    ]))
    story.append(t_items)
    story.append(Spacer(1, 24))

    # 4. Certification & Notes
    notes_p = Paragraph(
        "<b>Important Information:</b><br/>"
        "• This is an electronically generated computer invoice and serves as official receipt of settlement.<br/>"
        "• All services rendered are subject to Influencers.com Terms of Service and Master Service Agreement.<br/>"
        "• Questions regarding this invoice? Reach out to support@influencers.com.",
        meta_style
    )
    story.append(notes_p)
    story.append(Spacer(1, 30))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E2E8F0'), spaceAfter=10))

    footer_text = "Influencers.com Technologies · Registered Digital Marketplace Infrastructure · www.influencers.com"
    story.append(Paragraph(footer_text, footer_style))

    doc.build(story)
    return buffer.getvalue()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_payment_invoice_email_task(self, payment_id: str) -> bool:
    """
    Dispatch a branded HTML receipt and tax invoice PDF to the paying customer.

    :param self: Celery task execution instance for retry control.
    :param payment_id: UUID string primary key of Payment record.
    :return: True if the dispatch succeeded.
    """
    try:
        payment = Payment.objects.select_related('user').get(id=payment_id)
    except (Payment.DoesNotExist, ValueError) as err:
        logger.error(f"Payment '{payment_id}' not found for invoice dispatch: {err}")
        return False

    user = payment.user
    inv_number = f"INV-{str(payment.id).replace('-', '')[:8].upper()}"
    total_amount = Decimal(payment.amount_cents) / Decimal(100)
    curr_sym = "₹" if payment.currency.upper() == 'INR' else "$"
    formatted_amount = f"{curr_sym}{total_amount:,.2f}"

    subject = f"Payment Receipt & Tax Invoice #{inv_number} — Influencers.com"
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', '"Influencers.com" <support@influencers.com>')
    if '<' in from_email and not from_email.startswith('"'):
        name, addr = from_email.split('<', 1)
        name = name.strip()
        from_email = f'"{name}" <{addr}' if '.' in name else f'{name} <{addr}'

    # Generate PDF
    pdf_bytes = generate_invoice_pdf(payment)

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Payment Receipt</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #0f172a; line-height: 1.6;">
  <div style="max-width: 600px; margin: 32px auto; background-color: #ffffff; border-radius: 16px; overflow: hidden; border: 1px solid #e2e8f0; box-shadow: 0 4px 12px rgba(15, 23, 42, 0.05);">
    
    <!-- Header Banner -->
    <div style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); padding: 32px 24px; text-align: center;">
      <span style="display: inline-block; background: rgba(16, 185, 129, 0.2); color: #10b981; font-size: 11px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; padding: 4px 12px; border-radius: 20px;">
        Payment Receipt Confirmed
      </span>
      <h1 style="color: #ffffff; font-size: 24px; font-weight: 700; margin: 12px 0 0 0; letter-spacing: -0.5px;">
        Influencers<span style="color: #10b981;">.com</span>
      </h1>
      <p style="color: #94a3b8; font-size: 13px; margin: 6px 0 0 0;">
        Tax Invoice #{inv_number}
      </p>
    </div>

    <!-- Main Content -->
    <div style="padding: 32px 28px;">
      <h2 style="font-size: 18px; font-weight: 600; color: #0f172a; margin: 0 0 16px 0;">
        Thank you for your payment!
      </h2>
      <p style="font-size: 14px; color: #334155; margin: 0 0 16px 0;">
        Your subscription payment has been successfully processed and verified. Attached to this email is your official, GST-compliant tax invoice (PDF).
      </p>

      <!-- Payment Summary Table -->
      <div style="background-color: #f1f5f9; border-radius: 12px; padding: 18px 20px; margin: 24px 0;">
        <h3 style="font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #64748b; margin: 0 0 12px 0;">
          Transaction Summary
        </h3>
        <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
          <tr>
            <td style="padding: 6px 0; color: #64748b; width: 140px;">Amount Paid:</td>
            <td style="padding: 6px 0; font-weight: 700; color: #047857; font-size: 15px;">{formatted_amount}</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #64748b;">Invoice Reference:</td>
            <td style="padding: 6px 0; font-weight: 600; color: #0f172a;">{inv_number}</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #64748b;">Gateway Ref:</td>
            <td style="padding: 6px 0; font-family: monospace; color: #0f172a;">{payment.gateway_reference or 'Direct Gateway'}</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #64748b;">Status:</td>
            <td style="padding: 6px 0; font-weight: 600; color: #10b981;">PAID & SETTLED</td>
          </tr>
        </table>
      </div>

      <div style="text-align: center; margin: 28px 0;">
        <a href="http://localhost:8083/subscription" style="display: inline-block; background-color: #047857; color: #ffffff; text-decoration: none; font-size: 14px; font-weight: 600; padding: 12px 28px; border-radius: 10px;">
          View Subscription & Invoices →
        </a>
      </div>

      <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;" />

      <p style="font-size: 12px; color: #94a3b8; margin: 0;">
        A copy of your PDF invoice (<code>Invoice_{inv_number}.pdf</code>) is attached to this email for your accounting and taxation records.
      </p>
    </div>

    <!-- Footer -->
    <div style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 16px 24px; text-align: center;">
      <p style="font-size: 11px; color: #94a3b8; margin: 0;">
        © 2026 Influencers.com Inc. All rights reserved. Registered customer: {user.email}.
      </p>
    </div>

  </div>
</body>
</html>"""

    text_content = strip_tags(html_content)

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[user.email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.attach(f"Invoice_{inv_number}.pdf", pdf_bytes, "application/pdf")
        sent = msg.send(fail_silently=False)
        logger.info(f"Successfully emailed invoice {inv_number} to {user.email} (sent={sent})")
        return True
    except Exception as exc:
        logger.error(f"Failed to dispatch invoice email to {user.email}: {exc}")
        if not getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
            raise self.retry(exc=exc)
        return False

