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

import re

from trac.core import *
from trac.db.api import IDatabaseConnector
from trac.db.util import ConnectionWrapper

psycopg = None
PgSQL = None
PGSchemaError = None

_like_escape_re = re.compile(r'([/_%])')


class PostgreSQLConnector(Component):
    """PostgreSQL database support."""

    implements(IDatabaseConnector)

    def get_supported_schemes(self):
        return [('postgres', 1)]

    def get_connection(self, path, user=None, password=None, host=None,
                       port=None, params={}):
        return PostgreSQLConnection(path, user, password, host, port, params)

    def init_db(self, path, user=None, password=None, host=None, port=None,
                params={}):
        cnx = self.get_connection(path, user, password, host, port, params)
        cursor = cnx.cursor()
        if cnx.schema:
            cursor.execute('CREATE SCHEMA %s' % cnx.schema)
            cursor.execute('SET search_path TO %s, public', (cnx.schema,))
        from trac.db_default import schema
        for table in schema:
            for stmt in self.to_sql(table):
                cursor.execute(stmt)
        cnx.commit()

    def to_sql(self, table):
        sql = ["CREATE TABLE %s (" % table.name]
        coldefs = []
        for column in table.columns:
            ctype = column.type
            if column.auto_increment:
                ctype = "SERIAL"
            if len(table.key) == 1 and column.name in table.key:
                ctype += " PRIMARY KEY"
            coldefs.append("    %s %s" % (column.name, ctype))
        if len(table.key) > 1:
            coldefs.append("    CONSTRAINT %s_pk PRIMARY KEY (%s)"
                           % (table.name, ','.join(table.key)))
        sql.append(',\n'.join(coldefs) + '\n)')
        yield '\n'.join(sql)
        for index in table.indices:
            yield "CREATE INDEX %s_%s_idx ON %s (%s)" % (table.name, 
                   '_'.join(index.columns), table.name, ','.join(index.columns))


class PostgreSQLConnection(ConnectionWrapper):
    """Connection wrapper for PostgreSQL."""

    poolable = True

    def __init__(self, path, user=None, password=None, host=None, port=None,
                 params={}):
        if path.startswith('/'):
            path = path[1:]
        # We support both psycopg and PgSQL but prefer psycopg
        global psycopg
        global PgSQL
        global PGSchemaError
        
        if not psycopg and not PgSQL:
            try:
                import psycopg2 as psycopg
                import psycopg2.extensions
                from psycopg2 import ProgrammingError as PGSchemaError
                psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)
            except ImportError:
                from pyPgSQL import PgSQL
                from pyPgSQL.libpq import OperationalError as PGSchemaError
        if psycopg:
            dsn = []
            if path:
                dsn.append('dbname=' + path)
            if user:
                dsn.append('user=' + user)
            if password:
                dsn.append('password=' + password)
            if host:
                dsn.append('host=' + host)
            if port:
                dsn.append('port=' + str(port))
            cnx = psycopg.connect(' '.join(dsn))
            cnx.set_client_encoding('UNICODE')
        else:
            cnx = PgSQL.connect('', user, password, host, path, port, 
                                client_encoding='utf-8', unicode_results=True)
        try:
            self.schema = None
            if 'schema' in params:
                self.schema = params['schema']
            cnx.cursor().execute('SET search_path TO %s, public', 
                                (self.schema,))
        except PGSchemaError:
            cnx.rollback()
        ConnectionWrapper.__init__(self, cnx)

    def cast(self, column, type):
        # Temporary hack needed for the union of selects in the search module
        return 'CAST(%s AS %s)' % (column, type)

    def like(self):
        # Temporary hack needed for the case-insensitive string matching in the
        # search module
        return "ILIKE %s ESCAPE '/'"

    def like_escape(self, text):
        return _like_escape_re.sub(r'/\1', text)

    def get_last_id(self, cursor, table, column='id'):
        cursor.execute("SELECT CURRVAL('%s_%s_seq')" % (table, column))
        return cursor.fetchone()[0]

    def rollback(self):
        self.cnx.rollback()
        if self.schema:
            try:
                self.cnx.cursor().execute("SET search_path TO %s, public", 
                                         (self.schema,))
            except PGSchemaError:
                self.cnx.rollback()
