import pandas as pd
import mysql.connector
from datetime import datetime
import time

db_config = {
    "host": "collpolldb10-read.c5sc77nejhmr.ap-south-1.rds.amazonaws.com",
    "user": "suraj_shetty",
    "password": "SEaucTgQZg",
    "database": "collpoll_gdgu"
}

conn = mysql.connector.connect(**db_config)

queries = {
    "schema_report": """
        SELECT  c.course_code, ess.name AS schema_name, tc.course_name Active_courses, examination_id, t1.name term, ee.name AS exam_name FROM term_course tc left join ems_examination_course_schema es on es.course_id = tc.course_id LEFT JOIN ems_examination_schema ess ON ess.id = es.examination_schema_id LEFT JOIN course c ON c.course_id = es.course_id LEFT JOIN ems_examination ee ON ee.id = es.examination_id and ee.term_id = tc.term_id LEFT JOIN term t1 on tc.term_id = t1.id where t1.id = 131;
    """,
    "exam_enrolment_due_details": """
        SELECT tc.id, CONCAT(ua.registration_id, '-', tc.course_code) AS `Key`, t1.enrollment_status AS `Enrollment Status`, t.name AS Term_Name, ee.name AS Exam_Name, eet.name AS Exam_Type, ua.registration_id AS Regitration, CONCAT(ua.f_name, ' ', ua.l_name) AS Student_Name, d.department_name AS `Department Name`, p.programme_name AS `Program Name`, tc.course_name AS `Course Name`, tc.course_code AS `Course Code`, t1.type AS `Course Type`, sp.year_of_joining, COALESCE( IF(t1.override_fee_amount IS NULL AND t1.enrollment_status != 'AUTO_ENROLLED', 500, t1.override_fee_amount), 0 ) AS Applicable_Fee, IF( status = 'cleared' AND t1.enrollment_status = 'ENROLLED' AND t1.override_fee_amount IS NULL, 500, IF( status = 'cleared' AND t1.enrollment_status = 'ENROLLED' AND t1.override_fee_amount IS NOT NULL, 5000, 0 ) ) AS `Fees Paid`, IF(dd.status IS NULL AND t1.added_by IS NULL, 'No Dues Found', dd.status) AS Dues_Status, CONCAT(ua1.f_name, ' ', ua1.l_name) AS Added_Explicitly_By FROM ems_student_course_enrollment t1 LEFT JOIN ems_student_programme_enrollment t2 ON t1.student_programme_enrollment_id = t2.id LEFT JOIN term_course tc ON t1.term_course_id = tc.id LEFT JOIN term t ON t.id = tc.term_id LEFT JOIN ems_examination ee ON ee.id = t2.exam_id LEFT JOIN user_attributes ua ON ua.ukid = t2.ukid LEFT JOIN user_attributes ua1 ON ua1.ukid = t1.added_by LEFT JOIN student_profile sp ON sp.ukid = ua.ukid LEFT JOIN department d ON d.department_id = sp.department_id LEFT JOIN programme p ON p.programme_id = sp.programme_id LEFT JOIN ems_examination_type eet ON eet.id = t2.exam_type_id LEFT JOIN dues dd ON dd.id = t1.dues_id WHERE eet.name IN ( 'ETE', 'Theory/practical and jury', 'ETE Practical', 'Internship/Dissertation', 'Viva', 'Research', 'LR Documents' ) AND t1.enrollment_status NOT IN ('NOT_ENROLLED') and t.id = 131;
    """,
    "ext_marks_entry": """
        SELECT t.name AS term_name, dp.department_name AS Course_Department_Name, c.course_name AS Course_Name, c.course_code AS Course_Code, c.course_credits AS Course_Credits, ess.name AS `Schema`, ua.registration_id AS Registration_Id, year_of_joining AS Batch_Year, p.programme_name AS Student_Programme_Name, ec.label AS Label, em.marks, tc.id, t1.term_course_id, t1.type, es.id, COALESCE( COALESCE( GROUP_CONCAT(DISTINCT CONCAT(ua1.f_name, ' ', ua1.l_name) SEPARATOR ', '), GROUP_CONCAT(DISTINCT CONCAT(ua2.f_name, ' ', ua2.l_name) SEPARATOR ', ') ), 'Not Assigned' ) AS Faculty FROM ems_student_course_enrollment t1 LEFT JOIN ems_student_programme_enrollment t2 ON t1.student_programme_enrollment_id = t2.id LEFT JOIN term_course tc ON tc.id = t1.term_course_id LEFT JOIN course c ON c.course_id = tc.course_id LEFT JOIN ems_examination_student_course_grade eg ON eg.course_id = c.course_id AND eg.student_ukid = t2.ukid AND eg.examination_id = t2.exam_id LEFT JOIN ems_examination_course_schema es ON es.course_id = c.course_id AND es.examination_id = t2.exam_id LEFT JOIN ems_examination_schema ess ON ess.id = es.examination_schema_id LEFT JOIN ems_examination_schema_component ec ON ec.ems_examination_schema_id = ess.id LEFT JOIN ems_examination_student_component_marks em ON em.student_ukid = t2.ukid AND em.schema_component_id = ec.id AND em.term_course_id = t1.term_course_id LEFT JOIN user_attributes ua ON ua.ukid = t2.ukid LEFT JOIN student_profile sp ON sp.ukid = ua.ukid LEFT JOIN department dp ON dp.department_id = c.department_id LEFT JOIN programme p ON p.programme_id = sp.programme_id LEFT JOIN ems_examination_course_result_admin ea ON ea.ems_course_schema_id = es.id LEFT JOIN class cc ON cc.course_id = c.course_id LEFT JOIN class_faculty cf ON cf.class_id = cc.id LEFT JOIN user_attributes ua1 ON ua1.ukid = ea.result_admin_ukid LEFT JOIN user_attributes ua2 ON ua2.ukid = cf.faculty_id LEFT JOIN term t ON t.id = tc.term_id WHERE ec.component_type_id IN (1, 2) AND exam_type_id != 1 AND t.id = 131 GROUP BY dp.department_name, c.course_name, c.course_code, c.course_credits, ess.name, ua.registration_id, year_of_joining, p.programme_name, ec.label, em.marks, tc.id, t1.term_course_id, t1.type, es.id, t.name;
    """,
    "curriculum_report": """
        SELECT t9.programme_name, t11.department_name prog_dept, t15.batch_year, t14.sequence AS 'Semester/Year', t5.course_code, d.department_name course_dept, t5.course_name, t5.course_id,t5.course_credits, t.name term_name,t7.name as course_reg_type, COUNT(DISTINCT t3.ukid) AS students_registered, COUNT(DISTINCT cl.id) AS total_class_groups_created, COUNT(DISTINCT cs.ukid) AS students_added_in_class_group,CONCAT(t15.batch_year, '-', t14.sequence) AS concat FROM ams_registration_session_courses t5 LEFT JOIN course_registration_session crs ON crs.id = t5.session_id LEFT JOIN ams_registration_type_clusters t2 ON t2.session_course_id = t5.id LEFT JOIN ams_course_registration_student_courses t1 ON t1.ams_registration_type_cluster_id = t2.id LEFT JOIN ams_course_registration_student t3 ON t1.ams_course_registration_student_id = t3.id LEFT JOIN ams_course_registration_settings acrs ON acrs.id = t3.ams_course_registration_setting_id LEFT JOIN ams_course_registration_student_session t4 ON t1.ams_course_registration_student_session_id = t4.id AND t4.ams_course_registration_student_id = t3.id LEFT JOIN curriculum_cluster_set t6 ON t2.curriculum_cluster_set_id = t6.id LEFT JOIN course_registration_type t7 ON t6.course_registration_type_id = t7.id LEFT JOIN student_profile t8 ON t3.ukid = t8.ukid LEFT JOIN user_attributes t10 ON t10.ukid = t8.ukid LEFT JOIN programme_section t12 ON t8.section_id = t12.programme_section_id LEFT JOIN authenticator t13 ON t8.ukid = t13.ukid LEFT JOIN curriculum_cluster t14 ON t6.curriculum_cluster_id = t14.id LEFT JOIN curriculum t15 ON t14.curriculum_id = t15.id LEFT JOIN programme t9 ON t15.programme_id = t9.programme_id LEFT JOIN department t11 ON t11.department_id = t9.department_id LEFT JOIN department d ON d.department_id = t5.department_id LEFT JOIN programme_specialisation_mapping t16 ON t15.programme_specialisation_mapping_id = t16.id LEFT JOIN specialisation t17 ON t16.specialisation_id = t17.id LEFT JOIN term t ON t.id = crs.term_id LEFT JOIN class cl ON cl.course_id = t5.course_id AND cl.term_id = t.id LEFT JOIN class_student cs ON cs.class_id = cl.id AND cs.ukid = t3.ukid WHERE(is_course_active = 1 OR is_activated_from_curriculum = 1) AND t.id IN (131) GROUP BY t9.programme_name , t11.department_name , t15.batch_year , t5.course_code , t5.course_id , t.id , t5.course_name , t5.course_id , t.name ORDER BY t5.course_id;
    """
}

timestamp = datetime.now().strftime("%d%m%Y_%H%M")
output_file = f"C:\\Users\\suraj\\OneDrive\\Desktop\\Query Data Even Semester 2025-26 {timestamp}.xlsx"

with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
    for sheet_name, query in queries.items():
        df = pd.read_sql(query, conn)
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        time.sleep(5)

conn.close()

print(f"Excel file created successfully: {output_file}")
