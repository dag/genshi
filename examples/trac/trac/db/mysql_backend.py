# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005-2006 Edgewall Software
# Copyright (C) 2005-2006 Christopher Lenz <cmlenz@gmx.de>
# Copyright (C) 2005 Jeff Weiss <trac@jeffweiss.org>
# Copyright (C) 2006 Andres Salomon <dilinger@athenacr.com>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://trac.edgewall.com/license.html.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://projects.edgewall.com/trac/.

import re

from trac.core import *
from trac.db.api import IDatabaseConnector
from trac.db.util import ConnectionWrapper

_like_escape_re = re.compile(r'([/_%])')


class MySQLConnector(Component):
    """MySQL database support for version 4.1 and greater.
    
    Database urls should be of the form:
        mysql://user[:password]@host[:port]/database
    """

    implements(IDatabaseConnector)

    def get_supported_schemes(self):
        return [('mysql', 1)]

    def get_connection(self, path, user=None, password=None, host=None,
                       port=None, params={}):
        return MySQLConnection(path, user, password, host, port, params)

    def init_db(self, path, user=None, password=None, host=None, port=None,
                params={}):
        cnx = self.get_connection(path, user, password, host, port, params)
        cursor = cnx.cursor()
        from trac.db_default import schema
        for table in schema:
            for stmt in self.to_sql(table):
                self.env.log.debug(stmt)
                cursor.execute(stmt)
        cnx.commit()

    def _collist(self, table, columns):
        """Take a list of columns and impose limits on each so that indexing
        works properly.
        
        Some Versions of MySQL limit each index prefix to 500 bytes total, with
        a max of 255 bytes per column.
        """
        cols = []
        limit = 500 / len(columns)
        if limit > 255:
            limit = 255
        for c in columns:
            name = '`%s`' % c
            table_col = filter((lambda x: x.name == c), table.columns)
            if len(table_col) == 1 and table_col[0].type.lower() == 'text':
                name += '(%s)' % limit
            # For non-text columns, we simply throw away the extra bytes.
            # That could certainly be optimized better, but for now let's KISS.
            cols.append(name)
        return ','.join(cols)

    def to_sql(self, table):
        sql = ['CREATE TABLE %s (' % table.name]
        coldefs = []
        for column in table.columns:
            ctype = column.type
            if column.auto_increment:
                ctype = 'INT UNSIGNED NOT NULL AUTO_INCREMENT'
                # Override the column type, as a text field cannot
                # use auto_increment.
                column.type = 'int'
            coldefs.append('    `%s` %s' % (column.name, ctype))
        if len(table.key) > 0:
            coldefs.append('    PRIMARY KEY (%s)' %
                           self._collist(table, table.key))
        sql.append(',\n'.join(coldefs) + '\n)')
        yield '\n'.join(sql)

        for index in table.indices:
            yield 'CREATE INDEX %s_%s_idx ON %s (%s);' % (table.name,
                  '_'.join(index.columns), table.name,
                  self._collist(table, index.columns))


class MySQLConnection(ConnectionWrapper):
    """Connection wrapper for MySQL."""

    poolable = True

    def _mysqldb_gt_or_eq(self, v):
        """This function checks whether the version of python-mysqldb
        is greater than or equal to the version that's passed to it.
        Note that the tuple only checks the major, minor, and sub versions;
        the sub-sub version is weird, so we only check for 'final' versions.
        """
        from MySQLdb import version_info as ver
        if ver[0] < v[0] or ver[1] < v[1] or ver[2] < v[2]:
            return False
        if ver[3] != 'final':
            return False
        return True

    def _set_character_set(self, cnx, charset):
        vers = tuple([ int(n) for n in cnx.get_server_info().split('.')[:2] ])
        if vers < (4, 1):
            raise TracError, 'MySQL servers older than 4.1 are not supported!'
        cnx.query('SET NAMES %s' % charset)
        cnx.store_result()
        cnx.charset = charset

    def __init__(self, path, user=None, password=None, host=None,
                 port=None, params={}):
        import MySQLdb

        if path.startswith('/'):
            path = path[1:]
        if password == None:
            password = ''
        if port == None:
            port = 3306

        # python-mysqldb 1.2.1 added a 'charset' arg that is required for
        # unicode stuff.  We hack around that here for older versions; at
        # some point, this hack should be removed, and a strict requirement
        # on 1.2.1 made.  -dilinger
        if (self._mysqldb_gt_or_eq((1, 2, 1))):
            cnx = MySQLdb.connect(db=path, user=user, passwd=password,
                                  host=host, port=port, charset='utf8')
        else:
            cnx = MySQLdb.connect(db=path, user=user, passwd=password,
                                  host=host, port=port, use_unicode=True)
            self._set_character_set(cnx, 'utf8')
        ConnectionWrapper.__init__(self, cnx)

    def cast(self, column, type):
        return 'CAST(%s AS %s)' % (column, type)

    def like(self):
        return "LIKE %s ESCAPE '/'"

    def like_escape(self, text):
        return _like_escape_re.sub(r'/\1', text)

    def get_last_id(self, cursor, table, column='id'):
        return self.cnx.insert_id()
