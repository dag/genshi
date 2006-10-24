# -*- coding: utf-8 -*-
#
# Copyright (C) 2006 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://genshi.edgewall.org/wiki/License.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://genshi.edgewall.org/log/.

import doctest
import unittest
import sys

from genshi.core import Stream
from genshi.input import HTML, XML
from genshi.output import DocType, XMLSerializer, XHTMLSerializer, \
                          HTMLSerializer, EmptyTagFilter


class XMLSerializerTestCase(unittest.TestCase):

    def test_doctype_in_stream(self):
        stream = Stream([(Stream.DOCTYPE, DocType.HTML_STRICT, ('?', -1, -1))])
        output = stream.render(XMLSerializer)
        self.assertEqual('<!DOCTYPE html PUBLIC '
                         '"-//W3C//DTD HTML 4.01//EN" '
                         '"http://www.w3.org/TR/html4/strict.dtd">\n',
                         output)

    def test_doctype_in_stream_no_sysid(self):
        stream = Stream([(Stream.DOCTYPE,
                         ('html', '-//W3C//DTD HTML 4.01//EN', None),
                         ('?', -1, -1))])
        output = stream.render(XMLSerializer)
        self.assertEqual('<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN">\n',
                         output)

    def test_doctype_in_stream_no_pubid(self):
        stream = Stream([(Stream.DOCTYPE,
                         ('html', None, 'http://www.w3.org/TR/html4/strict.dtd'),
                         ('?', -1, -1))])
        output = stream.render(XMLSerializer)
        self.assertEqual('<!DOCTYPE html SYSTEM '
                         '"http://www.w3.org/TR/html4/strict.dtd">\n',
                         output)

    def test_doctype_in_stream_no_pubid_or_sysid(self):
        stream = Stream([(Stream.DOCTYPE, ('html', None, None),
                         ('?', -1, -1))])
        output = stream.render(XMLSerializer)
        self.assertEqual('<!DOCTYPE html>\n', output)

    def test_serializer_doctype(self):
        stream = Stream([])
        output = stream.render(XMLSerializer, doctype=DocType.HTML_STRICT)
        self.assertEqual('<!DOCTYPE html PUBLIC '
                         '"-//W3C//DTD HTML 4.01//EN" '
                         '"http://www.w3.org/TR/html4/strict.dtd">\n',
                         output)

    def test_doctype_one_and_only(self):
        stream = Stream([(Stream.DOCTYPE, ('html', None, None), ('?', -1, -1))])
        output = stream.render(XMLSerializer, doctype=DocType.HTML_STRICT)
        self.assertEqual('<!DOCTYPE html PUBLIC '
                         '"-//W3C//DTD HTML 4.01//EN" '
                         '"http://www.w3.org/TR/html4/strict.dtd">\n',
                         output)

    def test_comment(self):
        stream = Stream([(Stream.COMMENT, 'foo bar', ('?', -1, -1))])
        output = stream.render(XMLSerializer)
        self.assertEqual('<!--foo bar-->', output)

    def test_processing_instruction(self):
        stream = Stream([(Stream.PI, ('python', 'x = 2'), ('?', -1, -1))])
        output = stream.render(XMLSerializer)
        self.assertEqual('<?python x = 2?>', output)

    def test_nested_default_namespaces(self):
        xml = XML("""<div xmlns="http://www.w3.org/1999/xhtml">
          <p xmlns="http://www.w3.org/1999/xhtml" />
        </div>""")
        output = xml.render(XMLSerializer)
        self.assertEqual("""<div xmlns="http://www.w3.org/1999/xhtml">
          <p/>
        </div>""", output)

    def test_nested_bound_namespaces(self):
        xml = XML("""<div xmlns:x="http://example.org/">
          <p xmlns:x="http://example.org/" />
        </div>""")
        output = xml.render(XMLSerializer)
        self.assertEqual("""<div xmlns:x="http://example.org/">
          <p/>
        </div>""", output)


