# -*- coding: utf-8 -*-
#
# Copyright (C) 2006-2007 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://genshi.edgewall.org/wiki/License.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://genshi.edgewall.org/log/.

"""This module provides different kinds of serialization methods for XML event
streams.
"""

from itertools import chain
try:
    frozenset
except NameError:
    from sets import ImmutableSet as frozenset
import re

from genshi.core import escape, Attrs, Markup, Namespace, QName, StreamEventKind
from genshi.core import DOCTYPE, START, END, START_NS, END_NS, TEXT, \
                        START_CDATA, END_CDATA, PI, COMMENT, XML_NAMESPACE

__all__ = ['DocType', 'XMLSerializer', 'XHTMLSerializer', 'HTMLSerializer',
           'TextSerializer']


class DocType(object):
    """Defines a number of commonly used DOCTYPE declarations as constants."""

    HTML_STRICT = (
        'html', '-//W3C//DTD HTML 4.01//EN',
        'http://www.w3.org/TR/html4/strict.dtd'
    )
    HTML_TRANSITIONAL = (
        'html', '-//W3C//DTD HTML 4.01 Transitional//EN',
        'http://www.w3.org/TR/html4/loose.dtd'
    )
    HTML = HTML_STRICT

    XHTML_STRICT = (
        'html', '-//W3C//DTD XHTML 1.0 Strict//EN',
        'http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd'
    )
    XHTML_TRANSITIONAL = (
        'html', '-//W3C//DTD XHTML 1.0 Transitional//EN',
        'http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd'
    )
    XHTML = XHTML_STRICT


class XMLSerializer(object):
    """Produces XML text from an event stream.
    
    >>> from genshi.builder import tag
    >>> elem = tag.div(tag.a(href='foo'), tag.br, tag.hr(noshade=True))
    >>> print ''.join(XMLSerializer()(elem.generate()))
    <div><a href="foo"/><br/><hr noshade="True"/></div>
    """

    _PRESERVE_SPACE = frozenset()

    def __init__(self, doctype=None, strip_whitespace=True,
                 namespace_prefixes=None):
        """Initialize the XML serializer.
        
        @param doctype: a `(name, pubid, sysid)` tuple that represents the
            DOCTYPE declaration that should be included at the top of the
            generated output
        @param strip_whitespace: whether extraneous whitespace should be
            stripped from the output
        """
        self.preamble = []
        if doctype:
            self.preamble.append((DOCTYPE, doctype, (None, -1, -1)))
        self.filters = [EmptyTagFilter()]
        if strip_whitespace:
            self.filters.append(WhitespaceFilter(self._PRESERVE_SPACE))
        self.filters.append(NamespaceFlattener(prefixes=namespace_prefixes))

    def __call__(self, stream):
        have_doctype = False
        in_cdata = False

        stream = chain(self.preamble, stream)
        for filter_ in self.filters:
            stream = filter_(stream)
        for kind, data, pos in stream:

            if kind is START or kind is EMPTY:
                tag, attrib = data
                buf = ['<', tag]
                for attr, value in attrib:
                    buf += [' ', attr, '="', escape(value), '"']
                buf.append(kind is EMPTY and '/>' or '>')
                yield Markup(u''.join(buf))

            elif kind is END:
                yield Markup('</%s>' % data)

            elif kind is TEXT:
                if in_cdata:
                    yield data
                else:
                    yield escape(data, quotes=False)

            elif kind is COMMENT:
                yield Markup('<!--%s-->' % data)

            elif kind is DOCTYPE and not have_doctype:
                name, pubid, sysid = data
                buf = ['<!DOCTYPE %s']
                if pubid:
                    buf.append(' PUBLIC "%s"')
                elif sysid:
                    buf.append(' SYSTEM')
                if sysid:
                    buf.append(' "%s"')
                buf.append('>\n')
                yield Markup(u''.join(buf), *filter(None, data))
                have_doctype = True

            elif kind is START_CDATA:
                yield Markup('<![CDATA[')
                in_cdata = True

            elif kind is END_CDATA:
                yield Markup(']]>')
                in_cdata = False

            elif kind is PI:
                yield Markup('<?%s %s?>' % data)


