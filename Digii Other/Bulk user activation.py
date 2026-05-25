import requests
import pandas as pd
import time

# Reading the Excel sheet
df = pd.read_excel("C:\\Users\\suraj\\OneDrive\\Desktop\\ukid.xlsx")

# Iterate ukid over each row from the sheet
for index, row in df.iterrows():
    ukid = row['ukid']

    # API url 
    url = f'https://demo.digiicampus.com/rest/users/activate'

    # API body for ukid
    body = str(ukid)

    # API headers and auth token
    authtoken = "eyJlbmMiOiJBMjU2R0NNIiwiYWxnIjoiZGlyIn0..oHQbBRDKYTMqrPnV.G5KbBbpELYlXi1m0hxgLA6rJtvKFRnBIzp9RmleW7MMC4vhNqV8Ft5UCjn9rQ7eLXxMq18u2IMCHyVJR8e1N2xb_E6VYGxXRLU-XqTFoX23b-LfPfbtJnqhg5OMFX4yL6rpbOooX3aNHGHvGT0_NPqeA7wOWqsmWqah65JTgPxgdKS6zlHyGPpm67lDebNPpzWe8VS5C--4vskJWUF8lCQeDuc3w2_4QhXT0KrtxaLIWqkjEqTg4HC_tpjIIom5z_VlvicB0YXnbHTFVeWb2_C5aQg1wGWZ6pYSIoVsF-cLdOpm1BQhVXF14v7ApcKBff4hn135a22dDIYLJUKJcLk_tgDwpfK0bQnLpoQ_Lmiy3DIbkm4HnO3seCU0zOwOOPq_wg0dWnuNZ9kzZy1q-Vm73SKe6jXq9kr-AUuttn7Arvx8AV8I23UHm5rqNVpV8CtPksx7m9iQRjFyLJqUd7NMxjdAvNdg6R7x1VM2-9NKfLSFiREBVr1lPjb4livsLdBHY21rEJKZvfBZhUvnEoAt7BMACclsslODBjMf3CniCktpK3HjyByqYlZKZpnn5_1Gq0TJT6CPhgeah3T7G2dbO5Ll5AecryNPaEgi_2M9Jdi0RyO4_L2YCyIOiO9Pemg-nOduLqEHVoYw4PMibzOqwVESuUqAQtvqWzyBDTBb3S5UrIIg2UECJV44528YL3vNR2lKqRk9Tm8wkmgEIj5udeZwmMbcU9pQPsvmjql8ZC35mbrptouYsxqaHaL9bnqWXwsoedcbgLTDgtUkFADYLYLx1QkojmZJ-u4jFwiGOUX2ztX4jqGA8uqlhgNbLP2nwa7eAW1twt-ZQt3BVzGKCAYjIkEGEg5kV4JL5Be90C536PIy4RDERHM1RPX_anzQI5egYhzD-sLV7pVPFyxn6kadWK_Fxx636JujDYpH8NOTe9atJw5pLEHsxCJAgqL_J4JwlO5uCz-Rd2mozurAp1fMiNMRC3rgmvLeSH-oF2nmiXTTnxztitVBL7ldnbyJ73X9Kb25REc6RzEsZWZrcUbyoTD7GLiKTUBab8tWgrhePUHwXclTNU6Pk11bClYZ4Q_LaSemWIL4A64zZxKOMJmwWze47L432aHH57DaH-dmsGx_IwV-s2F5L2Jgyh5Gk5EKO19ZCWh2NeLxQB-GIIrmaptIWSWaXLgjSeU-eeBuuZIpNermI77SwWKTdwWDIUky7ncQ2-5F5p2zeD3bW42fMRD9Ruv0zfHKiq5caJ9trMtO6pOzlg35ATulGflVjKxGzB2fNn5E02RlCKYJjCdBOCFErT3zEfbDIe_xNL9_SAH-F5dGJnymWAqtTCaLblf-vtHpcHFPt9yNB2KX1iTbCHzXcvWkqgDeCd2euFHeAqBnTC2A8S1O-5JNVTZXAwN2vhZTBWh5aJ0QB-Pv97TgFvIEludEepmQmO8b8SDb62UM0DuRAckoIzlr8vbFHPApxd-naEVkpZQ5Od8elVFtQmfOgjCrFaF05ltw7xUTGsnx1DhUo139cMdE7qACR1M3csPtGW45qNpsLMQB_l5WVfyEGESEIBd16SWJLQXD0gIBavzpB08mhmqVpXWptb-iblnxYQy44vk6JLq2Qd-PeLN6jf3XmjRwIjEMp3uIdNr_AmipgpNLYEhSiukOiZ2-uiXqahvVymrqa0G9Xy1R9ikpINgYCox8MBKv0N5CjAbtEpGy698DgSjbxAcJLqwF00iHUC_5sp1blODNurQ_Gq273paEcb_MgekcKMhJgV4kKNsIvxzsjMp9XFIrnR1Q5pdJN3hu_Pk_Omyu0DzlK1j_ubkXy-n5H52rdt_d9I2C63XKuMbthoVTK3JO15PdwCwfeDqA392h9vZJqspZbJ25tolI9s3Zjf_T1_-fbwzbUTGIAxUWf9poKvhXREb4SsR8JkzRUmT9UAgJ4TYwOuma2cYsp-UK-xgJGI7hBSliHDVMc3pEwSWlafRrrYFL9wV3WGeY-xpN2Jfr8ltAK_DTShUE4LlISMBLydMPInIqrappuqZ8fNrphzDYY4jwaSHuLj1RtHH-0S0g9aj6KT7j5uOONU9FtYEUrYpgcdqDhtoo_yXbwrmQEvP1KtnsY0hsZGrTnrkxTzqRv7qF8ClAIh-sv9d7fZ9GBGw79obW8qQ.GBJfzJtQ0fwLWl26K1ltfw"
    headers = {'Content-type': 'application/json', "auth-token": authtoken}

    # Defining response for POST method
    response = requests.put(url, body, headers=headers)
    

    # Check the response code and display success or error message
    if response.status_code == 200:
        print(f"{ukid} was successfully activated.")
    else:
        print(f"{ukid} activation was failed with status code {response.status_code}.")

    time.sleep(5)