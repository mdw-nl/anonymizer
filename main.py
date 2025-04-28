from config_handler import Config
from consumer import Consumer
import logging
import pandas as pd
import json
import time
import os
import pydicom
from deid.dicom import get_files, replace_identifiers
from deid.config import DeidRecipe
from deid.dicom import get_identifiers

def custom_func(item, value, field, dicom):
    # Get the current PatientID from the DICOM file
    dicom_path = os.path.join("dicomdata", "RS.PYTIM05_.dcm")
    ds = pydicom.dcmread(dicom_path)
    PatientID = ds.PatientID
    
    # Create pandas dataframe from the recipe CSV file and get the new value
    df = pd.read_csv('recipe_CSV.csv')
    new_value = df.loc[df['original'] == PatientID, 'new'].values[0]
    
    return new_value


def anonymize(ch, method, properties, body, executor):
    """The anonymize function that anonymizes the data, in the consumer method"""
    message_str = body.decode("utf-8")
    message_data = json.loads(message_str)
    input_folder = message_data.get('input_folder_path')
    output_folder = message_data.get('output_folder_path')
    recipe_path = message_data.get('recipe_path')
    action = message_data.get('action')
    
    if action != "anonymize":
        logging.info(f"Action {action} is not supported. Skipping message.")
        return
    
    # This removes all the files in the output folder, this is only for testing purposes
    for filename in os.listdir(output_folder):
        file_path = os.path.join(output_folder, filename)
        if os.path.isfile(file_path):
            os.remove(file_path)
    
    dicom_files = list(get_files(input_folder))
    recipe = DeidRecipe(deid=recipe_path)
    
    # Update the items so it contains the generate_uid function
    items = get_identifiers(dicom_files)
    for item in items:
        items[item]["custom_func"] = custom_func
         
    updated = replace_identifiers(dicom_files=dicom_files, deid=recipe, ids=items)
    
    i = 0
    for files in dicom_files:
        output_filename = f"anonymised_CT.PYTIM05_{i+1}.dcm"
        output_path = os.path.join(output_folder, output_filename)
        updated[i].save_as(output_path)
        i += 1
        
    
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger()

if __name__ == "__main__":
    rabbitMQ_config = Config("rabbitMQ")
    cons = Consumer(rmq_config=rabbitMQ_config)
    cons.open_connection_rmq()
    cons.send_message()
    cons.start_consumer(callback=anonymize)

