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
from HTMLParser import HTMLParseError
import unittest

from genshi.builder import Element, tag
from genshi.core import Attrs, Stream
from genshi.input import XML


class ElementFactoryTestCase(unittest.TestCase):

    def test_link(self):
        link = tag.a(href='#', title='Foo', accesskey=None)('Bar')
        bits = iter(link.generate())
        self.assertEqual((Stream.START,
                          ('a', Attrs([('href', "#"), ('title', "Foo")])),
                          (None, -1, -1)), bits.next())
        self.assertEqual((Stream.TEXT, u'Bar', (None, -1, -1)), bits.next())
        self.assertEqual((Stream.END, 'a', (None, -1, -1)), bits.next())

    def test_nonstring_attributes(self):
        """
        Verify that if an attribute value is given as an int (or some other
        non-string type), it is coverted to a string when the stream is
        generated.
        """
        event = iter(tag.foo(id=3)).next()
        self.assertEqual((Stream.START, ('foo', Attrs([('id', '3')])),
                          (None, -1, -1)),
                         event)

    def test_stream_as_child(self):
        xml = list(tag.span(XML('<b>Foo</b>')).generate())
        self.assertEqual(5, len(xml))
        self.assertEqual((Stream.START, ('span', ()), (None, -1, -1)), xml[0])
        self.assertEqual((Stream.START, ('b', ()), (None, 1, 0)), xml[1])
        self.assertEqual((Stream.TEXT, 'Foo', (None, 1, 3)), xml[2])
        self.assertEqual((Stream.END, 'b', (None, 1, 6)), xml[3])
        self.assertEqual((Stream.END, 'span', (None, -1, -1)), xml[4])


def suite():
    suite = unittest.TestSuite()
    suite.addTest(doctest.DocTestSuite(Element.__module__))
    suite.addTest(unittest.makeSuite(ElementFactoryTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
