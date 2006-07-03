from trac.config import Configuration
from trac.log import logger_factory
from trac.test import Mock, EnvironmentStub
from trac.ticket.query import Query

import unittest


class QueryTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub(default_data=True)
        

    def test_all_ordered_by_id(self):
        query = Query(self.env, order='id')
        sql, args = query.get_sql()
        self.assertEqual(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.milestone AS milestone,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
ORDER BY COALESCE(t.id,0)=0,t.id""")
        self.assertEqual([], args)
        tickets = query.execute(Mock(href=self.env.href))

    def test_all_ordered_by_id_desc(self):
        query = Query(self.env, order='id', desc=1)
        sql, args = query.get_sql()
        self.assertEqual(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.milestone AS milestone,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
ORDER BY COALESCE(t.id,0)=0 DESC,t.id DESC""")
        self.assertEqual([], args)
        tickets = query.execute(Mock(href=self.env.href))

    def test_all_ordered_by_id_verbose(self):
        query = Query(self.env, order='id', verbose=1)
        sql, args = query.get_sql()
        self.assertEqual(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.milestone AS milestone,t.reporter AS reporter,t.description AS description,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
ORDER BY COALESCE(t.id,0)=0,t.id""")
        self.assertEqual([], args)
        tickets = query.execute(Mock(href=self.env.href))

    def test_all_ordered_by_priority(self):
        query = Query(self.env) # priority is default order
        sql, args = query.get_sql()
        self.assertEqual(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.milestone AS milestone,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
ORDER BY COALESCE(t.priority,'')='',priority.value,t.id""")
        self.assertEqual([], args)
        tickets = query.execute(Mock(href=self.env.href))

    def test_all_ordered_by_priority_desc(self):
        query = Query(self.env, desc=1) # priority is default order
        sql, args = query.get_sql()
        self.assertEqual(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.milestone AS milestone,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
ORDER BY COALESCE(t.priority,'')='' DESC,priority.value DESC,t.id""")
        self.assertEqual([], args)
        tickets = query.execute(Mock(href=self.env.href))

    def test_all_ordered_by_version(self):
        query = Query(self.env, order='version')
        sql, args = query.get_sql()
        self.assertEqual(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.version AS version,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
  LEFT OUTER JOIN version ON (version.name=version)
ORDER BY COALESCE(t.version,'')='',COALESCE(version.time,0)=0,version.time,t.version,t.id""")
        self.assertEqual([], args)
        tickets = query.execute(Mock(href=self.env.href))

    def test_all_ordered_by_version_desc(self):
        query = Query(self.env, order='version', desc=1)
        sql, args = query.get_sql()
        self.assertEqual(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.version AS version,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
  LEFT OUTER JOIN version ON (version.name=version)
ORDER BY COALESCE(t.version,'')='' DESC,COALESCE(version.time,0)=0 DESC,version.time DESC,t.version DESC,t.id""")
        self.assertEqual([], args)
        tickets = query.execute(Mock(href=self.env.href))

    def test_constrained_by_milestone(self):
        query = Query.from_string(self.env, 'milestone=milestone1', order='id')
        sql, args = query.get_sql()
        self.assertEqual(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.component AS component,t.time AS time,t.changetime AS changetime,t.milestone AS milestone,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
WHERE COALESCE(t.milestone,'')=%s
ORDER BY COALESCE(t.id,0)=0,t.id""")
        self.assertEqual(['milestone1'], args)
        tickets = query.execute(Mock(href=self.env.href))

    def test_all_grouped_by_milestone(self):
        query = Query(self.env, order='id', group='milestone')
        sql, args = query.get_sql()
        self.assertEqual(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.component AS component,t.milestone AS milestone,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
  LEFT OUTER JOIN milestone ON (milestone.name=milestone)
ORDER BY COALESCE(t.milestone,'')='',COALESCE(milestone.due,0)=0,milestone.due,t.milestone,COALESCE(t.id,0)=0,t.id""")
        self.assertEqual([], args)
        tickets = query.execute(Mock(href=self.env.href))

    def test_all_grouped_by_milestone_desc(self):
        query = Query(self.env, order='id', group='milestone', groupdesc=1)
        sql, args = query.get_sql()
        self.assertEqual(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.component AS component,t.milestone AS milestone,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
  LEFT OUTER JOIN milestone ON (milestone.name=milestone)
ORDER BY COALESCE(t.milestone,'')='' DESC,COALESCE(milestone.due,0)=0 DESC,milestone.due DESC,t.milestone DESC,COALESCE(t.id,0)=0,t.id""")
        self.assertEqual([], args)
        tickets = query.execute(Mock(href=self.env.href))

    def test_grouped_by_priority(self):
        query = Query(self.env, group='priority')
        sql, args = query.get_sql()
        self.assertEqual(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.milestone AS milestone,t.component AS component,t.priority AS priority,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
ORDER BY COALESCE(t.priority,'')='',priority.value,t.id""")
        self.assertEqual([], args)
        tickets = query.execute(Mock(href=self.env.href))

    def test_constrained_by_milestone_not(self):
        query = Query.from_string(self.env, 'milestone!=milestone1', order='id')
        sql, args = query.get_sql()
        self.assertEqual(sql,
"""SELECT t.id AS id,t.summary AS summary,t.milestone AS milestone,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
WHERE COALESCE(t.milestone,'')!=%s
ORDER BY COALESCE(t.id,0)=0,t.id""")
        self.assertEqual(['milestone1'], args)
        tickets = query.execute(Mock(href=self.env.href))

    def test_constrained_by_status(self):
        query = Query.from_string(self.env, 'status=new|assigned|reopened',
                                  order='id')
        sql, args = query.get_sql()
        self.assertEqual(sql,
"""SELECT t.id AS id,t.summary AS summary,t.status AS status,t.owner AS owner,t.type AS type,t.priority AS priority,t.milestone AS milestone,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
WHERE COALESCE(t.status,'') IN (%s,%s,%s)
ORDER BY COALESCE(t.id,0)=0,t.id""")
        self.assertEqual(['new', 'assigned', 'reopened'], args)
        tickets = query.execute(Mock(href=self.env.href))

    def test_constrained_by_owner_containing(self):
        query = Query.from_string(self.env, 'owner~=someone', order='id')
        sql, args = query.get_sql()
        self.assertEqual(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.milestone AS milestone,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
WHERE COALESCE(t.owner,'') LIKE %s
ORDER BY COALESCE(t.id,0)=0,t.id""")
        self.assertEqual(['%someone%'], args)
        tickets = query.execute(Mock(href=self.env.href))

    def test_constrained_by_owner_not_containing(self):
        query = Query.from_string(self.env, 'owner!~=someone', order='id')
        sql, args = query.get_sql()
        self.assertEqual(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.milestone AS milestone,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
WHERE COALESCE(t.owner,'') NOT LIKE %s
ORDER BY COALESCE(t.id,0)=0,t.id""")
        self.assertEqual(['%someone%'], args)
        tickets = query.execute(Mock(href=self.env.href))

    def test_constrained_by_owner_beginswith(self):
        query = Query.from_string(self.env, 'owner^=someone', order='id')
        sql, args = query.get_sql()
        self.assertEqual(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.milestone AS milestone,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
WHERE COALESCE(t.owner,'') LIKE %s
ORDER BY COALESCE(t.id,0)=0,t.id""")
        self.assertEqual(['someone%'], args)
        tickets = query.execute(Mock(href=self.env.href))

    def test_constrained_by_owner_endswith(self):
        query = Query.from_string(self.env, 'owner$=someone', order='id')
        sql, args = query.get_sql()
        self.assertEqual(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.milestone AS milestone,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
WHERE COALESCE(t.owner,'') LIKE %s
ORDER BY COALESCE(t.id,0)=0,t.id""")
        self.assertEqual(['%someone'], args)
        tickets = query.execute(Mock(href=self.env.href))

    def test_constrained_by_custom_field(self):
        self.env.config.set('ticket-custom', 'foo', 'text')
        query = Query.from_string(self.env, 'foo=something', order='id')
        sql, args = query.get_sql()
        self.assertEqual(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.milestone AS milestone,t.time AS time,t.changetime AS changetime,priority.value AS priority_value,foo.value AS foo
FROM ticket AS t
  LEFT OUTER JOIN ticket_custom AS foo ON (id=foo.ticket AND foo.name='foo')
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
WHERE COALESCE(foo.value,'')=%s
ORDER BY COALESCE(t.id,0)=0,t.id""")
        self.assertEqual(['something'], args)
        tickets = query.execute(Mock(href=self.env.href))

    def test_grouped_by_custom_field(self):
        self.env.config.set('ticket-custom', 'foo', 'text')
        query = Query(self.env, group='foo', order='id')
        sql, args = query.get_sql()
        self.assertEqual(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.milestone AS milestone,t.time AS time,t.changetime AS changetime,priority.value AS priority_value,foo.value AS foo
FROM ticket AS t
  LEFT OUTER JOIN ticket_custom AS foo ON (id=foo.ticket AND foo.name='foo')
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
ORDER BY COALESCE(foo.value,'')='',foo.value,COALESCE(t.id,0)=0,t.id""")
        self.assertEqual([], args)
        tickets = query.execute(Mock(href=self.env.href))

    def test_constrained_by_multiple_owners(self):
        query = Query.from_string(self.env, 'owner=someone|someone_else',
                                  order='id')
        sql, args = query.get_sql()
        self.assertEqual(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.milestone AS milestone,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
WHERE COALESCE(t.owner,'') IN (%s,%s)
ORDER BY COALESCE(t.id,0)=0,t.id""")
        self.assertEqual(['someone', 'someone_else'], args)
        tickets = query.execute(Mock(href=self.env.href))

    def test_constrained_by_multiple_owners_not(self):
        query = Query.from_string(self.env, 'owner!=someone|someone_else',
                                  order='id')
        sql, args = query.get_sql()
        self.assertEqual(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.milestone AS milestone,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
WHERE COALESCE(t.owner,'') NOT IN (%s,%s)
ORDER BY COALESCE(t.id,0)=0,t.id""")
        self.assertEqual(['someone', 'someone_else'], args)
        tickets = query.execute(Mock(href=self.env.href))

    def test_constrained_by_multiple_owners_contain(self):
        query = Query.from_string(self.env, 'owner~=someone|someone_else',
                                  order='id')
        sql, args = query.get_sql()
        self.assertEqual(['%someone%', '%someone_else%'], args)
        self.assertEqual(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.milestone AS milestone,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
WHERE (COALESCE(t.owner,'') LIKE %s OR COALESCE(t.owner,'') LIKE %s)
ORDER BY COALESCE(t.id,0)=0,t.id""")
        tickets = query.execute(Mock(href=self.env.href))

    def test_constrained_by_empty_value_contains(self):
        query = Query.from_string(self.env, 'owner~=|', order='id')
        sql, args = query.get_sql()
        self.assertEqual(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.milestone AS milestone,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
ORDER BY COALESCE(t.id,0)=0,t.id""")
        self.assertEqual([], args)
        tickets = query.execute(Mock(href=self.env.href))

    def test_constrained_by_empty_value_startswith(self):
        query = Query.from_string(self.env, 'owner^=|', order='id')
        sql, args = query.get_sql()
        self.assertEqual(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.milestone AS milestone,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
ORDER BY COALESCE(t.id,0)=0,t.id""")
        self.assertEqual([], args)
        tickets = query.execute(Mock(href=self.env.href))

    def test_constrained_by_empty_value_endswith(self):
        query = Query.from_string(self.env, 'owner$=|', order='id')
        sql, args = query.get_sql()
        self.assertEqual(sql,
"""SELECT t.id AS id,t.summary AS summary,t.owner AS owner,t.type AS type,t.status AS status,t.priority AS priority,t.milestone AS milestone,t.time AS time,t.changetime AS changetime,priority.value AS priority_value
FROM ticket AS t
  LEFT OUTER JOIN enum AS priority ON (priority.type='priority' AND priority.name=priority)
ORDER BY COALESCE(t.id,0)=0,t.id""")
        self.assertEqual([], args)
        tickets = query.execute(Mock(href=self.env.href))


def suite():
    return unittest.makeSuite(QueryTestCase, 'test')

if __name__ == '__main__':
    unittest.main()
