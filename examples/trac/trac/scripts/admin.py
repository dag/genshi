# -*- coding: utf-8 -*-
# 
# Copyright (C) 2003-2006 Edgewall Software
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

__copyright__ = 'Copyright (c) 2003-2006 Edgewall Software'

import cmd
import getpass
import os
import shlex
import shutil
import StringIO
import sys
import time
import traceback
import urllib
import locale

import trac
from trac import perm, util, db_default
from trac.config import default_dir
from trac.core import TracError
from trac.env import Environment
from trac.perm import PermissionSystem
from trac.ticket.model import *
from trac.util.markup import html
from trac.util.text import to_unicode, wrap
from trac.wiki import WikiPage
from trac.wiki.macros import WikiMacroBase

def copytree(src, dst, symlinks=False, skip=[]):
    """Recursively copy a directory tree using copy2() (from shutil.copytree.)

    Added a `skip` parameter consisting of absolute paths
    which we don't want to copy.
    """
    names = os.listdir(src)
    os.mkdir(dst)
    errors = []
    for name in names:
        srcname = os.path.join(src, name)
        if srcname in skip:
            continue
        dstname = os.path.join(dst, name)
        try:
            if symlinks and os.path.islink(srcname):
                linkto = os.readlink(srcname)
                os.symlink(linkto, dstname)
            elif os.path.isdir(srcname):
                copytree(srcname, dstname, symlinks, skip)
            else:
                shutil.copy2(srcname, dstname)
            # XXX What about devices, sockets etc.?
        except (IOError, os.error), why:
            errors.append((srcname, dstname, why))
    if errors:
        raise shutil.Error, errors


