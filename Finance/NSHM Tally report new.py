import pandas as pd
import numpy as np
import mysql.connector
import datetime

def fetch_data(instance_name, query):
    # Normalize instance_name to lowercase for consistency
    instance = instance_name.lower()
    if instance == "nshmd":
        db_config = {
            'host': "collpolldb13-read.c5sc77nejhmr.ap-south-1.rds.amazonaws.com",
            'user': "suraj_shetty",
            'passwd': "7uhlKo4yeZ",
            'database': "collpoll_nshmd"
        }
    elif instance == "nshmk":
        db_config = {
            'host': "collpolldb13-read.c5sc77nejhmr.ap-south-1.rds.amazonaws.com",
            'user': "suraj_shetty",
            'passwd': "7uhlKo4yeZ",
            'database': "collpoll_nshmk"
        }
    else:
        raise ValueError("Invalid instance name. Please provide either 'NSHMD' or 'NSHMK'.")
    
    mydb = mysql.connector.connect(**db_config)
    mycursor = mydb.cursor(dictionary=True)
    mycursor.execute(query)
    raw_data = mycursor.fetchall()
    return pd.DataFrame(raw_data)

instance_name = input("Enter the instance name (NSHMD or NSHMK): ")

# Fetch transactions data
transactions = fetch_data(instance_name, '''
SELECT po.ukid, IF(ua.registration_id IS NULL, ps.application_number, ua.registration_id) AS 'applicationNo/registrationId', 
       CONCAT(ua.f_name, ' ', ua.l_name) AS 'Name', 
       IF(p1.programme_name IS NULL, p2.programme_name, p1.programme_name) AS 'Programme', 
       coalesce(p1.duration, p2.duration) as duration, 
       IF(q1.name IS NULL, q2.name, q1.name) AS 'Quota', 
       IF(sp.year_of_joining IS NULL, ps.year_of_joining, sp.year_of_joining) AS 'Batch',
       sp.date_of_joining, po.description AS 'Fee Plan', 
       po.feeType, 
       CASE WHEN po.entity = 'dues_payment' THEN 'dues_payment' 
            WHEN po.entity = 'fee_refund' THEN 'fee_refund' 
            ELSE 'fee_payment' END AS 'Module', 
       CONCAT((CASE WHEN po.entity = 'dues_payment' THEN 'dues_payment' 
                    WHEN po.entity = 'fee_refund' THEN 'fee_refund' 
                    ELSE 'fee_payment' END), "/", (IF(sp.year_of_joining IS NULL, ps.year_of_joining, sp.year_of_joining)), "/", po.idd) as keyy, 
       po.idd as 'fee/due_id', po.mode, po.id payment_order_id, 
       extra.mode as instrument_mode, extra.bank as instrument_bank, 
       DATE_FORMAT(extra.date, '%d-%m-%Y') as instrument_date, 
       extra.ref_no as ref_no, actual_payment_date, 
       CONCAT(ua2.f_name, ' ', ua2.l_name) AS 'Paid By', 
       COALESCE(po.gateway_transaction_id, ' ') 'Transaction Number', 
       pr.id AS 'Receipt Number', po.amount, po.status, po.remarks AS 'remarks', 
       ADDTIME(po.created_timestamp, '05:30:00') AS 'Date', 
       IF(au.is_active = 1, 'Active', 'De-active') AS 'User Status', 
       po.gateway_transaction_id AS 'Transaction id', au.email 
FROM ((SELECT t1.*, t2.student_fee_id as idd, '' AS 'remarks', 'Student Fee' AS 'feeType' 
       FROM (SELECT * FROM payment_order WHERE entity IN ('fee_payment', 'fee_refund')) AS t1 
       LEFT JOIN student_fee_payment_log t2 ON t1.entity_id = t2.id) 
      UNION DISTINCT 
      (SELECT t1.*, t4.id as idd, GROUP_CONCAT(t4.remarks) AS 'remarks', CONCAT(t6.category) AS 'feeType' 
       FROM (SELECT * FROM payment_order WHERE entity = 'dues_payment') AS t1 
       LEFT JOIN dues_payment t2 ON t1.entity_id = t2.id 
       LEFT JOIN dues_payment_mapping t3 ON t2.id = t3.dues_payment_id 
       LEFT JOIN dues t4 ON t4.id = t3.dues_id 
       LEFT JOIN dues_category t6 ON t4.category_id = t6.id 
       LEFT JOIN department t7 ON t4.department_id = t7.department_id GROUP BY t1.id)) AS po 
LEFT JOIN payment_receipt pr ON po.id = pr.order_id 
LEFT JOIN student_profile sp ON po.ukid = sp.ukid 
LEFT JOIN user_attributes ua ON po.ukid = ua.ukid 
LEFT JOIN user_attributes ua2 ON po.paid_by = ua2.ukid 
LEFT JOIN programme p1 ON sp.programme_id = p1.programme_id 
LEFT JOIN quota q1 ON sp.quota_id = q1.id 
LEFT JOIN prospective_student ps ON po.ukid = ps.ukid 
LEFT JOIN programme p2 ON ps.programme_id = p2.programme_id 
LEFT JOIN quota q2 ON ps.quota_id = q2.id 
LEFT JOIN authenticator au ON po.ukid = au.ukid 
LEFT JOIN (
    SELECT id, ukid, IF(mode = "online", online_payment_channel, mode) as mode, 
           COALESCE(cheque_date, neft_date, cash_date, imps_date, dd_date, rtgs_date, upi_date, DATE(processed_timestamp)) AS Date, 
           IF(mode = 'cheque', cheque_date, TIMESTAMP(
               IF(mode = 'demand_draft', dd_date, 
                  IF(mode = 'neft', neft_date, 
                     IF(mode = 'rtgs', rtgs_date, 
                        IF(mode = 'imps', imps_date, 
                           IF(mode = 'pos', pos_date, 
                              IF(mode = 'upi', upi_date, 
                                 IF(mode = 'cash', cash_date, 
                                    IF(mode = 'online', DATE(ADDTIME(modified_timestamp, '05:30:00')), 'NA')
                                 )
                              )
                           )
                        )
                     )
                  )
               )
           )) as actual_payment_date,
           COALESCE(cheque_bank, neft_acc_holder_bank, imps_acc_holder_bank, dd_bank, rtgs_acc_holder_bank, "-") AS Bank, 
           COALESCE(CONCAT(cheque_number, "'"), CONCAT(neft_utr_id, "'"), CONCAT(gateway_transaction_id, "'"), 
                    CONCAT(imps_utr_id, "'"), CONCAT(dd_number, "'"), CONCAT(rtgs_utr_id, "'"), 
                    CONCAT(upi_utr_id, "'"), "-") AS ref_no 
    FROM payment_order WHERE status = 'success'
) extra ON extra.id = po.id 
WHERE po.status = 'success'
''')

