from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from database import db, Worker, RepairRecord
from datetime import datetime
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///workshop.db')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///workshop.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# إنشاء قاعدة البيانات بدون أي عمال افتراضيين
with app.app_context():
    db.create_all()

# ============ الصفحات الرئيسية ============

@app.route('/')
def index():
    records = RepairRecord.query.order_by(RepairRecord.created_at.desc()).all()
    workers = Worker.query.all()

    total_records = len(records)
    total_revenue = sum(r.amount_received for r in records)
    total_cost = sum(r.cost for r in records)
    total_profit = total_revenue - total_cost

    worker_stats = {}
    for worker in workers:
        worker_records = [r for r in records if r.worker_id == worker.id]
        worker_stats[worker.name] = {
            'count': len(worker_records),
            'revenue': sum(r.amount_received for r in worker_records),
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
            status = request.form.get('status', 'مكتمل')

            if not device_name:
                flash('اسم الجهاز مطلوب!', 'error')
                return redirect(url_for('add_record'))

            if not worker_id:
                flash('اسم العامل مطلوب!', 'error')
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
            record.worker_id = int(request.form.get('worker_id'))
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
            'total_revenue': sum(r.amount_received for r in records),
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
        'total_revenue': sum(r.amount_received for r in records),
        'total_cost': sum(r.cost for r in records),
        'total_profit': sum(r.profit for r in records),
        'workers': []
    }

    for worker in workers:
        worker_records = [r for r in records if r.worker_id == worker.id]
        stats['workers'].append({
            'name': worker.name,
            'count': len(worker_records),
            'revenue': sum(r.amount_received for r in worker_records),
            'cost': sum(r.cost for r in worker_records),
            'profit': sum(r.profit for r in worker_records)
        })

    return jsonify(stats)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)