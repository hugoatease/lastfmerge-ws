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
    running = db.BooleanProperty()
    total = db.IntegerProperty()
    failed = db.IntegerProperty()

@app.route('/')
def index():
    bottle.redirect('https://github.com/hugoatease/lastfmerge')

@app.route('/auth')
def lastauth():
    bottle.redirect('http://www.last.fm/api/auth/?cb=http://lastfmerge.appspot.com/callback&api_key=' + config.lastfm['Key'])

@app.route('/callback')
def lastcallback():
    error = False
    token = bottle.request.query.token
    
    data = common.jsonfetch(common.appendsig('http://ws.audioscrobbler.com/2.0/?method=auth.getSession&format=json&api_key=' + config.lastfm['Key'] + '&token=' + token))

    try:
        username = data['session']['name']
        session = data['session']['key']
    except KeyError:
        error = True
    
    if error:
        return '''<h3>Last.fmerge - Last.Fm Api Authentication</h3><p><span style="color: red;">ERROR</span> Authentication has failed, please retry.</p>'''
    else:
        servicetoken = common.Token(length=10).make()
        
        q = Users().all(keys_only = True)
        q.filter('username =', username)
        old = q.fetch(50)
        for key in old:
            item = Users().get(key)
            item.delete()
    
        userentity = Users(token = servicetoken, username = username, session = session)
        userentity.put()
        
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
    try:
        scrobbles = simplejson.loads(bottle.request.forms.scrobbles)
        try:
            mode = bottle.request.forms.mode
        except:
            mode = None
        if mode == None or mode == 'scrobble':
            remove = False
        elif mode == 'remove':
            remove = True
        
        q = Users().all()
        q.filter('token =', servicetoken)
        result = q.fetch(1)[0]
        sk = result.session
        userkey = result.key()

        valid = True
        i = 0
        for scrobble in scrobbles:
            if scrobble.has_key('Time') == False or scrobble.has_key('Name') == False or scrobble.has_key('Artist') == False:
                valid = False
                return {'Message' : 'ERROR : Inputed scrobble data is unrecognised. It seems that scrobble #'+str(i) + 'is invalid.'}
        if valid:
            if remove == False:
                i = 0
                total = len(scrobbles)
                while len(scrobbles) != 0:
                    part = scrobbles[0:10]
                    taskqueue.add(queue_name='lastfm', url='/task/scrobble/' + str(userkey) + '/' + str( total-1 -i ), method='POST', params = {'scrobbles' : simplejson.dumps(part)})
                    for scrobble in part:
                        scrobbles.remove(scrobble)
                    i = i +1
                user = Users.get(userkey)
                user.running = True
                user.put()
                return {'Message' : 'Inputed scrobbles have been planned for submission.', 'Error' : False}
            elif remove == True:
                for scrobble in scrobbles:
                    taskqueue.add(queue_name='lastfm', url=quote('/task/remove/' + sk + '/' + scrobble['Artist'] + '/' + scrobble['Name'] + '/' + scrobble['Time']), method='GET')
                return {'Message' : 'Inputed scrobbles have been planned for deletion.', 'Error' : False}

    except:
        return {'Message' : 'ERROR : Wrong token. Please retry the authentication process at http://lastfmerge.appspot.com/auth', 'Error' : True}

@app.route('/task/scrobble/:userkey/:remaining', method='POST')
def doscrobble(userkey, remaining):
    remaining = int(remaining)
    
    user = Users.get( db.Key(userkey) )
    sk = user.session
    scrobbles = simplejson.loads(bottle.request.forms.scrobbles)
    payload = {'method' : 'track.scrobble', 'api_key' : config.lastfm['Key'], 'sk' : sk}
    i = 0
    
    parsed_scrobbles = list()
    for scrobble in scrobbles:
        converted = common.unicodefilter(scrobble)
        if converted != None:
            parsed_scrobbles.append(converted)

    for scrobble in parsed_scrobbles:
        payload[ 'artist[' + str(i) + ']' ] = scrobble['Artist']
        payload[ 'track[' + str(i) + ']' ] = scrobble['Name']
        payload[ 'timestamp[' + str(i) + ']' ] = scrobble['Time']
        i = i +1
    
    payload['api_sig'] = common.makesig(url=None, params=payload)
    payload = urlencode(payload)
    logging.debug( str( urlfetch.fetch('http://ws.audioscrobbler.com/2.0/?format=json', payload = payload, method= urlfetch.POST).content ) )
    
    if remaining == 0:
        user.running = False
        user.put()

@app.route('/task/remove/:sk/:artist/:name/:timestamp')
def doremove(sk, artist, name, timestamp):
    payload = {'method' : 'library.removeScrobble', 'api_key' : config.lastfm['Key'], 'sk' : sk}
    
    if common.unicodefilter( {'Artist' : artist, 'Name' : name, 'Time' : timestamp} ) != None:
        payload['artist'] = artist
        payload['track'] = name
        payload['timestamp'] = timestamp
        payload['api_sig'] = common.makesig(url=None, params=payload)
        payload = urlencode(payload)
        logging.debug( str( urlfetch.fetch('http://ws.audioscrobbler.com/2.0/?format=json', payload = payload, method= urlfetch.POST).content ) )
    else:
        logging.debug('Unicode error : ' + artist + ' - ' + name)

bottle.run(app, server = 'gae')
