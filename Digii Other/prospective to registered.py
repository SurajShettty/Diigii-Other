import requests
import pandas as pd
import numpy as np
import mysql.connector
from mysql.connector import Error
import json

def fetch_data(query):
    mydb = mysql.connector.connect(
        # host="collpolldb6.c5sc77nejhmr.ap-south-1.rds.amazonaws.com",
        # user="read_isbr",
        # passwd="nImoTmEM",
        # database="collpoll_isbr"
        host="digiicommondbinstance.c5sc77nejhmr.ap-south-1.rds.amazonaws.com",
        user="read_demo",
        passwd="Pko0lum",
        database="collpoll_demo"
    )

    mycursor = mydb.cursor(dictionary=True)
    mycursor.execute(query)
    raw_data = mycursor.fetchall()
    return pd.DataFrame(raw_data)
    

# Reading the Excel sheet to get email IDs
emails_df = pd.read_excel('C:/Users/Suraj Shetty/OneDrive/Desktop/ss.xlsx')

# Extracting email IDs and formatting them for SQL query
email_list = emails_df['email'].tolist()
formatted_emails = ', '.join(f"'{email}'" for email in email_list)

# keeping teh email IDs in the WHERE clause
query = f'''
SELECT  a.email, ps.ukid, sac.id AS categoryId 
FROM prospective_student ps 
LEFT JOIN student_admission_category sac 
    ON sac.programme_id = ps.programme_id 
    AND sac.batch = ps.year_of_joining 
    AND sac.quota_id = ps.quota_id 
LEFT JOIN authenticator a 
    ON a.ukid = ps.ukid 
WHERE a.email IN ({formatted_emails})
'''

# fetching data from query to df
df = fetch_data(query)

