import requests
import pandas as pd
import time

# Reading the Excel sheet
df = pd.read_excel(r"C:\Users\suraj\Downloads\course_active (1).xlsx")

# Iterate requestID over each row from the sheet
for index, row in df.iterrows():
    requestId = row['requestId']
    courseId = row['courseId']
    courseVersionId = row["courseVersionId"]
    courseName = row['courseName']
    courseCode = row['courseCode']
    programmeId = row["programmeId"]
    programmeName = row['programmeName']
    programmeCode = row['programmeCode']
    batchYear = row["batchYear"]
    sequence = row['sequence']
    curriculumClusterSetId = row['curriculumClusterSetId']


    # API url with the requestId
    url = f'https://gdgu.digiicampus.com/api/courseRegistration/session/courses/{requestId}/manually/activate'

    # API body
    body = [
    {
        "courseId": courseId,
        "courseVersionId": courseVersionId,
        "version": None,
        "courseName": courseName,
        "courseCode": courseCode,
        "courseCredits": None,
        "description": None,
        "departmentId": None,
        "departmentName": None,
        "sessionId": None,
        "id": None,
        "registrationTypeClusterId": None,
        "programmeId": programmeId,
        "programmeName": programmeName,
        "programmeCode": programmeCode,
        "batchYear": batchYear,
        "specialisationMappingId": None,
        "poolId": None,
        "sequence": 1,
        "hasPreRequisites": None,   
        "manuallyActivated": None,
        "isDeleted": None,
        "sessionCourseId": None,
        "specialisationName": None,
        "poolName": None,
        "seatsOffered": None,
        "waitlistAllowed": None,
        "clusterName": None,
        "preRequisites": None,
        "specialisationId": None,
        "curriculumClusterSetId": curriculumClusterSetId,
        "cgpaSgpaRule": None,
        "added": True
    }
]
    # API headers and auth token
    authtoken = "eyJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJEaWdpaWNhbXB1cyIsInN1YiI6InVzZXJzLzM2MjYwNCIsInVraWQiOjM2MjYwNCwidXNlclR5cGUiOiJjb2xscG9sbC1hZG1pbiIsImludGVncmF0aW9uUm9sZXMiOltdLCJodWJOYW1lIjoiaHViLWFwLXNvdXRoLTEtZGIxMCIsInRlbmFudE5hbWUiOiJnZGd1IiwiaW5zdGl0dXRlVXJsIjoiaHR0cHM6Ly9nZGd1LmRpZ2lpY2FtcHVzLmNvbSIsImNvbGxlZ2VJZCI6MjA5LCJqdGkiOiJhMjA5M2UyYS1lOWE0LTRlMzktOTdhZS0zY2QyMzQ1MGU4MGEiLCJpYXQiOjE3NzQyNTQ3MzYsImV4cCI6MTc3NDg3OTMzNn0.S_rjShyD0a4c1fC4y947r9tOza6UFU4arq5wFURkTrRw5n9I228hJdvjV3E-IbRslFapHJj-vsKsrxfFY-8islBwRnftrVKyhImack0-WStO9ri_YrE5ARlXOgcAJ2iO_xlsyLij_vdc_bleCca5iYe7_IEqAKRz314mswpkTiQr0bC1iflrgSK5oKNLxCg95ytmrmzWyk7SKgNUpGbHT8wb-j-8TWGxamKO7Q6MaJkMSGzz7Wf2W9_0_xPeq6IHKn1Anpd0nkvxx0tEM6EGxaSFh8bvb2j4wnxOEee9mG_dNLpalxv_nX3WmqOim-ROj1ITtWPw9maWU91IDX7Pug"
    headers = {'Content-type': 'application/json', "Auth-Token": authtoken}

    # Defining response for POST method
    response = requests.put(url, json=body, headers=headers)
    

    # Check the response code and display success or error message
    if response.status_code == 200:
        print(f"Request with requestId {requestId} was successful.")
    else:
        print(f"Request with requestId {requestId} failed with status code {response.status_code} | {response.text}.")

    time.sleep(2)