# Fetch active demand data
active_demand = fetch_data(instance_name, '''
SELECT au.email, IF(ua.registration_id IS NULL, ps.application_number, ua.registration_id) AS 'applicationNo/registrationId', 
       CONCAT(ua.f_name, ' ', ua.l_name) AS 'Name', 
       IF(p1.programme_name IS NULL, p2.programme_name, p1.programme_name) AS 'Programme', 
       COALESCE(p1.duration, p2.duration) AS Duration, 
       IF(q1.name IS NULL, q2.name, q1.name) AS 'Quota', 
       IF(sp.year_of_joining IS NULL, ps.year_of_joining, sp.year_of_joining) AS 'Batch', 
       IF(d1.department_name IS NULL, d2.department_name, d1.department_name) AS 'Department', 
       IF(au.is_active = 1, 'Active', 'Deactive') AS 'User Status', 
       COALESCE(sp.date_of_joining, '-') AS 'Date of Activated Demand', tab1.ukid, 
       IF(invalidated = 0, COALESCE(applicable_fee, 0.00), '0') AS applicable_fee, 
       IF(invalidated = 0, COALESCE(carry_over, 0.00), '0') AS carry_over, 
       IF(invalidated = 0, COALESCE(penalty_amount, 0.00), '0') AS penalty_amount, 
       IF(invalidated = 0, COALESCE(total_amount, 0.00), '0') AS total_amount, 
       IF(invalidated = 0, COALESCE(total_payable, 0.00), '0') AS total_payable, 
       IF(invalidated = 0, COALESCE(type, '-'), '-') AS type, 
       IF(invalidated = 0, COALESCE(waiver, '-'), '-') AS waiver, 
       Fee_Plan, academic_year, invalidated AS 'Fee Plan not in Use(Invalidated)', 
       isactive AS 'Fee Plan Status', 
       DATE_FORMAT(DATE(due_date), '%d-%m-%Y') AS due_date, sequence, Module, 
       tab1.Scholarship, keyy, tab1.id AS 'fee/due_id', 
       DATE_FORMAT(DATE(tab1.created_timestamp), '%d-%m-%Y') AS 'demandDate' 
FROM (
    SELECT s1.ukid, applicable_fee, carry_over, penalty_amount, total_amount, total_payable, type, 
           COALESCE(waiver, 0.0) AS waiver, Fee_Plan, invalidated, isactive, sequence, due_date, 
           academic_year, Module, Scholarship, keyy, id, created_timestamp 
    FROM (
        SELECT t1.ukid, t1.id AS 'fee_id', applicable_fee, carry_over, t6.amount AS total_amount, 
               t1.total_amount AS total_payable, t1.penalty_amount, t8.name AS 'type', t3.name AS 'Fee_Plan', 
               t1.invalidated, t3.status AS isactive, t2.sequence, t2.due_date, 'Fee Management' AS 'Module', 
               COALESCE(sfc.scholarship, 0) AS 'Scholarship', 
               CONCAT('fee_payment', '/', COALESCE(sp.year_of_joining, ps.year_of_joining), '/', t1.id) AS 'keyy', 
               t1.id, t2.academic_year, t2.activated_on AS created_timestamp 
        FROM student_fee t1 
        LEFT JOIN fee_structure t2 ON t1.fee_structure_id = t2.id 
        LEFT JOIN fee_plan t3 ON t2.fee_plan_id = t3.id 
        LEFT JOIN student_profile sp ON sp.ukid = t1.ukid 
        LEFT JOIN student_fee_component sfc ON sfc.student_fee_id = t1.id 
        LEFT JOIN prospective_student ps ON ps.ukid = t1.ukid 
        LEFT JOIN fee_plan_structure t6 ON t6.fee_plan_id = t3.id 
             AND t6.quota_id = COALESCE(sp.quota_id, ps.quota_id) 
        LEFT JOIN fee_type t8 ON t8.id = COALESCE(t6.fee_type_id, sfc.entity_id) 
        LEFT JOIN student_scholarship t4 ON t1.id = t4.student_fee_id
    ) s1 
    LEFT JOIN (
        SELECT t2.ukid, t1.student_fee_id, SUM(t1.waiver) AS waiver 
        FROM student_fee_component t1 
        LEFT JOIN student_fee t2 ON t1.student_fee_id = t2.id 
        WHERE waiver > 0 
        GROUP BY student_fee_id
    ) s2 ON s1.fee_id = s2.student_fee_id
    UNION DISTINCT 
    SELECT s1.ukid, applicable_fee, carry_over, penalty_amount, total_amount, total_payable, type, 
           COALESCE(waiver, 0.0) AS waiver, Fee_Plan, invalidated, isactive, sequence, due_date, academic_year, 
           Module, Scholarship, keyy, id, DATE(created_timestamp) 
    FROM (
        SELECT t4.ukid, t4.id AS 'due_id', t5.amount AS 'applicable_fee', (t5.amount - coalesce(waived_off_amount,0) + coalesce(penalty_amount,0))  AS total_payable, 
               0 AS 'carry_over', penalty_amount AS 'penalty_amount', (t5.amount - coalesce(waived_off_amount,0) + coalesce(penalty_amount,0)) AS 'total_amount', 
               CONCAT(t6.category) AS 'type', waived_off_amount AS 'waiver', t7.department_name AS 'Fee_Plan', 
               DATE_ADD(t4.created_timestamp, INTERVAL 30 DAY) AS due_date, '-' AS invalidated, '-' AS isactive, 
               sequence_id AS sequence, 'Dues Management' AS 'Module', 0 AS 'Scholarship', 
               CONCAT('dues_payment', '/', spp.year_of_joining, '/', t4.id) AS 'keyy', t4.id, '-' AS academic_year, 
               t4.created_timestamp 
        FROM dues t4 
        LEFT JOIN student_profile spp ON spp.ukid = t4.ukid 
        LEFT JOIN dues_finance t5 ON t4.id = t5.due_id 
        LEFT JOIN dues_category t6 ON t4.category_id = t6.id 
        LEFT JOIN department t7 ON t4.department_id = t7.department_id 
        WHERE t4.due_type = 'financial'
    ) s1
) tab1 
LEFT JOIN student_profile sp ON tab1.ukid = sp.ukid 
LEFT JOIN user_attributes ua ON tab1.ukid = ua.ukid 
LEFT JOIN programme p1 ON sp.programme_id = p1.programme_id 
LEFT JOIN quota q1 ON sp.quota_id = q1.id 
LEFT JOIN prospective_student ps ON tab1.ukid = ps.ukid 
LEFT JOIN programme p2 ON ps.programme_id = p2.programme_id 
LEFT JOIN quota q2 ON ps.quota_id = q2.id 
LEFT JOIN authenticator au ON tab1.ukid = au.ukid 
LEFT JOIN department d1 ON p1.department_id = d1.department_id 
LEFT JOIN department d2 ON p2.department_id = d2.department_id;
''')

