import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import pandas as pd
import io
from datetime import datetime
import os
from pathlib import Path
import boto3
from botocore.exceptions import ClientError
from pathlib import Path
import requests
import json


AWS_REGION = "us-west-2"
_sender_address = 'Team - Digii<emailexchange@collpoll.com>'


def process_email_template(temp, r):
    for each in row.keys():
        temp = temp.replace('{{' + str(each) + '}}', str(r[each]))

    return temp


def send_email(t_type, sub, rows, tplate):
    BODY_TEXT = process_email_template(tplate, rows)
    CHARSET = 'utf-8'

    client = boto3.client('ses',
                          region_name=AWS_REGION)

    try:
        message_value = MIMEMultipart()

        if t_type == 'html':
            message_value.attach(MIMEText(BODY_TEXT.encode(CHARSET), 'html', CHARSET))
        elif t_type == 'simple':
            message_value.attach(MIMEText(BODY_TEXT.encode(CHARSET), 'plain', CHARSET))

        if 'attachment' in row and str(row['attachment']) != 'nan':
            for attachment in row['attachment'].split(','):
                with open(attachment, 'rb') as f:
                    part = MIMEApplication(f.read())
                    part.add_header('Content-Disposition', 'attachment', filename=os.path.basename(attachment))
                    message_value.attach(part)

        message_value['Subject'] = sub

        destination = row['email']
        message_value['To'] = row['email']
        if 'cc' in list(row.keys()):
            destination = destination + ',' + row['cc']
            message_value['CC'] = row['cc']
        if 'bcc' in list(row.keys()):
            destination = destination + ',' + row['bcc']
            message_value['BCC'] = row['bcc']

        message_value['From'] = _sender_address
        print(destination)
        response = client.send_raw_email(
            Destinations=destination.split(','),
            RawMessage={'Data': message_value.as_string()},
            Source=_sender_address,
        )

    except ClientError as e:
        print("\t" + e.response['Error']['Message'])
    else:
        print("\tEmail sent! Message ID:" + response['MessageId'])


def get_instance_name(url):
    req_url = "https://" + url + "/rest/service/collegeConfig?url=" + url

    payload = {}
    headers = {
        'accept': 'application/json'
    }
    
    response = requests.request("GET", req_url, headers=headers, data=payload)
    if response.status_code == 200:
        return json.loads(response.text)['name']
    else:
        return None


if __name__ == '__main__':
    try:
        instance = input('Enter complete instance url:\n')
        instance_name = get_instance_name(instance)
        # instance_name = 'bitslaw.digiicampus.com'

        if instance_name is not None:
            print('Compulsory Field- email\nOptional Field-name, registration_id, cc, bcc etc.')
            print('In order to use any field header in email template use {{field_name}} inside the template.')
            file_loc = input('Enter file location with data:\n')
            # input data file for sending emails
            if file_loc.split('.')[-1] == 'xlsx' or file_loc.split('.')[-1] == 'xls':
                df = pd.read_excel(file_loc)
            elif file_loc.split('.')[-1] == 'csv':
                df = pd.read_csv(file_loc)
            else:
                sys.exit('Unknown file format. Accepted formats are: xlsx, xls, csv')
            df['instance_name'] = instance_name

            template_type = input('Enter template type(HTML/SIMPLE):\n')
            template_loc = input('Enter email template(txt file):\n')
            # input email template
            if template_type.lower() == 'html':
                with open(template_loc, 'r', encoding='utf-8') as f:
                    template = f.read()
            elif template_type.lower() == 'simple':
                template = Path(template_loc).read_text()
            else:
                sys.exit('Unknown TEMPLATE_TYPE')

            subject = input('Enter subject for the mail:\n')
            for index, row in df.iterrows():
                print(row['email'])
                # subject = row.get('subject', 'Default Subject line')  # Fetch subject from the row or use a default value
                send_email(template_type.lower(), subject, row, template)
                # break

    except FileNotFoundError as e:
        print(e)
