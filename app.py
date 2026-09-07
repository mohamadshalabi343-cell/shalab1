import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from database import *
from datetime import date, timedelta
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
uri = os.environ.get('DATABASE_URL', 'sqlite:///workshop.db')
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()

# ============ دوال مساعدة ============

def get_weekly_range():
    """تعيد بداية الأسبوع (السبت) ونهايته (الخميس) وآخر خميس"""
    today = date.today()
    days_since_thursday = (today.weekday() - 3) % 7
    last_thursday = today - timedelta(days=days_since_thursday)
    start_date = last_thursday - timedelta(days=6)
    end_date = last_thursday + timedelta(days=1)
    return start_date, end_date, last_thursday

# ============ الصفحات الرئيسية ============

@app.route('/')
def index():
    records = RepairRecord.query.order_by(RepairRecord.created_at.desc()).all()
    workers = Worker.query.all()

    total_records = len(records)
    total_revenue = sum(r.effective_amount_received for r in records)
    total_cost = sum(r.cost for r in records)
    total_profit = total_revenue - total_cost

    worker_stats = {}
    for worker in workers:
        worker_records = [r for r in records if r.worker_id == worker.id]
        worker_stats[worker.name] = {
            'count': len(worker_records),
            'revenue': sum(r.effective_amount_received for r in worker_records),
            'cost': sum(r.cost for r in worker_records),
            'profit': sum(r.profit for r in worker_records)
        }

    return render_template('index.html',
                          records=records,
                          workers=workers,
                          total_records=total_records,
                          total_revenue=total_revenue,
                          total_cost=total_cost,
                          total_profit=total_profit,
                          worker_stats=worker_stats)

@app.route('/add', methods=['GET', 'POST'])
def add_record():
    if request.method == 'POST':
        try:
            worker_id = int(request.form.get('worker_id'))
            device_name = request.form.get('device_name', '').strip()
            device_model = request.form.get('device_model', '').strip()
            cost = float(request.form.get('cost', 0) or 0)
            amount_received = float(request.form.get('amount_received', 0) or 0)
            issues = request.form.get('issues', '').strip()
            notes = request.form.get('notes', '').strip()
            status = request.form.get('status', 'تم التسليم')

            if not device_name:
                flash('اسم الجهاز مطلوب!', 'error')
                return redirect(url_for('add_record'))

            if not worker_id:
                flash('اسم العامل مطلوب!', 'error')
                return redirect(url_for('add_record'))

            # التحقق من وجود العامل
            worker = Worker.query.get(worker_id)
            if not worker:
                flash('العامل المحدد غير موجود!', 'error')
                return redirect(url_for('add_record'))

            record = RepairRecord(
                worker_id=worker_id,
                device_name=device_name,
                device_model=device_model,
                cost=cost,
                amount_received=amount_received,
                issues=issues,
                notes=notes,
                status=status
            )

            db.session.add(record)
            db.session.commit()

            flash('تمت إضافة السجل بنجاح!', 'success')
            return redirect(url_for('index'))

        except ValueError:
            flash('خطأ في البيانات: تأكد من إدخال أرقام صحيحة', 'error')
        except Exception as e:
            flash(f'حدث خطأ: {str(e)}', 'error')

    workers = Worker.query.all()
    return render_template('add_record.html', workers=workers)

@app.route('/edit/<int:record_id>', methods=['GET', 'POST'])
def edit_record(record_id):
    record = RepairRecord.query.get_or_404(record_id)

    if request.method == 'POST':
        try:
            worker_id = int(request.form.get('worker_id'))
            # التحقق من وجود العامل
            worker = Worker.query.get(worker_id)
            if not worker:
                flash('العامل المحدد غير موجود!', 'error')
                return redirect(url_for('edit_record', record_id=record_id))

            record.worker_id = worker_id
            record.device_name = request.form.get('device_name', '').strip()
            record.device_model = request.form.get('device_model', '').strip()
            record.cost = float(request.form.get('cost', 0) or 0)
            record.amount_received = float(request.form.get('amount_received', 0) or 0)
            record.issues = request.form.get('issues', '').strip()
            record.notes = request.form.get('notes', '').strip()
            record.status = request.form.get('status', 'مكتمل')
            record.updated_at = datetime.utcnow()

            db.session.commit()

            flash('تم تحديث السجل بنجاح!', 'success')
            return redirect(url_for('index'))

        except ValueError:
            flash('خطأ في البيانات: تأكد من إدخال أرقام صحيحة', 'error')
        except Exception as e:
            flash(f'حدث خطأ: {str(e)}', 'error')

    workers = Worker.query.all()
    return render_template('edit_record.html', record=record, workers=workers)

@app.route('/delete/<int:record_id>', methods=['POST'])
def delete_record(record_id):
    record = RepairRecord.query.get_or_404(record_id)
    try:
        db.session.delete(record)
        db.session.commit()
        flash('تم حذف السجل بنجاح!', 'success')
    except Exception as e:
        flash(f'حدث خطأ أثناء الحذف: {str(e)}', 'error')

    return redirect(url_for('index'))

@app.route('/view/<int:record_id>')
def view_record(record_id):
    record = RepairRecord.query.get_or_404(record_id)
    return render_template('view_record.html', record=record)

# ============ إدارة العمال ============

@app.route('/workers')
def workers():
    all_workers = Worker.query.all()
    worker_performance = {}

    for worker in all_workers:
        records = RepairRecord.query.filter_by(worker_id=worker.id).all()
        worker_performance[worker.id] = {
            'total_records': len(records),
            'total_revenue': sum(r.effective_amount_received for r in records),
            'total_profit': sum(r.profit for r in records)
        }

    return render_template('workers.html',
                          workers=all_workers,
                          worker_performance=worker_performance)

