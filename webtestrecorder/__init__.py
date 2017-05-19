import sys
import re
import warnings
import optparse
import threading
from cStringIO import StringIO
from tempita import HTMLTemplate
from webob.dec import wsgify
from webob import exc
from webob import Request, Response
from webtest import TestRequest, TestResponse


class Recorder(object):
  def __init__(self, app, file, intercept='/.webtestrecorder', require_devauth=False, record_filter_fn=None):
    self.app = app
    if isinstance(file, basestring):
      file = open(file, 'ab')
    self.file = file
    self.lock = threading.Lock()
    self.intercept = intercept
    self.require_devauth = require_devauth
    self.record_filter_fn = record_filter_fn

  @classmethod
  def entry_point(cls, app, global_conf, filename, intercept='/.webtestrecorder',
                  require_devauth=False):
    from paste.deploy.converters import asbool
    require_devauth = asbool(require_devauth)
    return cls(app, filename, intercept, require_devauth)

  @wsgify
  def __call__(self, req):
    if self.intercept and req.path_info.startswith(self.intercept):
      return self.internal(req)
    resp = req.get_response(self.app)
    if (not self.record_filter_fn) or self.record_filter_fn(req):
      self.write_record(req, resp)
    return resp

  def write_record(self, req, resp):
    data = []
    data.append('--Request:\n')
    data.append(str(req))
    if not req.content_length:
      data.append('\n')
    data.append('\n--Response:\n')
    data.append(str(resp))
    if not resp.body:
      data.append('\n')
    data.append('\n')
    self.lock.acquire()
    try:
      self.file.write(''.join(data))
      self.file.flush()
    finally:
      self.lock.release()

  @wsgify
  def internal(self, req):
    if (self.require_devauth
        and not req.environ.get('x-wsgiorg.developer_user')):
      raise exc.HTTPForbidden('You must login')
    if req.method == 'POST':
      if req.params.get('clear'):
        name = self.file.name
        self.file.close()
        self.file = open(name, 'wb')
      else:
        false_req = Request.blank('/')
        false_resp = Response('', status='200 Internal Note')
        false_resp.write(req.params['note'])
        self.write_record(false_req, false_resp)
      raise exc.HTTPFound(req.url)
    if req.params.get('download'):
      if req.params['download'] == 'doctest':
        text = self.doctest(req)
      else:
        text = self.function_unittest(req)
      return Response(text, content_type='text/plain')
    return Response(self._intercept_template.substitute(req=req, s=self))

  _intercept_template = HTMLTemplate('''\
<html>
 <head>
  <title>WebTest Recorder</title>
  <style type="text/css">
    body {
      font-family: sans-serif;
    }
    pre {
      overflow: auto;
    }
  </style>
 </head>
 <body>
  <h1>WebTest Recorder</h1>

  <div>
   <a href="#doctest">doctest</a> (<a href="{{req.url}}?download=doctest">download</a>)
     | <a href="#function_unittest">function unittest</a>
       (<a href="{{req.url}}?download=function_unittest">download</a>)
  </div>

  <form action="{{req.url}}" method="POST">
   <fieldset>
   You may add a note/comment to the record:<br>
   <textarea name="note" rows=4 style="width: 100%"></textarea><br>
   <button type="submit">Save note</button>
   <button type="submit" name="clear" value="1"
    style="background-color: #f99">Clear!</button>
   </fieldset>
  </form>

  <h1 id="doctest">Current tests as a doctest</h1>

  <pre>{{s.doctest(req)}}</pre>

  <h1 id="function_unittest">Current tests as a function unittest</h1>

  <pre>{{s.function_unittest(req)}}</pre>

 </body>
</html>
''', name='_intercept_template')

  def doctest(self, req):
    records = self.get_records()
    out = StringIO()
    write_doctest(records, out, default_host=req.host)
    return out.getvalue()

  def function_unittest(self, req):
    records = self.get_records()
    out = StringIO()
    write_function_unittest(records, out, default_host=req.host)
    return out.getvalue()

  def get_records(self):
    self.file.flush()
    fn = self.file.name
    fp = open(fn, 'rb')
    content = StringIO(fp.read())
    fp.close()
    return get_records(content)


