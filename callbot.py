# -*- encoding: utf-8 -*-

import json
import ovh
import os
import time
import sys
import inspect
from datetime import datetime

# mandatory variables, example below
#
# OVH_ENDPOINT=ovh-eu
# OVH_APP_KEY=rIksDzjVfgRTsmAP
# OVH_APP_SEC=1qEFGlks45FRGH234Abhdsjt99abDFRF
# OVH_CONS_KEY=EEJdlkzox4dkjb5nqiubf5jjSSF45flk
# BOT_NUMBER_LIST=0102030405,0203040506,0304050607
# OVH_BILLING_ACCOUNT=vc12345-ovh-1
# OVH_SIP_LINE_NUMBER=0033972012345

# optional variables with default values
#
# OVH_TEXT_MESSAGE="We all have two lives, the second begins when we realize we only have one"
# OVH_ANONYMOUS_CALL=False
# OVH_CALL_TIMEOUT=20
# BOT_WAIT_BEFORE_API_CHECK=20
# BOT_WAIT_BEFORE_NEXT_CALL=10
# BOT_TRY_COUNT_PER_NUMBER=1
# BOT_RING_UNTIL_ANSWER=False

vars = [ \
         'OVH_ENDPOINT',\
         'OVH_APP_KEY',\
         'OVH_APP_SEC',\
         'OVH_CONS_KEY',\
         'BOT_NUMBER_LIST',\
         'OVH_BILLING_ACCOUNT',\
         'OVH_SIP_LINE_NUMBER',\
       ]


for elem in vars:
    if elem not in os.environ:
        print("error : %s is not set in environment. exiting."%elem)
        import sys
        sys.exit(1)


# Instanciate an OVH Client.
# You can generate new credentials with full access to your account on
# the token creation page
client = ovh.Client(
    endpoint=os.environ.get('OVH_ENDPOINT'),               # Endpoint of API OVH Europe (List of available endpoints)
    application_key=os.environ.get('OVH_APP_KEY'),         # Application Key
    application_secret=os.environ.get('OVH_APP_SEC'),      # Application Secret
    consumer_key=os.environ.get('OVH_CONS_KEY'),           # Consumer Key
)

# ovh billing account unique identifier
ovhaccount = os.environ.get('OVH_BILLING_ACCOUNT')

# ovh sip line that makes the call
sipline = os.environ.get('OVH_SIP_LINE_NUMBER')

# text message to announce when communication is established
if 'OVH_TEXT_MESSAGE' in os.environ:
    message = os.environ.get('OVH_TEXT_MESSAGE')
else:
    message = "We all have two lives, the second begins when we realize we only have one"

# list of oncall phone numbers to iterate on
oncallnumbers = os.environ.get('BOT_NUMBER_LIST')
numbers = []
numbers.append(oncallnumbers)
if ' ' in oncallnumbers:
    numbers = oncallnumbers.split(' ')
if ',' in oncallnumbers:
    numbers = oncallnumbers.split(',')

# enable anonymous call
if 'OVH_ANONYMOUS_CALL' in os.environ:
    anonymous = os.environ.get('OVH_ANONYMOUS_CALL')
else:
    anonymous = "false"

# call ring duration
if 'OVH_CALL_TIMEOUT' in os.environ:
    calltimeout = os.environ.get('OVH_CALL_TIMEOUT')
else:
    calltimeout = 20

# time to wait before asking call status to API
# should be greater than ring duration
if 'BOT_WAIT_BEFORE_API_CHECK' in os.environ:
    apisleep = os.environ.get('BOT_WAIT_BEFORE_API_CHECK')
else:
    apisleep = 30

# time to wait between calls
if 'BOT_WAIT_BEFORE_NEXT_CALL' in os.environ:
    callsleep = os.environ.get('BOT_WAIT_BEFORE_NEXT_CALL')
else:
    callsleep = 10

# number of try per phone number
if 'BOT_TRY_COUNT_PER_NUMBER' in os.environ:
    trycount = os.environ.get('BOT_TRY_COUNT_PER_NUMBER')
else:
    trycount = 1

# loop over all numbers until someone answer
if 'BOT_RING_UNTIL_ANSWER' in os.environ:
    ring_until_answer = os.environ.get('BOT_RING_UNTIL_ANSWER')
else:
    ring_until_answer = False

baseapi = '/telephony/' + ovhaccount + '/line/' + sipline

def make_call(phonenumber,msg):
    result = client.post(baseapi + '/automaticCall',
        bridgeNumberDialplan=None, # Number to call if transfer in dialplan selected (type: phoneNumber)
        calledNumber=phonenumber, # Number to call (type: phoneNumber)
        callingNumber=sipline, # Optional, number where the call come from (type: phoneNumber)
        dialplan='ReadText', # Dialplan used for the call (type: telephony.CallsGeneratorDialplanEnum)
        isAnonymous=anonymous, # For anonymous call (type: boolean)
        playbackAudioFileDialplan=None, # Name of the audioFile (if needed) with extention. This audio file must have been upload previously (type: string)
        timeout=calltimeout, # Timeout (in seconds). Default is 20 seconds (type: long)
        ttsTextDialplan=msg, # Text to read if TTS on dialplan selected (type: string)
    )
    return str(result)

def logit(msg, stdout=True, stderr=False):
    curframe = inspect.currentframe()
    calframe = inspect.getouterframes(curframe, 2)
    try:
        timestamp = str(datetime.now())
    except:
        timestamp = '?'

    content = '['+calframe[1][3]+']['+timestamp+'] '+msg
    if stdout:
        sys.stdout.write(content+"\n")
    if stderr:
        sys.stderr.write("error ==> %s\n" % (content))

def get_call_info(callid):
    result = client.get(baseapi +'/automaticCall/' + callid)
    return result

def display_call_info(callid):
    payload = get_call_info(callid)
    print("%s"%json.dumps(payload, indent=4))

def ring_loop(number, iteration=1):
    cpt = int(iteration) + 1
    for i in range(1, cpt):
        logit("Ringing %s   [try %s/%s]"%(number, i, iteration))
        mycall = make_call(number, message)
        logit("    => waiting %s seconds before querying api for call status"%apisleep)
        time.sleep(apisleep)
        data = get_call_info(mycall)
        #display_call_info(mycall)
        if data['callDuration'] > 0 and data['answerDatetime'] is not None:
            logit("    => communication established at %s for %s seconds"%(data['answerDatetime'], data['callDuration']))
            sys.exit(0)
        else:
            logit("    => no answer")
        logit("    => waiting %s seconds before next call"%callsleep)
        time.sleep(callsleep)

def oncall_loop():
    for num in numbers:
        logit("Calling number %s"%num)
        ring_loop(num, iteration=trycount)

logit("Oncall Bot started at UTC %s\n"%datetime.now())
while True:
    oncall_loop()
    if not ring_until_answer:
        break
