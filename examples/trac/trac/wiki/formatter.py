# -*- coding: utf-8 -*-
#
# Copyright (C) 2003-2006 Edgewall Software
# Copyright (C) 2003-2005 Jonas Borgström <jonas@edgewall.com>
# Copyright (C) 2004-2005 Christopher Lenz <cmlenz@gmx.de>
# Copyright (C) 2005-2006 Christian Boos <cboos@neuf.fr>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://trac.edgewall.com/license.html.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://projects.edgewall.com/trac/.
#
# Author: Jonas Borgström <jonas@edgewall.com>
#         Christopher Lenz <cmlenz@gmx.de>
#         Christian Boos <cboos@neuf.fr>

import re
import os
import urllib

from StringIO import StringIO

from trac.core import *
from trac.mimeview import *
from trac.wiki.api import WikiSystem
from trac.util.text import shorten_line, to_unicode
from trac.util.markup import escape, Markup, Element, html

__all__ = ['wiki_to_html', 'wiki_to_oneliner', 'wiki_to_outline',
           'wiki_to_link', 'Formatter' ]


def system_message(msg, text=None):
    return html.DIV(html.STRONG(msg), text and html.PRE(text),
                    class_="system-message")


class WikiProcessor(object):

    _code_block_re = re.compile('^<div(?:\s+class="([^"]+)")?>(.*)</div>$')

    def __init__(self, env, name):
        # TODO: transmit `formatter` argument
        self.env = env
        self.name = name
        self.error = None
        self.macro_provider = None

        builtin_processors = {'html': self._html_processor,
                              'default': self._default_processor,
                              'comment': self._comment_processor}
        
        self.processor = builtin_processors.get(name)
        if not self.processor:
            # Find a matching wiki macro
            for macro_provider in WikiSystem(self.env).macro_providers:
                for macro_name in macro_provider.get_macros():
                    if self.name == macro_name:
                        self.processor = self._macro_processor
                        self.macro_provider = macro_provider
                        break
        if not self.processor:
            # Find a matching mimeview renderer
            from trac.mimeview.api import Mimeview
            mimetype = Mimeview(self.env).get_mimetype(self.name)
            if mimetype:
                self.name = mimetype
                self.processor = self._mimeview_processor
            else:
                self.processor = self._default_processor
                self.error = "No macro or processor named '%s' found" % name

    # builtin processors

    def _comment_processor(self, req, text):
        return ''

    def _default_processor(self, req, text):
        return html.PRE(text, class_="wiki")

    def _html_processor(self, req, text):
        from HTMLParser import HTMLParseError
        try:
            return Markup(text).sanitize()
        except HTMLParseError, e:
            self.env.log.warn(e)
            return system_message('HTML parsing error: %s' % escape(e.msg),
                                  text.splitlines()[e.lineno - 1].strip())

    # generic processors

    def _macro_processor(self, req, text):
        # TODO: macro should take a `formatter` argument
        self.env.log.debug('Executing Wiki macro %s by provider %s'
                           % (self.name, self.macro_provider))
        return self.macro_provider.render_macro(req, self.name, text)

    def _mimeview_processor(self, req, text):
        # TODO: transmit context from `formatter`
        return Mimeview(self.env).render(req, self.name, text)

    def process(self, req, text, in_paragraph=False):
        if self.error:
            text = system_message(Markup('Error: Failed to load processor '
                                         '<code>%s</code>', self.name),
                                  self.error)
        else:
            text = self.processor(req, text)
        if in_paragraph:
            content_for_span = None
            interrupt_paragraph = False
            if isinstance(text, Element):
                tagname = text.tagname.lower()
                if tagname == 'div':
                    class_ = text.attr.get('class_', '')
                    if class_ and 'code' in class_:
                        content_for_span = text.children
                    else:
                        interrupt_paragraph = True
                elif tagname == 'table':
                    interrupt_paragraph = True
            else:
                match = re.match(self._code_block_re, text)
                if match:
                    if match.group(1) and 'code' in match.group(1):
                        content_for_span = match.group(2)
                    else:
                        interrupt_paragraph = True
                elif text.startswith('<table'):
                    interrupt_paragraph = True
            if content_for_span:
                text = html.SPAN(content_for_span, class_='code-block')
            elif interrupt_paragraph:
                text = "</p>%s<p>" % to_unicode(text)
        return text