def get_records(file, RequestClass=TestRequest,
                ResponseClass=TestResponse):
  if isinstance(file, basestring):
    file = open(file, 'rb')
  records = []
  while 1:
    line = file.readline()
    if not line:
      break
    line = line.strip()
    if not line:
      # Because we add a newline at the end of the request, a
      # blank line is likely here:
      line = file.readline()
      if not line:
        break
      line = line.strip()
    if not line.startswith('--Request:'):
      warnings.warn('Invalid line (--Request: expected) at byte %s in %s'
                    % (file.tell(), file))
    req = RequestClass.from_file(file)
    line = file.readline()
    if not line.strip():
      line = file.readline()
    if not line:
      records.append(req)
      break
    line = line.strip()
    if not line:
      line = file.readline()
      if not line:
        break
      line = line.strip()
    if not line.startswith('--Response:'):
      warnings.warn('Invalid line (--Response: expected) at byte %s in %s'
                    % (file.tell(), file))
    resp = ResponseClass.from_file(file)
    resp.request = req
    req.response = resp
    records.append(req)
  return records


def write_doctest(records, fp, default_host='http://localhost'):
  for req in records:
    write_doctest_item(req, fp, default_host)


def write_doctest_item(req, fp, default_host='http://localhost'):
  fixup_response(req)
  resp = req.response
  msg = internal_note(resp)
  if msg:
    fp.write('\n%s\n\n' % msg.strip())
    return
  call_text = str_method_call(req, resp, default_host)
  fp.write('    >>> print app%s\n' % call_text)
  for line in str(resp).splitlines():
    if not line:
      fp.write('    <BLANKLINE>\n')
    else:
      fp.write('    %s\n' % line)


def default_intro(fp, indent, func_name):
  fp.write('%sfrom webtest import TestApp\n\n' % indent)
  fp.write('%sdef %s():\n' % (indent, func_name))
  fp.write('%s    app = TestApp(application)\n' % indent)


def write_function_unittest(records, fp, func_name='test_app', intro='default',
                            indent='', default_host='http://localhost', filter_fn=None, resp_processing_fn=None,
                            header_transforms=None):
  if intro == 'default':
    default_intro(fp, indent, func_name)
  elif intro:
    fp.write(intro)
  for req in records:
    write_function_unittest_item(req, fp, indent + '    ', app_name='app', default_host=default_host,
                                 filter_fn=filter_fn, resp_processing_fn=resp_processing_fn,
                                 header_transforms=header_transforms)


def write_function_unittest_item(req, fp, indent, app_name='app', default_host='http://localhost', filter_fn=None,
                                 resp_processing_fn=None, header_transforms=None):
  if not hasattr(req, 'response'):
    return

  if filter_fn and not filter_fn(req):
    return

  fixup_response(req)
  resp = req.response

  # if resp.status_code == 401:
  #   return

  msg = internal_note(resp)
  if msg:
    fp.write(''.join('%s# %s\n' % (indent, line)
                     for line in msg.splitlines()))
    return

  call_text = str_method_call(req, resp, default_host, header_transforms=header_transforms)
  fp.write('%sresp = %s%s\n' % (indent, app_name, call_text))

  # if resp.content_type == 'application/json':
    # import ipdb; ipdb.set_trace()
  b = resp_processing_fn(req) if resp_processing_fn else req.body
  # print b
  fp.write('%sassert resp.body == %s\n' % (indent, pyrepr(b, indent)))
  ## FIXME: I could check other things, but what things specifically?


def fixup_response(req):
  """Make sure the req has a TestResponse response"""
  try:
    if not req.response or not isinstance(req.response, TestResponse):
      resp = TestResponse(body=req.response.body, status=req.response.status,
                          headerlist=req.response.headerlist)
      req.response = resp

  except:
    import ipdb; ipdb.set_trace()