class XHTMLSerializer(XMLSerializer):
    """Produces XHTML text from an event stream.
    
    >>> from genshi.builder import tag
    >>> elem = tag.div(tag.a(href='foo'), tag.br, tag.hr(noshade=True))
    >>> print ''.join(XHTMLSerializer()(elem.generate()))
    <div><a href="foo"></a><br /><hr noshade="noshade" /></div>
    """

    _EMPTY_ELEMS = frozenset(['area', 'base', 'basefont', 'br', 'col', 'frame',
                              'hr', 'img', 'input', 'isindex', 'link', 'meta',
                              'param'])
    _BOOLEAN_ATTRS = frozenset(['selected', 'checked', 'compact', 'declare',
                                'defer', 'disabled', 'ismap', 'multiple',
                                'nohref', 'noresize', 'noshade', 'nowrap'])
    _PRESERVE_SPACE = frozenset([
        QName('pre'), QName('http://www.w3.org/1999/xhtml}pre'),
        QName('textarea'), QName('http://www.w3.org/1999/xhtml}textarea')
    ])

    def __init__(self, doctype=None, strip_whitespace=True,
                 namespace_prefixes=None):
        super(XHTMLSerializer, self).__init__(doctype, False)
        self.filters = [EmptyTagFilter()]
        if strip_whitespace:
            self.filters.append(WhitespaceFilter(self._PRESERVE_SPACE))
        namespace_prefixes = namespace_prefixes or {}
        namespace_prefixes['http://www.w3.org/1999/xhtml'] = ''
        self.filters.append(NamespaceFlattener(prefixes=namespace_prefixes))

    def __call__(self, stream):
        boolean_attrs = self._BOOLEAN_ATTRS
        empty_elems = self._EMPTY_ELEMS
        have_doctype = False
        in_cdata = False

        stream = chain(self.preamble, stream)
        for filter_ in self.filters:
            stream = filter_(stream)
        for kind, data, pos in stream:

            if kind is START or kind is EMPTY:
                tag, attrib = data
                buf = ['<', tag]
                for attr, value in attrib:
                    if attr in boolean_attrs:
                        value = attr
                    buf += [' ', attr, '="', escape(value), '"']
                if kind is EMPTY:
                    if tag in empty_elems:
                        buf.append(' />')
                    else:
                        buf.append('></%s>' % tag)
                else:
                    buf.append('>')
                yield Markup(u''.join(buf))

            elif kind is END:
                yield Markup('</%s>' % data)

            elif kind is TEXT:
                if in_cdata:
                    yield data
                else:
                    yield escape(data, quotes=False)

            elif kind is COMMENT:
                yield Markup('<!--%s-->' % data)

            elif kind is DOCTYPE and not have_doctype:
                name, pubid, sysid = data
                buf = ['<!DOCTYPE %s']
                if pubid:
                    buf.append(' PUBLIC "%s"')
                elif sysid:
                    buf.append(' SYSTEM')
                if sysid:
                    buf.append(' "%s"')
                buf.append('>\n')
                yield Markup(u''.join(buf), *filter(None, data))
                have_doctype = True

            elif kind is START_CDATA:
                yield Markup('<![CDATA[')
                in_cdata = True

            elif kind is END_CDATA:
                yield Markup(']]>')
                in_cdata = False

            elif kind is PI:
                yield Markup('<?%s %s?>' % data)


class HTMLSerializer(XHTMLSerializer):
    """Produces HTML text from an event stream.
    
    >>> from genshi.builder import tag
    >>> elem = tag.div(tag.a(href='foo'), tag.br, tag.hr(noshade=True))
    >>> print ''.join(HTMLSerializer()(elem.generate()))
    <div><a href="foo"></a><br><hr noshade></div>
    """

    _NOESCAPE_ELEMS = frozenset([
        QName('script'), QName('http://www.w3.org/1999/xhtml}script'),
        QName('style'), QName('http://www.w3.org/1999/xhtml}style')
    ])

    def __init__(self, doctype=None, strip_whitespace=True):
        """Initialize the HTML serializer.
        
        @param doctype: a `(name, pubid, sysid)` tuple that represents the
            DOCTYPE declaration that should be included at the top of the
            generated output
        @param strip_whitespace: whether extraneous whitespace should be
            stripped from the output
        """
        super(HTMLSerializer, self).__init__(doctype, False)
        self.filters = [EmptyTagFilter()]
        if strip_whitespace:
            self.filters.append(WhitespaceFilter(self._PRESERVE_SPACE,
                                                 self._NOESCAPE_ELEMS))
        self.filters.append(NamespaceStripper('http://www.w3.org/1999/xhtml'))

    def __call__(self, stream):
        boolean_attrs = self._BOOLEAN_ATTRS
        empty_elems = self._EMPTY_ELEMS
        noescape_elems = self._NOESCAPE_ELEMS
        have_doctype = False
        noescape = False

        stream = chain(self.preamble, stream)
        for filter_ in self.filters:
            stream = filter_(stream)
        for kind, data, pos in stream:

            if kind is START or kind is EMPTY:
                tag, attrib = data
                buf = ['<', tag]
                for attr, value in attrib:
                    if attr in boolean_attrs:
                        if value:
                            buf += [' ', attr]
                    else:
                        buf += [' ', attr, '="', escape(value), '"']
                buf.append('>')
                if kind is EMPTY:
                    if tag not in empty_elems:
                        buf.append('</%s>' % tag)
                yield Markup(u''.join(buf))
                if tag in noescape_elems:
                    noescape = True

            elif kind is END:
                yield Markup('</%s>' % data)
                noescape = False

            elif kind is TEXT:
                if noescape:
                    yield data
                else:
                    yield escape(data, quotes=False)

            elif kind is COMMENT:
                yield Markup('<!--%s-->' % data)

            elif kind is DOCTYPE and not have_doctype:
                name, pubid, sysid = data
                buf = ['<!DOCTYPE %s']
                if pubid:
                    buf.append(' PUBLIC "%s"')
                elif sysid:
                    buf.append(' SYSTEM')
                if sysid:
                    buf.append(' "%s"')
                buf.append('>\n')
                yield Markup(u''.join(buf), *filter(None, data))
                have_doctype = True

            elif kind is PI:
                yield Markup('<?%s %s?>' % data)


