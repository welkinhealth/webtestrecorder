import sys
import os

from webtestrecorder import get_records, write_function_unittest

intro = """
from dugong.test.functional.dugong_test_case import DugongTestCase


class TwilioTests(DugongTestCase):

 def test_autogen(self):
   app = self.test_app
"""


def request_filter(req):
  return req.response.status_code != 401 and ('twilio/phonograph' in req.url or 'recording_proxy' in req.url)


header_transforms = {
    # basic auth for "megasecretpwd"
    'authorization': lambda (old_val): 'Basic dHdpbGlvOm1lZ2FzZWNyZXRwd2Q='
}


def response_processor(req):
  b = req.response.body
  b = b.replace('https://twilio:g3qmwbY1WmgX@wiltzius.ngrok.io',
                'http://twilio:megasecretpwd@localhost')
  return b


def main():
  welkin_root = os.environ['WELKIN_ROOT']
  with open(welkin_root + '/web_recorder_output.txt') as f:
    records = get_records(f)
    write_function_unittest(records, sys.stdout, intro=intro, filter_fn=request_filter,
                            resp_processing_fn=response_processor,
                            header_transforms=header_transforms)


if __name__ == '__main__':
  main()
