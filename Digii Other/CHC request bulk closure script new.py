import requests
import pandas as pd
import numpy as np
import mysql.connector
from mysql.connector import Error
import json
import time
from datetime import datetime


def fetch_data(query):
    mydb = mysql.connector.connect(
        host="collpolldb11-read.c5sc77nejhmr.ap-south-1.rds.amazonaws.com",
        user="suraj_shetty",
        passwd="pTXr8yJmOR",
        database="collpoll_nlsiu"
    )

    mycursor = mydb.cursor(dictionary=True)
    mycursor.execute(query)
    raw_data = mycursor.fetchall()
    return pd.DataFrame(raw_data)

query = f'''
select service_id,cwca.id as action_id,cr.id as request_id from 
chc_request cr left join chc_work_centre_action cwca on cwca.work_centre_id = cr.work_centre_id 
where service_id in (61) and status = 'submitted' '''

df = fetch_data(query)

# Iterate requestID over each row from the sheet
for index, row in df.iterrows():
    requestId = row['request_id']
    actionId = int(row['action_id'])


    # API url with the requestId
    url = f'https://nls.digiicampus.com/rest/campusHelpCentre/requests/{requestId}/actions'

    # API body
    body = {
        "actionId": actionId
    }

    # API headers and auth token
    authtoken = "eyJlbmMiOiJBMjU2R0NNIiwiYWxnIjoiZGlyIn0..H25SbqwlTAfftNDY.M7IqEViHlMeWWkx8Ekl33fvYLWrXp6Gu_bfdcmOp8pciLm-YpK8P_U_5imXF-bTaagsUxfktDGjOjHuyph9CejnHEEJSlDOLPiq8e4jlPhwoNs72Mfowzv8QRcs9JVpvWOf0DXJinRIrpblCanNlrRjcf6O8L89w6Gp-ykGBgSGFpqladkAPdxqUQhdxdeu3GHNo5o1bLZGGznnThzoXpQ40YmBdNQlnfTipp7s4Vk7PtK3rd8LCg658eIwPK2Xj-yIo8Ww80rTLx9O1eu1VGN5wS3gn2BWsmdOkcO3tboEurpAmQuwh9c6U1hKow1MDxefWOCW0aeoxFFaIn82ScvpRyS_ZHpo2Ozf_GStgfzOSBgJxOZNSvsNvI8BUrvmaKK4cGZe81LS6fYIhfkpidOmzYEFm5tejVBzni62R_kH77ZKP6K-yLnuww0EQpRVrst6U6f_1wl7rtZU6lJRkiUVrxyoP8gWLlfE7xkRvo_vNikDGU2xu60CYtAkieGCnXdKCzZRCZE5FlXefiSpjGF9VblokvHD1XBf1IBIDdC7_ZBK7g6gtL3SFP8CVhE-Ok-lYAIiYXf6aR3x4tuBvp9kN2a35U5dUWjATbiYLh0ukycBtTmMbWEYxjZsqSvSXTjPeqaiEeRQdAc9pEuD40bMZATof_GQwecFrO6_fL4LCtq93Bcp688Bkk19OoU_pKBt9a6dAyNgNRbgYf44p3nIm5KG08i7erjSHQ-iL_4hoHAX-Oh8bQonYah6cva1L5LWdINAyatzyFcLJ341ZHQBkbkzHB1aH4kA7ileX6ToDvKns-4egE_Led2dyFThofpoPSBXzqdG4G_MqmlfMH-A8Z1tySb97dg-tk4JMzvX6HWY2nlyIHF-8yO-RAH_V_1NZM6LX3YxYz1U0RnhquIIab3K1lQBvEA1tevBeDm5y-lIJ_WSEJBWLk0dabdC_j5-SXGF1EG-fwwpsp-Z-WoUuuCrUkd-5LnuyXzBB8KysRc8MO8Aov9wBTiUbLjCRDD1tROakcbswB_UO97joNjprzfHDKiJBmQsH77ZVsS_mi7On_VKqYdSY_fJsYzTMdbjHdrWiCVsyw8Lf1s7xdgBzd_kN5RBSOlzsHANfN2FuXNHnrUSjHoDqgjT8ZVoSLL9Uo7P9UTK956EY6xDmUqxJwRQ.3nt9r_bNq5rJKagXnFRNkA"
    headers = {'Content-type': 'application/json', "Auth-Token": authtoken}

    # Defining response for POST method
    response = requests.post(url, json=body, headers=headers)
    

    # Check the response code and display success or error message
    if response.status_code == 200:
        print(f"Request with requestId {requestId} was successful.")
    else:
        print(f"Request with requestId {requestId} failed with status code {response.status_code}.")

# select service_id,cwca.id as action_id,cr.id as request_id from chc_request cr left join chc_work_centre_action cwca on cwca.work_centre_id = cr.work_centre_id where service_id in (61) and status = 'submitted';
# service 61 login & password - bhavana.n@digiicampus.com - Digii@2027