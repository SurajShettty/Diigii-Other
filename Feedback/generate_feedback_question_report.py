"""
Question-level feedback report (Excel).

One row per session / class / faculty / objective question, with:
  term, class, session_name, course_code, faculty_name, question_id, question_text,
  programme_name, course_name, course_department, course_type, template_name,
  faculty_department_name, faculty_registration_id,
  <one column per option = no. of students who picked it>,
  student_count, student_response_count, average_score

Option columns differ by template, so each template gets its own sheet
(option columns ordered by option_score). Options nobody picked show 0.
"""
import re
from pathlib import Path

import mysql.connector
import pandas as pd

DB_NAME = "collpoll_rec"
OBJECTIVE_QTYPES = ("SINGLE_SELECT", "MULTI_SELECT")


def fetch_data(query):
    mydb = mysql.connector.connect(
        host="collpolldb18-read.c5sc77nejhmr.ap-south-1.rds.amazonaws.com",
        user="suraj_shetty",
        passwd="tttUVwa1nM",
        database=DB_NAME,
    )
    try:
        cur = mydb.cursor(dictionary=True)
        cur.execute(query)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
        return pd.DataFrame(rows, columns=cols)
    finally:
        mydb.close()


def safe_sheet_name(name, used):
    """Excel sheet names: max 31 chars, no []:*?/\\ and must be unique."""
    base = re.sub(r'[\[\]:*?/\\]', '_', str(name)).strip() or "Sheet"
    base = base[:31]
    candidate, n = base, 1
    while candidate.lower() in used:
        suffix = f"_{n}"
        candidate = base[:31 - len(suffix)] + suffix
        n += 1
    used.add(candidate.lower())
    return candidate


ID_COLS = [
    'term', 'class', 'session_name', 'course_code', 'faculty_name', 'question_id',
    'question_text', 'programme_name', 'course_name', 'course_department',
    'course_type', 'template_name', 'faculty_department_name', 'faculty_registration_id',
]
# internal keys used for grouping (names can collide, ids can't)
KEY_COLS = ['session_id', 'class_id', 'faculty_ukid', 'template_id', 'question_id']