class Formatter(object):
    flavor = 'default'

    # Some constants used for clarifying the Wiki regexps:

    BOLDITALIC_TOKEN = "'''''"
    BOLD_TOKEN = "'''"
    ITALIC_TOKEN = "''"
    UNDERLINE_TOKEN = "__"
    STRIKE_TOKEN = "~~"
    SUBSCRIPT_TOKEN = ",,"
    SUPERSCRIPT_TOKEN = r"\^"
    INLINE_TOKEN = "`"
    STARTBLOCK_TOKEN = r"\{\{\{"
    STARTBLOCK = "{{{"
    ENDBLOCK_TOKEN = r"\}\}\}"
    ENDBLOCK = "}}}"
    
    LINK_SCHEME = r"[\w.+-]+" # as per RFC 2396
    INTERTRAC_SCHEME = r"[a-zA-Z.+-]*?" # no digits (support for shorthand links)

    QUOTED_STRING = r"'[^']+'|\"[^\"]+\""

    SHREF_TARGET_FIRST = r"[\w/?!#@]"
    SHREF_TARGET_MIDDLE = r"(?:\|(?=[^|\s])|[^|<>\s])"
    SHREF_TARGET_LAST = r"[a-zA-Z0-9/=]" # we don't want "_"

    LHREF_RELATIVE_TARGET = r"[/.][^\s[\]]*"

    # Sequence of regexps used by the engine

    _pre_rules = [
        # Font styles
        r"(?P<bolditalic>!?%s)" % BOLDITALIC_TOKEN,
        r"(?P<bold>!?%s)" % BOLD_TOKEN,
        r"(?P<italic>!?%s)" % ITALIC_TOKEN,
        r"(?P<underline>!?%s)" % UNDERLINE_TOKEN,
        r"(?P<strike>!?%s)" % STRIKE_TOKEN,
        r"(?P<subscript>!?%s)" % SUBSCRIPT_TOKEN,
        r"(?P<superscript>!?%s)" % SUPERSCRIPT_TOKEN,
        r"(?P<inlinecode>!?%s(?P<inline>.*?)%s)" \
        % (STARTBLOCK_TOKEN, ENDBLOCK_TOKEN),
        r"(?P<inlinecode2>!?%s(?P<inline2>.*?)%s)" \
        % (INLINE_TOKEN, INLINE_TOKEN)]

    # Rules provided by IWikiSyntaxProviders will be inserted here

    _post_rules = [
        # > ...
        r"(?P<citation>^(?P<cdepth>>(?: *>)*))",
        # &, < and > to &amp;, &lt; and &gt;
        r"(?P<htmlescape>[&<>])",
        # wiki:TracLinks
        r"(?P<shref>!?((?P<sns>%s):(?P<stgt>%s|%s(?:%s*%s)?)))" \
        % (LINK_SCHEME, QUOTED_STRING,
           SHREF_TARGET_FIRST, SHREF_TARGET_MIDDLE, SHREF_TARGET_LAST),
        # [[macro]] call
        (r"(?P<macro>!?\[\[(?P<macroname>[\w/+-]+)"
         r"(\]\]|\((?P<macroargs>.*?)\)\]\]))"),
        # [wiki:TracLinks with label]
        (r"(?P<lhref>!?\[(?:"
         r"(?P<rel>%s)|" % LHREF_RELATIVE_TARGET + # ./... or /...
         r"(?:(?P<lns>%s):)?(?P<ltgt>%s|[^\]\s]*))" % \
         (LINK_SCHEME, QUOTED_STRING) + # wiki:TracLinks or wiki:"trac links"
         r"(?:\s+(?P<label>%s|[^\]]+))?\])" % QUOTED_STRING), # label
        # == heading == #hanchor
        r"(?P<heading>^\s*(?P<hdepth>=+)\s.*\s(?P=hdepth)\s*"
        r"(?P<hanchor>#[\w:](?<!\d)[\w:.-]*)?$)",
        #  * list
        r"(?P<list>^(?P<ldepth>\s+)(?:[-*]|\d+\.|[a-zA-Z]\.|[ivxIVX]{1,5}\.) )",
        # definition:: 
        r"(?P<definition>^\s+((?:%s.*?%s|%s.*?%s|[^%s%s])+?::)(?:\s+|$))"
        % (INLINE_TOKEN, INLINE_TOKEN, STARTBLOCK_TOKEN, ENDBLOCK_TOKEN,
           INLINE_TOKEN, STARTBLOCK[0]),
        # (leading space)
        r"(?P<indent>^(?P<idepth>\s+)(?=\S))",
        # || table ||
        r"(?P<last_table_cell>\|\|\s*$)",
        r"(?P<table_cell>\|\|)"]

    _processor_re = re.compile('#\!([\w+-][\w+-/]*)')
    _anchor_re = re.compile('[^\w:.-]+', re.UNICODE)

    def __init__(self, env, req=None, absurls=False, db=None):
        self.env = env
        self.req = req
        self._db = db
        self._absurls = absurls
        self._anchors = {}
        self._open_tags = []
        self.href = absurls and (req or env).abs_href or (req or env).href
        self._local = env.config.get('project', 'url') \
                      or (req or env).abs_href.base
        self.wiki = WikiSystem(self.env)

    def _get_db(self):
        if not self._db:
            self._db = self.env.get_db_cnx()
        return self._db
    db = property(fget=_get_db)

    def split_link(self, target):
        """Split a target along "?" and "#" in `(path, query, fragment)`."""
        query = fragment = ''
        idx = target.find('#')
        if idx >= 0:
            target, fragment = target[:idx], target[idx:]
        idx = target.find('?')
        if idx >= 0:
            target, query = target[:idx], target[idx:]
        return (target, query, fragment)

    # -- Pre- IWikiSyntaxProvider rules (Font styles)
    
    def tag_open_p(self, tag):
        """Do we currently have any open tag with `tag` as end-tag?"""
        return tag in self._open_tags

    def close_tag(self, tag):
        tmp =  ''
        for i in xrange(len(self._open_tags)-1, -1, -1):
            tmp += self._open_tags[i][1]
            if self._open_tags[i][1] == tag:
                del self._open_tags[i]
                for j in xrange(i, len(self._open_tags)):
                    tmp += self._open_tags[j][0]
                break
        return tmp

    def open_tag(self, open, close):
        self._open_tags.append((open, close))

    def simple_tag_handler(self, match, open_tag, close_tag):
        """Generic handler for simple binary style tags"""
        if match[0] == '!':
            return match[1:]
        if self.tag_open_p((open_tag, close_tag)):
            return self.close_tag(close_tag)
        else:
            self.open_tag(open_tag, close_tag)
        return open_tag

    def _bolditalic_formatter(self, match, fullmatch):
        if match[0] == '!':
            return match[1:]
        italic = ('<i>', '</i>')
        italic_open = self.tag_open_p(italic)
        tmp = ''
        if italic_open:
            tmp += italic[1]
            self.close_tag(italic[1])
        tmp += self._bold_formatter(match, fullmatch)
        if not italic_open:
            tmp += italic[0]
            self.open_tag(*italic)
        return tmp

    def _bold_formatter(self, match, fullmatch):
        return self.simple_tag_handler(match, '<strong>', '</strong>')

    def _italic_formatter(self, match, fullmatch):
        return self.simple_tag_handler(match, '<i>', '</i>')

    def _underline_formatter(self, match, fullmatch):
        return self.simple_tag_handler(match, '<span class="underline">',
                                       '</span>')

    def _strike_formatter(self, match, fullmatch):
        return self.simple_tag_handler(match, '<del>', '</del>')

    def _subscript_formatter(self, match, fullmatch):
        return self.simple_tag_handler(match, '<sub>', '</sub>')

    def _superscript_formatter(self, match, fullmatch):
        return self.simple_tag_handler(match, '<sup>', '</sup>')

    def _inlinecode_formatter(self, match, fullmatch):
        return html.TT(fullmatch.group('inline'))

    def _inlinecode2_formatter(self, match, fullmatch):
        return html.TT(fullmatch.group('inline2'))

    # -- Post- IWikiSyntaxProvider rules

    # HTML escape of &, < and >

    def _htmlescape_formatter(self, match, fullmatch):
        return match == "&" and "&amp;" or match == "<" and "&lt;" or "&gt;"

    # Short form (shref) and long form (lhref) of TracLinks

    def _unquote(self, text):
        if text and text[0] in "'\"" and text[0] == text[-1]:
            return text[1:-1]
        else:
            return text

    def _shref_formatter(self, match, fullmatch):
        ns = fullmatch.group('sns')
        target = self._unquote(fullmatch.group('stgt'))
        return self._make_link(ns, target, match, match)

    def _lhref_formatter(self, match, fullmatch):
        rel = fullmatch.group('rel')
        ns = fullmatch.group('lns') or (not rel and 'wiki')
        target = self._unquote(fullmatch.group('ltgt'))
        label = fullmatch.group('label')
        if not label: # e.g. `[http://target]` or `[wiki:target]`
            if target:
                if target.startswith('//'): # for `[http://target]`
                    label = ns+':'+target   #  use `http://target`
                else:                       # for `wiki:target`
                    label = target          #  use only `target`
            else: # e.g. `[search:]` 
                label = ns
        else:
            label = self._unquote(label)
        if rel:
            return self._make_relative_link(rel, label or rel)
        else:
            return self._make_link(ns, target, match, label)

    def _make_link(self, ns, target, match, label):
        # first check for an alias defined in trac.ini
        ns = self.env.config.get('intertrac', ns) or ns
        if ns in self.wiki.link_resolvers:
            return self.wiki.link_resolvers[ns](self, ns, target,
                                                escape(label, False))
        elif target.startswith('//') or ns == "mailto":
            return self._make_ext_link(ns+':'+target, label)
        else:
            return self._make_intertrac_link(ns, target, label) or \
                   self._make_interwiki_link(ns, target, label) or \
                   match

    def _make_intertrac_link(self, ns, target, label):
        url = self.env.config.get('intertrac', ns + '.url')
        if url:
            name = self.env.config.get('intertrac', ns + '.title',
                                       'Trac project %s' % ns)
            sep = target.find(':')
            if sep != -1:
                url = '%s/%s/%s' % (url, target[:sep], target[sep + 1:])
            else: 
                url = '%s/search?q=%s' % (url, urllib.quote_plus(target))
            return self._make_ext_link(url, label, '%s in %s' % (target, name))
        else:
            return None

    def shorthand_intertrac_helper(self, ns, target, label, fullmatch):
        if fullmatch: # short form
            it_group = fullmatch.group('it_%s' % ns)
            if it_group:
                alias = it_group.strip()
                intertrac = self.env.config.get('intertrac', alias) or alias
                target = '%s:%s' % (ns, target[len(it_group):])
                return self._make_intertrac_link(intertrac, target, label) or \
                       label
        return None

    def _make_interwiki_link(self, ns, target, label):
        from trac.wiki.interwiki import InterWikiMap        
        interwiki = InterWikiMap(self.env)
        if ns in interwiki:
            url, title = interwiki.url(ns, target)
            return self._make_ext_link(url, label, title)
        else:
            return None

    def _make_ext_link(self, url, text, title=''):
        if not url.startswith(self._local):
            return html.A(html.SPAN(text, class_="icon"),
                          class_="ext-link", href=url, title=title or None)
        else:
            return html.A(text, href=url, title=title or None)

    def _make_relative_link(self, url, text):
        if url.startswith('//'): # only the protocol will be kept
            return html.A(text, class_="ext-link", href=url)
        else:
            return html.A(text, href=url)

    # WikiMacros
    
    def _macro_formatter(self, match, fullmatch):
        name = fullmatch.group('macroname')
        if name.lower() == 'br':
            return '<br />'
        args = fullmatch.group('macroargs')
        try:
            macro = WikiProcessor(self.env, name)
            return macro.process(self.req, args, True)
        except Exception, e:
            self.env.log.error('Macro %s(%s) failed' % (name, args),
                               exc_info=True)
            return system_message('Error: Macro %s(%s) failed' % (name, args),
                                  e)

    # Headings

    def _parse_heading(self, match, fullmatch, shorten):
        match = match.strip()

        depth = min(len(fullmatch.group('hdepth')), 5)
        anchor = fullmatch.group('hanchor') or ''
        heading = match[depth+1:-depth-1-len(anchor)]
        heading = wiki_to_oneliner(heading, self.env, self.db, shorten,
                                   self._absurls)
        if anchor:
            anchor = anchor[1:]
        else:
            sans_markup = heading.plaintext(keeplinebreaks=False)
            anchor = self._anchor_re.sub('', sans_markup)
            if not anchor or anchor[0].isdigit() or anchor[0] in '.-':
                # an ID must start with a Name-start character in XHTML
                anchor = 'a' + anchor # keeping 'a' for backward compat
        i = 1
        anchor_base = anchor
        while anchor in self._anchors:
            anchor = anchor_base + str(i)
            i += 1
        self._anchors[anchor] = True
        return (depth, heading, anchor)

    def _heading_formatter(self, match, fullmatch):
        self.close_table()
        self.close_paragraph()
        self.close_indentation()
        self.close_list()
        self.close_def_list()
        depth, heading, anchor = self._parse_heading(match, fullmatch, False)
        self.out.write('<h%d id="%s">%s</h%d>' %
                       (depth, anchor, heading, depth))

    # Generic indentation (as defined by lists and quotes)

    def _set_tab(self, depth):
        """Append a new tab if needed and truncate tabs deeper than `depth`

        given:       -*-----*--*---*--
        setting:              *
        results in:  -*-----*-*-------
        """
        tabstops = []
        for ts in self._tabstops:
            if ts >= depth:
                break
            tabstops.append(ts)
        tabstops.append(depth)
        self._tabstops = tabstops

    # Lists
    
    def _list_formatter(self, match, fullmatch):
        ldepth = len(fullmatch.group('ldepth'))
        listid = match[ldepth]
        self.in_list_item = True
        class_ = start = None
        if listid in '-*':
            type_ = 'ul'
        else:
            type_ = 'ol'
            idx = '01iI'.find(listid)
            if idx >= 0:
                class_ = ('arabiczero', None, 'lowerroman', 'upperroman')[idx]
            elif listid.isdigit():
                start = match[ldepth:match.find('.')]
            elif listid.islower():
                class_ = 'loweralpha'
            elif listid.isupper():
                class_ = 'upperalpha'
        self._set_list_depth(ldepth, type_, class_, start)
        return ''
        
    def _get_list_depth(self):
        """Return the space offset associated to the deepest opened list."""
        return self._list_stack and self._list_stack[-1][1] or 0

    def _set_list_depth(self, depth, new_type, list_class, start):
        def open_list():
            self.close_table()
            self.close_paragraph()
            self.close_indentation() # FIXME: why not lists in quotes?
            self._list_stack.append((new_type, depth))
            self._set_tab(depth)
            class_attr = list_class and ' class="%s"' % list_class or ''
            start_attr = start and ' start="%s"' % start or ''
            self.out.write('<'+new_type+class_attr+start_attr+'><li>')
        def close_list(tp):
            self._list_stack.pop()
            self.out.write('</li></%s>' % tp)

        # depending on the indent/dedent, open or close lists
        if depth > self._get_list_depth():
            open_list()
        else:
            while self._list_stack:
                deepest_type, deepest_offset = self._list_stack[-1]
                if depth >= deepest_offset:
                    break
                close_list(deepest_type)
            if depth > 0:
                if self._list_stack:
                    old_type, old_offset = self._list_stack[-1]
                    if new_type and old_type != new_type:
                        close_list(old_type)
                        open_list()
                    else:
                        if old_offset != depth: # adjust last depth
                            self._list_stack[-1] = (old_type, depth)
                        self.out.write('</li><li>')
                else:
                    open_list()

    def close_list(self):
        self._set_list_depth(0, None, None, None)

    # Definition Lists

    def _definition_formatter(self, match, fullmatch):
        tmp = self.in_def_list and '</dd>' or '<dl>'
        definition = match[:match.find('::')]
        tmp += '<dt>%s</dt><dd>' % wiki_to_oneliner(definition, self.env,
                                                    self.db)
        self.in_def_list = True
        return tmp

    def close_def_list(self):
        if self.in_def_list:
            self.out.write('</dd></dl>\n')
        self.in_def_list = False

    # Blockquote

    def _indent_formatter(self, match, fullmatch):
        idepth = len(fullmatch.group('idepth'))
        if self._list_stack:
            ltype, ldepth = self._list_stack[-1]
            if idepth < ldepth:
                for _, ldepth in self._list_stack:
                    if idepth > ldepth:
                        self.in_list_item = True
                        self._set_list_depth(idepth, None, None, None)
                        return ''
            elif idepth <= ldepth + (ltype == 'ol' and 3 or 2):
                self.in_list_item = True
                return ''
        if not self.in_def_list:
            self._set_quote_depth(idepth)
        return ''

    def _citation_formatter(self, match, fullmatch):
        cdepth = len(fullmatch.group('cdepth').replace(' ', ''))
        self._set_quote_depth(cdepth, True)
        return ''

    def close_indentation(self):
        self._set_quote_depth(0)

    def _get_quote_depth(self):
        """Return the space offset associated to the deepest opened quote."""
        return self._quote_stack and self._quote_stack[-1] or 0

    def _set_quote_depth(self, depth, citation=False):
        def open_quote(depth):
            self.close_table()
            self.close_paragraph()
            self.close_list()
            def open_one_quote(d):
                self._quote_stack.append(d)
                self._set_tab(d)
                class_attr = citation and ' class="citation"' or ''
                self.out.write('<blockquote%s>' % class_attr + os.linesep)
            if citation:
                for d in range(quote_depth+1, depth+1):
                    open_one_quote(d)
            else:
                open_one_quote(depth)
        def close_quote():
            self.close_table()
            self.close_paragraph()
            self._quote_stack.pop()
            self.out.write('</blockquote>' + os.linesep)
        quote_depth = self._get_quote_depth()
        if depth > quote_depth:
            self._set_tab(depth)
            tabstops = self._tabstops[::-1]
            while tabstops:
                tab = tabstops.pop()
                if tab > quote_depth:
                    open_quote(tab)
        else:
            while self._quote_stack:
                deepest_offset = self._quote_stack[-1]
                if depth >= deepest_offset:
                    break
                close_quote()
            if not citation and depth > 0:
                if self._quote_stack:
                    old_offset = self._quote_stack[-1]
                    if old_offset != depth: # adjust last depth
                        self._quote_stack[-1] = depth
                else:
                    open_quote(depth)
        if depth > 0:
            self.in_quote = True

    # Table
    
    def _last_table_cell_formatter(self, match, fullmatch):
        return ''

    def _table_cell_formatter(self, match, fullmatch):
        self.open_table()
        self.open_table_row()
        if self.in_table_cell:
            return '</td><td>'
        else:
            self.in_table_cell = 1
            return '<td>'

    def open_table(self):
        if not self.in_table:
            self.close_paragraph()
            self.close_list()
            self.close_def_list()
            self.in_table = 1
            self.out.write('<table class="wiki">' + os.linesep)

    def open_table_row(self):
        if not self.in_table_row:
            self.open_table()
            self.in_table_row = 1
            self.out.write('<tr>')

    def close_table_row(self):
        if self.in_table_row:
            self.in_table_row = 0
            if self.in_table_cell:
                self.in_table_cell = 0
                self.out.write('</td>')

            self.out.write('</tr>')

    def close_table(self):
        if self.in_table:
            self.close_table_row()
            self.out.write('</table>' + os.linesep)
            self.in_table = 0

    # Paragraphs

    def open_paragraph(self):
        if not self.paragraph_open:
            self.out.write('<p>' + os.linesep)
            self.paragraph_open = 1

    def close_paragraph(self):
        if self.paragraph_open:
            while self._open_tags != []:
                self.out.write(self._open_tags.pop()[1])
            self.out.write('</p>' + os.linesep)
            self.paragraph_open = 0

    # Code blocks
    
    def handle_code_block(self, line):
        if line.strip() == Formatter.STARTBLOCK:
            self.in_code_block += 1
            if self.in_code_block == 1:
                self.code_processor = None
                self.code_text = ''
            else:
                self.code_text += line + os.linesep
                if not self.code_processor:
                    self.code_processor = WikiProcessor(self.env, 'default')
        elif line.strip() == Formatter.ENDBLOCK:
            self.in_code_block -= 1
            if self.in_code_block == 0 and self.code_processor:
                self.close_table()
                self.close_paragraph()
                self.out.write(to_unicode(self.code_processor.process(
                    self.req, self.code_text)))
            else:
                self.code_text += line + os.linesep
        elif not self.code_processor:
            match = Formatter._processor_re.search(line)
            if match:
                name = match.group(1)
                self.code_processor = WikiProcessor(self.env, name)
            else:
                self.code_text += line + os.linesep 
                self.code_processor = WikiProcessor(self.env, 'default')
        else:
            self.code_text += line + os.linesep

    def close_code_blocks(self):
        while self.in_code_block > 0:
            self.handle_code_block(Formatter.ENDBLOCK)

    # -- Wiki engine
    
    def handle_match(self, fullmatch):
        for itype, match in fullmatch.groupdict().items():
            if match and not itype in self.wiki.helper_patterns:
                # Check for preceding escape character '!'
                if match[0] == '!':
                    return escape(match[1:])
                if itype in self.wiki.external_handlers:
                    external_handler = self.wiki.external_handlers[itype]
                    return external_handler(self, match, fullmatch)
                else:
                    internal_handler = getattr(self, '_%s_formatter' % itype)
                    return internal_handler(match, fullmatch)

    def replace(self, fullmatch):
        """Replace one match with its corresponding expansion"""
        replacement = self.handle_match(fullmatch)
        if replacement:
            return to_unicode(replacement)

    def reset(self, out=None):
        class NullOut(object):
            def write(self, data): pass
        self.out = out or NullOut()
        self._open_tags = []
        self._list_stack = []
        self._quote_stack = []
        self._tabstops = []

        self.in_code_block = 0
        self.in_table = 0
        self.in_def_list = 0
        self.in_table_row = 0
        self.in_table_cell = 0
        self.paragraph_open = 0

    def format(self, text, out=None, escape_newlines=False):
        self.reset(out)
        for line in text.splitlines():
            # Handle code block
            if self.in_code_block or line.strip() == Formatter.STARTBLOCK:
                self.handle_code_block(line)
                continue
            # Handle Horizontal ruler
            elif line[0:4] == '----':
                self.close_table()
                self.close_paragraph()
                self.close_indentation()
                self.close_list()
                self.close_def_list()
                self.out.write('<hr />' + os.linesep)
                continue
            # Handle new paragraph
            elif line == '':
                self.close_paragraph()
                self.close_indentation()
                self.close_list()
                self.close_def_list()
                continue

            # Tab expansion and clear tabstops if no indent
            line = line.replace('\t', ' '*8)
            if not line.startswith(' '):
                self._tabstops = []

            if escape_newlines:
                line += ' [[BR]]'
            self.in_list_item = False
            self.in_quote = False
            # Throw a bunch of regexps on the problem
            result = re.sub(self.wiki.rules, self.replace, line)

            if not self.in_list_item:
                self.close_list()

            if not self.in_quote:
                self.close_indentation()

            if self.in_def_list and not line.startswith(' '):
                self.close_def_list()

            if self.in_table and line.strip()[0:2] != '||':
                self.close_table()

            if len(result) and not self.in_list_item and not self.in_def_list \
                    and not self.in_table:
                self.open_paragraph()
            self.out.write(result + os.linesep)
            self.close_table_row()

        self.close_table()
        self.close_paragraph()
        self.close_indentation()
        self.close_list()
        self.close_def_list()
        self.close_code_blocks()