class XHTMLSerializerTestCase(unittest.TestCase):

    def test_textarea_whitespace(self):
        content = '\nHey there.  \n\n    I am indented.\n'
        stream = XML('<textarea name="foo">%s</textarea>' % content)
        output = stream.render(XHTMLSerializer)
        self.assertEqual('<textarea name="foo">%s</textarea>' % content, output)

    def test_xml_space(self):
        text = '<foo xml:space="preserve"> Do not mess  \n\n with me </foo>'
        output = XML(text).render(XHTMLSerializer)
        self.assertEqual(text, output)

    def test_empty_script(self):
        text = """<html xmlns="http://www.w3.org/1999/xhtml">
            <script src="foo.js" />
        </html>"""
        output = XML(text).render(XHTMLSerializer)
        self.assertEqual("""<html xmlns="http://www.w3.org/1999/xhtml">
            <script src="foo.js"></script>
        </html>""", output)

    def test_script_escaping(self):
        text = """<script>/*<![CDATA[*/
            if (1 < 2) { alert("Doh"); }
        /*]]>*/</script>"""
        output = XML(text).render(XHTMLSerializer)
        self.assertEqual(text, output)

    def test_script_escaping_with_namespace(self):
        text = """<script xmlns="http://www.w3.org/1999/xhtml">/*<![CDATA[*/
            if (1 < 2) { alert("Doh"); }
        /*]]>*/</script>"""
        output = XML(text).render(XHTMLSerializer)
        self.assertEqual(text, output)

    def test_style_escaping(self):
        text = """<style>/*<![CDATA[*/
            html > body { display: none; }
        /*]]>*/</style>"""
        output = XML(text).render(XHTMLSerializer)
        self.assertEqual(text, output)

    def test_style_escaping_with_namespace(self):
        text = """<style xmlns="http://www.w3.org/1999/xhtml">/*<![CDATA[*/
            html > body { display: none; }
        /*]]>*/</style>"""
        output = XML(text).render(XHTMLSerializer)
        self.assertEqual(text, output)

    def test_embedded_svg(self):
        text = """<html xmlns="http://www.w3.org/1999/xhtml" xmlns:svg="http://www.w3.org/2000/svg">
          <body>
            <button>
              <svg:svg width="600px" height="400px">
                <svg:polygon id="triangle" points="50,50 50,300 300,300" />
              </svg:svg>
            </button>
          </body>
        </html>"""
        output = XML(text).render(XHTMLSerializer)
        self.assertEqual(text, output)

    def test_xhtml_namespace_prefix(self):
        text = """<html:div xmlns:html="http://www.w3.org/1999/xhtml">
            <html:strong>Hello</html:strong>
        </html:div>"""
        output = XML(text).render(XHTMLSerializer)
        self.assertEqual(text, output)

    def test_nested_default_namespaces(self):
        xml = XML("""<div xmlns="http://www.w3.org/1999/xhtml">
          <p xmlns="http://www.w3.org/1999/xhtml" />
        </div>""")
        output = xml.render(XHTMLSerializer)
        self.assertEqual("""<div xmlns="http://www.w3.org/1999/xhtml">
          <p></p>
        </div>""", output)

    def test_nested_bound_namespaces(self):
        xml = XML("""<div xmlns:x="http://example.org/">
          <x:p xmlns:x="http://example.org/" />
        </div>""")
        output = xml.render(XHTMLSerializer)
        self.assertEqual("""<div xmlns:x="http://example.org/">
          <x:p />
        </div>""", output)


class HTMLSerializerTestCase(unittest.TestCase):

    def test_xml_space(self):
        text = '<foo xml:space="preserve"> Do not mess  \n\n with me </foo>'
        output = XML(text).render(HTMLSerializer)
        self.assertEqual('<foo> Do not mess  \n\n with me </foo>', output)

    def test_empty_script(self):
        text = '<script src="foo.js" />'
        output = XML(text).render(XHTMLSerializer)
        self.assertEqual('<script src="foo.js"></script>', output)

    def test_script_escaping(self):
        text = '<script>if (1 &lt; 2) { alert("Doh"); }</script>'
        output = XML(text).render(HTMLSerializer)
        self.assertEqual('<script>if (1 < 2) { alert("Doh"); }</script>',
                         output)

    def test_script_escaping_with_namespace(self):
        text = """<script xmlns="http://www.w3.org/1999/xhtml">
            if (1 &lt; 2) { alert("Doh"); }
        </script>"""
        output = XML(text).render(HTMLSerializer)
        self.assertEqual("""<script>
            if (1 < 2) { alert("Doh"); }
        </script>""", output)

    def test_style_escaping(self):
        text = '<style>html &gt; body { display: none; }</style>'
        output = XML(text).render(HTMLSerializer)
        self.assertEqual('<style>html > body { display: none; }</style>',
                         output)

    def test_style_escaping_with_namespace(self):
        text = """<style xmlns="http://www.w3.org/1999/xhtml">
            html &gt; body { display: none; }
        </style>"""
        output = XML(text).render(HTMLSerializer)
        self.assertEqual("""<style>
            html > body { display: none; }
        </style>""", output)


class EmptyTagFilterTestCase(unittest.TestCase):

    def test_empty(self):
        stream = XML('<elem></elem>') | EmptyTagFilter()
        self.assertEqual([EmptyTagFilter.EMPTY], [ev[0] for ev in stream])

    def test_text_content(self):
        stream = XML('<elem>foo</elem>') | EmptyTagFilter()
        self.assertEqual([Stream.START, Stream.TEXT, Stream.END],
                         [ev[0] for ev in stream])

    def test_elem_content(self):
        stream = XML('<elem><sub /><sub /></elem>') | EmptyTagFilter()
        self.assertEqual([Stream.START, EmptyTagFilter.EMPTY,
                          EmptyTagFilter.EMPTY, Stream.END],
                         [ev[0] for ev in stream])


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(XMLSerializerTestCase, 'test'))
    suite.addTest(unittest.makeSuite(XHTMLSerializerTestCase, 'test'))
    suite.addTest(unittest.makeSuite(HTMLSerializerTestCase, 'test'))
    suite.addTest(unittest.makeSuite(EmptyTagFilterTestCase, 'test'))
    suite.addTest(doctest.DocTestSuite(XMLSerializer.__module__))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