class TracAdmin(cmd.Cmd):
    intro = ''
    license = trac.__license_long__
    doc_header = 'Trac Admin Console %(ver)s\n' \
                 'Available Commands:\n' \
                 % {'ver':trac.__version__ }
    ruler = ''
    prompt = "Trac> "
    __env = None
    _date_format = '%Y-%m-%d'
    _datetime_format = '%Y-%m-%d %H:%M:%S'
    _date_format_hint = 'YYYY-MM-DD'

    def __init__(self, envdir=None):
        cmd.Cmd.__init__(self)
        self.interactive = False
        if envdir:
            self.env_set(os.path.abspath(envdir))
        self._permsys = None

    def emptyline(self):
        pass

    def onecmd(self, line):
        """`line` may be a `str` or an `unicode` object"""
        try:
            if isinstance(line, str):
                line = to_unicode(line, sys.stdin.encoding)
            rv = cmd.Cmd.onecmd(self, line) or 0
        except SystemExit:
            raise
        except Exception, e:
            print>>sys.stderr, 'Command failed: %s' % e
            rv = 2
        if not self.interactive:
            return rv

    def run(self):
        self.interactive = True
        print 'Welcome to trac-admin %(ver)s\n'                \
              'Interactive Trac administration console.\n'       \
              '%(copy)s\n\n'                                    \
              "Type:  '?' or 'help' for help on commands.\n" %  \
              {'ver':trac.__version__,'copy':__copyright__}
        self.cmdloop()

    ##
    ## Environment methods
    ##

    def env_set(self, envname, env=None):
        self.envname = envname
        self.prompt = "Trac [%s]> " % self.envname
        if env is not None:
            self.__env = env

    def env_check(self):
        try:
            self.__env = Environment(self.envname)
        except:
            return 0
        return 1

    def env_open(self):
        try:
            if not self.__env:
                self.__env = Environment(self.envname)
            return self.__env
        except Exception, e:
            print 'Failed to open environment.', e
            traceback.print_exc()
            sys.exit(1)

    def db_open(self):
        return self.env_open().get_db_cnx()

    def db_query(self, sql, cursor=None, params=None):
        if not cursor:
            cnx = self.db_open()
            cursor = cnx.cursor()
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        for row in cursor:
            yield row

    def db_update(self, sql, cursor=None, params=None):
        if not cursor:
            cnx = self.db_open()
            cursor = cnx.cursor()
        else:
            cnx = None
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        if cnx:
            cnx.commit()

    ##
    ## Utility methods
    ##

    def arg_tokenize (self, argstr):
        """`argstr` is an `unicode` string

        ... but shlex is not unicode friendly.
        """
        return [unicode(token, 'utf-8')
                for token in shlex.split(argstr.encode('utf-8'))] or ['']

    def word_complete (self, text, words):
        return [a for a in words if a.startswith (text)]

    def print_listing(self, headers, data, sep=' ', decor=True):
        cons_charset = sys.stdout.encoding
        ldata = list(data)
        if decor:
            ldata.insert(0, headers)
        print
        colw = []
        ncols = len(ldata[0]) # assumes all rows are of equal length
        for cnum in xrange(0, ncols):
            mw = 0
            for cell in [unicode(d[cnum]) or '' for d in ldata]:
                if len(cell) > mw:
                    mw = len(cell)
            colw.append(mw)
        for rnum in xrange(len(ldata)):
            for cnum in xrange(ncols):
                if decor and rnum == 0:
                    sp = ('%%%ds' % len(sep)) % ' '  # No separator in header
                else:
                    sp = sep
                if cnum + 1 == ncols:
                    sp = '' # No separator after last column
                pdata = ((u'%%-%ds%s' % (colw[cnum], sp)) 
                         % (ldata[rnum][cnum] or ''))
                if cons_charset and isinstance(pdata, unicode):
                    pdata = pdata.encode(cons_charset, 'replace')
                print pdata,
            print
            if rnum == 0 and decor:
                print ''.join(['-' for x in
                               xrange(0, (1 + len(sep)) * cnum + sum(colw))])
        print

    def print_doc(cls, docs, stream=None):
        if stream is None:
            stream = sys.stdout
        if not docs: return
        for cmd, doc in docs:
            print>>stream, cmd
            print>>stream, '\t-- %s\n' % doc
    print_doc = classmethod(print_doc)

    def get_component_list(self):
        rows = self.db_query("SELECT name FROM component")
        return [row[0] for row in rows]

    def get_user_list(self):
        rows = self.db_query("SELECT DISTINCT username FROM permission")
        return [row[0] for row in rows]

    def get_wiki_list(self):
        rows = self.db_query('SELECT DISTINCT name FROM wiki') 
        return [row[0] for row in rows]

    def get_dir_list(self, pathstr, justdirs=False):
        dname = os.path.dirname(pathstr)
        d = os.path.join(os.getcwd(), dname)
        dlist = os.listdir(d)
        if justdirs:
            result = []
            for entry in dlist:
                try:
                    if os.path.isdir(entry):
                        result.append(entry)
                except:
                    pass
        else:
            result = dlist
        return result

    def get_enum_list(self, type):
        rows = self.db_query("SELECT name FROM enum WHERE type=%s",
                             params=[type])
        return [row[0] for row in rows]

    def get_milestone_list(self):
        rows = self.db_query("SELECT name FROM milestone")
        return [row[0] for row in rows]

    def get_version_list(self):
        rows = self.db_query("SELECT name FROM version")
        return [row[0] for row in rows]

    def _parse_date(self, t):
        seconds = None
        t = t.strip()
        if t == 'now':
            seconds = int(time.time())
        else:
            for format in [self._date_format, '%x %X', '%x, %X', '%X %x',
                           '%X, %x', '%x', '%c', '%b %d, %Y']:
                try:
                    pt = time.strptime(t, format)
                    seconds = int(time.mktime(pt))
                except ValueError:
                    continue
                break
        if seconds == None:
            try:
                seconds = int(t)
            except ValueError:
                pass
        if seconds == None:
            print>>sys.stderr, 'Unknown time format %s' % t
        return seconds

    def _format_date(self, s):
        return time.strftime(self._date_format, time.localtime(s))

    def _format_datetime(self, s):
        return time.strftime(self._datetime_format, time.localtime(s))


    ##
    ## Available Commands
    ##

    ## Help
    _help_help = [('help', 'Show documentation')]

    def all_docs(cls):
        return (cls._help_about + cls._help_help +
                cls._help_initenv + cls._help_hotcopy +
                cls._help_resync + cls._help_upgrade +
                cls._help_wiki +
#               cls._help_config + cls._help_wiki +
                cls._help_permission + cls._help_component +
                cls._help_ticket +
                cls._help_ticket_type + cls._help_priority +
                cls._help_severity +  cls._help_version +
                cls._help_milestone)
    all_docs = classmethod(all_docs)

    def do_help(self, line=None):
        arg = self.arg_tokenize(line)
        if arg[0]:
            try:
                doc = getattr(self, "_help_" + arg[0])
                self.print_doc(doc)
            except AttributeError:
                print "No documentation found for '%s'" % arg[0]
        else:
            print 'trac-admin - The Trac Administration Console %s' \
                  % trac.__version__
            if not self.interactive:
                print
                print "Usage: trac-admin </path/to/projenv> [command [subcommand] [option ...]]\n"
                print "Invoking trac-admin without command starts "\
                      "interactive mode."
            self.print_doc(self.all_docs())

    
    ## About / Version
    _help_about = [('about', 'Shows information about trac-admin')]

    def do_about(self, line):
        print
        print 'Trac Admin Console %s' % trac.__version__
        print '================================================================='
        print self.license


    ## Quit / EOF
    _help_quit = [['quit', 'Exit the program']]
    _help_exit = _help_quit
    _help_EOF = _help_quit

    def do_quit(self, line):
        print
        sys.exit()

    do_exit = do_quit # Alias
    do_EOF = do_quit # Alias


    # Component
    _help_component = [('component list', 'Show available components'),
                       ('component add <name> <owner>', 'Add a new component'),
                       ('component rename <name> <newname>',
                        'Rename a component'),
                       ('component remove <name>',
                        'Remove/uninstall component'),
                       ('component chown <name> <owner>',
                        'Change component ownership')]

    def complete_component(self, text, line, begidx, endidx):
        if begidx in (16, 17):
            comp = self.get_component_list()
        elif begidx > 15 and line.startswith('component chown '):
            comp = self.get_user_list()
        else:
            comp = ['list', 'add', 'rename', 'remove', 'chown']
        return self.word_complete(text, comp)

    def do_component(self, line):
        arg = self.arg_tokenize(line)
        if arg[0]  == 'list':
            self._do_component_list()
        elif arg[0] == 'add' and len(arg)==3:
            name = arg[1]
            owner = arg[2]
            self._do_component_add(name, owner)
        elif arg[0] == 'rename' and len(arg)==3:
            name = arg[1]
            newname = arg[2]
            self._do_component_rename(name, newname)
        elif arg[0] == 'remove'  and len(arg)==2:
            name = arg[1]
            self._do_component_remove(name)
        elif arg[0] == 'chown' and len(arg)==3:
            name = arg[1]
            owner = arg[2]
            self._do_component_set_owner(name, owner)
        else:    
            self.do_help ('component')

    def _do_component_list(self):
        data = []
        for c in Component.select(self.env_open()):
            data.append((c.name, c.owner))
        self.print_listing(['Name', 'Owner'], data)

    def _do_component_add(self, name, owner):
        component = Component(self.env_open())
        component.name = name
        component.owner = owner
        component.insert()

    def _do_component_rename(self, name, newname):
        component = Component(self.env_open(), name)
        component.name = newname
        component.update()

    def _do_component_remove(self, name):
        component = Component(self.env_open(), name)
        component.delete()

    def _do_component_set_owner(self, name, owner):
        component = Component(self.env_open(), name)
        component.owner = owner
        component.update()


    ## Permission
    _help_permission = [('permission list [user]', 'List permission rules'),
                        ('permission add <user> <action> [action] [...]',
                         'Add a new permission rule'),
                        ('permission remove <user> <action> [action] [...]',
                         'Remove permission rule')]

    def complete_permission(self, text, line, begidx, endidx):
        argv = self.arg_tokenize(line)
        argc = len(argv)
        if line[-1] == ' ': # Space starts new argument
            argc += 1
        if argc == 2:
            comp = ['list', 'add', 'remove']
        elif argc >= 4:
            comp = perm.permissions + perm.meta_permissions.keys()
            comp.sort()
        return self.word_complete(text, comp)

    def do_permission(self, line):
        arg = self.arg_tokenize(line)
        if arg[0]  == 'list':
            user = None
            if len(arg) > 1:
                user = arg[1]
            self._do_permission_list(user)
        elif arg[0] == 'add' and len(arg) >= 3:
            user = arg[1]
            for action in arg[2:]:
                self._do_permission_add(user, action)
        elif arg[0] == 'remove'  and len(arg) >= 3:
            user = arg[1]
            for action in arg[2:]:
                self._do_permission_remove(user, action)
        else:
            self.do_help('permission')

    def _do_permission_list(self, user=None):
        if not self._permsys:
            self._permsys = PermissionSystem(self.env_open())
        if user:
            rows = []
            perms = self._permsys.get_user_permissions(user)
            for action in perms:
                if perms[action]:
                    rows.append((user, action))
        else:
            rows = self._permsys.get_all_permissions()
        rows.sort()
        self.print_listing(['User', 'Action'], rows)
        print
        print 'Available actions:'
        actions = self._permsys.get_actions()
        actions.sort()
        text = ', '.join(actions)
        print wrap(text, initial_indent=' ', subsequent_indent=' ',
                   linesep='\n')
        print

    def _do_permission_add(self, user, action):
        if not self._permsys:
            self._permsys = PermissionSystem(self.env_open())
        if not action.islower() and not action.isupper():
            print 'Group names must be in lower case and actions in upper case'
            return
        self._permsys.grant_permission(user, action)

    def _do_permission_remove(self, user, action):
        if not self._permsys:
            self._permsys = PermissionSystem(self.env_open())
        rows = self._permsys.get_all_permissions()
        if action == '*':
            for row in rows:
                if user != '*' and user != row[0]:
                    continue
                self._permsys.revoke_permission(row[0], row[1])
        else:
            for row in rows:
                if action != row[1]:
                    continue
                if user != '*' and user != row[0]:
                    continue
                self._permsys.revoke_permission(row[0], row[1])

    ## Initenv
    _help_initenv = [('initenv',
                      'Create and initialize a new environment interactively'),
                     ('initenv <projectname> <db> <repostype> <repospath> <templatepath>',
                      'Create and initialize a new environment from arguments')]

    def do_initdb(self, line):
        self.do_initenv(line)

    def get_initenv_args(self):
        returnvals = []
        print 'Creating a new Trac environment at %s' % self.envname
        print
        print 'Trac will first ask a few questions about your environment '
        print 'in order to initalize and prepare the project database.'
        print
        print " Please enter the name of your project."
        print " This name will be used in page titles and descriptions."
        print
        dp = 'My Project'
        returnvals.append(raw_input('Project Name [%s]> ' % dp).strip() or dp)
        print
        print ' Please specify the connection string for the database to use.'
        print ' By default, a local SQLite database is created in the environment '
        print ' directory. It is also possible to use an already existing '
        print ' PostgreSQL database (check the Trac documentation for the exact '
        print ' connection string syntax).'
        print
        ddb = 'sqlite:db/trac.db'
        prompt = 'Database connection string [%s]> ' % ddb
        returnvals.append(raw_input(prompt).strip() or ddb)
        print
        print ' Please specify the type of version control system,'
        print ' By default, it will be svn.'
        print
        print ' If you don\'t want to use Trac with version control integration, '
        print ' choose the default here and don\'t specify a repository directory. '
        print ' in the next question.'
        print 
        drpt = 'svn'
        prompt = 'Repository type [%s]> ' % drpt
        returnvals.append(raw_input(prompt).strip() or drpt)
        print
        print ' Please specify the absolute path to the version control '
        print ' repository, or leave it blank to use Trac without a repository.'
        print ' You can also set the repository location later.'
        print 
        prompt = 'Path to repository [/path/to/repos]> '
        returnvals.append(raw_input(prompt).strip())
        print
        print ' Please enter location of Trac page templates.'
        print ' Default is the location of the site-wide templates installed with Trac.'
        print
        dt = default_dir('templates')
        prompt = 'Templates directory [%s]> ' % dt
        returnvals.append(raw_input(prompt).strip() or dt)
        print
        return returnvals

    def do_initenv(self, line):
        if self.env_check():
            print "Initenv for '%s' failed." % self.envname
            print "Does an environment already exist?"
            return 2

        if os.path.exists(self.envname) and os.listdir(self.envname):
            print "Initenv for '%s' failed." % self.envname
            print "Directory exists and is not empty."
            return 2

        arg = self.arg_tokenize(line)
        project_name = None
        db_str = None
        repository_dir = None
        templates_dir = None
        if len(arg) == 1 and not arg[0]:
            returnvals = self.get_initenv_args()
            project_name, db_str, repository_type, repository_dir, \
                          templates_dir = returnvals
        elif len(arg) != 5:
            print 'Wrong number of arguments to initenv: %d' % len(arg)
            return 2
        else:
            project_name, db_str, repository_type, repository_dir, \
                          templates_dir = arg[:5]

        if not os.access(os.path.join(templates_dir, 'header.cs'), os.F_OK):
            print templates_dir, "doesn't look like a Trac templates directory"
            return 2

        try:
            print 'Creating and Initializing Project'
            options = [
                ('trac', 'database', db_str),
                ('trac', 'repository_type', repository_type),
                ('trac', 'repository_dir', repository_dir),
                ('trac', 'templates_dir', templates_dir),
                ('project', 'name', project_name),
            ]
            try:
                self.__env = Environment(self.envname, create=True,
                                         options=options)
            except Exception, e:
                print 'Failed to create environment.', e
                traceback.print_exc()
                sys.exit(1)

            # Add a few default wiki pages
            print ' Installing default wiki pages'
            cnx = self.__env.get_db_cnx()
            cursor = cnx.cursor()
            self._do_wiki_load(default_dir('wiki'), cursor)
            cnx.commit()

            if repository_dir:
                try:
                    repos = self.__env.get_repository()
                    if repos:
                        print ' Indexing repository'
                        repos.sync()
                except TracError, e:
                    print>>sys.stderr, "\nWarning:\n"
                    if repository_type == "svn":
                        print>>sys.stderr, "You should install the SVN bindings"
                    else:
                        print>>sys.stderr, "Repository type %s not supported" \
                                           % repository_type
        except Exception, e:
            print 'Failed to initialize environment.', e
            traceback.print_exc()
            return 2

        print """
---------------------------------------------------------------------
Project environment for '%(project_name)s' created.

You may now configure the environment by editing the file:

  %(config_path)s

If you'd like to take this new project environment for a test drive,
try running the Trac standalone web server `tracd`:

  tracd --port 8000 %(project_path)s

Then point your browser to http://localhost:8000/%(project_dir)s.
There you can also browse the documentation for your installed
version of Trac, including information on further setup (such as
deploying Trac to a real web server).

The latest documentation can also always be found on the project
website:

  http://projects.edgewall.com/trac/

Congratulations!
""" % dict(project_name=project_name, project_path=self.envname,
           project_dir=os.path.basename(self.envname),
           config_path=os.path.join(self.envname, 'conf', 'trac.ini'))

    _help_resync = [('resync', 'Re-synchronize trac with the repository')]

    ## Resync
    def do_resync(self, line):
        print 'Resyncing repository history...'
        cnx = self.db_open()
        cursor = cnx.cursor()
        cursor.execute("DELETE FROM revision")
        cursor.execute("DELETE FROM node_change")
        repos = self.__env.get_repository()
        cursor.execute("DELETE FROM system WHERE name='repository_dir'")
        cursor.execute("INSERT INTO system (name,value) "
                       "VALUES ('repository_dir',%s)", (repos.name,))
        repos.sync()
        print 'Done.'

    ## Wiki
    _help_wiki = [('wiki list', 'List wiki pages'),
                  ('wiki remove <name>', 'Remove wiki page'),
                  ('wiki export <page> [file]',
                   'Export wiki page to file or stdout'),
                  ('wiki import <page> [file]',
                   'Import wiki page from file or stdin'),
                  ('wiki dump <directory>',
                   'Export all wiki pages to files named by title'),
                  ('wiki load <directory>',
                   'Import all wiki pages from directory'),
                  ('wiki upgrade',
                   'Upgrade default wiki pages to current version')]

    def complete_wiki(self, text, line, begidx, endidx):
        argv = self.arg_tokenize(line)
        argc = len(argv)
        if line[-1] == ' ': # Space starts new argument
            argc += 1
        if argc == 2:
            comp = ['list', 'remove', 'import', 'export', 'dump', 'load',
                    'upgrade']
        else:
            if argv[1] in ('dump', 'load'):
                comp = self.get_dir_list(argv[-1], 1)
            elif argv[1] == 'remove':
                comp = self.get_wiki_list()
            elif argv[1] in ('export', 'import'):
                if argc == 3:
                    comp = self.get_wiki_list()
                elif argc == 4:
                    comp = self.get_dir_list(argv[-1])
        return self.word_complete(text, comp)

    def do_wiki(self, line):
        arg = self.arg_tokenize(line)
        if arg[0]  == 'list':
            self._do_wiki_list()
        elif arg[0] == 'remove'  and len(arg)==2:
            name = arg[1]
            self._do_wiki_remove(name)
        elif arg[0] == 'import' and len(arg) == 3:
            title = arg[1]
            file = arg[2]
            self._do_wiki_import(file, title)
        elif arg[0] == 'export'  and len(arg) in [2,3]:
            page = arg[1]
            file = (len(arg) == 3 and arg[2]) or None
            self._do_wiki_export(page, file)
        elif arg[0] == 'dump' and len(arg) in [1,2]:
            dir = (len(arg) == 2 and arg[1]) or ''
            self._do_wiki_dump(dir)
        elif arg[0] == 'load' and len(arg) in [1,2]:
            dir = (len(arg) == 2 and arg[1]) or ''
            self._do_wiki_load(dir)
        elif arg[0] == 'upgrade' and len(arg) == 1:
            self._do_wiki_load(default_dir('wiki'),
                               ignore=['WikiStart', 'checkwiki.py'],
                               create_only=['InterMapTxt'])
        else:    
            self.do_help ('wiki')

    def _do_wiki_list(self):
        rows = self.db_query("SELECT name, max(version), max(time) "
                             "FROM wiki GROUP BY name ORDER BY name")
        self.print_listing(['Title', 'Edits', 'Modified'],
                           [(r[0], r[1], self._format_datetime(r[2])) for r in rows])

    def _do_wiki_remove(self, name):
        page = WikiPage(self.env_open(), name)
        page.delete()

    def _do_wiki_import(self, filename, title, cursor=None,
                        create_only=[]):
        if not os.path.isfile(filename):
            raise Exception, '%s is not a file' % filename

        f = open(filename,'r')
        data = to_unicode(f.read(), 'utf-8')

        # Make sure we don't insert the exact same page twice
        rows = self.db_query("SELECT text FROM wiki WHERE name=%s "
                             "ORDER BY version DESC LIMIT 1", cursor,
                             params=(title,))
        old = list(rows)
        if old and title in create_only:
            print '  %s already exists.' % title
            return
        if old and data == old[0][0]:
            print '  %s already up to date.' % title
            return
        f.close()

        self.db_update("INSERT INTO wiki(version,name,time,author,ipnr,text) "
                       " SELECT 1+COALESCE(max(version),0),%s,%s,"
                       " 'trac','127.0.0.1',%s FROM wiki "
                       " WHERE name=%s",
                       cursor, (title, int(time.time()), data, title))

    def _do_wiki_export(self, page, filename=''):
        data = self.db_query("SELECT text FROM wiki WHERE name=%s "
                             "ORDER BY version DESC LIMIT 1", params=[page])
        text = data.next()[0]
        if not filename:
            print text
        else:
            if os.path.isfile(filename):
                raise Exception("File '%s' exists" % filename)
            f = open(filename,'w')
            f.write(text.encode('utf-8'))
            f.close()

    def _do_wiki_dump(self, dir):
        pages = self.get_wiki_list()
        for p in pages:
            dst = os.path.join(dir, urllib.quote(p, ''))
            print " %s => %s" % (p, dst)
            self._do_wiki_export(p, dst)

    def _do_wiki_load(self, dir, cursor=None, ignore=[], create_only=[]):
        for page in os.listdir(dir):
            if page in ignore:
                continue
            filename = os.path.join(dir, page)
            page = urllib.unquote(page)
            if os.path.isfile(filename):
                print " %s => %s" % (filename, page)
                self._do_wiki_import(filename, page, cursor, create_only)

    ## Ticket
    _help_ticket = [('ticket remove <number>', 'Remove ticket')]

    def complete_ticket(self, text, line, begidx, endidx):
        argv = self.arg_tokenize(line)
        argc = len(argv)
        if line[-1] == ' ': # Space starts new argument
            argc += 1
        comp = []
        if argc == 2:
            comp = ['remove']
        return self.word_complete(text, comp)

    def do_ticket(self, line):
        arg = self.arg_tokenize(line)
        if arg[0] == 'remove'  and len(arg)==2:
            try:
                number = int(arg[1])
            except ValueError:
                print>>sys.stderr, "<number> must be a number"
                return
            self._do_ticket_remove(number)
        else:    
            self.do_help ('ticket')

    def _do_ticket_remove(self, number):
        ticket = Ticket(self.env_open(), number)
        ticket.delete()
        print "Ticket %d and all associated data removed." % number


    ## (Ticket) Type
    _help_ticket_type = [('ticket_type list', 'Show possible ticket types'),
                         ('ticket_type add <value>', 'Add a ticket type'),
                         ('ticket_type change <value> <newvalue>',
                          'Change a ticket type'),
                         ('ticket_type remove <value>', 'Remove a ticket type'),
                         ('ticket_type order <value> up|down',
                          'Move a ticket type up or down in the list')]

    def complete_ticket_type (self, text, line, begidx, endidx):
        if begidx == 16:
            comp = self.get_enum_list ('ticket_type')
        elif begidx < 15:
            comp = ['list', 'add', 'change', 'remove', 'order']
        return self.word_complete(text, comp)
 
    def do_ticket_type(self, line):
        self._do_enum('ticket_type', line)
 
    ## (Ticket) Priority
    _help_priority = [('priority list', 'Show possible ticket priorities'),
                       ('priority add <value>', 'Add a priority value option'),
                       ('priority change <value> <newvalue>',
                        'Change a priority value'),
                       ('priority remove <value>', 'Remove priority value'),
                       ('priority order <value> up|down',
                        'Move a priority value up or down in the list')]

    def complete_priority (self, text, line, begidx, endidx):
        if begidx == 16:
            comp = self.get_enum_list ('priority')
        elif begidx < 15:
            comp = ['list', 'add', 'change', 'remove', 'order']
        return self.word_complete(text, comp)

    def do_priority(self, line):
        self._do_enum('priority', line)

    ## (Ticket) Severity
    _help_severity = [('severity list', 'Show possible ticket severities'),
                      ('severity add <value>', 'Add a severity value option'),
                      ('severity change <value> <newvalue>',
                       'Change a severity value'),
                      ('severity remove <value>', 'Remove severity value'),
                      ('severity order <value> up|down',
                       'Move a severity value up or down in the list')]

    def complete_severity (self, text, line, begidx, endidx):
        if begidx == 16:
            comp = self.get_enum_list ('severity')
        elif begidx < 15:
            comp = ['list', 'add', 'change', 'remove', 'order']
        return self.word_complete(text, comp)

    def do_severity(self, line):
        self._do_enum('severity', line)

    # Type, priority, severity share the same datastructure and methods:

    _enum_map = {'ticket_type': Type, 'priority': Priority,
                 'severity': Severity}

    def _do_enum(self, type, line):
        arg = self.arg_tokenize(line)
        if arg[0]  == 'list':
            self._do_enum_list(type)
        elif arg[0] == 'add' and len(arg) == 2:
            name = arg[1]
            self._do_enum_add(type, name)
        elif arg[0] == 'change' and len(arg) == 3:
            name = arg[1]
            newname = arg[2]
            self._do_enum_change(type, name, newname)
        elif arg[0] == 'remove' and len(arg) == 2:
            name = arg[1]
            self._do_enum_remove(type, name)
        elif arg[0] == 'order' and len(arg) == 3 and arg[2] in ('up', 'down'):
            name = arg[1]
            if arg[2] == 'up':
                direction = -1
            else:
                direction = 1
            self._do_enum_order(type, name, direction)
        else:    
            self.do_help(type)

    def _do_enum_list(self, type):
        enum_cls = self._enum_map[type]
        self.print_listing(['Possible Values'],
                           [(e.name,) for e in enum_cls.select(self.env_open())])

    def _do_enum_add(self, type, name):
        cnx = self.db_open()
        sql = ("INSERT INTO enum(value,type,name) "
               " SELECT 1+COALESCE(max(%(cast)s),0),'%(type)s','%(name)s'"
               "   FROM enum WHERE type='%(type)s'" 
               % {'type':type, 'name':name, 'cast': cnx.cast('value', 'int')})
        cursor = cnx.cursor()
        self.db_update(sql, cursor)
        cnx.commit()

    def _do_enum_change(self, type, name, newname):
        enum_cls = self._enum_map[type]
        enum = enum_cls(self.env_open(), name)
        enum.name = newname
        enum.update()

    def _do_enum_remove(self, type, name):
        enum_cls = self._enum_map[type]
        enum = enum_cls(self.env_open(), name)
        enum.delete()

    def _do_enum_order(self, type, name, direction):
        env = self.env_open()
        enum_cls = self._enum_map[type]
        enum1 = enum_cls(env, name)
        enum1.value = int(float(enum1.value) + direction)
        for enum2 in enum_cls.select(env):
            if int(float(enum2.value)) == enum1.value:
                enum2.value = int(float(enum2.value) - direction)
                break
        else:
            return
        enum1.update()
        enum2.update()

    ## Milestone

    _help_milestone = [('milestone list', 'Show milestones'),
                       ('milestone add <name> [due]', 'Add milestone'),
                       ('milestone rename <name> <newname>',
                        'Rename milestone'),
                       ('milestone due <name> <due>',
                        'Set milestone due date (Format: "%s" or "now")'
                        % _date_format_hint),
                       ('milestone completed <name> <completed>',
                        'Set milestone completed date (Format: "%s" or "now")'
                        % _date_format_hint),
                       ('milestone remove <name>', 'Remove milestone')]

    def complete_milestone (self, text, line, begidx, endidx):
        if begidx in (15, 17):
            comp = self.get_milestone_list()
        elif begidx < 15:
            comp = ['list', 'add', 'rename', 'time', 'remove']
        return self.word_complete(text, comp)

    def do_milestone(self, line):
        arg = self.arg_tokenize(line)
        if arg[0]  == 'list':
            self._do_milestone_list()
        elif arg[0] == 'add' and len(arg) in [2,3]:
            self._do_milestone_add(arg[1])
            if len(arg) == 3:
                self._do_milestone_set_due(arg[1], arg[2])
        elif arg[0] == 'rename' and len(arg) == 3:
            self._do_milestone_rename(arg[1], arg[2])
        elif arg[0] == 'remove' and len(arg) == 2:
            self._do_milestone_remove(arg[1])
        elif arg[0] == 'due' and len(arg) == 3:
            self._do_milestone_set_due(arg[1], arg[2])
        elif arg[0] == 'completed' and len(arg) == 3:
            self._do_milestone_set_completed(arg[1], arg[2])
        else:
            self.do_help('milestone')

    def _do_milestone_list(self):
        data = []
        for m in Milestone.select(self.env_open()):
            data.append((m.name, m.due and self._format_date(m.due),
                         m.completed and self._format_datetime(m.completed)))

        self.print_listing(['Name', 'Due', 'Completed'], data)

    def _do_milestone_rename(self, name, newname):
        milestone = Milestone(self.env_open(), name)
        milestone.name = newname
        milestone.update()

    def _do_milestone_add(self, name):
        milestone = Milestone(self.env_open())
        milestone.name = name
        milestone.insert()

    def _do_milestone_remove(self, name):
        milestone = Milestone(self.env_open(), name)
        milestone.delete(author=getpass.getuser())

    def _do_milestone_set_due(self, name, t):
        milestone = Milestone(self.env_open(), name)
        milestone.due = self._parse_date(t)
        milestone.update()

    def _do_milestone_set_completed(self, name, t):
        milestone = Milestone(self.env_open(), name)
        milestone.completed = self._parse_date(t)
        milestone.update()

    ## Version
    _help_version = [('version list', 'Show versions'),
                       ('version add <name> [time]', 'Add version'),
                       ('version rename <name> <newname>',
                        'Rename version'),
                       ('version time <name> <time>',
                        'Set version date (Format: "%s" or "now")'
                        % _date_format_hint),
                       ('version remove <name>', 'Remove version')]

    def complete_version (self, text, line, begidx, endidx):
        if begidx in (13, 15):
            comp = self.get_version_list()
        elif begidx < 13:
            comp = ['list', 'add', 'rename', 'time', 'remove']
        return self.word_complete(text, comp)

    def do_version(self, line):
        arg = self.arg_tokenize(line)
        if arg[0]  == 'list':
            self._do_version_list()
        elif arg[0] == 'add' and len(arg) in [2,3]:
            self._do_version_add(arg[1])
            if len(arg) == 3:
                self._do_version_time(arg[1], arg[2])
        elif arg[0] == 'rename' and len(arg) == 3:
            self._do_version_rename(arg[1], arg[2])
        elif arg[0] == 'time' and len(arg) == 3:
            self._do_version_time(arg[1], arg[2])
        elif arg[0] == 'remove' and len(arg) == 2:
            self._do_version_remove(arg[1])
        else:
            self.do_help('version')

    def _do_version_list(self):
        data = []
        for v in Version.select(self.env_open()):
            data.append((v.name, v.time and self._format_date(v.time)))
        self.print_listing(['Name', 'Time'], data)

    def _do_version_rename(self, name, newname):
        version = Version(self.env_open(), name)
        version.name = newname
        version.update()

    def _do_version_add(self, name):
        version = Version(self.env_open())
        version.name = name
        version.insert()

    def _do_version_remove(self, name):
        version = Version(self.env_open(), name)
        version.delete()

    def _do_version_time(self, name, t):
        version = Version(self.env_open(), name)
        version.time = self._parse_date(t)
        version.update()

    _help_upgrade = [('upgrade', 'Upgrade database to current version')]
    def do_upgrade(self, line):
        arg = self.arg_tokenize(line)
        do_backup = True
        if arg[0] in ['-b', '--no-backup']:
            do_backup = False
        self.db_open()

        if not self.__env.needs_upgrade():
            print "Database is up to date, no upgrade necessary."
            return

        self.__env.upgrade(backup=do_backup)
        print 'Upgrade done.'

    _help_hotcopy = [('hotcopy <backupdir>',
                      'Make a hot backup copy of an environment')]
    def do_hotcopy(self, line):
        arg = self.arg_tokenize(line)
        if arg[0]:
            dest = arg[0]
        else:
            self.do_help('hotcopy')
            return

        # Bogus statement to lock the database while copying files
        cnx = self.db_open()
        cursor = cnx.cursor()
        cursor.execute("UPDATE system SET name=NULL WHERE name IS NULL")

        try:
            print 'Hotcopying %s to %s ...' % (self.__env.path, dest),
            db_str = self.__env.config.get('trac', 'database')
            prefix, db_path = db_str.split(':', 1)
            if prefix == 'sqlite':
                # don't copy the journal (also, this would fail on Windows)
                db_path = os.path.normpath(db_path)
                skip = ['%s-journal' % os.path.join(self.__env.path, db_path)]
            else:
                skip = []
            copytree(self.__env.path, dest, symlinks=1, skip=skip)
        finally:
            # Unlock database
            cnx.rollback()

        print 'Hotcopy done.'


