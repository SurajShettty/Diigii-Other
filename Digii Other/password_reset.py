import requests
import pandas as pd

# Reading the Excel sheet
df = pd.read_excel('C:/Users/suraj/Desktop/Book11.xlsx')

# Iterate cluster identifier & masteridentifier over each row from the sheet
for index, row in df.iterrows():
    ukid = row['ukid']
    password = row['password']

    

    # API url
    url = f'https://shooliniuniversity.digiicampus.com/rest/users/admin/password'

    # API body
    body = [
            {
                "ukid": str(ukid),
                "password": str(password)
            }
    ]

    # API headers and auth token
    authtoken = "eyJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwOi8vY29sbHBvbGwuY29tIiwic3ViIjoidXNlcnMvNDMwNjY2IiwidWtpZCI6NDMwNjY2LCJlbWFpbCI6ImFkbWluQGNvbGxwb2xsLmNvbSIsInBob25lIjoiOTEtODEyMzA5NTA2MCIsInVzZXJUeXBlIjoiY29sbHBvbGwtYWRtaW4iLCJ2ZXJpZmljYXRpb25TdGF0dXMiOiIiLCJuYW1lIjoiQ29sbFBvbGwgIEFkbWluIiwiYWRtaW5Sb2xlcyI6WyJBQ0wiLCJBVE0iLCJDU00iLCJFQ1IiLCJFRU0iLCJFRVMiLCJFTVIiLCJFTVMiLCJFVE0iLCJFWE0iLCJGQVciLCJGQ1ciLCJGUkUiLCJGUlYiLCJJQ0wiLCJJTk0iLCJNTUUiLCJNTVYiLCJNU1ciLCJQTEEiLCJQVE0iLCJTUkUiLCJTVVAiLCJVTSIsIlVNRSIsIlVNUyIsIlVQIl0sImV4cCI6MTczNTY1NDM4NX0.N0DRMGzqxzV5HttPCp-R4WbDSvAOlXIVe-lb9nKAQSg"
    headers = {'Content-type': 'application/json', "Auth-Token": authtoken}

    # Defining response for PUT method
    response = requests.put(url, json=body, headers=headers)
    

    # Check the response code and display success or error message
    if response.status_code == 200:
        print(f"Password successfully reset for {ukid}.")
    else:
        print(f"Password reset was unsuccessfull for {ukid} with status code {response.status_code}.")