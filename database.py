from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Worker(db.Model):
    __tablename__ = 'workers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    repairs = db.relationship('RepairRecord', backref='worker', lazy=True)
    
    def __repr__(self):
        return f'<Worker {self.name}>'

class RepairRecord(db.Model):
    __tablename__ = 'repair_records'
    
    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('workers.id'), nullable=False)
    device_name = db.Column(db.String(200), nullable=False)
    device_model = db.Column(db.String(200), nullable=True)
    cost = db.Column(db.Float, nullable=False, default=0.0)
    amount_received = db.Column(db.Float, nullable=False, default=0.0)
    issues = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), default='تم التسليم')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def profit(self):
        """الربح لا يحسب إلا إذا كانت الحالة 'تم التسليم'"""
        if self.status == 'تم التسليم':
            return self.amount_received - self.cost
        return 0
    
    @property
    def effective_amount_received(self):
        """المبلغ المقبوض يُعتد به فقط إذا كانت الحالة 'تم التسليم'"""
        if self.status == 'تم التسليم':
            return self.amount_received
        return 0
    
    @property
    def profit_margin(self):
        if self.amount_received > 0 and self.status == 'تم التسليم':
            return (self.profit / self.amount_received) * 100
        return 0
    
    def to_dict(self):
        return {
            'id': self.id,
            'worker_name': self.worker.name if self.worker else 'غير معروف',
            'device_name': self.device_name,
            'device_model': self.device_model or '',
            'cost': self.cost,
            'amount_received': self.amount_received,
            'effective_amount_received': self.effective_amount_received,
            'profit': self.profit,
            'profit_margin': round(self.profit_margin, 1),
            'issues': self.issues or '',
            'notes': self.notes or '',
            'status': self.status,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M') if self.updated_at else ''
        }
    
    def __repr__(self):
        return f'<RepairRecord {self.device_name} - {self.worker.name}>'