def internal_note(resp):
  """Returns the internal note, if the response is such a response.
  Otherwise returns None."""
  if resp.status.lower() == '200 internal note':
    return resp.body
  return None


def match_host(hostname, url):
  if not hostname.startswith('http://'):
    if ':' in hostname:
      hostname = hostname.split(':', 1)[0]
    hostname = 'http://' + hostname
  if url.startswith(hostname + '/'):
    return url[len(hostname):]
  elif url.startswith(hostname + ':'):
    url = url[len(hostname) + 1:]
    if '/' in url:
      return '/' + url.split('/', 1)[1]
    else:
      return '/'
  else:
    if hostname == 'http://127.0.0.1':
      return match_host('http://localhost', url)
    return url


def str_method_call(req, resp=None, default_host='http://localhost', header_transforms=None):
  """Returns a method call that represents the given request, as
  though you were generating that request with WebTest.

  This returns something like ``'.get(\"url\")'`` -- you add the
  object.
  """
  if resp is None:
    resp = req.response
  # url = req.url
  url = req.path_qs
  url = match_host(default_host, url)
  kw = {}
  # import ipdb; ipdb.set_trace()
  for name, value in req.headers.iteritems():
    py_name = name.lower().replace('-', '_')

    # TODO pass in list of header name => transform functions, no-op transforms for ones that should be included

    if py_name == 'content_type':
      if not value or value.lower() == 'application/x-www-form-urlencoded':
        # Default content-type
        continue
    if py_name in ('content_length', 'host', 'user_agent',
                   'connection', 'keep_alive',
                   'accept_language', 'accept_charset', 'accept_encoding',
                   'cache_control'):
      # blacklisted headers
      continue
    elif header_transforms and py_name in header_transforms:
      # whitelisted headers, with optional transforms
      if header_transforms[py_name] is None:
        kw.setdefault('headers', {})[name] = value
      else:
        kw.setdefault('headers', {})[name] = header_transforms[py_name](value)
  if req.method == 'POST' and req.content_type == 'application/x-www-form-urlencoded':
    if dict(req.POST) == req.POST:
      kw['params'] = dict(req.POST)
    else:
      kw['params'] = req.POST.items()
  else:
    if req.body:
      b = req.body
      kw['params'] = b
  if resp.status_int >= 400:
    kw['status'] = resp.status_int
  params = [pyrepr(url)]
  params.extend('%s=%s' % (name, pyrepr(value)) for name, value in sorted(kw.items()))
  params = ', '.join(params)
  ## FIXME: not all methods work this way (e.g., there's no app.mkcol()):
  return '.%s(%s)' % (req.method.lower(), params)


def pyrepr(value, indent=''):
  if isinstance(value, basestring) and '\n' in value:
    # v = repr(value)
    # q = v[0]
    # v = q + q + v + q + q
    # lines = v.split('\\n')
    # return '\n'.join(lines[0] + [indent + l for l in lines[1:]])
    return repr(value)
  elif isinstance(value, dict):
    if all((isinstance(key, basestring)
            and re.match(r'^[a-zA-Z_][a-zA-Z_0-9]*$', key))
           for key in value):
      return 'dict(%s)' % (', '.join('%s=%s' % (key, pyrepr(v, indent))
                                     for key, v in sorted(value.items())))
    else:
      return '{%s}' % (', '.join('%s: %s' % (pyrepr(key, indent), pyrepr(v, indent))
                                 for key, v in sorted(value.items())))
  else:
    return repr(value)


parser = optparse.OptionParser(
  usage='%prog < recorded_file > doctest')

parser.add_option(
  '--func-unittest', action='store_true',
  help="Write a functional unittest instead of a doctest")


def main():
  options, args = parser.parse_args()
  records = get_records(sys.stdin)
  if options.func_unittest:
    write_function_unittest(records, sys.stdout)
  else:
    write_doctest(records, sys.stdout)


if __name__ == '__main__':
  main()