class TextSerializer(object):
    """Produces plain text from an event stream.
    
    Only text events are included in the output. Unlike the other serializer,
    special XML characters are not escaped:
    
    >>> from genshi.builder import tag
    >>> elem = tag.div(tag.a('<Hello!>', href='foo'), tag.br)
    >>> print elem
    <div><a href="foo">&lt;Hello!&gt;</a><br/></div>
    >>> print ''.join(TextSerializer()(elem.generate()))
    <Hello!>

    If text events contain literal markup (instances of the `Markup` class),
    tags or entities are stripped from the output:
    
    >>> elem = tag.div(Markup('<a href="foo">Hello!</a><br/>'))
    >>> print elem
    <div><a href="foo">Hello!</a><br/></div>
    >>> print ''.join(TextSerializer()(elem.generate()))
    Hello!
    """

    def __call__(self, stream):
        for event in stream:
            if event[0] is TEXT:
                data = event[1]
                if type(data) is Markup:
                    data = data.striptags().stripentities()
                yield unicode(data)


class EmptyTagFilter(object):
    """Combines `START` and `STOP` events into `EMPTY` events for elements that
    have no contents.
    """

    EMPTY = StreamEventKind('EMPTY')

    def __call__(self, stream):
        prev = (None, None, None)
        for ev in stream:
            if prev[0] is START:
                if ev[0] is END:
                    prev = EMPTY, prev[1], prev[2]
                    yield prev
                    continue
                else:
                    yield prev
            if ev[0] is not START:
                yield ev
            prev = ev


EMPTY = EmptyTagFilter.EMPTY


class NamespaceFlattener(object):
    r"""Output stream filter that removes namespace information from the stream,
    instead adding namespace attributes and prefixes as needed.
    
    @param prefixes: optional mapping of namespace URIs to prefixes
    
    >>> from genshi.input import XML
    >>> xml = XML('''<doc xmlns="NS1" xmlns:two="NS2">
    ...   <two:item/>
    ... </doc>''')
    >>> for kind, data, pos in NamespaceFlattener()(xml):
    ...     print kind, repr(data)
    START (u'doc', Attrs([(u'xmlns', u'NS1'), (u'xmlns:two', u'NS2')]))
    TEXT u'\n  '
    START (u'two:item', Attrs())
    END u'two:item'
    TEXT u'\n'
    END u'doc'
    """

    def __init__(self, prefixes=None):
        self.prefixes = {XML_NAMESPACE.uri: 'xml'}
        if prefixes is not None:
            self.prefixes.update(prefixes)

    def __call__(self, stream):
        prefixes = dict([(v, [k]) for k, v in self.prefixes.items()])
        namespaces = {XML_NAMESPACE.uri: ['xml']}
        def _push_ns(prefix, uri):
            namespaces.setdefault(uri, []).append(prefix)
            prefixes.setdefault(prefix, []).append(uri)

        ns_attrs = []
        _push_ns_attr = ns_attrs.append

        def _gen_prefix():
            val = 0
            while 1:
                val += 1
                yield 'ns%d' % val
        _gen_prefix = _gen_prefix().next

        for kind, data, pos in stream:

            if kind is START or kind is EMPTY:
                tag, attrs = data

                tagname = tag.localname
                tagns = tag.namespace
                if tagns:
                    if tagns in namespaces:
                        prefix = namespaces[tagns][-1]
                        if prefix:
                            tagname = u'%s:%s' % (prefix, tagname)
                    else:
                        _push_ns_attr((u'xmlns', tagns))
                        _push_ns('', tagns)

                new_attrs = []
                for attr, value in attrs:
                    attrname = attr.localname
                    attrns = attr.namespace
                    if attrns:
                        if attrns not in namespaces:
                            prefix = _gen_prefix()
                            _push_ns(prefix, attrns)
                        else:
                            prefix = namespaces[attrns][-1]
                        if prefix:
                            attrname = u'%s:%s' % (prefix, attrname)
                    new_attrs.append((attrname, value))

                yield kind, (tagname, Attrs(ns_attrs + new_attrs)), pos
                del ns_attrs[:]

            elif kind is END:
                tagname = data.localname
                tagns = data.namespace
                if tagns:
                    prefix = namespaces[tagns][-1]
                    if prefix:
                        tagname = u'%s:%s' % (prefix, tagname)
                yield kind, tagname, pos

            elif kind is START_NS:
                prefix, uri = data
                if uri not in namespaces:
                    prefix = prefixes.get(uri, [prefix])[-1]
                    if not prefix:
                        _push_ns_attr((u'xmlns', uri))
                    else:
                        _push_ns_attr((u'xmlns:%s' % prefix, uri))
                _push_ns(prefix, uri)

            elif kind is END_NS:
                if data in prefixes:
                    uris = prefixes.get(data)
                    uri = uris.pop()
                    if not uris:
                        del prefixes[data]
                    if uri not in uris or uri != uris[-1]:
                        uri_prefixes = namespaces[uri]
                        uri_prefixes.pop()
                        if not uri_prefixes:
                            del namespaces[uri]

            else:
                yield kind, data, pos


