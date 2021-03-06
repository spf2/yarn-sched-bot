# Yarn scheduling bot

This bot helps find a time for groups to meet. It is a little bit like doodle, but different.

# How to participate in a poll 

So, you've been invited to a Yarn thread. (Yay! \o/). Once you've joined, you can expect the organizer to send out a poll
to help find the best day for all the participants.

You should get a message like: 

```@sched: What days work for you? <link>```

Just click on the link, pick from the available days (gray dates are unavailable), and hit 'Submit'.
When everyone has responded, the @sched bot will announce which day is best.

![Calendar](https://cdn-images-1.medium.com/max/1200/1*uyWed-ObRNiyGjehMkz7Zg.png)

# How to create a poll

Create a new thread if needed. This can be done from the main number. 
If you don't have that, type ```/about``` to get it. 
It'll also send you a vcard so you can add it to your address book for next time.

Add the bot to your thread

```/add @sched```

(You can remove later with ```/thx @sched```)

Add or invite your people.
(Add puts them in the thread directly without asking them. Invite asks them first, and they can opt-in.)

```/add alice```

```/invite 800-555-1212```

(If you're inviting a new Yarn user, it will give you a form to fill out with their full name.)

Once people have all joined, you can ask sched to find a weekday with

```@sched weekday```

The sched bot will send a link to everyone asking them to pick available days.

You can check on the status of your poll just by mentioning @sched, and it will reply like:

> 3/6 have responded. Tomorrow is best so far. Alice, Bob and Chuck are free. Type @sched done or nevermind to announce result or stop poll [respectively]

# What's next

This is just a demo at this point. It needs a lot more features like:

- TODO: Poll new participants as they are added or join
- TODO: Offer other canned options (like "@sched weekend"), as well as specify date options (like doodle)
- TODO: Time
- TODO: Recurring polls

Pull requests welcome, of course!
