import requests
import pandas as pd
import time

# Reading the Excel sheet
df = pd.read_excel('C:/Users/suraj/OneDrive/Desktop/id2.xlsx')

# Iterate ukid over each row from the sheet
for index, row in df.iterrows():
    duesId = row['duesId']

    # API url 
    url = f'https://aimsrchittoor.digiicampus.com/api/dues/v2/studentManagement/cancel'

    # API body for ukid
    body = {
        "duesId": str(duesId)
    }
    
    # API headers and auth token
    authtoken = "eyJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJEaWdpaWNhbXB1cyIsInN1YiI6InVzZXJzLzEzNTE0NTAiLCJ1a2lkIjoxMzUxNDUwLCJ1c2VyVHlwZSI6ImFkbWluaXN0cmF0b3IiLCJpbnRlZ3JhdGlvblJvbGVzIjpbXSwiaW50ZWdyYXRpb25GZWF0dXJlRmxhZ3MiOltdLCJodWJOYW1lIjoiaHViLWFwLXNvdXRoLTEtZGIxOSIsInRlbmFudE5hbWUiOiJhaW1zcmNoaXR0b29yIiwiaW5zdGl0dXRlVXJsIjoiaHR0cHM6Ly9haW1zcmNoaXR0b29yLmRpZ2lpY2FtcHVzLmNvbSIsImNvbGxlZ2VJZCI6MjY0LCJqdGkiOiI4YmM3MmViMi04NzVlLTQyN2UtYmI5ZS1lODM0NzRjNDViMDciLCJpYXQiOjE3ODE1MjQ4NDAsImV4cCI6MTc4MjE0OTQ0MH0.VNzT2CspecK512CC0GigOAA_nv6X0h1CZ_s498YqBASvvPH8M6f3DhOVk4fx45sICDsz81VbNzvNFKRTl49fDKicTVrrQivL6_hlM6Ll90jEdicBvbhAiDXszxitUsWEKmsKzGCI7DJmJvdUy8zyjdhzl12fKGNm4skAC0pSWuY3e82Z6CKZ-51uWeCqqzUD7aXs4J2YheRYihsUf2a_plz-Hn2KIFPgCUMMHpSI6OUWv5urti6GU1RAU55253q61RP8dweXjRu35blj71OcaVcHky8QDUaMylXXxSn7AOgyFjR_Uwp7YGDbv-7zccLsahj6lxIMPNrEcYMAc7zBGg"
    headers = {'Content-type': 'application/json', "auth-token": authtoken}

    # Defining response for POST method
    response = requests.put(url, json=body, headers=headers)
    

    # Check the response code and display success or error message
    if response.status_code == 200:
        print(f"{duesId} was successfully cancelled.")
    else:
        print(f"Cancellation of due id {duesId} was failed with status code {response.status_code}.")

    time.sleep(10)