# Define the API URL and headers
url = 'https://demo.digiicampus.com/rest/admission/prospectiveStudentToStudent?changeAdmissionFormStatus=true&dateOfJoining=2024-12-24'
authtoken = "eyJlbmMiOiJBMjU2R0NNIiwiYWxnIjoiZGlyIn0..slI31Mr78A_m8fOK.TlZMwUsBJmIAFcsudFXeTolAJEcwoobRyHxnVOA15kiGD_d110ioMTPOeal4IxG6eDufWenCSUXnuqtvKVFHSEUdfrSZ-noITAL4X80GePwNROkdeE_617YrBcZkLr38-1cewno71StShfnH3a8TlpH6IHIX9wZYMMJeh2kR_l7ElekeGRc2tzpO1Axr9YXcCTK6TN7jK3LNQkd0Fg3K4deYaSD5CjMkQuPDrg4Q8VUbnZQLKnSBFhi6UaMlIq2yAUfL1vcgJRG9yb9PmCVYhtI4mjQk_rwvZWAL4zvaE96GA1TguzjjoAxl0LBBW3Fb3XtUFvDWBp7Kv0cHsa4rln6W_YyJ5SZjS9qz3qtd8gamchcERy-c4Sw9vegHIBJpKRwirydsNFYXRT8jeM9xwfO3cQeY9K1WD2sCrthL0sgRsltJtg0RsxvrQ_5yxlStM4TqPLxzLFN9u1fbprjJRFnax-4CKDUG2nj286dagFhNKGhDJu1QDKZMt_wuFENvtOnYaQT7CZ0s_y7NqiAw3OmgxdCb8b39X4xjmcd_cyn9NpP1WX12PewEOPS6QmXoJzrw5HVL5sXvUMSt_aWtTeihz0oNfiG8-voi7IEJBr4tuZROMT1Yt7Wjw5-nuIu3MhWNT6EBWky40AnB0lNeHR64BHgm3kdTd_pa_yeVd1Q9BnvDlaZl8oRBuw7AAwIhhz-LuNDgNnhqt9yqGUG2DIbrHrU0it288cXyO2_tlkEhrWUELPmsIgnqFrL88z7mQGyYihJ08f-s1YLswBcMvjn3aEFTJryG7OoT0zDlGoeWn9vZQFNfKCntk10acMCtjRTanI1QnymZ5a3G3nMHTwo5s8t1mGRQzR98kj1Pk3UufmMGuWqWXNnmtNmOjxLNuiodlZX0TpJq6uL6cr66B9AbwJ99hgzmJROQXlmX_NATZyDLWe8d91tRT7Si_Lx6ycSSb0vDaWei225K47IWvUqqZg87y8CZhLfYZbhyPfIfBQ_F5JQvEwX7x0doWO4oDLUG5FwORxoWfHzht64WRqGMwM4dfxcq_NZKo__ZE8OqQiEOFd54s8femzXab25jaxKPuPNMykSINvjYLqn0Ii_y0FMXQRjC6ABS4nkpoGbVzkhR_PFlo893eUV-Tu2gepjTJFRYq1AyKIPYmf6yROnPg5S_kifHCU_67_yJtH_0SqprnbZwHIPbhqEokW5U-tK2EWwAZrt8F69xlk3kC4WaEvuFrGEd9vHF7fGDbQhKNis-N6Z5IkZXk13kooJ74cOThg16dhFolLAK39zhIiQgCCtOfxqk6vL1M6C56KOcaEuvFoEiFaKrOvSwOACMWs3sRZA1agFxVaIw8tvcT8P-wq3G1zno2LSjEVWq9Bgs2mkrkBxGza_fxV0gaT3QTrovO8aANpb6VENTr-MDN9u3RO1Mu4DCRmssPiQULu64oIYtOc23Bi38BqdWx1RxCujBbfXl4Yrx1885jY7O4TlmyuRdnde0F7jbCd_5VS00FWOuSoliQXv-Gw0ip445bmNrxme7JZwW_rCmEWkBY7rbQSW3I4HAcZs-vXVrjbMqiHwGauPQaUhxdwtYG12YWRoE7wpgJ6N_0gDktpIyJtqGDjJ1aFyREFumifshGLER9FoB0w2Dce26iJhMqxDZnVuaSmQfIgnHkPpwoLXiEOJ0TSBjScjGp0VTjgzJxrV3gYwAqh2SZtJF4seIpnrcG9Tm3i5hqmEmpF4-doVEnrshtPkfIgPJpnRKssvVa60OfOdcqD_JlR7acNnWE3GaT09ZlBdYN-Iu8emJRboTx3aKw6BoOjd7JYae3stxxIlu4Cg4JTChLDztSVqpIvrwbsA97Oew0mCR0a6RhWBFTni-4LSJxt22LlVJt3l6c6bT9UauTH8kKClJ9oeGE5p9od3kWUoZrtM5p9Xajq4HHMCeNty9gEyaV-4-aEqt2Glkw5tK7UEwKz8ka-NdmSrkHmgYdsc1MB7fjnX290sM7YTNMlfni8Xq7xcW4O9xEkVVlg6YxIA_.5RIBm5QyBWuLD-2QmzBLZA"
headers = {'Content-type': 'application/json', "Auth-Token": authtoken}

# Create an empty list to store error messages
error_logs = []

# Iterate over each row in the dataframe and send API requests
for index, row in df.iterrows():
    email = row['email']
    ukid = row['ukid']
    categoryId = row['categoryId']

    # API body
    body = {
        "students": [
            {
                "ukid": ukid,
                "categoryId": categoryId
            }
        ]
    }

    # Send the PUT request
    response = requests.put(url, json=body, headers=headers)

    # Check the response code and add custom message or response message to error_logs
    if response.status_code == 200:
        error_logs.append((email, "Successfully registered as a student."))
    else:
        try:
            response_json = response.json()
            message = response_json.get('message', 'No message')
        except json.decoder.JSONDecodeError:
            message = 'Error decoding JSON response'
        error_logs.append((email, message))

# Create DataFrame from error_logs list
error_df = pd.DataFrame(error_logs, columns=['Email', 'Message'])

# Save error logs to Excel
error_df.to_excel('C:/Users/Suraj Shetty/OneDrive/Desktop/output.xlsx', index=False)