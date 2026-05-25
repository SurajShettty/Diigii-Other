import requests
import pandas as pd
import time

# Reading the Excel sheet
df = pd.read_excel("C:\\Users\\suraj\\OneDrive\\Desktop\\template bulk penalty.xlsx")

# Iterate cluster identifier & masteridentifier over each row from the sheet
for index, row in df.iterrows():
    reg_id = row['registration_id']
    studentFeeId = int(row['studentFeeId'])
    penaltyPlanId = int(row['penaltyPlanId'])
    dueDate = row['dueDate']

    

    # API url
    url = f'https://apollouniversity.digiicampus.com/api/academicFee/v2/penalty/student/add'

    # API body
    body = {
        "studentFeeId": studentFeeId,
        "academicFeePenaltyType": "PENALTY_PLAN",
        "penaltyPlanId": penaltyPlanId,
        "dueDate": dueDate
    }

    # API headers and auth token
    authtoken = "eyJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJEaWdpaWNhbXB1cyIsInN1YiI6InVzZXJzLzQ0NDAwMyIsInVraWQiOjQ0NDAwMywidXNlclR5cGUiOiJjb2xscG9sbC1hZG1pbiIsImludGVncmF0aW9uUm9sZXMiOltdLCJpbnRlZ3JhdGlvbkZlYXR1cmVGbGFncyI6W10sImh1Yk5hbWUiOiJodWItYXAtc291dGgtMS1kYjEzIiwidGVuYW50TmFtZSI6ImFwb2xsb3VuaXZlcnNpdHkiLCJpbnN0aXR1dGVVcmwiOiJodHRwczovL2Fwb2xsb3VuaXZlcnNpdHkuZGlnaWljYW1wdXMuY29tIiwiY29sbGVnZUlkIjoyNjUsImp0aSI6ImE2ZDk3ZTFjLWIwN2ItNDhlYS05NGQ3LTQ1YTI0ZGM4MmVmZCIsImlhdCI6MTc3NjMyMDc4OCwiZXhwIjoxNzc2OTQ1Mzg4fQ.U8Dmad4vOYW1T4BUgnW1vY6yFU07SXkUBILz5YswzXitIiJ58L7ft9lbIXVaAM5CDyXeBr0ZWwPptqotgCDe2qKAPnOLTiCbDmc-8C_9n23b04w8kSxpSJ8LW-dgoka8PF5L46P6yzNAcKmn5ME99GR5_aE4en90Rn-qGbOgqsRnntblfMqYlxYSaolJKlLiEXD_vGDe7dwlqnF0076wEsjRDZIGjgRnmLIBdYdgY8HergYIhJAyxPhEHQC8k8V34DszGrX3rwuGbo7NxNg23dCEqe4edwmlhDKm5QolOiP91cPfeodI7k3OjTlLeVHK9cvhwLAtIeBOwLsdPzkuoQ"
    headers = {'Content-type': 'application/json', "Auth-Token": authtoken}

    # Defining response for PUT method
    response = requests.post(url, json=body, headers=headers)
    # print(studentFeeId, penaltyPlanId, dueDate)

    # Check the response code and display success or error message
    if response.status_code == 200:
        print(f"Penalty successfully applied for registration ID {reg_id}.")
    else:
        print(f"Penalty was not added for registration ID {reg_id} with status code {response.status_code} {response.text}.")

    time.sleep(15)

# select ua.registration_id,ua.ukid,sf.id as feeID from student_fee_v2 sf left join user_attributes ua on ua.ukid = sf.ukid where is_active = 1 and ua.registration_id in ('23BABITS002')
# select * from penalty_plan;