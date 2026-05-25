import requests
import pandas as pd

# Reading the Excel sheet
df = pd.read_excel('C:/Users/suraj/Desktop/Book1.xlsx')

# Iterate cluster identifier & masteridentifier over each row from the sheet
for index, row in df.iterrows():
    ukid = row['ukid']
    # userVerificationBits = row['userVerificationBits']
    # status = row['status']
    

    # API url
    url = f'https://ju.digiicampus.com/rest/users/admin/authenticationStatus?='

    # API body
    body = [
            {
                "ukid": str(ukid),
                "userVerificationBits": 3,
                "status": "RE"
            }
    ]

    # API headers and auth token
    authtoken = "eyJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwOi8vY29sbHBvbGwuY29tIiwic3ViIjoidXNlcnMvNzc5MTY3IiwidWtpZCI6Nzc5MTY3LCJlbWFpbCI6ImFkbWluQGNvbGxwb2xsLmNvbSIsInBob25lIjoiOTEtODEyMzA5NTA2MCIsInVzZXJUeXBlIjoiY29sbHBvbGwtYWRtaW4iLCJ2ZXJpZmljYXRpb25TdGF0dXMiOiIiLCJuYW1lIjoiQ29sbFBvbGwgIEFkbWluIiwiYWRtaW5Sb2xlcyI6WyJBQ0wiLCJBUkQiLCJBVE0iLCJDQ1MiLCJFQ1IiLCJFRU0iLCJFRVMiLCJFTVIiLCJFTVMiLCJFVE0iLCJFWE0iLCJGUkUiLCJQVE0iLCJTVVAiLCJVTSIsIlVNRSJdLCJleHAiOjE3MjQ5NDQ3NDV9.K2PqMy-8QcodoBsqoKBMx8tBwhyQGzPsdw3VQOt5qCM"
    headers = {'Content-type': 'application/json', "Auth-Token": authtoken}

    # Defining response for PUT method
    response = requests.put(url, json=body, headers=headers)
    

    # Check the response code and display success or error message
    if response.status_code == 200:
        print(f"Verification bit successfull for {ukid}.")
    else:
        print(f"Verification bit unsuccessfull for {ukid} with status code {response.status_code}.")