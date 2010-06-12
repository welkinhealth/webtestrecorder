from cStringIO import StringIO
from webtest import TestApp
from webob.dec import wsgify
from webtestrecorder import recorder, get_records, write_doctest

@wsgify
def demo_application(req):
    return 'test response'

def test_recorder():
    out = StringIO()
    app = TestApp(recorder(demo_application, file=out))
    app.get('/test')
    app.post('/example', {'var': 'value'})
    data = out.getvalue()
    records = get_records(StringIO(data))
    result = StringIO()
    write_doctest(records, result)
    dt = result.getvalue()
    assert dt == doctest_example

doctest_example = """\
    >>> print app.get('/test', content_type='')
    Response: 200 OK
    <BLANKLINE>
    Content-Type: text/html; charset=UTF-8
    test response
    >>> print app.post('/example', params={'var': u'value'})
    Response: 200 OK
    <BLANKLINE>
    Content-Type: text/html; charset=UTF-8
    test response
"""
