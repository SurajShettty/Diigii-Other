import requests
import pandas as pd
import time

# Reading the Excel sheet
df = pd.read_excel(r"C:\Users\suraj\OneDrive\Desktop\cred.xlsx")

# Iterate requestID over each row from the sheet
for index, row in df.iterrows():
    classId = int(row['classId'])
    ukid = int(row['ukid'])

    # API url with the requestId
    url = f'https://jiet.digiicampus.com/rest/classGroups/students'    # API body
    body = {
            "classId" : classId,
            "studentUkids" : [int(ukid)]
            }

    # API headers and auth token
    authtoken = "eyJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJEaWdpaWNhbXB1cyIsInN1YiI6InVzZXJzLzEyOTE1NjUiLCJ1a2lkIjoxMjkxNTY1LCJ1c2VyVHlwZSI6ImFkbWluaXN0cmF0b3IiLCJpbnRlZ3JhdGlvblJvbGVzIjpbXSwiaW50ZWdyYXRpb25GZWF0dXJlRmxhZ3MiOltdLCJodWJOYW1lIjoiaHViLWFwLXNvdXRoLTEtZGIxNiIsInRlbmFudE5hbWUiOiJqaWV0IiwiaW5zdGl0dXRlVXJsIjoiaHR0cHM6Ly9qaWV0LmRpZ2lpY2FtcHVzLmNvbSIsImNvbGxlZ2VJZCI6MzgzLCJqdGkiOiIzZmE2ZmQyZC01YWJiLTQyYmMtOTRkYS01ZWQ1ZGI5M2YxNzgiLCJpYXQiOjE3NzUwNjg4ODYsImV4cCI6MTc3NTY5MzQ4Nn0.Vp-IDfN7VethXu-ixu9LyK9a-xm_-s-mFRSPaOMBrT40Vnu4C_l-oyyyOUBY6MfatIOVA9ydwYfG7HL40m2-oK2RPKhMhkPDJV6AxNZWdnNVhOW0eOCELJgo4A07LRuXCSpg-g4CnjDsiPfBbbDZo7NMZ3xjJx8ZpnFA8Srjxq36UCKXXqwINt1T6Twa5WHZZk3Hm2dA4xHjnInZJADnaFxBCueNiecv3YXRbLMzvS1l3q3i_RILM-RV-2jWdjX_7AwSb0vTMo9fwbyP9lassH-0VVOvqXgJC1ytnOGHSQ7nyrY2c4Q7Z-hRY0BhsMe39njFr-MSC3oHxdi2oeO4Rg"
    headers = {'Content-type': 'application/json', "Auth-Token": authtoken}

    # Defining response for POST method
    response = requests.post(url, json=body, headers=headers)
    

    # Check the response code and display success or error message
    if response.status_code == 200:
        print(f"Success! {ukid} has been added to {classId}.")
    else:
        print(f"{ukid} couldnot be added to {classId} with status code {response.status_code}.")

    # Delay of 5 seconds
    time.sleep(1)