# -*- encoding: utf-8 -*-

import json
import logging
import os
import re
import sys
import time

import ovh

# mandatory variables, example below
#
# OVH_ENDPOINT=ovh-eu
# OVH_APP_KEY=rIksDzjVfgRTsmAP
# OVH_APP_SEC=1qEFGlks45FRGH234Abhdsjt99abDFRF
# OVH_CONS_KEY=EEJdlkzox4dkjb5nqiubf5jjSSF45flk
# BOT_NUMBER_LIST=0102030405,0203040506,0304050607   (not needed in check mode)
# OVH_BILLING_ACCOUNT=vc12345-ovh-1
# OVH_SIP_LINE_NUMBER=0033972012345

# optional variables with default values
#
# OVH_TEXT_MESSAGE="We all have two lives, the second begins when we realize we only have one"
# OVH_ANONYMOUS_CALL=False
# OVH_CALL_TIMEOUT=20               ring duration, in seconds
# OVH_DIALPLAN=ReadText             ReadText reads the text and hangs up.
#                                   RequestAppointmentConfirmation reads the text,
#                                   then asks to press a key to confirm.
# BOT_ACK_RESULTS=                  if set (ex: "rdvConfirmed"), a call is acknowledged
#                                   only if its applicationResult is in this list.
#                                   A voicemail can't confirm, so it can't acknowledge.
# BOT_WAIT_BEFORE_NEXT_CALL=10
# BOT_CALL_MAX_WAIT=300             max seconds to wait for a call to hang up
# BOT_POLL_INTERVAL=5               seconds between two call status queries
# BOT_TRY_COUNT_PER_NUMBER=1
# BOT_RING_UNTIL_ANSWER=False
# BOT_MAX_DURATION=0                give up after this many seconds (0 = never)
# BOT_DEBUG=False                   dump the call status returned by the api
#
# exit codes: 0 acknowledged (or check ok), 1 nobody acknowledged (or check
# failed), 2 configuration error.