if __name__ == "__main__":
    session_id = int(input("Enter Session Id: "))

    # one row per (student, question, chosen option) for submitted objective responses
    responses = fetch_data(f'''
        select fss.session_id, fs.session_name, term.name as term,
               cl.id as class_id, cl.batch as class,
               fcft.faculty_ukid, concat(ua.f_name, ' ', ua.l_name) as faculty_name,
               ua.registration_id as faculty_registration_id,
               fd.department_name as faculty_department_name,
               pr.programme_name, c.course_code, c.course_name,
               cd.department_name as course_department, cl.type as course_type,
               fcft.template_id, ft.template_name,
               fsr.question_id, ftsq.question_text, ftsq.question_type,
               fss.student_ukid, ftqo.id as option_id, ftqo.option_text, ftqo.option_score
        from feedback_student_response fsr
        join feedback_student_template_status fsts on fsts.id = fsr.session_student_template_status_id
        join feedback_session_student fss on fss.id = fsts.student_session_id
        left join feedback_session fs on fs.id = fss.session_id
        left join feedback_course_faculty_template fcft on fcft.id = fsts.feedback_course_faculty_template_id
        left join feedback_template ft on ft.id = fcft.template_id
        left join feedback_template_section_question ftsq on ftsq.id = fsr.question_id
        left join feedback_template_question_option ftqo on ftqo.id = fsr.option_id
        left join class cl on cl.id = fcft.class_id
        left join course c on c.course_id = cl.course_id
        left join department cd on cd.department_id = c.department_id
        left join programme pr on pr.programme_id = cl.programme_id
        left join term on term.id = cl.term_id
        left join faculty_profile fp on fp.ukid = fcft.faculty_ukid
        left join department fd on fd.department_id = fp.department_id
        left join user_attributes ua on ua.ukid = fcft.faculty_ukid
        where fss.session_id = {session_id}
          and fsts.submitted = 1
          and fsr.option_id is not null
    ''')

    if responses.empty:
        print("No objective responses found for this session.")
        raise SystemExit

    responses = responses[responses['question_type'].isin(OBJECTIVE_QTYPES)]
    # same student/question/option recorded twice should only count once
    responses = responses.drop_duplicates(subset=KEY_COLS + ['student_ukid', 'option_id'])

    # all defined options per question (so options nobody picked still get a 0 column)
    template_ids = ",".join(str(int(t)) for t in responses['template_id'].dropna().unique())
    options = fetch_data(f'''
        select fts.feedback_template_id as template_id, ftsq.id as question_id,
               ftqo.id as option_id, ftqo.option_text, ftqo.option_score
        from feedback_template_section fts
        join feedback_template_section_question ftsq on ftsq.template_section_id = fts.id
        join feedback_template_question_option ftqo on ftqo.feedback_question_id = ftsq.id
        where fts.feedback_template_id in ({template_ids})
          and ftsq.question_type in ('SINGLE_SELECT', 'MULTI_SELECT')
        order by fts.feedback_template_id, fts.id, ftsq.id, ftqo.option_score
    ''')
    options['option_text'] = options['option_text'].astype(str).str.strip()
    responses['option_text'] = responses['option_text'].astype(str).str.strip()

    class_strength = fetch_data('''
        select class_id, count(distinct ukid) as student_count
        from class_student
        group by class_id
    ''')

    # ---- per-question aggregates ----
    stats = (
        responses.groupby(KEY_COLS)
        .agg(student_response_count=('student_ukid', 'nunique'),
             total_score=('option_score', 'sum'))
        .reset_index()
    )
    stats['average_score'] = (stats['total_score'] / stats['student_response_count']).round(2)
    stats = stats.drop(columns='total_score')

    # descriptive columns (first value per key)
    info = responses.groupby(KEY_COLS, as_index=False)[[c for c in ID_COLS if c != 'question_id']].first()

    # option counts: distinct students per option text
    counts = (
        responses.groupby(KEY_COLS + ['option_text'])['student_ukid'].nunique()
        .unstack('option_text', fill_value=0)
        .reset_index()
    )

    report = (
        info.merge(counts, on=KEY_COLS, how='left')
            .merge(stats, on=KEY_COLS, how='left')
            .merge(class_strength, on='class_id', how='left')
    )

    # ---- summary: one row per session / class / faculty / template ----
    SUM_KEYS = ['session_id', 'class_id', 'faculty_ukid', 'template_id']
    summary = (
        responses.groupby(SUM_KEYS, as_index=False)
        .agg(**{c: (c, 'first') for c in ['term', 'session_name', 'programme_name', 'template_name',
                                         'class', 'course_name', 'course_code', 'course_type',
                                         'faculty_name', 'faculty_registration_id']},
             student_response_count=('student_ukid', 'nunique'))
        .merge(stats.groupby(SUM_KEYS, as_index=False)['average_score'].mean().round(2),
               on=SUM_KEYS, how='left')
        .merge(class_strength, on='class_id', how='left')
        .sort_values(['term', 'template_name', 'course_code', 'class', 'faculty_name'])
    )
    summary = summary.rename(columns={
        'term': 'Term', 'session_name': 'Session Name', 'programme_name': 'Programme Name',
        'template_name': 'Template Name', 'class': 'Class Group Name', 'course_name': 'Course Name',
        'course_code': 'Course Code', 'course_type': 'Course Component', 'faculty_name': 'Faculty Name',
        'faculty_registration_id': 'Faculty ID', 'student_count': 'Student Count',
        'student_response_count': 'Student Responses Count', 'average_score': 'Avg Score',
    })[['Term', 'Session Name', 'Programme Name', 'Template Name', 'Class Group Name', 'Course Name',
        'Course Code', 'Course Component', 'Faculty Name', 'Faculty ID', 'Student Count',
        'Student Responses Count', 'Avg Score']]

    # ---- write summary tab + one sheet per template ----
    out_dir = Path.home() / "Downloads" / f"{DB_NAME.split('_')[-1]}_{session_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"feedback_question_report_{session_id}.xlsx"
    summary_file = out_dir / f"feedback_summary_report_{session_id}.xlsx"

    summary.to_excel(summary_file, sheet_name='Summary', index=False)
    print(f"Summary: {len(summary)} rows")
    print(f"Summary report saved: {summary_file}")

    question_order = {q: i for i, q in enumerate(options['question_id'].drop_duplicates())}
    used_names = set()

    with pd.ExcelWriter(out_file, engine='openpyxl') as writer:
        for template_id, tdf in report.groupby('template_id', sort=False):
            topts = options[options['template_id'] == template_id]
            # option columns in score order, unique by text (questions in a
            # template usually share a scale; differing scales just add columns)
            opt_cols = (topts.sort_values('option_score')['option_text']
                        .drop_duplicates().tolist())
            # include any answered option text missing from the definition
            opt_cols += [c for c in counts.columns
                         if c not in KEY_COLS and c not in opt_cols and tdf[c].fillna(0).sum() > 0]

            tdf = tdf.copy()
            for c in opt_cols:
                if c not in tdf.columns:
                    tdf[c] = 0
                tdf[c] = tdf[c].fillna(0).astype(int)

            tdf['_q'] = tdf['question_id'].map(question_order)
            tdf = tdf.sort_values(['term', 'course_code', 'class', 'faculty_name', '_q'])

            final_cols = ID_COLS + opt_cols + ['student_count', 'student_response_count', 'average_score']
            sheet = safe_sheet_name(tdf['template_name'].iloc[0], used_names)
            tdf[final_cols].to_excel(writer, sheet_name=sheet, index=False)
            print(f"{sheet}: {len(tdf)} rows, options: {opt_cols}")

    print(f"Question report saved: {out_file}")
