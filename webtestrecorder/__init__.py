import sys
import re
import warnings
import optparse
from webob.dec import wsgify
from webob import Request
from webtest import TestRequest, TestResponse
from webob import descriptors

@wsgify.middleware
def recorder(req, app, file):
    data = []
    data.append('--Request:\n')
    data.append(str(req))
    if not req.content_length:
        data.append('\n')
    resp = req.get_response(app)
    data.append('\n--Response:\n')
    data.append(str(resp))
    data.append('\n')
    file.write(''.join(data))
    return resp

def record_file(app, filename):
    fp = open(filename, 'ab')
    return recorder(app, file=fp)

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

def write_doctest(records, fp):
    for req in records:
        write_doctest_item(req, fp)

def write_doctest_item(req, fp, default_host='http://localhost'):
    fixup_response(req)
    resp = req.response
    call_text = str_method_call(req, resp, default_host)
    fp.write('    >>> print app%s\n' % call_text)
    for line in str(resp).splitlines():
        if not line:
            fp.write('    <BLANKLINE>\n')
        else:
            fp.write('    %s\n' % line)

def write_function_unittest(records, fp, func_name='test_app', include_intro=True,
                            indent='', default_host='http://localhost'):
    if include_intro:
        fp.write('%sfrom webtest import TestApp\n\n' % indent)
        fp.write('%sdef %s():\n' % (indent, func_name))
        fp.write('%s    app = TestApp(application)\n' % indent)
    for req in records:
        write_function_unittest_item(req, fp, indent + '    ', app_name='app',
                                     default_host=default_host)

def write_function_unittest_item(req, fp, indent, app_name='app', default_host='http://localhost'):
    fixup_response(req)
    resp = req.response
    call_text = str_method_call(req, resp, default_host)
    fp.write('%sresp = %s%s\n' % (indent, app_name, call_text))
    fp.write('%sassert resp.body == %s\n' % (indent, pyrepr(resp.body, indent)))
    ## FIXME: I could check other things, but what things specifically?

def fixup_response(req):
    """Make sure the req has a TestResponse response"""
    if not isinstance(req.response, TestResponse):
        resp = TestResponse(body=req.response.body, status=req.response.status,
                            headerlist=req.response.headerlist)
        req.response = resp

def str_method_call(req, resp=None, default_host='http://localhost'):
    """Returns a method call that represents the given request, as
    though you were generating that request with WebTest.

    This returns something like ``'.get(\"url\")'`` -- you add the
    object.
    """
    if resp is None:
        resp = req.response
    url = req.url
    if url.startswith(default_host + '/'):
        url = url[len(default_host):]
    kw = {}
    for name, value in req.headers.iteritems():
        py_name = name.lower().replace('-', '_')
        if py_name == 'content_type':
            if not value or value.lower() == 'application/x-www-form-urlencoded':
                # Default content-type
                continue
        if py_name == 'content_length':
            continue
        if py_name == 'host':
            continue
        if hasattr(Request, py_name):
            desc = getattr(Request, py_name)
            if isinstance(desc, descriptors.converter):
                value = desc.getter_converter(value)
            kw[py_name] = value
        else:
            kw.setdefault('headers', {})[name] = value
    if req.method == 'POST' and req.content_type == 'application/x-www-form-urlencoded':
        if dict(req.POST) == req.POST:
            kw['params'] = dict(req.POST)
        else:
            kw['params'] = req.POST.items()
    else:
        if req.body:
            kw['body'] = req.body
    if resp.status_int >= 400:
        kw['status'] = resp.status_int
    params = [pyrepr(url)]
    params.extend('%s=%s' % (name, pyrepr(value)) for name, value in sorted(kw.items()))
    params = ', '.join(params)
    ## FIXME: not all methods work this way (e.g., there's no app.mkcol()):
    return '.%s(%s)' % (req.method.lower(), params)

def pyrepr(value, indent=''):
    if isinstance(value, basestring) and '\n' in value:
        v = repr(value)
        q = v[0]
        v = q + q + v + q + q
        lines = v.split('\\n')
        return '\n'.join(lines[0] + [indent + l for l in lines[1:]])
    elif isinstance(value, dict):
        if all(re.match(r'[a-z_][a-z_0-9]*', key) for key in value):
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