class OneLinerFormatter(Formatter):
    """
    A special version of the wiki formatter that only implement a
    subset of the wiki formatting functions. This version is useful
    for rendering short wiki-formatted messages on a single line
    """
    flavor = 'oneliner'

    def __init__(self, env, absurls=False, db=None):
        Formatter.__init__(self, env, None, absurls, db)

    # Override a few formatters to disable some wiki syntax in "oneliner"-mode
    def _list_formatter(self, match, fullmatch): return match
    def _indent_formatter(self, match, fullmatch): return match
    def _citation_formatter(self, match, fullmatch):
        return escape(match, False)
    def _heading_formatter(self, match, fullmatch):
        return escape(match, False)
    def _definition_formatter(self, match, fullmatch):
        return escape(match, False)
    def _table_cell_formatter(self, match, fullmatch): return match
    def _last_table_cell_formatter(self, match, fullmatch): return match

    def _macro_formatter(self, match, fullmatch):
        name = fullmatch.group('macroname')
        if name.lower() == 'br':
            return ' '
        elif name == 'comment':
            return ''
        else:
            args = fullmatch.group('macroargs')
            return '[[%s%s]]' % (name,  args and '(...)' or '')

    def format(self, text, out, shorten=False):
        if not text:
            return
        self.out = out
        self._open_tags = []

        # Simplify code blocks
        in_code_block = 0
        processor = None
        buf = StringIO()
        for line in text.strip().splitlines():
            if line.strip() == Formatter.STARTBLOCK:
                in_code_block += 1
            elif line.strip() == Formatter.ENDBLOCK:
                if in_code_block:
                    in_code_block -= 1
                    if in_code_block == 0:
                        if processor != 'comment':
                            buf.write(' ![...]' + os.linesep)
                        processor = None
            elif in_code_block:
                if not processor:
                    if line.startswith('#!'):
                        processor = line[2:].strip()
            else:
                buf.write(line + os.linesep)
        result = buf.getvalue()[:-1]

        if shorten:
            result = shorten_line(result)

        result = re.sub(self.wiki.rules, self.replace, result)
        result = result.replace('[...]', '[&hellip;]')
        if result.endswith('...'):
            result = result[:-3] + '&hellip;'

        # Close all open 'one line'-tags
        result += self.close_tag(None)
        # Flush unterminated code blocks
        if in_code_block > 0:
            result += '[&hellip;]'
        out.write(result)


