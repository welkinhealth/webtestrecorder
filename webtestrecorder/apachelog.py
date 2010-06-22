import re
from datetime import datetime
from webob import Request, Response

apache_regex = re.compile(
    r'''
    (?P<remote_host>[^\s]+) \s+
    (?P<remote_ident>[^\s]+) \s+
    (?P<remote_user>[^\s]+) \s+
    \[ (?P<date>[^\]]*) \] \s+
    " (?P<method>[A-Z]+) \s+
      (?P<path>[^\s]+) \s+
      (?P<http_version>[^"]+) " \s+
    (?P<status>\d+) \s+
    (?P<size>\d+) \s+
    " (?P<referrer>[^"]+) " \s+
    " (?P<user_agent>[^"]+) "
    ''',
    re.VERBOSE)

def parse_apache_log(fp, host='localhost',
                     RequestClass=Request, ResponseClass=Response):
    for line in fp:
        line = line.strip()
        if not line:
            continue
        match = apache_regex.match(line)
        if not match:
            continue
        d = match.groupdict()
        for key in d:
            if d[key] == '-':
                d[key] = None
        req = RequestClass.blank(
            d['path'],
            host=host,
            method=d['method'],
            referrer=d['referrer'],
            user_agent=d['user_agent'],
            )
        req.date = parse_apache_date(d['date'])
        if d['remote_user']:
            req.environ['REMOTE_USER'] = d['remote_user']
        if d['remote_host']:
            req.environ['REMOTE_HOST'] = d['remote_host']
        req.environ['HTTP_PROTOCOL'] = d['http_version']
        resp = ResponseClass('\0' * int(d['size'] or 0),
                             status=d['status'])
        req.response = resp
        yield req


def parse_apache_date(date):
    return datetime.strptime(date.split()[0], '%d/%b/%Y:%H:%M:%S')
