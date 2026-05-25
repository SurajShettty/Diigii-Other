import os
from openpyxl import Workbook

def get_files_in_folder(folder_path):
    files = os.listdir(folder_path)
    return [file for file in files if os.path.isfile(os.path.join(folder_path, file))]

def export_to_excel(file_names, excel_file_path):
    wb = Workbook()
    ws = wb.active
    ws.append(["File Names"])
    for file_name in file_names:
        ws.append([file_name])
    wb.save(excel_file_path)

if __name__ == "__main__":
    folder_path = input("Enter the path of the folder: ")
    file_names = get_files_in_folder(folder_path)
    excel_file_path = 'C:\\Users\\Suraj Shetty\\OneDrive\\Desktop\\Filess.xlsx'
    export_to_excel(file_names, excel_file_path)
    print("File names exported to Excel successfully.")


# C:\Users\Suraj Shetty\OneDrive\Desktop