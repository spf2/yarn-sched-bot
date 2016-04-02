import inflect
import logging
import os
import requests

from collections import defaultdict
from datetime import datetime, timedelta
from flask import Flask, request, abort
from google.protobuf import json_format

from model import db, Meeting, Availability, current_meeting, \
    insert_or_update_availability
from proto.bot_api_pb2 import BotInvocation, BotInvocationReply, BotCall
from proto.common_pb2 import Event, Form, FormItem, FormSelect, FormOption,\
    Thread, Message, MediaItem


YARN_API_URL = 'http://localhost:5000/api/v1/call'
YARN_AUTH_TOKEN = os.environ['YARN_AUTH_TOKEN']
YARN_AUTH_SECRET = os.environ['YARN_AUTH_SECRET']

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
db.init_app(app)
plural = inflect.engine()


@app.route("/", methods=['POST'])
def handle_invocation():
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
    if me.ident in (p.user.ident for p in mention.thread.participants):
        return BotInvocationReply(
            form=poll_users(mention.thread),
            all_participants=True)

    return reply_all(u"hi! i can help find times to meet. type /add @sched")


def handle_submitted(submission):
    meeting = current_meeting(submission.form.thread_id)
    if not meeting:
        return reply(u"hm, it looks like you're too late?")

    dates = ','.join(o.value for o in submission.form.items[0].select.options
                             if o.selected)
    insert_or_update_availability(meeting, submission.user, dates)
    db.session.commit()

    if meeting.availabilities.count() < meeting.num_participants:
        return reply(u"thanks. {} of {} have responded".format(
            meeting.availabilities.count(), meeting.num_participants))

    dates = defaultdict(list)
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    for availability in meeting.availabilities.all():
        for datestr in availability.dates.split(','):
            date = datetime.strptime(datestr, "%Y-%m-%d")
            if (date - today).days >= 0:
                dates[date].append(availability)
    best = min(dates.iteritems(), key=lambda i: (-len(i[1]), i[0]))

    text = ""
    delta = (best[0] - today).days
    day = best[0].strftime('%A (%-m/%-d)')
    if delta == 0:
        day = "today"
    elif delta == 1:
        day = "tomorrow"

    if len(best[1]) >= meeting.num_participants:
        # the participants may have changed, so this is kinda a guess...
        names = ['everyone']
    else:
        names = [a.user_name for a in best[1]]
    text = u"{} is best. {} {} free".format(
        day, plural.join(names), plural.plural_verb('is', len(names)))

    meeting.done = True
    db.session.commit()

    return reply_all(text)


def handle_added(thread):
    return reply_all(u"hi! if you mention @sched i'll poll everyone for free days")


def num_users(thread):
    return sum(1 for p in thread.participants
                 if p.user.ident.startswith('user:'))


def poll_users(thread):
    db.session.add(Meeting(
        thread_id=thread.thread_id,
        topic=thread.topic,
        num_participants=num_users(thread)))
    db.session.commit()

    return Form(
        action="meeting",
        thread_id=thread.thread_id,
        label=u"find a time for {}".format(thread.topic),
        items=[FormItem(select=FormSelect(
            type=FormSelect.DATE,
            label=u"what days work for you?",
            multiple=True,
            options=date_options()))])


def date_options():
    now = datetime.now()
    for i in xrange(7):
        d = timedelta(days=i) + now
        value = d.strftime('%Y-%m-%d')
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
