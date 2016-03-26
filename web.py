import inflect
import logging
import os
import requests

from collections import defaultdict
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, abort
from google.protobuf import json_format

from model import db, Meeting, Availability, current_meeting
from proto.bot_api_pb2 import BotInvocation, BotCall
from proto.common_pb2 import Event, Form, FormItem, FormSelect, FormOption,\
    Thread, Message


YARN_API_URL = 'http://localhost:5000/api/v1/call'
YARN_AUTH_TOKEN = os.environ['YARN_AUTH_TOKEN']
YARN_AUTH_SECRET = os.environ['YARN_AUTH_SECRET']

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
db.init_app(app)
plural = inflect.engine()


@app.route("/", methods=['POST'])
def handle_invocation():
    invocation = json_format.Parse(request.data, BotInvocation())
    reply_text = ""
    if invocation.HasField('mention'):
        reply_text = handle_mentioned(invocation.bot, invocation.mention)
    elif invocation.HasField('submission'):
        reply_text = handle_submitted(invocation.submission)
    elif (invocation.delivery.event.type == Event.ADDED and
          invocation.bot.ident in (u.ident for u in invocation.delivery.event.users)):
        reply_text = message_reply(handle_added(invocation.delivery.thread))
    return message_reply(reply_text)


def handle_mentioned(me, mention):
    if me.ident in (p.user.ident for p in mention.thread.participants):
        if num_users(mention.thread) < 2:
            return u"i need at least 2 people to be useful... /add some?"

        poll_users(mention.thread)
        return u"yo. i'll message you individually and report back..."

    return u"hi! i can help find times to meet. type /add @sched"


def handle_submitted(submission):
    meeting = current_meeting(submission.form.thread_id)
    if not meeting:
        return u"hm, it looks like you're too late?"

    dates = ','.join(o.value for o in submission.form.items[0].select.options
                             if o.selected)
    avail = db.session.merge(Availability(
        meeting=meeting,
        user_ident=submission.user.ident,
        user_name=submission.user.name,
        dates=dates))
    db.session.commit()

    if meeting.availabilities.count() < meeting.num_participants:
        return u"thanks. {} of {} have responded".format(
            meeting.availabilities.count(), meeting.num_participants)

    dates = defaultdict(list)
    now = datetime.now()
    for availability in meeting.availabilities.all():
        for datestr in availability.dates.split(','):
            date = datetime.strptime(datestr, "%Y-%m-%d")
            if (date - now).days >= 0:
                dates[date].append(availability)
    best = max(dates.iteritems(), key=lambda i: (len(i[1]), i[0]))

    text = ""
    if len(best[1]) < 2:
        text = u"i couldn't find any day that works. bummer :("
    else:
        delta = best[0] - datetime.now()
        day = best[0].strftime('%A (%-m/%-d)')
        if delta == 0:
            day = "today"
        elif delta == 1:
            day = "tomorrow"
        names = plural.join([a.user_name for a in best[1]])
        text = u"the best day is {}. {} are free".format(day, names)

    bot_call = BotCall(
        thread=Thread(thread_id=meeting.thread_id),
        message=Message(text=text))

    send_bot_call(bot_call)

    meeting.done = True
    db.session.commit()


def handle_added(thread):
    if num_users(thread) < 2:
        u"after you add more people, type @sched for my help"
        return

    poll_users(thread)
    return (
        u"hi! i'll message the {} of you individually "
        u"and report back".format(len(thread.participants) - 1))


def num_users(thread):
    return sum(1 for p in thread.participants
                 if p.user.ident.startswith('user:'))


def poll_users(thread):
    bot_call = BotCall(
        thread=thread,
        form=Form(
            action="meeting",
            thread_id=thread.thread_id,
            label="i'm trying to find a time for {}".format(thread.topic),
            items=[FormItem(select=FormSelect(
                label="what days work for you? choose",
                multiple=True,
                options=date_options()))]))

    send_bot_call(bot_call)

    db.session.add(Meeting(
        thread_id=thread.thread_id,
        topic=thread.topic,
        num_participants=num_users(thread)))
    db.session.commit()


def send_bot_call(bot_call):
    resp = requests.post(
        YARN_API_URL,
        json_format.MessageToJson(bot_call),
        auth=(YARN_AUTH_TOKEN, YARN_AUTH_SECRET))

    if resp.status_code != 200:
        print resp
        abort(500)


def date_options():
    now = datetime.now()
    for i in xrange(7):
        d = timedelta(days=i) + now
        if i == 0:
            name = 'today'
        elif i == 1:
            name = 'tmrw'
        else:
            name = d.strftime('%a').lower()
        value = d.strftime('%Y-%m-%d')
        yield FormOption(name=name, value=value)


def message_reply(text):
    if not text:
        return ""
    return jsonify(message={'text': text})


if __name__ == "__main__":
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', '*')
    app.run(
        debug=True,
        threaded=True,
        host='0.0.0.0',
        port=int(os.environ.get('PORT')) if 'PORT' in os.environ else None)
