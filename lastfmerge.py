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
        q = Users().all()
        q.filter('token =', servicetoken)
    
        result = q.fetch(1)[0]
        scrobbles = simplejson.loads(bottle.request.forms.scrobbles)
        valid = True
        i = 0
        for scrobble in scrobbles:
            if scrobble.has_key('Time') == False or scrobble.has_key('Name') == False or scrobble.has_key('Artist') == False:
                valid = False
                return {'Message' : 'ERROR : Inputed scrobble data is unrecognised. It seems that scrobble #'+str(i) + 'is invalid.'}
        if valid:
            i = 0
            while len(scrobbles) != 0:
                part = scrobbles[0:10]
                taskqueue.add(queue_name='lastfm', url='/task/scrobble/' + servicetoken, method='POST', params = {'scrobbles' : simplejson.dumps(part)})
                for scrobble in part:
                    scrobbles.remove(scrobble)
                i = i +1
            return {'Message' : 'Inputed scrobbles have been planned for submission.', 'Error' : False}

    except:
        return {'Message' : 'ERROR : Wrong token. Please retry the authentication process at http://lastfmerge.appspot.com/auth', 'Error' : True}

@app.route('/task/scrobble/:servicetoken', method='POST')
def do(servicetoken):
    try:
        q = Users().all()
        q.filter('token =', servicetoken)
        result = q.fetch(1)[0]
        sk = result.session
        scrobbles = simplejson.loads(bottle.request.forms.scrobbles)
        payload = {'method' : 'track.scrobble', 'format' : 'json', 'api_key' : config.lastfm['Key'], 'sk' : sk}
        i = 0
        
        parsed_scrobbles = list()
        for scrobble in scrobbles:
            converted = common.unicodefilter(scrobble)
            if converted != None:
                parsed_scrobbles.append(converted)
    
        for scrobble in parsed_scrobbles:
            payload[ 'artist[' + str(i) + ']' ] = quote(scrobble['Artist'])
            payload[ 'track[' + str(i) + ']' ] = quote(scrobble['Name'])
            payload[ 'timestamp[' + str(i) + ']' ] = scrobble['Time']
            i = i +1
        
        payload['api_sig'] = common.makesig(url=None, params=payload)
        payload = urlencode(payload)
        logging.debug( str( urlfetch.fetch('http://ws.audioscrobbler.com/2.0/', payload = payload, method= urlfetch.POST).content ) )
    
    except:
        return {'Message' : 'ERROR : Wrong token. Please retry the authentication process at http://lastfmerge.appspot.com/auth', 'Error' : True}

bottle.run(app, server = 'gae')
