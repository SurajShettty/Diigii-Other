import numpy as np
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

    df = pd.read_excel(r"C:\Users\suraj\Downloads\Templates for scripts and APIs (Excel & csv)\Programme add Templete.xlsx", sheet_name='Sheet1')
    df = df.fillna(0)
    df['programmeCode'] = df['programmeCode'].astype(str).replace('.0', '')

    for index, row in df.iterrows():

        body = [{"durationYears": int(row["durationYears"]),
                 "durationMonths": None if row["durationMonths"] == "nan" else int(row["durationMonths"]),
                 "durationDays": None if row["durationDays"] is None else int(row["durationDays"]),
                 "programmeName": str(row["programmeName"]),
                 "programmeCode": str(row["programmeCode"]),
                 "yearOfStart": int(row["yearOfStart"]),
                 "programmeTypeId": int(row["programmeTypeId"]),
                 "system": str(row["system"]).lower(),
                 "systemCount": int(row["systemCount"]),
                 "creditSystem": str(row["creditSystem"]),
                 "departmentId": int(row["departmentId"])
                 }]

        url = "https://vitaa.digiicampus.com/rest/structureV2/programme"
        authtoken = "eyJhbGciOiJSUzI1NiJ9.eyJpc3MiOiJEaWdpaWNhbXB1cyIsInN1YiI6InVzZXJzLzE1NzMzNzUiLCJ1a2lkIjoxNTczMzc1LCJ1c2VyVHlwZSI6ImFkbWluaXN0cmF0b3IiLCJpbnRlZ3JhdGlvblJvbGVzIjpbXSwiaW50ZWdyYXRpb25GZWF0dXJlRmxhZ3MiOltdLCJodWJOYW1lIjoiaHViLWFwLXNvdXRoLTEtZGIxIiwidGVuYW50TmFtZSI6InZpdGFhIiwiaW5zdGl0dXRlVXJsIjoiaHR0cHM6Ly92aXRhYS5kaWdpaWNhbXB1cy5jb20iLCJjb2xsZWdlSWQiOjU2NywianRpIjoiYjgyMDBkMzAtMTRlMi00MGRiLWIzNmYtNTJkMTBjNWQ0YjY3IiwiaWF0IjoxNzc4MDc4Njc3LCJleHAiOjE3Nzg3MDMyNzd9.pKZLRRdShykZ_4AbvciMOhueZhoubP7tEX6IflKhEkJue4LZNQ4JNNZEktN-y1veLXbf-PJOAdfndaa3CFvCeC8fvWjX7w-SLAPIXxxB38_O3u3LDPW1GDT_GcZszMth4OoMwmAkhfvya8u0sBoCUnvRONwXhn0wz_eBjudTG0kPqcnTt5COuHJFJvC2aMX5JkRQDb9UPgyLzYD3fAc6jZKrY3XA2vGO4XYuqeBOq57hJF9DN2s6jeQbuI3LwyhjfK_x1DzWLUig8eYNGUDoo9VlwyxXdQzxA6Iv4UIFQxR9X7yenFASvUwXgT-ytruYmxk-8-mF1_RDTTanqYOjfg"
        headers = {'Content-type': 'application/json', "Auth-Token": authtoken}

        implement(body, headers, url)
