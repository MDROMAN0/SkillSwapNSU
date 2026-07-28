"""
routes/search.py — "Find a partner".

Every filter is optional and every value is bound as a parameter, so the
same statement serves all filter combinations without string concatenation
of user input.
"""

from flask import Blueprint, render_template, request

from db import query
from helpers import categories, current_user, departments, login_required

bp = Blueprint('search', __name__)


@bp.route('/search')
@login_required
def search():
    user = current_user()
    uid = user['user_id']

    f_name = (request.args.get('q') or request.args.get('name') or '').strip()
    f_skill = (request.args.get('skill') or '').strip()
    f_cat = (request.args.get('category') or '').strip()
    f_dept = (request.args.get('department') or '').strip()
    f_level = (request.args.get('level') or '').strip()
    only_match = request.args.get('match') == '1'
    sort_by = request.args.get('sort') or 'match'

    # ---------------- the filtered id list ----------------
    rows = query("""
        SELECT DISTINCT u.user_id
        FROM       users      u
        LEFT JOIN  userskills us ON us.user_id = u.user_id AND us.skill_type = 'Teach'
        LEFT JOIN  skills     s  ON s.skill_id = us.skill_id
        WHERE u.user_id <> %s
          AND (%s = '' OR u.name LIKE %s OR u.department LIKE %s OR s.skill_name LIKE %s)
          AND (%s = '' OR u.department = %s)
          AND (%s = '' OR s.skill_name LIKE %s)
          AND (%s = '' OR s.category = %s)
          AND (%s = '' OR us.proficiency = %s)
    """, (uid,
          f_name, '%' + f_name + '%', '%' + f_name + '%', '%' + f_name + '%',
          f_dept, f_dept,
          f_skill, '%' + f_skill + '%',
          f_cat, f_cat,
          f_level, f_level))

    ids = [r['user_id'] for r in rows]
    results = []

    if ids:
        marks = ','.join(['%s'] * len(ids))

        people = query("""SELECT u.user_id, u.name, u.email, u.department, u.bio,
                                 u.profile_picture, u.created_at,
                                 COALESCE(v.total_reviews, 0) AS total_reviews,
                                 v.avg_rating
                          FROM users u
                          LEFT JOIN v_user_ratings v ON v.user_id = u.user_id
                          WHERE u.user_id IN (%s)""" % marks, tuple(ids))

        # One query for every skill row belonging to the matched students.
        skill_rows = query("""SELECT us.user_id, us.skill_type, us.proficiency,
                                     s.skill_id, s.skill_name, s.category
                              FROM userskills us
                              INNER JOIN skills s ON s.skill_id = us.skill_id
                              WHERE us.user_id IN (%s)
                              ORDER BY s.skill_name""" % marks, tuple(ids))

        my_teach_ids = {r['skill_id'] for r in query(
            "SELECT skill_id FROM userskills WHERE user_id = %s AND skill_type = 'Teach'", (uid,))}
        my_learn_ids = {r['skill_id'] for r in query(
            "SELECT skill_id FROM userskills WHERE user_id = %s AND skill_type = 'Learn'", (uid,))}

        by_user = {i: {'Teach': [], 'Learn': []} for i in ids}
        for row in skill_rows:
            by_user[row['user_id']][row['skill_type']].append(row)

        for person in people:
            teach = by_user[person['user_id']]['Teach']
            learn = by_user[person['user_id']]['Learn']

            hits = teach
            if f_skill:
                hits = [s for s in hits if f_skill.lower() in s['skill_name'].lower()]
            if f_cat:
                hits = [s for s in hits if s['category'] == f_cat]
            if f_level:
                hits = [s for s in hits if s['proficiency'] == f_level]

            they_teach_i_want = [s for s in teach if s['skill_id'] in my_learn_ids]
            they_want_i_teach = [s for s in learn if s['skill_id'] in my_teach_ids]
            matched = bool(they_teach_i_want and they_want_i_teach)

            if only_match and not matched:
                continue

            results.append({
                'u': person,
                'teach': teach,
                'learn': learn,
                'hits': hits if (f_skill or f_cat or f_level) else teach,
                'they_teach_i_want': they_teach_i_want,
                'they_want_i_teach': they_want_i_teach,
                'matched': matched,
                'rating': {'count': int(person['total_reviews'] or 0),
                           'avg': float(person['avg_rating']) if person['avg_rating'] else None},
                'score': len(they_teach_i_want) + len(they_want_i_teach),
            })

    if sort_by == 'rating':
        results.sort(key=lambda r: (-(r['rating']['avg'] or 0), r['u']['name']))
    elif sort_by == 'name':
        results.sort(key=lambda r: r['u']['name'])
    elif sort_by == 'newest':
        results.sort(key=lambda r: r['u']['created_at'], reverse=True)
    else:
        results.sort(key=lambda r: (-r['score'], -(r['rating']['avg'] or 0), r['u']['name']))

    total_others = query('SELECT COUNT(*) - 1 AS n FROM users', one=True)['n']

    my_teach = query("""SELECT s.skill_id, s.skill_name
                        FROM userskills us
                        INNER JOIN skills s ON s.skill_id = us.skill_id
                        WHERE us.user_id = %s AND us.skill_type = 'Teach'
                        ORDER BY s.skill_name""", (uid,))

    return render_template('search.html',
                           results=results, total_others=total_others,
                           my_teach=my_teach,
                           departments=departments(), categories=categories(),
                           all_skills=query('SELECT skill_name FROM skills ORDER BY skill_name'),
                           f={'name': f_name, 'skill': f_skill, 'category': f_cat,
                              'department': f_dept, 'level': f_level,
                              'match': only_match, 'sort': sort_by})
