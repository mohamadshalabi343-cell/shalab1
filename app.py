import os
from datetime import datetime, timedelta
from collections import defaultdict
from flask import (Flask, render_template, request, redirect, url_for,
                   flash, jsonify, make_response)
from sqlalchemy import text
from database import *

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
    # ترحيل بسيط: إضافة عمود is_archived إذا لم يكن موجوداً
    try:
        with db.engine.connect() as conn:
            conn.execute(text(
                "ALTER TABLE repair_records ADD COLUMN is_archived BOOLEAN DEFAULT FALSE"
            ))
            conn.commit()
            print("✅ تمت إضافة عمود is_archived")
    except Exception:
        pass  # العمود موجود مسبقاً

    # ضبط أي قيم NULL
    try:
        with db.engine.connect() as conn:
            conn.execute(text(
                "UPDATE repair_records SET is_archived = FALSE WHERE is_archived IS NULL"
            ))
            conn.commit()
    except Exception:
        pass


# ============ دوال مساعدة ============

def get_day_range(date_str):
    day = datetime.strptime(date_str, '%Y-%m-%d')
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start, end


def get_week_range(date_str=None):
    if date_str:
        ref = datetime.strptime(date_str, '%Y-%m-%d')
    else:
        ref = datetime.utcnow()
    days_since_sat = (ref.weekday() - 5) % 7
    start = (ref - timedelta(days=days_since_sat)).replace(
        hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=7)
    return start, end


def calc_totals(records):
    revenue = sum(r.effective_amount_received for r in records)
    cost = sum(r.cost for r in records)
    return {
        'count': len(records),
        'revenue': revenue,
        'cost': cost,
        'profit': revenue - cost,
    }


def group_by_day(records):
    groups = defaultdict(list)
    for r in records:
        key = r.created_at.strftime('%Y-%m-%d') if r.created_at else 'غير معروف'
        groups[key].append(r)
    return groups


# ============ الصفحة الرئيسية ============

@app.route('/')
def index():
    # السجلات النشطة (الفترة الحالية) - للساعات والإحصائيات العلوية
    current_records = (RepairRecord.query
                       .filter_by(is_archived=False)
                       .order_by(RepairRecord.created_at.desc())
                       .all())

    # جميع السجلات - لسجل الأجهزة الكامل في الأسفل
    all_records = (RepairRecord.query
                   .order_by(RepairRecord.created_at.desc())
                   .all())

    workers = Worker.query.all()

    # ملخص يومي للفترة الحالية فقط
    daily_summary = []
    for date_key in sorted(group_by_day(current_records).keys(), reverse=True):
        day_records = group_by_day(current_records)[date_key]
        totals = calc_totals(day_records)
        daily_summary.append({
            'date': date_key,
            'count': totals['count'],
            'revenue': totals['revenue'],
            'cost': totals['cost'],
            'profit': totals['profit'],
            'delivered': sum(1 for r in day_records if r.status == 'تم التسليم'),
            'not_delivered': sum(1 for r in day_records if r.status == 'لم تسلم'),
            'debt': sum(1 for r in day_records if r.status == 'دين'),
        })

    # سجل الأجهزة الكامل (جميع الفترات)
    all_groups = group_by_day(all_records)
    full_log = []
    for date_key in sorted(all_groups.keys(), reverse=True):
        day_records = all_groups[date_key]
        totals = calc_totals(day_records)
        full_log.append({
            'date': date_key,
            'count': totals['count'],
            'revenue': totals['revenue'],
            'cost': totals['cost'],
            'profit': totals['profit'],
            'has_archived': any(r.is_archived for r in day_records),
            'has_active': any(not r.is_archived for r in day_records),
        })

    # إحصائيات الفترة الحالية فقط
    total_records = len(current_records)
    total_revenue = sum(r.effective_amount_received for r in current_records)
    total_cost = sum(r.cost for r in current_records)
    total_profit = total_revenue - total_cost

    worker_stats = {}
    for worker in workers:
        worker_records = [r for r in current_records if r.worker_id == worker.id]
        worker_stats[worker.name] = {
            'count': len(worker_records),
            'revenue': sum(r.effective_amount_received for r in worker_records),
            'cost': sum(r.cost for r in worker_records),
            'profit': sum(r.profit for r in worker_records)
        }

    archived_count = sum(1 for r in all_records if r.is_archived)

    return render_template('index.html',
                          daily_summary=daily_summary,
                          full_log=full_log,
                          workers=workers,
                          total_records=total_records,
                          total_revenue=total_revenue,
                          total_cost=total_cost,
                          total_profit=total_profit,
                          worker_stats=worker_stats,
                          archived_count=archived_count)


# ============ إعادة تعيين الفترة ============

@app.route('/reset', methods=['POST'])
def reset_period():
    """أرشفة كل السجلات النشطة (تصفير الإحصائيات) مع الاحتفاظ بها في السجل الكامل"""
    try:
        count = RepairRecord.query.filter_by(is_archived=False).update(
            {RepairRecord.is_archived: True}
        )
        db.session.commit()
        if count:
            flash(f'تم إعادة تعيين الفترة الحالية. تم أرشفة {count} سجل مع الاحتفاظ بها في سجل الأجهزة بالأسفل.', 'success')
        else:
            flash('لا توجد سجلات نشطة لإعادة تعيينها.', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'حدث خطأ أثناء إعادة التعيين: {str(e)}', 'error')
    return redirect(url_for('index'))


