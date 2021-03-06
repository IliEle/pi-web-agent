#!/usr/bin/python
import sys
import os
import xml.etree.ElementTree as ET
from random import random, seed
import ast
if 'MY_HOME' not in os.environ:
    os.environ['MY_HOME']='/usr/libexec/pi-web-agent'
sys.path.append(os.environ['MY_HOME']+'/cgi-bin/toolkit')
sys.path.append(os.environ['MY_HOME']+'/cgi-bin/chrome')
sys.path.append(os.environ['MY_HOME']+'/cgi-bin')
import cgi, cgitb
from HTMLPageGenerator import *
cgitb.enable()

class InvalidXMLException(Exception):
    AUTH_ERROR=30
    BAD_TAG=22
    API_DISABLED=10
    CALLED_FROM_BROWSER = 401 
    def __init__(self, message=None, code=None):
        Exception.__init__(self)
        if message == None:
            self.strerror=""
        else:
            self.strerror=message
        
        if code == None or (code < 0 or code > 500):
            self.ex_code=500
        else:
            self.ex_code = code
        
    def __str__(self):
        return "InvalidXMLException: " + self.strerror + "\nCode:" + str(self.ex_code)

        
class RequestManager(object):

    def __init__(self, xml):
        self.xml=xml
        el_request = self.xml.getroot()
        if (not el_request.tag == 'request'):
            raise InvalidXMLException(message='request expected')
        request_type = el_request.attrib.get('type')
        self.id = str(random()).split('.')[1]  
        if request_type == 'authentication':
            self.request = AuthenticationRequest(el_request, self.id)

    
    def submit(self):
        self.request.doTransaction()
        
def findSingleElement(key, xml):
        element=xml.findall(key)
        if len(element) > 1:
            raise InvalidXMLException(message='Multiple tag: ' + key)
        if len(element) == 0:
            return None    
        return element[0]        

HEADER="cernvm-api"
SUPPORTED_VERSIONS=["1.0"]

#abstract class Request / Pattern: Template for other requests
class Request(object):

    def __init__(self, request, rmID):
        self.xml=request
        seed(os.urandom)
        self.req_id=rmID

    def doTransaction(self):
        try:        
            self._parse()  
            self._validate()
            self._execute()
            self._response()
        except InvalidXMLException as ixe:
            self._response(ixe)
            
    def _parse(self):
        raise NotImplementedError()
        
    def _execute(self):
        
        raise NotImplementedError()
    
    def _validate(self):
        raise NotImplementedError()

    def _authenticate(self):
        data=None
        try:
            with open(os.environ['MY_HOME']+"/etc/config/.api_access", "r") as regFile:
                data = ast.literal_eval(regFile.readline())
        except IOError as ioe:
            raise InvalidXMLException('API not enabled', InvalidXMLException.API_DISABLED)
            
        username = data.keys()[0]
        apikey = data[username]
        if username == self.username and apikey == self.apikey:
            return
        else:
            raise InvalidXMLException('Authentication failure', InvalidXMLException.AUTH_ERROR)
            
    def _response(self, ex=None):
        response = Response(self.req_id)
        if ex==None:
            responseCode = 0
        else:
            responseCode = ex.ex_code
        self.code = responseCode
        response.buildResponse(responseCode)
        composeXMLDocument(response.xml)

                
class AuthenticationRequest(Request):       
        
    def _parse(self):
        el_username=findSingleElement('username', self.xml)
        if el_username == None:
            raise InvalidXMLException(message='Tag <username> not found')    
        el_apikey=findSingleElement('api-key', self.xml)
        if el_apikey == None:
            raise InvalidXMLException(message='Tag <apikey> not found')
        self.username = el_username.text
        self.apikey = el_apikey.text    
            
    def _validate(self):
        self._authenticate()

    def _execute(self):
        pass

class SimpleAuthenticationRequest(AuthenticationRequest):

    def doTransaction(self):
        self._parse()
        self._validate()
      
class Response(object):    

    def __init__(self, rID):

        self.id=rID
        pass
    
    def buildResponse(self, rcode, message=None):
        req=ET.Element('response')
        req.text=str(self.id)
        code=ET.Element('code')
        if message == None:
            code.text=str(rcode)
        else:
            code.text = str(rcode) + ' ' + message
        self.xml=ET.Element('pi-api', {'version':'1.0'})
        self.xml.append(req)
        self.xml.append(code)

def errorResponse(message):
    return ""
    
def main():
    fs=cgi.FieldStorage()
    if 'xml' not in fs:
        ixe = InvalidXMLException('Post might be called from browser',\
         InvalidXMLException.CALLED_FROM_BROWSER)
        raise ixe    
    transaction=ET.fromstring(fs['xml'].value)
    el_tree = ET.ElementTree()
    el_tree._setroot(transaction)
    try:
        rm=RequestManager(el_tree)
        rm.submit()
    except InvalidXMLException as ixe:
        response=Response(0)
        response.buildResponse(ixe.ex_code)
        composeXMLDocument(response.xml)


if __name__ == '__main__':
    try:
        main()
    except InvalidXMLException as ixe:
        r=Response(0)
        r.buildResponse(ixe.ex_code)     
        composeXMLDocument(r.xml)
