import requests
from requests.auth import HTTPBasicAuth
import json
import xml.etree.ElementTree as ET

SCP_url = "http://localhost/xapi/dicomscp"
SCP_headers = {"Content-Type": "application/json"}

project_url = "http://localhost/data/projects"
project_headers = {"Content-Type": "application/xml"}


with open(r"XNAT_compose\SCP_receiver.json", "r") as json_data:
    SCP_dataset = json.load(json_data)


with open(r'XNAT_compose\project.xml', 'r', encoding='utf-8') as file:
    xml_data = file.read()

for data in SCP_dataset:
    response = requests.post(SCP_url, json=data, headers=SCP_headers, auth=HTTPBasicAuth('admin', 'admin'))
    print("Status Code:", response.status_code)

root = ET.fromstring(xml_data)

namespaces = {'xnat': 'http://localhost/data/projects'}

for project in root.findall('xnat:projectData', namespaces):
    project_data = ET.tostring(project, encoding='unicode')
    response = requests.post(project_url, data=project_data, headers=project_headers, auth=HTTPBasicAuth('admin', 'admin'))
    print("Status Code:", response.status_code)