# Convert total_amount to numeric to avoid aggregation errors
active_demand['total_amount'] = pd.to_numeric(active_demand['total_amount'], errors='coerce')
active_demand['total_amount'].fillna(0, inplace=True)

# Define the columns you want to fetch for transactions
columns_to_fetch = ['Date', 'actual_payment_date', 'Receipt Number', 'applicationNo/registrationId',
                    'Name', 'Quota', 'Batch', 'User Status', 'Programme', 'duration', 'amount',
                    'Module', 'keyy', 'fee/due_id', 'payment_order_id', 'instrument_mode', 'ref_no',
                    'instrument_bank']

# Select specific columns for transactions
df = transactions[columns_to_fetch]

# Create the pivot table from active_demand using total_amount as the aggregation value
pivot_table = pd.pivot_table(active_demand, 
                             index=['demandDate', 'keyy', 'due_date', 'applicationNo/registrationId', 'Name', 'Quota', 
                                    'Batch', 'User Status', 'Date of Activated Demand', 'Programme', 'Duration', 
                                    'academic_year', 'applicable_fee', 'carry_over', 'penalty_amount', 'waiver', 
                                    'Scholarship', 'total_payable', 'Fee Plan not in Use(Invalidated)', 'sequence', 
                                    'Fee Plan Status'], 
                             columns=['Module', 'type'], 
                             values=['total_amount'])
# Reset the index to ensure demandDate appears as a separate column
pivot_table = pivot_table.reset_index()

# Merge transactions with the due_date from active_demand
merged_df = pd.merge(df, active_demand[['keyy', 'due_date']], on='keyy', how='left')
merged_df = merged_df.drop_duplicates()

# Define the Excel file path to save the data
today_date = datetime.date.today()
formatted_date = today_date.strftime("%d-%m-%Y")
excel_file = 'C:\\Users\\suraj\\OneDrive\\Desktop\\' + instance_name + ' tally reports for ' + formatted_date + '.xlsx'

# Create a new Excel writer object and save the sheets
with pd.ExcelWriter(excel_file) as writer:
    # Write the pivot table (Active Demand data) to the 'Active Demand' sheet
    pivot_table.to_excel(writer, index=True, sheet_name="Active Demand")
    # Write transactions data to the 'Transactions' sheet
    merged_df.to_excel(writer, index=False, sheet_name="Transactions")

print(f"Tally reports have been generated for {instance_name} for {formatted_date} and saved to {excel_file}.")
