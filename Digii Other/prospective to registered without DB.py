import pandas as pd
import requests
from datetime import datetime
import time  # for sleep

# API Details
url = "https://kishkindauniversity.digiicampus.com/rest/admission/prospectiveStudentToStudent?changeAdmissionFormStatus=true&dateOfJoining=2025-08-20"
authtoken = "eyJlbmMiOiJBMjU2R0NNIiwiYWxnIjoiZGlyIn0.._TnKdxu3wRwmQGdf.TCXDnyE1Ms_nhj6RxF1lZPk5ARkKqMrrZfWsqkNXA7s3BcUQdslc9CXl4lgG-ui_yFwdKv8hNzf8JIxG4rrzxqjR-rPZB-KzNBcFRXxinjEZ1rM0MNoUKMbgNnjbfGmd86cEwvJYSMzPaGa74MNdIyCDlDXTSeK6XwjyJpUP-wiB5O_ufoe1f1HLRAaMXjLlBzWaVfadwvctg9B4cIv27o_ES-jGRdpQzOkz3ee2PLtC9irQ4vRMG6sKcgP1eu7LW4k4PzwWXvp_dtAC59H4lDZZDqY-M1In0SZzrgqhkqQAsSYukCDgSryO5LFmgzGDbTJNBjO4WHGnW6C4UcV_GNO1iGrwT4jheDErZ1kjRRYa7Pzg-T7O1mLhlDniYSHBuYsAVKASKYt9VsfnShrcqr4-m2ExjQ8sK3YYOkIjyt-evZT2AZhvjnZf-LPxQczbQ7LX8Jn7lcsb8CtkLuNsPuzuvTxrrsd3FByaNcezHSrQwATrRdw4it1l4hos2fFA7RzL_b739g86OZbC7LPetUoQTF9GW4VU4zo6MyOoevFa-uSWrFTkOFFLBGfMtwJFOoIiPRvuFl1W5ULbHTzwAFUIFFHJSMplCyqwgvtO89_mQXWzXN9qaaNFLjaU_RbxSILbFzAhBWjQV1-tAg-TXvP9s_JrWBnimpxoZfgaQe5W4A87HmnPz84BSSHxoEBcmVTH-TNfRq2Rdxe4LYFuBstrIBo1R1HqjApzQpou9MfhuNCk-Jp_uKnpFhdC8bbPghfa2ckoXSpM04UKjNOlnBgvhTk8M5eIvi7O8lR-GeRBQofgO7ECiSAOxM56wafdauYir2l98cwbtbhv7IkI8HknInLPaqknA1qPiEY1ZX4A35yh52Vkdk_RTpK9V3lhnUhONFPmcuAC0O58KUd_9xF5BHW9eX7ZRZQP27K3pScegSUgMyVOZKMvR0G--UdcipSNpKVTh5ykdpMJFQeUFxSu6hqHSQAjJcI6aocqNiZPGQ9DlKtcMYtuxiyOw6G69zMRkBY7fUe39Vn008PLS40bwtKCaA1zNZP2xh9blMxTyhy-ffobT0JWOIZ_PKJNJwuPOkv8Wd-TE_V-h8xiyog5pKi-SYRSM7Z8rfi59b6RMR19ECG2FtbWKRG69iooFSD5zzuyhBdhtkeGhp3vQag731a_NSxEOZoEPTTyPP0AiG1zVGIXBGzyDKb59P2R8KQA1ZgoEaA0vadjFnq0iSUu76vQDYHdDTPjDyFMQqrE9d9YD2smeXz1J8mYwl_JZ4jD8zp6TfvjDEv9HLTEKWZfgWvD3DiSDuuC4_ufiu8B45s.-FdfnAmdIhbc0j_O2V-0Yg"
headers = {"Content-type": "application/json", "Auth-Token": authtoken}

# Input Excel (must have columns: ukid, categoryId)
input_file = "C:\\Users\\Suraj Shetty\\OneDrive\\Desktop\\ss.xlsx"
df = pd.read_excel(input_file)

# Create a log list
logs = []

# Loop through each row in Excel
for index, row in df.iterrows():
    ukid = row["ukid"]
    email = row["email"]
    categoryId = row["categoryId"]

    body = {
        "students": [
            {
                "ukid": ukid,        # Ensure string type
                "categoryId": categoryId
            }
        ]
    }

    try:
        response = requests.put(url, json=body, headers=headers, timeout=30)
        status = "Success" if response.status_code == 200 else "Failed"
        logs.append({
            "ukid": ukid,
            "email": email,
            "categoryId": categoryId,
            "status_code": response.status_code,
            "response": response.text,
            "status": status,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    except Exception as e:
        logs.append({
            "ukid": ukid,
            "email": email,
            "categoryId": categoryId,
            "status_code": "Error",
            "response": str(e),
            "status": "Failed",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    time.sleep(5)

# Save log to Excel
log_df = pd.DataFrame(logs)
output_file = "C:\\Users\\Suraj Shetty\\OneDrive\\Desktop\\api_log.xlsx"
log_df.to_excel(output_file, index=False)

print(f"API execution completed ✅. Log saved to {output_file}")
