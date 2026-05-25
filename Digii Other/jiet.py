import requests
import pandas as pd
import time

# Reading the Excel sheet
df = pd.read_excel("C:\\Users\\suraj\\Downloads\\cred - Copy.xlsx")

# Iterate requestID over each row from the sheet
for index, row in df.iterrows():
    classId = int(row['classId'])
    ukid = int(row['ukid'])

    # API url with the requestId
    url = f'https://jiet.digiicampus.com/rest/classGroups/students'

    # API body
    body = {
            "classId" : classId,
            "studentUkids" : [int(ukid)]
            }

    # API headers and auth token
    authtoken = "eyJlbmMiOiJBMjU2R0NNIiwiYWxnIjoiZGlyIn0..Ubpv4AtzymQhRmN1.DBU3wmf5szdwhwWN6-SDgpa7LS_WcBUpD7SlfAx9jt6a-GhfvvsvdLT2Oc9oCGrF6Tgo1bUbeoz4H7CAi3hucxEmKNxfs35JdVLI8gt1eaANP_sr55aowTBc2yWMbpMrChFJ_NZ1kzM5bOWU31EGoMPLV6QjAH9QJ-motWnddcokiVVkiQ8Y7yQ1yzur-S-voW5q6TCxGY0xRZ8GQATpWMRrUvfhnNP7jjOa5LcLvf5Bn4dzvoo23XltYPTsQZd2z5omfpwtcObPnyOmiB8Ptbxo_HLIlOm1RDccB56WoptdF8ytebPjaFIKZ1OjNlqTlzvk6WwSFMBI0jKPQwkKv5p41d3zzBXLVEqmOCKx-U3OpSUryDNGu02fepGjCBprhgJWKPKy5__mfvBtH9eA0EEZ3JAOrdtBLjWqFoPpzBMaLsC6pMVRrZNqLYCdnVNi3JugLj2LRtxfooyfR6lHJX6oENC0IdPW84ukb0ACOi2SV1UQYXdhgcySsalOXsKAPITgUt557TsiKxvE-nurafnumtMeguztLMitrhuPPhUNUcXcaNOxXpaxdhe1bYsBXkXuWJDdWp_Oo-cFfuZdASNboAoEHOyUPrqcMPQ-Hk-p0BUngY8pY0RzyM1g07EmagdZk4x2vUf99KL8UTN7IHdWcyxqHlKvNGJmv36Swp1nnyReUJRtOgO3hZr8QJAwFBYzkFm4MnpaY8aSgAtQquhRnTpP5iyqzf-ze-kiamPxdaOt7a5P6vbsPHa5ZpuLKcgK30gcR9znsEkv6QPN-GBcXvjFjASA4FyYV_zfSogOYzIJzb-W1bscFOvmF5ArVv1wqGRuJG8ZJA6rmxgwTCW_4v_Rs8v5CR-qDXHQtSqC0k_NaEcQeYsV8rVDiUXMXY9W5sDYbW_ys3aUmiVnG3rB_OxCbIrV_1jRK50PyUfDHTHr5ZqQG0l7Tl6wmfntASnN7MglXFRhbdJ7z73rLjXUmUGjj8BhZTj1aUPz9ewok1A_tiNKoOmV9BNk7Ok1d08h7r2XhWkooNKMIvQ83Ujn-jNoWc_LzdSvS9c8MSZu_s26AFNuF_zXMfdN7lGZkaudn_JzuZcjmDHwKEP-WA7-lrHsIxi1mej62R3Mg1QW4jP4kqez1KbAbGHeT5arPzOEjZXjPyUZrJ6E8cQygUxzx0eCuONN3QW20T35lpBLVZ7gCWHlEHwg6sZhUt2kV9TZTgHcKqWHyl-2GWg3Ke-YlZyn-XqjX1A7Zqy1JcsnOIJtrzJnctfBPncyrOXBzVLZSP-7FbqZMQxwY5QEI8PM8J0tpXo9GBo_nlLlY6ZrTk8wG743Obwqe5j3LWpddp6oSQRDDkP_EPKp8aGRAs6UKx-C06d8-bMxZWlUFG3c9nQFJ4fzUKvfDPqZsEjr2_f1HOsl-78qIDG2r6xFPQhPMruO.04-thUUdBtJC1MzgQRmzHg"
    headers = {'Content-type': 'application/json', "Auth-Token": authtoken}

    # Defining response for POST method
    response = requests.post(url, json=body, headers=headers)
    

    # Check the response code and display success or error message
    if response.status_code == 200:
        print(f"Success! {ukid} has been added to {classId}.")
    else:
        print(f"{ukid} couldnot be added to {classId} with status code {response.status_code}.")

    # Delay of 5 seconds
    time.sleep(5)