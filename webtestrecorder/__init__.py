import sys
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

def write_doctest_item(req, fp):
    resp = req.response
    if not isinstance(resp, TestResponse):
        resp = TestResponse(body=resp.body, status=resp.status,
                            headerlist=resp.headerlist)
        req.response = resp
    url = req.url
    if url.startswith('http://localhost/'):
        url = url[len('http://localhost'):]
    kw = {}
    for name, value in req.headers.iteritems():
        if name.lower() == 'content-type':
            continue
        if name.lower() == 'content-length':
            continue
        if name.lower() == 'host':
            continue
        py_name = name.lower().replace('-', '_')
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
        kw['content_type'] = req.content_type
    if resp.status_int >= 400:
        kw['status'] = resp.status_int
    params = [repr(url)]
    params.extend('%s=%r' % (name, value) for name, value in sorted(kw.items()))
    params = ', '.join(params)
    fp.write('    >>> print app.%s(%s)\n' % (req.method.lower(), params))
    for line in str(resp).splitlines():
        if not line:
            fp.write('    <BLANKLINE>\n')
        else:
            fp.write('    %s\n' % line)

parser = optparse.OptionParser(
    usage='%prog < recorded_file > doctest')

def main():
    options, args = parser.parse_args()
    records = get_records(sys.stdin)
    write_doctest(records, sys.stdout)

if __name__ == '__main__':
    main()