class TracAdminHelpMacro(WikiMacroBase):
    """Displays help for trac-admin commands.

    Examples:
    {{{
    [[TracAdminHelp]]               # all commands
    [[TracAdminHelp(wiki)]]         # all wiki commands
    [[TracAdminHelp(wiki export)]]  # the "wiki export" command
    [[TracAdminHelp(upgrade)]]      # the upgrade command
    }}}
    """

    def render_macro(self, req, name, content):
        if content:
            try:
                arg = content.split(' ', 1)[0]
                doc = getattr(TracAdmin, '_help_' + arg)
            except AttributeError:
                raise TracError('Unknown trac-admin command "%s"' % content)
            if arg != content:
                for cmd, help in doc:
                    if cmd.startswith(content):
                        doc = [(cmd, help)]
                        break
        else:
            doc = TracAdmin.all_docs()
        buf = StringIO.StringIO()
        TracAdmin.print_doc(doc, buf)
        return html.PRE(buf.getvalue(), class_='wiki')


def run(args):
    """Main entry point."""
    admin = TracAdmin()
    if len(args) > 0:
        if args[0] in ('-h', '--help', 'help'):
            return admin.onecmd("help")
        elif args[0] in ('-v','--version','about'):
            return admin.onecmd("about")
        else:
            admin.env_set(os.path.abspath(args[0]))
            if len(args) > 1:
                s_args = ' '.join(["'%s'" % c for c in args[2:]])
                command = args[1] + ' ' +s_args
                return admin.onecmd(command)
            else:
                while True:
                    admin.run()
    else:
        return admin.onecmd("help")


if __name__ == '__main__':
    run(sys.argv[1:])