@app.route('/add_worker', methods=['POST'])
def add_worker():
    name = request.form.get('worker_name', '').strip()

    if not name:
        flash('اسم العامل مطلوب!', 'error')
        return redirect(url_for('workers'))

    existing = Worker.query.filter_by(name=name).first()
    if existing:
        flash('هذا الاسم موجود بالفعل!', 'error')
        return redirect(url_for('workers'))

    worker = Worker(name=name)
    db.session.add(worker)
    db.session.commit()

    flash('تمت إضافة العامل بنجاح!', 'success')
    return redirect(url_for('workers'))

@app.route('/delete_worker/<int:worker_id>', methods=['POST'])
def delete_worker(worker_id):
    worker = Worker.query.get_or_404(worker_id)

    if worker.repairs:
        flash('لا يمكن حذف العامل لوجود سجلات مرتبطة به!', 'error')
        return redirect(url_for('workers'))

    try:
        db.session.delete(worker)
        db.session.commit()
        flash('تم حذف العامل بنجاح!', 'success')
    except Exception as e:
        flash(f'حدث خطأ: {str(e)}', 'error')

    return redirect(url_for('workers'))

# ============ API endpoints ============

@app.route('/api/records')
def api_records():
    records = RepairRecord.query.order_by(RepairRecord.created_at.desc()).all()
    return jsonify([r.to_dict() for r in records])

@app.route('/api/records/<int:record_id>')
def api_record(record_id):
    record = RepairRecord.query.get_or_404(record_id)
    return jsonify(record.to_dict())

@app.route('/api/stats')
def api_stats():
    records = RepairRecord.query.all()
    workers = Worker.query.all()

    stats = {
        'total_records': len(records),
        'total_revenue': sum(r.effective_amount_received for r in records),
        'total_cost': sum(r.cost for r in records),
        'total_profit': sum(r.profit for r in records),
        'workers': []
    }

    for worker in workers:
        worker_records = [r for r in records if r.worker_id == worker.id]
        stats['workers'].append({
            'name': worker.name,
            'count': len(worker_records),
            'revenue': sum(r.effective_amount_received for r in worker_records),
            'cost': sum(r.cost for r in worker_records),
            'profit': sum(r.profit for r in worker_records)
        })

    return jsonify(stats)

# ============ تقرير PDF الأسبوعي ============

@app.route('/report/weekly')
def download_weekly_report():
    start_date, end_date, last_thursday = get_weekly_range()
    
    records = RepairRecord.query.filter(
        RepairRecord.created_at >= start_date,
        RepairRecord.created_at < end_date
    ).order_by(RepairRecord.created_at.desc()).all()
    
    total_records = len(records)
    total_cost = sum(r.cost for r in records)
    total_revenue = sum(r.effective_amount_received for r in records)
    total_profit = total_revenue - total_cost
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20, leftMargin=20, topMargin=30, bottomMargin=20)
    elements = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=1,
        spaceAfter=12
    )
    title = Paragraph(f"<b>تقرير إيرادات الأسبوع</b><br/>(من {start_date.strftime('%Y-%m-%d')} إلى {last_thursday.strftime('%Y-%m-%d')})", title_style)
    elements.append(title)
    elements.append(Spacer(1, 12))
    
    summary_style = ParagraphStyle('SummaryStyle', parent=styles['Normal'], fontSize=12, spaceAfter=6)
    summary_data = [
        f"<b>عدد الإصلاحات:</b> {total_records}",
        f"<b>إجمالي التكلفة:</b> {total_cost:,.0f} ل.س",
        f"<b>إجمالي الإيرادات الفعلية:</b> {total_revenue:,.0f} ل.س",
        f"<b>صافي الربح:</b> {total_profit:,.0f} ل.س"
    ]
    for line in summary_data:
        elements.append(Paragraph(line, summary_style))
    elements.append(Spacer(1, 12))
    
    if records:
        table_data = [
            ['#', 'العامل', 'الجهاز', 'التكلفة', 'المقبوض', 'الربح']
        ]
        for r in records:
            profit_val = r.profit
            profit_str = f"{profit_val:,.0f}"
            table_data.append([
                str(r.id),
                r.worker.name,
                r.device_name[:20] + ('...' if len(r.device_name) > 20 else ''),
                f"{r.cost:,.0f}",
                f"{r.effective_amount_received:,.0f}",
                profit_str
            ])
        
        table = Table(table_data, colWidths=[0.8*cm, 3.5*cm, 4*cm, 2.5*cm, 2.5*cm, 2.5*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ALIGN', (3, 1), (5, -1), 'RIGHT'),
        ]))
        # تلوين الخلايا السالبة في عمود الربح
        for i in range(1, len(table_data)):
            profit_val = float(table_data[i][5].replace(',', ''))
            if profit_val < 0:
                table.setStyle(TableStyle([
                    ('TEXTCOLOR', (5, i), (5, i), colors.red),
                ]))
            else:
                table.setStyle(TableStyle([
                    ('TEXTCOLOR', (5, i), (5, i), colors.green),
                ]))
        
        elements.append(table)
    else:
        elements.append(Paragraph("لا توجد سجلات في هذا الأسبوع.", styles['Normal']))
    
    doc.build(elements)
    buffer.seek(0)
    
    filename = f"تقرير_الأسبوع_{start_date.strftime('%Y-%m-%d')}_إلى_{last_thursday.strftime('%Y-%m-%d')}.pdf"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
