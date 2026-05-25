import requests
import pandas as pd
import csv
import json


def implement(value, headers, url):
   try:
       r = requests.post(url, json=value, headers=headers)
       # r.raise_for_status()
       print(r.status_code)
       print(r.text)

   except requests.exceptions.HTTPError as err:
       print(err)


if __name__ == '__main__':

   df = pd.read_excel(r"C:\Users\suraj\Downloads\Templates for scripts and APIs (Excel & csv)\dept add template.xlsx", sheet_name='Sheet1')

   for index, row in df.iterrows():
       body = [{
           "id": "null",
           "category": row["Type (Academic/Non Academic)"],
           "collegeId": 578,
           "name": row['Name'],
           "description": row['Name'],
           "altName": row['Name'],
           "code": row['Code']
       }]

       url = "https://rtc.digiicampus.com/rest/service/departments"
       authtoken = "eyJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJEaWdpaWNhbXB1cyIsInN1YiI6InVzZXJzLzE2ODcxOTkiLCJ1a2lkIjoxNjg3MTk5LCJ1c2VyVHlwZSI6ImNvbGxwb2xsLWFkbWluIiwiaW50ZWdyYXRpb25Sb2xlcyI6W10sImh1Yk5hbWUiOiJodWItYXAtc291dGgtMS1kYjEzIiwidGVuYW50TmFtZSI6InJ0YyIsImluc3RpdHV0ZVVybCI6Imh0dHBzOi8vcnRjLmRpZ2lpY2FtcHVzLmNvbSIsImNvbGxlZ2VJZCI6NTc4LCJqdGkiOiIxY2VlMDc3ZS1iNzFiLTQwYTYtOWI2MC1iMjhhMGFlZjJlODQiLCJpYXQiOjE3NzM2NDQ3ODQsImV4cCI6MTc3NDI2OTM4NH0.UAd-8-5pRTqiI6IoE1jM4jgZFHIRotoO3azS4D--GdeP0CB0zcgBhm8ImsBffZEMvt6OkLtrJ3U9EutG-C7Lp-OkVHEAovlploSw9WmaDE2HuRTJqjYO866zviNPdhd724Mgeg9WraALL4U-TovVZd0AeOwgN6JC8G7f3YhGoFlRZwPom8Ns54mPpdE1N7LBbpid-OM16BccxYIA18mcjjmilnAHLT0jjGHe0DRAkY5sOoILqJg4DtnIP-cszNoZt4ga3LP3_gndY9K-AH-FXDkeVeBgdc1KBwiwWzaje9RqZbgaJ_euFaClXNJPjQ25aXJuvkjRWNSvFauypEVrUw"
       headers = {'Content-type': 'application/json', "Auth-Token": authtoken}

       implement(body, headers, url)
