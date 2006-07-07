# -*- coding: utf-8 -*-
#
# Copyright (C) 2005 Edgewall Software
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
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
# Author: Christopher Lenz <cmlenz@gmx.de>

import os
import re

from trac import mimeview
from trac.config import *
from trac.core import *
from trac.env import IEnvironmentSetupParticipant
from trac.util.markup import html
from trac.web.api import IRequestHandler, HTTPNotFound
from trac.web.href import Href
from trac.wiki import IWikiSyntaxProvider

def add_link(req, rel, href, title=None, mimetype=None, classname=None):
    """Add a link to the HDF data set that will be inserted as <link> element in
    the <head> of the generated HTML
    """
    link = {'href': href}
    if title:
        link['title'] = title
    if mimetype:
        link['type'] = mimetype
    if classname:
        link['class'] = classname
    # FIXME: don't add the same link more than once
    req.environ.setdefault('trac.chrome.links', {}).setdefault(rel, []).append(link)

def add_stylesheet(req, filename, mimetype='text/css'):
    """Add a link to a style sheet to the HDF data set so that it gets included
    in the generated HTML page.
    """
    if filename.startswith('common/') and 'htdocs_location' in req.hdf:
        href = Href(req.hdf['htdocs_location'])
        filename = filename[7:]
    else:
        href = Href(req.base_path).chrome
    add_link(req, 'stylesheet', href(filename), mimetype=mimetype)

def add_script(req, filename, mimetype='text/javascript'):
    """Add a reference to an external javascript file to the template."""
    if filename.startswith('common/') and 'htdocs_location' in req.hdf:
        href = Href(req.hdf['htdocs_location'])
        filename = filename[7:]
    else:
        href = Href(req.base_path).chrome
    script = {'href': href(filename), 'type': mimetype}
    # FIXME: don't add the same script more than once
    req.environ.setdefault('trac.chrome.scripts', []).append(script)

def add_javascript(req, filename):
    """Deprecated: use `add_script()` instead."""
    add_script(req, filename, mimetype='text/javascript')


class INavigationContributor(Interface):
    """Extension point interface for components that contribute items to the
    navigation.
    """

    def get_active_navigation_item(req):
        """This method is only called for the `IRequestHandler` processing the
        request.
        
        It should return the name of the navigation item that should be
        highlighted as active/current.
        """

    def get_navigation_items(req):
        """Should return an iterable object over the list of navigation items to
        add, each being a tuple in the form (category, name, text).
        """


class ITemplateProvider(Interface):
    """Extension point interface for components that provide their own
    ClearSilver templates and accompanying static resources.
    """

    def get_htdocs_dirs():
        """Return a list of directories with static resources (such as style
        sheets, images, etc.)

        Each item in the list must be a `(prefix, abspath)` tuple. The
        `prefix` part defines the path in the URL that requests to these
        resources are prefixed with.
        
        The `abspath` is the absolute path to the directory containing the
        resources on the local file system.
        """

    def get_templates_dirs():
        """Return a list of directories containing the provided ClearSilver
        templates.
        """


