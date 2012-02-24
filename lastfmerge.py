# -*- coding: utf-8 -*-

import config, common, bottle
from google.appengine.api.labs import taskqueue
from google.appengine.ext import db
from google.appengine.api import urlfetch
from urllib import urlencode, quote
import simplejson
import logging

app = bottle.Bottle()

class Users(db.Model):
    token = db.StringProperty()
    username = db.StringProperty()
    session = db.StringProperty()
    done = db.IntegerProperty()

@app.route('/')
def index():
    bottle.redirect('https://github.com/hugoatease/lastfmerge')

@app.route('/auth')
def lastauth():
    token = bottle.request.query.token
    if token == None or len(token) < 1:
        bottle.redirect('http://www.last.fm/api/auth/?cb=http://lastfmerge.appspot.com/callback&api_key=' + config.lastfm['Key'])

    data = common.jsonfetch(common.appendsig('http://ws.audioscrobbler.com/2.0/?method=auth.getSession&format=json&api_key=' + config.lastfm['Key'] + '&token=' + token))

    try:
        username = data['session']['name']
        session = data['session']['key']
    except KeyError:
        return '''<h3>Last.fmerge - Last.Fm Api Authentication</h3><p><span style="color: red;">ERROR</span> Authentication has failed, please retry.</p>'''

    servicetoken = common.Token(length=15).make()
    
    q = Users.all(keys_only = True)
    q.filter('username =', username)
    old = q.fetch(50)
    for key in old:
        item = Users.get(key)
        item.delete()

    user = Users(token = servicetoken, username = username, session = session)
    user.put()
    
    return '''<h3>Last.fmerge - Last.Fm Api Authentication</h3><p>Authentication with the Last.fm API has succeed. Now you can return to the desktop application and give it this code :</p><p><b>''' + servicetoken + '''</b></p>'''
    
@app.route('/check/:servicetoken')
def check(servicetoken):
    q = Users().all()
    q.filter('token =', servicetoken)
    try:
        result = q.fetch(1)[0]
        return {'Username' : result.username}
    except:
        return {'Message' : 'ERROR : Wrong token. Please retry the authentication process at http://lastfmerge.appspot.com/auth', 'Error' : True}

@app.route('/scrobble/:servicetoken', method='POST')
def scrobble(servicetoken):
    scrobbles = simplejson.loads(bottle.request.forms.scrobbles)
    try:
        mode = bottle.request.forms.mode
    except:
        mode = None
    if mode == None or mode == 'scrobble':
        remove = False
    elif mode == 'remove':
        remove = True
    
    q = Users.all()
    q.filter('token =', servicetoken)
    try:
        user = q.fetch(1)[0]
    except KeyError:
        return {'Message' : 'ERROR : Wrong token. Please retry the authentication process at http://lastfmerge.appspot.com/auth', 'Error' : True}

    i = 0
    for scrobble in scrobbles:
        i = i +1
        if scrobble.has_key('Time') == False or scrobble.has_key('Name') == False or scrobble.has_key('Artist') == False:
            return {'Message' : 'ERROR : Inputed scrobble data is unrecognised. It seems that scrobble #'+str(i) + 'is invalid.'}
    
    converted = list()
    for scrobble in scrobbles:
        converted.append( common.unicodeparser(scrobble) )
    scrobble = converted

    if remove == False:
        user.done = 0
        user.put()
        i = 0
        while len(scrobbles) != 0:
            part = scrobbles[0:10]
            taskqueue.add(queue_name='scrobble', url='/task/scrobble/' + user.session, method='POST', params = {'scrobbles' : simplejson.dumps(part)})
            for scrobble in part:
                scrobbles.remove(scrobble)
            i = i +1
        return {'Message' : 'Inputed scrobbles have been planned for submission.', 'Error' : False}
    elif remove == True:
        for scrobble in scrobbles:
            taskqueue.add(queue_name='remove', url=quote('/task/remove/' + user.session + '/' + scrobble['Artist'] + '/' + scrobble['Name'] + '/' + scrobble['Time']), method='GET')
        return {'Message' : 'Inputed scrobbles have been planned for deletion.', 'Error' : False}

@app.route('/task/scrobble/:session', method='POST')
def doscrobble(session):
    scrobbles = simplejson.loads(bottle.request.forms.scrobbles)

    payload = {'method' : 'track.scrobble', 'api_key' : config.lastfm['Key'], 'sk' : session}
    
    i = 0
    for scrobble in scrobbles:
        payload[ 'artist[' + str(i) + ']' ] = scrobble['Artist']
        payload[ 'track[' + str(i) + ']' ] = scrobble['Name']
        payload[ 'timestamp[' + str(i) + ']' ] = scrobble['Time']
        i = i +1
    
    payload['api_sig'] = common.makesig(url=None, params=payload)
    payload = urlencode(payload)
    logging.debug( str( urlfetch.fetch('http://ws.audioscrobbler.com/2.0/?format=json', payload = payload, method= urlfetch.POST).content ) )

@app.route('/task/remove/:sk/:artist/:name/:timestamp')
def doremove(sk, artist, name, timestamp):
    payload = {'method' : 'library.removeScrobble', 'api_key' : config.lastfm['Key'], 'sk' : sk}
    
    payload['artist'] = artist
    payload['track'] = name
    payload['timestamp'] = timestamp
    payload['api_sig'] = common.makesig(url=None, params=payload)
    payload = urlencode(payload)
    logging.debug( str( urlfetch.fetch('http://ws.audioscrobbler.com/2.0/?format=json', payload = payload, method= urlfetch.POST).content ) )

bottle.run(app, server = 'gae')