class OutlineFormatter(Formatter):
    """Special formatter that generates an outline of all the headings."""
    flavor = 'outline'
    
    def __init__(self, env, absurls=False, db=None):
        Formatter.__init__(self, env, None, absurls, db)

    # Avoid the possible side-effects of rendering WikiProcessors

    def _macro_formatter(self, match, fullmatch):
        return ''

    def handle_code_block(self, line):
        if line.strip() == Formatter.STARTBLOCK:
            self.in_code_block += 1
        elif line.strip() == Formatter.ENDBLOCK:
            self.in_code_block -= 1

    def format(self, text, out, max_depth=6, min_depth=1):
        self.outline = []
        Formatter.format(self, text)

        if min_depth > max_depth:
            min_depth, max_depth = max_depth, min_depth
        max_depth = min(6, max_depth)
        min_depth = max(1, min_depth)

        curr_depth = min_depth - 1
        for depth, anchor, text in self.outline:
            if depth < min_depth or depth > max_depth:
                continue
            if depth < curr_depth:
                out.write('</li></ol><li>' * (curr_depth - depth))
            elif depth > curr_depth:
                out.write('<ol><li>' * (depth - curr_depth))
            else:
                out.write("</li><li>\n")
            curr_depth = depth
            out.write('<a href="#%s">%s</a>' % (anchor, text))
        out.write('</li></ol>' * curr_depth)

    def _heading_formatter(self, match, fullmatch):
        depth, heading, anchor = self._parse_heading(match, fullmatch, True)
        heading = re.sub(r'</?a(?: .*?)?>', '', heading) # Strip out link tags
        self.outline.append((depth, anchor, heading))