class Chrome(Component):
    """Responsible for assembling the web site chrome, i.e. everything that
    is not actual page content.
    """
    implements(IEnvironmentSetupParticipant, IRequestHandler, ITemplateProvider,
               IWikiSyntaxProvider)

    navigation_contributors = ExtensionPoint(INavigationContributor)
    template_providers = ExtensionPoint(ITemplateProvider)

    templates_dir = Option('trac', 'templates_dir', default_dir('templates'),
        """Path to the !ClearSilver templates.""")

    htdocs_location = Option('trac', 'htdocs_location', '',
        """Base URL of the core static resources.""")

    metanav_order = ListOption('trac', 'metanav',
                               'login,logout,settings,help,about', doc=
        """List of items IDs to display in the navigation bar `metanav`.""")

    mainnav_order = ListOption('trac', 'mainnav',
                               'wiki,timeline,roadmap,browser,tickets,'
                               'newticket,search', doc=
        """List of item IDs to display in the navigation bar `mainnav`.""")

    logo_link = Option('header_logo', 'link', 'http://example.org/',
        """URL to link to from header logo.""")

    logo_src = Option('header_logo', 'src', 'common/trac_banner.png',
        """URL of the image to use as header logo.""")

    logo_alt = Option('header_logo', 'alt', '',
        """Alternative text for the header logo.""")

    logo_width = IntOption('header_logo', 'width', -1,
        """Width of the header logo image in pixels.""")

    logo_height = IntOption('header_logo', 'height', -1,
        """Height of the header logo image in pixels.""")

    # IEnvironmentSetupParticipant methods

    def environment_created(self):
        """Create the environment templates directory."""
        if self.env.path:
            templates_dir = os.path.join(self.env.path, 'templates')
            if not os.path.exists(templates_dir):
                os.mkdir(templates_dir)

            fileobj = open(os.path.join(templates_dir, 'site.html'), 'w')
            try:
                fileobj.write("""<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:py="http://markup.edgewall.org/" py:strip="">
  <!-- Custom match templates fo here -->
</html>""")
            finally:
                fileobj.close()


    def environment_needs_upgrade(self, db):
        return False

    def upgrade_environment(self, db):
        pass

    # IRequestHandler methods

    anonymous_request = True
    use_template = False

    def match_request(self, req):
        match = re.match(r'/chrome/(?P<prefix>[^/]+)/(?P<filename>[/\w\-\.]+)',
                         req.path_info)
        if match:
            req.args['prefix'] = match.group('prefix')
            req.args['filename'] = match.group('filename')
            return True

    def process_request(self, req):
        prefix = req.args['prefix']
        filename = req.args['filename']

        dirs = []
        for provider in self.template_providers:
            for dir in [os.path.normpath(dir[1]) for dir
                        in provider.get_htdocs_dirs() if dir[0] == prefix]:
                dirs.append(dir)
                path = os.path.normpath(os.path.join(dir, filename))
                assert os.path.commonprefix([dir, path]) == dir
                if os.path.isfile(path):
                    req.send_file(path)

        self.log.warning('File %s not found in any of %s', filename, dirs)
        raise HTTPNotFound('File %s not found', filename)

    # ITemplateProvider methods

    def get_htdocs_dirs(self):
        from trac.config import default_dir
        return [('common', default_dir('htdocs')),
                ('site', self.env.get_htdocs_dir())]

    def get_templates_dirs(self):
        return [self.env.get_templates_dir(), self.templates_dir]

    # IWikiSyntaxProvider methods
    
    def get_wiki_syntax(self):
        return []
    
    def get_link_resolvers(self):
        yield ('htdocs', self._format_link)

    def _format_link(self, formatter, ns, file, label):
        return html.A(label, href=formatter.href.chrome('site', file))

    # Public API methods

    def get_all_templates_dirs(self):
        """Return a list of the names of all known templates directories."""
        dirs = []
        for provider in self.template_providers:
            dirs += provider.get_templates_dirs()
        return dirs

    def render_response(self, req, template_name, content_type, data):
        from markup.core import Markup
        from markup.input import HTML, XML
        from markup.template import Context, TemplateLoader
        from trac import __version__ as VERSION

        loader = TemplateLoader(self.get_all_templates_dirs())
        template = loader.load(template_name)

        data.setdefault('chrome', {}).update({
            'footer': Markup(self.env.project_footer),
            'logo': req.environ.get('trac.chrome.logo', {}),
            'links': req.environ.get('trac.chrome.links', []),
            'nav': req.environ.get('trac.chrome.nav', {}),
            'scripts': req.environ.get('trac.chrome.scripts', []),
            'version': VERSION
        })
        data['req'] = req
        data['href'] = req.href
        data['perm'] = req.perm
        data['Markup'] = Markup
        data['HTML'] = HTML
        data['XML'] = XML
        stream = template.generate(Context(**data))

        if content_type is None:
            content_type = 'text/html'
        method = {'text/html': 'html'}.get(content_type, 'xml')
        return stream.render(method)

    def _finalize_hdf(self, req):
        req.hdf['chrome.links'] = req.environ.get('trac.chrome.links', [])
        req.hdf['chrome.logo'] = req.environ.get('trac.chrome.logo', {})
        req.hdf['chrome.scripts'] = req.environ.get('trac.chrome.scripts', [])

        for category, items in req.environ.get('trac.chrome.nav', {}).items():
            for item in items:
                prefix = 'chrome.nav.%s.%s' % (category, item['name'])
                req.hdf[prefix] = item['label']

    def populate_hdf(self, req, handler):
        """Add chrome-related data to the HDF."""

        # Provided for template customization
        req.hdf['HTTP.PathInfo'] = req.path_info

        href = Href(req.base_path)
        req.hdf['chrome.href'] = href.chrome()
        htdocs_location = self.htdocs_location or href.chrome('common')
        req.hdf['htdocs_location'] = htdocs_location.rstrip('/') + '/'

        # HTML <head> links
        add_link(req, 'start', req.href.wiki())
        add_link(req, 'search', req.href.search())
        add_link(req, 'help', req.href.wiki('TracGuide'))
        add_stylesheet(req, 'common/css/trac.css')
        add_script(req, 'common/js/trac.js')

        icon = self.env.project_icon
        if icon:
            if not icon.startswith('/') and icon.find('://') == -1:
                if '/' in icon:
                    icon = href.chrome(icon)
                else:
                    icon = href.chrome('common', icon)
            mimetype = mimeview.get_mimetype(icon)
            add_link(req, 'icon', icon, mimetype=mimetype)
            add_link(req, 'shortcut icon', icon, mimetype=mimetype)

        # Logo image
        logo = {}
        logo_src = self.logo_src
        if logo_src:
            logo_src_abs = logo_src.startswith('http://') or \
                           logo_src.startswith('https://')
            if not logo_src.startswith('/') and not logo_src_abs:
                if '/' in logo_src:
                    logo_src = href.chrome(logo_src)
                else:
                    logo_src = href.chrome('common', logo_src)
            width = self.logo_width > -1 and self.logo_width
            height = self.logo_height > -1 and self.logo_height
            logo = {
                'link': self.logo_link, 'src': logo_src,
                'src_abs': logo_src_abs, 'alt': self.logo_alt,
                'width': width, 'height': height
            }
        else:
            logo = {'link': self.logo_link}
        req.environ['trac.chrome.logo'] = logo

        # Navigation links
        allitems = {}
        active = None
        for contributor in self.navigation_contributors:
            for category, name, text in contributor.get_navigation_items(req):
                allitems.setdefault(category, {})[name] = text
            if contributor is handler:
                active = contributor.get_active_navigation_item(req)

        nav = {}
        for category, items in [(k, v.items()) for k, v in allitems.items()]:
            order = getattr(self, category + '_order')
            def navcmp(x, y):
                if x[0] not in order:
                    return int(y[0] in order)
                if y[0] not in order:
                    return -int(x[0] in order)
                return cmp(order.index(x[0]), order.index(y[0]))
            items.sort(navcmp)

            nav[category] = []
            for name, label in items:
                nav[category].append({'name': name, 'label': label})
                if name == active:
                    nav[category][-1]['active'] = True

        req.environ['trac.chrome.nav'] = nav
