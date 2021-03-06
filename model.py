import logging

from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint

db = SQLAlchemy()


def current_meeting(thread_id):
    meeting = Meeting.query\
        .filter_by(thread_id=thread_id)\
        .order_by(Meeting.created.desc())\
        .first()
    return meeting


def insert_or_update_availability(meeting, user, dates):
    avail = Availability.query\
        .filter_by(meeting=meeting, user_ident=user.ident)\
        .first()
    if avail:
        avail.dates = dates
    else:
        db.session.add(Availability(
            meeting=meeting,
            user_ident=user.ident,
            user_name=user.name,
            dates=dates))
    db.session.commit()


class Availability(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_ident = db.Column(db.String(30))
    user_name = db.Column(db.Text)
    meeting_id = db.Column(db.Integer, db.ForeignKey('meeting.id'))
    meeting = db.relationship('Meeting', backref=db.backref('availabilities', lazy='dynamic'))
    dates = db.Column(db.Text)  # comma-separated YYYY-MM-DD
    __table_args__ = (UniqueConstraint('meeting_id', 'user_ident'),)


class Meeting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(db.String(30), index=True)
    created = db.Column(db.DateTime, index=True, server_default=db.func.now())
    topic = db.Column(db.Text)
    done = db.Column(db.Boolean)
    num_participants = db.Column(db.Integer)
