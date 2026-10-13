from pathlib import Path
from uuid import uuid4
from io import BytesIO
from xml.sax.saxutils import escape
from flask import Blueprint, request, jsonify, current_app, g, send_file
from sqlalchemy import select
from werkzeug.utils import secure_filename
from werkzeug.exceptions import BadRequest, Forbidden
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from app.models import Attachment, Customer, Order, Product, Payment
from app.extensions import db
from app.services.access import get, customer, order, quote, role
from app.services.audit import audit
from app.services.serialization import base, quotation
bp=Blueprint('files',__name__)

def access(entity,id,write=False):
    if entity=='customers': return customer(id,write)
    if entity=='orders':
        role('admin','sales','finance')
        if write: role('admin','sales','finance')
        return order(id)
    if entity=='products':
        role('admin','sales','procurement')
        if write: role('admin','procurement')
        return get(Product,id)
    if entity=='payments':
        role('admin','finance');p=get(Payment,id);order(p.order_id);return p
    raise BadRequest('不支持的附件对象')

@bp.get('/api/attachments/<entity>/<int:id>')
def list_attachments(entity,id):
    access(entity,id);return jsonify([base(a) for a in db().scalars(select(Attachment).where(Attachment.entity==entity,Attachment.entity_id==id))])

@bp.post('/api/attachments/<entity>/<int:id>')
def upload(entity,id):
    access(entity,id,True);file=request.files.get('file')
    if not file or not file.filename: raise BadRequest('请选择文件')
    ext=Path(file.filename).suffix.lower()
    if ext not in {'.pdf','.png','.jpg','.jpeg','.webp','.csv','.xlsx','.docx','.txt'}: raise BadRequest('支持 PDF、图片、CSV、XLSX、DOCX 和 TXT')
    if ext in {'.png','.jpg','.jpeg','.webp'}:
        from PIL import Image, UnidentifiedImageError
        try:
            image=Image.open(file.stream)
            if image.format not in ['PNG','JPEG','WEBP'] or image.width*image.height>25000000: raise ValueError()
            image.verify();file.stream.seek(0)
        except (ValueError,OSError,Image.DecompressionBombError,Image.DecompressionBombWarning): raise BadRequest('图片格式无效或超过 2500 万像素')
    storage=uuid4().hex+ext;path=Path(current_app.config['UPLOAD_PATH'])/storage
    file.save(path)
    a=Attachment(entity=entity,entity_id=id,filename=Path(file.filename.replace('\\','/')).name[:250],storage_name=storage,user_id=g.user.id)
    db().add(a);audit('上传附件',a);return jsonify(base(a)),201

@bp.get('/api/attachments/<int:id>/download')
def download(id):
    a=get(Attachment,id);access(a.entity,a.entity_id)
    return send_file(Path(current_app.config['UPLOAD_PATH'])/a.storage_name,as_attachment=True,download_name=a.filename)

@bp.get('/api/quotations/<int:id>/pdf')
def quote_pdf(id):
    q=quote(id);d=quotation(q);c=get(Customer,q.customer_id)
    pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
    styles=getSampleStyleSheet()
    for s in styles.byName.values(): s.fontName='STSong-Light';s.leading=15
    buffer=BytesIO();doc=SimpleDocTemplate(buffer,title=q.number,author='Yuanfan CRM')
    def p(v): return Paragraph(escape(str(v)),styles['Normal'])
    story=[Paragraph('QUOTATION / 产品报价单',styles['Title']),Spacer(1,20),p('编号：'+q.number+'  |  版本：'+str(q.version)),p('客户：'+c.name),p('有效期：'+q.valid_until+'  |  币种：'+q.currency),Spacer(1,18)]
    data=[[p(s) for s in ['产品 / 规格','数量','单位','单价','金额']]]
    for l in d['lines']:
        data.append([p(l['name']+' / '+l['spec']),p(l['quantity']),p(l['unit']),p(f"{l['price']/100:,.2f}"),p(f"{l['price']*l['quantity']/100:,.2f}")])
    t=Table(data,colWidths=[225,45,40,70,80],repeatRows=1)
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#eeeeff')),('GRID',(0,0),(-1,-1),.3,colors.HexColor('#dddddd')),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),9)]))
    story.extend([t,Spacer(1,16),p(f"合计：{q.currency} {d['amount']/100:,.2f}"),Spacer(1,15)])
    for title,value in [('贸易术语及地点',q.term),('付款条件',q.payment_terms),('交期',q.lead_time),('备注',q.notes)]: story.append(p(title+'：'+value))
    doc.build(story);buffer.seek(0)
    return send_file(buffer,mimetype='application/pdf',as_attachment=True,download_name=q.number+'.pdf')

@bp.get('/api/attachments/<int:id>/preview')
def preview(id):
    a=get(Attachment,id);access(a.entity,a.entity_id)
    if Path(a.storage_name).suffix.lower() not in {'.png','.jpg','.jpeg','.webp'}: raise BadRequest('该附件不支持图片预览')
    return send_file(Path(current_app.config['UPLOAD_PATH'])/a.storage_name,as_attachment=False,download_name=a.filename)
