import config
from hashlib import md5
import urlparse, simplejson
from google.appengine.api import urlfetch
import random

def parse_qs(qs):
    result = dict()
    for pair in qs.split('&'):
        sep = pair.split('=')
        result [ sep[0] ] = sep[1]
    return result

def makesig(url = None, params = None):
    #Making an ordered dictionnary of query parameters for the URL
    if url != None:
        dic = parse_qs( urlparse.urlparse(url).query )
    elif params != None:
        dic = params
    try:
        dic.pop('format')
    except:
        pass
    result = str()
    for key in sorted(dic): #While sorting the dictionnary alphabetically
        #Append each <name><value> pair included in dictionnary
        result = result + key + str(dic[key])

    result = result + config.lastfm['Secret'] #Appending Secret API Key
    #Hashing the string with MD5
    hashobject = md5()
    hashobject.update(result)
    result = hashobject.hexdigest()
    return result

def appendsig(url):
    sig = makesig(url)
    return url + '&api_sig=' + sig

def jsonfetch(url, payload = None, method = urlfetch.GET):
    error = 0
    ok = False
    while ok == False and error < 3:
        try:
            data = urlfetch.fetch(url, payload = payload, method = method).content
            ok = True
        except:
            error = error + 1
    if ok == True:
        return simplejson.loads(data)
    else:
        return None

class Token:
    def __init__(self, length=50, capitals = True):
        self.length = length
        self.token = str()
        self.capitals = capitals
        self.iterator = 0
        
    def genLetter(self):
        letter = random.choice('abcdefghijklmnopqrstuvwxyz')
        if self.capitals == True:
            if random.randint(0, 1) == 1:
                letter = letter.capitalize()
        return letter
    
    def genInt(self):
        return random.randint(0,9)
        
    def make(self):
        while self.iterator != self.length:
            if random.randint(0, 1) == 1:
                char = self.genInt()
            else:
                char = self.genLetter()
            char = str(char)
            self.token = self.token + char
            self.iterator = self.iterator + 1
            
        return self.token