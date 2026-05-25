import requests
import pandas as pd
import time

# Reading the Excel sheet
df = pd.read_excel('C:/Users/suraj/OneDrive/Desktop/id2.xlsx')

# Iterate ukid over each row from the sheet
for index, row in df.iterrows():
    duesId = row['duesId']

    # API url 
    url = f'https://demo.digiicampus.com/api/dues/v2/studentManagement/cancel'

    # API body for ukid
    body = {
        "duesId": str(duesId)
    }
    
    # API headers and auth token
    authtoken = "eyJlbmMiOiJBMjU2R0NNIiwiYWxnIjoiZGlyIn0..m-Imld1o0DwtA-Ve.70go9k6tJK5kVEUxHgRGSvM0L0Ldl8E-dkPAUfZtYi4RwvkcuCJyzQcRw_tYL6vy0lqtm9h2RsUdpIMAJDTVk3GpJSfWsl53SFvhQsIe7SM5p859cOz1yCKGUjSji-ZWjrQGz2VS7pxizrmtgDTMFXuF3LM40ICx8HTsqvBi-dwqu0dul3l5xOZ-U3HcP-3czfvCwtc8x9qQTUyAg-_vfp_eApyqpR6ABhG1zwT3ONAFbeMBHYyOcBMs0rc9GI73SKhvtn4mUmfVSqSX_5HFmco1Q9wwPc8NWPHBoQ2Aku-cA9bCnR7C0srRdCplE2ZF5jXTdrGlo2B4ZmvkOu5dy9YSS9HbiCCgAPKiHySNcBxdMtY_KO3MYvr11G1NYvT4dQhvBqX49qemJmi-Uqka5klPS9GBcLjIzxC3kYvhLJyxxgLDP0Evpwq7O1qO6S0VmyI4mTCeJHKoKTOHeCeFyBeqgzjLzvxefJwlYl4KWkvoW5tpuynJo_1ca2FraEXXtHHC-MQzz-0SVSta3GzZHID9zY5FPPP6rnXUJdJ0pfVr8-p81Dg5S9ruoVNVnFXTpaW_MzWfRAOTiIfqtwfkRbcoo412UbNhU5HpnCJdSNstiBqSxThL8gKOU7rJSNmqHMnR0-Gtqpm-8O_JqgKHiyDEGT40YGq66z097UYQWdMqgA3hwyZnf9QKv-ZWwLvIe3kJi5WkOSjaEMOF7MFKfw-0Dy7xpXUcOU0K4J7zjGQv7PCzQoU7kuaT1M_IBL-Iqi1iz07ICSH5fqV4ICdslhva1kco4ET0ju0aE03ot0QLpSCnQST3cUrYY0omraqQB-AZdx1V3XBIMPRT3w9BRy0z0giGL9qxCWNUQwyCRdlZr3TkSEgnfbM2fD7ldFPcQqbzUBTm4ugtr3DJLgfIUeQukb47iNBmHNm0DrnXBpJKgYC4oP12JXcVwf9PWyZokgdcl6P9rHlvh-50szYhyfVXzva6EfW3c3lMpTKql4VZf3F6RlV__TpL6MnUokIfdviWNCv1RUisyMSuOOdX-zXKnfKf93wfl_jClyvRDkUk8MyZxaMn1h1zMChrvEeRLBhAOYOTO8KrHTJcLrMCEGxmXgR416S8bU3o14gR63LIaGrfI4EJO2GVArdeBSVzyxS20zB-Exooe65B6x9-SGUy0JRfkvBjlvEPsuVOe7qVZNKV9JhDRap6a5BkU_ck6i5udrqFY3BtfomDuTMFokAOx6EUfWO3NitW-7qVvMIfjgYyW9qklN4xEkTm5fmbl-mPeboXgBZCudW4V25lE9ToujPHv0MtWgFo8x88foxMlYjf48t4ScF3uEI6-BvPknZ05CwWwUfSMnM3-fgMLS_V38hJHDUEVwnzcSKQobVQe4TpMPM-Zj94iYGikTIkYsVagkToPxgig01MGpSavjKGIqn1SlMfk2I1TAggLq4Oae8S8gDm5nFrIWpfblH25-YHu3FqAsh0lGcMwP2JGpVjqtjpGzeO5dMNFRA3kqg6hOwvJXPScwlKGO9Ef13GAA5bNF0NXnKEWWm0WGQsZZ3l065VasLTm58VHLpbcOVTOfn8giqGnZW_u4kITk6an0BlR9UB9h-wWojSSoJKeUTf4_cBhyFwF3ngcvWhFBMBxJujQ03c4-VHdFk3AJzQY0q0Ih4nHBaXfacOMpvqG7GImPDeOHoWvum2FaLWJoEZJYug8kOD--6t2JSDFP-6QwcSr3f8EVKmMsXLlGsNewwPBqg0Z13V-vD3sIdo-qJCv8-QvF99_msBoGpyFAhoKaOIQd8h_MjEPTO1cDh4ei-SzM7JIylUroK4vb6S70AEj40WENEBxnhJElWA9g-3ZsWFVRGTsCghtgmvV_J6pc_jinMwUnzUDDpKNxceWkAvQGTz5jOpmQG5coV4Obh5NCpF2HXJEiZJOeX3-SRp707GkpkwQ3M_ujJJwbA8bt_vryfMJbdKzDw3v4FTbx0kMOdBsIh5EpDTdMexIfKKDXz-JPSoy-tG55ip_H2_E3Fx8J_8cpLPdBUpy1eyil23n4GpCUaJ2c8AJAnf0qbej_0h53ZYRYlO7HY5E7bncAuseTg_u96vyKiUkm52qRKV36lEjFhs6fExBcvO27Sb6bGiO1OeoshrsDawquxnWfGzUlXk7kPYFj1F4LBLeIu9hr4GSiwc7jj_HWTsJMR7KVypKzkUdOKG771P_cojW2Q.QoZmml6s26bAREAIiY8U_w"
    headers = {'Content-type': 'application/json', "auth-token": authtoken}

    # Defining response for POST method
    response = requests.put(url, json=body, headers=headers)
    

    # Check the response code and display success or error message
    if response.status_code == 200:
        print(f"{duesId} was successfully cancelled.")
    else:
        print(f"Cancellation of due id {duesId} was failed with status code {response.status_code}.")

    time.sleep(10)