class NamespaceStripper(object):
    r"""Stream filter that removes all namespace information from a stream, and
    optionally strips out all tags not in a given namespace.
    
    @param namespace: the URI of the namespace that should not be stripped. If
        not set, only elements with no namespace are included in the output.
    
    >>> from genshi.input import XML
    >>> xml = XML('''<doc xmlns="NS1" xmlns:two="NS2">
    ...   <two:item/>
    ... </doc>''')
    >>> for kind, data, pos in NamespaceStripper(Namespace('NS1'))(xml):
    ...     print kind, repr(data)
    START (u'doc', Attrs())
    TEXT u'\n  '
    TEXT u'\n'
    END u'doc'
    """

    def __init__(self, namespace=None):
        if namespace is not None:
            self.namespace = Namespace(namespace)
        else:
            self.namespace = {}

    def __call__(self, stream):
        namespace = self.namespace

        for kind, data, pos in stream:

            if kind is START or kind is EMPTY:
                tag, attrs = data
                if tag.namespace and tag not in namespace:
                    continue

                new_attrs = []
                for attr, value in attrs:
                    if not attr.namespace or attr in namespace:
                        new_attrs.append((attr, value))

                data = tag.localname, Attrs(new_attrs)

            elif kind is END:
                if data.namespace and data not in namespace:
                    continue
                data = data.localname

            elif kind is START_NS or kind is END_NS:
                continue

            yield kind, data, pos


class WhitespaceFilter(object):
    """A filter that removes extraneous ignorable white space from the
    stream.
    """

    def __init__(self, preserve=None, noescape=None):
        """Initialize the filter.
        
        @param preserve: a set or sequence of tag names for which white-space
            should be preserved
        @param noescape: a set or sequence of tag names for which text content
            should not be escaped
        
        The `noescape` set is expected to refer to elements that cannot contain
        further child elements (such as <style> or <script> in HTML documents).
        """
        if preserve is None:
            preserve = []
        self.preserve = frozenset(preserve)
        if noescape is None:
            noescape = []
        self.noescape = frozenset(noescape)

    def __call__(self, stream, ctxt=None, space=XML_NAMESPACE['space'],
                 trim_trailing_space=re.compile('[ \t]+(?=\n)').sub,
                 collapse_lines=re.compile('\n{2,}').sub):
        mjoin = Markup('').join
        preserve_elems = self.preserve
        preserve = 0
        noescape_elems = self.noescape
        noescape = False

        textbuf = []
        push_text = textbuf.append
        pop_text = textbuf.pop
        for kind, data, pos in chain(stream, [(None, None, None)]):

            if kind is TEXT:
                if noescape:
                    data = Markup(data)
                push_text(data)
            else:
                if textbuf:
                    if len(textbuf) > 1:
                        text = mjoin(textbuf, escape_quotes=False)
                        del textbuf[:]
                    else:
                        text = escape(pop_text(), quotes=False)
                    if not preserve:
                        text = collapse_lines('\n', trim_trailing_space('', text))
                    yield TEXT, Markup(text), pos

                if kind is START:
                    tag, attrs = data
                    if preserve or (tag in preserve_elems or
                                    attrs.get(space) == 'preserve'):
                        preserve += 1
                    if not noescape and tag in noescape_elems:
                        noescape = True

                elif kind is END:
                    noescape = False
                    if preserve:
                        preserve -= 1

                elif kind is START_CDATA:
                    noescape = True

                elif kind is END_CDATA:
                    noescape = False

                if kind:
                    yield kind, data, pos
