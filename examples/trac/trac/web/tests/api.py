# -*- coding: utf-8 -*-

from trac.test import Mock
from trac.web.api import Request, RequestDone
from trac.web.clearsilver import HDFWrapper

from Cookie import SimpleCookie as Cookie
from StringIO import StringIO
import unittest


class RequestTestCase(unittest.TestCase):

    def _make_environ(self, scheme='http', server_name='example.org',
                      server_port=80, method='GET', script_name='/trac',
                      **kwargs):
        environ = {'wsgi.url_scheme': scheme, 'wsgi.input': StringIO(''),
                   'REQUEST_METHOD': method, 'SERVER_NAME': server_name,
                   'SERVER_PORT': server_port, 'SCRIPT_NAME': script_name}
        environ.update(kwargs)
        return environ

    def test_base_url(self):
        environ = self._make_environ()
        req = Request(environ, None)
        self.assertEqual('http://example.org/trac', req.base_url)

    def test_base_url_host(self):
        environ = self._make_environ(server_port=8080, HTTP_HOST='example.com')
        req = Request(environ, None)
        self.assertEqual('http://example.com/trac', req.base_url)

    def test_base_url_nondefaultport(self):
        environ = self._make_environ(server_port=8080)
        req = Request(environ, None)
        self.assertEqual('http://example.org:8080/trac', req.base_url)

    def test_base_url_https(self):
        environ = self._make_environ(scheme='https', server_port=443)
        req = Request(environ, None)
        self.assertEqual('https://example.org/trac', req.base_url)

    def test_base_url_https_host(self):
        environ = self._make_environ(scheme='https', server_port=443,
                                     HTTP_HOST='example.com')
        req = Request(environ, None)
        self.assertEqual('https://example.com/trac', req.base_url)

    def test_base_url_https_nondefaultport(self):
        environ = self._make_environ(scheme='https', server_port=8443)
        req = Request(environ, None)
        self.assertEqual('https://example.org:8443/trac', req.base_url)

    def test_base_url_proxy(self):
        environ = self._make_environ(HTTP_HOST='localhost',
                                     HTTP_X_FORWARDED_HOST='example.com')
        req = Request(environ, None)
        self.assertEqual('http://localhost/trac', req.base_url)

    def test_redirect(self):
        status_sent = []
        headers_sent = {}
        def start_response(status, headers):
            status_sent.append(status)
            headers_sent.update(dict(headers))
        environ = self._make_environ(method='HEAD')
        req = Request(environ, start_response)
        self.assertRaises(RequestDone, req.redirect, '/trac/test')
        self.assertEqual('302 Found', status_sent[0])
        self.assertEqual('http://example.org/trac/test',
                         headers_sent['Location'])

    def test_redirect_absolute(self):
        status_sent = []
        headers_sent = {}
        def start_response(status, headers):
            status_sent.append(status)
            headers_sent.update(dict(headers))
        environ = self._make_environ(method='HEAD')
        req = Request(environ, start_response)
        self.assertRaises(RequestDone, req.redirect,
                          'http://example.com/trac/test')
        self.assertEqual('302 Found', status_sent[0])
        self.assertEqual('http://example.com/trac/test',
                         headers_sent['Location'])

    def test_write_unicode(self):
        buf = StringIO()
        def write(data):
            buf.write(data)
        def start_response(status, headers):
            return write
        environ = self._make_environ(method='HEAD')
        req = Request(environ, start_response)
        req.send_header('Content-Type', 'text/plain;charset=utf-8')
        req.write(u'Föö')
        self.assertEqual('Föö', buf.getvalue())


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(RequestTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main()