logging.basicConfig(
    format="[%(asctime)s] %(levelname)s %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
log = logging.getLogger("callbot")

EXIT_OK = 0
EXIT_NO_ACK = 1
EXIT_CONFIG = 2


def env_str(name, default=None):
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


def env_int(name, default):
    value = env_str(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        log.error("%s=%r is not an integer", name, value)
        sys.exit(EXIT_CONFIG)


def env_bool(name, default):
    value = env_str(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "y", "on")


def parse_list(value):
    # accept comma and/or space separated lists, ignore stray quotes
    value = value.replace('"', "").replace("'", "")
    return [n for n in re.split(r"[\s,]+", value) if n]


def check_mandatory(names):
    missing = [n for n in names if not env_str(n)]
    if missing:
        log.error("not set in environment: %s. exiting.", ", ".join(missing))
        sys.exit(EXIT_CONFIG)


class CallBot(object):
    def __init__(self):
        self.client = ovh.Client(
            endpoint=env_str("OVH_ENDPOINT"),
            application_key=env_str("OVH_APP_KEY"),
            application_secret=env_str("OVH_APP_SEC"),
            consumer_key=env_str("OVH_CONS_KEY"),
        )
        self.baseapi = "/telephony/%s/line/%s" % (
            env_str("OVH_BILLING_ACCOUNT"),
            env_str("OVH_SIP_LINE_NUMBER"),
        )
        self.sipline = env_str("OVH_SIP_LINE_NUMBER")
        self.message = env_str(
            "OVH_TEXT_MESSAGE",
            "We all have two lives, the second begins when we realize we only have one",
        )
        self.anonymous = env_bool("OVH_ANONYMOUS_CALL", False)
        self.calltimeout = env_int("OVH_CALL_TIMEOUT", 20)
        self.dialplan = env_str("OVH_DIALPLAN", "ReadText")
        self.ack_results = parse_list(env_str("BOT_ACK_RESULTS", ""))
        self.callsleep = env_int("BOT_WAIT_BEFORE_NEXT_CALL", 10)
        self.call_max_wait = env_int("BOT_CALL_MAX_WAIT", 300)
        self.poll_interval = env_int("BOT_POLL_INTERVAL", 5)
        self.trycount = env_int("BOT_TRY_COUNT_PER_NUMBER", 1)
        self.ring_until_answer = env_bool("BOT_RING_UNTIL_ANSWER", False)
        self.max_duration = env_int("BOT_MAX_DURATION", 0)
        self.debug = env_bool("BOT_DEBUG", False)
        self.started = time.time()

    def expired(self):
        return self.max_duration > 0 and time.time() - self.started > self.max_duration

    def make_call(self, number):
        result = self.client.post(
            self.baseapi + "/automaticCall",
            calledNumber=number,
            callingNumber=self.sipline,
            dialplan=self.dialplan,
            isAnonymous=self.anonymous,
            timeout=self.calltimeout,
            ttsTextDialplan=self.message,
        )
        return str(result)

    def wait_call_end(self, callid):
        """
        Poll the call status until the api reports a hangup, instead of
        guessing how long the call lasts. Return the last status seen.
        """
        deadline = time.time() + self.call_max_wait
        data = None
        while time.time() < deadline:
            time.sleep(self.poll_interval)
            try:
                data = self.client.get(self.baseapi + "/automaticCall/" + callid)
            except Exception as exc:
                # the call may not be visible yet, or a transient api error
                log.warning("    => call %s status query failed: %s", callid, exc)
                continue
            if data.get("hangupDatetime"):
                return data
        log.warning("    => call %s not hung up after %ss", callid, self.call_max_wait)
        return data

    def acknowledged(self, data):
        if not data:
            return False
        answered = (data.get("callDuration") or 0) > 0 and data.get("answerDatetime") is not None
        if not answered:
            return False
        if not self.ack_results:
            return True
        # the dtmf field is not reliable (a confirmed call can report ","),
        # the application result is.
        return data.get("applicationResult") in self.ack_results

    def ring(self, number, attempt):
        log.info("Ringing %s   [try %s/%s]", number, attempt, self.trycount)
        try:
            callid = self.make_call(number)
        except Exception as exc:
            log.error("    => call to %s failed: %s", number, exc)
            return False
        data = self.wait_call_end(callid)
        if self.debug:
            log.info("    => call status:\n%s", json.dumps(data, indent=4, default=str))
        if self.acknowledged(data):
            log.info(
                "    => acknowledged at %s, call lasted %ss, result %s",
                data.get("answerDatetime"), data.get("callDuration"), data.get("applicationResult"),
            )
            return True
        if data:
            log.info(
                "    => not acknowledged: answer %s, duration %s, result %s, hangup cause %s",
                data.get("answerDatetime"), data.get("callDuration"),
                data.get("applicationResult"), data.get("hangupCause"),
            )
        else:
            log.info("    => not acknowledged: no call status")
        return False

    def run(self, numbers):
        log.info(
            "Oncall bot started: numbers %s, dialplan %s, ack results %s",
            " ".join(numbers), self.dialplan, " ".join(self.ack_results) or "any answer",
        )
        while True:
            for number in numbers:
                log.info("Calling number %s", number)
                for attempt in range(1, self.trycount + 1):
                    if self.expired():
                        log.error("nobody acknowledged within %ss. giving up.", self.max_duration)
                        return EXIT_NO_ACK
                    if self.ring(number, attempt):
                        return EXIT_OK
                    log.info("    => waiting %s seconds before next call", self.callsleep)
                    time.sleep(self.callsleep)
            if not self.ring_until_answer:
                log.error("nobody acknowledged. giving up.")
                return EXIT_NO_ACK

    def check(self):
        """
        Validate the api access (tls, credentials, line) without making a call.
        """
        try:
            line = self.client.get(self.baseapi)
        except Exception as exc:
            log.error("check failed: %s", exc)
            return EXIT_NO_ACK
        log.info("check ok: line %s", line.get("serviceName", self.sipline))
        return EXIT_OK


def main(argv):
    mandatory = [
        "OVH_ENDPOINT",
        "OVH_APP_KEY",
        "OVH_APP_SEC",
        "OVH_CONS_KEY",
        "OVH_BILLING_ACCOUNT",
        "OVH_SIP_LINE_NUMBER",
    ]
    if "--check" in argv:
        check_mandatory(mandatory)
        return CallBot().check()
    check_mandatory(mandatory + ["BOT_NUMBER_LIST"])
    numbers = parse_list(env_str("BOT_NUMBER_LIST"))
    if not numbers:
        log.error("BOT_NUMBER_LIST is empty. exiting.")
        return EXIT_CONFIG
    return CallBot().run(numbers)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
