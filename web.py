# This is a bot for finding the best day for a group of people. It works
# a lot like doodle.com.
# It expects to be added to the thread so it greet and poll new users, and
# also so it can recur automatically if desired.

import inflect
import logging
import os
import requests
import string

from collections import defaultdict
from datetime import datetime, timedelta
from flask import Flask, request, abort
from google.protobuf import json_format

from model import db, Meeting, Availability, current_meeting, \
    insert_or_update_availability
from proto.bot_api_pb2 import BotInvocation, BotInvocationReply, BotCall
from proto.common_pb2 import Event, Form, FormItem, FormSelect, FormOption,\
    Thread, Message, MediaItem


if os.environ.get('YARN_ENVIRONMENT') == 'prod':
    YARN_API_URL = 'https://yarn-service.herokuapp.com/api/v1/call'
else:
    YARN_API_URL = 'http://localhost:5000/api/v1/call'

YARN_AUTH_TOKEN = os.environ['YARN_AUTH_TOKEN']
YARN_AUTH_SECRET = os.environ['YARN_AUTH_SECRET']

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
plural = inflect.engine()


@app.route("/", methods=['GET', 'POST'])
def handle_invocation():
    if request.method == 'GET':
        return "@sched"
    reply = None
    invocation = json_format.Parse(request.data, BotInvocation())
    if invocation.HasField('mention'):
        reply = handle_mentioned(invocation.bot, invocation.mention)
    elif invocation.HasField('submission'):
        reply = handle_submitted(invocation.submission)
    elif (invocation.delivery.event.type == Event.ADDED and
          invocation.bot.ident in (u.ident for u in invocation.delivery.event.users)):
        reply = handle_added(invocation.delivery.thread)

    return json_format.MessageToJson(reply) if reply else ""


def handle_mentioned(me, mention):
    if me.ident not in (p.user.ident for p in mention.thread.participants):
        return reply_all(u"Hi! I can help find times to meet. Type /add @sched")

    command = mention.message.text\
        .replace(r'@sched', '')\
        .strip(string.punctuation + string.whitespace)\
        .lower()
    meeting = current_meeting(mention.thread.thread_id)
    if command:
        if meeting and not meeting.done:
            known = ['done', 'nevermind', 'nm', 'quit', 'cancel']
            if command in known:
                meeting.done = True
                db.session.commit()
            if command == 'done':
                return reply_all(get_status(meeting))
            elif command in known:
                return reply_all(
                    u"Canceled by {}. Type @sched to start again".format(
                        mention.message.sender.name))
            else:
                return reply_in_progress(meeting)
        else:
            if command != 'weekday':
                return reply(u"I only know about weekday meetings so far...")

            return BotInvocationReply(
                form=poll_users(mention.thread, mention.message.sender),
                all_participants=True)
    else:
        if meeting and not meeting.done:
            return reply_in_progress(meeting)
        else:
            return reply(u"Type @sched weekday to find a day to meet")


def handle_submitted(submission):
    meeting = current_meeting(submission.form.thread_id)
    if not meeting:
        return reply(u"I can't find that meeting. My bad.")

    dates = ','.join(o.value for o in submission.form.items[0].select.options
                             if o.selected)
    insert_or_update_availability(meeting, submission.user, dates)

    if meeting.availabilities.count() < meeting.num_participants:
        return reply(u"Thanks. {}/{} have responded so far".format(
            meeting.availabilities.count(), meeting.num_participants))

    meeting.done = True
    db.session.commit()

    return reply_all(get_status(meeting))


def reply_in_progress(meeting):
    status = get_status(meeting)
    return reply(
        u"{}/{} have responded. {}. "
        u"Type @sched done or nevermind "
        u"to announce result or stop poll".format(
            meeting.availabilities.count(),
            meeting.num_participants,
            status))


def get_status(meeting):
    if meeting.availabilities.count() == 0:
        return u"No one has responded yet"
    dates = defaultdict(list)
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    for availability in meeting.availabilities.all():
        for datestr in availability.dates.split(','):
            date = datetime.strptime(datestr, "%Y-%m-%d")
            if (date - today).days >= 0:
                dates[date].append(availability)
    best = min(dates.iteritems(), key=lambda i: (-len(i[1]), i[0]))

    delta = (best[0] - today).days
    day = best[0].strftime('%A (%-m/%-d)')
    if delta == 0:
        day = "Today"
    elif delta == 1:
        day = "Tomorrow"
    names = [a.user_name for a in best[1]]
    return u"{} is best{}. {} {} free".format(
        day,
        " so far" if not meeting.done else "",
        plural.join(names),
        plural.plural_verb('is', len(names)))


def handle_added(thread):
    return reply(
        u"Hi! Thanks for adding me! "
        u"To poll everyone for free days, type @sched weekday")


def num_users(thread):
    return sum(1 for p in thread.participants
                 if p.user.ident.startswith('user:'))


def poll_users(thread, sender):
    db.session.add(Meeting(
        thread_id=thread.thread_id,
        topic=thread.topic,
        num_participants=num_users(thread)))
    db.session.commit()

    return Form(
        action="meeting",
        thread_id=thread.thread_id,
        label=u"Finding a day for \"{}\"".format(sender.name, thread.topic),
        items=[FormItem(select=FormSelect(
            type=FormSelect.DATE,
            label=u"What days work for you?",
            multiple=True,
            options=date_options()))])


def date_options(num=7):
    now = datetime.now()
    for i in xrange(num):
        d = timedelta(days=i) + now
        value = d.strftime('%Y-%m-%d')
        if d.isoweekday() in range(1, 6):
            yield FormOption(value=value)


def reply(text):
    return BotInvocationReply(message=Message(text=text))

def reply_all(text):
    return BotInvocationReply(message=Message(text=text), all_participants=True)


if __name__ == "__main__":
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', '*')
    app.run(
        debug=True,
        threaded=True,
        host='0.0.0.0',
        port=int(os.environ.get('PORT')) if 'PORT' in os.environ else None)
