# -*- coding: utf-8 -*-
#
# Copyright (C) 2005-2006 Edgewall Software
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
# Author: Christian Boos <cboos@neuf.fr>

import re

from trac.core import *
from trac.wiki.formatter import Formatter
from trac.wiki.api import IWikiChangeListener, IWikiMacroProvider

class InterWikiMap(Component):
    """Implements support for InterWiki maps."""

    implements(IWikiChangeListener, IWikiMacroProvider)

    _page_name = 'InterMapTxt'
    _interwiki_re = re.compile(r"(%s)[ \t]+([^ \t]+)(?:[ \t]+#(.*))?" %
                               Formatter.LINK_SCHEME, re.UNICODE)
    _argspec_re = re.compile(r"\$\d")

    def __init__(self):
        self._interwiki_map = None
        # This dictionary maps upper-cased namespaces
        # to (namespace, prefix, title) values;

    # The component itself behaves as a map

    def __contains__(self, ns):
        self._update()
        return ns.upper() in self._interwiki_map

    def __getitem__(self, ns):
        self._update()
        return self._interwiki_map[ns.upper()]

    def __setitem__(self, ns, value):
        self._update()
        self._interwiki_map[ns.upper()] = value

    def keys(self):
        self._update()
        return self._interwiki_map.keys()

    # Expansion of positional arguments ($1, $2, ...) in URL and title
    def _expand(self, txt, args):
        """Replace "$1" by the first args, "$2" by the second, etc."""
        def setarg(match):
            num = int(match.group()[1:])
            return 0 < num <= len(args) and args[num-1] or ''
        return re.sub(InterWikiMap._argspec_re, setarg, txt)

    def _expand_or_append(self, txt, args):
        """Like expand, but also append first arg if there's no "$"."""
        if not args:
            return txt
        expanded = self._expand(txt, args)
        return expanded == txt and txt + args[0] or expanded

    def url(self, ns, target):
        """Return `(url, title)` for the given InterWiki `ns`.
        
        Expand the colon-separated `target` arguments.
        """
        ns, url, title = self[ns]
        args = target.split(':')
        expanded_url = self._expand_or_append(url, args)
        expanded_title = self._expand(title, args)
        if expanded_title == title:
            expanded_title = target+' in '+title
        return expanded_url, expanded_title

    # IWikiChangeListener methods

    def wiki_page_added(self, page):
        if page.name == InterWikiMap._page_name:
            self._update()

    def wiki_page_changed(self, page, version, t, comment, author, ipnr):
        if page.name == InterWikiMap._page_name:
            self._update()

    def wiki_page_deleted(self, page):
        if page.name == InterWikiMap._page_name:
            self._interwiki_map = None

    def wiki_page_version_deleted(self, page):
        if page.name == InterWikiMap._page_name:
            self._update()

    def _update(self):
        from trac.wiki.model import WikiPage
        if self._interwiki_map is not None:
            return
        self._interwiki_map = {}
        content = WikiPage(self.env, InterWikiMap._page_name).text
        in_map = False
        for line in content.split('\n'):
            if in_map:
                if line.startswith('----'):
                    in_map = False
                else:
                    m = re.match(InterWikiMap._interwiki_re, line)
                    if m:
                        prefix, url, title = m.groups()
                        url = url.strip()
                        title = title and title.strip() or prefix
                        self[prefix] = (prefix, url, title)
            elif line.startswith('----'):
                in_map = True

    # IWikiMacroProvider methods

    def get_macros(self):
        yield 'InterWiki'

    def get_macro_description(self, name): 
        return "Provide a description list for the known InterWiki prefixes."

    def render_macro(self, req, name, content):
        from trac.util import sorted
        from trac.util.markup import html as _
        interwikis = []
        for k in sorted(self.keys()):
            prefix, url, title = self[k]
            interwikis.append({
                'prefix': prefix, 'url': url, 'title': title,
                'rc_url': self._expand_or_append(url, ['RecentChanges']),
                'description': title == prefix and url or title})

        return _.TABLE(_.TR(_.TH(_.EM("Prefix")), _.TH(_.EM("Site"))),
                       [ _.TR(_.TD(_.A(w['prefix'], href=w['rc_url'])),
                              _.TD(_.A(w['description'], href=w['url'])))
                         for w in interwikis ],
                       class_="wiki interwiki")