class LinkFormatter(OutlineFormatter):
    """Special formatter that focuses on TracLinks."""
    flavor = 'outline'
    
    def __init__(self, env, absurls=False, db=None):
        OutlineFormatter.__init__(self, env, absurls, db)
        
    def match(self, wikitext):
        """Return the Wiki match found at the beginning of the `wikitext`"""
        self.reset()        
        match = re.match(self.wiki.rules, wikitext)
        if match:
            return self.handle_match(match)


# -- wiki_to_* helper functions

def wiki_to_html(wikitext, env, req, db=None,
                 absurls=False, escape_newlines=False):
    if not wikitext:
        return Markup()
    out = StringIO()
    Formatter(env, req, absurls, db).format(wikitext, out, escape_newlines)
    return Markup(out.getvalue())

def wiki_to_oneliner(wikitext, env, db=None, shorten=False, absurls=False):
    if not wikitext:
        return Markup()
    out = StringIO()
    OneLinerFormatter(env, absurls, db).format(wikitext, out, shorten)
    return Markup(out.getvalue())

def wiki_to_outline(wikitext, env, db=None,
                    absurls=False, max_depth=None, min_depth=None):
    if not wikitext:
        return Markup()
    out = StringIO()
    OutlineFormatter(env, absurls, db).format(wikitext, out, max_depth,
                                              min_depth)
    return Markup(out.getvalue())

def wiki_to_link(wikitext, env, req):
    if not wikitext:
        return ''
    return LinkFormatter(env, False, None).match(wikitext)

