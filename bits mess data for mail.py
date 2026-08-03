import requests
import pandas as pd
import numpy as np
import mysql.connector
from mysql.connector import Error
import json
import time
from datetime import datetime
import calendar


def fetch_data_from_database(query, db_config):
    """Fetch data from a MySQL database using the provided query and database configuration."""
    try:
        mydb = mysql.connector.connect(
            host=db_config['host'],
            user=db_config['user'],
            passwd=db_config['password'],
            database=db_config['database']
        )

        mycursor = mydb.cursor(dictionary=True)
        mycursor.execute(query)
        raw_data = mycursor.fetchall()
        return pd.DataFrame(raw_data)
    except Error as e:
        print(f"Error: {e}")
        return pd.DataFrame()
    finally:
        if mydb.is_connected():
            mydb.close()


# Database configurations
db1_config = {
    "host": "collpolldb19-read.c5sc77nejhmr.ap-south-1.rds.amazonaws.com",
    "user": "suraj_shetty",
    "password": "LW3J0MU3mZ",
    "database": "collpoll_bitsdes"
}

db2_config = {
    "host": "collpolldb19-read.c5sc77nejhmr.ap-south-1.rds.amazonaws.com",
    "user": "suraj_shetty",
    "password": "LW3J0MU3mZ",
    "database": "collpoll_bitslaw"
}

db3_config = {
    "host": "collpolldb19-read.c5sc77nejhmr.ap-south-1.rds.amazonaws.com",
    "user": "suraj_shetty",
    "password": "LW3J0MU3mZ",
    "database": "collpoll_bitsom"
}
# Input year and month
year = input("Enter the year (YYYY): ")
month = input("Enter the month (MM): ")

# calclating the date range for the given month and year
try:
    year = int(year)
    month = int(month)
    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year}-{month:02d}-{calendar.monthrange(year, month)[1]}"
except ValueError:
    print("Invalid input. Please enter a valid year and month.")
    exit()

# Query with dynamic date range
query = f'''
SELECT t1.ukid, CONCAT(ua.f_name, ' ', ua.l_name) AS Name, ua.registration_id AS 'Registration ID', 
a.email, mm.name AS 'Mess Name', 
SUM(CASE WHEN m.name = 'Breakfast' THEN t1.meal_availed_count ELSE 0 END) AS 'Breakfast', 
SUM(CASE WHEN m.name = 'Lunch' THEN t1.meal_availed_count ELSE 0 END) AS 'Lunch', 
SUM(CASE WHEN m.name in ('Evening Snacks','Snacks') THEN t1.meal_availed_count ELSE 0 END) AS 'Evening Snacks', 
SUM(CASE WHEN m.name = 'Dinner' THEN t1.meal_availed_count ELSE 0 END) AS 'Dinner', 
SUM(t1.meal_availed_count) AS total_meals, 
YEAR(ms.date) AS year, MONTHNAME(ms.date) AS month, c.college_name AS school,
concat(CAST(reg_code_abbrev AS CHAR CHARACTER SET utf8)," Monthly Meal Consumption Report for ",MONTHNAME(ms.date)," ",YEAR(ms.date)) as subject
FROM user_mess_schedule t1 
LEFT JOIN mess_schedule ms ON ms.id = t1.mess_schedule_id 
LEFT JOIN meal m ON m.id = ms.meal_id 
LEFT JOIN mess mm ON mm.id = ms.mess_id 
LEFT JOIN user_attributes ua ON ua.ukid = t1.ukid 
LEFT JOIN authenticator a ON a.ukid = ua.ukid 
LEFT JOIN college c ON c.college_id = ua.college_id 
WHERE ms.date BETWEEN '{start_date}' AND '{end_date}' 
GROUP BY t1.ukid, mm.name 
ORDER BY ms.date;
'''


# Fetching data from both databases
df1 = fetch_data_from_database(query, db1_config)
df2 = fetch_data_from_database(query, db2_config)
df3 = fetch_data_from_database(query, db3_config)

# Combining the data from both databases
combined_df = pd.concat([df1, df2, df3], ignore_index=True)

if combined_df.empty:
    print("No data found for the given month and year.")
    exit()

month_name = calendar.month_name[month]

# Saving the combined data to an Excel file
output_file = f"C:\\Users\\suraj\\OneDrive\\Desktop\\BITS meal consumption data for {month_name} - {year}.xlsx"
combined_df.to_excel(output_file, index=False)

print(f"Data has been successfully saved to {output_file}")