@app.route('/day/<date>')
def day_records(date):
    """عرض سجلات يوم معين (جميع الحالات: نشطة + مؤرشفة)"""
    try:
        start, end = get_day_range(date)
    except ValueError:
        flash('تاريخ غير صالح', 'error')
        return redirect(url_for('index'))

    records = RepairRecord.query.filter(
        RepairRecord.created_at >= start,
        RepairRecord.created_at < end
    ).order_by(RepairRecord.created_at.desc()).all()

    totals = calc_totals(records)
    return render_template('day_records.html',
                          records=records,
                          date=date,
                          total_records=totals['count'],
                          total_revenue=totals['revenue'],
                          total_cost=totals['cost'],
                          total_profit=totals['profit'])


@app.route('/search')
def search():
    q = request.args.get('q', '').strip()
    date_from = request.args.get('from', '').strip()
    date_to = request.args.get('to', '').strip()

    query = RepairRecord.query.join(Worker)

    if q:
        like = f'%{q}%'
        query = query.filter(
            db.or_(
                RepairRecord.device_name.ilike(like),
                RepairRecord.device_model.ilike(like),
                RepairRecord.issues.ilike(like),
                RepairRecord.notes.ilike(like),
                Worker.name.ilike(like),
                RepairRecord.status.ilike(like),
            )
        )

    if date_from:
        try:
            d = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(RepairRecord.created_at >= d)
        except ValueError:
            pass

    if date_to:
        try:
            d = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(RepairRecord.created_at < d)
        except ValueError:
            pass

    records = query.order_by(RepairRecord.created_at.desc()).all() if (q or date_from or date_to) else []
    totals = calc_totals(records)

    return render_template('search_results.html',
                          records=records,
                          query=q,
                          date_from=date_from,
                          date_to=date_to,
                          total_records=totals['count'],
                          total_revenue=totals['revenue'],
                          total_cost=totals['cost'],
                          total_profit=totals['profit'])


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

            record = RepairRecord(
                worker_id=worker_id,
                device_name=device_name,
                device_model=device_model,
                cost=cost,
                amount_received=amount_received,
                issues=issues,
                notes=notes,
                status=status,
                is_archived=False
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


# ============ التقارير ============

@app.route('/reports')
def reports():
    today = datetime.utcnow().strftime('%Y-%m-%d')
    week_start, _ = get_week_range()
    return render_template('reports.html',
                          today=today,
                          week_start=week_start.strftime('%Y-%m-%d'))


def render_pdf(template_name, **context):
    from weasyprint import HTML
    html_string = render_template(template_name, **context)
    pdf_bytes = HTML(string=html_string).write_pdf()
    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    return response


@app.route('/reports/daily/<date>.pdf')
def daily_pdf(date):
    try:
        start, end = get_day_range(date)
    except ValueError:
        flash('تاريخ غير صالح', 'error')
        return redirect(url_for('reports'))

    records = RepairRecord.query.filter(
        RepairRecord.created_at >= start,
        RepairRecord.created_at < end
    ).order_by(RepairRecord.created_at.desc()).all()

    totals = calc_totals(records)

    response = render_pdf('pdf_daily.html',
                         records=records,
                         date=date,
                         total_records=totals['count'],
                         total_revenue=totals['revenue'],
                         total_cost=totals['cost'],
                         total_profit=totals['profit'])
    response.headers['Content-Disposition'] = f'inline; filename=daily_report_{date}.pdf'
    return response


@app.route('/reports/weekly.pdf')
def weekly_pdf():
    week_start_str = request.args.get('start')
    start, end = get_week_range(week_start_str)

    records = RepairRecord.query.filter(
        RepairRecord.created_at >= start,
        RepairRecord.created_at < end
    ).order_by(RepairRecord.created_at.desc()).all()

    daily_groups = group_by_day(records)
    days_data = []
    for key in sorted(daily_groups.keys()):
        day_recs = daily_groups[key]
        t = calc_totals(day_recs)
        days_data.append({
            'date': key,
            'records': day_recs,
            'count': t['count'],
            'revenue': t['revenue'],
            'cost': t['cost'],
            'profit': t['profit'],
        })

    totals = calc_totals(records)

    response = render_pdf('pdf_weekly.html',
                         days_data=days_data,
                         start_date=start.strftime('%Y-%m-%d'),
                         end_date=(end - timedelta(days=1)).strftime('%Y-%m-%d'),
                         total_records=totals['count'],
                         total_revenue=totals['revenue'],
                         total_cost=totals['cost'],
                         total_profit=totals['profit'])

    response.headers['Content-Disposition'] = (
        f'inline; filename=weekly_report_{start.strftime("%Y-%m-%d")}.pdf'
    )
    return response


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


# ============ تشغيل التطبيق ============
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
